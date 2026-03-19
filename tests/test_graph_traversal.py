"""
Test graph traversal functions - getting related entities and neighborhoods.
"""

import sys
sys.path.insert(0, '.')

from tools.graph_db import GraphDatabase
from tools.sql_db import SQLDatabase
import os
import shutil

# Use tests/tmp/ for test databases, not memory/
TEST_DIR = "./tests/tmp"
DB_PATH = os.path.join(TEST_DIR, "test_traversal.kuzu")
SQL_PATH = os.path.join(TEST_DIR, "test_traversal_sql.db")
os.makedirs(TEST_DIR, exist_ok=True)

# Clean up test databases
if os.path.exists(DB_PATH):
    if os.path.isdir(DB_PATH):
        shutil.rmtree(DB_PATH)
    else:
        os.remove(DB_PATH)
if os.path.exists(SQL_PATH):
    os.remove(SQL_PATH)

print("="*60)
print("Testing Graph Traversal Functions")
print("="*60)

# Create databases
sql_db = SQLDatabase(SQL_PATH)
sql_db.create_project("test-project", "Test project")

# Store interactions
uuid1 = sql_db.store_interaction({
    "project_name": "test-project",
    "user_message": "LadybugDB is located at ./memory/knowledge.ladybug",
    "assistant_message": "Got it!"
})

uuid2 = sql_db.store_interaction({
    "project_name": "test-project",
    "user_message": "It uses Python 3.9",
    "assistant_message": "Noted!"
})

uuid3 = sql_db.store_interaction({
    "project_name": "test-project",
    "user_message": "Python is a programming language",
    "assistant_message": "Yes!"
})

# Get hashes
int1 = sql_db.get_interaction_by_uuid(uuid1)
int2 = sql_db.get_interaction_by_uuid(uuid2)
int3 = sql_db.get_interaction_by_uuid(uuid3)

print(f"\n[OK] Created 3 SQL interactions")

# Create graph database
graph_db = GraphDatabase(DB_PATH)
graph_db.create_project_node("test-project", "Test project")

# Create entities
# LadybugDB -> ./memory/knowledge.ladybug
# LadybugDB -> Python
# Python -> 3.9
# Python -> programming language

ladybug_uuid = graph_db.create_entity(
    name="LadybugDB",
    group_id="test-project",
    source_interactions=[uuid1],
    source_hashes=[int1["content_hash"]],
    extraction_version="v1.0.0",
    extraction_commit="abc123",
    summary="Graph database",
    labels=["technology", "database"]
)

path_uuid = graph_db.create_entity(
    name="./memory/knowledge.ladybug",
    group_id="test-project",
    source_interactions=[uuid1],
    source_hashes=[int1["content_hash"]],
    extraction_version="v1.0.0",
    extraction_commit="abc123",
    summary="Database file path",
    labels=["file", "path"]
)

python_uuid = graph_db.create_entity(
    name="Python",
    group_id="test-project",
    source_interactions=[uuid2, uuid3],
    source_hashes=[int2["content_hash"], int3["content_hash"]],
    extraction_version="v1.0.0",
    extraction_commit="abc123",
    summary="Programming language",
    labels=["technology", "language"]
)

version_uuid = graph_db.create_entity(
    name="3.9",
    group_id="test-project",
    source_interactions=[uuid2],
    source_hashes=[int2["content_hash"]],
    extraction_version="v1.0.0",
    extraction_commit="abc123",
    summary="Python version",
    labels=["version"]
)

lang_uuid = graph_db.create_entity(
    name="programming language",
    group_id="test-project",
    source_interactions=[uuid3],
    source_hashes=[int3["content_hash"]],
    extraction_version="v1.0.0",
    extraction_commit="abc123",
    summary="Type of language",
    labels=["concept"]
)

# Link to project
for entity_uuid in [ladybug_uuid, path_uuid, python_uuid, version_uuid, lang_uuid]:
    graph_db.link_project_to_entity("test-project", entity_uuid)

print(f"[OK] Created 5 entities")

# Create relationships
# LadybugDB -[LOCATED_AT]-> ./memory/knowledge.ladybug
rel1_uuid = graph_db.create_relationship(
    source_uuid=ladybug_uuid,
    target_uuid=path_uuid,
    relationship_name="LOCATED_AT",
    fact="LadybugDB is located at ./memory/knowledge.ladybug",
    group_id="test-project",
    episodes=[uuid1],
    episode_hashes=[int1["content_hash"]],
    derivation_version="v1.0.0",
    derivation_commit="abc123",
    valid_at=int1["timestamp"]
)

# LadybugDB -[USES]-> Python
rel2_uuid = graph_db.create_relationship(
    source_uuid=ladybug_uuid,
    target_uuid=python_uuid,
    relationship_name="USES",
    fact="LadybugDB uses Python",
    group_id="test-project",
    episodes=[uuid2],
    episode_hashes=[int2["content_hash"]],
    derivation_version="v1.0.0",
    derivation_commit="abc123",
    valid_at=int2["timestamp"]
)

# Python -[HAS_VERSION]-> 3.9
rel3_uuid = graph_db.create_relationship(
    source_uuid=python_uuid,
    target_uuid=version_uuid,
    relationship_name="HAS_VERSION",
    fact="Python version is 3.9",
    group_id="test-project",
    episodes=[uuid2],
    episode_hashes=[int2["content_hash"]],
    derivation_version="v1.0.0",
    derivation_commit="abc123",
    valid_at=int2["timestamp"]
)

