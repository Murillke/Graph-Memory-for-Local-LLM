#!/bin/bash
# Test all wrapper scripts with a complete workflow

set -e

mkdir -p ./tmp
WRAPPER_MEM_CONFIG=./tmp/test-wrappers.mem.config.json
cat > "$WRAPPER_MEM_CONFIG" <<'EOF'
{
  "project_name": "test-wrappers",
  "python_path": "python3",
  "database": {
    "sql_path": "./memory/test-wrappers.db",
    "graph_path": "./memory/{project_name}.graph"
  },
  "paths": {
    "tmp_dir": "./tmp",
    "memory_dir": "./memory"
  }
}
EOF
export MEM_CONFIG="$WRAPPER_MEM_CONFIG"

echo "============================================================"
echo "Testing Wrapper Scripts - Complete Workflow"
echo "============================================================"

rm -rf ./memory/test-wrappers.db ./memory/test-wrappers.kuzu

echo ""
echo "Step 1: Store interactions"
echo "------------------------------------------------------------"
python3 scripts/store_interaction.py \
    --db ./memory/test-wrappers.db \
    --project "test-wrappers" \
    --user "We are using LadybugDB for the knowledge graph" \
    --assistant "Great choice! LadybugDB is perfect for this."

python3 scripts/store_interaction.py \
    --db ./memory/test-wrappers.db \
    --project "test-wrappers" \
    --user "It's located at ./memory/knowledge.ladybug" \
    --assistant "Got it, I'll remember that location."

python3 scripts/store_interaction.py \
    --db ./memory/test-wrappers.db \
    --project "test-wrappers" \
    --user "LadybugDB uses Python 3.9" \
    --assistant "Perfect, Python 3.9 is a solid choice."

echo ""
echo "[OK] Stored 3 interactions"

echo ""
echo "Step 2: Export conversation history"
echo "------------------------------------------------------------"
python3 scripts/export_history.py \
    --db ./memory/test-wrappers.db \
    --project "test-wrappers" \
    --limit 2

echo ""
echo "Step 3: Verify SQL hash chain"
echo "------------------------------------------------------------"
python3 scripts/verify_integrity.py \
    --sql-db ./memory/test-wrappers.db \
    --graph-db ./memory/test-wrappers.kuzu \
    --project "test-wrappers" \
    --sql

echo ""
echo "Step 4: Extract entities to graph (using Python API)"
echo "------------------------------------------------------------"
python3 <<'EOF'
import sys
sys.path.insert(0, '.')
from tools.sql_db import SQLDatabase
from tools.graph_db import GraphDatabase

sql_db = SQLDatabase('./memory/test-wrappers.db')
graph_db = GraphDatabase('./memory/test-wrappers.kuzu')
interactions = sql_db.get_all_interactions('test-wrappers')

graph_db.create_project_node('test-wrappers', 'Test project for wrappers')

ladybug = graph_db.create_entity(
    name='LadybugDB',
    group_id='test-wrappers',
    source_interactions=[interactions[0]['uuid']],
    source_hashes=[interactions[0]['content_hash']],
    extraction_version='v1.0.0',
    extraction_commit='abc123',
    summary='A graph database for knowledge storage',
    labels=['technology', 'database']
)
graph_db.link_project_to_entity('test-wrappers', ladybug)

location = graph_db.create_entity(
    name='./memory/knowledge.ladybug',
    group_id='test-wrappers',
    source_interactions=[interactions[1]['uuid']],
    source_hashes=[interactions[1]['content_hash']],
    extraction_version='v1.0.0',
    extraction_commit='abc123',
    summary='File path for LadybugDB storage',
    labels=['path', 'file']
)
graph_db.link_project_to_entity('test-wrappers', location)

python = graph_db.create_entity(
    name='Python',
    group_id='test-wrappers',
    source_interactions=[interactions[2]['uuid']],
    source_hashes=[interactions[2]['content_hash']],
    extraction_version='v1.0.0',
    extraction_commit='abc123',
    summary='Programming language',
    labels=['technology', 'language']
)
graph_db.link_project_to_entity('test-wrappers', python)

graph_db.create_relationship(
    source_uuid=ladybug,
    target_uuid=location,
    relationship_name='LOCATED_AT',
    fact='LadybugDB is located at ./memory/knowledge.ladybug',
    group_id='test-wrappers',
    episodes=[interactions[1]['uuid']],
    episode_hashes=[interactions[1]['content_hash']],
    derivation_version='v1.0.0',
    derivation_commit='abc123',
    valid_at='2026-03-01T00:00:00Z'
)

graph_db.create_relationship(
    source_uuid=ladybug,
    target_uuid=python,
    relationship_name='USES',
    fact='LadybugDB uses Python',
    group_id='test-wrappers',
    episodes=[interactions[2]['uuid']],
    episode_hashes=[interactions[2]['content_hash']],
    derivation_version='v1.0.0',
    derivation_commit='abc123',
    valid_at='2026-03-01T00:00:00Z'
)

print("[OK] Created 3 entities and 2 relationships")
EOF

echo ""
echo "Step 5: Query the knowledge graph"
echo "------------------------------------------------------------"
echo "5a. Search for 'LadybugDB':"
printf 'LadybugDB\n' > ./tmp/search.txt
python3 scripts/query_memory.py \
    --db ./memory/test-wrappers.kuzu \
    --project "test-wrappers" \
    --search-file ./tmp/search.txt

echo ""
echo "5b. Get facts about LadybugDB:"
printf 'LadybugDB\n' > ./tmp/entity.txt
python3 scripts/query_memory.py \
    --db ./memory/test-wrappers.kuzu \
    --project "test-wrappers" \
    --entity-file ./tmp/entity.txt

echo ""
echo "5c. Search for entities with label 'technology':"
python3 scripts/query_memory.py \
    --db ./memory/test-wrappers.kuzu \
    --project "test-wrappers" \
    --label "technology"

echo ""
echo "Step 6: Verify graph integrity"
echo "------------------------------------------------------------"
python3 scripts/verify_integrity.py \
    --sql-db ./memory/test-wrappers.db \
    --graph-db ./memory/test-wrappers.kuzu \
    --project "test-wrappers" \
    --all

echo ""
echo "============================================================"
echo "[OK] ALL WRAPPER TESTS PASSED!"
echo "============================================================"
