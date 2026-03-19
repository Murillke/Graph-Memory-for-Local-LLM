import json
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tools.timestamp_proof import (
    create_timestamp_proof,
    verify_timestamp_proof,
    get_attestation_status,
    has_bitcoin_attestation,
)


class TimestampProofTests(unittest.TestCase):
    def test_constrained_environment_proof_is_explicit(self):
        proof_json = create_timestamp_proof(
            "a" * 64,
            constrained_environment=True,
            constraint_reason="No outbound network access"
        )
        proof = json.loads(proof_json)

        self.assertEqual(proof["version"], "2.0")
        self.assertEqual(proof["proof_type"], "timestamp")
        self.assertEqual(proof["proof_mode"], "local")
        self.assertEqual(proof["attestation_status"], "not_requested")
        self.assertEqual(proof["network_mode"], "constrained")
        self.assertEqual(proof["constraint_reason"], "No outbound network access")

        verified, _, _ = verify_timestamp_proof("a" * 64, proof_json)
        self.assertTrue(verified)
        self.assertEqual(get_attestation_status(proof_json), "not_requested")
        self.assertFalse(has_bitcoin_attestation(proof_json))

    def test_local_only_proof_has_signature(self):
        proof_json = create_timestamp_proof("b" * 64, submit_to_ots=False)
        proof = json.loads(proof_json)

        self.assertIn("signature", proof)
        self.assertEqual(proof["proof_mode"], "local")
        self.assertEqual(proof["attestation_status"], "not_requested")

        verified, _, _ = verify_timestamp_proof("b" * 64, proof_json)
        self.assertTrue(verified)


if __name__ == "__main__":
    unittest.main()
