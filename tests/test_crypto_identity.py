"""
Tests for crypto identity enforcement (c3ed4ce).

Phase 1: Person sanitization, spoofing detection, ban policy
Phase 2: Signed authorship claims
"""

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from mcp_server.security import (
    # Phase 1
    is_cert_id_claim,
    extract_claimed_fingerprint,
    sanitize_person_entities,
    calculate_ban_duration,
    # Phase 2
    create_authorship_claim,
    canonicalize_claim,
    sign_claim,
    verify_signature,
)
from tests.helpers.tls_certs import create_test_ca, issue_cert


class TestPhase1PersonSanitization(unittest.TestCase):
    """Tests for Person entity sanitization."""

    def test_is_cert_id_claim_detects_cert_prefix(self):
        self.assertTrue(is_cert_id_claim("cert:abc123"))
        self.assertTrue(is_cert_id_claim("sha256:abc123"))
        self.assertTrue(is_cert_id_claim("fingerprint:abc123"))
        self.assertTrue(is_cert_id_claim("CERT:ABC123"))  # Case insensitive

    def test_is_cert_id_claim_rejects_human_names(self):
        self.assertFalse(is_cert_id_claim("John Smith"))
        self.assertFalse(is_cert_id_claim("Alice"))
        self.assertFalse(is_cert_id_claim("certificate_holder"))

    def test_extract_claimed_fingerprint(self):
        self.assertEqual(extract_claimed_fingerprint("cert:abc123"), "abc123")
        self.assertEqual(extract_claimed_fingerprint("sha256:xyz"), "xyz")
        self.assertEqual(extract_claimed_fingerprint("fingerprint:def456"), "def456")

    def test_sanitize_person_replaces_human_name(self):
        extraction = {
            "extractions": [
                {"entities": [{"name": "John Smith", "type": "Person"}]}
            ]
        }
        sanitized, violations = sanitize_person_entities(extraction, "abc123def456")
        
        self.assertEqual(len(violations), 0)
        self.assertEqual(
            sanitized["extractions"][0]["entities"][0]["name"],
            "cert:abc123def456"
        )
        self.assertTrue(sanitized["extractions"][0]["entities"][0]["_sanitized"])

    def test_sanitize_person_detects_spoofing(self):
        extraction = {
            "extractions": [
                {"entities": [{"name": "cert:WRONGFINGERPRINT", "type": "Person"}]}
            ]
        }
        sanitized, violations = sanitize_person_entities(extraction, "abc123def456")
        
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]["type"], "identity_spoofing")
        self.assertIn("WRONGFINGERPRINT", violations[0]["claimed_identity"])

    def test_sanitize_person_allows_matching_cert_id(self):
        extraction = {
            "extractions": [
                {"entities": [{"name": "cert:abc123", "type": "Person"}]}
            ]
        }
        sanitized, violations = sanitize_person_entities(extraction, "abc123def456")
        
        self.assertEqual(len(violations), 0)  # No spoofing - prefix matches

    def test_sanitize_ignores_non_person_entities(self):
        extraction = {
            "extractions": [
                {"entities": [{"name": "MyProject", "type": "Project"}]}
            ]
        }
        sanitized, violations = sanitize_person_entities(extraction, "abc123")
        
        self.assertEqual(sanitized["extractions"][0]["entities"][0]["name"], "MyProject")


class TestPhase1BanPolicy(unittest.TestCase):
    """Tests for exponential ban policy."""

    def test_ban_duration_first_offense(self):
        self.assertEqual(calculate_ban_duration(1), timedelta(minutes=10))

    def test_ban_duration_doubles(self):
        self.assertEqual(calculate_ban_duration(2), timedelta(minutes=20))
        self.assertEqual(calculate_ban_duration(3), timedelta(minutes=40))
        self.assertEqual(calculate_ban_duration(4), timedelta(minutes=80))

    def test_ban_duration_no_limit(self):
        # 10th offense = 10 * 2^9 = 5120 minutes = ~3.5 days
        self.assertEqual(calculate_ban_duration(10), timedelta(minutes=5120))
        # 20th offense = 10 * 2^19 = 5242880 minutes = ~10 years
        self.assertGreater(calculate_ban_duration(20), timedelta(days=3600))

    def test_ban_duration_zero_offenses(self):
        self.assertEqual(calculate_ban_duration(0), timedelta(minutes=0))


class TestPhase2AuthorshipClaims(unittest.TestCase):
    """Tests for signed authorship claims."""

    @classmethod
    def setUpClass(cls):
        """Create test certificates."""
        cls.tmp = Path(tempfile.mkdtemp())
        cls.ca = create_test_ca(cls.tmp / "ca")
        cls.client = issue_cert(
            cls.tmp / "client",
            Path(cls.ca["cert_path"]),
            Path(cls.ca["key_path"]),
            common_name="test-client",
            cert_filename="client.crt",
            key_filename="client.key",
            is_client=True,
        )
        cls.client2 = issue_cert(
            cls.tmp / "client2",
            Path(cls.ca["cert_path"]),
            Path(cls.ca["key_path"]),
            common_name="other-client",
            cert_filename="client2.crt",
            key_filename="client2.key",
            is_client=True,
        )

    def test_create_authorship_claim_structure(self):
        claim = create_authorship_claim("entity-abc123", "authored")
        
        self.assertEqual(claim["target_uuid"], "entity-abc123")
        self.assertEqual(claim["claim_type"], "authored")
        self.assertIn("timestamp", claim)

    def test_canonicalize_claim_deterministic(self):
        claim = {"target_uuid": "x", "claim_type": "authored", "timestamp": "2024-01-01"}
        
        canonical1 = canonicalize_claim(claim)
        canonical2 = canonicalize_claim(claim)
        
        self.assertEqual(canonical1, canonical2)
        # Keys should be sorted
        self.assertIn(b'"claim_type"', canonical1)

    def test_sign_and_verify_claim(self):
        claim = create_authorship_claim("entity-test", "authored")
        
        key_pem = Path(self.client["key_path"]).read_bytes()
        signature = sign_claim(claim, key_pem)
        
        cert_pem = Path(self.client["cert_path"]).read_bytes()
        is_valid, error = verify_signature(claim, signature, cert_pem)
        
        self.assertTrue(is_valid)
        self.assertEqual(error, "")

    def test_verify_rejects_wrong_cert(self):
        claim = create_authorship_claim("entity-test", "authored")
        
        # Sign with client1
        key_pem = Path(self.client["key_path"]).read_bytes()
        signature = sign_claim(claim, key_pem)
        
        # Verify with client2's cert - should fail
        cert_pem = Path(self.client2["cert_path"]).read_bytes()
        is_valid, error = verify_signature(claim, signature, cert_pem)
        
        self.assertFalse(is_valid)
        self.assertIn("Invalid signature", error)

    def test_verify_rejects_tampered_claim(self):
        claim = create_authorship_claim("entity-test", "authored")
        
        key_pem = Path(self.client["key_path"]).read_bytes()
        signature = sign_claim(claim, key_pem)
        
        # Tamper with claim
        claim["target_uuid"] = "entity-TAMPERED"
        
        cert_pem = Path(self.client["cert_path"]).read_bytes()
        is_valid, error = verify_signature(claim, signature, cert_pem)
        
        self.assertFalse(is_valid)


if __name__ == "__main__":
    unittest.main()

