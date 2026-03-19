# Quick Start Guide

Get started with the memory system in 5 minutes.

---

## Key Concept - Two Databases

**IMPORTANT: Understand the architecture first!**

**Graph Database (PRIMARY - THE MEMORY):**
- Stores entities, facts, relationships
- **This is what you query** to remember things
- Main entry point to the memory system
- Use `query_memory.py` to access

**SQL Database (SECONDARY - AUDIT LOG):**
- Stores raw conversation history
- Optional provenance trail
- Can be lost without losing knowledge
- Use `export_history.py` to access

**When someone asks "what did we discuss about X?" -> Query the GRAPH, not SQL!**

---

## Installation

### 1. Check Python Version

```bash
python --version
```

**Requirements:**
- Python 3.8-3.13 (NOT 3.14+)
- kuzu 0.11.0+
- SQLite (built-in)

**If you have Python 3.14:** See WINDOWS-SETUP.md or install Python 3.13.

---

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

---

### 3. Run Health Check

```bash
python scripts/health_check.py
```

**Expected output:**
```
[OK] ALL CHECKS PASSED!
Your system is ready to use.
```

**If checks fail:** See TROUBLESHOOTING.md

---

### 4. Verify Database Setup

The memory directory will be created automatically on first use. You'll have:

- `./memory/conversations.db` - SQL database (all projects)
- `./memory/{project}.graph` - Graph database (per project)

---

## Basic Usage

### Store a Conversation

```bash
python3 scripts/store_interaction.py \
    --project "my-project" \
    --user "Let's build a web app" \
    --assistant "Great! I'll help you build a web app."
```

**Output:**
```
[OK] Interaction stored successfully!

[LIST] Details:
   UUID:         uuid-abc123
   Project:      my-project
   Chain Index:  1
   Content Hash: sha256-def456...
```

---

### Store Extraction (Knowledge Graph)

After storing interactions, you can extract entities and facts:

```bash
python scripts/store_extraction.py \
    --project "my-project" \
    --extraction-file extraction.json
```

**Quality review behavior:**
- Default: `store_extraction.py` runs configured quality checks automatically
- Manual blocking review: use `--require-quality-review --quality-answers-file tmp/quality-answers.json`
- The script no longer pauses waiting for a root-level `quality-answers.json`
- If the wrapper in `mem.config.json` is `null`, missing, or empty, there is
  no automatic reviewer and the current agent must review the generated
  questions itself or deliberately use `--skip-quality-check`

**See:** [LLM-INSTRUCTIONS.md](../LLM-INSTRUCTIONS.md) for complete details.

---

### Query the Knowledge Graph

```bash
# Get all entities (verify data was stored)
python scripts/query_memory.py \
    --project "my-project" \
    --all

# Search for entities
python scripts/query_memory.py \
    --project "my-project" \
    --search-file tmp/search.txt

# Get facts about an entity
python scripts/query_memory.py \
    --project "my-project" \
    --entity-file tmp/entity.txt

# Use verbose mode to see which database file is being used
python scripts/query_memory.py \
    --project "my-project" \
    --all \
    --verbose
```

**If query returns 0 entities:** See TROUBLESHOOTING.md section "Query Returns 0 Results"

---

### Verify Cryptographic Integrity

Every piece of data in the memory system has cryptographic proof of origin. You can verify:

**Verify everything:**
```bash
python scripts/verify_integrity.py --project "my-project" --all
```

**Verify just SQL hash chain:**
```bash
python scripts/verify_integrity.py --project "my-project" --sql
```

**Verify just graph proofs:**
```bash
python scripts/verify_integrity.py --project "my-project" --graph
```

**Verify specific entity:**
```bash
python scripts/verify_integrity.py --entity "entity-abc123"
```

**Expected output:**
```
[SEARCH] Verifying SQL hash chain for project 'my-project'...
[OK] Hash chain verified!
   Total interactions: 27

[SEARCH] Verifying entity extraction proofs for project 'my-project'...
[OK] All 37 entities verified!

[SEARCH] Verifying relationship derivation proofs for project 'my-project'...
[OK] All 21 relationships verified!

============================================================
[OK] ALL VERIFICATIONS PASSED!
============================================================
```

**What gets verified:**

1. **Integrity Proof** - The SQL hash chain shows each interaction links to the previous one
2. **Entity Derivation Proofs** - Each entity can be checked against its source interaction hashes
3. **Relationship Derivation Proofs** - Each fact can be checked against its source episode hashes

**See:** [CRYPTO-PROOFS.md](CRYPTO-PROOFS.md) for complete technical documentation

---

### Export History

