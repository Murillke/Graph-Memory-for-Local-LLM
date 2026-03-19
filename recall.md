# recall.md - Time-Aware Memory Query

---

## [BOT] Config First

**Read `mem.config.json` before running any command:**
- Use `python_path` value for `{PYTHON_PATH}`
- Use `project_name` value for `{PROJECT}`
- Do not guess or substitute different values

---

## LLM Instructions

**Step 1:** Get system time (DO NOT trust system prompt date!)
```sh
date
```

**Step 2:** Calculate date range from user request

**Step 3:** Run recall.py
```sh
{PYTHON_PATH} scripts/recall.py --project {PROJECT} --start {START} --end {END}
```
- Understanding the "story" of what happened during those days
- Recall now includes task activity from SQL `task_operations` when the window contains task events

**This is like having a time machine for your knowledge graph!**

---

## What This Does

Query what you knew at a specific point in time with **hour-level precision**:
- See all entities created during a date range (or specific hours!)
- See task state changes that happened during the same window
- Timestamps shown by default (when each entity was created)
- Explore how concepts were connected back then
- Understand the "story" of what happened each day
- Time-aware memory awareness!

**New features:**
- [OK] Hour-level precision (e.g., 2026-03-06T00:00:00 to 2026-03-06T02:00:00)
- [OK] Timestamps shown by default
- [OK] Configurable entity limit (default: 50, use --limit to see more)
- [OK] Task activity section shown automatically when task events exist
- [OK] `--hide-task-activity` opt-out

**Use cases:**
- "What did we work on last week?"
- "Show me everything from March 3rd"
- "What did we do Friday midnight to 2am?" (hour-level!)
- "What was connected to Database Path Inconsistency back then?"

---

## Prerequisites

- Memory system initialized
- Entities stored in graph database
- Project name

---

## Query Time Period

```sh
{PYTHON_PATH} scripts/recall.py --project {PROJECT} --start {START_DATE} --end {END_DATE}
```

Use values from `mem.config.json` for `{PROJECT}` and `{PYTHON_PATH}`.

**Examples:**
```sh
# Query by date range
{PYTHON_PATH} scripts/recall.py --project {PROJECT} --start 2026-03-03 --end 2026-03-06

# Query by date + time (hour-level precision)
{PYTHON_PATH} scripts/recall.py --project {PROJECT} --start 2026-03-06T00:00:00 --end 2026-03-06T02:00:00

# Hide timestamps (shown by default)
{PYTHON_PATH} scripts/recall.py --project {PROJECT} --start 2026-03-06 --end 2026-03-06 --hide-time

# Show more entities (default: 50)
{PYTHON_PATH} scripts/recall.py --project {PROJECT} --start 2026-03-06 --end 2026-03-06 --limit 100

# Hide task activity section
{PYTHON_PATH} scripts/recall.py --project {PROJECT} --start 2026-03-06 --end 2026-03-06 --hide-task-activity
```

**Expected output:**
```
================================================================================
RECALL - Time-Aware Memory Query
================================================================================

Querying knowledge from 2026-03-03 to 2026-03-06...

================================================================================
[DATE] 2026-03-03 - 75 entities
================================================================================

1. SQL Database Architecture
   [TIME] 2026-03-03T10:15:23.456789
   SQL database stores only raw interactions, not entities...

2. Graph Database Architecture
   [TIME] 2026-03-03T10:16:45.123456
   Graph database stores extracted entities and facts...

3. Database Path Inconsistency
   [TIME] 2026-03-03T10:18:12.789012
   query_memory.py and store_extraction.py use different default database paths...

   ... and 72 more entities (use --limit to see more)

================================================================================
[*] 2026-03-04 - 55 entities
================================================================================

1. Architecture Diagrams
   Visual representations of system architecture...

   ... and 54 more entities

================================================================================
[*] SUMMARY
================================================================================
Total entities from 2026-03-03 to 2026-03-06: 176
Days with activity: 3
  2026-03-03: 75 entities
  2026-03-04: 55 entities
  2026-03-05: 46 entities
```

---

## Explore Entity Relationships

**Focus on a specific entity and see its connections:**

**Recommended (file-based, avoids quote issues):**
```sh
# Create tmp/entity.txt with entity name (use agent's file tools)
{PYTHON_PATH} scripts/recall.py --project {PROJECT} --start 2026-03-03 --end 2026-03-06 --entity-file tmp/entity.txt
```

**Direct `--entity` remains temporary backward compatibility only and is not part of the approved workflow.**
Direct `--entity` is rejected by default.
Set `MEM_ALLOW_DIRECT_INPUT=1` only for legacy/manual compatibility.

**Expected output:**
```
================================================================================
[GRAPH] RELATIONSHIPS - Database Path Inconsistency
================================================================================

  Incoming connections (3):
    ← DOCUMENTS ← CRITICAL-ISSUES-FOUND.md
      "CRITICAL-ISSUES-FOUND.md documents database path inconsistency issue..."
    ← RESOLVES ← 4-Phase Action Plan
      "4-Phase action plan resolves database path inconsistency..."
    ← RESOLVES ← Database Auto-Detection
      "Database auto-detection resolves database path inconsistency..."
```

---

## Task Activity In Recall

Recall now checks SQL `task_operations` for the same inclusive time window and shows a `TASK ACTIVITY` section when events exist.

Shown events:
- created
- started
- paused
- completed
- invalidated
- priority changed

Behavior:
- events are shown in chronological order
- the first 20 events are printed
- if more exist, recall prints a `... and N more task events` summary line
- `--entity-file` still only scopes the relationship section; task activity remains window-wide context
- use `--hide-task-activity` if the user only wants entity recall output

---

## Use Cases

### "What did we work on last week?"
```sh
{PYTHON_PATH} scripts/recall.py --project {PROJECT} --start 2026-02-24 --end 2026-03-03
```

### "Show me everything from March 3rd"
```sh
{PYTHON_PATH} scripts/recall.py --project {PROJECT} --start 2026-03-03 --end 2026-03-03
```

### "What was connected to X back then?"
```sh
# Create tmp/entity.txt with entity name, then:
{PYTHON_PATH} scripts/recall.py --project {PROJECT} --start 2026-03-03 --end 2026-03-06 --entity-file tmp/entity.txt
```

---

## What You Get

**Time-based view:**
- Entities grouped by day
- See what was created when
- Understand the timeline of knowledge

**Relationship exploration:**
- See how concepts connected
- Understand the "story" of that time
- Trace how problems were solved

**Memory awareness:**
- Know what you knew at a specific time
- See how knowledge evolved
- Time-travel through your memory!

---

**This is like having a time machine for your knowledge graph!** [*]

