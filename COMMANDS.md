# COMMANDS.md - Command Reference Index

**[*] IMPORTANT: Before creating custom scripts or tools, CHECK THIS FILE to see if an existing command handles your need!**

---

## [BOT] For AI Agents

**When the user asks a question or makes a request, FIRST check this index to see if an existing command file handles it.**

**Examples:**
- "How many Bitcoin attestations?" -> **verify.md**
- "What do we know about X?" -> **recall.md** or **search.md**
- "Save this conversation" -> **dump.md** or **sync.md**
- "Show me tasks" -> **tasks.md**
- "Import a document" -> **import-documents.md**

**DO NOT create custom scripts if an existing command exists!**

**Current workflow rules to remember while using this index:**
- Read `mem.config.json` first and use its configured `python_path` / `project_name`
- Prefer workflow docs over ad hoc command construction
- Use helper-file / `--*-file` inputs where the workflow requires them
- For sync/import flows, use `--constrained-environment` unless outbound network access is positively confirmed

---

## [*] Command Categories

### **Memory Operations**

**sync.md** - Full Pipeline (Dump + Extract)
- Saves conversation to SQL with OpenTimestamps
- Extracts entities/facts to graph database
- Use when: You want to do everything at once
- Time: ~2 minutes

**dump.md** - Quick Conversation Save
- Saves conversation to SQL with OpenTimestamps
- Fast exit, extraction happens later
- Use when: Active instance needs to exit quickly
- Time: ~10 seconds

**extract.md** - Knowledge Extraction
- Extracts entities/facts from pending conversations
- Stores in graph database
- Use when: After dump.md, background processing
- Time: ~2 minutes

---

### **Query & Search**

**recall.md** - Query Memory
- Query entities by name, type, or relationship
- Get facts about entities
- Use when: "What do we know about X?"
- Examples: recall.md with entity name

**search.md** - Search Entities
- Search across all entities by text
- Filter by type or label
- Use when: "Find all entities related to X"
- Examples: search.md with search query

**search-external.md** - Search Across All Projects
- Search multiple graph databases
- Cross-project entity discovery
- Use when: "Search all projects for X"

**remember-external.md** - Remember Across All Projects
- Query entities across multiple projects
- Use when: Cross-project queries

---

### **Verification & Integrity**

**verify.md** - Verify Bitcoin Attestations
- Check Bitcoin attestations status
- Upgrade timestamps to get Bitcoin proofs
- Verify integrity of stored data
- Use when: "How many Bitcoin attestations?", "Verify timestamps"
- **IMPORTANT: Use this instead of creating custom attestation scripts!**

---

### **Document Management**

**import-documents.md** - Import External Documents
- Import PDFs, Word docs, text files
- Version tracking with hash deduplication
- Optional AI extraction
- Use when: "Import this document", "Add this PDF to memory"

**import.md** - Import Project
- Import entire project into memory system
- Use when: Setting up new project

---

### **Task Management**

**tasks.md** - Task Management
- Show current tasks
- Mark tasks complete/invalid
- Add and edit tasks, blockers, and parent/subtask links
- Use when: "Show tasks", "Mark task complete", "Edit task", "Set blocker"

---

### **Visualization**

**visualize.md** - Visualize Knowledge Graph
- Export graph to JSON
- Interactive browser visualization
- Smart filtering (time, entity, type, document)
- Use when: "Show me the graph", "Visualize connections"

---

### **Consolidation & Analysis**

**consolidate.md** - Find Patterns
- Find hubs (highly connected entities)
- Detect clusters
- Identify patterns
- Use when: "Find important entities", "Show me hubs"

---

### **Export**

**export.md** - Export Data
- Export conversations, entities, facts
- Use when: "Export my data", "Backup memory"

---

### **Initialization, Status & Configuration**

**init.md** - Initialize Memory System
- Set up new memory system
- Create databases
- Use when: First time setup

**status.md** - System Status
- Show database statistics
- Check system health
- Use when: "Show me stats", "How much data do we have?"

**config.md** - Project Configuration
- View and edit settings (JSON config + SQL metadata)
- Configure backup repo for encrypted backups
- Check env overrides
- Use when: "Show settings", "Set backup repo", "What's my config?"

---

## [*] Quick Decision Tree

**User asks about:**
- Bitcoin attestations? -> **verify.md**
- What we know about X? -> **recall.md** or **search.md**
- Save conversation? -> **dump.md** (fast) or **sync.md** (full)
- Tasks? -> **tasks.md**
- Import document? -> **import-documents.md**
- Visualize graph? -> **visualize.md**
- Find patterns? -> **consolidate.md**
- System stats? -> **status.md**
- Verify data? -> **verify.md**
- Settings / config? -> **config.md**

---

## [!] IMPORTANT REMINDERS

1. **ALWAYS check this file before creating custom scripts!**
2. **Use existing commands when they exist!**
3. **Only create custom solutions when NO command exists!**
4. **When in doubt, check COMMANDS.md!**
5. **Workflow docs define the approved command contract; do not prefer deprecated direct flags over helper-file flows.**

---

**This file is your command reference - use it!** [*]