```bash
# Export to stdout
python3 scripts/export_history.py \
    --project "my-project"

# Export to file
python3 scripts/export_history.py \
    --project "my-project" \
    --output history.txt

# Export with verification
python3 scripts/export_history.py \
    --project "my-project" \
    --verify
```

---

## Python API Usage

### Store Interaction

```python
from tools.sql_db import SQLDatabase

db = SQLDatabase('./memory/conversations.db')

interaction = {
    'project_name': 'my-project',
    'user_message': 'Let\'s build a web app',
    'assistant_message': 'Great! I\'ll help you.'
}

uuid = db.store_interaction(interaction)
print(f"Stored: {uuid}")
```

---

### Create Entity

```python
from tools.graph_db import GraphDatabase

graph_db = GraphDatabase('./memory/my-project.graph')

# Create project node first
graph_db.create_project_node('my-project', 'My project description')

# Create entity
entity_uuid = graph_db.create_entity(
    name='React',
    group_id='my-project',
    source_interactions=['uuid-abc123'],
    source_hashes=['sha256-def456...'],
    extraction_version='v1.0.0',
    extraction_commit='abc123',
    summary='Frontend framework',
    labels=['technology', 'frontend']
)

# Link to project
graph_db.link_project_to_entity('my-project', entity_uuid)
```

---

### Query Entities

```python
# Search
entities = graph_db.search_entities('my-project', query='React')

# Get by name
entity = graph_db.get_entity_by_name('my-project', 'React')

# Get facts
facts = graph_db.get_entity_facts(entity['uuid'])

# Get related entities
related = graph_db.get_related_entities(entity['uuid'], direction='both')
```

---

### Verify Integrity

```python
# Verify SQL hash chain
result = db.verify_interaction_chain('my-project')
if result['verified']:
    print(f"[OK] Chain verified ({result['total_interactions']} interactions)")

# Verify entity extraction proof
result = graph_db.verify_entity_extraction(entity_uuid)
if result['verified']:
    print(f"[OK] Entity verified")

# Verify relationship derivation proof
result = graph_db.verify_relationship_derivation(rel_uuid)
if result['verified']:
    print(f"[OK] Relationship verified")
```

---

## Complete Example

```python
from tools.sql_db import SQLDatabase
from tools.graph_db import GraphDatabase

# Initialize
sql_db = SQLDatabase('./memory/conversations.db')
graph_db = GraphDatabase('./memory/my-project.graph')

# Store interaction
interaction = sql_db.store_interaction({
    'project_name': 'my-project',
    'user_message': 'We are using React',
    'assistant_message': 'Great choice!'
})

# Get the stored interaction
stored = sql_db.get_interaction_by_uuid(interaction)

# Create project in graph
graph_db.create_project_node('my-project')

# Extract entity
entity_uuid = graph_db.create_entity(
    name='React',
    group_id='my-project',
    source_interactions=[stored['uuid']],
    source_hashes=[stored['content_hash']],
    extraction_version='v1.0.0',
    extraction_commit='manual',
    summary='Frontend framework',
    labels=['technology']
)
graph_db.link_project_to_entity('my-project', entity_uuid)

# Query
entities = graph_db.search_entities('my-project', query='React')
print(f"Found {len(entities)} entities")

# Verify
sql_result = sql_db.verify_interaction_chain('my-project')
graph_result = graph_db.verify_entity_extraction(entity_uuid)

print(f"SQL verified: {sql_result['verified']}")
print(f"Graph verified: {graph_result['verified']}")
```

---

## Next Steps

1. Read [AUGGIE-INTEGRATION.md](./AUGGIE-INTEGRATION.md) for integration guide
2. Read [AUGGIE-EXAMPLE.md](./AUGGIE-EXAMPLE.md) for real-world examples
3. Run `tests/test_integration.py` to see it in action
4. Implement LLM-based extraction in `scripts/extract_knowledge.py`

---

## Troubleshooting

### "Could not set lock on file"

**Problem:** Kuzu doesn't allow multiple connections to the same database.

**Solution:** Close connections before opening new ones:
```python
graph_db.conn.close()
graph_db.db.close()
```

### "Project not found"

**Problem:** Project doesn't exist in the database.

**Solution:** Create the project first:
```python
sql_db.create_project('my-project', 'Description')
graph_db.create_project_node('my-project', 'Description')
```

---

## Documentation

- [Database Schema](./database-schema.md) - Complete schema
- [Tool Interfaces](./tool-interfaces.md) - All 25+ functions
- [Workflows](./workflows.md) - Common usage patterns
- [Crypto Proofs](./CRYPTO-PROOFS.md) - Cryptographic system
- [Graph Traversal](./GRAPH-TRAVERSAL.md) - Query and traversal
- [Integration](./AUGGIE-INTEGRATION.md) - Auggie integration

---

**Ready to build! **

