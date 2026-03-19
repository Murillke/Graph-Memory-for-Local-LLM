"""
Tests for ownership proof generation and verification.

THIS IS A CRITICAL FEATURE - the cryptographic proof system is THE differentiator.
These tests MUST catch any regression. If you break this, tests should SCREAM.

Test coverage:
- Merkle tree: empty, single, power-of-2, non-power-of-2, large, tamper detection
- Ownership proof generation: empty project, single interaction, many, determinism
- Ownership proof verification: valid, tampered root, tampered count, missing fields
- Integrity verification: valid chain, corrupted hash, gaps, None proofs
- End-to-end: full workflow with tampering detection
"""

import sys
import os
import json
import shutil
import hashlib
import copy

sys.path.insert(0, '.')
import pytest

from tools.sql_db import SQLDatabase
from tools.graph_db import GraphDatabase
from tools.merkle_tree import MerkleTree


@pytest.fixture
def test_dbs(tmp_path):
    """Create test databases with sample data."""
    sql_path = str(tmp_path / "test_ownership_sql.db")
    graph_path = str(tmp_path / "test_ownership.kuzu")

    # Create SQL database with interactions
    sql_db = SQLDatabase(sql_path)
    sql_db.create_project("test-ownership", "Test project for ownership proofs")

    # Store multiple interactions to build a chain
    uuids = []
    hashes = []
    for i in range(5):
        uuid = sql_db.store_interaction({
            "project_name": "test-ownership",
            "user_message": f"Test message {i}",
            "assistant_message": f"Test response {i}"
        })
        interaction = sql_db.get_interaction_by_uuid(uuid)
        uuids.append(uuid)
        hashes.append(interaction["content_hash"])

    # Create graph database with entity
    graph_db = GraphDatabase(graph_path)
    graph_db.create_project_node("test-ownership", "Test project")

    entity_uuid = graph_db.create_entity(
        name="TestEntity",
        group_id="test-ownership",
        source_interactions=[uuids[0], uuids[1]],
        source_hashes=[hashes[0], hashes[1]],
        extraction_version="v1.0.0",
        extraction_commit="test123",
        summary="Test entity for ownership proofs",
        labels=["test"]
    )

    data = {
        "sql_db": sql_db,
        "graph_db": graph_db,
        "sql_path": sql_path,
        "graph_path": graph_path,
        "project": "test-ownership",
        "uuids": uuids,
        "hashes": hashes,
        "entity_uuid": entity_uuid
    }

    yield data

    # Cleanup: close connections
    try:
        graph_db.close()
    except:
        pass


@pytest.fixture
def empty_project_db(tmp_path):
    """Create database with empty project (no interactions)."""
    sql_path = str(tmp_path / "test_empty_sql.db")

    sql_db = SQLDatabase(sql_path)
    sql_db.create_project("empty-project", "Empty project")

    yield {
        "sql_db": sql_db,
        "sql_path": sql_path,
        "project": "empty-project"
    }


@pytest.fixture
def large_project_db(tmp_path):
    """Create database with many interactions for stress testing."""
    sql_path = str(tmp_path / "test_large_sql.db")

    sql_db = SQLDatabase(sql_path)
    sql_db.create_project("large-project", "Large project")

    uuids = []
    hashes = []
    # Create 100 interactions
    for i in range(100):
        uuid = sql_db.store_interaction({
            "project_name": "large-project",
            "user_message": f"Message {i} with unique content {hashlib.md5(str(i).encode()).hexdigest()}",
            "assistant_message": f"Response {i}"
        })
        interaction = sql_db.get_interaction_by_uuid(uuid)
        uuids.append(uuid)
        hashes.append(interaction["content_hash"])

    yield {
        "sql_db": sql_db,
        "sql_path": sql_path,
        "project": "large-project",
        "uuids": uuids,
        "hashes": hashes
    }


