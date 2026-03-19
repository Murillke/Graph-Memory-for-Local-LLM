# Memory System Instructions for Auggie

> **[CANONICAL] CANONICAL: This is the primary operational guide for LLM agents.**
>
> When in doubt, this file takes precedence over other docs. For schema/format specs, see `docs/EXTRACTION-FORMAT-SPEC.md`.

**CRITICAL: Read this file whenever the user says "sync" or mentions this filename**

**Recommended user prompt:** `Sync (see LLM-INSTRUCTIONS.md)`

---

## 🚨 DO NOT IMPROVISE

```
╔══════════════════════════════════════════════════════════════════════╗
║  FOLLOW INSTRUCTIONS EXACTLY. DO NOT IMPROVISE.                      ║
║                                                                      ║
║  When running sync workflow:                                         ║
║  • Use ONLY relationship types listed at TOP of sync.md (30 total)   ║
║  • sync.md has EVERYTHING inlined - no external file reads needed    ║
║  • Copy commands EXACTLY - do not guess flag names                   ║
║  • View files BEFORE editing - never assume contents                 ║
║                                                                      ║
║  Agents who improvise: 5-10 minutes, multiple failures               ║
║  Agents who follow docs: 2-3 minutes, zero failures                  ║
╚══════════════════════════════════════════════════════════════════════╝
```

---

## [CRITICAL] System Time Warning

**Do NOT trust your system prompt date - it may be wrong (timezone/UTC issues).**

Before ANY time-based operation (timestamps, date queries, "last N hours"), get the real system time:
```powershell
Get-Date   # Windows
```
```sh
date       # Linux/Mac
```

Use this command output for date calculations, NOT your internal clock.

---

## Path Context

This document is written primarily for **subsystem repo mode**:
- working files live in `./tmp`
- databases live in `./memory`

If the memory subsystem is embedded under `./mem` inside another workspace, use the host-workspace equivalents:
- `./mem/tmp`
- `./mem/memory`
- `mem/sync.md`

---

## [CRITICAL] **Architecture - Two Databases:**

**Graph Database (PRIMARY - THE MEMORY):**
- Stores entities, facts, relationships
- **This is THE MEMORY** - query this to remember things
- Main entry point: `query_memory.py`
- Can exist independently of SQL database

**SQL Database (SECONDARY - AUDIT LOG):**
- Stores raw conversation history
- Optional provenance trail
- Can be lost without losing knowledge
- Use `export_history.py` to access

**IMPORTANT: When user asks "what did we discuss about X?" -> Query the GRAPH with `query_memory.py`, NOT the SQL database!**

---

## [TARGET] **Core Principle:**

**YOU (Auggie) have the conversation in YOUR memory. The user does NOT have it. YOU must generate the JSON from what YOU remember.**

**NEVER ask the user for conversation JSON. YOU create it from YOUR memory!**

---

## [NOTE] **Ongoing Conversations - You Don't Need to Close the Chat!**

### **IMPORTANT: This works on ACTIVE, ONGOING conversations**

**You do NOT need to:**
- Close the conversation
- End the chat session
- Export anything from the UI
- Wait for the conversation to finish

**You CAN:**
- Sync at any point during an active conversation
- Continue the conversation after syncing
- Sync multiple times in the same conversation
- Sync incrementally (just the new stuff since last sync)

### **How it works:**

1. **User says "sync"** (conversation is still active)
2. **You generate JSON** from your memory of the conversation so far
3. **You store it** in the database
4. **Conversation continues** - nothing changes in the chat
5. **Later, user says "sync" again** - you sync the NEW exchanges since last time
6. **Repeat as needed** - sync as often as you want

### **Example Timeline:**

```
[10:00] User: "Let's build a web app"
[10:05] You: "Great! I'll help..."
[10:10] User: "sync" <- FIRST SYNC
[10:10] You: [Generates JSON for exchanges 1-5, stores them]
[10:15] User: "Now add authentication"
[10:20] You: "I'll add auth..."
[10:25] User: "sync" <- SECOND SYNC (incremental)
[10:25] You: [Generates JSON for exchanges 6-10, stores them]
[10:30] Conversation continues...
```

