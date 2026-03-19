# ADR 002: Layered Configuration System

**Date:** 2026-03-04  
**Status:** Accepted

---

## Context

The memory system needs stable path resolution for:
- SQL audit log
- per-project graph memory
- tmp working files
- Python interpreter path

Before the configuration cleanup, scripts mixed:
- hardcoded defaults
- ad hoc CLI behavior
- inconsistent path conventions

That created three problems:
- different entrypoints behaved differently
- docs and runtime drifted apart
- host-workspace and subsystem-repo installs were easy to confuse

---

## Decision

We use a **layered configuration system** with this priority order:

1. CLI arguments
2. environment variables
3. project config: `mem.config.json`
4. global config: `~/.mem/config.json`
5. built-in defaults

This behavior is implemented in `tools/config.py`.

---

## Default Path Model

The system supports two valid path contexts.

### Subsystem Repo Mode

Use this when working inside the memory repo itself.

- SQL: `./memory/conversations.db`
- graph: `./memory/{project_name}.graph`
- tmp: `./tmp`

### Host Workspace Mode

Use this when the memory system is embedded under `./mem`.

- SQL: `./mem/memory/conversations.db`
- graph: `./mem/memory/{project_name}.graph`
- tmp: `./mem/tmp`

These are the same logical defaults, expressed relative to different roots.

---

## Config Shape

Example:

```json
{
  "project_name": "my-project",
  "database": {
    "sql_path": "./mem/memory/conversations.db",
    "graph_path": "./mem/memory/{project_name}.graph"
  },
  "paths": {
    "tmp_dir": "./mem/tmp",
    "memory_dir": "./mem/memory"
  },
  "extraction": {
    "version": "v1.0.0",
    "skip_quality_check": false
  }
}
```

Notes:
- SQL stores raw conversations and should usually remain private.
- Graph stores extracted memory and may be shared more broadly.
- `graph_path` may contain `{project_name}` and should resolve per project.

---

## Environment Variables

Supported high-signal overrides:

```bash
export MEM_PROJECT="my-project"
export MEM_SQL_DB="/data/memory/conversations.db"
export MEM_GRAPH_DB="/data/memory/my-project.graph"
export MEM_EXTRACTION_VERSION="v1.0.0"
export MEM_SKIP_QUALITY_CHECK="false"
```

---

## Why This Design

This design gives:
- sensible defaults for local use
- project-local customization via `mem.config.json`
- deployment overrides via environment variables
- exact one-off overrides via CLI

It also keeps SQL and graph paths independently configurable, which matters
because the two databases have different trust and sharing characteristics.

---

## Typical Configurations

### 1. Local Default

Host workspace install:

```json
{
  "project_name": "my-project",
  "database": {
    "sql_path": "./mem/memory/conversations.db",
    "graph_path": "./mem/memory/{project_name}.graph"
  }
}
```

### 2. Custom Local Storage

```json
{
  "project_name": "my-project",
  "database": {
    "sql_path": "/data/memory/conversations.db",
    "graph_path": "/data/memory/my-project.graph"
  }
}
```

### 3. Private SQL, Shared Graph

```json
{
  "project_name": "frontend",
  "database": {
    "sql_path": "./mem/memory/conversations.db",
    "graph_path": "/shared/team/frontend.graph"
  }
}
```

This keeps raw conversations local while sharing extracted memory.

### 4. Shared Team Storage

```json
{
  "project_name": "frontend",
  "database": {
    "sql_path": "/shared/memory/conversations.db",
    "graph_path": "/shared/memory/frontend.graph"
  }
}
```

This shares both audit log and graph memory.

---

## Consequences

### Positive

- one consistent resolution path across main workflows
- project-level defaults without forcing CLI repetition
- environment-friendly deployment behavior
- explicit separation of SQL and graph storage concerns
- support for both repo-internal and embedded installs

### Negative

- more documentation burden
- multiple override layers to understand
- stale examples become actively harmful if not maintained

---

## Rejected Alternatives

### CLI only

Rejected because it is repetitive and easy for agents to misapply.

### Environment variables only

Rejected because it is weak for per-project defaults and local portability.

### Config file only

Rejected because it removes easy operational overrides.

---

## Operational Rule

When code, docs, and examples disagree:
- `tools/config.py` is the runtime authority
- `mem.config.json` is the project-local source of truth
- docs must follow those two, not the reverse

---

## Related Documents

- [../system-overview.md](../system-overview.md)
- [../data-model.md](../data-model.md)
- [../../docs/CONFIGURATION.md](../../docs/CONFIGURATION.md)
