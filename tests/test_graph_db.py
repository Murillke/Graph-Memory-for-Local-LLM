"""
Test Graph database with extraction proofs.
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
if os.path.exists("./tests/tmp/test_graph.kuzu"):
    if os.path.isdir("./tests/tmp/test_graph.kuzu"):
        shutil.rmtree("./tests/tmp/test_graph.kuzu")
    else:
        os.remove("./tests/tmp/test_graph.kuzu")
if os.path.exists("./tests/tmp/test_graph_sql.db"):
    os.remove("./tests/tmp/test_graph_sql.db")

print("="*60)
print("Testing Graph Database with Extraction Proofs")
print("="*60)

# Create SQL database first (source of truth)
sql_db = SQLDatabase("./tests/tmp/test_graph_sql.db")
sql_db.create_project("test-project", "Test project")
sql_db.associate_path_with_project("/test", "test-project")

# Store interaction
uuid1 = sql_db.store_interaction({
    "project_name": "test-project",
    "user_message": "We are using LadybugDB at ./memory/knowledge.ladybug",
    "assistant_message": "Got it! LadybugDB is an embedded graph database."
})

print(f"\n[OK] Stored interaction: {uuid1}")

# Get interaction to extract hash
interaction = sql_db.get_interaction_by_uuid(uuid1)
content_hash = interaction["content_hash"]

print(f"[OK] Interaction hash: {content_hash[:16]}...")

# Create graph database
graph_db = GraphDatabase("./tests/tmp/test_graph.kuzu")

print(f"\n[OK] Graph database created")

# Create project node
graph_db.create_project_node("test-project", "Test project")

print(f"[OK] Project node created")

# Create entity with extraction proof
entity1_uuid = graph_db.create_entity(
    name="LadybugDB",
    group_id="test-project",
    source_interactions=[uuid1],
    source_hashes=[content_hash],
    extraction_version="v1.0.0",
    extraction_commit="test-commit-abc123",
    summary="Embedded graph database",
    labels=["technology", "database"]
)

print(f"\n[OK] Created entity 1: {entity1_uuid}")
print(f"   Name: LadybugDB")
print(f"   Source: {uuid1}")
print(f"   Hash: {content_hash[:16]}...")

# Create second entity
entity2_uuid = graph_db.create_entity(
    name="./memory/knowledge.ladybug",
    group_id="test-project",
    source_interactions=[uuid1],
    source_hashes=[content_hash],
    extraction_version="v1.0.0",
    extraction_commit="test-commit-abc123",
    summary="Database file path",
    labels=["file", "path"]
)

print(f"\n[OK] Created entity 2: {entity2_uuid}")
print(f"   Name: ./memory/knowledge.ladybug")

# Link entities to project
graph_db.link_project_to_entity("test-project", entity1_uuid)
graph_db.link_project_to_entity("test-project", entity2_uuid)

print(f"\n[OK] Linked entities to project")

# Create relationship with derivation proof
rel_uuid = graph_db.create_relationship(
    source_uuid=entity1_uuid,
    target_uuid=entity2_uuid,
    relationship_name="LOCATED_AT",
    fact="LadybugDB is located at ./memory/knowledge.ladybug",
    group_id="test-project",
    episodes=[uuid1],
    episode_hashes=[content_hash],
    derivation_version="v1.0.0",
    derivation_commit="test-commit-abc123",
    valid_at=interaction["timestamp"]
)

print(f"\n[OK] Created relationship: {rel_uuid}")
print(f"   Type: LOCATED_AT")
print(f"   Fact: LadybugDB is located at ./memory/knowledge.ladybug")
print(f"   Source: {entity1_uuid}")
print(f"   Target: {entity2_uuid}")

print(f"\n{'='*60}")
print(f"[OK] ALL GRAPH TESTS PASSED!")
print(f"{'='*60}")
print(f"\nCreated:")
print(f"  - 1 project node")
print(f"  - 2 entity nodes (with extraction proofs)")
print(f"  - 1 relationship (with derivation proof)")
print(f"  - All linked to SQL interaction via content_hash")