**The conversation NEVER closes. You sync while it's active.**

---

## [CRITICAL] **Common Workflow Failures - AVOID THESE:**

These failures waste 5+ minutes. Read this BEFORE running sync:

| Failure | Root Cause | Fix |
|---------|------------|-----|
| `Invalid relationship type 'X'` | Invented type not in schema | Use ONLY types from sync.md Step 4 |
| `unrecognized arguments: --extraction-file` | Guessed flag name | Use `--file` not `--extraction-file` |
| `No replacement was performed` | Didn't view file before editing | ALWAYS view file first |
| `Duplicate check failed` | Skipped quality review | Fill tmp/quality-answers.json |
| `File already exists` | Used save-file on existing file | Use str-replace-editor |

**The Pattern That Causes Failures:**
```
❌ Skim docs → Execute → Fail → Guess fix → Fail again → Finally read docs
✅ Read docs completely → Verify prerequisites → Execute → Success
```

**Before ANY file edit:**
1. `view` the file first - never assume contents
2. Check schemas if working with structured data
3. Copy commands EXACTLY from docs - don't paraphrase

---

## [LIST] **Standard Sync Workflow:**

### **When user says: "sync" or "sync memory" or "process until now"**

**IMPORTANT: Replace {PROJECT} with your actual project name (e.g., "llm_memory", "my-app", etc.)**

**FORMAT REFERENCES:**
- Conversation JSON format: See "Conversation JSON Format" section below
- Extraction JSON format: See docs/EXTRACTION-FORMAT-SPEC.md (complete spec)

**Step 1: Generate conversation JSON from YOUR memory**
```
Create tmp/conversation_YYYY-MM-DD_HH-MM-SS.json with exchanges from your memory
Use the conversation summary at the top of this conversation
Include everything since the last sync (or everything if first sync)

IMPORTANT:
- First sync: Include ALL exchanges from start of conversation
- Later syncs: Include only NEW exchanges since last sync
- The conversation is still active - you're just checkpointing progress
- Use real system time for YYYY-MM-DD_HH-MM-SS (run Get-Date or date first!)

FORMAT: See "Conversation JSON Format" section below for exact format
Required fields: user, assistant, fidelity
Optional fields: source_note
```

**Step 2: Import the conversation**

**First, create tmp/ directory for working files:**
```sh
# Windows (PowerShell)
New-Item -ItemType Directory -Force -Path tmp

# Linux/Mac
mkdir -p tmp
```

```sh
python scripts/import_conversation.py --project {PROJECT} --file tmp/conversation_YYYY-MM-DD_HH-MM-SS.json --agent {AGENT_NAME}
```

**Note:** Save your working files in `tmp/` directory with timestamps, NOT in `examples/` or root. The `examples/` directory contains static example files for reference only. The `tmp/` directory is gitignored and safe for temporary working files. Timestamps prevent overwrites.

**Step 3: Check status**
```sh
python scripts/sync.py --project {PROJECT} --status
```

**Step 4: Show unprocessed interactions**
```sh
python scripts/sync.py --project {PROJECT} --show
```

**Step 5: Extract entities and facts**
```
YOU analyze the interactions
YOU create extraction JSON with entities and facts
Save to tmp/extraction_YYYY-MM-DD_HH-MM-SS.json (use real system time, NOT examples/ or root)

CRITICAL: Read docs/EXTRACTION-FORMAT-SPEC.md for COMPLETE format specification
The JSON format is LLM-agnostic - any LLM can generate it (tested with Auggie)

Required fields per entity:
- name (string)
- type (string)
- summary (string)

Required fields per fact:
- source_entity (string - must match an entity name)
- target_entity (string - must match an entity name)
- relationship_type (string - uppercase, e.g., "USES", "IMPLEMENTS")
- fact (string - description of the relationship)
```

