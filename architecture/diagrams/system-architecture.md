# System Architecture Diagram

Primary architecture diagrams for the LLM Memory System.

These diagrams reflect the current runtime model:
- SQL audit log: `conversations.db`
- Graph memory: `{project}.graph`
- dual path contexts:
  - subsystem repo mode: `./memory`, `./tmp`
  - host workspace mode: `./mem/memory`, `./mem/tmp`

See [../../docs/proof-model.md](../../docs/proof-model.md) for canonical proof
terminology.

---

## 1. High-Level Architecture

```mermaid
flowchart TB
    User[User or LLM Agent]

    subgraph Interface[Workflow Interface]
        Sync[sync.md]
        Remember[remember.md]
        Search[search.md]
        Verify[verify.md]
        Export[export.md]
    end

    subgraph Scripts[Execution Layer]
        Import[import_conversation.py]
        Store[store_extraction.py]
        Query[query_memory.py]
        Check[verify_integrity.py]
        History[export_history.py]
    end

    subgraph Logic[Core Logic]
        Config[config.py]
        SQLLib[sql_db.py]
        GraphLib[graph_db.py]
        Review[deduplication.py / contradiction.py]
    end

    subgraph Storage[Storage]
        SQL[(SQL Audit Log<br/>conversations.db)]
        Graph[(Graph Memory<br/>{project}.graph)]
    end

    User --> Interface --> Scripts --> Logic
    Config -.paths and defaults.-> Scripts
    SQLLib --> SQL
    GraphLib --> Graph
    Review --> Graph
    Import --> SQL
    Store --> Graph
    Query --> Graph
    Check --> SQL
    Check --> Graph
    History --> SQL
    SQL -.source hashes feed.-> Graph
```

---

## 2. Path Contexts

```mermaid
flowchart LR
    subgraph Repo[Subsystem Repo Mode]
        R1[tmp files<br/>./tmp]
        R2[SQL<br/>./memory/conversations.db]
        R3[Graph<br/>./memory/{project}.graph]
        R4[Workflow file<br/>sync.md]
    end

    subgraph Host[Host Workspace Mode]
        H1[tmp files<br/>./mem/tmp]
        H2[SQL<br/>./mem/memory/conversations.db]
        H3[Graph<br/>./mem/memory/{project}.graph]
        H4[Workflow file<br/>mem/sync.md]
    end
```

**Interpretation:**
- both contexts are valid
- the difference is embedding location, not system behavior

---

## 3. Sync Workflow

```mermaid
flowchart TB
    A[Conversation recalled by agent]
    B[tmp/conversation.json]
    C[import_conversation.py]
    D[(conversations.db)]
    E[tmp/extraction.json]
    F[store_extraction.py]
    G[quality review]
    H[aliases / invalidations]
    I[({project}.graph)]

    A --> B --> C --> D
    D --> E --> F --> G --> H --> I
```

**Read it as:**
- SQL stores the conversation trail first
- graph memory is built from extraction output
- quality review refines graph state before it becomes queryable memory

---

## 4. Query Workflow

```mermaid
flowchart LR
    A[User asks a memory question]
    B[query_memory.py]
    C[(Graph Memory)]
    D[Entities]
    E[Facts]
    F[Related entities]
    G[Answer with memory context]

    A --> B --> C
    C --> D
    C --> E
    C --> F
    D --> G
    E --> G
    F --> G
```

---

## 5. Trust and Verification

```mermaid
flowchart LR
    SQL[Integrity Proof<br/>SQL hash chain]
    Entity[Entity Derivation Proof<br/>extraction_proof]
    Rel[Relationship Derivation Proof<br/>derivation_proof]
    Time[Timestamp Proof<br/>local signed claim]
    Attest[External Attestation<br/>OpenTimestamps / Bitcoin]

    SQL --> Entity
    SQL --> Rel
    Entity --> Time
    Rel --> Time
    Time --> Attest
```

**Meaning:**
- integrity proof checks append-only interaction history
- derivation proofs check graph artifacts against source hashes
- timestamp proofs are local timestamp claims
- external attestation is a separate upgrade, not a synonym for verification

---

## 6. Shared Multi-Project Layout

```mermaid
flowchart TB
    subgraph SQL[Shared SQL Audit Log]
        S[(conversations.db)]
    end

    subgraph Graphs[Per-Project Graph Memory]
        G1[(frontend.graph)]
        G2[(backend.graph)]
        G3[(deploy.graph)]
    end

    A1[Frontend agent] --> S
    A2[Backend agent] --> S
    A3[Deploy agent] --> S

    A1 --> G1
    A2 --> G2
    A3 --> G3
```

