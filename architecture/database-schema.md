# Database Schema Specification

**Persisted schema definitions for SQLite and Kuzu graph database**

> **[!] IMPLEMENTATION SCHEMA:** This document describes the actual persisted schema as implemented in `tools/sql_db.py` and `tools/graph_db.py`. Some concepts are inspired by [Graphiti](https://github.com/getzep/graphiti) but adapted for Kuzu compatibility.

> **[!] JSON-ENCODED FIELDS:** Kuzu does not support array columns. Fields that are conceptually arrays (e.g., `source_interactions`, `labels`, `episodes`) are stored as **JSON-encoded strings** in `STRING` columns. Parse them with `json.loads()` before use.

## Path Context

This document assumes **subsystem repo mode** unless noted otherwise:
- working files under `./tmp`
- databases under `./memory`

If the subsystem is embedded under `./mem` in another workspace, the host-workspace equivalents are typically `./mem/tmp` and `./mem/memory`.

---

## SQLite Schema (Episodic Memory)

### Purpose
Store raw conversation interactions verbatim for:
- Evidence and provenance
- Rebuild capability
- Conversation history

### Table: `projects`

```sql
CREATE TABLE projects (
  name TEXT PRIMARY KEY,
  description TEXT,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

**Purpose:** Store project metadata (machine-independent)

**Fields:**
- `name` - Project name (e.g., "gml-llm", "auth-service")
- `description` - Optional project description
- `created_at` - When project was first created

### Table: `project_paths`

```sql
CREATE TABLE project_paths (
  path TEXT PRIMARY KEY,
  project_name TEXT NOT NULL,
  machine_id TEXT,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (project_name) REFERENCES projects(name)
);

CREATE INDEX idx_project_name ON project_paths(project_name);
```

**Purpose:** Map local file paths to projects (machine-specific)

**Fields:**
- `path` - Full directory path (e.g., "/Users/davidastua/Documents/gml-llm")
- `project_name` - Which project this path belongs to
- `machine_id` - Optional identifier for which machine/OS
- `created_at` - When mapping was created

**Why separate tables:**
- [OK] Same project can have different paths on different machines
- [OK] Coworker on Linux: `/home/coworker/projects/gml-llm` -> `gml-llm`
- [OK] You on macOS: `/Users/davidastua/Documents/gml-llm` -> `gml-llm`
- [OK] You on Windows: `C:\Users\davidastua\projects\gml-llm` -> `gml-llm`

### Table: `interactions`

```sql
CREATE TABLE interactions (
  -- Identity
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  uuid TEXT UNIQUE NOT NULL,
  project_name TEXT NOT NULL,

  -- Conversation content
  user_message TEXT NOT NULL,
  assistant_message TEXT NOT NULL,
  timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

  -- Hash chain for cryptographic integrity
  content_hash TEXT NOT NULL,       -- SHA-256 (includes agent identity fields)
  previous_hash TEXT,               -- Hash of previous interaction in chain
  chain_index INTEGER NOT NULL,     -- Sequential number in chain (per project)

  -- Timestamp proof (OpenTimestamps)
  file_hash TEXT,                   -- Hash submitted to OTS
  timestamp_proof TEXT,             -- OTS proof or local-only proof JSON

  -- Processing status
  processed BOOLEAN DEFAULT FALSE,
  extracted_at DATETIME,

  -- Agent identity (who imported this interaction)
  imported_by_agent TEXT,           -- Agent name (e.g., "auggie", "codex")
  imported_by_model TEXT,           -- Model name (e.g., "claude-opus-4-20250514")

  -- Optional metadata
  session_id TEXT,
  interaction_number INTEGER,
  response_time_ms INTEGER,
  token_count INTEGER,

  -- Data fidelity tracking
  fidelity TEXT DEFAULT 'full' CHECK(fidelity IN ('full', 'paraphrased', 'reconstructed', 'summary')),
  source_note TEXT,                 -- Description of data source/quality
  context_data TEXT,                -- JSON blob for extra metadata

  -- Privacy/confidentiality flag
  confidential BOOLEAN DEFAULT FALSE,  -- Exclude from extraction if true

  -- Soft delete
  deleted_at DATETIME DEFAULT NULL
);

-- Indexes
CREATE INDEX idx_project ON interactions(project_name);
CREATE INDEX idx_timestamp ON interactions(timestamp);
CREATE INDEX idx_processed ON interactions(processed);
CREATE INDEX idx_uuid ON interactions(uuid);
CREATE INDEX idx_chain ON interactions(project_name, chain_index);
```

**[!] IMMUTABILITY:** The SQL database has triggers that prevent UPDATE and DELETE operations on interactions. Only soft-delete via `deleted_at` is allowed. See `sql_db.py:110` for trigger definitions.

**[!] HASH INCLUDES AGENT:** The `content_hash` computation includes `imported_by_agent` and `imported_by_model` fields. For legacy data where these are NULL, they contribute empty strings to maintain hash compatibility.

### Hash Chain Explanation

**Purpose:** Cryptographic proof that interactions haven't been tampered with, reordered, or deleted.

**How it works:**

```python
# First interaction in chain
interaction_1 = {
  "uuid": "uuid-1",
  "user_message": "We are using LadybugDB",
  "assistant_message": "Got it!",
  "timestamp": "2026-03-01T10:00:00Z",
  "chain_index": 1,
  "previous_hash": None  # First in chain
}

# Calculate hash
content = f"{uuid}|{project_name}|{user_message}|{assistant_message}|{timestamp}|{chain_index}|{previous_hash or ''}"
interaction_1["content_hash"] = sha256(content)  # "abc123..."

# Second interaction
interaction_2 = {
  "uuid": "uuid-2",
  "user_message": "Where is it located?",
  "assistant_message": "The project graph database lives under ./memory/{project}.graph",
  "timestamp": "2026-03-01T10:05:00Z",
  "chain_index": 2,
  "previous_hash": "abc123..."  # Links to previous!
}
interaction_2["content_hash"] = sha256(...)  # "def456..."
```

**Verification:**
- Recalculate each interaction's hash
- Verify it matches stored `content_hash`
- Verify `previous_hash` matches previous interaction's `content_hash`
- Verify `chain_index` is sequential

**Tamper detection:**
- [ERROR] Modify content -> hash mismatch
- [ERROR] Delete interaction -> chain breaks
- [ERROR] Reorder interactions -> previous_hash doesn't match
- [ERROR] Insert interaction -> chain breaks

### Field Descriptions

**Identity:**
- `id` - Auto-incrementing primary key (internal use)
- `uuid` - Globally unique identifier (used in graph DB references)

**Project Association:**
- `project_name` - Project name (e.g., "gml-llm") - machine-independent

**Conversation Content:**
- `user_message` - Verbatim user prompt/question
- `assistant_message` - Verbatim AI response

**Metadata:**
- `timestamp` - When the interaction occurred (ISO 8601 format)
- `session_id` - Conversation session identifier (groups related interactions)
- `interaction_number` - Sequential number within session (1, 2, 3, ...)

**Processing Status:**
- `processed` - Has this interaction been extracted to graph DB?
- `extracted_at` - When extraction occurred

**Performance Metrics (Optional):**
- `response_time_ms` - How long the response took (milliseconds)
- `token_count` - Total tokens used (if available)

**Additional Context:**
- `context_data` - JSON blob for any extra metadata (flexible)

### Example Data

```sql
-- Create project
INSERT INTO projects (name, description) VALUES (
  'gml-llm',
  'Graph Memory for Local LLM - AI memory system'
);

-- Map paths to project (different machines)
INSERT INTO project_paths (path, project_name, machine_id) VALUES
  ('/Users/davidastua/Documents/gml-llm', 'gml-llm', 'macOS-laptop'),
  ('/home/davidastua/projects/gml-llm', 'gml-llm', 'linux-desktop'),
  ('C:\Users\davidastua\projects\gml-llm', 'gml-llm', 'windows-pc');

-- Store interaction
INSERT INTO interactions (
  uuid,
  project_name,
  user_message,
  assistant_message,
  timestamp,
  session_id,
  interaction_number,
  processed
) VALUES (
  'uuid-847',
  'gml-llm',
  'We are using LadybugDB as the graph database',
  'Got it! LadybugDB is an embedded graph database, successor to Kùzu. I will remember this.',
  '2026-03-01T10:00:00Z',
  'session-2026-03-01',
  1,
  FALSE
);
```

---

## Graph Database Schema (Semantic Memory)

### Purpose
Store extracted knowledge as a graph:
- Entities (nodes)
- Relationships (edges with rich metadata)
- Temporal versioning

**Note:** We use Graphiti's schema (Apache 2.0 licensed) with multi-project support via `group_id` = project name.

### Node Types

#### 1. Project Node (Our Addition)

```cypher
CREATE NODE TABLE Project (
  name STRING PRIMARY KEY,
  description STRING,
  created_at TIMESTAMP NOT NULL
);

CREATE INDEX ON Project(name);
```

**Properties:**
- `name` - Project name (e.g., "gml-llm") - machine-independent
- `description` - Optional project description
- `created_at` - When project was first created

**Purpose:**
- Store project metadata in graph DB (shareable)
- Enable graph DB to be standalone (no SQLite dependency)
- Allow future project relationships

**Note:** Path mappings are stored in SQLite only (machine-specific, not shareable)

#### 2. Entity Node

> **[!] ACTUAL SCHEMA:** This is the persisted Kuzu schema from `graph_db.py:119`. Conceptually inspired by Graphiti but adapted for Kuzu compatibility.

```cypher
CREATE NODE TABLE Entity (
  uuid STRING PRIMARY KEY,
  name STRING,
  group_id STRING,                    -- Project name
  summary STRING,
  labels STRING,                      -- JSON array: '["Technology", "Database"]'
  attributes STRING,                  -- JSON object
  created_at TIMESTAMP,

  -- Extraction provenance
  source_interactions STRING,         -- JSON array of UUIDs
  source_hashes STRING,               -- JSON array of content_hash values
  source_chain STRING,                -- JSON array of chain references
  extraction_timestamp TIMESTAMP,
  extraction_timestamp_str STRING,    -- ISO format string
  extraction_version STRING,
  extraction_commit STRING,
  extraction_proof STRING,            -- SHA-256 proof
  timestamp_proof STRING,             -- OTS proof
  extraction_batch_uuid STRING,       -- Reference to ExtractionBatch node

  -- Access tracking (NOT in crypto proof)
  t_last_accessed TIMESTAMP,
  access_count INT64,

  -- Task-specific (optional, for Task entities)
  priority STRING,
  status STRING,

  -- Soft delete
  deleted_at TIMESTAMP
);
```

**[!] JSON-ENCODED FIELDS:** The following are stored as JSON strings, not arrays:
- `labels` - Parse with `json.loads()` -> `["Technology", "Database"]`
- `source_interactions` - Parse with `json.loads()` -> `["uuid-abc123", "uuid-def456"]`
- `source_hashes` - Parse with `json.loads()` -> `["sha256-1", "sha256-2"]`
- `attributes` - Parse with `json.loads()` -> `{"key": "value"}`

**[!] NO EMBEDDINGS:** Vector embeddings (`name_embedding`) are NOT implemented. Semantic search uses keyword matching.

**Properties:**
- `uuid` - Unique identifier (e.g., "entity-abc123")
- `name` - Entity name (e.g., "React", "User Authentication")
- `group_id` - Project name (e.g., "llm_memory")
- `summary` - Concise description
- `labels` - JSON array of type labels
- `extraction_batch_uuid` - Links to ExtractionBatch for provenance tracking

**Bi-Temporal Model:**
- `extraction_timestamp` = Event time (when entity was observed in conversation)
- `created_at` = Ingestion time (when entity was added to database)

#### 3. ExtractionBatch Node (Provenance Hub)

> **[!] NEW:** Added for agent identity tracking. Links extractions to the agent that created them.

```cypher
CREATE NODE TABLE ExtractionBatch (
  batch_uuid STRING PRIMARY KEY,
  batch_hash STRING,                  -- SHA-256 of canonical JSON payload
  timestamp_proof STRING,             -- OTS proof

  extracted_by_agent STRING,          -- Agent name (e.g., "auggie", "codex")
  extracted_by_model STRING,          -- Model name (e.g., "claude-opus-4-20250514")

  extraction_version STRING,
  extraction_commit STRING,
  project_name STRING,

  source_interaction_uuids STRING,    -- JSON array
  source_interaction_hashes STRING,   -- JSON array

  created_entity_uuids STRING,        -- JSON array
  created_relationship_uuids STRING,  -- JSON array

  previous_batch_hash STRING,         -- Links to previous batch (chain)
  batch_index INT64,

  created_at TIMESTAMP
);
```

**Purpose:** Tracks provenance of each extraction run - who did it, what sources, what was created.

**[!] NOT IMPLEMENTED:** Graphiti's `Episodic` node table is not used. Episode data is stored in SQLite `interactions` table instead.

### Edge Types

#### 1. HAS_ENTITY (Project -> Entity) - Our Addition

```cypher
CREATE REL TABLE HAS_ENTITY (
  FROM Project TO Entity
);
```

**Purpose:** Link projects to their entities (enables project-level queries)

**Example:**
```cypher
(project:Project {name: "gml-llm"})-[:HAS_ENTITY]->(entity:Entity {group_id: "gml-llm"})
```

#### 2. RELATES_TO (Entity -> Entity)

> **[!] ACTUAL SCHEMA:** This is the persisted Kuzu schema from `graph_db.py:245`.

```cypher
CREATE REL TABLE RELATES_TO (
  FROM Entity TO Entity,

  uuid STRING,
  name STRING,                        -- Relationship type (e.g., "USES", "LOCATED_IN")
  fact STRING,                        -- The actual fact text
  group_id STRING,                    -- Project name
  episodes STRING,                    -- JSON array of interaction UUIDs

  -- Temporal tracking
  created_at TIMESTAMP,
  expired_at TIMESTAMP,
  valid_at TIMESTAMP,                 -- When fact became true (event time)
  valid_at_str STRING,                -- ISO format string
  invalid_at TIMESTAMP,               -- When fact stopped being true

  -- Derivation provenance
  episode_hashes STRING,              -- JSON array of content_hash values
  derivation_timestamp TIMESTAMP,
  derivation_timestamp_str STRING,
  derivation_version STRING,
  derivation_commit STRING,
  derivation_proof STRING,            -- SHA-256 proof
  timestamp_proof STRING,             -- OTS proof
  extraction_batch_uuid STRING,       -- Reference to ExtractionBatch

  -- Superseding provenance
  superseded_by STRING,
  superseding_proof STRING,

  attributes STRING                   -- JSON object
);
```

**[!] JSON-ENCODED FIELDS:** `episodes` and `episode_hashes` are JSON arrays in STRING columns.

**[!] NO EMBEDDINGS:** `fact_embedding` is not implemented.

**[!] RELATIONSHIP TYPES:** See `schema/relationship_types.py` for the 24 canonical types (USES, IMPLEMENTS, CONTAINS, etc.) and validation rules.

**[!] NOT IMPLEMENTED:** Graphiti's `MENTIONS` edge (Episodic -> Entity) is not used since we don't have Episodic nodes.

---

## Temporal Tracking Pattern (Graphiti's Approach)

### Current Facts
```cypher
MATCH (e1:Entity)-[r:RELATES_TO]->(e2)
WHERE r.invalid_at IS NULL  -- Fact is still valid
  AND r.expired_at IS NULL  -- Edge not expired
  AND r.group_id = $project_name  -- e.g., "gml-llm"
RETURN e1, r, e2
```

### Historical Facts
```cypher
MATCH (e1:Entity)-[r:RELATES_TO]->(e2)
WHERE r.invalid_at IS NOT NULL  -- Fact was invalidated
  AND r.group_id = $project_name  -- e.g., "gml-llm"
ORDER BY r.invalid_at DESC
RETURN e1, r, e2
```

### Bi-Temporal Tracking

**Event Time** (`valid_at`, `invalid_at`):
- When the fact was actually true in the real world

**Ingestion Time** (`created_at`, `expired_at`):
- When we learned about it / when we marked it as expired

**Example:**
```cypher
# Old fact (superseded)
(auth_repo)-[:RELATES_TO {
  name: "LOCATED_AT",
  fact: "auth repo is located at ../auth-service",
  valid_at: "2026-03-01T10:00:00Z",
  invalid_at: "2026-03-01T15:45:00Z",  # When it stopped being true
  created_at: "2026-03-01T10:05:00Z",
  expired_at: "2026-03-01T15:50:00Z",  # When we marked it expired
  group_id: "gml-llm"  # Project name (machine-independent)
}]->(location)

# New fact (current)
(auth_repo)-[:RELATES_TO {
  name: "LOCATED_AT",
  fact: "auth repo is located at ~/projects/auth",
  valid_at: "2026-03-01T15:45:00Z",
  invalid_at: NULL,  # Still valid
  created_at: "2026-03-01T15:50:00Z",
  expired_at: NULL,  # Not expired
  group_id: "gml-llm"  # Project name (machine-independent)
}]->(new_location)
```

---

## Cryptographic Proof System

### Purpose

Provide tamper-evidence and audit trail for:
1. **SQL Interactions** - Prove interactions haven't been modified, deleted, or reordered
2. **Graph Extractions** - Prove entities were actually extracted from specific interactions
3. **Graph Derivations** - Prove facts were actually derived from specific interactions
4. **AI Reasoning** - Track how AI interpreted data at extraction time

### Two-Layer Trust Model

**Layer 1: SQL DB (Trusted Source)**
- Backed up, replicated, audit-logged
- Timestamps are server-controlled
- Hash chain provides tamper detection
- Source of truth for all interactions

**Layer 2: Graph DB (Verified Derivations)**
- Crypto proofs link back to Layer 1
- Can prove extraction/derivation is legitimate
- Can detect tampering with graph data
- Can verify standalone (without SQL) using stored hashes

### Hash Chain (SQL Interactions)

**Purpose:** Detect tampering with interaction history

**How it works:**
```python
# Calculate interaction hash
content = "|".join([
    interaction["uuid"],
    interaction["project_name"],
    interaction["user_message"],
    interaction["assistant_message"],
    interaction["timestamp"],
    str(interaction["chain_index"]),
    interaction["previous_hash"] or ""
])
interaction["content_hash"] = sha256(content)
```

**Verification:**
- Recalculate each hash
- Verify matches stored `content_hash`
- Verify `previous_hash` links to previous interaction
- Verify `chain_index` is sequential

**Tamper detection:**
- [ERROR] Modify content -> hash mismatch
- [ERROR] Delete interaction -> chain breaks
- [ERROR] Reorder interactions -> previous_hash doesn't match
- [ERROR] Insert interaction -> chain breaks

### Extraction Proof (Graph Entities)

**Purpose:** Prove entity was extracted from specific interactions

**How it works:**
```python
# Get source interactions from SQL
source_interactions = [get_interaction(uuid) for uuid in source_uuids]
source_hashes = [i["content_hash"] for i in source_interactions]

# Calculate extraction proof
extraction_content = "|".join([
    entity["name"],
    entity["summary"] or "",
    json.dumps(sorted(entity["labels"])),
    json.dumps(entity["attributes"]) if entity["attributes"] else "",
    *sorted(source_hashes),  # From SQL hash chain!
    entity["extraction_timestamp"]
])
entity["extraction_proof"] = sha256(extraction_content)
```

**Verification (with SQL):**
- Fetch source interactions from SQL
- Extract their `content_hash` values
- Recalculate extraction proof
- Verify matches stored proof

**Verification (standalone, without SQL):**
- Use `source_hashes` stored in graph
- Recalculate extraction proof
- Verify matches stored proof
- [WARNING] Cannot verify hashes are correct (no SQL to check against)

### Derivation Proof (Graph Relationships)

**Purpose:** Prove fact was derived from specific interactions

**How it works:**
```python
# Get source interactions from SQL
source_interactions = [get_interaction(uuid) for uuid in episode_uuids]
episode_hashes = [i["content_hash"] for i in source_interactions]

# Calculate derivation proof
derivation_content = "|".join([
    relationship["fact"],
    relationship["source_uuid"],
    relationship["target_uuid"],
    relationship["name"],
    relationship["group_id"],
    *sorted(episode_hashes),  # From SQL hash chain!
    relationship["valid_at"]
])
relationship["derivation_proof"] = sha256(derivation_content)
```

**Verification:** Same as extraction proof (with SQL or standalone)

### Extraction Context Tracking

**Purpose:** Capture HOW the AI interpreted data at extraction time

**Fields:**
- `extraction_version` - Semantic version (e.g., "v1.0.0")
- `extraction_commit` - Git commit hash (absolute reference to extraction rules)
- `extraction_timestamp` - When extraction happened

**Why this matters:**
- Same interaction + different extraction rules = different entities/facts
- Graph is a snapshot of AI reasoning at that moment
- Can compare extractions over time
- Can debug "why did AI think that?"

**Example:**
```
Entity: "LadybugDB"
- Extracted: 2026-03-01T10:05:00Z
- Version: v1.0.0
- Commit: a1b2c3d4e5f6...
- Proof: def456... [OK]

To see extraction rules used:
git show a1b2c3d4:docs/extraction-rules.md
```

### Verification Levels

| Scenario | What You Can Verify | Trust Level |
|----------|---------------------|-------------|
| **SQL + Graph** | Complete chain: SQL -> Entities -> Facts | **HIGH** [OK] |
| **Graph only** | Internal consistency of graph | **MEDIUM** [WARNING] |
| **SQL only** | Interaction chain integrity | **HIGH** [OK] |

**Key insight:** SQL is source of truth. Graph can work standalone but with lower trust.

---

## Multi-Project Design Summary

### How It Works

**SQLite (Machine-Specific):**
- Stores path -> project mappings
- Each machine has its own paths
- Example:
  - Your macOS: `/Users/davidastua/Documents/gml-llm` -> `gml-llm`
  - Coworker Linux: `/home/coworker/projects/gml-llm` -> `gml-llm`
  - Your Windows: `C:\Users\davidastua\projects\gml-llm` -> `gml-llm`

**Graph DB (Machine-Independent):**
- Uses project name as `group_id`
- All entities/edges tagged with project name
- Shareable across machines (no paths stored)

### Workflow Example

```
# On your macOS machine
You: "Sync"
Me:
  1. Get current path: /Users/davidastua/Documents/gml-llm
  2. Query SQLite: SELECT project_name FROM project_paths WHERE path = ...
  3. Found: "gml-llm"
  4. Extract entities with group_id = "gml-llm"
  5. Store to graph DB

# Coworker on Linux downloads your project graph database
Coworker: "Sync"
Me:
  1. Get current path: /home/coworker/projects/gml-llm
  2. Query SQLite: SELECT project_name FROM project_paths WHERE path = ...
  3. Not found! Ask: "What project is this?"
  Coworker: "gml-llm"
  4. Create mapping: /home/coworker/projects/gml-llm -> gml-llm
  5. Now can query graph DB with group_id = "gml-llm"
  6. Sees all your extracted knowledge!
```

### Benefits

[OK] **Machine-independent knowledge** - Share graph DB across machines
[OK] **Flexible paths** - Same project, different paths per machine
[OK] **Standalone graph DB** - Can work without SQLite (just can't rebuild)
[OK] **Team collaboration** - Share knowledge without sharing conversations

---

## Next Steps

See:
- `TIMESTAMP-SCHEMA.md` - Bi-temporal model, access tracking, and priority ordering
- `tool-interfaces.md` - How to interact with these schemas
- `workflows.md` - How data flows through the system
- `cypher-queries.md` - Common query patterns

