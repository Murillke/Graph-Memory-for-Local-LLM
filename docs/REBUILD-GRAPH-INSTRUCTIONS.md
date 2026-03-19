# Rebuild Graph Instructions

**Quick reference for rebuilding the graph database from scratch**

---

## [TARGET] **When to Rebuild:**

- After fixing major bugs (limit bug, entity loading, etc.)
- To create a clean v2 with lessons learned
- To test that all fixes work correctly
- To compare old vs new graph

---

##  **Quick Start:**

**User says:** `Rebuild the graph` or `Create v2 graph`

**Auggie does:**

1. Check status: `python3 scripts/sync.py --project "gml-llm" --status`
2. Show all interactions: `python3 scripts/sync.py --project "gml-llm" --show`
3. Extract all entities and facts from ALL interactions
4. Store to new database: `python3 scripts/store_extraction.py --project "gml-llm-v2" --graph-db "./memory/gml-llm-v2.db" --extraction-file examples/full-extraction.json`
5. Compare old vs new

---

## [*] **Timeline:**

**Total: ~1 hour (NOT hours!)**

- Read interactions from SQL: 1 minute [OK] (automated)
- Analyze and extract: 30-60 minutes [OK] (Auggie's work)
- Generate JSON: 1 minute [OK] (automated)
- Store to graph: 5 minutes [OK] (automated)
- Compare: 5 minutes [OK] (automated)

**Only the extraction step requires thinking - everything else is automated!**

---

## [LIST] **Extraction Best Practices:**

### **Rule 1: Extract ALL entities referenced in facts**

[ERROR] **BAD:**
```json
{
  "entities": [{"name": "Entity A"}],
  "facts": [{"source_entity": "Entity B", "target_entity": "Entity A"}]
}
```
Result: Fact skipped because "Entity B" doesn't exist

[OK] **GOOD:**
```json
{
  "entities": [
    {"name": "Entity A"},
    {"name": "Entity B"}
  ],
  "facts": [{"source_entity": "Entity B", "target_entity": "Entity A"}]
}
```
Result: Fact stored successfully

### **Rule 2: Check before storing**

Before running storage, verify:
1. List all entity names in facts
2. Check all are in entities list
3. Add missing entities

### **Rule 3: Don't assume entities exist**

Even though the storage script now pre-loads existing entities, it's best practice to extract all entities in the current extraction for completeness.

---

## [SEARCH] **Comparison Commands:**

### **Entity counts:**
```bash
python3 -c "
from tools.graph_db import GraphDatabase
db1 = GraphDatabase('./memory/gml-llm.db')
db2 = GraphDatabase('./memory/gml-llm-v2.db')
e1 = db1.get_all_entities('gml-llm')
e2 = db2.get_all_entities('gml-llm-v2')
print(f'v1: {len(e1)} entities')
print(f'v2: {len(e2)} entities')
print(f'Difference: {len(e2) - len(e1)}')
db1.close()
db2.close()
"
```

### **Fact counts:**
```bash
python3 -c "
from tools.graph_db import GraphDatabase
db1 = GraphDatabase('./memory/gml-llm.db')
db2 = GraphDatabase('./memory/gml-llm-v2.db')
f1 = db1.get_all_facts('gml-llm')
f2 = db2.get_all_facts('gml-llm-v2')
print(f'v1: {len(f1)} facts')
print(f'v2: {len(f2)} facts')
print(f'Difference: {len(f2) - len(f1)}')
db1.close()
db2.close()
"
```

### **Find missing entities:**
```bash
python3 -c "
from tools.graph_db import GraphDatabase
db1 = GraphDatabase('./memory/gml-llm.db')
db2 = GraphDatabase('./memory/gml-llm-v2.db')
e1 = set([e['name'] for e in db1.get_all_entities('gml-llm')])
e2 = set([e['name'] for e in db2.get_all_entities('gml-llm-v2')])
missing_in_v1 = e2 - e1
missing_in_v2 = e1 - e2
print(f'Entities in v2 but not v1: {len(missing_in_v1)}')
for e in sorted(missing_in_v1)[:10]:
    print(f'  - {e}')
print(f'Entities in v1 but not v2: {len(missing_in_v2)}')
for e in sorted(missing_in_v2)[:10]:
    print(f'  - {e}')
db1.close()
db2.close()
"
```

---

## [OK] **Success Criteria:**

After rebuild, v2 should have:
- [OK] More entities than v1 (no missing entities)
- [OK] More facts than v1 (no skipped facts)
- [OK] All fixes verified (limit bug, entity loading, quote escaping)
- [OK] Complete extraction from the start

---

## [START] **Ready to Rebuild?**

Just say: `Rebuild the graph (see docs/REBUILD-GRAPH-INSTRUCTIONS.md)`

Auggie will handle the rest!

