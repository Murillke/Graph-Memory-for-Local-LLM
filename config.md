# config.md - Project Configuration

**What this does:** View and manage project settings across JSON config and SQL metadata.

---

## [BOT] Config First

**Read `mem.config.json` before running any command:**
- Use `python_path` value for `{PYTHON_PATH}`
- Use `project_name` value for `{PROJECT}`
- Do not guess or substitute different values

---

## Quick Reference

**View all settings:**
```sh
{PYTHON_PATH} scripts/config.py --project {PROJECT} --show
```

**View as JSON:**
```sh
{PYTHON_PATH} scripts/config.py --project {PROJECT} --show-json
```

**Set backup repo (stored in SQL, not config file):**
```sh
{PYTHON_PATH} scripts/config.py --project {PROJECT} --set-sql backup_repo "github.com/user/private-repo"
```

---

## Settings Categories

### Git-Safe Settings (mem.config.json)

These travel with your repo and are safe to commit:

| Setting | Path | Purpose |
|---------|------|---------|
| Project name | `project_name` | Project identifier |
| SQL database | `database.sql_path` | Path to conversations.db |
| Graph database | `database.graph_path` | Path to .graph folder |
| Extraction version | `extraction.version` | Current extraction schema |
| Entity wrapper | `extraction.llm_wrapper_entities` | LLM wrapper for entities |
| Fact wrapper | `extraction.llm_wrapper_facts` | LLM wrapper for facts |
| Quality wrapper | `quality_check.llm_wrapper` | LLM wrapper for quality |
| Tmp directory | `paths.tmp_dir` | Temp files location |
| Memory directory | `paths.memory_dir` | Database location |

### Machine-Specific Settings (mem.config.json)

These vary per machine - override with env vars if needed:

| Setting | Path | Env Override |
|---------|------|--------------|
| Python path | `python_path` | `MEM_PYTHON_PATH` |

### Private Settings (SQL Metadata)

These are stored in the database, NOT in config file - they travel with your data:

| Setting | Key | Purpose |
|---------|-----|---------|
| Backup repo | `backup_repo` | Private repo URL for commit-hash backups |

### Runtime State (Auto-Updated)

These are updated by scripts - don't edit manually:

| Setting | Path | Updated By |
|---------|------|------------|
| Last consolidation | `consolidation.last_run_timestamp` | consolidate_knowledge.py |
| Last cleanup | `temp_file_cleanup.last_cleanup_timestamp` | cleanup_temp_files.py |

---

## View Settings

**View all (human-readable):**
```sh
{PYTHON_PATH} scripts/config.py --project {PROJECT} --show
```

**View all (JSON):**
```sh
{PYTHON_PATH} scripts/config.py --project {PROJECT} --show-json
```

**Get specific setting:**
```sh
{PYTHON_PATH} scripts/config.py --project {PROJECT} --get database.sql_path
```

**List SQL metadata:**
```sh
{PYTHON_PATH} scripts/config.py --project {PROJECT} --list-sql
```

---

## Edit JSON Settings

**Set value (dot-notation for nested keys):**
```sh
{PYTHON_PATH} scripts/config.py --set extraction.version "v2.0.0"
{PYTHON_PATH} scripts/config.py --set python_path "./venv/bin/python"
```

**Edit directly:**
Open `mem.config.json` in editor. Changes take effect immediately.

---

## Edit SQL Settings

**Set backup repo:**
```sh
{PYTHON_PATH} scripts/config.py --project {PROJECT} --set-sql backup_repo "github.com/user/private-repo"
```

**Alternative (existing command):**
```sh
{PYTHON_PATH} scripts/backup_secure.py --project {PROJECT} --set-repo "github.com/user/private-repo"
```

Both commands write to the same SQL metadata table.

---

## Environment Variable Overrides

Override any setting at runtime without editing files:

| Variable | Overrides |
|----------|-----------|
| `MEM_PROJECT` | `project_name` |
| `MEM_PYTHON_PATH` | `python_path` |
| `MEM_SQL_DB` | `database.sql_path` |
| `MEM_GRAPH_DB` | `database.graph_path` |
| `MEM_EXTRACTION_VERSION` | `extraction.version` |
| `MEM_SKIP_QUALITY_CHECK` | `extraction.skip_quality_check` |
| `LLM_AGENT_NAME` | Default agent identity |

**Priority:** Environment > JSON config > Defaults

---

## Common Workflows

### Initial Setup
After `init.md`, customize your config:
```sh
# Set your Python path
{PYTHON_PATH} scripts/config.py --set python_path "./venv/bin/python"

# Set extraction wrappers (if using automated extraction)
{PYTHON_PATH} scripts/config.py --set extraction.llm_wrapper_entities "extraction_wrapper_auggie.py"
```

### Configure Encrypted Backups
```sh
# Set private repo for commit-hash password mode
{PYTHON_PATH} scripts/config.py --project {PROJECT} --set-sql backup_repo "github.com/your-user/obscure-private-repo"

# Verify
{PYTHON_PATH} scripts/config.py --project {PROJECT} --list-sql
```

### Check Current State
```sh
# Full view
{PYTHON_PATH} scripts/config.py --project {PROJECT} --show

# Export for debugging
{PYTHON_PATH} scripts/config.py --project {PROJECT} --show-json > config-snapshot.json
```

---

## Anti-Patterns (DO NOT)

| Don't | Why |
|-------|-----|
| Store `backup_repo` in mem.config.json | Contains private repo URL |
| Edit SQL metadata with raw SQL | Use config.py for consistency |
| Commit machine-specific python_path | Use env override on other machines |
| Edit runtime timestamps manually | Scripts update these automatically |

---

## Success Criteria

- [OK] `--show` displays all settings (JSON + SQL)
- [OK] `--get` retrieves correct value
- [OK] `--set` persists to mem.config.json
- [OK] `--set-sql` persists to SQL metadata
- [OK] Changes visible in subsequent runs

