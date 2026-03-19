# Graph Traversal Functions

Complete documentation for querying and traversing the knowledge graph.

---

## Overview

The graph database provides powerful functions for:
1. **Finding related entities** - Get all entities connected to a given entity
2. **Getting relationship details** - Get the entities involved in a specific fact
3. **Searching** - Find entities and facts by text, labels, or types

---

## 1. Get Related Entities

### `get_related_entities(entity_uuid, direction, relationship_type, limit)`

Get all entities connected to a given entity via relationships.

**Returns:** Full entity objects (not just facts) for all connected entities.

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `entity_uuid` | str | required | UUID of the entity to find connections for |
| `direction` | str | `"both"` | Which relationships to follow:<br>- `"outgoing"`: Only entities this entity points TO<br>- `"incoming"`: Only entities that point TO this entity<br>- `"both"`: All connected entities |
| `relationship_type` | str | `None` | Optional filter by relationship type (e.g., `"LOCATED_AT"`) |
| `limit` | int | `50` | Maximum number of entities to return |

### Returns

List of entity dictionaries with additional relationship info:

```python
[
    {
        "uuid": "entity-abc123",
        "name": "Entity Name",
        "summary": "...",
        "labels": [...],
        "attributes": {...},
        "direction": "outgoing",  # How this entity is connected
        "relationship_type": "LOCATED_AT",
        "relationship_uuid": "rel-xyz789",
        "fact": "The actual fact text"
    },
    ...
]
```

### Examples

```python
# Get all entities that LadybugDB points to
entities = graph_db.get_related_entities(
    ladybug_uuid, 
    direction="outgoing"
)
# Returns: [{"name": "./memory/knowledge.ladybug", ...}, {"name": "Python", ...}]

# Get all entities connected to LadybugDB in any direction
entities = graph_db.get_related_entities(ladybug_uuid)

# Get only entities connected via "LOCATED_AT" relationships
entities = graph_db.get_related_entities(
    ladybug_uuid,
    relationship_type="LOCATED_AT"
)
# Returns: [{"name": "./memory/knowledge.ladybug", ...}]

# Get all entities that point TO Python
entities = graph_db.get_related_entities(
    python_uuid,
    direction="incoming"
)
# Returns: [{"name": "LadybugDB", ...}]
```

---

## 2. Get Relationship Entities

### `get_relationship_entities(relationship_uuid)`

Get the source and target entities for a specific relationship.

**Use case:** When you have a relationship/fact UUID and want to know which entities are involved.

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `relationship_uuid` | str | UUID of the relationship |

### Returns

Dictionary with source and target entities, plus relationship info:

```python
{
    "relationship_uuid": "rel-xyz789",
    "relationship_type": "LOCATED_AT",
    "fact": "LadybugDB is located at ./memory/knowledge.ladybug",
    "valid_at": "2026-03-01T10:00:00",
    "derivation_version": "v1.0.0",
    "source": {
        "uuid": "entity-abc123",
        "name": "LadybugDB",
        "summary": "...",
        "labels": [...]
    },
    "target": {
        "uuid": "entity-def456",
        "name": "./memory/knowledge.ladybug",
        "summary": "...",
        "labels": [...]
    }
}
```

Returns `None` if relationship not found.

### Example

```python
# Get entities involved in a specific fact
rel_info = graph_db.get_relationship_entities("rel-xyz789")

print(f"{rel_info['source']['name']} -> {rel_info['target']['name']}")
# Output: LadybugDB -> ./memory/knowledge.ladybug

print(f"Fact: {rel_info['fact']}")
# Output: Fact: LadybugDB is located at ./memory/knowledge.ladybug

# Access full entity details
print(f"Source labels: {rel_info['source']['labels']}")
# Output: Source labels: ['technology', 'database']
```

---

## 3. Get Entity Neighborhood (NOT YET IMPLEMENTED)

### `get_entity_neighborhood(entity_uuid, max_hops, direction)`

**STATUS:** Not yet implemented due to Kuzu limitations.

**Workaround:** Use `get_related_entities()` for getting direct neighbors (1 hop).

**Planned functionality:** Get all entities within N hops of a given entity (graph traversal).

---

## Complete Query Function Reference

### Entity Queries

| Function | Description | Returns |
|----------|-------------|---------|
| `search_entities(project, query, labels, limit)` | Search by text and/or labels | List of entities |
| `get_all_entities(project, limit)` | Get all entities in project | List of entities |
| `get_entity_by_name(project, name)` | Exact name match | Single entity or None |
| `get_entity_by_uuid(uuid)` | Get by UUID | Single entity or None |
| `get_entities_by_label(project, label, limit)` | Filter by label | List of entities |
| **`get_related_entities(uuid, direction, type, limit)`** | **Get connected entities** | **List of entities with relationship info** |

### Fact/Relationship Queries

| Function | Description | Returns |
|----------|-------------|---------|
| `get_entity_facts(uuid)` | Get all facts about entity | List of facts |
| `search_facts(project, query, type, limit)` | Search by text and/or type | List of facts |
| **`get_relationship_entities(uuid)`** | **Get entities in a relationship** | **Dict with source/target entities** |

---

## Usage Patterns

### Pattern 1: Explore Entity Connections

```python
# Start with an entity
entity = graph_db.get_entity_by_name("my-project", "LadybugDB")

# Get all connected entities
related = graph_db.get_related_entities(entity['uuid'])

# Explore each connection
for r in related:
    print(f"{r['direction']}: {r['name']} via {r['relationship_type']}")
```

### Pattern 2: Trace Fact to Source

```python
# Find a fact
facts = graph_db.search_facts("my-project", query="located")

# Get the entities involved
for fact in facts:
    rel_info = graph_db.get_relationship_entities(fact['uuid'])
    print(f"Source: {rel_info['source']['name']}")
    print(f"Target: {rel_info['target']['name']}")
    print(f"Fact: {rel_info['fact']}")
```

### Pattern 3: Build Entity Graph

```python
# Get an entity and all its connections
entity = graph_db.get_entity_by_name("my-project", "Python")

# Get outgoing relationships
outgoing = graph_db.get_related_entities(entity['uuid'], direction="outgoing")
print(f"Python points to: {[e['name'] for e in outgoing]}")

# Get incoming relationships
incoming = graph_db.get_related_entities(entity['uuid'], direction="incoming")
print(f"Points to Python: {[e['name'] for e in incoming]}")
```

---

## Limitations

1. **Multi-hop traversal not yet supported** - `get_entity_neighborhood()` is not implemented
   - **Workaround:** Use `get_related_entities()` iteratively
   
2. **No path finding** - Cannot find shortest path between two entities
   - **Workaround:** Implement manually using `get_related_entities()`

3. **No graph algorithms** - No PageRank, centrality, etc.
   - **Future:** May be added when Kuzu supports these features

---

## Performance Notes

- All queries use indices on `uuid` fields (fast lookups)
- Text search uses `CONTAINS` (case-insensitive substring match)
- Limit results to avoid large result sets
- For large graphs, consider pagination

---

## See Also

- [Database Schema](./database-schema.md) - Complete schema documentation
- [Tool Interfaces](./tool-interfaces.md) - All 25+ tool functions
- [Workflows](./workflows.md) - Common usage workflows

