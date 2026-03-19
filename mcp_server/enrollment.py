"""
Certificate Enrollment API - curl-friendly, no UI needed.

Flow:
1. Admin creates enrollment token: POST /enroll/tokens
2. User generates local key + CSR
3. User submits CSR with token: POST /enroll/csr
4. User gets signed cert back

Example:
    # Admin creates token
    curl -X POST http://localhost:8080/enroll/tokens \
        -H "X-Admin-Key: $ADMIN_KEY" \
        -d '{"name": "alice", "activation_delay_hours": 0}'
    
    # User generates key + CSR locally
    openssl genrsa -out client.key 2048
    openssl req -new -key client.key -out client.csr -subj "/CN=alice"
    
    # User submits CSR
    curl -X POST http://localhost:8080/enroll/csr \
        -H "X-Enrollment-Token: $TOKEN" \
        -F "csr=@client.csr"
    
    # Response: signed certificate PEM
"""

import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from tools.config import load_config


def generate_enrollment_token() -> str:
    """Generate a secure one-time enrollment token."""
    return secrets.token_urlsafe(32)


def create_enrollment_record(
    name: str,
    activation_delay_hours: int = 0,
    validity_days: int = 90,
) -> dict:
    """
    Create an enrollment record with a one-time token.
    
    Returns dict with token and metadata. Store this securely.
    """
    token = generate_enrollment_token()
    now = datetime.now(timezone.utc)
    
    return {
        "token_hash": hashlib.sha256(token.encode()).hexdigest(),
        "token_plaintext": token,  # Only returned once, never stored
        "name": name,
        "created_at": now.isoformat(),
        "activation_delay_hours": activation_delay_hours,
        "validity_days": validity_days,
        "used": False,
        "used_at": None,
    }


def sign_csr(
    csr_pem: bytes,
    ca_cert_path: str,
    ca_key_path: str,
    validity_days: int = 90,
    not_before_delay_hours: int = 0,
) -> bytes:
    """
    Sign a CSR with the CA key.
    
    Args:
        csr_pem: PEM-encoded CSR from client
        ca_cert_path: Path to CA certificate
        ca_key_path: Path to CA private key
        validity_days: Certificate validity period
        not_before_delay_hours: Delay before cert becomes valid
        
    Returns:
        PEM-encoded signed certificate
    """
    # Load CSR
    csr = x509.load_pem_x509_csr(csr_pem)
    
    # Load CA
    ca_cert = x509.load_pem_x509_certificate(Path(ca_cert_path).read_bytes())
    ca_key = serialization.load_pem_private_key(
        Path(ca_key_path).read_bytes(),
        password=None,
    )
    
    # Build certificate
    now = datetime.now(timezone.utc)
    not_before = now + timedelta(hours=not_before_delay_hours)
    not_after = not_before + timedelta(days=validity_days)
    
    builder = (
        x509.CertificateBuilder()
        .subject_name(csr.subject)
        .issuer_name(ca_cert.subject)
        .public_key(csr.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before)
        .not_valid_after(not_after)
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=True,
                content_commitment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH]),
            critical=False,
        )
    )
    
    cert = builder.sign(ca_key, hashes.SHA256())
    return cert.public_bytes(serialization.Encoding.PEM)


def get_cert_fingerprint(cert_pem: bytes) -> str:
    """Get SHA256 fingerprint of a certificate."""
    cert = x509.load_pem_x509_certificate(cert_pem)
    return cert.fingerprint(hashes.SHA256()).hex()

