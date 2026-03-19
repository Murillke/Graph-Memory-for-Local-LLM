# Configuration Guide

**How to configure the LLM Memory System.**

---

## Overview

The memory system supports flexible configuration through multiple sources:

**Priority Order (highest to lowest):**
1. **Command-line arguments** - Explicit overrides
2. **Environment variables** - CI/CD and temporary settings
3. **Project config file** - Project-specific settings (`mem.config.json`)
4. **Global config file** - User-wide settings (`~/.mem/config.json`)
5. **Defaults** - Built-in fallbacks

**Important:** SQL and Graph databases can live in different locations!
- **SQL database** - Contains raw conversations (private, may include cursing, personal info)
- **Graph database** - Contains extracted entities/facts (clean, shareable)

---

## Quick Start

### Path Context

There are two valid ways to read the path examples in this document:

- **Subsystem repo mode**: you are running inside the memory subsystem repo itself. Default paths look like `./memory/...` and `./tmp/...`.
- **Host workspace mode**: the subsystem lives under `./mem` in another project. The same paths become `./mem/memory/...` and `./mem/tmp/...`.

The runtime defaults implemented in this repo are **subsystem repo mode**.

### No Configuration Needed

**The system works out of the box with sensible defaults:**

```bash
# Just specify project name
python mem/scripts/sync.py --project my-project

# Uses defaults:
# - SQL: ./mem/memory/conversations.db
# - Graph: ./mem/memory/my-project.graph
```

### Add Project Configuration

**Create `mem.config.json` in your project root:**

```json
{
  "project_name": "my-project",
  "python_path": ".\\python313\\python.exe",
  "database": {
    "sql_path": "./mem/memory/conversations.db",
    "graph_path": "./mem/memory/{project_name}.graph"
  }
}
```

**Now you don't need `--project` flag:**

```bash
# Reads project_name from mem.config.json
python mem/scripts/sync.py
```

---

## Configuration File Format

### Project Config (mem.config.json)

**Location:** Project root directory

**Full example:**

```json
{
  "project_name": "my-project",
  "python_path": ".\\python313\\python.exe",
  "database": {
    "sql_path": "./mem/memory/conversations.db",
    "graph_path": "./mem/memory/{project_name}.graph"
  },
  "extraction": {
    "version": "v1.0.0",
    "skip_quality_check": false
  },
  "paths": {
    "tmp_dir": "./tmp",
    "memory_dir": "./mem/memory"
  },
  "quality_check": {
    "questions_file": "quality-questions.json",
    "answers_file": "quality-answers.json"
  }
}
```

**Configuration Options:**

- **`python_path`** (NEW!) - Which Python executable to use
  - Windows with portable Python: `".\\python313\\python.exe"`
  - Linux/Mac or system Python: `"python3"`
  - Custom Python: `"C:\\Python311\\python.exe"`
  - **Why:** Different machines have different Python installations
  - **LLM usage:** Read this value and use it in all Python commands

### Global Config (~/.mem/config.json)

**Location:** User home directory (`~/.mem/config.json`)

**Use for:** User-wide defaults

**Example:**

```json
{
  "extraction": {
    "version": "v1.0.0",
    "skip_quality_check": false
  },
  "paths": {
    "tmp_dir": "./tmp"
  }
}
```

---

## Configuration Options

### project_name

**Type:** String

**Description:** Name of the project (used to isolate data in shared databases)

**Default:** None (must be specified)

**Example:**
```json
{
  "project_name": "my-frontend-app"
}
```

### database.sql_path

**Type:** String (file path)

**Description:** Path to SQL database file

**Default:** `./memory/conversations.db` in subsystem repo mode  
**Host workspace equivalent:** `./mem/memory/conversations.db`

**Example:**
```json
{
  "database": {
    "sql_path": "/data/memory/conversations.db"
  }
}
```

### database.graph_path

**Type:** String (directory path)

**Description:** Path to graph database directory

**Default:** `./memory/{project_name}.graph` in subsystem repo mode  
**Host workspace equivalent:** `./mem/memory/{project_name}.graph`

**Note:** Can be different from SQL path! Graph contains extracted entities/facts (shareable), SQL contains raw conversations (private).

**Example:**
```json
{
  "database": {
    "sql_path": "./mem/memory/conversations.db",
    "graph_path": "/shared/team/my-project.graph"
  }
}
```

**Why split paths?**
- SQL database may contain personal info, cursing, sensitive conversations
- Graph database only has clean, extracted entities and facts
- You can keep SQL private, share Graph with team

### extraction.version

**Type:** String

**Description:** Extraction version identifier

**Default:** `"v1.0.0"`

**Example:**
```json
{
  "extraction": {
    "version": "v2.0.0"
  }
}
```

### extraction.skip_quality_check

**Type:** Boolean

**Description:** Skip duplicate/contradiction quality checks

**Default:** `false`

**Example:**
```json
{
  "extraction": {
    "skip_quality_check": true
  }
}
```

### extraction.llm_wrapper_entities / extraction.llm_wrapper_facts

**Type:** String or null

**Description:** Wrapper scripts for automated entity/fact extraction.

If both are configured, `scripts/extract_with_wrappers.py` calls them.

If either is `null`, missing, or an empty string, that means **manual extraction mode**:
- do not call `extract_with_wrappers.py`
- read the interactions yourself
- write `tmp/extraction.json`
- validate it with `scripts/validate_extraction.py`
- store it with `scripts/store_extraction.py`

**Example:**
```json
{
  "extraction": {
    "llm_wrapper_entities": null,
    "llm_wrapper_facts": null
  }
}
```

---

