# remember-external.md - Query Other Projects

**What this does:** Query knowledge from OTHER projects in a shared database.

**Same query patterns as [remember.md](remember.md), just with a different `--project` value.**

---

## [BOT] Config First

**Read `mem.config.json` before running any command:**
- Use `python_path` value for `{PYTHON_PATH}`
- Use `project_name` for your project, but query other projects by name

---

## Quick Reference

**Hot path:**
```
1. List projects         -> query_memory.py --list-projects
2. Prepare helper files  -> prepare_sync_files.py --json
3. Query other project   -> query_memory.py --project {OTHER} --search-file tmp/search.txt
```

---

## Step 1: Discover Projects

```sh
{PYTHON_PATH} scripts/query_memory.py --list-projects
```

**Expected output:**
```
Available projects:
  - llm_memory
  - backend-api
  - frontend-auth
```

---

## Step 2: Query Other Project

**Prepare helper files:**
```sh
# Use your current project for helper file creation (any project works)
{PYTHON_PATH} scripts/prepare_sync_files.py --project {YOUR_PROJECT} --json
# Edit tmp/search.txt or tmp/entity.txt with your query
```

**Search other project:**
```sh
{PYTHON_PATH} scripts/query_memory.py --project backend-api --search-file tmp/search.txt
```

**Get entity from other project:**
```sh
{PYTHON_PATH} scripts/query_memory.py --project backend-api --entity-file tmp/entity.txt
```

**Get all from other project:**
```sh
{PYTHON_PATH} scripts/query_memory.py --project backend-api --all
```

---

## Quick Queries

```sh
# Get all entities
{PYTHON_PATH} scripts/query_memory.py --project backend-api --all

# Search / entity lookups use helper files
{PYTHON_PATH} scripts/query_memory.py --project backend-api --search-file tmp/search.txt

# Filter by label
{PYTHON_PATH} scripts/query_memory.py --project backend-api --label Library

# Get related entities (need UUID from previous query)
{PYTHON_PATH} scripts/query_memory.py --project backend-api --entity-uuid entity-abc123 --related
```

---

## Use Cases

**Frontend learns backend APIs:**
```sh
{PYTHON_PATH} scripts/query_memory.py --project backend-api --label Endpoint
```

**Discover what libraries another team uses:**
```sh
{PYTHON_PATH} scripts/query_memory.py --project backend-api --label Library
```

---

## Comparison: remember-external vs search-external

| Doc | Use When | Command Pattern |
|-----|----------|-----------------|
| **remember-external.md** | You know which project to query | `--project {OTHER} --search-file` |
| **search-external.md** | You want to search ALL projects | `--search-file --all-projects` |

---

## Anti-Patterns (DO NOT)

| Don't | Why |
|-------|-----|
| Use inline search text flags | Direct search strings are deprecated for workflow use |
| Use inline entity name flags | Direct entity strings are deprecated for workflow use |
| Query without listing projects first | Project may not exist |
| Skip prepare_sync_files.py | Helper files may be stale |

---

## Troubleshooting

**"Project not found"**
- Use `--list-projects` to see available projects
- Check spelling (case-sensitive)

**"No entities found"**
- Project exists but has no data yet

**"Direct flag rejected"**
- Direct query/name flags are disabled by default
- Use helper files such as `tmp/search.txt` or `tmp/entity.txt`
- Set `MEM_ALLOW_DIRECT_INPUT=1` only for legacy/manual compatibility

---

## Success Criteria

- [OK] Projects listed with --list-projects
- [OK] Query returns entities from other project
- [OK] Multi-word queries use file-backed input
