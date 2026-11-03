"""Mock TI gateway (simulated HSM-B / SMC-B).

Reverse proxy in front of the FHIR/ePA mock. Per request it:
  * keeps the patient's Gesundheits-ID bearer token untouched (Authorization),
  * adds X-TI-Telematik-ID (institution identity) and
  * adds X-SMCB-Assertion: a short-lived RS256 JWT signed with the simulated SMC-B key
    (the certificate is embedded as x5c so a receiver can verify it).
In production the key lives in a HSM at the gateway provider (RISE, CGM, ...); here it is generated
at start-up (or loaded from certs/) so no private key is ever committed.
"""
import datetime
import logging
import os
import uuid
from pathlib import Path

import httpx
import jwt
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from fastapi import FastAPI, Request, Response

log = logging.getLogger("ti-gateway")
logging.basicConfig(level=logging.INFO)

UPSTREAM = os.getenv("UPSTREAM_FHIR_URL", "http://mock-kis-fhir:8080/fhir").rstrip("/")
TELEMATIK_ID = os.getenv("TELEMATIK_ID", "1-1.2.3.4.5.KlinikKoeln")  # format of a real Telematik-ID
AUDIENCE = os.getenv("ASSERTION_AUDIENCE", "gematik-epa-fachdienst")
CERT_DIR = Path(os.getenv("CERT_DIR", "certs"))
TRANSPORT: httpx.AsyncBaseTransport | None = None  # replaced in tests

HOP_BY_HOP = {"host", "content-length", "connection", "transfer-encoding", "accept-encoding"}


def _load_or_create_identity() -> tuple[bytes, x509.Certificate]:
    key_file, cert_file = CERT_DIR / "smcb_key.pem", CERT_DIR / "smcb_cert.pem"
    if key_file.exists() and cert_file.exists():
        return key_file.read_bytes(), x509.load_pem_x509_certificate(cert_file.read_bytes())
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, "Klinik-Koeln-SMCB"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Gematik-Test"),
            x509.NameAttribute(NameOID.COUNTRY_NAME, "DE"),
        ]
    )
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=365))
        .sign(key, hashes.SHA256())
    )
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return pem, cert


PRIVATE_KEY, CERT = _load_or_create_identity()
CERT_B64 = __import__("base64").b64encode(CERT.public_bytes(serialization.Encoding.DER)).decode()

app = FastAPI(title="Simuliertes gematik TI-Gateway")


def make_assertion() -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "iss": TELEMATIK_ID,
        "sub": TELEMATIK_ID,
        "aud": AUDIENCE,
        "iat": now,
        "exp": now + datetime.timedelta(minutes=5),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, PRIVATE_KEY, algorithm="RS256", headers={"x5c": [CERT_B64]})


@app.get("/health")
def health():
    return {"status": "ok", "telematik_id": TELEMATIK_ID}


@app.api_route("/fhir/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy_to_ti(path: str, request: Request):
    log.info("request %s /fhir/%s", request.method, path)
    headers = {k: v for k, v in request.headers.items() if k.lower() not in HOP_BY_HOP}
    headers["X-TI-Telematik-ID"] = TELEMATIK_ID
    headers["X-SMCB-Assertion"] = make_assertion()
    log.info("signed with SMC-B key, telematik-id=%s", TELEMATIK_ID)
    try:
        async with httpx.AsyncClient(transport=TRANSPORT, timeout=30) as client:
            upstream = await client.request(
                request.method,
                f"{UPSTREAM}/{path}",
                headers=headers,
                content=await request.body(),
                params=request.query_params,
            )
    except httpx.HTTPError as exc:
        log.warning("upstream failure: %s", type(exc).__name__)
        return Response(f"TI routing error: {type(exc).__name__}", status_code=502)
    out = {k: v for k, v in upstream.headers.items() if k.lower() in ("content-type", "location", "etag")}
    return Response(upstream.content, status_code=upstream.status_code, headers=out)
