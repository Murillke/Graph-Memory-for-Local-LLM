# visualize.md - Visualize Knowledge Graph

> **[EXPERIMENTAL]** D3.js-based graph viewer. Works but limited features. See `docs/STATUS.md` for details.

[!] **BEFORE STARTING: Check COMMANDS.md to see if a different command better fits the user's request!**

---

## [BOT] Config First

**Read `mem.config.json` before running any command:**
- Use `python_path` value for `{PYTHON_PATH}`
- Use `project_name` value for `{PROJECT}`
- Do not guess or substitute different values

---

## LLM Instructions

**If you have been instructed to "follow visualize.md", "execute visualize.md", or "run visualize.md", you are expected to:**

1. **Export the graph to JSON** using export_graph.py
   - **IMPORTANT:** For entity-centered exports, ALWAYS use `--center-file` instead of `--center`
   - **Steps:**
     1. Create `tmp/center.txt` with the entity name (one line)
     2. Run: `{PYTHON_PATH} scripts/export_graph.py --project {PROJECT} --output OUTPUT.json --center-file tmp/center.txt --depth N`
   - This avoids PowerShell/shell quote issues with entity names containing spaces
2. **If running in headless/sandboxed environment** (no browser):
   - Export to JSON only - do NOT attempt to open browser
   - Tell user: "JSON exported to {output}. Open visualize_graph.html manually in your browser."
3. **If running interactively** (has browser):
   - Guide user to open visualize_graph.html
   - Guide them to load the exported JSON file

**This is a workflow to be followed by an AI agent.**

### Path Context

**If this repo is a submodule (host mode):**
- Working from: `{host_workspace}/mem/`
- Config file: `./mem.config.json`
- Visualizer: `./visualize_graph.html`

**If this repo is standalone:**
- Working from repo root
- Config file: `./mem.config.json`
- Visualizer: `./visualize_graph.html`

### Prerequisites

1. [OK] Read `mem.config.json` for `python_path` and `project_name`
2. [OK] Graph database exists (`memory/{project}.graph/`)
3. [OK] `tmp/` directory exists for output

### Constrained/Headless Environment

[!] **If you are a sandboxed agent (Codex, CI, etc.) that cannot open a browser:**

- **DO:** Export the JSON file
- **DO NOT:** Run `start`, `xdg-open`, or `open` commands
- **TELL USER:** "Graph exported to {output}.json. Open visualize_graph.html in your browser and load the JSON file."

---

## [*] Graph Visualization Workflow

### Step 1: Export Graph to JSON

**[BOT] LLM: Read python_path from mem.config.json and use it in the command below!**

**Command pattern:**
```sh
{PYTHON_PATH} scripts/export_graph.py --project {PROJECT} --output graph.json
```

**With limit (recommended for large graphs):**
```sh
{PYTHON_PATH} scripts/export_graph.py --project {PROJECT} --output graph.json --limit 100
```

Use values from `mem.config.json` for `{PROJECT}` and `{PYTHON_PATH}`.

**Example:**
```sh
{PYTHON_PATH} scripts/export_graph.py --project {PROJECT} --output graph.json --limit 50
```

**Example (Entity-centered with file - RECOMMENDED for AI agents):**
```sh
# Step 1: Create tmp/center.txt with entity name (use agent's file tools)
# Step 2: Export centered graph
{PYTHON_PATH} scripts/export_graph.py --project {PROJECT} --output centered.json --center-file tmp/center.txt --depth 2
```

**Why use --center-file?**
- [OK] No quote/escaping issues
- [OK] Works on all platforms
- [OK] Simpler for AI agents to generate
- [OK] Handles entity names with spaces/special characters

**Output:**
- Creates `graph.json` with nodes and links
- Shows entity count and relationship count

---

### Smart Export Options (NEW!)

For large graphs, use filtering to export only what you need:

**Time-based:**
```sh
# Last 7 days only
{PYTHON_PATH} scripts/export_graph.py --project {PROJECT} --output recent.json --last-days 7

# Date range
{PYTHON_PATH} scripts/export_graph.py --project {PROJECT} --output march.json --start 2026-03-01 --end 2026-03-08
```

**Entity-centered (explore connections):**
```sh
# Create tmp/center.txt with entity name (use agent's file tools, not echo)
# Then export centered graph:
{PYTHON_PATH} scripts/export_graph.py --project {PROJECT} --output centered.json --center-file tmp/center.txt --depth 2

# Direct connections only
{PYTHON_PATH} scripts/export_graph.py --project {PROJECT} --output centered_direct.json --center-file tmp/center.txt --depth 1
```

**Note:** Using `--center-file` avoids shell quote issues with entity names containing spaces.

**Type filtering:**
```sh
# Only specific types
{PYTHON_PATH} scripts/export_graph.py --project {PROJECT} --output tech.json --types Technology,Feature

# Exclude types
{PYTHON_PATH} scripts/export_graph.py --project {PROJECT} --output no_tasks.json --exclude-types Task
```