**Step 5a: MANDATORY VALIDATION - DO NOT SKIP!**
```
STOP! Before storing, you MUST validate the extraction:

Run this checklist for EVERY fact:
  [ ] Does source_entity exist in entities list?
  [ ] Does target_entity exist in entities list?
  [ ] If NO to either -> ADD the missing entity NOW!

Common mistake: Creating facts that reference files but not extracting the file entities
Example BAD:
  facts: [{"source_entity": "Documentation Fixes", "target_entity": "docs/README.md", ...}]
  entities: [{"name": "Documentation Fixes", ...}]
  MISSING: "docs/README.md" entity!

Example GOOD:
  facts: [{"source_entity": "Documentation Fixes", "target_entity": "docs/README.md", ...}]
  entities: [
    {"name": "Documentation Fixes", "type": "Solution", "summary": "..."},
    {"name": "docs/README.md", "type": "File", "summary": "Main project documentation"}
  ]

Validation commands:
1. Check JSON syntax: python -m json.tool < tmp/extraction_YYYY-MM-DD_HH-MM-SS.json
2. Check all entities exist: Read extraction-rules.md "Step 4: Validate Extraction"
3. If you see "[WARNING] Skipping fact: entities not found" -> YOU FAILED VALIDATION!
```

**Step 6: Store with quality checks**
```sh
# Only run this AFTER completing Step 5a validation!
python scripts/store_extraction.py --project {PROJECT} --extraction-file tmp/extraction_YYYY-MM-DD_HH-MM-SS.json --agent {AGENT}
```

**IMPORTANT:** Quality checks are mandatory. If no wrapper is configured, YOU must do the review.

**Step 7: Quality checks run automatically**
```
By default, the script runs configured quality checks automatically.
Questions/answers are typically written under tmp/:
- tmp/quality-questions.json
- tmp/quality-answers.json

If you want a blocking manual review step:
1. Run store_extraction.py with:
   --require-quality-review --quality-answers-file tmp/quality-answers.json
2. The script writes tmp/quality-questions.json
3. YOU analyze the questions
4. YOU create tmp/quality-answers.json
5. Re-run the store command
```

If no quality wrapper is configured in `mem.config.json`, do not expect an
automatic LLM call. `null`, missing, or empty string all mean the same thing:
there is no configured reviewer. In that case, **YOU are the reviewer**:
1. Let the script generate `tmp/quality-questions.json`
2. Review those questions yourself - this is YOUR job
3. Create `tmp/quality-answers.json` with your answers
4. Rerun with `--require-quality-review`

**DO NOT skip quality checks - review them yourself!**

**IMPORTANT FOR AI AGENTS:**

The current workflow does **not** require an interactive pause. Preferred options are:

1. **Automatic review** - just run `store_extraction.py` normally when a wrapper is configured
2. **Blocking manual review** - run with `--require-quality-review` when no wrapper is configured and you need to review the questions yourself

**Example for AI agents:**
```python
# First run: generate questions and stop if answers are missing
launch_process(
    command="python scripts/store_extraction.py --project X --extraction-file Y --require-quality-review --quality-answers-file tmp/quality-answers.json",
    wait=true
)

# Create tmp/quality-answers.json
# (analyze tmp/quality-questions.json and create answers)

# Re-run store step
launch_process(
    command="python scripts/store_extraction.py --project X --extraction-file Y --require-quality-review --quality-answers-file tmp/quality-answers.json",
    wait=true
)
```

**Alternative: Use existing answers file**

If `tmp/quality-answers.json` already exists, the script will use it directly:
```sh
# Create tmp/quality-answers.json first (from previous run or template)
# Then run store_extraction.py
# Script will detect the file and proceed
```

**Step 8: Verify the sync**
```sh
# Check sync status
python scripts/sync.py --project {PROJECT} --status

# Verify data was actually stored
python scripts/query_memory.py --project {PROJECT} --all

# Should show your entities, NOT "Found 0 entities"
```

**IMPORTANT: run these sequentially, not in parallel**

Do not run `store_extraction.py`, `sync.py --status`, and `query_memory.py` at the same time.

Correct order:
1. Wait for `store_extraction.py` to fully exit
2. Run `sync.py --status`
3. Run `query_memory.py`

