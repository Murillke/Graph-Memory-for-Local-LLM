# Shared Database Setup

How to run multiple agents or projects against shared memory storage.

Current defaults:
- shared SQL audit log: `conversations.db`
- per-project graph memory: `{project}.graph`

---

## Recommended Model

Use:
- **one shared SQL database** for conversations and provenance
- **one graph file per project** for memory isolation

Example:

```text
memory/
  conversations.db
  frontend.graph
  backend.graph
  devops.graph
```

This is the safest default for cross-project collaboration because it keeps:
- conversation history centralized
- graph memory isolated per project

---

## Why Not One Shared Graph by Default

One shared graph file for every project increases:
- accidental cross-project contamination
- query ambiguity
- operational blast radius

Per-project graph files are easier to reason about and match the current
runtime model.

---

## How It Works

### SQL Audit Log

Shared SQL stores:
- project metadata
- path mappings
- all interactions
- integrity proof chain

Projects stay distinguishable because interactions carry `project_name`.

### Graph Memory

Each project gets its own graph file:
- `frontend.graph`
- `backend.graph`
- `devops.graph`

Queries stay simple because each graph file already scopes memory to one
project.

---

## Configuration Examples

### Host Workspace Mode

```json
{
  "project_name": "frontend",
  "database": {
    "sql_path": "./mem/memory/conversations.db",
    "graph_path": "./mem/memory/{project_name}.graph"
  }
}
```

### Shared Network Storage

```json
{
  "project_name": "frontend",
  "database": {
    "sql_path": "/shared/memory/conversations.db",
    "graph_path": "/shared/memory/{project_name}.graph"
  }
}
```

This gives:
- shared conversation provenance
- isolated graph memory per project

---

## Typical Multi-Instance Layout

```text
/shared/mem/
  memory/
    conversations.db
    frontend.graph
    backend.graph
    devops.graph
  scripts/
  tools/

/workspace/frontend/
/workspace/backend/
/workspace/devops/
```

Each agent points to the same SQL file and to its own project graph path.

---

## Cross-Project Access

There are two ways to look across projects:

### 1. Query Another Project Directly

```bash
python scripts/query_memory.py --project backend --search-file tmp/search.txt
```

### 2. Use Cross-Project Search Tools

```bash
python scripts/query_memory.py --search-file tmp/search.txt --all-projects
```

This does not require a single shared graph file for all projects.

---

## Migration from Older Layouts

If you still have:
- `interactions.db`
- `knowledge.kuzu`
- one graph file shared by every project

Move toward:
- `conversations.db`
- `{project}.graph`

At minimum, update config:

```json
{
  "database": {
    "sql_path": "./memory/conversations.db",
    "graph_path": "./memory/{project_name}.graph"
  }
}
```

Then migrate graph content project by project if needed.

---

## Recommendation

Use this unless you have a very specific reason not to:

- shared SQL
- per-project graph files

That gives the best balance of:
- collaboration
- provenance
- isolation
- operational clarity

---

## See Also

- [CONFIGURATION.md](./CONFIGURATION.md)
- [cross-project.md](./cross-project.md)
- [MULTI-MACHINE-SETUP.md](./MULTI-MACHINE-SETUP.md)
