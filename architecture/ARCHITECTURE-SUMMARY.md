# Architecture Summary

Short summary of the current architecture state.

---

## Core Model

The system has two storage layers:

- **SQL audit log** in `conversations.db`
- **graph memory** in `{project}.graph`

The graph is the memory you query.
The SQL database preserves conversation history and provenance.

---

## Main Components

- workflow files like `sync.md`, `remember.md`, `verify.md`
- scripts like `import_conversation.py`, `store_extraction.py`, `query_memory.py`
- core libraries like `sql_db.py`, `graph_db.py`, `config.py`

---

## Proof Model

See [../docs/proof-model.md](../docs/proof-model.md) for canonical terminology.

- **integrity proof** = SQL hash chain
- **entity derivation proof** = `extraction_proof`
- **relationship derivation proof** = `derivation_proof`
- **timestamp proof** = local signed timestamp claim
- **external attestation** = OpenTimestamps / Bitcoin anchoring state

---

## Default Layout

### Subsystem Repo Mode

- SQL: `./memory/conversations.db`
- graph: `./memory/{project}.graph`
- tmp: `./tmp`

### Host Workspace Mode

- SQL: `./mem/memory/conversations.db`
- graph: `./mem/memory/{project}.graph`
- tmp: `./mem/tmp`

---

## Workflow Shape

```text
conversation
  -> SQL import
  -> extraction
  -> quality review
  -> graph store
  -> memory query
  -> integrity / derivation verification
```

---

## Why This Architecture

- SQL is good for append-only history and provenance
- graph storage is good for connected memory and traversal
- keeping them separate avoids bloating the graph with raw conversation text
- the system can rebuild graph memory from SQL if needed

---

## Main References

- [system-overview.md](./system-overview.md)
- [data-model.md](./data-model.md)
- [workflow-sync.md](./workflow-sync.md)
- [diagrams/system-architecture.md](./diagrams/system-architecture.md)
