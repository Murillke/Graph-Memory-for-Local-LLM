# Stats - Memory Statistics

**Get quantitative insights about your knowledge graph**

[!] **BEFORE STARTING: Check COMMANDS.md to see if a different command better fits the user's request!**

---

## [BOT] Config First

**Read `mem.config.json` before running any command:**
- Use `python_path` value for `{PYTHON_PATH}`
- Use `project_name` value for `{PROJECT}`
- Do not guess or substitute different values

**Get system time first for date-based comparisons:**
```sh
date
```

---

## LLM Instructions

When the user asks for stats or metrics:
1. Use `query_memory.py --all` to count entities
2. Use `consolidate_knowledge.py` to find hubs/clusters
3. Calculate growth by comparing date ranges with `recall.py`
4. Summarize key metrics

### Path Context

**If this repo is a submodule (host mode):**
- Working from: `{host_workspace}/mem/`
- Config file: `./mem.config.json`

**If this repo is standalone:**
- Working from repo root
- Config file: `./mem.config.json`

### Prerequisites

1. [OK] Read `mem.config.json` for `python_path` and `project_name`
2. [OK] Get real system time (for date comparisons)
3. [OK] Memory database exists

---

## Quick Start

### **Count all entities:**
```sh
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --all
```

### **Find hubs and clusters:**
```sh
{PYTHON_PATH} scripts/consolidate_knowledge.py --project {PROJECT}
```

### **Export conversation history:**
```sh
{PYTHON_PATH} scripts/export_history.py --project {PROJECT}
```

---

## What You Get

### **Entity Count**
```sh
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --all
```

Shows all entities with their types and summaries.

### **Hubs (Highly Connected Entities)**
```sh
{PYTHON_PATH} scripts/consolidate_knowledge.py --project {PROJECT}
```

Shows:
- Hub entities (5+ relationships)
- Clusters (5+ densely connected entities)
- Relationship patterns
- Transitive chains

### **Growth Over Time**

**Get real system time first**, then use `recall.py` with different date ranges:
```sh
# January
{PYTHON_PATH} scripts/recall.py --project {PROJECT} --start 2026-01-01 --end 2026-01-31

# February
{PYTHON_PATH} scripts/recall.py --project {PROJECT} --start 2026-02-01 --end 2026-02-28

# March
{PYTHON_PATH} scripts/recall.py --project {PROJECT} --start 2026-03-01 --end 2026-03-31
```

Count entities in each month to see growth.

---

## Example Stats Summary

**Total Entities:** 150
**Total Facts:** 200
**Total Conversations:** 25

**Top Hubs:**
1. React (15 relationships)
2. Python (12 relationships)
3. JavaScript (10 relationships)

**Entity Types:**
- Technology: 60 (40%)
- Concept: 45 (30%)
- Tool: 30 (20%)
- Other: 15 (10%)

**Growth:**
- Jan: 50 entities
- Feb: 75 entities (+25)
- Mar: 150 entities (+75)

---

## Tips

[TIP] **Use stats to:**
- Monitor knowledge growth
- Find central concepts (hubs)
- Track conversation frequency
- Identify knowledge gaps

[TIP] **Combine with other commands:**
- `stats.md` -> See overall metrics
- `consolidate.md` -> Find structural patterns
- `timeline.md` -> See growth over time
- `visualize.md` -> Explore graph visually

---

## Troubleshooting

**"No entities found"**
- Check project name matches what you used during import
- Verify memory database exists in `memory/{PROJECT}.graph`

**"Date range returns nothing"**
- Verify you're using real system time, not system prompt date
- Check date format: `YYYY-MM-DD` or `YYYY-MM-DDTHH:MM:SS`

---

## Success Criteria

- [OK] Entity count returns > 0
- [OK] Hub analysis shows top connected entities
- [OK] Date range queries return expected results

---

## Next Steps

After viewing stats:
- Use `consolidate.md` to find hubs/clusters
- Use `timeline.md` to see evolution
- Use `visualize.md` to explore graph
