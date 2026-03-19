# consolidate.md - Find Patterns in Your Knowledge Graph

---

## [BOT] Config First

**Read `mem.config.json` before running any command:**
- Use `python_path` value for `{PYTHON_PATH}`
- Use `project_name` value for `{PROJECT}`
- Do not guess or substitute different values

---

## LLM Instructions

**If you have been instructed to "follow consolidate.md", "execute consolidate.md", or "run consolidate.md", you are expected to:**

1. **Run the consolidation script** to find patterns in the knowledge graph
2. **Present the results** to the user (hubs, clusters, patterns)
3. **Explain the findings** in natural language

**This is a workflow to be followed by an AI agent.**

---

## What This Does

Find higher-order patterns in your knowledge graph:
- **Hub entities** - Concepts with many connections (incoming + outgoing)
- **Clusters** - Groups of densely connected entities (related topics)
- **Relationship patterns** - Common relationship types (how things connect)
- **Transitive chains** - Implied connections (A->B->C implies A->C)

All queries are **project-scoped** - only analyzes entities within `{PROJECT}`.

** This is a fully cypher/graph kind of trick **
- [OK] Uses graph traversal (not expensive LLM consolidation)
- [OK] Cheap and fast (just Cypher queries)
- [OK] Finds real patterns (not emergent buzzwords)

---

## Quick Start

```sh
{PYTHON_PATH} scripts/consolidate_knowledge.py --project {PROJECT}
```

Use values from `mem.config.json` for `{PROJECT}` and `{PYTHON_PATH}`.

---

## Examples

### **Basic consolidation:**
```sh
{PYTHON_PATH} scripts/consolidate_knowledge.py --project {PROJECT}
```

### **Find smaller hubs (3+ relationships):**
```sh
{PYTHON_PATH} scripts/consolidate_knowledge.py --project {PROJECT} --min-hub-size 3
```

### **Find smaller clusters (3+ members):**
```sh
{PYTHON_PATH} scripts/consolidate_knowledge.py --project {PROJECT} --min-cluster-size 3
```

### **Find transitive relationships (slower):**
```sh
{PYTHON_PATH} scripts/consolidate_knowledge.py --project {PROJECT} --find-transitive
```

### **Store insights with separate hash chain:**
```sh
{PYTHON_PATH} scripts/consolidate_knowledge.py --project {PROJECT} --store
```

### **Cleanup old detections (manual):**
```sh
{PYTHON_PATH} scripts/consolidate_knowledge.py --project {PROJECT} --cleanup
```

### **Store with auto-cleanup (if enabled in config):**
```sh
{PYTHON_PATH} scripts/consolidate_knowledge.py --project {PROJECT} --store
# Auto-cleanup runs if consolidation.auto_cleanup_enabled = true in mem.config.json
```

### **Override archive days:**
```sh
{PYTHON_PATH} scripts/consolidate_knowledge.py --project {PROJECT} --cleanup --archive-days 90
```

---

## What You'll See

### **Hub Entities:**
```
1. David Astua (10 relationships)
   User who proposed pure entity decomposition approach...
   
2. Attestation (5 relationships)
   Chain of custody proof that preserves original extraction...
```

**Meaning:** These are your central concepts!

### **Clusters:**
```
1. David Astua (10 connected entities)
   Connected to: Pure Entity Decomposition, Emergent Episodes, ...
   
2. Attestation (7 connected entities)
   Connected to: Chain of Custody, verify_attested_entity.py, ...
```

**Meaning:** These are related topic groups!

### **Relationship Patterns:**
```
1. IMPLEMENTS: used 22 times
2. USES: used 17 times
3. DOCUMENTS: used 11 times
4. ENABLES: used 10 times
```

**Meaning:** These are your most common relationship types!

---

## Use Cases

### **1. Understand Your Knowledge Structure:**
```sh
# What are my central concepts?
{PYTHON_PATH} scripts/consolidate_knowledge.py --project {PROJECT}
```

### **2. Find Related Topics:**
```sh
# What clusters exist?
{PYTHON_PATH} scripts/consolidate_knowledge.py --project {PROJECT} --min-cluster-size 3
```

### **3. Discover Implied Connections:**
```sh
# What transitive relationships exist?
{PYTHON_PATH} scripts/consolidate_knowledge.py --project {PROJECT} --find-transitive
```

---

## How It Works

**Unlike Google's expensive LLM consolidation:**

