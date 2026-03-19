# Multi-Machine Setup

How to use the memory system from more than one machine.

---

## Core Recommendation

Best option:
- use one shared SQL database
- use one graph file per project

Example shared storage:

```text
/shared/memory/
  conversations.db
  my-project.graph
```

This avoids merge complexity and keeps provenance intact.

---

## Why Merging Is Still Hard

Merging independently written memory stores is expensive because:
- interaction chains diverge
- extracted entities may overlap with different UUIDs
- timing and provenance become harder to reason about
- contradiction and duplicate review become noisier

So the preferred answer is still:
- **share storage instead of merging after the fact**

---

## Recommended Solutions

### 1. Shared Storage

Best for:
- same team
- same project
- reliable network or synced folder

Example config on both machines:

```json
{
  "project_name": "my-project",
  "database": {
    "sql_path": "/shared/memory/conversations.db",
    "graph_path": "/shared/memory/{project_name}.graph"
  }
}
```

Benefits:
- no merge step
- one provenance chain
- one graph memory for the project

Tradeoffs:
- requires shared access
- concurrent access behavior still matters

### 2. Separate Projects Per Machine

Best for:
- intermittent connectivity
- exploratory work
- intentionally separate memory spaces

Machine A:

```json
{
  "project_name": "my-project-work",
  "database": {
    "sql_path": "./mem/memory/conversations.db",
    "graph_path": "./mem/memory/{project_name}.graph"
  }
}
```

Machine B:

```json
{
  "project_name": "my-project-home",
  "database": {
    "sql_path": "./mem/memory/conversations.db",
    "graph_path": "./mem/memory/{project_name}.graph"
  }
}
```

Benefits:
- no merge conflicts
- easy mental separation

Tradeoffs:
- memory is fragmented
- cross-machine comparison becomes a query problem

### 3. Primary / Secondary Copy

Best for:
- one write machine
- one read-mostly machine

Primary machine writes to shared storage or periodically syncs the `memory/`
folder to the secondary machine.

Benefits:
- no conflicting writes
- simple operational model

Tradeoffs:
- secondary machine lags behind

---

## What to Avoid

Avoid routine bidirectional merging of independently active databases unless you
actually need it.

It is the highest-friction path and remains harder to validate than shared
storage.

---

## Practical Recommendation Matrix

- Same project, both machines online: shared storage
- Same project, one machine mostly read-only: primary / secondary copy
- Different work contexts with occasional lookup: separate project names

---

## Example Shared Setup

### Host Workspace Mode

```json
{
  "project_name": "my-project",
  "database": {
    "sql_path": "/mnt/network/memory/conversations.db",
    "graph_path": "/mnt/network/memory/{project_name}.graph"
  }
}
```

### Synced Folder Example

```json
{
  "project_name": "my-project",
  "database": {
    "sql_path": "~/Dropbox/memory/conversations.db",
    "graph_path": "~/Dropbox/memory/{project_name}.graph"
  }
}
```

---

## Verification Advice

If multiple machines share the same storage:
- use `verify_integrity.py` periodically
- keep backups of the shared `memory/` directory
- prefer one graph file per project instead of a single catch-all graph

---

## See Also

- [shared-database.md](./shared-database.md)
- [MERGE-VERIFICATION.md](./MERGE-VERIFICATION.md)
- [CONFIGURATION.md](./CONFIGURATION.md)
