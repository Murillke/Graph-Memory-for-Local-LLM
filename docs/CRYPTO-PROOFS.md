# Cryptographic Proof System

See [proof-model.md](./proof-model.md) for the canonical vocabulary. In this
document:
- **integrity proof** = SQL hash chain
- **derivation proof** = `extraction_proof` / `derivation_proof` in the graph
- **timestamp proof** = local signed timestamp payload
- **external attestation** = OpenTimestamps / Bitcoin anchoring state

**Complete tamper-evidence and audit trail for AI reasoning**

---

## Quick Start - Verify Your Data

**Verify everything:**
```bash
python scripts/verify_integrity.py --project "my-project" --all
```

**Expected output:**
```
[OK] Hash chain verified! (27 interactions)
[OK] All 37 entities verified!
[OK] All 21 relationships verified!
[OK] ALL VERIFICATIONS PASSED!
```

**What this means:**
- All interactions have valid SHA-256 hash chain
- All entities have valid derivation proofs tied to source interactions
- All facts have valid derivation proofs tied to source episodes
- No data has been tampered with

**Other verification commands:**
```bash
# Verify just SQL hash chain
python scripts/verify_integrity.py --project "my-project" --sql

# Verify just graph proofs (entities + relationships)
python scripts/verify_integrity.py --project "my-project" --graph

# Verify specific entity
python scripts/verify_integrity.py --entity "entity-abc123"

# Verify specific relationship
python scripts/verify_integrity.py --relationship "rel-xyz789"

# Verbose output (shows each entity/fact being verified)
python scripts/verify_integrity.py --project "my-project" --all --verbose
```

**Script location:** `scripts/verify_integrity.py`

---

## Overview

The memory system includes a layered proof system that provides:

1. **Integrity proofs** - Detect modification to interaction history
2. **Derivation proofs** - Trace entities/facts back to source hashes
3. **Standalone graph verification** - Check graph-contained evidence without SQL
4. **AI reasoning tracking** - Capture how AI interpreted data at extraction time
5. **Timestamp proofs and external attestation** - Record when proof-bearing artifacts were created and whether they were externally anchored

---

## Proof Layers

### Layer 1: Integrity Proof

**Implemented by:** SQL hash chain

**Purpose:** Prove interactions haven't been tampered with, deleted, or reordered

**How it works:**
- Each interaction has a `content_hash` (SHA-256 of its content)
- Each interaction has a `previous_hash` (links to previous interaction)
- Each interaction has a `chain_index` (sequential number)

**Tamper detection:**
- [ERROR] Modify content -> hash mismatch
- [ERROR] Delete interaction -> chain breaks
- [ERROR] Reorder interactions -> previous_hash doesn't match
- [ERROR] Insert interaction -> chain breaks

**Fields added to `interactions` table:**
```sql
content_hash TEXT NOT NULL,       -- SHA-256 of this interaction
previous_hash TEXT,               -- Hash of previous interaction
chain_index INTEGER NOT NULL,     -- Sequential number in chain
```

---

### Layer 2: Derivation Proofs for Entities

**Implemented by:** `extraction_proof` on entities

**Purpose:** Prove entities were derived from specific interactions

**How it works:**
- Entity stores `source_interactions` (UUIDs)
- Entity stores `source_hashes` (content_hash from each interaction)
- Entity has `extraction_proof` (SHA-256 of entity + source hashes)

**Verification:**
- With SQL: Fetch interactions, verify hashes match, recalculate proof
- Without SQL: Use stored hashes, recalculate proof (lower trust)

**Fields added to `Entity` node:**

> **[!] JSON ENCODING:** Kuzu does not support array columns. These fields are stored as JSON strings in `STRING` columns. Parse with `json.loads()`.

```cypher
source_interactions STRING,        -- JSON array: '["uuid-abc", "uuid-def"]'
source_hashes STRING,              -- JSON array: '["sha256-1", "sha256-2"]'
extraction_timestamp TIMESTAMP,    -- When extraction happened
extraction_version STRING,         -- Semantic version (e.g., "v1.0.0")
extraction_commit STRING,          -- Git commit hash (absolute reference)
extraction_proof STRING,           -- SHA-256 derivation proof for the entity
extraction_batch_uuid STRING,      -- Reference to ExtractionBatch node
```

---

### Layer 3: Derivation Proofs for Relationships

**Implemented by:** `derivation_proof` on relationships

**Purpose:** Prove facts were derived from specific interactions

**How it works:**
- Relationship stores `episodes` (interaction UUIDs)
- Relationship stores `episode_hashes` (content_hash from each interaction)
- Relationship has `derivation_proof` (SHA-256 of fact + episode hashes)