```
Google's Approach:
  Flat SQLite -> LLM finds connections -> $$$$ every 30 min

Our Approach:
  Graph Database -> Cypher queries -> Free, instant!
```

**We use graph traversal to find:**
1. Entities with many relationships (hubs)
2. Densely connected groups (clusters)
3. Common relationship types (patterns)
4. A->B->C chains (transitive)

**All without LLM calls!** Just graph queries! [*]

---

## Configuration

**In `mem.config.json`:**

```json
{
  "consolidation": {
    "auto_cleanup_enabled": false,
    "archive_after_days": 180
  }
}
```

**Settings:**
- `auto_cleanup_enabled` - When `true`, automatically archives and deletes old detections when using `--store`
- `archive_after_days` - Number of days to keep in graph before archiving (default: 180)
- `last_run_timestamp` - Timestamp of last consolidation run (auto-updated, don't edit manually)
- `recommend_after_days` - Show reminder to run consolidation after this many days (default: 30, set to 0 to disable)

**Examples:**

```json
// Keep everything (no auto-cleanup)
{
  "consolidation": {
    "auto_cleanup_enabled": false,
    "archive_after_days": 180
  }
}

// Auto-cleanup after 90 days
{
  "consolidation": {
    "auto_cleanup_enabled": true,
    "archive_after_days": 90
  }
}

// Auto-cleanup after 1 year
{
  "consolidation": {
    "auto_cleanup_enabled": true,
    "archive_after_days": 365
  }
}
```

---

## Smart Reminders

**Automatic recommendations to run consolidation!**

After you run `store_extraction.py` (the last step in sync.md), the system checks if it's been a while since you last ran consolidation.

**How it works:**
1. First time: Initializes timestamp to now (no reminder)
2. After 30 days: Shows helpful reminder at end of `store_extraction.py`
3. Run consolidation: Updates timestamp, reminder disappears
4. Repeat!

**Example reminder:**
```
================================================================================
[TIP] CONSOLIDATION RECOMMENDATION
================================================================================

It's been 31 days since you last ran consolidation analysis.

Running consolidation helps you:
  - Discover hub entities (central concepts in your knowledge)
  - Find clusters (groups of related topics)
  - Identify relationship patterns (how things connect)
  - Track knowledge evolution over time

Recommended command:
  {PYTHON_PATH} scripts/consolidate_knowledge.py --project {PROJECT} --store

This will:
  [OK] Analyze your current knowledge graph
  [OK] Store insights with cryptographic proofs
  [OK] Update the last-run timestamp
  [OK] Help you understand your knowledge structure

To disable these reminders, set "recommend_after_days": 0 in mem.config.json

================================================================================
```

**Configure reminder frequency:**
```json
{
  "consolidation": {
    "recommend_after_days": 30  // Change to 7, 15, 60, 90, etc.
  }
}
```

**Disable reminders:**
```json
{
  "consolidation": {
    "recommend_after_days": 0  // No reminders
  }
}
```

---

## Storage Strategy (Hybrid Approach)

**With `--store` flag:**
- Creates separate hub hash chain (not linked to conversation chain)
- Uses hash-of-hashes for compact fact verification (70 bytes vs 70 KB!)
- **Currently stores:** Hub detections only (clusters and patterns are display-only)
- Ready for OpenTimestamps integration

**With `--cleanup` flag:**
- Keeps 180 days of history in graph (configurable with `--archive-days`)
- Archives older hub detections to `hub_archive_{PROJECT}.jsonl`
- Deletes archived detections from graph (safe because archived with proofs!)
- Prevents bloated queries
- **Project-scoped:** Only affects the specified project's detections

**Benefits:**
- [OK] Fast queries (only recent data in graph)
- [OK] Full history preserved (in archive)
- [OK] Cryptographic proofs (hash chain + timestamps)
- [OK] Can delete safely (separate chain + archive)

---

## Tips

1. **Run periodically** - See how your knowledge evolves
2. **Lower thresholds** - Use `--min-hub-size 3` to see more
3. **Find transitive** - Use `--find-transitive` for deeper insights
4. **Compare over time** - Run weekly to see growth

---

## What's Next?

After consolidation, you might want to:
- **Visualize** - See clusters visually (`visualize.md`)
- **Query** - Explore specific hubs (`remember.md`)
- **Recall** - See when hubs were created (`recall.md`)

---

**Consolidation reveals the hidden structure of your knowledge!** [*]

