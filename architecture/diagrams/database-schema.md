# Database Schema Diagrams

Compact schema diagrams for the SQL audit log and graph memory layers.

Current model:
- SQL database: `conversations.db`
- graph database: `{project}.graph`

---

## 1. SQL Audit Log Schema

```mermaid
erDiagram
    projects ||--o{ project_paths : has
    projects ||--o{ interactions : has

    projects {
        string name PK
        string description
        datetime created_at
    }

    project_paths {
        string path PK
        string project_name FK
        string machine_id
        datetime created_at
    }

    interactions {
        int id PK
        string uuid UK
        string project_name FK
        string user_message
        string assistant_message
        datetime timestamp
        string content_hash
        string previous_hash
        int chain_index
        string file_hash
        string timestamp_proof
        boolean processed
        datetime extracted_at
        string session_id
        int interaction_number
        int response_time_ms
        int token_count
        string fidelity
        string source_note
        string context_data
        boolean confidential
        datetime deleted_at
    }
```

**Primary role:**
- append-only conversation audit log
- integrity proof via `content_hash`, `previous_hash`, `chain_index`

---

## 2. Integrity Chain

```mermaid
flowchart LR
    I1[Interaction 1<br/>content_hash h1<br/>previous_hash null]
    I2[Interaction 2<br/>content_hash h2<br/>previous_hash h1]
    I3[Interaction 3<br/>content_hash h3<br/>previous_hash h2]
    I4[Interaction 4<br/>content_hash h4<br/>previous_hash h3]

    I1 --> I2 --> I3 --> I4
```

**Integrity proof checks:**
- recompute `content_hash`
- verify `previous_hash`
- verify sequential `chain_index`

---

## 3. Graph Memory Schema

```mermaid
flowchart LR
    P[Project]
    E1[Entity]
    E2[Entity]
    A[Alias]
    R[RELATES_TO]

    P -->|HAS_ENTITY| E1
    P -->|HAS_ENTITY| E2
    A -->|ALIAS_OF| E1
    E1 -->|RELATES_TO| E2
```

```mermaid
flowchart TB
    Entity[Entity node]
    EntityFields[name<br/>type<br/>summary<br/>source_interactions<br/>source_hashes<br/>extraction_proof<br/>timestamp_proof]

    Rel[RELATES_TO edge]
    RelFields[fact<br/>relationship_type<br/>episodes<br/>episode_hashes<br/>derivation_proof<br/>timestamp_proof<br/>valid_at<br/>invalid_at]

    Alias[Alias node]
    AliasFields[name<br/>canonical_uuid<br/>source_hashes<br/>alias_proof<br/>timestamp_proof]

    Entity --> EntityFields
    Rel --> RelFields
    Alias --> AliasFields
```

**Primary role:**
- queryable memory for entities, facts, relationships, and aliases

---

## 4. Derivation Links

```mermaid
flowchart TB
    subgraph SQL[SQL Source Rows]
        I1[uuid-1<br/>content_hash h1]
        I2[uuid-2<br/>content_hash h2]
    end

    subgraph Graph[Graph Memory]
        E[Entity<br/>source_hashes h1,h2<br/>extraction_proof]
        R[Relationship<br/>episode_hashes h2<br/>derivation_proof]
        A[Alias<br/>source_hashes h1<br/>alias_proof]
    end

    I1 -.-> E
    I2 -.-> E
    I2 -.-> R
    I1 -.-> A
```

**Interpretation:**
- graph artifacts carry source hashes so they can be checked later
- this is the derivation layer, not the integrity layer

---

## 5. Timestamp and Attestation Fields

```mermaid
flowchart LR
    Artifact[Entity / Relationship / Alias / Interaction]
    TP[timestamp_proof]
    State[attestation_status]
    Anchor[OpenTimestamps / Bitcoin]

    Artifact --> TP --> State --> Anchor
```

**Terminology:**
- `timestamp_proof` = local timestamp claim
- `attestation_status` = whether external anchoring was attempted or confirmed

---

## 6. SQL vs Graph Responsibility Split

```mermaid
flowchart LR
    SQL[(conversations.db<br/>raw interactions<br/>integrity proof)]
    Graph[({project}.graph<br/>entities, facts, aliases<br/>derivation proofs)]

    SQL -.source hashes feed.-> Graph
```

**Use SQL for:**
- conversation export
- chain verification
- provenance recovery

**Use Graph for:**
- memory queries
- relationship traversal
- semantic recall

---

## 7. Multi-Project Layout

```mermaid
flowchart TB
    SQL[(conversations.db)]

    subgraph Projects[Per-Project Graph Files]
        G1[(frontend.graph)]
        G2[(backend.graph)]
        G3[(ops.graph)]
    end

    SQL --> G1
    SQL --> G2
    SQL --> G3
```

**Model:**
- one shared SQL audit log
- one graph memory file per project by default

---

## See Also

- [system-architecture.md](./system-architecture.md)
- [../data-model.md](../data-model.md)
- [../../docs/database-schema.md](../../docs/database-schema.md)
- [../../docs/proof-model.md](../../docs/proof-model.md)