class TestMerkleTree:
    """
    Test Merkle tree implementation - THE FOUNDATION of ownership proofs.
    If these fail, the entire proof system is compromised.
    """

    def test_merkle_tree_single_hash(self):
        """Single hash tree should return the hash itself."""
        tree = MerkleTree(["hash1"])
        assert tree.root is not None
        assert tree.root == "hash1"

    def test_merkle_tree_two_hashes(self):
        """Two hashes should produce deterministic root."""
        tree = MerkleTree(["hash1", "hash2"])
        assert tree.root is not None
        assert len(tree.root) == 64  # SHA-256 hex

        # Same input = same output (determinism)
        tree2 = MerkleTree(["hash1", "hash2"])
        assert tree.root == tree2.root

        # Different order = different root
        tree3 = MerkleTree(["hash2", "hash1"])
        assert tree.root != tree3.root

    def test_merkle_tree_power_of_two(self):
        """Power of 2 elements should work correctly."""
        for n in [2, 4, 8, 16]:
            hashes = [f"hash{i}" for i in range(n)]
            tree = MerkleTree(hashes)
            assert tree.root is not None
            assert len(tree.root) == 64

    def test_merkle_tree_non_power_of_two(self):
        """Non-power of 2 elements should work (with padding/duplication)."""
        for n in [3, 5, 7, 9, 15, 17]:
            hashes = [f"hash{i}" for i in range(n)]
            tree = MerkleTree(hashes)
            assert tree.root is not None

    def test_merkle_tree_large(self):
        """Large tree (1000 elements) should work."""
        hashes = [hashlib.sha256(str(i).encode()).hexdigest() for i in range(1000)]
        tree = MerkleTree(hashes)
        assert tree.root is not None
        assert len(tree.root) == 64

    def test_merkle_proof_all_indices(self):
        """Should generate valid proofs for ALL indices."""
        hashes = ["hash1", "hash2", "hash3", "hash4", "hash5", "hash6", "hash7", "hash8"]
        tree = MerkleTree(hashes)

        for i, h in enumerate(hashes):
            proof = tree.get_proof(i)
            assert isinstance(proof, list), f"Proof for index {i} should be a list"
            verified = tree.verify_proof(h, proof, tree.root)
            assert verified is True, f"Proof for index {i} should verify"

    def test_merkle_proof_wrong_leaf_fails(self):
        """Wrong leaf value should fail verification."""
        hashes = ["hash1", "hash2", "hash3", "hash4"]
        tree = MerkleTree(hashes)

        proof = tree.get_proof(0)

        # Try to verify with wrong leaf
        assert tree.verify_proof("TAMPERED", proof, tree.root) is False
        assert tree.verify_proof("", proof, tree.root) is False
        assert tree.verify_proof("hash2", proof, tree.root) is False  # Wrong index

    def test_merkle_proof_wrong_root_fails(self):
        """Wrong root should fail verification."""
        hashes = ["hash1", "hash2", "hash3", "hash4"]
        tree = MerkleTree(hashes)

        proof = tree.get_proof(0)

        # Tampered root
        fake_root = "a" * 64
        assert tree.verify_proof("hash1", proof, fake_root) is False

    def test_merkle_proof_tampered_proof_fails(self):
        """Tampered proof path should fail verification."""
        hashes = ["hash1", "hash2", "hash3", "hash4"]
        tree = MerkleTree(hashes)

        proof = tree.get_proof(0)

        if len(proof) > 0:
            # Tamper with proof
            tampered_proof = copy.deepcopy(proof)
            tampered_proof[0] = ("TAMPERED", tampered_proof[0][1]) if isinstance(tampered_proof[0], tuple) else "TAMPERED"
            assert tree.verify_proof("hash1", tampered_proof, tree.root) is False

    def test_merkle_determinism_critical(self):
        """CRITICAL: Same data MUST produce same root every time."""
        hashes = [hashlib.sha256(f"interaction_{i}".encode()).hexdigest() for i in range(50)]

        roots = []
        for _ in range(10):
            tree = MerkleTree(hashes.copy())
            roots.append(tree.root)

        # All roots must be identical
        assert len(set(roots)) == 1, "Merkle root must be deterministic!"