**Document-based:**
```sh
# Only entities from imported documents
{PYTHON_PATH} scripts/export_graph.py --project {PROJECT} --output docs.json --from-documents
```

**Combined filters (use file-based --center-file):**
```sh
# Create tmp/center.txt with entity name, then:
{PYTHON_PATH} scripts/export_graph.py --project {PROJECT} --output filtered.json --last-days 7 --center-file tmp/center.txt --depth 2
```

---

### Step 2: Open Visualization in Browser

[!] **HEADLESS/SANDBOXED AGENTS: Skip this step. Tell user to open manually.**

**Simply open the HTML file (platform-specific):**
- **Windows:** `start visualize_graph.html`
- **Linux:** `xdg-open visualize_graph.html`
- **Mac:** `open visualize_graph.html`

**Or just double-click `visualize_graph.html` in your file explorer!**

---

### Step 3: Load Your Graph

**In the browser:**

1. Click "Choose File" button
2. Select `graph.json`
3. Graph will render!

**Or click "Load Sample Data" to see a demo first.**

---

## [*] Features

### **Interactive Graph:**
- [*]️ **Drag nodes** - Click and drag to reposition
- [*] **Hover for details** - Hover over nodes/links to see info
- [*] **Color-coded** - Different colors for different entity types
- [*] **Force-directed layout** - Nodes automatically organize
- [*] **Filter** - Show only specific nodes with simple queries

### **What You See:**
- **Nodes (circles)** - Entities in your knowledge graph
- **Links (lines)** - Relationships between entities
- **Labels** - Entity names
- **Tooltips** - Detailed info on hover

### **Filter Examples:**

Show only specific nodes or relationships using simple queries:

**Filter by Entity:**
```
type:Technology          - Show only Technology entities
name:Python              - Show entities with "Python" in name
summary:database         - Show entities with "database" in summary
Python OR NumPy          - Show entities matching either term
type:Feature OR name:SQL - Combine filters with OR
```

**Filter by Relationship:**
```
rel:USES                 - Show only USES relationships (and connected nodes)
relationship:ENABLES     - Show only ENABLES relationships
rel:REQUIRES             - Show only REQUIRES relationships
rel:PART_OF OR rel:USES  - Show multiple relationship types
```

**How to use:**
1. Type filter in the text box
2. Click "Apply Filter"
3. Click "Clear Filter" to see all nodes again

**Note:** When filtering by relationship, you see only the nodes connected by those relationships!

---

## [TIP] Tips

### **Large Graphs:**
Use `--limit` to export only a subset:
```sh
{PYTHON_PATH} scripts/export_graph.py --project {PROJECT} --output graph.json --limit 100
```

### **Focus on Specific Entities:**
Export only entities related to a topic (future feature - for now use limit)

### **Export Multiple Projects:**
```sh
{PYTHON_PATH} scripts/export_graph.py --project {PROJECT_1} --output graph1.json
{PYTHON_PATH} scripts/export_graph.py --project {PROJECT_2} --output graph2.json
```

Then load different graphs in the visualizer!

---

## [*] Customization

### **Edit visualize_graph.html to:**
- Change colors
- Adjust node sizes
- Modify force simulation parameters
- Add filters
- Export to image

**It's just HTML/JavaScript - customize as you like!**

---

## [*] Example Output

**Graph JSON structure:**
```json
{
  "nodes": [
    {
      "id": "uuid-123",
      "name": "Python",
      "type": "Technology",
      "summary": "Programming language",
      "group": 1
    }
  ],
  "links": [
    {
      "source": "uuid-123",
      "target": "uuid-456",
      "type": "USES",
      "fact": "Python uses NumPy"
    }
  ],
  "metadata": {
    "project": "my_project",
    "node_count": 50,
    "link_count": 31
  }
}
```

---

## [*] Quick Start

**Read `mem.config.json` for `python_path` and `project_name`, then:**
```sh
# Export
{PYTHON_PATH} scripts/export_graph.py --project {PROJECT} --output graph.json --limit 50

# Open in browser (see Step 2 above for platform-specific commands)
# Load graph.json in browser
```

**That's it!**

---

## Troubleshooting

**"Graph file is empty or has no nodes"**
- Check that entities exist: `{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --all`
- Try removing `--limit` to see all entities

**"Browser doesn't open" (headless environment)**
- This is expected in sandboxed/CI environments
- Manually open `visualize_graph.html` in your local browser
- Load the exported JSON file

**"JSON file not loading in visualizer"**
- Check JSON syntax: `{PYTHON_PATH} -m json.tool < graph.json`
- Ensure file has both `nodes` and `links` arrays

---

## Success Criteria

- [OK] JSON file created with nodes and links
- [OK] Visualizer loads and renders nodes
- [OK] Nodes are draggable and hoverable
- [OK] Filter works to show subsets

---

**See [WORKFLOWS.md](WORKFLOWS.md) for more usage patterns ->**

