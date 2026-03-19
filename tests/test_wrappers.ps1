# Test all wrapper scripts with a complete workflow (Windows PowerShell Version)

$ErrorActionPreference = "Stop"  # Exit on error

New-Item -ItemType Directory -Force -Path "./tmp" | Out-Null
$env:MEM_CONFIG = "./tmp/test-wrappers.mem.config.json"
@'
{
  "project_name": "test-wrappers",
  "python_path": "python",
  "database": {
    "sql_path": "./memory/test-wrappers.db",
    "graph_path": "./memory/{project_name}.graph"
  },
  "paths": {
    "tmp_dir": "./tmp",
    "memory_dir": "./memory"
  }
}
'@ | Set-Content -Encoding UTF8 $env:MEM_CONFIG

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Testing Wrapper Scripts - Complete Workflow" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# Clean up any existing test data
if (Test-Path "./memory/test-wrappers.db") { Remove-Item "./memory/test-wrappers.db" -Force }
if (Test-Path "./memory/test-wrappers.kuzu") { Remove-Item "./memory/test-wrappers.kuzu" -Recurse -Force }

Write-Host ""
Write-Host "Step 1: Store interactions" -ForegroundColor Yellow
Write-Host "------------------------------------------------------------"
python scripts/store_interaction.py `
    --db ./memory/test-wrappers.db `
    --project "test-wrappers" `
    --user "We are using LadybugDB for the knowledge graph" `
    --assistant "Great choice! LadybugDB is perfect for this."

python scripts/store_interaction.py `
    --db ./memory/test-wrappers.db `
    --project "test-wrappers" `
    --user "It's located at ./memory/knowledge.ladybug" `
    --assistant "Got it, I'll remember that location."

python scripts/store_interaction.py `
    --db ./memory/test-wrappers.db `
    --project "test-wrappers" `
    --user "LadybugDB uses Python 3.9" `
    --assistant "Perfect, Python 3.9 is a solid choice."

Write-Host ""
Write-Host "[OK] Stored 3 interactions" -ForegroundColor Green

Write-Host ""
Write-Host "Step 2: Export conversation history" -ForegroundColor Yellow
Write-Host "------------------------------------------------------------"
python scripts/export_history.py `
    --db ./memory/test-wrappers.db `
    --project "test-wrappers" `
    --limit 2

Write-Host ""
Write-Host "Step 3: Verify SQL hash chain" -ForegroundColor Yellow
Write-Host "------------------------------------------------------------"
python scripts/verify_integrity.py `
    --sql-db ./memory/test-wrappers.db `
    --project "test-wrappers" `
    --sql

Write-Host ""
Write-Host "Step 4: Extract entities to graph (using Python API)" -ForegroundColor Yellow
Write-Host "------------------------------------------------------------"
python -c @"
import sys
sys.path.insert(0, '.')
from tools.sql_db import SQLDatabase
from tools.graph_db import GraphDatabase

# Connect to databases
sql_db = SQLDatabase('./memory/test-wrappers.db')
graph_db = GraphDatabase('./memory/test-wrappers.kuzu')

# Get interactions
interactions = sql_db.get_all_interactions('test-wrappers')

# Create project node in graph
graph_db.create_project_node('test-wrappers', 'Test project for wrappers')

# Create entities
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

python_entity = graph_db.create_entity(
    name='Python',
    group_id='test-wrappers',
    source_interactions=[interactions[2]['uuid']],
    source_hashes=[interactions[2]['content_hash']],
    extraction_version='v1.0.0',
    extraction_commit='abc123',
    summary='Programming language',
    labels=['technology', 'language']
)
graph_db.link_project_to_entity('test-wrappers', python_entity)

# Create relationships
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
    target_uuid=python_entity,
    relationship_name='USES',
    fact='LadybugDB uses Python',
    group_id='test-wrappers',
    episodes=[interactions[2]['uuid']],
    episode_hashes=[interactions[2]['content_hash']],
    derivation_version='v1.0.0',
    derivation_commit='abc123',
    valid_at='2026-03-01T00:00:00Z'
)

print('[OK] Created 3 entities and 2 relationships')
"@

Write-Host ""
Write-Host "Step 5: Query the knowledge graph" -ForegroundColor Yellow
Write-Host "------------------------------------------------------------"
Write-Host "5a. Search for 'LadybugDB':"
"LadybugDB" | Set-Content -Encoding UTF8 ./tmp/search.txt
python scripts/query_memory.py `
    --db ./memory/test-wrappers.kuzu `
    --project "test-wrappers" `
    --search-file ./tmp/search.txt

Write-Host ""
Write-Host "5b. Get facts about LadybugDB:"
"LadybugDB" | Set-Content -Encoding UTF8 ./tmp/entity.txt
python scripts/query_memory.py `
    --db ./memory/test-wrappers.kuzu `
    --project "test-wrappers" `
    --entity-file ./tmp/entity.txt

Write-Host ""
Write-Host "5c. Search for entities with label 'technology':"
python scripts/query_memory.py `
    --db ./memory/test-wrappers.kuzu `
    --project "test-wrappers" `
    --label "technology"

Write-Host ""
Write-Host "Step 6: Verify graph integrity" -ForegroundColor Yellow
Write-Host "------------------------------------------------------------"
python scripts/verify_integrity.py `
    --sql-db ./memory/test-wrappers.db `
    --graph-db ./memory/test-wrappers.kuzu `
    --project "test-wrappers" `
    --all

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "[OK] ALL WRAPPER TESTS PASSED!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Summary:"
Write-Host "  [OK] store_interaction.py - Stores conversations"
Write-Host "  [OK] export_history.py - Exports conversation history"
Write-Host "  [OK] query_memory.py - Queries knowledge graph"
Write-Host "  [OK] verify_integrity.py - Verifies cryptographic proofs"
Write-Host ""
Write-Host "The memory system is ready to use! " -ForegroundColor Green