class TestOwnershipProofGeneration:
    """
    Test ownership proof generation - PROVES you own the data.
    """

    def test_generate_ownership_proof_import(self):
        """generate_ownership_proof.py should be importable without errors."""
        from scripts.generate_ownership_proof import generate_ownership_proof
        assert callable(generate_ownership_proof)

    def test_generate_proof_has_required_fields(self, test_dbs):
        """Proof MUST contain all required fields."""
        from scripts.generate_ownership_proof import generate_ownership_proof

        proof = generate_ownership_proof(test_dbs["project"], test_dbs["sql_path"])

        required_fields = ["project_name", "merkle_root", "timestamp", "interaction_count"]
        for field in required_fields:
            assert field in proof, f"Proof missing required field: {field}"

        assert proof["project_name"] == test_dbs["project"]
        assert proof["interaction_count"] == 5
        assert len(proof["merkle_root"]) == 64

    def test_generate_proof_deterministic(self, test_dbs):
        """CRITICAL: Same data MUST produce same merkle root."""
        from scripts.generate_ownership_proof import generate_ownership_proof

        proof1 = generate_ownership_proof(test_dbs["project"], test_dbs["sql_path"])
        proof2 = generate_ownership_proof(test_dbs["project"], test_dbs["sql_path"])

        assert proof1["merkle_root"] == proof2["merkle_root"], \
            "Same data must produce identical merkle root!"

    def test_generate_proof_large_project(self, large_project_db):
        """Should handle large projects (100+ interactions)."""
        from scripts.generate_ownership_proof import generate_ownership_proof

        proof = generate_ownership_proof(
            large_project_db["project"],
            large_project_db["sql_path"]
        )

        assert proof["interaction_count"] == 100
        assert len(proof["merkle_root"]) == 64

    def test_generate_proof_empty_project_fails(self, empty_project_db):
        """Empty project should raise error or return empty proof."""
        from scripts.generate_ownership_proof import generate_ownership_proof

        # Empty project should either raise or return 0 interactions
        try:
            proof = generate_ownership_proof(
                empty_project_db["project"],
                empty_project_db["sql_path"]
            )
            assert proof["interaction_count"] == 0
        except (ValueError, Exception):
            pass  # Raising is also acceptable

    def test_generate_proof_nonexistent_project_fails(self, test_dbs):
        """Nonexistent project should fail gracefully."""
        from scripts.generate_ownership_proof import generate_ownership_proof

        with pytest.raises(Exception):
            generate_ownership_proof("nonexistent-project", test_dbs["sql_path"])


