"""
Test verification of extraction and derivation proofs.
"""

import sys
sys.path.insert(0, '.')

from tools.graph_db import GraphDatabase
from tools.sql_db import SQLDatabase
import os
import shutil

# Ensure test directory exists
os.makedirs("./tests/tmp", exist_ok=True)

# Clean up test databases
if os.path.exists("./tests/tmp/test_verify.kuzu"):
    if os.path.isdir("./tests/tmp/test_verify.kuzu"):
        shutil.rmtree("./tests/tmp/test_verify.kuzu")
    else:
        os.remove("./tests/tmp/test_verify.kuzu")
if os.path.exists("./tests/tmp/test_verify_sql.db"):
    os.remove("./tests/tmp/test_verify_sql.db")

print("="*60)
print("Testing Cryptographic Proof Verification")
print("="*60)

# Create SQL database
sql_db = SQLDatabase("./tests/tmp/test_verify_sql.db")
sql_db.create_project("test-project", "Test project")

# Store interaction
uuid1 = sql_db.store_interaction({
    "project_name": "test-project",
    "user_message": "LadybugDB is awesome!",
    "assistant_message": "Indeed it is!"
})

interaction = sql_db.get_interaction_by_uuid(uuid1)
content_hash = interaction["content_hash"]

print(f"\n[OK] Created SQL interaction: {uuid1}")
print(f"   Hash: {content_hash[:16]}...")

# Create graph database
graph_db = GraphDatabase("./tests/tmp/test_verify.kuzu")
graph_db.create_project_node("test-project", "Test project")

# Create entity
entity_uuid = graph_db.create_entity(
    name="LadybugDB",
    group_id="test-project",
    source_interactions=[uuid1],
    source_hashes=[content_hash],
    extraction_version="v1.0.0",
    extraction_commit="abc123",
    summary="Graph database",
    labels=["technology"]
)

print(f"\n[OK] Created entity: {entity_uuid}")

# Create second entity
entity2_uuid = graph_db.create_entity(
    name="Awesome",
    group_id="test-project",
    source_interactions=[uuid1],
    source_hashes=[content_hash],
    extraction_version="v1.0.0",
    extraction_commit="abc123",
    summary="Quality attribute",
    labels=["attribute"]
)

print(f"[OK] Created entity: {entity2_uuid}")

# Create relationship
rel_uuid = graph_db.create_relationship(
    source_uuid=entity_uuid,
    target_uuid=entity2_uuid,
    relationship_name="HAS_QUALITY",
    fact="LadybugDB is awesome",
    group_id="test-project",
    episodes=[uuid1],
    episode_hashes=[content_hash],
    derivation_version="v1.0.0",
    derivation_commit="abc123",
    valid_at=interaction["timestamp"]
)

print(f"[OK] Created relationship: {rel_uuid}")

# TEST 1: Verify entity extraction proof
print(f"\n{'='*60}")
print("TEST 1: Verify Entity Extraction Proof")
print(f"{'='*60}")

result = graph_db.verify_entity_extraction(entity_uuid)

print(f"\nEntity: {result['entity_name']}")
print(f"Stored proof:     {result['stored_proof'][:32]}...")
print(f"Calculated proof: {result['calculated_proof'][:32]}...")
print(f"Match: {result['match']}")
print(f"Verified: {result['verified']}")

if result['verified']:
    print(f"\n[OK] ENTITY EXTRACTION PROOF VERIFIED!")
else:
    print(f"\n[ERROR] VERIFICATION FAILED!")
    sys.exit(1)

# TEST 2: Verify relationship derivation proof
print(f"\n{'='*60}")
print("TEST 2: Verify Relationship Derivation Proof")
print(f"{'='*60}")

result = graph_db.verify_relationship_derivation(rel_uuid)

print(f"\nFact: {result['fact']}")
print(f"Stored proof:     {result['stored_proof'][:32]}...")
print(f"Calculated proof: {result['calculated_proof'][:32]}...")
print(f"Match: {result['match']}")
print(f"Verified: {result['verified']}")

if result['verified']:
    print(f"\n[OK] RELATIONSHIP DERIVATION PROOF VERIFIED!")
else:
    print(f"\n[ERROR] VERIFICATION FAILED!")
    sys.exit(1)

# TEST 3: Verify SQL hash chain
print(f"\n{'='*60}")
print("TEST 3: Verify SQL Hash Chain")
print(f"{'='*60}")

result = sql_db.verify_interaction_chain("test-project")

print(f"\nTotal interactions: {result['total_interactions']}")
print(f"Verified: {result['verified']}")

if result['verified']:
    print(f"\n[OK] SQL HASH CHAIN VERIFIED!")
else:
    print(f"\n[ERROR] VERIFICATION FAILED!")
    print(f"Errors: {result['errors']}")
    sys.exit(1)

print(f"\n{'='*60}")
print(f"[OK] ALL VERIFICATION TESTS PASSED!")
print(f"{'='*60}")
print(f"\nVerified:")
print(f"  - Entity extraction proof (SHA-256)")
print(f"  - Relationship derivation proof (SHA-256)")
print(f"  - SQL hash chain integrity")

