# Timestamp Schema & Recency-Based Memory Retrieval

**How the memory system tracks time and prioritizes recent/accessed memories**

---

## Overview

The memory system uses a **bi-temporal model** with **access tracking** to implement recency-based memory retrieval inspired by neuroscience and state-of-the-art systems like Zep/Graphiti and AriGraph.

**Key Concepts:**
- **Event Time** - When something actually happened in conversation
- **Ingestion Time** - When it was recorded in the database
- **Access Tracking** - When and how often memories are retrieved
- **Priority Ordering** - New and recently accessed memories first

---

## Timestamp Fields

### Entity Timestamps

```cypher
CREATE NODE TABLE Entity (
  -- ... other fields ...
  
  -- Bi-Temporal Tracking
  extraction_timestamp TIMESTAMP,  -- Event time (when entity was observed in conversation)
  created_at TIMESTAMP NOT NULL,   -- Ingestion time (when added to database)
  
  -- Access Tracking (NOT in crypto proof - metadata only)
  t_last_accessed TIMESTAMP,       -- Last query time (when last retrieved)
  access_count INT64 DEFAULT 0     -- Number of times accessed
);
```

### Relationship Timestamps

```cypher
CREATE REL TABLE RELATES_TO (
  FROM Entity TO Entity,
  
  -- ... other fields ...
  
  -- Bi-Temporal Tracking (from Graphiti)
  valid_at TIMESTAMP,              -- Event time (when fact became true)
  invalid_at TIMESTAMP,            -- Event time (when fact stopped being true)
  created_at TIMESTAMP NOT NULL,   -- Ingestion time (when edge was created)
  expired_at TIMESTAMP             -- Ingestion time (when edge was marked as expired)
);
```

---

## Bi-Temporal Model

### Event Time vs Ingestion Time

**Example:**

```
March 5, 10:00 AM: You and I discuss "Bi-Temporal Model" in conversation
March 19, 3:00 PM: I sync the conversation to memory
```

**Entity timestamps:**
- `extraction_timestamp` = `2026-03-05T10:00:00Z` (event time - when we discussed it)
- `created_at` = `2026-03-19T15:00:00Z` (ingestion time - when I synced it)

**Why this matters:**
- Event time = when knowledge was created in the real world
- Ingestion time = when we recorded it
- Allows querying "what did we know on March 10?" (event time)
- Allows auditing "what was added on March 19?" (ingestion time)

### Field Semantics

| Field | Type | Meaning | Used For |
|-------|------|---------|----------|
| `extraction_timestamp` | Event Time | When entity was observed in conversation | Temporal queries, priority ordering |
| `created_at` | Ingestion Time | When entity was added to database | Audit trail, sync tracking |
| `valid_at` | Event Time | When fact became true | Temporal queries, history |
| `invalid_at` | Event Time | When fact stopped being true | Temporal queries, superseding |
| `expired_at` | Ingestion Time | When edge was marked as expired | Audit trail |

---

## Access Tracking

### How It Works

**When you query entities:**
1. System retrieves matching entities
2. For each entity returned, updates:
   - `t_last_accessed` = current timestamp
   - `access_count` = `access_count + 1`

**Example:**
```python
# Query entity
entity = graph_db.get_entity_by_uuid(uuid, track_access=True)

# Entity before query:
# - t_last_accessed: None
# - access_count: 0

# Entity after query:
# - t_last_accessed: 2026-03-05T17:23:15Z
# - access_count: 1

# Query again:
# - t_last_accessed: 2026-03-05T17:25:30Z
# - access_count: 2
```

### When Access Tracking Happens

**Enabled by default:**
- `get_entity_by_uuid(track_access=True)` - User queries
- `search_entities(track_access=True)` - User searches
- `get_entity_by_name(track_access=True)` - User lookups

**Disabled by default:**
- `get_all_entities(track_access=False)` - Bulk operations
- Quality checks, migrations, internal operations

---

## Priority Ordering

### The Algorithm

**Goal:** Return memories in order of relevance based on recency and access patterns.

**3-Tier Priority System:**

```
Priority 1: NEW entities (extraction_timestamp > base_time)
Priority 2: RECENTLY ACCESSED entities (t_last_accessed > base_time)
Priority 3: OLD entities (everything else)
```

**Base Time Calculation:**
```
base_time = (most recent entity's extraction_timestamp) - 24 hours
```

