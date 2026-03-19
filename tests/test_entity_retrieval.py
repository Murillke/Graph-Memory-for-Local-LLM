"""
Test entity field retrieval to catch column index bugs.

Run with: python tests/test_entity_retrieval.py
"""

import sys
import os
import shutil
sys.path.insert(0, '.')

from tools.graph_db import GraphDatabase

# Use tests/tmp/ for test databases, not memory/
os.makedirs("./tests/tmp", exist_ok=True)
TEST_DB_PATH = "./tests/tmp/test_entity_retrieval.kuzu"

# Clean up old test database
if os.path.exists(TEST_DB_PATH):
    try:
        shutil.rmtree(TEST_DB_PATH)
    except:
        pass

print("=" * 80)
print("Testing Entity Field Retrieval")
print("=" * 80)

# Create test database
db = GraphDatabase(TEST_DB_PATH)

# Test 1: All fields are retrieved correctly
print("\n[Test 1] Verifying all fields are retrieved correctly...")
entity_uuid = db.create_entity(
    name="Test Entity",
    group_id="test-group",
    summary="Test summary",
    labels=["Test", "Validation"],
    attributes={"key": "value"},
    source_interactions=["uuid-123"],
    source_hashes=["hash-123"],
    source_chain=[{"interaction": "uuid-123", "hash": "hash-123"}],
    event_timestamp="2026-03-09 15:00:00",
    extraction_version="v1.0.0",
    extraction_commit="test-commit"
)

entity = db.get_entity_by_uuid(entity_uuid)

assert entity['name'] == "Test Entity", "Name mismatch"
assert entity['summary'] == "Test summary", "Summary mismatch"
assert entity['labels'] == ["Test", "Validation"], "Labels mismatch"
assert entity['extraction_commit'] == "test-commit", "Commit mismatch"
print("  [OK] Basic fields correct")

# Test 2: extraction_proof is NOT extraction_commit
print("\n[Test 2] Verifying extraction_proof != extraction_commit...")
assert entity['extraction_proof'] != "test-commit", "extraction_proof should NOT be extraction_commit!"
assert entity['extraction_proof'] != entity['extraction_commit'], "Proof and commit should be different!"
assert len(entity['extraction_proof']) == 64, f"Proof should be 64 chars, got {len(entity['extraction_proof'])}"
assert all(c in '0123456789abcdef' for c in entity['extraction_proof']), "Proof should be valid hex"
print("  [OK] extraction_proof is a valid SHA-256 hash, not the commit value")

# Test 3: Proof verification works
print("\n[Test 3] Verifying proof calculation...")
result = db.verify_entity_extraction(entity_uuid)
assert result['verified'] == True, "Entity should be verified"
assert result['match'] == True, f"Proof should match! Stored: {result['stored_proof'][:32]}..., Calculated: {result['calculated_proof'][:32]}..."
print("  [OK] Proof verification passed")

# Test 4: source_chain field exists
print("\n[Test 4] Verifying source_chain field...")
assert 'source_chain' in entity, "source_chain field missing!"
assert entity['source_chain'] == [{"interaction": "uuid-123", "hash": "hash-123"}], "source_chain mismatch"
print("  [OK] source_chain field retrieved correctly")

# Test 5: timestamp_proof field exists
print("\n[Test 5] Verifying timestamp_proof field...")
assert 'timestamp_proof' in entity, "timestamp_proof field missing!"
# Should be None for this entity since we didn't provide one
assert entity['timestamp_proof'] is None or entity['timestamp_proof'] == '', "timestamp_proof should be None/empty"
print("  [OK] timestamp_proof field exists")

# Clean up
db.close()
try:
    shutil.rmtree("./memory/test_entity_retrieval.kuzu")
except:
    pass  # Cleanup is optional

print("\n" + "=" * 80)
print("[SUCCESS] All entity retrieval tests passed!")
print("=" * 80)
print("\nThese tests verify:")
print("  1. All entity fields are retrieved correctly")
print("  2. extraction_proof is NOT the same as extraction_commit")
print("  3. Proof verification works correctly")
print("  4. source_chain field is retrieved")
print("  5. timestamp_proof field exists")
print("\nThis prevents column index mismatch bugs!")

