# Semantic Code Graph

Implementation specification for a separate, rebuildable code-intelligence graph.

---

## Purpose

This system is intentionally separate from the cryptographic memory graph.

The existing memory graph is:
- durable
- provenance-heavy
- append-oriented
- designed to preserve semantic knowledge over time

The semantic code graph is different:
- mutable
- rebuildable
- derived from the current repository state
- optimized for code navigation and structural queries

Examples of target queries:
- "Who calls `X()`?"
- "Give me all callers of `Foo()`"
- "What functions are called from `Bar()`?"
- "Are these classes related?"
- "Show the references and definitions for this symbol"

---

## Non-Goals

This system does not try to be:
- a cryptographically attested history of code state
- the same database as semantic memory
- a full security analysis graph on day one
- a vector database replacement

It may later support snapshots by commit, but its default mode is current-workspace indexing.

---

## Separation Rule

The memory graph and code graph must remain separate at every important boundary.

### Memory Graph

- File: `memory/{project}.graph`
- Library: `tools/graph_db.py`
- Source of truth: extracted conversation knowledge
- Update style: append / merge / temporal supersession
- Trust model: cryptographic proofs and provenance

### Code Graph

- File: `memory/{project}.code.graph`
- Library: `tools/code_graph.py`
- Source of truth: repository files plus semantic indexers
- Update style: reindex / incremental refresh / overwrite
- Trust model: rebuildability and index freshness

### Interoperability

The two systems may exchange search input, but they do not share storage or identity.

Allowed interaction patterns:
- memory query output becomes text input to code search
- code query output becomes text input to memory search
- optional soft links may exist in a separate bridge layer

Forbidden interaction patterns:
- storing code symbols as `Entity` nodes in the memory graph
- storing code `CALLS` or `REFERS_TO` edges in the memory graph
- applying cryptographic proof semantics to volatile code-index edges

---

## Storage Layout

Recommended files:

```text
memory/
  {project}.graph
  {project}.code.graph
  {project}.code.meta.json
```

Recommended source files:

```text
schema/
  code_intelligence_schema.cypher

tools/
  code_graph.py
  code_indexer.py
  code_queries.py
  code_bridge.py

scripts/
  index_code_graph.py
  query_code_graph.py
```

`code.meta.json` tracks index freshness:
- repository root
- active branch
- indexed commit hash
- indexer version
- timestamp
- file hashes or incremental checkpoints

---

## Data Model

The code graph is a precise navigation graph first. It can be extended later.

### Node Types

#### `CodeRepo`

One node per indexed repository.

Fields:
- `name`
- `root_path`
- `default_branch`
- `last_indexed_commit`
- `last_indexed_at`
- `indexer_version`

#### `CodeFile`

One node per indexed source file.

Fields:
- `path`
- `repo_name`
- `language`
- `extension`
- `content_hash`
- `last_indexed_at`

Primary key recommendation:
- `path`

#### `CodeSymbol`

Canonical symbol node for functions, methods, classes, modules, fields, and constants.

Fields:
- `symbol_id`
- `repo_name`
- `language`
- `kind`
- `display_name`
- `qualified_name`
- `signature`
- `visibility`
- `file_path`
- `start_line`
- `start_column`
- `end_line`
- `end_column`
- `docstring`
- `is_external`
- `content_hash`
- `last_indexed_at`

Primary key recommendation:
- `symbol_id`

`symbol_id` should be stable across reindex runs whenever the logical symbol has not changed.
Preferred format:

```text
{language}:{qualified_name}:{file_path}:{start_line}
```

For languages with better symbol schemes, use the indexer's native canonical symbol identity.

#### `CodeOccurrence`

Optional but strongly recommended. Represents a concrete definition or reference span in a file.

Fields:
- `occurrence_id`
- `file_path`
- `symbol_id`
- `occurrence_kind` (`definition`, `reference`, `import`, `call`)
- `start_line`
- `start_column`
- `end_line`
- `end_column`
- `enclosing_symbol_id`

