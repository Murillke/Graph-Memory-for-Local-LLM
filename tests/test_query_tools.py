"""
Test query tools for searching entities and facts.
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
if os.path.exists("./tests/tmp/test_query.kuzu"):
    if os.path.isdir("./tests/tmp/test_query.kuzu"):
        shutil.rmtree("./tests/tmp/test_query.kuzu")
    else:
        os.remove("./tests/tmp/test_query.kuzu")
if os.path.exists("./tests/tmp/test_query_sql.db"):
    os.remove("./tests/tmp/test_query_sql.db")

print("="*60)
print("Testing Query Tools")
print("="*60)

# Create databases
sql_db = SQLDatabase("./tests/tmp/test_query_sql.db")
sql_db.create_project("test-project", "Test project")

# Store some interactions
uuid1 = sql_db.store_interaction({
    "project_name": "test-project",
    "user_message": "We are using LadybugDB for the knowledge graph",
    "assistant_message": "Great choice!"
})

uuid2 = sql_db.store_interaction({
    "project_name": "test-project",
    "user_message": "It's located at ./memory/knowledge.ladybug",
    "assistant_message": "Got it!"
})

uuid3 = sql_db.store_interaction({
    "project_name": "test-project",
    "user_message": "We're also using Python 3.9",
    "assistant_message": "Perfect!"
})

# Get hashes
int1 = sql_db.get_interaction_by_uuid(uuid1)
int2 = sql_db.get_interaction_by_uuid(uuid2)
int3 = sql_db.get_interaction_by_uuid(uuid3)

print(f"\n[OK] Created 3 SQL interactions")

# Create graph database
graph_db = GraphDatabase("./tests/tmp/test_query.kuzu")
graph_db.create_project_node("test-project", "Test project")

# Create entities
ladybug_uuid = graph_db.create_entity(
    name="LadybugDB",
    group_id="test-project",
    source_interactions=[uuid1],
    source_hashes=[int1["content_hash"]],
    extraction_version="v1.0.0",
    extraction_commit="abc123",
    summary="Graph database for knowledge storage",
    labels=["technology", "database"]
)

path_uuid = graph_db.create_entity(
    name="./memory/knowledge.ladybug",
    group_id="test-project",
    source_interactions=[uuid2],
    source_hashes=[int2["content_hash"]],
    extraction_version="v1.0.0",
    extraction_commit="abc123",
    summary="Database file path",
    labels=["file", "path"]
)

python_uuid = graph_db.create_entity(
    name="Python",
    group_id="test-project",
    source_interactions=[uuid3],
    source_hashes=[int3["content_hash"]],
    extraction_version="v1.0.0",
    extraction_commit="abc123",
    summary="Programming language",
    labels=["technology", "language"]
)

version_uuid = graph_db.create_entity(
    name="3.9",
    group_id="test-project",
    source_interactions=[uuid3],
    source_hashes=[int3["content_hash"]],
    extraction_version="v1.0.0",
    extraction_commit="abc123",
    summary="Python version",
    labels=["version"]
)

# Link to project
graph_db.link_project_to_entity("test-project", ladybug_uuid)
graph_db.link_project_to_entity("test-project", path_uuid)
graph_db.link_project_to_entity("test-project", python_uuid)
graph_db.link_project_to_entity("test-project", version_uuid)

print(f"[OK] Created 4 entities")

# Create relationships
rel1_uuid = graph_db.create_relationship(
    source_uuid=ladybug_uuid,
    target_uuid=path_uuid,
    relationship_name="LOCATED_AT",
    fact="LadybugDB is located at ./memory/knowledge.ladybug",
    group_id="test-project",
    episodes=[uuid2],
    episode_hashes=[int2["content_hash"]],
    derivation_version="v1.0.0",
    derivation_commit="abc123",
    valid_at=int2["timestamp"]
)

rel2_uuid = graph_db.create_relationship(
    source_uuid=python_uuid,
    target_uuid=version_uuid,
    relationship_name="HAS_VERSION",
    fact="Python version is 3.9",
    group_id="test-project",
    episodes=[uuid3],
    episode_hashes=[int3["content_hash"]],
    derivation_version="v1.0.0",
    derivation_commit="abc123",
    valid_at=int3["timestamp"]
)

print(f"[OK] Created 2 relationships")

# TEST 1: Search all entities
print(f"\n{'='*60}")
print("TEST 1: Get All Entities")
print(f"{'='*60}")

entities = graph_db.get_all_entities("test-project")
print(f"\nFound {len(entities)} entities:")
for e in entities:
    print(f"  - {e['name']} (labels: {e['labels']})")

assert len(entities) == 4, f"Expected 4 entities, got {len(entities)}"
print(f"\n[OK] TEST 1 PASSED")

# TEST 2: Search entities by text
print(f"\n{'='*60}")
print("TEST 2: Search Entities by Text")
print(f"{'='*60}")

results = graph_db.search_entities("test-project", query="knowledge storage")
print(f"\nSearch 'knowledge storage' found {len(results)} entities:")
for e in results:
    print(f"  - {e['name']}: {e['summary']}")

assert len(results) == 1, f"Expected 1 entity, got {len(results)}"
assert results[0]['name'] == "LadybugDB"
print(f"\n[OK] TEST 2 PASSED")

# TEST 3: Search entities by label
print(f"\n{'='*60}")
print("TEST 3: Search Entities by Label")
print(f"{'='*60}")

results = graph_db.get_entities_by_label("test-project", "technology")
print(f"\nEntities with label 'technology': {len(results)}")
for e in results:
    print(f"  - {e['name']}")

assert len(results) == 2, f"Expected 2 entities, got {len(results)}"
assert any(e['name'] == "LadybugDB" for e in results)
assert any(e['name'] == "Python" for e in results)
print(f"\n[OK] TEST 3 PASSED")

# TEST 4: Get entity by name
print(f"\n{'='*60}")
print("TEST 4: Get Entity by Name")
print(f"{'='*60}")

entity = graph_db.get_entity_by_name("test-project", "LadybugDB")
print(f"\nFound entity: {entity['name']}")
print(f"  Summary: {entity['summary']}")
print(f"  Labels: {entity['labels']}")
print(f"  UUID: {entity['uuid']}")

assert entity is not None
assert entity['name'] == "LadybugDB"
assert "database" in entity['labels']
print(f"\n[OK] TEST 4 PASSED")

# TEST 5: Get entity facts
print(f"\n{'='*60}")
print("TEST 5: Get Entity Facts")
print(f"{'='*60}")

facts = graph_db.get_entity_facts(ladybug_uuid)
print(f"\nFacts about LadybugDB: {len(facts)}")
for f in facts:
    print(f"  - [{f['direction']}] {f['fact']}")

assert len(facts) == 1, f"Expected 1 fact, got {len(facts)}"
assert facts[0]['fact'] == "LadybugDB is located at ./memory/knowledge.ladybug"
assert facts[0]['direction'] == "outgoing"
print(f"\n[OK] TEST 5 PASSED")

# TEST 6: Search facts
print(f"\n{'='*60}")
print("TEST 6: Search Facts")
print(f"{'='*60}")

facts = graph_db.search_facts("test-project", query="located")
print(f"\nSearch 'located' found {len(facts)} facts:")
for f in facts:
    print(f"  - {f['fact']}")

assert len(facts) == 1, f"Expected 1 fact, got {len(facts)}"
assert "located" in facts[0]['fact'].lower()
print(f"\n[OK] TEST 6 PASSED")

# TEST 7: Search facts by relationship type
print(f"\n{'='*60}")
print("TEST 7: Search Facts by Relationship Type")
print(f"{'='*60}")

facts = graph_db.search_facts("test-project", relationship_type="HAS_VERSION")
print(f"\nFacts with type 'HAS_VERSION': {len(facts)}")
for f in facts:
    print(f"  - {f['source_name']} -> {f['target_name']}: {f['fact']}")

assert len(facts) == 1, f"Expected 1 fact, got {len(facts)}"
assert facts[0]['relationship_type'] == "HAS_VERSION"
print(f"\n[OK] TEST 7 PASSED")

# TEST 8: Get entity by UUID
print(f"\n{'='*60}")
print("TEST 8: Get Entity by UUID")
print(f"{'='*60}")

entity = graph_db.get_entity_by_uuid(python_uuid)
print(f"\nFound entity: {entity['name']}")
print(f"  UUID: {entity['uuid']}")
print(f"  Labels: {entity['labels']}")

assert entity is not None
assert entity['uuid'] == python_uuid
assert entity['name'] == "Python"
print(f"\n[OK] TEST 8 PASSED")

# TEST 9: Get facts about entity (incoming)
print(f"\n{'='*60}")
print("TEST 9: Get Facts (Incoming Relationships)")
print(f"{'='*60}")

facts = graph_db.get_entity_facts(version_uuid)
print(f"\nFacts about '3.9': {len(facts)}")
for f in facts:
    print(f"  - [{f['direction']}] {f['fact']}")

assert len(facts) == 1, f"Expected 1 fact, got {len(facts)}"
assert facts[0]['direction'] == "incoming"
assert facts[0]['source_name'] == "Python"
print(f"\n[OK] TEST 9 PASSED")

print(f"\n{'='*60}")
print(f"[OK] ALL QUERY TESTS PASSED!")
print(f"{'='*60}")
print(f"\nTested:")
print(f"  - Get all entities")
print(f"  - Search entities by text")
print(f"  - Search entities by label")
print(f"  - Get entity by name")
print(f"  - Get entity by UUID")
print(f"  - Get entity facts (outgoing)")
print(f"  - Get entity facts (incoming)")
print(f"  - Search facts by text")
print(f"  - Search facts by relationship type")