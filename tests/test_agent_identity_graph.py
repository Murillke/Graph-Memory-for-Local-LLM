#!/usr/bin/env python3
"""Test agent identity tracking in Graph layer (ExtractionBatch)."""

import sys
import os
import shutil
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.graph_db import GraphDatabase

# Use workspace-backed temp directory (Kuzu can't access %TEMP% on some Windows setups)
REPO_ROOT = Path(__file__).resolve().parent.parent
TEST_TMP = REPO_ROOT / "tests" / "tmp"


def get_test_dir():
    """Create a unique test directory under tests/tmp/."""
    TEST_TMP.mkdir(parents=True, exist_ok=True)
    test_dir = TEST_TMP / f"agent_identity_graph_{uuid4().hex[:8]}"
    test_dir.mkdir(parents=True, exist_ok=True)
    return test_dir


def test_batch_hash_computation():
    """Test that batch hash is computed correctly."""
    test_dir = get_test_dir()
    try:
        db_path = str(test_dir / "test.graph")
        db = GraphDatabase(db_path)
        
        # Test hash computation
        hash1 = db._calculate_batch_hash(
            extracted_by_agent="codex",
            extracted_by_model="o3",
            extraction_version="v1.0.0",
            extraction_commit="abc123",
            project_name="test",
            source_interaction_uuids=["uuid-1", "uuid-2"],
            source_interaction_hashes=["hash-1", "hash-2"],
            created_entity_uuids=["entity-1", "entity-2"],
            created_relationship_uuids=["rel-1"]
        )
        
        # Same inputs should give same hash
        hash2 = db._calculate_batch_hash(
            extracted_by_agent="codex",
            extracted_by_model="o3",
            extraction_version="v1.0.0",
            extraction_commit="abc123",
            project_name="test",
            source_interaction_uuids=["uuid-2", "uuid-1"],  # Different order
            source_interaction_hashes=["hash-2", "hash-1"],  # Different order
            created_entity_uuids=["entity-2", "entity-1"],  # Different order
            created_relationship_uuids=["rel-1"]
        )
        
        assert hash1 == hash2, "Hash should be order-independent (arrays sorted)"
        print("[PASS] Batch hash is order-independent")
        
        # Different inputs should give different hash
        hash3 = db._calculate_batch_hash(
            extracted_by_agent="auggie",  # Different agent
            extracted_by_model="o3",
            extraction_version="v1.0.0",
            extraction_commit="abc123",
            project_name="test",
            source_interaction_uuids=["uuid-1", "uuid-2"],
            source_interaction_hashes=["hash-1", "hash-2"],
            created_entity_uuids=["entity-1", "entity-2"],
            created_relationship_uuids=["rel-1"]
        )
        
        assert hash1 != hash3, "Different agent should give different hash"
        print("[PASS] Agent identity affects batch hash")

        db.close()
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def test_create_extraction_batch():
    """Test creating an ExtractionBatch node."""
    test_dir = get_test_dir()
    try:
        db_path = str(test_dir / "test.graph")
        db = GraphDatabase(db_path)

        batch_uuid = db.create_extraction_batch(
            project_name="test",
            extracted_by_agent="codex",
            extracted_by_model="o3",
            extraction_version="v1.0.0",
            extraction_commit="abc123",
            source_interaction_uuids=["uuid-1"],
            source_interaction_hashes=["hash-1"],
            created_entity_uuids=["entity-1"],
            created_relationship_uuids=["rel-1"]
        )
        
        assert batch_uuid.startswith("batch-"), f"Expected batch-*, got {batch_uuid}"
        print(f"[PASS] Created ExtractionBatch: {batch_uuid}")
        
        # Query to verify
        result = db.conn.execute("""
            MATCH (b:ExtractionBatch)
            RETURN b.batch_uuid, b.extracted_by_agent, b.batch_hash, b.batch_index
        """)
        
        assert result.has_next(), "Should find the batch"
        row = result.get_next()
        assert row[0] == batch_uuid
        assert row[1] == "codex"
        assert row[2] is not None  # batch_hash computed
        assert row[3] == 1  # First batch
        print("[PASS] ExtractionBatch stored with correct fields")

        db.close()
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def test_batch_chain():
    """Test that batches form a chain."""
    test_dir = get_test_dir()
    try:
        db_path = str(test_dir / "test.graph")
        db = GraphDatabase(db_path)

        # Create first batch
        batch1 = db.create_extraction_batch(
            project_name="test",
            extracted_by_agent="codex",
            extracted_by_model=None,
            extraction_version="v1.0.0",
            extraction_commit="abc",
            source_interaction_uuids=["uuid-1"],
            source_interaction_hashes=["hash-1"],
            created_entity_uuids=["entity-1"],
            created_relationship_uuids=[]
        )

        # Create second batch
        batch2 = db.create_extraction_batch(
            project_name="test",
            extracted_by_agent="auggie",
            extracted_by_model=None,
            extraction_version="v1.0.0",
            extraction_commit="def",
            source_interaction_uuids=["uuid-2"],
            source_interaction_hashes=["hash-2"],
            created_entity_uuids=["entity-2"],
            created_relationship_uuids=[]
        )
        
        # Query to verify chain
        result = db.conn.execute("""
            MATCH (b:ExtractionBatch)
            WHERE b.batch_uuid = $batch_uuid
            RETURN b.batch_index, b.previous_batch_hash
        """, {"batch_uuid": batch2})
        
        assert result.has_next()
        row = result.get_next()
        assert row[0] == 2, f"Second batch should have index 2, got {row[0]}"
        assert row[1] is not None, "Second batch should have previous_batch_hash"
        print("[PASS] Batch chain maintained (batch 2 links to batch 1)")

        db.close()
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def main():
    print("=" * 60)
    print("Testing Agent Identity Graph Layer")
    print("=" * 60)
    print()
    
    test_batch_hash_computation()
    test_create_extraction_batch()
    test_batch_chain()
    
    print()
    print("=" * 60)
    print("All tests passed!")
    print("=" * 60)


if __name__ == '__main__':
    main()

