# remember.md - Query Memory

**What this does:** Search the knowledge graph for entities, facts, and relationships.

---

## [BOT] Config First

**Read `mem.config.json` before running any command:**
- Use `python_path` value for `{PYTHON_PATH}`
- Use `project_name` value for `{PROJECT}`
- Do not guess or substitute different values

---

## Quick Reference

**Step 0:** Prepare helper files
```sh
{PYTHON_PATH} scripts/prepare_sync_files.py --project {PROJECT} --json
```

Use `search_file` or `entity_file` from output for queries.

**Query patterns:**
```
Search:       query_memory.py --search-file tmp/search.txt
Entity:       query_memory.py --entity-file tmp/entity.txt
All:          query_memory.py --all
Recent:       query_memory.py --last 10
```

---

## Search for Topic

**Step 1:** Prepare files
```sh
{PYTHON_PATH} scripts/prepare_sync_files.py --project {PROJECT} --json
```

**Step 2:** Edit `tmp/search.txt` with your query (use str-replace-editor)

**Step 3:** Run search
```sh
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --search-file tmp/search.txt
```

**Expected output:**
```
[SEARCH] Searching for entities matching 'your query'...

[PACKAGE] React
   Summary: JavaScript library for building user interfaces

Total entities: 1
```

---

## Get Entity Details

**Step 1:** Prepare files (if not already done)
```sh
{PYTHON_PATH} scripts/prepare_sync_files.py --project {PROJECT} --json
```

**Step 2:** Edit `tmp/entity.txt` with entity name (use str-replace-editor)

**Step 3:** Run query
```sh
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --entity-file tmp/entity.txt
```

**Expected output:**
```
[PACKAGE] React
   Summary: JavaScript library for building user interfaces

[FACTS] Relationships:
   React --[USES]--> Component
   React --[DEPENDS_ON]--> Node.js
```

---

## Quick Queries

```sh
# Get all entities
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --all

# Get last 10 entities
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --last 10

# Search / entity lookups still use helper files
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --search-file tmp/search.txt
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --entity-file tmp/entity.txt
```

---

## If Needed

### Filter by type
```sh
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --all --type USES
```

### JSON output
```sh
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --all --json
```

### Limit results
```sh
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --all --limit 20
```

### Verbose output
```sh
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --all --verbose
```

### Search procedures
```sh
# Edit tmp/search.txt with procedure search term
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --search-procedures-file tmp/search.txt
```

---

## Anti-Patterns (DO NOT)

| Don't | Why |
|-------|-----|
| Use inline search text flags | Direct search strings are deprecated for workflow use |
| Use inline entity name flags | Direct entity strings are deprecated for workflow use |
| Use shell echo for file creation | Encoding issues; use save-file tool |
| Skip prepare_sync_files.py | Helper files may have stale content |

---

## Troubleshooting

**"No entities found"**
- Have you synced conversations? See sync.md
- Check project name is correct

**"Project not found"**
- Project doesn't exist yet
- Run sync.md first

**"Direct flag rejected"**
- Direct query/name flags are disabled by default
- Use `--search-file tmp/search.txt` or `--entity-file tmp/entity.txt`
- Set `MEM_ALLOW_DIRECT_INPUT=1` only for legacy/manual compatibility

---

## Success Criteria

- [OK] Query returns entities/facts
- [OK] Multi-word queries use file-backed input
- [OK] Results match expected format
