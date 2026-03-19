# Temporal Queries - "What were we doing 3 months ago?"

**Great question!** Let's analyze what we have and what's missing for temporal queries.

---

## [SEARCH] Current State

### What We Have [OK]

**1. Timestamps in SQL Database:**
```sql
-- interactions table
timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP

-- projects table
created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
```

**2. Timestamps in Graph Database:**
```python
# Entity timestamps
created_at TIMESTAMP           # When entity was created in graph
extraction_timestamp TIMESTAMP # When entity was extracted from conversation

# Relationship timestamps
created_at TIMESTAMP           # When relationship was created in graph
valid_at TIMESTAMP            # When the fact became true
invalid_at TIMESTAMP          # When the fact stopped being true
derivation_timestamp TIMESTAMP # When relationship was extracted
```

**3. Current Query Functions:**
- `get_all_interactions(project_name)` - Get all interactions (no time filter)
- `get_interaction_by_uuid(uuid)` - Get single interaction
- `search_entities(query, labels)` - Search entities (no time filter)
- `get_facts_by_entity(entity_uuid)` - Get facts (no time filter)

---

## [ERROR] What's Missing

### Missing Query Functions:

**1. Time-Based Interaction Queries** [ERROR]
```python
# NOT IMPLEMENTED YET
get_interactions_by_timerange(
    project_name: str,
    start_date: str,  # "2025-12-01"
    end_date: str     # "2026-03-01"
) -> List[Dict]
```

**2. Time-Based Entity Queries** [ERROR]
```python
# NOT IMPLEMENTED YET
get_entities_by_extraction_time(
    start_date: str,
    end_date: str
) -> List[Dict]
```

**3. Time-Based Fact Queries** [ERROR]
```python
# NOT IMPLEMENTED YET
get_facts_valid_at_time(
    timestamp: str  # "2025-12-01T00:00:00Z"
) -> List[Dict]

get_facts_by_timerange(
    start_date: str,
    end_date: str
) -> List[Dict]
```

**4. Natural Language Time Queries** [ERROR]
```python
# NOT IMPLEMENTED YET
query_memory_by_time(
    query: str  # "What were we doing 3 months ago?"
) -> List[Dict]
```

---

## [TARGET] Implementation Plan

### Phase 1: SQL Time Queries (Easy - 1-2 hours)

**Add to `tools/sql_db.py`:**

```python
def get_interactions_by_timerange(
    self,
    project_name: str,
    start_date: str,
    end_date: str
) -> List[Dict[str, Any]]:
    """Get interactions within a time range.
    
    Args:
        project_name: Project name
        start_date: Start date (ISO format: "2025-12-01" or "2025-12-01T00:00:00")
        end_date: End date (ISO format: "2026-03-01" or "2026-03-01T00:00:00")
    
    Returns:
        List of interactions within the time range
    """
    conn = self._get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM interactions
        WHERE project_name = ?
          AND deleted_at IS NULL
          AND timestamp >= ?
          AND timestamp <= ?
        ORDER BY timestamp ASC
    """, (project_name, start_date, end_date))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

def get_interactions_since(
    self,
    project_name: str,
    since_date: str
) -> List[Dict[str, Any]]:
    """Get interactions since a specific date."""
    conn = self._get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM interactions
        WHERE project_name = ?
          AND deleted_at IS NULL
          AND timestamp >= ?
        ORDER BY timestamp ASC
    """, (project_name, since_date))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

def get_interactions_before(
    self,
    project_name: str,
    before_date: str
) -> List[Dict[str, Any]]:
    """Get interactions before a specific date."""
    conn = self._get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM interactions
        WHERE project_name = ?
          AND deleted_at IS NULL
          AND timestamp <= ?
        ORDER BY timestamp ASC
    """, (project_name, before_date))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]
```

---

### Phase 2: Graph Time Queries (Medium - 2-3 hours)

**Add to `tools/graph_db.py`:**