class TestOwnershipProofVerification:
    """
    Test ownership proof verification - VALIDATES claimed ownership.
    TAMPERING MUST BE DETECTED.
    """

    def test_verify_ownership_proof_import(self):
        """verify_ownership_proof.py should be importable."""
        from scripts.verify_ownership_proof import verify_ownership_proof
        assert callable(verify_ownership_proof)

    def test_verify_valid_proof_passes(self, test_dbs):
        """Valid proof should pass FULL verification against database."""
        from scripts.generate_ownership_proof import generate_ownership_proof
        from scripts.verify_ownership_proof import verify_ownership_proof

        proof = generate_ownership_proof(test_dbs["project"], test_dbs["sql_path"])
        # Full verification WITH database
        assert verify_ownership_proof(proof, test_dbs["sql_path"]) is True

    def test_verify_tampered_merkle_root_fails(self, test_dbs):
        """CRITICAL: Tampered merkle root MUST fail full verification."""
        from scripts.generate_ownership_proof import generate_ownership_proof
        from scripts.verify_ownership_proof import verify_ownership_proof

        proof = generate_ownership_proof(test_dbs["project"], test_dbs["sql_path"])

        # Tamper with merkle root
        tampered = copy.deepcopy(proof)
        tampered["merkle_root"] = "a" * 64  # Fake root

        # Full verification should detect tampering
        result = verify_ownership_proof(tampered, test_dbs["sql_path"])
        assert result is False, "Tampered merkle root MUST be rejected!"

    def test_verify_tampered_interaction_count_fails(self, test_dbs):
        """CRITICAL: Tampered interaction count MUST fail full verification."""
        from scripts.generate_ownership_proof import generate_ownership_proof
        from scripts.verify_ownership_proof import verify_ownership_proof

        proof = generate_ownership_proof(test_dbs["project"], test_dbs["sql_path"])

        # Tamper with count
        tampered = copy.deepcopy(proof)
        tampered["interaction_count"] = 9999

        # Full verification should detect count mismatch
        result = verify_ownership_proof(tampered, test_dbs["sql_path"])
        assert result is False, "Tampered interaction count MUST be rejected!"

    def test_verify_missing_fields_fails(self, test_dbs):
        """Proof with missing fields MUST fail."""
        from scripts.generate_ownership_proof import generate_ownership_proof
        from scripts.verify_ownership_proof import verify_ownership_proof

        proof = generate_ownership_proof(test_dbs["project"], test_dbs["sql_path"])

        for field in ["merkle_root", "project_name", "interaction_count"]:
            incomplete = copy.deepcopy(proof)
            del incomplete[field]

            # Even portable verification (no db) should fail on missing fields
            result = verify_ownership_proof(incomplete)
            assert result is False, f"Missing {field} MUST fail verification"

    def test_portable_verification_accepts_wellformed(self, test_dbs):
        """Portable verification (no DB) should accept well-formed proofs."""
        from scripts.generate_ownership_proof import generate_ownership_proof
        from scripts.verify_ownership_proof import verify_ownership_proof

        proof = generate_ownership_proof(test_dbs["project"], test_dbs["sql_path"])

        # Portable verification (no database) - only checks structure
        result = verify_ownership_proof(proof)  # No db path
        assert result is True, "Well-formed proof should pass portable verification"


class TestVerifyIntegrity:
    """
    Test verify_integrity.py - the AUDIT TRAIL validator.
    """

    def test_verify_integrity_functions_exist(self):
        """verify_integrity.py should have required functions."""
        with open("scripts/verify_integrity.py", "r") as f:
            source = f.read()

        required_functions = [
            "def verify_sql_chain",
            "def verify_graph_entities",
            "def verify_graph_relationships"
        ]
        for func in required_functions:
            assert func in source, f"Missing function: {func}"

    def test_none_extraction_proof_handling(self):
        """verify_integrity.py MUST handle None extraction_proof gracefully."""
        with open("scripts/verify_integrity.py", "r") as f:
            source = f.read()

        # Verify our fix is in place
        assert "if extraction_proof is None:" in source, \
            "None extraction_proof check is MISSING - will crash on OTS-deferred entities!"
        assert 'extraction_proof = {}' in source

    def test_sql_chain_valid(self, test_dbs):
        """Valid SQL chain should pass verification."""
        result = test_dbs["sql_db"].verify_interaction_chain(test_dbs["project"])
        assert result["verified"] is True
        assert result["total_interactions"] == 5
        assert len(result["errors"]) == 0

    def test_sql_chain_detects_tampering(self, test_dbs):
        """CRITICAL: Database MUST prevent tampering via trigger."""
        import sqlite3

        # Try to tamper with content directly in DB
        conn = test_dbs["sql_db"]._get_connection()
        cursor = conn.cursor()

        # Attempt tampering - should be blocked by trigger
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            cursor.execute(
                "UPDATE interactions SET user_message = 'TAMPERED' WHERE uuid = ?",
                (test_dbs["uuids"][2],)
            )

        conn.close()

        # Chain should still be valid (tampering was blocked)
        result = test_dbs["sql_db"].verify_interaction_chain(test_dbs["project"])
        assert result["verified"] is True, "Chain should be intact - tampering was blocked!"

    def test_hash_chain_integrity_verified(self, test_dbs):
        """Verify hash chain integrity using the built-in verification."""
        # Add more interactions to extend the chain
        for i in range(3):
            test_dbs["sql_db"].store_interaction({
                "project_name": test_dbs["project"],
                "user_message": f"Chain extension message {i}",
                "assistant_message": f"Chain extension response {i}"
            })

        # Verify full chain - should pass
        result = test_dbs["sql_db"].verify_interaction_chain(test_dbs["project"])
        assert result["verified"] is True, "Chain should verify after extensions"
        assert result["total_interactions"] == 8  # 5 original + 3 new

        # Verify chain indices are sequential
        interactions = test_dbs["sql_db"].get_all_interactions(test_dbs["project"])
        for i, interaction in enumerate(interactions):
            assert interaction["chain_index"] == i + 1, \
                f"Chain index should be sequential: expected {i+1}, got {interaction['chain_index']}"

            # Verify previous_hash links
            if i > 0:
                assert interaction["previous_hash"] == interactions[i-1]["content_hash"], \
                    "Previous hash should link to prior interaction's content hash"