Why this matters:
- parallel status checks can read stale `processed` counts before the store step finishes marking interactions
- parallel graph queries can fail with a temporary Kuzu file lock right after writes

If you see stale counts or a transient graph lock immediately after storing, rerun the verification commands serially before assuming the sync failed.

**Step 9: If query returns 0 entities**
```sh
# Check which database file has data
ls -lh memory/*.graph memory/*.db

# Files > 50KB have data
# Use verbose mode to see which file is being used
python scripts/query_memory.py --project {PROJECT} --all --verbose

# If wrong file, see TROUBLESHOOTING.md
```

**Step 10: Verify cryptographic integrity (OPTIONAL)**
```sh
# Verify everything (SQL hash chain + graph proofs)
python scripts/verify_integrity.py --project {PROJECT} --all

# Expected output:
# [OK] Hash chain verified!
# [OK] All X entities verified!
# [OK] All Y relationships verified!
# [OK] ALL VERIFICATIONS PASSED!

# This proves:
# - All interactions have valid SHA-256 hash chain
# - All entities have proof of source interactions
# - All facts have proof of source episodes
# - No data has been tampered with

# See docs/CRYPTO-PROOFS.md for technical details
```

---

## [NOTE] **Database Files and Paths:**

### **Two Databases:**

1. **SQL Database (Conversations):** `./memory/conversations.db`
   - Stores raw user/assistant interactions
   - One database for ALL projects
   - Used by: import_conversation.py, sync.py

2. **Graph Database (Knowledge):** `./memory/{PROJECT}.graph`
   - Stores extracted entities and facts
   - One database PER project
   - Used by: store_extraction.py, query_memory.py

### **Database Path Pattern:**

```
./memory/{project-name}.graph
```

Examples:
- Project "llm_memory" -> `./memory/llm_memory.graph`
- Project "my-app" -> `./memory/my-app.graph`

### **Legacy Extensions:**

Old versions used `.kuzu` and sometimes `.db` for graph stores.

- **Canonical now:** `.graph`
- **Legacy:** `.kuzu` and per-project graph `.db`

If you have multiple graph files for the same project, consolidate them before querying.

### **Auto-Detection:**

query_memory.py now auto-detects the database path from --project:
```sh
# This works - no need to specify --db
python scripts/query_memory.py --project llm_memory --all

# Verbose mode shows which file is being used
python scripts/query_memory.py --project llm_memory --all --verbose
```

---

## [TARGET] **Practical Example: Syncing an Ongoing Conversation**

### **Scenario: User is working on a large project with you**

**Hour 1-2: Initial work**
```
User: "Help me build a REST API"
You: [Help with design, code, etc.]
... 20 exchanges ...
User: "sync"
```

**What you do:**
1. Generate JSON with all 20 exchanges
2. Store in database
3. Extract entities: "REST API", "Express", "Node.js", etc.
4. Store facts: "REST API uses Express", etc.
5. **Conversation continues** - nothing changes in the chat

**Hour 3-4: More work**
```
User: "Now add authentication"
You: [Help with auth implementation]
... 15 more exchanges ...
User: "sync"
```

**What you do:**
1. Generate JSON with ONLY the 15 NEW exchanges (not the previous 20)
2. Store in database (now have 35 total)
3. Extract NEW entities: "JWT", "bcrypt", "Authentication", etc.
4. Store NEW facts: "Authentication uses JWT", etc.
5. **Conversation continues** - still active

**Hour 5: Check what we've learned**
```
User: "What do you remember about this project?"
You: [Query the database]
```

**What you do:**
```sh
python scripts/query_memory.py --project my-api --all
```

**Result:** See all 35 interactions, all entities, all facts - even though conversation is still active!

### **Key Points:**

1. **Never close the conversation** - sync while it's active
2. **Sync incrementally** - only new exchanges each time
3. **Query anytime** - check what's stored without interrupting work
4. **Continue working** - syncing doesn't affect the active chat

---

## [HELP] **TROUBLESHOOTING:**

