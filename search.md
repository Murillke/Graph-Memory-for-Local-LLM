# search.md - Advanced Search

**What this does:** Advanced filtering by entity type, relationship type, direction, UUID.

**For basic queries (all, last N, text search), see [remember.md](remember.md).**

---

## [BOT] Config First

**Read `mem.config.json` before running any command:**
- Use `python_path` value for `{PYTHON_PATH}`
- Use `project_name` value for `{PROJECT}`
- Do not guess or substitute different values

---

## Quick Reference

**Common patterns:**
```
By label:        query_memory.py --label Bug
By relationship: query_memory.py --type USES
By UUID:         query_memory.py --project {PROJECT} --entity-uuid entity-abc123
By direction:    query_memory.py --project {PROJECT} --entity-file tmp/entity.txt --direction incoming
```

**IMPORTANT: For searches with spaces, use file-based input:**
- Create `tmp/search.txt` with the search query
- Use `--search-file tmp/search.txt` instead of inline search text flags
- Deprecated direct search/name flags are rejected by default
- Set `MEM_ALLOW_DIRECT_INPUT=1` only for legacy/manual compatibility

**CRITICAL: If user asks for time-based searches (e.g., "last 4 hours"):**
Do NOT trust your system prompt date - it may be wrong (timezone/UTC issues).
Run `date` FIRST to get the real system time.

**Follow the instructions below for advanced search options.**

**Replace `{PYTHON_PATH}` and `{PROJECT}` with values from mem.config.json**

---

## What This Does

Provides advanced search capabilities beyond basic queries.

---

## Search by Entity Type

```sh
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --label "{TYPE}"
```

**Replace {TYPE}** with entity type (e.g., "Library", "Bug", "Feature")

**Example:**
```sh
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --label "Bug"
```

**Expected output:** All entities of type "Bug"

---

## Search by Relationship Type

```sh
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --type "{RELATIONSHIP}"
```

**Replace {RELATIONSHIP}** with relationship type (e.g., "USES", "REQUIRES", "FIXES")

**Example:**
```sh
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --type "FIXES"
```

**Expected output:** All facts with "FIXES" relationship

---

## Search by UUID

```sh
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --entity-uuid "{UUID}"
```

**Replace {UUID}** with entity UUID (e.g., "entity-abc123")

**Example:**
```sh
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --entity-uuid "entity-abc123"
```

**Expected output:** Specific entity by UUID

---

## Traverse Relationships

**Get incoming relationships:**
```sh
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --entity-file tmp/entity.txt --direction incoming
```

**Get outgoing relationships:**
```sh
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --entity-file tmp/entity.txt --direction outgoing
```

**Get both directions:**
```sh
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --entity-file tmp/entity.txt --direction both
```

---

## Combine Filters

**Search + Type:**
```sh
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --search-file tmp/search.txt --label "Library"
```

**Entity + Relationship Type:**
```sh
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --entity-file tmp/entity.txt --type "USES"
```

---

## Output Formats

**JSON (for parsing):**
```sh
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --all --json
```

**Verbose (detailed):**
```sh
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --all --verbose
```

**Limited results:**
```sh
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --all --limit 5
```

---

## Examples

**"Find all bugs"**
```sh
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --label "Bug"
```

**"What does React use?"**
```sh
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --entity-file tmp/entity.txt --type "USES"
```

**"What uses React?"**
```sh
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --entity-file tmp/entity.txt --direction incoming
```

**"Find all FIXES relationships"**
```sh
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --type "FIXES"
```

---

**Advanced search complete!**

