from __future__ import annotations

import datetime as dt
import ipaddress
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


RSA_KEY_SIZE = 2048
HASH_ALGORITHM = hashes.SHA256()


def _generate_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=RSA_KEY_SIZE)


def _write_key(path: Path, key: rsa.RSAPrivateKey) -> None:
    path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )


def _write_cert(path: Path, cert: x509.Certificate) -> None:
    path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))


def _build_name(common_name: str) -> x509.Name:
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])


def _fingerprint(cert: x509.Certificate) -> str:
    return f"sha256:{cert.fingerprint(hashes.SHA256()).hex()}"


def create_test_ca(base_dir: Path, common_name: str = "llm-memory-test-ca") -> dict[str, str]:
    base_dir.mkdir(parents=True, exist_ok=True)
    key = _generate_key()
    subject = issuer = _build_name(common_name)
    now = dt.datetime.now(dt.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5))
        .not_valid_after(now + dt.timedelta(days=7))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(x509.KeyUsage(
            digital_signature=True,
            key_encipherment=False,
            key_cert_sign=True,
            crl_sign=True,
            content_commitment=False,
            data_encipherment=False,
            key_agreement=False,
            encipher_only=False,
            decipher_only=False,
        ), critical=True)
        .sign(key, HASH_ALGORITHM)
    )

    cert_path = base_dir / "ca.crt"
    key_path = base_dir / "ca.key"
    _write_cert(cert_path, cert)
    _write_key(key_path, key)
    return {
        "cert_path": str(cert_path),
        "key_path": str(key_path),
        "common_name": common_name,
        "fingerprint": _fingerprint(cert),
    }


def issue_cert(
    base_dir: Path,
    ca_cert_path: Path,
    ca_key_path: Path,
    *,
    common_name: str,
    cert_filename: str,
    key_filename: str,
    is_client: bool,
    san_dns: list[str] | None = None,
    san_ips: list[str] | None = None,
) -> dict[str, str]:
    base_dir.mkdir(parents=True, exist_ok=True)
    ca_cert = x509.load_pem_x509_certificate(ca_cert_path.read_bytes())
    ca_key = serialization.load_pem_private_key(ca_key_path.read_bytes(), password=None)
    key = _generate_key()
    subject = _build_name(common_name)
    now = dt.datetime.now(dt.timezone.utc)

    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5))
        .not_valid_after(now + dt.timedelta(days=3))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.KeyUsage(
            digital_signature=True,
            key_encipherment=True,
            key_cert_sign=False,
            crl_sign=False,
            content_commitment=False,
            data_encipherment=False,
            key_agreement=False,
            encipher_only=False,
            decipher_only=False,
        ), critical=True)
        .add_extension(
            x509.ExtendedKeyUsage(
                [ExtendedKeyUsageOID.CLIENT_AUTH if is_client else ExtendedKeyUsageOID.SERVER_AUTH]
            ),
            critical=False,
        )
    )

    general_names: list[x509.GeneralName] = []
    for dns_name in san_dns or []:
        general_names.append(x509.DNSName(dns_name))
    for ip in san_ips or []:
        general_names.append(x509.IPAddress(ipaddress.ip_address(ip)))
    if general_names:
        builder = builder.add_extension(x509.SubjectAlternativeName(general_names), critical=False)

    cert = builder.sign(ca_key, HASH_ALGORITHM)

    cert_path = base_dir / cert_filename
    key_path = base_dir / key_filename
    _write_cert(cert_path, cert)
    _write_key(key_path, key)

    # Also write fullchain (cert + CA cert) for TLS servers
    fullchain_path = base_dir / cert_filename.replace(".crt", "-fullchain.crt")
    fullchain_content = (
        cert.public_bytes(serialization.Encoding.PEM) +
        ca_cert.public_bytes(serialization.Encoding.PEM)
    )
    fullchain_path.write_bytes(fullchain_content)

    return {
        "cert_path": str(cert_path),
        "key_path": str(key_path),
        "fullchain_path": str(fullchain_path),
        "fingerprint": _fingerprint(cert),
        "subject": cert.subject.rfc4514_string(),
        "serial": format(cert.serial_number, "x"),
        "issuer": cert.issuer.rfc4514_string(),
        "not_before": cert.not_valid_before_utc.isoformat(),
        "not_after": cert.not_valid_after_utc.isoformat(),
    }