Primary key recommendation:
- `occurrence_id`

#### `CodeType`

Optional abstraction for languages where type identity should be modeled separately from symbol identity.
For Python v1, this can be omitted and represented through `CodeSymbol(kind=class|protocol|interface-like)`.

---

## Edge Model

### Required Edges

#### `OWNS_FILE`
`CodeRepo -> CodeFile`

The repository contains this file.

#### `DEFINES`
`CodeFile -> CodeSymbol`

The file contains the defining occurrence of the symbol.

#### `CONTAINS`
`CodeSymbol -> CodeSymbol`

Lexical containment.

Examples:
- module contains class
- class contains method
- function contains nested function

#### `REFERS_TO`
`CodeOccurrence -> CodeSymbol`

A concrete occurrence resolves to a canonical symbol.

#### `HAS_OCCURRENCE`
`CodeFile -> CodeOccurrence`

Useful for lookup by file span.

#### `CALLS`
`CodeSymbol -> CodeSymbol`

Caller symbol to callee symbol.

Required edge properties:
- `call_count`
- `confidence`
- `source` (`semantic`, `syntactic`, `inferred`)

#### `IMPORTS`
`CodeFile -> CodeFile` or `CodeSymbol -> CodeSymbol`

Implementation choice:
- `CodeFile -> CodeFile` for module-level imports
- optional `CodeSymbol -> CodeSymbol` for direct imported-symbol resolution

#### `EXTENDS`
`CodeSymbol -> CodeSymbol`

Subclass to superclass.

#### `IMPLEMENTS`
`CodeSymbol -> CodeSymbol`

Class to interface or protocol-like symbol.

#### `OVERRIDES`
`CodeSymbol -> CodeSymbol`

Method override relationship.

### Optional Edges

#### `RETURNS`
`CodeSymbol -> CodeSymbol`

Function/method return type points to type symbol.

#### `HAS_TYPE`
`CodeSymbol -> CodeSymbol`

Field/parameter/local type relation where available.

#### `INSTANTIATES`
`CodeSymbol -> CodeSymbol`

Function/method/class creates instances of another class.

#### `RELATED_TO`
`CodeSymbol -> CodeSymbol`

Heuristic relationship only. Use sparingly and always mark `source='heuristic'`.

---

## Recommended Kuzu Schema

Initial schema sketch:

```cypher
CREATE NODE TABLE IF NOT EXISTS CodeRepo (
    name STRING PRIMARY KEY,
    root_path STRING,
    default_branch STRING,
    last_indexed_commit STRING,
    last_indexed_at TIMESTAMP,
    indexer_version STRING
);

CREATE NODE TABLE IF NOT EXISTS CodeFile (
    path STRING PRIMARY KEY,
    repo_name STRING,
    language STRING,
    extension STRING,
    content_hash STRING,
    last_indexed_at TIMESTAMP
);

CREATE NODE TABLE IF NOT EXISTS CodeSymbol (
    symbol_id STRING PRIMARY KEY,
    repo_name STRING,
    language STRING,
    kind STRING,
    display_name STRING,
    qualified_name STRING,
    signature STRING,
    visibility STRING,
    file_path STRING,
    start_line INT64,
    start_column INT64,
    end_line INT64,
    end_column INT64,
    docstring STRING,
    is_external BOOLEAN,
    content_hash STRING,
    last_indexed_at TIMESTAMP
);

CREATE NODE TABLE IF NOT EXISTS CodeOccurrence (
    occurrence_id STRING PRIMARY KEY,
    file_path STRING,
    symbol_id STRING,
    occurrence_kind STRING,
    start_line INT64,
    start_column INT64,
    end_line INT64,
    end_column INT64,
    enclosing_symbol_id STRING
);

CREATE REL TABLE IF NOT EXISTS OWNS_FILE (
    FROM CodeRepo TO CodeFile
);

CREATE REL TABLE IF NOT EXISTS DEFINES (
    FROM CodeFile TO CodeSymbol
);

CREATE REL TABLE IF NOT EXISTS HAS_OCCURRENCE (
    FROM CodeFile TO CodeOccurrence
);

CREATE REL TABLE IF NOT EXISTS REFERS_TO (
    FROM CodeOccurrence TO CodeSymbol,
    resolution_kind STRING
);

CREATE REL TABLE IF NOT EXISTS CONTAINS (
    FROM CodeSymbol TO CodeSymbol
);

CREATE REL TABLE IF NOT EXISTS CALLS (
    FROM CodeSymbol TO CodeSymbol,
    call_count INT64,
    confidence DOUBLE,
    source STRING
);

CREATE REL TABLE IF NOT EXISTS IMPORTS (
    FROM CodeFile TO CodeFile,
    import_text STRING
);

CREATE REL TABLE IF NOT EXISTS EXTENDS (
    FROM CodeSymbol TO CodeSymbol
);

CREATE REL TABLE IF NOT EXISTS IMPLEMENTS (
    FROM CodeSymbol TO CodeSymbol
);

CREATE REL TABLE IF NOT EXISTS OVERRIDES (
    FROM CodeSymbol TO CodeSymbol
);
```