**Why this matters:**
- one SQL database can hold many projects
- graph memory stays isolated per project unless intentionally shared

---

## 7. Configuration Surface

```mermaid
flowchart TB
    Config[mem.config.json]
    Env[Environment overrides]
    CLI[CLI overrides]

    subgraph Resolved[Resolved Paths]
        SQL[database.sql_path]
        Graph[database.graph_path]
        Tmp[paths.tmp_dir]
        Py[python_path]
    end

    Config --> Resolved
    Env --> Resolved
    CLI --> Resolved
```

**Resolution order:**
1. defaults
2. global config
3. project config
4. environment variables
5. CLI arguments

---

## 8. Command Surface

```mermaid
mindmap
  root((Workflows))
    sync.md
      import conversation
      extract memory
      quality review
    remember.md
      entity lookup
      fact lookup
      relationship traversal
    verify.md
      SQL integrity proof
      graph derivation proofs
      timestamp-oriented checks
    export.md
      SQL conversation history
```

---

## 9. Integrity Chain

```mermaid
flowchart LR
    I1[Interaction 1<br/>content_hash: h1<br/>previous_hash: null]
    I2[Interaction 2<br/>content_hash: h2<br/>previous_hash: h1]
    I3[Interaction 3<br/>content_hash: h3<br/>previous_hash: h2]
    I4[Interaction 4<br/>content_hash: h4<br/>previous_hash: h3]

    I1 --> I2 --> I3 --> I4
```

**What it proves:**
- interactions were not silently edited
- interactions were not reordered
- middle deletions break verification

---

## 10. Derivation Links

```mermaid
flowchart TB
    subgraph SQL[SQL Interactions]
        I1[uuid-1<br/>content_hash h1]
        I2[uuid-2<br/>content_hash h2]
    end

    subgraph Graph[Graph Artifacts]
        E[Entity<br/>source_hashes: h1,h2<br/>extraction_proof]
        R[Relationship<br/>episode_hashes: h2<br/>derivation_proof]
    end

    I1 -.-> E
    I2 -.-> E
    I2 -.-> R
```

**Read it as:**
- entities and facts do not just "exist"
- they carry source hashes that can be checked later

---

## 11. Timestamp Proof States

```mermaid
stateDiagram-v2
    [*] --> LocalOnly: timestamp_proof created
    LocalOnly --> PendingOTS: OpenTimestamps submitted
    LocalOnly --> NotRequested: local-only by choice
    PendingOTS --> Confirmed: external attestation confirmed
    PendingOTS --> SubmissionFailed: submission failed
```

**Interpretation:**
- `timestamp_proof` exists in all cases above.
- Only `Confirmed` means external attestation is available.
- `LocalOnly` and `NotRequested` are still valid local timestamp proofs.

---

## 12. Quality Review Flow

```mermaid
flowchart LR
    NewData[New extraction] --> Detect[Detect duplicates and contradictions]
    Detect --> Review[Automatic or manual review]
    Review --> Alias[Create alias]
    Review --> Invalidate[Invalidate superseded fact]
    Alias --> Memory[Updated graph memory]
    Invalidate --> Memory
```

**Goal:**
- preserve history
- reduce duplicate entities
- mark stale facts without destructive deletion

---

## 13. Temporal Memory

```mermaid
flowchart LR
    Old[Fact A<br/>valid_at: 2020<br/>invalid_at: 2024]
    New[Fact B<br/>valid_at: 2024<br/>invalid_at: null]

    Old -->|superseded_by| New
```

**Use it for:**
- "what was true then?"
- "what is true now?"
- "how did this belief change?"

---

## 14. Non-Destructive Deduplication

```mermaid
flowchart LR
    Duplicate[DB Bug<br/>entity-456] --> Alias[Alias node]
    Canonical[Database Bug<br/>entity-123] --> Alias
    Alias -->|resolves to| Canonical
```

**Why aliases matter:**
- old names still work
- facts keep their lineage
- no silent data loss

---

## 15. Verification Surface

```mermaid
mindmap
  root((Verification))
    verify_integrity.py
      SQL integrity proof
      entity derivation proofs
      relationship derivation proofs
    verify_graph_standalone.py
      graph-internal consistency
      timestamp proof structure
      external attestation status
```

---

## Diagram Notes

- Use "integrity proof" for the SQL hash chain.
- Use "derivation proof" for `extraction_proof` and `derivation_proof`.
- Use "timestamp proof" for the local signed timestamp payload.
- Use "external attestation" for OpenTimestamps / Bitcoin anchoring.

---

## See Also

- [../database-schema.md](../database-schema.md)
- [../system-overview.md](../system-overview.md)
- [../../docs/proof-model.md](../../docs/proof-model.md)