# Python -[IS_A]-> programming language
rel4_uuid = graph_db.create_relationship(
    source_uuid=python_uuid,
    target_uuid=lang_uuid,
    relationship_name="IS_A",
    fact="Python is a programming language",
    group_id="test-project",
    episodes=[uuid3],
    episode_hashes=[int3["content_hash"]],
    derivation_version="v1.0.0",
    derivation_commit="abc123",
    valid_at=int3["timestamp"]
)

print(f"[OK] Created 4 relationships")
print(f"\nGraph structure:")
print(f"  LadybugDB -[LOCATED_AT]-> ./memory/knowledge.ladybug")
print(f"  LadybugDB -[USES]-> Python")
print(f"  Python -[HAS_VERSION]-> 3.9")
print(f"  Python -[IS_A]-> programming language")

# TEST 1: Get related entities (outgoing)
print(f"\n{'='*60}")
print("TEST 1: Get Related Entities (Outgoing)")
print(f"{'='*60}")

related = graph_db.get_related_entities(ladybug_uuid, direction="outgoing")
print(f"\nEntities that LadybugDB points to: {len(related)}")
for e in related:
    print(f"  - {e['name']} (via {e['relationship_type']})")
    print(f"    Fact: {e['fact']}")

assert len(related) == 2, f"Expected 2 entities, got {len(related)}"
assert any(e['name'] == "./memory/knowledge.ladybug" for e in related)
assert any(e['name'] == "Python" for e in related)
print(f"\n[OK] TEST 1 PASSED")

# TEST 2: Get related entities (incoming)
print(f"\n{'='*60}")
print("TEST 2: Get Related Entities (Incoming)")
print(f"{'='*60}")

related = graph_db.get_related_entities(python_uuid, direction="incoming")
print(f"\nEntities that point to Python: {len(related)}")
for e in related:
    print(f"  - {e['name']} (via {e['relationship_type']})")

assert len(related) == 1, f"Expected 1 entity, got {len(related)}"
assert related[0]['name'] == "LadybugDB"
assert related[0]['direction'] == "incoming"
print(f"\n[OK] TEST 2 PASSED")

# TEST 3: Get related entities (both directions)
print(f"\n{'='*60}")
print("TEST 3: Get Related Entities (Both Directions)")
print(f"{'='*60}")

related = graph_db.get_related_entities(python_uuid, direction="both")
print(f"\nAll entities connected to Python: {len(related)}")
for e in related:
    print(f"  - [{e['direction']}] {e['name']} (via {e['relationship_type']})")

assert len(related) == 3, f"Expected 3 entities, got {len(related)}"
# 1 incoming (LadybugDB), 2 outgoing (3.9, programming language)
incoming = [e for e in related if e['direction'] == 'incoming']
outgoing = [e for e in related if e['direction'] == 'outgoing']
assert len(incoming) == 1
assert len(outgoing) == 2
print(f"\n[OK] TEST 3 PASSED")

# TEST 4: Get related entities with type filter
print(f"\n{'='*60}")
print("TEST 4: Get Related Entities (Filtered by Type)")
print(f"{'='*60}")

related = graph_db.get_related_entities(
    python_uuid,
    direction="outgoing",
    relationship_type="HAS_VERSION"
)
print(f"\nEntities connected via HAS_VERSION: {len(related)}")
for e in related:
    print(f"  - {e['name']}")

assert len(related) == 1, f"Expected 1 entity, got {len(related)}"
assert related[0]['name'] == "3.9"
assert related[0]['relationship_type'] == "HAS_VERSION"
print(f"\n[OK] TEST 4 PASSED")

# TEST 5: Get relationship entities
print(f"\n{'='*60}")
print("TEST 5: Get Relationship Entities")
print(f"{'='*60}")

rel_info = graph_db.get_relationship_entities(rel2_uuid)
print(f"\nRelationship: {rel_info['relationship_type']}")
print(f"  Source: {rel_info['source']['name']}")
print(f"  Target: {rel_info['target']['name']}")
print(f"  Fact: {rel_info['fact']}")

assert rel_info is not None
assert rel_info['source']['name'] == "LadybugDB"
assert rel_info['target']['name'] == "Python"
assert rel_info['relationship_type'] == "USES"
assert rel_info['fact'] == "LadybugDB uses Python"
print(f"\n[OK] TEST 5 PASSED")

# NOTE: get_entity_neighborhood() is not yet implemented due to Kuzu limitations
# Use get_related_entities() instead for getting direct neighbors
print(f"\n{'='*60}")
print("NOTE: Skipping neighborhood tests (not yet implemented)")
print(f"{'='*60}")
print(f"Use get_related_entities() for getting direct neighbors")

print(f"\n{'='*60}")
print(f"[OK] ALL GRAPH TRAVERSAL TESTS PASSED!")
print(f"{'='*60}")
print(f"\nTested:")
print(f"  - Get related entities (outgoing)")
print(f"  - Get related entities (incoming)")
print(f"  - Get related entities (both directions)")
print(f"  - Get related entities (filtered by type)")
print(f"  - Get relationship entities")
print(f"\nNOTE: get_entity_neighborhood() not yet implemented (Kuzu limitation)")

# Python -[HAS_VERSION]-> 3.9
rel3_uuid = graph_db.create_relationship(
    source_uuid=python_uuid,
    target_uuid=version_uuid,
    relationship_name="HAS_VERSION",
    fact="Python version is 3.9",
    group_id="test-project",
    episodes=[uuid2],
    episode_hashes=[int2["content_hash"]],
    derivation_version="v1.0.0",
    derivation_commit="abc123",
    valid_at=int2["timestamp"]
)

