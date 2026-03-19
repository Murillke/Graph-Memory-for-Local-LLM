"""
Security enforcement for network MCP.

- Identity spoofing detection
- Person entity sanitization
- Ban logic with exponential backoff
- Violations recorded in graph (durable forever)
- Signed authorship claims (Phase 2)
"""

import base64
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.x509 import load_pem_x509_certificate
from cryptography.exceptions import InvalidSignature

# Base ban duration: 10 minutes
BASE_BAN_MINUTES = 10

# Pattern for cert-like identifiers that clients might try to spoof
CERT_ID_PATTERN = re.compile(r"^(cert:|sha256:|fingerprint:)", re.IGNORECASE)


def is_cert_id_claim(name: str) -> bool:
    """Check if a name looks like a cert ID claim."""
    return bool(CERT_ID_PATTERN.match(name.strip()))


def extract_claimed_fingerprint(name: str) -> Optional[str]:
    """Extract fingerprint from a cert ID claim."""
    name = name.strip().lower()
    for prefix in ("cert:", "sha256:", "fingerprint:"):
        if name.startswith(prefix):
            return name[len(prefix):].strip()
    return None


def sanitize_person_entities(
    extraction: Dict[str, Any],
    actual_fingerprint: str,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Sanitize Person entities in extraction payload.
    
    Returns:
        (sanitized_extraction, violations)
        
    Violations list contains any spoofing attempts detected.
    """
    violations = []
    sanitized = extraction.copy()
    short_fp = actual_fingerprint[:12] if actual_fingerprint else "unknown"
    
    if "extractions" not in sanitized:
        return sanitized, violations
    
    for ext in sanitized.get("extractions", []):
        if "entities" not in ext:
            continue
            
        for entity in ext.get("entities", []):
            if entity.get("type", "").lower() != "person":
                continue
            
            name = entity.get("name", "")
            
            if is_cert_id_claim(name):
                # Client is claiming a cert identity
                claimed_fp = extract_claimed_fingerprint(name)
                if claimed_fp and claimed_fp.lower() != actual_fingerprint.lower()[:len(claimed_fp)]:
                    # SPOOFING ATTEMPT - claimed ID doesn't match actual cert
                    violations.append({
                        "type": "identity_spoofing",
                        "claimed_identity": name,
                        "actual_fingerprint": actual_fingerprint,
                        "entity_name": name,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                # Replace with actual fingerprint regardless
                entity["name"] = f"cert:{short_fp}"
                entity["_original_name"] = name
                entity["_sanitized"] = True
            else:
                # Human name - sanitize to cert fingerprint
                entity["name"] = f"cert:{short_fp}"
                entity["_original_name"] = name  
                entity["_sanitized"] = True
    
    return sanitized, violations


def calculate_ban_duration(violation_count: int) -> timedelta:
    """
    Calculate ban duration with exponential backoff.
    
    1st offense: 10 min
    2nd offense: 20 min
    3rd offense: 40 min
    ... no limit
    """
    if violation_count <= 0:
        return timedelta(minutes=0)
    return timedelta(minutes=BASE_BAN_MINUTES * (2 ** (violation_count - 1)))


def is_fingerprint_banned(
    graph_db,
    fingerprint: str,
) -> Tuple[bool, Optional[datetime], Optional[int]]:
    """
    Check if a fingerprint is currently banned.
    
    Returns:
        (is_banned, ban_expires_at, violation_count)
    """
    # Query graph for violations by this fingerprint
    violations = graph_db.query_entities_by_attribute(
        "client_cert_fingerprint", fingerprint, entity_type="SecurityViolation"
    ) if hasattr(graph_db, 'query_entities_by_attribute') else []
    
    if not violations:
        return False, None, 0
    
    # Get violation count and last violation time
    violation_count = len(violations)
    
    # Find most recent violation
    latest = None
    for v in violations:
        attrs = v.get("attributes", {})
        ts_str = attrs.get("timestamp")
        if ts_str:
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                if latest is None or ts > latest:
                    latest = ts
            except (ValueError, TypeError):
                pass
    
    if latest is None:
        return False, None, violation_count
    
    # Calculate if still banned
    ban_duration = calculate_ban_duration(violation_count)
    ban_expires = latest + ban_duration
    now = datetime.now(timezone.utc)
    
    if now < ban_expires:
        return True, ban_expires, violation_count
    
    return False, None, violation_count


def record_violation(
    graph_db,
    project_name: str,
    fingerprint: str,
    violation: Dict[str, Any],
) -> str:
    """Record a security violation in the graph (durable forever)."""
    import uuid
    
    violation_uuid = f"entity-{uuid.uuid4().hex[:12]}"
    timestamp = violation.get("timestamp", datetime.now(timezone.utc).isoformat())
    
    graph_db.create_entity(
        name=f"violation:{fingerprint[:8]}:{timestamp[:10]}",
        entity_type="SecurityViolation",
        group_id=project_name,
        uuid_override=violation_uuid,
        source_interactions=[],
        source_hashes=[],
        extraction_version="security-v1",
        extraction_commit="",
        summary=f"Identity spoofing attempt: claimed {violation.get('claimed_identity', 'unknown')}",
        event_timestamp=timestamp,
        attributes={
            "client_cert_fingerprint": fingerprint,
            "violation_type": violation.get("type", "unknown"),
            "claimed_identity": violation.get("claimed_identity"),
            "actual_fingerprint": violation.get("actual_fingerprint"),
            "timestamp": timestamp,
        },
    )
    
    return violation_uuid


# ============================================================================
# Phase 2: Signed Authorship Claims
# ============================================================================

def create_authorship_claim(
    entity_or_fact_uuid: str,
    claim_type: str = "authored",
) -> Dict[str, Any]:
    """
    Create an authorship claim to be signed by the client.

    The client should:
    1. Call this to get the claim structure
    2. Sign the canonical JSON with their private key
    3. Submit the claim + signature to verify_and_store_authorship_claim
    """
    return {
        "target_uuid": entity_or_fact_uuid,
        "claim_type": claim_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def canonicalize_claim(claim: Dict[str, Any]) -> bytes:
    """Convert claim to canonical bytes for signing/verification."""
    # Sort keys for deterministic serialization
    return json.dumps(claim, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_claim(claim: Dict[str, Any], private_key_pem: bytes) -> str:
    """
    Sign a claim with a private key. (Client-side helper)

    Returns base64-encoded signature.
    """
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    private_key = load_pem_private_key(private_key_pem, password=None)
    canonical = canonicalize_claim(claim)

    signature = private_key.sign(
        canonical,
        padding.PKCS1v15(),
        hashes.SHA256(),
    )

    return base64.b64encode(signature).decode("ascii")


def verify_signature(
    claim: Dict[str, Any],
    signature_b64: str,
    cert_pem: bytes,
) -> Tuple[bool, str]:
    """
    Verify a signature against a certificate's public key.

    Returns (is_valid, error_message).
    """
    try:
        cert = load_pem_x509_certificate(cert_pem)
        public_key = cert.public_key()
        signature = base64.b64decode(signature_b64)
        canonical = canonicalize_claim(claim)

        public_key.verify(
            signature,
            canonical,
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return True, ""
    except InvalidSignature:
        return False, "Invalid signature - does not match certificate"
    except Exception as e:
        return False, f"Verification failed: {e}"


def verify_and_store_authorship_claim(
    graph_db,
    project_name: str,
    claim: Dict[str, Any],
    signature_b64: str,
    cert_fingerprint: str,
    cert_pem: Optional[bytes] = None,
) -> Tuple[bool, str, Optional[str]]:
    """
    Verify a signed authorship claim and store it in the graph.

    Args:
        graph_db: Graph database instance
        project_name: Project name
        claim: The claim dict (target_uuid, claim_type, timestamp)
        signature_b64: Base64-encoded signature
        cert_fingerprint: Fingerprint of the signing certificate
        cert_pem: PEM-encoded certificate (for signature verification)

    Returns:
        (success, message, claim_uuid)
    """
    import uuid as uuid_mod

    # Verify required fields
    target_uuid = claim.get("target_uuid")
    claim_type = claim.get("claim_type", "authored")
    timestamp = claim.get("timestamp")

    if not target_uuid:
        return False, "Missing target_uuid in claim", None
    if not timestamp:
        return False, "Missing timestamp in claim", None

    # Verify signature if cert provided
    if cert_pem:
        is_valid, error = verify_signature(claim, signature_b64, cert_pem)
        if not is_valid:
            return False, error, None

    # Check target exists
    # (In production, verify target_uuid exists in graph)

    # Create AuthorshipClaim entity
    claim_uuid = f"entity-{uuid_mod.uuid4().hex[:12]}"

    graph_db.create_entity(
        name=f"claim:{cert_fingerprint[:8]}:{target_uuid[-8:]}",
        entity_type="AuthorshipClaim",
        group_id=project_name,
        uuid_override=claim_uuid,
        source_interactions=[],
        source_hashes=[],
        extraction_version="authorship-v1",
        extraction_commit="",
        summary=f"Authorship claim by cert:{cert_fingerprint[:12]} for {target_uuid}",
        event_timestamp=timestamp,
        attributes={
            "target_uuid": target_uuid,
            "claim_type": claim_type,
            "claimant_fingerprint": cert_fingerprint,
            "signature": signature_b64,
            "timestamp": timestamp,
            "verified": cert_pem is not None,
        },
    )

    # Create relationship: AuthorshipClaim -[REFERENCES]-> Target
    # (The graph_db.create_fact would do this, but we store it in attributes for simplicity)

    return True, "Authorship claim recorded", claim_uuid


def get_authorship_claims(
    graph_db,
    target_uuid: str,
) -> List[Dict[str, Any]]:
    """
    Get all authorship claims for a target entity/fact.
    """
    claims = graph_db.query_entities_by_attribute(
        "target_uuid", target_uuid, entity_type="AuthorshipClaim"
    ) if hasattr(graph_db, 'query_entities_by_attribute') else []

    return [
        {
            "claim_uuid": c.get("uuid"),
            "claimant_fingerprint": c.get("attributes", {}).get("claimant_fingerprint"),
            "claim_type": c.get("attributes", {}).get("claim_type"),
            "timestamp": c.get("attributes", {}).get("timestamp"),
            "verified": c.get("attributes", {}).get("verified"),
        }
        for c in claims
    ]
