import asyncio
import importlib.util
from pathlib import Path

import httpx
import jwt
import pytest
from cryptography import x509

GATEWAY = Path(__file__).resolve().parents[2] / "mock-ti-services" / "mock-ti-gateway" / "gateway.py"


@pytest.fixture(scope="module")
def gw():
    spec = importlib.util.spec_from_file_location("ti_gateway", GATEWAY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_proxy_signs_and_keeps_patient_token(gw):
    seen = {}

    def upstream(request: httpx.Request) -> httpx.Response:
        seen["headers"] = request.headers
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"resourceType": "Bundle"})

    gw.TRANSPORT = httpx.MockTransport(upstream)

    async def call():
        transport = httpx.ASGITransport(app=gw.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://gw") as c:
            return await c.get(
                "/fhir/MedicationStatement?status=active", headers={"Authorization": "Bearer patient-token"}
            )

    r = asyncio.run(call())
    assert r.status_code == 200 and r.json()["resourceType"] == "Bundle"
    assert seen["headers"]["authorization"] == "Bearer patient-token"
    assert seen["headers"]["x-ti-telematik-id"] == gw.TELEMATIK_ID
    assert "status=active" in seen["url"]

    assertion = seen["headers"]["x-smcb-assertion"]
    cert = x509.load_der_x509_certificate(
        __import__("base64").b64decode(jwt.get_unverified_header(assertion)["x5c"][0])
    )
    claims = jwt.decode(assertion, cert.public_key(), algorithms=["RS256"], audience=gw.AUDIENCE)
    assert claims["iss"] == gw.TELEMATIK_ID


def test_upstream_down_gives_502(gw):
    def down(request):
        raise httpx.ConnectError("x")

    gw.TRANSPORT = httpx.MockTransport(down)

    async def call():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=gw.app), base_url="http://gw") as c:
            return await c.get("/fhir/Patient")

    assert asyncio.run(call()).status_code == 502