**Verification:** Same derivation-proof model as entities

**Fields added to `RELATES_TO` edge:**

> **[!] JSON ENCODING:** Same as Entity - these are JSON strings, not arrays.

```cypher
episodes STRING,                   -- JSON array of interaction UUIDs
episode_hashes STRING,             -- JSON array: '["sha256-1", "sha256-2"]'
derivation_timestamp TIMESTAMP,    -- When derivation happened
derivation_version STRING,         -- Semantic version (e.g., "v1.0.0")
derivation_commit STRING,          -- Git commit hash (absolute reference)
derivation_proof STRING,           -- SHA-256 derivation proof for the relationship
extraction_batch_uuid STRING,      -- Reference to ExtractionBatch node
superseded_by STRING,              -- UUID of fact that superseded this
superseding_proof STRING,          -- SHA-256 proof of superseding event
```

---

### Layer 4: Timestamp Proofs and External Attestation

**Implemented by:** `timestamp_proof` fields and OpenTimestamps-related metadata

**Purpose:** Record a local timestamp claim for proof-bearing artifacts and,
when available, show whether that claim was externally attested.

**Important distinction:**
- A **timestamp proof** is a local signed timestamp payload
- An **external attestation** is OpenTimestamps / Bitcoin anchoring state
- Neither replaces integrity verification or derivation verification

---

## Extraction Context Tracking

**Purpose:** Capture HOW the AI interpreted data at extraction time

**Why this matters:**
- Same interaction + different extraction rules = different entities/facts
- Graph is a snapshot of AI reasoning at that moment
- Can compare extractions over time
- Can debug "why did AI think that?"

**What we track:**
- `extraction_version` - Semantic version (e.g., "v1.0.0")
- `extraction_commit` - Git commit hash (absolute reference to extraction rules)
- `extraction_timestamp` - When extraction happened

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

---

## Verification Levels

| Scenario | What You Can Verify | Trust Level |
|----------|---------------------|-------------|
| **SQL + Graph** | Integrity proofs + derivation proofs | **HIGH** [OK] |
| **Graph only** | Internal graph consistency and graph-contained proofs | **MEDIUM** [WARNING] |
| **SQL only** | Interaction integrity proof | **HIGH** [OK] |

---

## User Commands

### Verify Everything
```
User: "Verify integrity"

Auggie: "[OK] Complete verification passed!

         Integrity proof: 847 interactions verified
         Entity derivation proofs: 123/123 verified against SQL
         Relationship derivation proofs: 456/456 verified against SQL

         Trust level: HIGH"
```

### Verify Graph Only
```
User: "Verify graph only"

Auggie: "[WARNING]  Standalone verification (SQL not checked)

         Graph Entities: 123/123 internally consistent
         Graph Relationships: 456/456 internally consistent

         Trust level: MEDIUM (graph is consistent but unanchored)"
```

### Verify Specific Fact
```
User: "Verify fact: LadybugDB is located at ./memory/knowledge.ladybug"

Auggie: "[OK] Fact verified with complete chain!

         Source Interaction: uuid-847 [2026-03-01T10:00:00Z]
         Hash: abc123... [OK]

         Extraction: v1.0.0 (commit: a1b2c3d4) [OK]
         Relationship derivation proof: def456... [OK]

         Trust level: HIGH"
```

---

## Benefits

### 1. Tamper Detection
- Detect any modification to SQL or graph data
- Cryptographic proof (can't fake without breaking chain)

### 2. Audit Trail
- Trace every fact back to source conversation
- Prove AI reasoning was legitimate
- Show extraction context (version, commit, timestamp)

### 3. Disaster Recovery
- Graph can work standalone (without SQL)
- Can verify graph internal consistency
- Can rebuild graph from SQL if needed

### 4. AI Evolution Tracking
- Compare extractions over time
- See how AI interpretation improved
- Debug extraction issues

### 5. Legal/Compliance
- Prove AI decision-making process
- Show evidence for recommendations
- Cryptographically verifiable audit trail

---

## Terminology Notes

- `extraction_proof` is the field name for an entity derivation proof
- `derivation_proof` is the field name for a relationship derivation proof
- `timestamp_proof` is separate from external OpenTimestamps / Bitcoin attestation
- "verified" should always be qualified with the proof layer being discussed

## Implementation

See:
- `proof-model.md` - Canonical proof taxonomy
- `database-schema.md` - Complete schema with crypto fields
- `tool-interfaces.md` - Verification tools (20-25)
- `workflows.md` - Verification workflows (6-8)
