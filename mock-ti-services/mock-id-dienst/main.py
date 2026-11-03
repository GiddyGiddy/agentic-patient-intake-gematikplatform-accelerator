"""Minimal mock of an OIDC identity provider (gematik Gesundheits-ID). Dev only."""
import json
import time

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from jwt.algorithms import RSAAlgorithm

ISSUER = "http://mock-id-dienst:8081"
AUDIENCE = "patient-intake"
KID = "mock-key-1"

_private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_jwk = {
    **json.loads(RSAAlgorithm.to_jwk(_private.public_key())),
    "kid": KID,
    "use": "sig",
    "alg": "RS256",
}

app = FastAPI(title="Mock ID-Dienst")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], allow_methods=["*"], allow_headers=["*"])


@app.get("/.well-known/openid-configuration")
def discovery():
    return {
        "issuer": ISSUER,
        "jwks_uri": f"{ISSUER}/jwks",
        "token_endpoint": f"{ISSUER}/token",
    }


@app.get("/jwks")
def jwks():
    return {"keys": [_jwk]}


@app.post("/token")
def token(sub: str = "X110000001"):
    """Issues a token for a fake KVNR (Krankenversichertennummer)."""
    now = int(time.time())
    access = jwt.encode(
        {"iss": ISSUER, "aud": AUDIENCE, "sub": sub, "iat": now, "exp": now + 3600},
        _private,
        algorithm="RS256",
        headers={"kid": KID},
    )
    return {"access_token": access, "token_type": "Bearer", "expires_in": 3600}
