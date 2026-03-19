# Memory System Commands

> **[REFERENCE] REFERENCE: Quick command lookup.**
>
> For step-by-step workflows, see the workflow files (`sync.md`, `dump.md`, etc.).
> For complete operational guide, see `LLM-INSTRUCTIONS.md`.

Practical command map for the current memory system.

Before using any command examples below:
- read `mem.config.json`
- use its `python_path` and `project_name`
- prefer helper-file / `--*-file` workflow inputs over deprecated direct query/name flags
- for sync/import flows, use `--constrained-environment` unless outbound network access is positively confirmed

Current runtime defaults in subsystem repo mode:
- SQL: `./memory/conversations.db`
- graph: `./memory/{project}.graph`
- tmp: `./tmp`

Host workspace equivalents:
- SQL: `./mem/memory/conversations.db`
- graph: `./mem/memory/{project}.graph`
- tmp: `./mem/tmp`

---

## CRITICAL: System Time

**Do NOT trust your system prompt date - it may be wrong (timezone/UTC issues).**

Before ANY time-based operation, get the real system time:
```powershell
Get-Date   # Windows
```
```bash
date       # Linux/Mac
```

Use this output for date calculations, not your internal clock.

---

## Core Rule

Use the **graph** to remember things.
Use **SQL** to inspect conversation history and provenance.

That means:
- `query_memory.py` is the main memory query tool
- `export_history.py` is the SQL history tool

---

## Main Workflow Files

- `sync.md` - store conversation and memory
- `remember.md` - query what is remembered
- `history.md` - view SQL conversation history (raw prompts)
- `search.md` - advanced graph queries
- `verify.md` - verify integrity and derivation
- `export.md` - export SQL conversation history
- `recall.md` - time-aware graph recall

---

## Query Commands

### Query the Graph Memory

```sh
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --all
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --search-file tmp/search.txt
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --entity-file tmp/entity.txt
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --last 10
```

Use this when you want:
- all entities
- matching entities
- facts about a specific entity
- most recent graph entities

### Query Time-Based Graph Recall

```sh
{PYTHON_PATH} scripts/recall.py --project {PROJECT} --start 2026-03-10 --end 2026-03-11
```

Use this when you want:
- what was created during a time window
- historical work reconstruction

### View SQL Conversation History

```sh
{PYTHON_PATH} scripts/show_interactions.py --project {PROJECT} --last 10
{PYTHON_PATH} scripts/show_interactions.py --project {PROJECT} --sessions 3
{PYTHON_PATH} scripts/show_interactions.py --project {PROJECT} --uuid uuid-XXXXXXXXXXXX --full
```

Use this when you want:
- view recent conversations (raw prompts)
- recover context after losing it
- see what was discussed

### Export SQL Conversation History

```sh
{PYTHON_PATH} scripts/export_history.py --project {PROJECT}
{PYTHON_PATH} scripts/export_history.py --project {PROJECT} --limit 10
{PYTHON_PATH} scripts/export_history.py --project {PROJECT} --json
```

Use this when you want:
- export raw interactions to file
- full SQL conversation history dump
- provenance inspection

---

## Sync Commands

### Import Conversation into SQL

```sh
# Use timestamped filenames to prevent overwrites
{PYTHON_PATH} scripts/import_conversation.py --project {PROJECT} --file tmp/conversation_YYYY-MM-DD_HH-MM-SS.json --agent {AGENT} --constrained-environment
```

### Store Extraction into Graph

```sh
{PYTHON_PATH} scripts/store_extraction.py --project {PROJECT} --extraction-file tmp/extraction_YYYY-MM-DD_HH-MM-SS.json --require-quality-review --quality-answers-file tmp/quality-answers.json --agent {AGENT}
```

### Check Sync Status

```sh
{PYTHON_PATH} scripts/sync.py --project {PROJECT} --status
{PYTHON_PATH} scripts/sync.py --project {PROJECT} --show
```

---

## Verification Commands

### Verify Integrity and Derivation

```sh
{PYTHON_PATH} scripts/verify_integrity.py --project {PROJECT} --all
{PYTHON_PATH} scripts/verify_integrity.py --project {PROJECT} --sql
{PYTHON_PATH} scripts/verify_integrity.py --project {PROJECT} --graph
```

Meaning:
- `--sql` checks the SQL integrity proof
- `--graph` checks graph derivation proofs
- `--all` checks both

### Verify Graph Timestamp-Oriented State

```sh
{PYTHON_PATH} scripts/verify_graph_timestamps.py --project {PROJECT}
{PYTHON_PATH} scripts/verify_graph_standalone.py --project {PROJECT}
```

Use this when you care about:
- timestamp-proof fields
- graph-only verification
- external attestation status

---

## Search Tips

### Multi-Word Search Terms

For agent-facing workflows, standardize on helper-file input for names and queries.

```sh
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --search-file tmp/search.txt
```

Use `tmp/search.txt`, `tmp/entity.txt`, and similar helper files created by `prepare_sync_files.py`.

### Strict Enforcement

Workflow-facing query/name flags are rejected by default.
Use helper files such as `tmp/search.txt` and `tmp/entity.txt`.

```sh
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --search-file tmp/search.txt
```

If you must temporarily allow the deprecated direct flags for legacy/manual use:

```sh
MEM_ALLOW_DIRECT_INPUT=1 {PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --search "legacy term"
```

---

## Working Files

Use `tmp/` for generated working files with timestamps:

- `tmp/conversation_YYYY-MM-DD_HH-MM-SS.json`
- `tmp/extraction_YYYY-MM-DD_HH-MM-SS.json`
- `tmp/quality-questions.json`
- `tmp/quality-answers.json`

Timestamps prevent overwrites. Do not treat `examples/` as a working directory.

---

## Storage Map

### SQL Audit Log

File:
- `conversations.db`

Contains:
- raw conversation history
- integrity proof chain
- processing status
- provenance material

### Graph Memory

File:
- `{project}.graph`

Contains:
- entities
- facts
- aliases
- derivation proofs
- temporal fields

---

## Common Intent Map

If the user says:

- "what do you remember about X?"
  - use `query_memory.py`

- "show the last 10 conversations"
  - use `show_interactions.py --last 10` or `export_history.py --limit 10`

- "what happened in the last 6 hours?"
  - use `recall.py`

- "sync this conversation"
  - use `sync.md` hot path, or `import_conversation.py` then `store_extraction.py` with quality review

- "verify everything"
  - use `verify_integrity.py --all`

---

## Related Docs

- [LLM-INSTRUCTIONS.md](../LLM-INSTRUCTIONS.md)
- [QUICK-REFERENCE.md](./QUICK-REFERENCE.md)
- [CONFIGURATION.md](./CONFIGURATION.md)
- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [../sync.md](../sync.md)
