# import.md - Import New Project

---

## [BOT] Config First

**Read `mem.config.json` before running any command:**
- Use `python_path` value for `{PYTHON_PATH}`
- Use `project_name` value for `{PROJECT}`
- Do not guess or substitute different values

---

## PARTIAL IMPLEMENTATION

**Status:**
- `--list` - List projects in source database (WORKING)
- `--check` - Check for conflicts (WORKING, requires distinct source DB)
- `--import` - Execute import (NOT YET IMPLEMENTED)

**What you CAN do now:** Inspect source databases and check for conflicts.
**What you CANNOT do yet:** Actually import data.

**Limitation:** `--check` requires a distinct source database. Using the same DB as source and target causes a graph lock error.

---

## [BOT] LLM INSTRUCTIONS

**If you have been instructed to "follow import.md", "execute import.md", or "run import.md", you are expected to:**

1. **List projects in source database** using `--list`
2. **Check for conflicts** using `--check`
3. **STOP and inform user** that `--import` is not yet implemented

**You are capable of:**
- Listing available projects in source database
- Checking if a project name conflicts with existing projects
- Reporting source/target statistics

**You CANNOT yet:**
- Actually import data (--import is not implemented)

---

## What This Will Do (When Implemented)

Import a complete project from another database into your database:
1. Validates source database
2. Checks for project name conflicts
3. Imports all interactions (with hash chain)
4. Imports all entities and facts
5. Preserves cryptographic proofs

**Use Case:**
- Colleague worked on a project, now you want access to their knowledge
- You started a project on another machine, want to import it here
- Merging team member's work into shared database

---

## Prerequisites

- Source database exists and is accessible
- Project name doesn't conflict (or you want to merge)
- Python environment set up

---

## Instructions

### Step 1: Inspect Source Database

```sh
{PYTHON_PATH} scripts/import_project.py \
  --source-sql "/path/to/source/memory/interactions.db" \
  --source-graph "/path/to/source/memory/knowledge.graph" \
  --list
```

**Expected output:**
```
[INFO] Inspecting source database...

[PROJECTS FOUND]
  1. frontend-auth
     - Interactions: 42
     - Entities: 67
     - Created: 2026-01-15
     - Last updated: 2026-03-04

  2. backend-api
     - Interactions: 28
     - Entities: 45
     - Created: 2026-02-01
     - Last updated: 2026-03-03

[ACTION]
Choose project to import with --project flag
```

---

### Step 2: Check for Conflicts

```sh
{PYTHON_PATH} scripts/import_project.py \
  --source-sql "/path/to/source/memory/interactions.db" \
  --source-graph "/path/to/source/memory/knowledge.graph" \
  --project frontend-auth \
  --check
```

**Expected output (no conflict):**
```
[INFO] Checking for conflicts...
[OK] Project "frontend-auth" does not exist in current database
[OK] Safe to import
```

**Expected output (conflict):**
```
[WARNING] Project "frontend-auth" already exists in current database!

[CURRENT DATABASE]
  Interactions: 15
  Entities: 23

[SOURCE DATABASE]
  Interactions: 42
  Entities: 67

[OPTIONS] (when --import is implemented)
  Import with different name: --rename new-name
```

---

### Step 3: Import Project (NOT YET IMPLEMENTED)

⚠️ **The `--import` flag is not yet implemented.**

When implemented, it will:
1. Create backup of current database
2. Import interactions with hash chain verification
3. Import entities and facts
4. Verify cryptographic proofs

For now, use `--list` and `--check` only.

## Options

| Flag | Status | Description |
|------|--------|-------------|
| `--list` | WORKING | List all projects in source database |
| `--check` | WORKING | Check for conflicts (requires distinct source DB) |
| `--import` | NOT IMPLEMENTED | Execute import |

---

## Planned Features (When Implemented)

**Automatic Backup:**
- Before import, current database will be backed up
- Location: `memory/backup-YYYY-MM-DD-HH-MM-SS/`

**Hash Chain Verification:**
- Will verify source hash chain before import
- Ensures data integrity
- Rejects corrupted databases

**Proof Verification:**
- Verifies all extraction proofs
- Verifies all derivation proofs
- Ensures cryptographic integrity

**Rollback:**
- If import fails, restore from backup
- Copy backup files back to `mem/memory/`

---

## Troubleshooting

**"Source database not found"**
- Check file paths are correct
- Check you have read permissions

**"Project not found in source"**
- Use --list to see available projects
- Check project name spelling

**"Hash chain verification failed"**
- Source database may be corrupted
- Don't import corrupted data

**"Proof verification failed"**
- Source database may be tampered
- Don't import unverified data

---

## Anti-Patterns (DO NOT)

| Don't | Why |
|-------|-----|
| Run `--import` | Not implemented yet - will exit with error |
| Assume import works | Only `--list` and `--check` are functional |

---

## Next Steps

- See [verify.md](verify.md) for verifying integrity