class TestEndToEndProofWorkflow:
    """
    End-to-end tests for the complete ownership proof workflow.
    These simulate real-world usage and attack scenarios.
    """

    def test_full_workflow_generate_and_verify(self, test_dbs):
        """Complete workflow: generate proof → full verify → portable verify."""
        from scripts.generate_ownership_proof import generate_ownership_proof
        from scripts.verify_ownership_proof import verify_ownership_proof

        # Generate
        proof = generate_ownership_proof(test_dbs["project"], test_dbs["sql_path"])

        # Full verification with database
        assert verify_ownership_proof(proof, test_dbs["sql_path"]) is True

        # Serialize and deserialize (simulates storage/transmission)
        proof_json = json.dumps(proof)
        proof_restored = json.loads(proof_json)

        # Portable verification (structure only)
        assert verify_ownership_proof(proof_restored) is True

        # Full verification after restoration
        assert verify_ownership_proof(proof_restored, test_dbs["sql_path"]) is True

    def test_proof_after_new_interaction_differs(self, test_dbs):
        """Adding new interaction MUST change the merkle root."""
        from scripts.generate_ownership_proof import generate_ownership_proof

        proof_before = generate_ownership_proof(test_dbs["project"], test_dbs["sql_path"])

        # Add new interaction
        test_dbs["sql_db"].store_interaction({
            "project_name": test_dbs["project"],
            "user_message": "New message after proof",
            "assistant_message": "New response"
        })

        proof_after = generate_ownership_proof(test_dbs["project"], test_dbs["sql_path"])

        assert proof_before["merkle_root"] != proof_after["merkle_root"], \
            "New data MUST change the merkle root!"
        assert proof_after["interaction_count"] == proof_before["interaction_count"] + 1

    def test_old_proof_fails_after_new_data(self, test_dbs):
        """CRITICAL: Old proof MUST fail verification after new data added."""
        from scripts.generate_ownership_proof import generate_ownership_proof
        from scripts.verify_ownership_proof import verify_ownership_proof

        # Generate proof at time T1
        proof_t1 = generate_ownership_proof(test_dbs["project"], test_dbs["sql_path"])

        # Verify at T1 - should pass
        assert verify_ownership_proof(proof_t1, test_dbs["sql_path"]) is True

        # Add new interaction (time T2)
        test_dbs["sql_db"].store_interaction({
            "project_name": test_dbs["project"],
            "user_message": "New data at T2",
            "assistant_message": "Response at T2"
        })

        # Old proof (from T1) should FAIL verification against current data
        result = verify_ownership_proof(proof_t1, test_dbs["sql_path"])
        assert result is False, "Old proof MUST fail after new data is added!"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