### quality_check.llm_wrapper

**Type:** String or null

**Description:** Wrapper script for automated duplicate/contradiction review.

If configured, `store_extraction.py` can call it automatically.

If it is `null`, missing, or an empty string:
- there is no configured reviewer
- the current agent must review the generated questions itself if review is required
- use `--skip-quality-check`, or
- let the script write `tmp/quality-questions.json`, review them yourself,
  create `tmp/quality-answers.json`, and rerun with
  `--require-quality-review`

---

## Environment Variables

### MEM_PROJECT

**Description:** Project name

**Example:**
```bash
export MEM_PROJECT="my-project"
```

### MEM_SQL_DB

**Description:** SQL database path

**Example:**
```bash
export MEM_SQL_DB="/data/memory/conversations.db"
```

### MEM_GRAPH_DB

**Description:** Graph database path

**Example:**
```bash
export MEM_GRAPH_DB="/data/memory/my-project.graph"
```

### MEM_EXTRACTION_VERSION

**Description:** Extraction version

**Example:**
```bash
export MEM_EXTRACTION_VERSION="v2.0.0"
```

### MEM_SKIP_QUALITY_CHECK

**Description:** Skip quality checks

**Example:**
```bash
export MEM_SKIP_QUALITY_CHECK="true"
```

---

## Use Cases

### Use Case 1: Single Project (Default)

**No config needed:**

```bash
python mem/scripts/sync.py --project my-project
```

**Databases:**
- SQL: `./mem/memory/conversations.db`
- Graph: `./mem/memory/my-project.graph`

### Use Case 2: Custom Database Location

**mem.config.json:**
```json
{
  "project_name": "my-project",
  "database": {
    "sql_path": "/data/memory/conversations.db",
    "graph_path": "/data/memory/my-project.graph"
  }
}
```

**Usage:**
```bash
python mem/scripts/sync.py
```

### Use Case 3: Split Databases (Private SQL, Shared Graph)

**Scenario:** Keep raw conversations private, share extracted knowledge

**Why:** Your SQL database contains raw conversations (including cursing, personal info). Your graph database only has clean, extracted entities and facts.

**mem.config.json:**
```json
{
  "project_name": "my-project",
  "database": {
    "sql_path": "./mem/memory/conversations.db",
    "graph_path": "/shared/team/my-project.graph"
  }
}
```

**Result:**
- SQL database stays local (private conversations)
- Graph database is shared (team can query your knowledge)
- Team sees "JWT Token" entity, not "I f***ing hate JWT tokens"

### Use Case 4: Fully Shared Database (Same Team)

**Scenario:** Multiple projects sharing everything (full trust)

**Frontend project (mem.config.json):**
```json
{
  "project_name": "frontend",
  "database": {
    "sql_path": "/shared/memory/conversations.db",
    "graph_path": "/shared/memory/frontend.graph"
  }
}
```

**Backend project (mem.config.json):**
```json
{
  "project_name": "backend",
  "database": {
    "sql_path": "/shared/memory/conversations.db",
    "graph_path": "/shared/memory/backend.graph"
  }
}
```

**Result:**
- Both projects share SQL database (all conversations visible)
- Both projects share graph database (all knowledge visible)
- Data is isolated by project_name

### Use Case 5: CI/CD Environment

**In CI/CD pipeline:**
```bash
export MEM_PROJECT="my-project"
export MEM_SQL_DB="/ci/memory/conversations.db"
export MEM_GRAPH_DB="/ci/memory/my-project.graph"
export MEM_SKIP_QUALITY_CHECK="true"

python mem/scripts/sync.py
```

### Use Case 6: Temporary Override

**Override config file with CLI:**
```bash
# mem.config.json says: sql_path = "./mem/memory/conversations.db"
# But we want to use a different path temporarily:

python mem/scripts/sync.py --sql-db /tmp/test.db
```

---

## Configuration Priority Examples

### Example 1: All Sources

**mem.config.json:**
```json
{
  "project_name": "from-config"
}
```

**Environment:**
```bash
export MEM_PROJECT="from-env"
```

**Command:**
```bash
python mem/scripts/sync.py --project from-cli
```

**Result:** `project_name = "from-cli"` (CLI wins)

### Example 2: Config + Environment

**mem.config.json:**
```json
{
  "project_name": "from-config",
  "database": {
    "sql_path": "./mem/memory/conversations.db"
  }
}
```

**Environment:**
```bash
export MEM_SQL_DB="/data/conversations.db"
```

**Result:**
- `project_name = "from-config"` (from config)
- `sql_path = "/data/conversations.db"` (env overrides config)

---

## Troubleshooting

### Config file not found

**Problem:** `mem.config.json` not being read

**Solution:** Make sure it's in the project root (same directory where you run commands)

### Environment variables not working

**Problem:** Environment variables ignored

**Solution:** Check spelling (case-sensitive: `MEM_PROJECT` not `mem_project`)

### Shared database not working

**Problem:** Projects not sharing data

**Solution:**
1. Check both projects use the same database paths
2. Check both projects have different `project_name`
3. For shared graph only: SQL paths can be different, graph paths must be same

### Priority confusion

**Problem:** Not sure which config is being used

**Solution:** Add `--verbose` flag to see loaded configuration

---

## Next Steps

- See [examples/mem.config.json](../examples/mem.config.json) for standard config
- See [examples/mem.config-shared.json](../examples/mem.config-shared.json) for shared graph database
- See [examples/mem.config-split-databases.json](../examples/mem.config-split-databases.json) for split SQL/Graph paths
- See [ADR 002](../architecture/decisions/002-configuration-system.md) for design rationale