**Within each priority tier, sort by:**
1. `extraction_timestamp DESC` (newest event first)
2. `t_last_accessed DESC` (most recently accessed first)

### Example

**Today is March 5, 5:00 PM**

**Entities:**
- Entity A: `extraction_timestamp` = March 5, 4:00 PM (1 hour ago)
- Entity B: `extraction_timestamp` = March 4, 3:00 PM (26 hours ago), `t_last_accessed` = March 5, 4:30 PM
- Entity C: `extraction_timestamp` = March 3, 2:00 PM (51 hours ago), `t_last_accessed` = March 4, 1:00 PM
- Entity D: `extraction_timestamp` = March 5, 3:00 PM (2 hours ago)

**Calculation:**
- Most recent entity: Entity A (March 5, 4:00 PM)
- Base time: March 4, 4:00 PM (24 hours before Entity A)

**Priority 1 (NEW - extraction_timestamp > base_time):**
- Entity A (March 5, 4:00 PM) ← Newest
- Entity D (March 5, 3:00 PM)

**Priority 2 (RECENTLY ACCESSED - t_last_accessed > base_time):**
- Entity B (accessed March 5, 4:30 PM)

**Priority 3 (OLD):**
- Entity C

**Final order:** A, D, B, C [OK]

---

## Implementation

### Database Query

```cypher
-- Step 1: Calculate base time
MATCH (e:Entity)
WHERE e.group_id = 'llm_memory'
  AND e.deleted_at IS NULL
RETURN max(e.extraction_timestamp) as max_time

-- Step 2: Query with priority ordering
MATCH (p:Project {name: 'llm_memory'})-[:HAS_ENTITY]->(e:Entity)
WHERE e.deleted_at IS NULL
ORDER BY 
  CASE 
    WHEN e.extraction_timestamp > timestamp('2026-03-04T16:00:00Z') THEN 1
    WHEN e.t_last_accessed IS NOT NULL AND e.t_last_accessed > timestamp('2026-03-04T16:00:00Z') THEN 2
    ELSE 3
  END,
  e.extraction_timestamp DESC,
  e.t_last_accessed DESC
LIMIT 50
```

### Performance

**Two-query approach:**
1. Get max timestamp: ~1ms (single aggregation)
2. Query with ordering: ~10ms (CASE + ORDER BY in database)

**Total latency:** <20ms for most queries [OK]

---

## Cryptographic Integrity

### What's Included in Proofs

**Entity Extraction Proof:**
```python
content = "|".join([
    entity_name,
    entity_summary or "",
    json.dumps(sorted(entity_labels)),
    json.dumps(entity_attributes) if entity_attributes else "",
    *sorted(source_hashes),
    extraction_timestamp  # ← Event time (IN proof)
])
extraction_proof = sha256(content)
```

**Relationship Derivation Proof:**
```python
content = "|".join([
    fact,
    source_uuid,
    target_uuid,
    relationship_name,
    group_id,
    *sorted(episode_hashes),
    valid_at  # ← Event time (IN proof)
])
derivation_proof = sha256(content)
```

**NOT included in proofs (metadata only):**
- `t_last_accessed` - Changes on every query
- `access_count` - Changes on every query
- `created_at` - Ingestion time (not part of content)

**Why this matters:**
- Event timestamps are cryptographically verified
- Access metadata can change without breaking proofs
- Ingestion time is audit trail, not content

---

## Migration

### Adding Timestamp Fields to Existing Entities

**Script:** `scripts/migrate_add_timestamps.py`

**What it does:**
1. Adds `t_last_accessed` and `access_count` properties to Entity schema
2. Sets `t_last_accessed` = NULL for all existing entities
3. Sets `access_count` = 0 for all existing entities
4. Preserves all existing data and crypto proofs

**Usage:**
```bash
# Dry run (see what would happen)
python scripts/migrate_add_timestamps.py --project llm_memory --dry-run

# Apply migration
python scripts/migrate_add_timestamps.py --project llm_memory
```

---

## See Also

- `docs/database-schema.md` - Complete schema specification
- `docs/CRYPTO-PROOFS.md` - Cryptographic integrity system
- `docs/TEMPORAL-QUERIES.md` - Querying by time
- `docs/ARCHITECTURE.md` - Overall system architecture


