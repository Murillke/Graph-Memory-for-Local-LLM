# search-external.md - Search Across All Projects

**What this does:** Search for entities across ALL projects in a shared database.

**For querying ONE specific project, see [remember-external.md](remember-external.md).**

---

## [BOT] Config First

**Read `mem.config.json` before running any command:**
- Use `python_path` value for `{PYTHON_PATH}`
- Cross-project search uses `--all-projects` flag

---

## Quick Reference

**Hot path:**
```
1. List projects         -> query_memory.py --list-projects
2. Prepare helper files  -> prepare_sync_files.py --json
3. Search all projects   -> query_memory.py --search-file tmp/search.txt --all-projects
```

---

## Step 1: List Projects

```sh
{PYTHON_PATH} scripts/query_memory.py --list-projects
```

See what projects exist in the shared database.

---

## Step 2: Search Across All Projects

**Prepare helper file:**
```sh
{PYTHON_PATH} scripts/prepare_sync_files.py --project {YOUR_PROJECT} --json
# Edit tmp/search.txt with your search term
```

**Run cross-project search:**
```sh
{PYTHON_PATH} scripts/query_memory.py --search-file tmp/search.txt --all-projects
```

**Expected output:**
```
[SEARCH] Searching across ALL projects for 'authentication'...

[PROJECT: frontend-auth]
  [ENTITY] JWT Token (Type: Security)
     Summary: JSON Web Token for user authentication

[PROJECT: backend-api]
  [ENTITY] Auth Middleware (Type: Code)
     Summary: Express middleware for JWT validation

Total entities: 2 (across 2 projects)
```

---

## Quick Queries

```sh
{PYTHON_PATH} scripts/query_memory.py --search-file tmp/search.txt --all-projects
```

---

## Use Cases

**"Who else is working on authentication?"**
```sh
# Edit tmp/search.txt: authentication
{PYTHON_PATH} scripts/query_memory.py --search-file tmp/search.txt --all-projects
```

**"Is this already solved somewhere?"**
```sh
# Edit tmp/search.txt: user management
{PYTHON_PATH} scripts/query_memory.py --search-file tmp/search.txt --all-projects
```

---

## Comparison: search-external vs remember-external

| Doc | Use When | Command Pattern |
|-----|----------|-----------------|
| **search-external.md** | Search ALL projects | `--search-file tmp/search.txt --all-projects` |
| **remember-external.md** | Query ONE specific project | `--project {OTHER} --search-file` |

---

## Anti-Patterns (DO NOT)

| Don't | Why |
|-------|-----|
| Use inline search text flags | Direct search strings are deprecated for workflow use |
| Use `--all-projects` without a search input file | Only works with search |
| Query one project here | Use remember-external.md instead |

Deprecated direct search text flags are rejected by default.
Set `MEM_ALLOW_DIRECT_INPUT=1` only for legacy/manual compatibility.

---

## Success Criteria

- [OK] Projects listed with --list-projects
- [OK] Cross-project search returns entities from multiple projects
- [OK] Multi-word searches use file-backed input