```python
def get_entities_by_extraction_time(
    self,
    start_date: str,
    end_date: str,
    group_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Get entities extracted within a time range.
    
    Args:
        start_date: Start date (ISO format)
        end_date: End date (ISO format)
        group_id: Optional group/project filter
    
    Returns:
        List of entities extracted in that time range
    """
    group_filter = f"AND e.group_id = '{group_id}'" if group_id else ""
    
    result = self.conn.execute(f"""
        MATCH (e:Entity)
        WHERE e.extraction_timestamp >= timestamp('{start_date}')
          AND e.extraction_timestamp <= timestamp('{end_date}')
          AND e.deleted_at IS NULL
          {group_filter}
        RETURN e.*
        ORDER BY e.extraction_timestamp ASC
    """)
    
    entities = []
    while result.has_next():
        row = result.get_next()
        entities.append({
            "uuid": row[0],
            "name": row[1],
            "summary": row[3],
            "extraction_timestamp": str(row[9]),
            # ... other fields
        })
    
    return entities

def get_facts_valid_at_time(
    self,
    timestamp: str,
    group_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Get facts that were valid at a specific time.
    
    Args:
        timestamp: Time to check (ISO format)
        group_id: Optional group/project filter
    
    Returns:
        List of facts valid at that time
    """
    group_filter = f"AND r.group_id = '{group_id}'" if group_id else ""
    
    result = self.conn.execute(f"""
        MATCH (source:Entity)-[r:RELATES_TO]->(target:Entity)
        WHERE r.valid_at <= timestamp('{timestamp}')
          AND (r.invalid_at IS NULL OR r.invalid_at > timestamp('{timestamp}'))
          {group_filter}
        RETURN source.uuid, source.name, target.uuid, target.name,
               r.uuid, r.name, r.fact, r.valid_at, r.invalid_at
    """)
    
    facts = []
    while result.has_next():
        row = result.get_next()
        facts.append({
            "source_entity": {"uuid": row[0], "name": row[1]},
            "target_entity": {"uuid": row[2], "name": row[3]},
            "relationship": {
                "uuid": row[4],
                "name": row[5],
                "fact": row[6],
                "valid_at": str(row[7]),
                "invalid_at": str(row[8]) if row[8] else None
            }
        })
    
    return facts
```

---

### Phase 3: CLI Wrapper (Easy - 1 hour)

**Add to `scripts/query_memory.py`:**

```python
# Add new subcommand: time-range
parser_time = subparsers.add_parser('time-range', help='Query by time range')
parser_time.add_argument('--start', required=True, help='Start date (YYYY-MM-DD)')
parser_time.add_argument('--end', required=True, help='End date (YYYY-MM-DD)')
parser_time.add_argument('--type', choices=['interactions', 'entities', 'facts'], 
                        default='interactions', help='What to query')

# Implementation
if args.command == 'time-range':
    if args.type == 'interactions':
        results = sql_db.get_interactions_by_timerange(
            project_name, args.start, args.end
        )
    elif args.type == 'entities':
        results = graph_db.get_entities_by_extraction_time(
            args.start, args.end, project_name
        )
    elif args.type == 'facts':
        # Get facts that were valid during this time range
        results = graph_db.get_facts_by_timerange(
            args.start, args.end, project_name
        )
```

---

### Phase 4: Natural Language Time Queries (Hard - 4-6 hours)

**This requires LLM to parse natural language:**

```python
# tools/extraction/parse_time_query.py

def parse_time_query(query: str) -> Dict[str, Any]:
    """Parse natural language time query using LLM.
    
    Examples:
        "What were we doing 3 months ago?" 
        -> {"type": "timerange", "start": "2025-12-01", "end": "2025-12-31"}
        
        "What did you learn last week?"
        -> {"type": "timerange", "start": "2026-02-22", "end": "2026-02-28"}
        
        "Show me facts from December"
        -> {"type": "timerange", "start": "2025-12-01", "end": "2025-12-31"}
    """
    # Use LLM to parse the query
    # Extract: time range, query type (interactions/entities/facts)
    # Return structured query parameters
```

---

## [DATA] Usage Examples

### Example 1: "What were we doing 3 months ago?"

```bash
# Step 1: Calculate date range (3 months ago = Dec 2025)
python3 scripts/query_memory.py time-range \
    --project "my-project" \
    --start "2025-12-01" \
    --end "2025-12-31" \
    --type interactions

# Output: All interactions from December 2025
```

### Example 2: "What facts were valid on Christmas?"

```bash
python3 scripts/query_memory.py facts-at-time \
    --project "my-project" \
    --timestamp "2025-12-25T00:00:00Z"

# Output: All facts that were valid on Dec 25, 2025
# (valid_at <= 2025-12-25 AND (invalid_at IS NULL OR invalid_at > 2025-12-25))
```

### Example 3: "What entities did we extract last month?"

```bash
python3 scripts/query_memory.py time-range \
    --project "my-project" \
    --start "2026-02-01" \
    --end "2026-02-28" \
    --type entities

# Output: All entities extracted in February 2026
```

---

## [OK] Summary

**Current Status:**
- [OK] We HAVE timestamps on everything
- [ERROR] We DON'T HAVE time-based query functions
- [ERROR] We DON'T HAVE natural language time parsing

**To Answer "What were we doing 3 months ago?":**

**Option 1: Add SQL time queries (1-2 hours)**
- Get interactions by time range
- Simple and effective

**Option 2: Add graph time queries (2-3 hours)**
- Get entities/facts by time
- More powerful

**Option 3: Add natural language parsing (4-6 hours)**
- Parse "3 months ago" -> actual dates
- Use LLM to understand time expressions
- Most user-friendly

**Recommendation:** Start with Option 1 (SQL time queries) - it's quick and solves 80% of the use case!

---

**Want me to implement SQL time queries now?** 

