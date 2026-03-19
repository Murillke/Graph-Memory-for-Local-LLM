"""
Starlette routes for certificate enrollment.

Mount these on your Starlette app to enable curl-friendly enrollment.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Optional

from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import JSONResponse

from mcp_server.enrollment import (
    create_enrollment_record,
    sign_csr,
    get_cert_fingerprint,
)
from tools.config import load_config

# In-memory token store (replace with SQL for production)
_enrollment_records: dict[str, dict] = {}


def _get_admin_key() -> Optional[str]:
    """Get admin key from config."""
    try:
        config = load_config()
        return config.raw.get("enrollment", {}).get("admin_key")
    except Exception:
        return None


async def create_token(request: Request) -> JSONResponse:
    """
    Create a one-time enrollment token (admin only).

    curl -X POST http://localhost:8080/enroll/tokens \
        -H "X-Admin-Key: $ADMIN_KEY" \
        -H "Content-Type: application/json" \
        -d '{"name": "alice"}'
    """
    admin_key = _get_admin_key()
    req_key = request.headers.get("X-Admin-Key")
    if not admin_key or req_key != admin_key:
        return JSONResponse({"error": "Invalid admin key"}, status_code=403)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    name = body.get("name")
    if not name:
        return JSONResponse({"error": "name is required"}, status_code=400)

    record = create_enrollment_record(
        name=name,
        activation_delay_hours=body.get("activation_delay_hours", 0),
        validity_days=body.get("validity_days", 90),
    )

    _enrollment_records[record["token_hash"]] = record

    return JSONResponse({
        "token": record["token_plaintext"],
        "name": record["name"],
        "activation_delay_hours": record["activation_delay_hours"],
        "validity_days": record["validity_days"],
        "message": "Save this token securely. It cannot be retrieved again.",
    })


async def submit_csr(request: Request) -> JSONResponse:
    """
    Submit CSR and receive signed certificate.

    curl -X POST http://localhost:8080/enroll/csr \
        -H "X-Enrollment-Token: $TOKEN" \
        -H "Content-Type: application/x-pem-file" \
        --data-binary @client.csr
    """
    token = request.headers.get("X-Enrollment-Token")
    if not token:
        return JSONResponse({"error": "X-Enrollment-Token header required"}, status_code=400)

    token_hash = hashlib.sha256(token.encode()).hexdigest()
    record = _enrollment_records.get(token_hash)

    if not record:
        return JSONResponse({"error": "Invalid or expired token"}, status_code=404)

    if record["used"]:
        return JSONResponse({"error": "Token already used"}, status_code=410)

    csr_pem = await request.body()
    if not csr_pem:
        return JSONResponse({"error": "CSR body required"}, status_code=400)

    try:
        config = load_config()
        ca_cert = config.raw.get("enrollment", {}).get("ca_cert_path")
        ca_key = config.raw.get("enrollment", {}).get("ca_key_path")
        if not ca_cert or not ca_key:
            return JSONResponse({"error": "CA not configured"}, status_code=500)
    except Exception as e:
        return JSONResponse({"error": f"Config error: {e}"}, status_code=500)

    try:
        cert_pem = sign_csr(
            csr_pem=csr_pem,
            ca_cert_path=ca_cert,
            ca_key_path=ca_key,
            validity_days=record["validity_days"],
            not_before_delay_hours=record["activation_delay_hours"],
        )
    except Exception as e:
        return JSONResponse({"error": f"CSR signing failed: {e}"}, status_code=400)

    record["used"] = True
    record["used_at"] = datetime.now(timezone.utc).isoformat()

    from cryptography import x509
    cert = x509.load_pem_x509_certificate(cert_pem)

    return JSONResponse({
        "certificate": cert_pem.decode(),
        "fingerprint": get_cert_fingerprint(cert_pem),
        "subject": cert.subject.rfc4514_string(),
        "not_before": cert.not_valid_before_utc.isoformat(),
        "not_after": cert.not_valid_after_utc.isoformat(),
    })


# Starlette routes
enrollment_routes = [
    Route("/enroll/tokens", create_token, methods=["POST"]),
    Route("/enroll/csr", submit_csr, methods=["POST"]),
]