---

## Ingestion Pipeline

### Stage 1: Discover

Input:
- repository root
- include/exclude patterns
- supported languages

Output:
- list of source files
- file hashes
- repo metadata

Rules:
- ignore generated files
- ignore virtual environments
- ignore build artifacts
- default to tracked files when git is available

### Stage 2: Parse and Index

Primary requirement:
- use language-aware semantic tooling where available

For Python v1:
- parse modules, classes, functions, methods, imports
- collect definitions and references
- infer containment
- produce best-effort call edges

Priority of backends:
1. semantic backend with symbol resolution
2. language-server-backed export
3. AST fallback with clearly marked lower confidence

Do not market tree-sitter-only output as precise semantics.

### Stage 3: Normalize

Convert backend-specific output into the graph schema:
- canonical `symbol_id`
- stable file paths relative to repo root
- consistent symbol kinds
- confidence annotation

### Stage 4: Store

Write to `memory/{project}.code.graph`.

Recommended write strategy:
- current-state indexing uses replace-by-repo semantics
- delete and rebuild repo-local code nodes/edges during full reindex
- support file-scoped upserts during incremental indexing

### Stage 5: Derive

Derive graph edges not directly emitted by the backend:
- caller symbol from callsite containment
- class relation shortcuts
- override chains
- neighborhood summaries

### Stage 6: Optional Semantic Retrieval

Build an optional embedding side index over:
- symbol names
- qualified names
- signatures
- docstrings
- short code summaries

Embeddings are only for candidate retrieval, not structural truth.

---

## Python-First Scope

The repo is Python-heavy, so implement Python first.

### Python v1 Guaranteed Queries

- exact symbol lookup
- definitions for module/class/function/method
- references for a symbol
- file containment
- class-to-method containment
- imports between files
- direct callers where resolution is available
- direct callees where resolution is available
- inheritance relationships

### Python v1 Best-Effort Queries

- dynamic dispatch callers
- monkey-patched function references
- reflective imports
- runtime-generated attributes
- indirect framework wiring

All best-effort results should expose confidence.

---

## Query API

Add a dedicated query layer separate from memory queries.

### Library API

Recommended methods in `tools/code_queries.py`:

- `find_symbol(query: str) -> list[dict]`
- `get_symbol(symbol_id: str) -> dict | None`
- `get_definitions(symbol_id: str) -> list[dict]`
- `get_references(symbol_id: str) -> list[dict]`
- `get_callers(symbol_id: str) -> list[dict]`
- `get_callees(symbol_id: str) -> list[dict]`
- `get_related_classes(symbol_id: str) -> list[dict]`
- `get_symbol_neighborhood(symbol_id: str, hops: int = 1) -> dict`
- `search_code(query: str) -> list[dict]`