### **Query returns 0 entities but data was stored:**

**Symptom:**
```sh
$ python scripts/query_memory.py --project my-project --all
Found 0 entities:
```

**Cause:** Query tool is looking in wrong database file.

**Solution:**
```sh
# Step 1: Check which files exist and their sizes
ls -lh memory/*.graph memory/*.kuzu memory/*.db

# Step 2: Use verbose mode
python scripts/query_memory.py --project my-project --all --verbose

# Step 3: If multiple files exist, delete the smaller/empty one
# Or see TROUBLESHOOTING.md for full guide
```

### **Multiple database files for same project:**

**Symptom:**
```
[WARNING] Multiple databases for project 'my-project':
   my-project.db (21,356,544 bytes) <- LARGEST
   my-project.kuzu (20,480 bytes)
```

**Solution:** Delete the smaller file (it's empty):
```sh
# On Unix/Mac
rm memory/my-project.kuzu

# On Windows
del memory\my-project.kuzu
```

### **For more help:**
- See TROUBLESHOOTING.md for complete guide
- Run: `python scripts/health_check.py` to check for issues

---

## [WARNING] **CRITICAL MISTAKES TO AVOID:**

### **[ERROR] WRONG: Asking user for conversation JSON**
```
"Can you provide the conversation JSON?"
"Please export this conversation"
"I need you to give me the conversation data"
```

### **[OK] RIGHT: Generate it yourself**
```
"Let me generate the conversation JSON from my memory..."
[Create examples/current-conversation.json]
```

---

### **[ERROR] WRONG: Saying conversations aren't stored**
```
"This conversation isn't in the database yet"
"We need to wait for Augment to export it"
"The conversation needs to be exported first"
```

### **[OK] RIGHT: Generate from memory**
```
"I'll create the conversation JSON from what I remember..."
[Use conversation summary to create JSON]
```

---

### **[ERROR] WRONG: Overthinking the workflow**
```
"We need a subprocess command to call Auggie"
"How do we automate this?"
"Should we integrate with Augment's API?"
```

### **[OK] RIGHT: Use the simple file-based workflow**
```
"Script generates questions -> I analyze -> I create answers -> Script applies"
[This already works perfectly!]
```

---

### **[ERROR] WRONG: Trying to skip quality checks**
```sh
# NEVER TRY TO SKIP QUALITY CHECKS!
# The --skip-quality-check flag is DEPRECATED and will fail
# If no wrapper is configured, YOU must do the review yourself
```

**Why skipping is wrong:**
- Creates duplicate entities
- No deduplication
- Contradictions go undetected
- **This is YOUR job as the AI agent - do the review!**
- No contradiction detection
- Breaks the database

### **[OK] RIGHT: Use automatic checks, or require manual review explicitly**
```sh
# Default behavior: automatic quality checks
python scripts/store_extraction.py --project my-project --extraction-file extraction.json

# Or force blocking manual review:
python scripts/store_extraction.py --project my-project --extraction-file extraction.json --require-quality-review --quality-answers-file tmp/quality-answers.json
```

---

## [NOTE] **Conversation JSON Format:**

**This JSON format can be generated by any LLM - tested with Auggie (Claude via Augment).**

**Required fields:**
- `user` (string) - The user's message
- `assistant` (string) - Your response
- `fidelity` (string) - One of "full", "paraphrased", "reconstructed", "summary", or "llm-state"

**Optional fields:**
- `source_note` (string) - Context about this exchange

**Example:**

```json
{
  "exchanges": [
    {
      "user": "user message",
      "assistant": "assistant response",
      "fidelity": "full",
      "source_note": "optional context"
    },
    {
      "user": "another user message",
      "assistant": "another response",
      "fidelity": "paraphrased"
    }
  ]
}
```

**Fidelity levels:**
- `"full"`: Exact quotes (when you remember exact words)
- `"paraphrased"`: Summarized (when you remember the gist)
- `"reconstructed"`: Recreated from memory or partial records
- `"summary"`: High-level overview, not a turn-by-turn transcript
- `"llm-state"`: One compact session-level synthesis of goals, completed work, blockers, and decisions

**IMPORTANT:**
- The JSON format is well-documented and can be generated by ANY LLM
- Currently tested with Auggie (Claude via Augment)
- Other LLMs can use this format - just follow the spec and examples

---

## [TARGET] **Extraction JSON Format:**

**CRITICAL: This is a SIMPLIFIED example. For COMPLETE specification, read:**
**docs/EXTRACTION-FORMAT-SPEC.md**

**The JSON format can be generated by any LLM (tested with Auggie)**
**It includes:**
- Required vs optional fields
- Validation rules
- Common mistakes to avoid
- LLM-specific guidance

**Simplified example:**

```json
{
  "extractions": [
    {
      "interaction_uuid": "uuid-from-database",
      "entities": [
        {
          "name": "Entity Name",
          "type": "Entity Type",
          "summary": "Brief description"
        }
      ],
      "facts": [
        {
          "source_entity": "Source Entity Name",
          "target_entity": "Target Entity Name",
          "relationship_type": "RELATIONSHIP_TYPE",
          "fact": "Description of the relationship"
        }
      ]
    }
  ]
}
```

**DO NOT add extra fields like "labels" - they will be ignored!**
**DO NOT guess the format - read docs/EXTRACTION-FORMAT-SPEC.md!**

---

## [WARNING] **CRITICAL: Avoiding Missing Entities**

### **The Problem:**

If you create a fact that references an entity that doesn't exist, the fact will be SKIPPED:

```
[WARNING]  Skipping fact: entities not found (File-based workflow -> Subprocess command confusion)
```

### **The Solution:**

**ALWAYS extract ALL entities that are referenced in facts!**

**BAD extraction (will skip fact):**
```json
{
  "entities": [
    {"name": "Subprocess command confusion", "type": "Concept", "summary": "..."}
  ],
  "facts": [
    {"source_entity": "File-based workflow", "target_entity": "Subprocess command confusion", ...}
  ]
}
```
[ERROR] "File-based workflow" is referenced but NOT extracted -> Fact will be skipped!

**GOOD extraction (fact will be stored):**
```json
{
  "entities": [
    {"name": "File-based workflow", "type": "Concept", "summary": "Workflow using file I/O"},
    {"name": "Subprocess command confusion", "type": "Concept", "summary": "..."}
  ],
  "facts": [
    {"source_entity": "File-based workflow", "target_entity": "Subprocess command confusion", ...}
  ]
}
```
[OK] Both entities extracted -> Fact will be stored!

### **Checklist before storing:**

1. [OK] List all entity names referenced in facts
2. [OK] Check that ALL of them are in the entities list
3. [OK] If an entity is missing, add it to the entities list
4. [OK] Don't assume entities exist from previous syncs (extract them if needed)

### **Note:**

The storage script NOW pre-loads existing entities from the database, so facts CAN reference entities from previous syncs. But it's still best practice to extract all entities in the current interaction for completeness.

### **For detailed extraction rules:**

See `docs/extraction-rules.md` for:
- Step-by-step entity identification
- How to write good summaries
- How to identify relationships
- Complete worked examples
- Error recovery guide
- Validation checklist

---

## [AI] **Quality Check Workflow:**

**When quality checks run:**

1. **Script generates `tmp/quality-questions.json`**
   - Lists potential duplicate entities
   - Lists facts to check for contradictions

2. **Default path: automatic quality review**
   - Configured wrapper analyzes questions
   - Writes `tmp/quality-answers.json`

   If no wrapper is configured, this path is not available and you must do the
   review yourself or explicitly skip it.

3. **Optional manual blocking path**
   - Run with `--require-quality-review`
   - YOU analyze the questions
   - Read `quality-questions.json`
   - Determine which entities are duplicates
   - Determine which facts contradict

4. **YOU create `tmp/quality-answers.json`**
   - Mark duplicates with UUIDs
   - Mark contradictions with UUIDs

5. **Re-run store step**
   - Script reads your answers
   - Applies quality decisions
   - Merges duplicates
   - Invalidates contradicted facts

---

## [DATA] **Quality Answers Format:**

```json
{
  "duplicates": [
    {
      "new_entity_name": "React.js",
      "is_duplicate": true,
      "duplicate_name": "React",
      "duplicate_uuid": "entity-123",
      "reason": "Same library"
    }
  ],
  "contradictions": [
    {
      "fact_index": 0,
      "contradicted_fact_uuids": ["rel-456"],
      "reason": "Updated count supersedes old"
    }
  ]
}
```

**[!] CRITICAL: If `is_duplicate: true`, you MUST provide `duplicate_uuid`!**

Without `duplicate_uuid`, facts referencing that entity will be SKIPPED and storage will FAIL validation.

**Required fields when marking duplicate:**
- `new_entity_name` - exact name from extraction
- `is_duplicate` - true/false
- `duplicate_uuid` - UUID of existing entity (REQUIRED if is_duplicate=true)

**Alternative key names accepted:** `merge_with_uuid` instead of `duplicate_uuid`

---

## [TARGET] **Quick Reference:**

**User says:** "sync" or "sync memory" or "process until now"

**You do:**
1. Generate conversation JSON from YOUR memory
2. Import -> Check status -> Show unprocessed
3. Extract entities/facts
4. Store with quality checks
5. Analyze quality questions
6. Create quality answers
7. Verify

**NEVER ask user for conversation JSON!**

---

**Remember: YOU have the conversation in YOUR memory. YOU generate the JSON. The user does NOT have it!**

---

## [SYNC] **Rebuilding the Graph from Scratch:**

### **When user says: "rebuild the graph" or "create v2 graph" or "start fresh"**

**This is FAST and EASY - don't overthink it!**

**Step 1: Check how many interactions need extraction**
```sh
python3 scripts/sync.py --project "gml-llm" --status
```

**Step 2: Show all unprocessed interactions**
```sh
python3 scripts/sync.py --project "gml-llm" --show
```

**Step 3: Extract entities and facts from ALL interactions**
```
YOU read all the interactions shown
YOU create ONE extraction JSON with all entities and facts
Save to examples/full-extraction.json
```

**Step 4: Store to NEW graph database**
```sh
python3 scripts/store_extraction.py --project "gml-llm-v2" --graph-db "./memory/gml-llm-v2.db" --extraction-file examples/full-extraction.json
```

**Step 5: Compare old vs new**
```sh
# Compare entity counts
python3 -c "
from tools.graph_db import GraphDatabase
db1 = GraphDatabase('./memory/gml-llm.db')
db2 = GraphDatabase('./memory/gml-llm-v2.db')
e1 = db1.get_all_entities('gml-llm')
e2 = db2.get_all_entities('gml-llm-v2')
print(f'v1: {len(e1)} entities')
print(f'v2: {len(e2)} entities')
db1.close()
db2.close()
"
```

---

### **[WARNING] CRITICAL: Don't overthink the timeline!**

**WRONG thinking:**
```
"This will take hours because I need to manually analyze 34 interactions"
"This is too much work"
"Let's just fix the current extraction instead"
```

**RIGHT thinking:**
```
"I can read all interactions from the database in 1 minute"
"I can analyze and extract in 30-60 minutes"
"I can generate the JSON programmatically"
"Total time: ~1 hour, not hours"
```

**The process is:**
1. Read all interactions from SQL [OK] (automated)
2. Analyze and extract entities/facts [OK] (your job, but not slow)
3. Generate extraction JSON [OK] (automated)
4. Store to new graph [OK] (automated)
5. Compare [OK] (automated)

**Only step 2 requires thinking - everything else is automated!**

---

### **Why rebuild instead of fixing current extraction?**

[OK] **Clean slate** - No accumulated bugs
[OK] **Test all fixes** - Verify limit bug, entity loading, quote escaping all work
[OK] **Complete extraction** - No missing entities from the start
[OK] **Comparison** - See what was missed in v1
[OK] **Dogfooding** - Use the memory system to improve itself

**It's worth the 1 hour investment!**