### CLI

Recommended script: `scripts/query_code_graph.py`

Examples:

```bash
python scripts/query_code_graph.py --project llm_memory --symbol GraphDatabase
python scripts/query_code_graph.py --project llm_memory --callers tools.graph_db.GraphDatabase.get_related_entities
python scripts/query_code_graph.py --project llm_memory --callees tools.graph_db.GraphDatabase.get_entity_by_name
python scripts/query_code_graph.py --project llm_memory --refs CodeGraphDB
python scripts/query_code_graph.py --project llm_memory --related-classes GraphDatabase CodeGraphDB
python scripts/query_code_graph.py --project llm_memory --search "timestamp proof verification"
```

---

## Bridge Layer

The bridge layer exists for retrieval orchestration, not storage unification.

### Rule

The bridge must not contaminate the trust model of the memory graph.

### Recommended Behavior

Memory to code:
- take memory entity names, summaries, and facts
- run them as code search terms
- resolve to symbols/files/classes/functions

Code to memory:
- take symbol names, qualified names, file paths, and docstrings
- run them as memory search terms
- find related historical discussions, tasks, and decisions

### Optional Bridge Storage

If persisted at all, persist in a separate lightweight mapping store.

Suggested record:
- `memory_uuid`
- `symbol_id`
- `link_type`
- `confidence`
- `created_at`
- `created_by`

This should not live in the durable memory graph and should not be proof-bearing.

---

## Index Freshness and Lifecycle

The code graph should expose freshness explicitly.

Required metadata:
- indexed commit hash
- indexed timestamp
- indexer version
- repository root
- language coverage

Lifecycle rules:
- full reindex is always allowed
- incremental reindex is preferred after local edits
- stale index results must be detectable
- callers/callees should be considered invalid if source files changed after indexing

---

## Incremental Indexing Strategy

Phase 1:
- full reindex only

Phase 2:
- detect changed files by git diff or file hash
- reindex changed files
- delete affected occurrences and edges
- recompute impacted symbol neighborhoods

Phase 3:
- support commit-pinned snapshots if historical code queries become necessary

---

## Suggested Implementation Plan

### Phase 1: Separate Foundation

Deliverables:
- `schema/code_intelligence_schema.cypher`
- updated `tools/code_graph.py` to target `memory/{project}.code.graph`
- `tools/code_indexer.py`
- `tools/code_queries.py`
- `scripts/index_code_graph.py`
- `scripts/query_code_graph.py`

Scope:
- Python only
- defs, refs, containment, imports, classes, methods
- best-effort direct call graph

### Phase 2: Better Resolution

Deliverables:
- incremental indexing
- confidence on call edges
- richer symbol search
- optional occurrence-level output formatting

### Phase 3: Retrieval Integration

Deliverables:
- `tools/code_bridge.py`
- memory-to-code and code-to-memory search helpers
- optional persisted bridge mappings

---

## Acceptance Criteria

The first usable version is done when all of these work:

1. Index this repository into `memory/llm_memory.code.graph`.
2. Resolve exact symbol lookup for top-level classes and functions.
3. Return direct callers for at least straightforward Python method/function calls.
4. Return direct callees for a selected function or method.
5. Show inheritance or containment relationships between classes.
6. Expose when a result is best-effort instead of fully resolved.
7. Rebuild the code graph without touching the memory graph.

---

## Architectural Rationale

This design keeps the important invariants clean:

- memory graph remains durable and attested
- code graph remains volatile and rebuildable
- both systems can still help each other through retrieval handoff
- the agent gets precise structural answers instead of guessing from raw files

That separation is not optional. It is the core design constraint that keeps both systems useful.
