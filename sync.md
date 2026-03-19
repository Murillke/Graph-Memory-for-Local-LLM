# sync.md - Sync Conversation to Memory

**What this does:** Stores conversation + extracts entities/facts to memory graph.

---

## 🚨 [BOT] CRITICAL: DO NOT IMPROVISE

```
╔══════════════════════════════════════════════════════════════════════╗
║  FOLLOW THESE INSTRUCTIONS EXACTLY. DO NOT IMPROVISE.                ║
║                                                                      ║
║  ❌ DO NOT invent relationship types - use ONLY the list below       ║
║  ❌ DO NOT guess command flags - copy EXACTLY from this doc          ║
║                                                                      ║
║  📋 FORMAT: Setup command output JSON is single-line; editable       ║
║     temp templates are multiline JSON.                              ║
║                                                                      ║
║  Every agent that improvised wasted 5+ minutes on failures.          ║
║  Every agent that followed instructions finished in 2-3 minutes.     ║
╚══════════════════════════════════════════════════════════════════════╝
```

---

## ⚠️ [BOT] Pre-Flight Checklist

**Before starting, confirm you understand:**

- [ ] **Read ALL steps 0-7** before executing any command
- [ ] **Relationship types** - use ONLY the 30 types listed directly above
- [ ] **Quality review in Step 6** is REQUIRED - you cannot skip it
- [ ] **Edit files in place** using str-replace-editor, NOT save-file
- [ ] **View files before editing** - never assume file contents

**If you skip this checklist, expect failures.**

**Time estimate:** 2-3 minutes if you follow instructions. 10+ minutes if you improvise.

---

## 📋 ALLOWED RELATIONSHIP TYPES

**DO NOT INVENT NEW TYPES. Validation will fail.**

Relationship types are embedded in extraction templates via `_help_relationship_types`.
See the categorized list in Step 4 when filling the extraction file.

---

## [BOT] Config First

**Read `mem.config.json` before running any command:**
- Use `python_path` value for `{PYTHON_PATH}`
- Use `project_name` value for `{PROJECT}`
- Do not guess or substitute different values

---

## Quick Reference

**Step 0 (REQUIRED):** Run setup script to prepare all temp files:
```sh
{PYTHON_PATH} scripts/prepare_sync_files.py --project {PROJECT} --json
```

This returns:
```json
{
  "timestamp": "2026-03-13_15-11-31",
  "conversation_file": "tmp/conversation_2026-03-13_15-11-31.json",
  "extraction_file": "tmp/extraction_2026-03-13_15-11-31.json",
  "entity_file": "tmp/entity.txt",
  "quality_answers_file": "tmp/quality-answers.json",
  "archive_dir": "tmp/old/2026-03-13_15-11-31",
  "status": "ready"
}
```

**Use these paths for all subsequent steps.**
The command output above is single-line JSON for machine use.
The generated editable temp files are multiline JSON on disk.

**[!] CRITICAL RULES:**
- **Edit prep-created files in place** - Do NOT recreate with save-file
- **Use str-replace-editor** - The prep script already created valid skeletons
- **Editable temp files are multiline JSON** - match the actual block on disk, not a guessed one-line shape
- **If JSON gets corrupted** - Re-run prepare_sync_files.py to get fresh skeletons
- **Decide network mode before import** - If network access is unavailable, restricted, or unknown, use `--constrained-environment`
- **Direct query/name flags disabled by default** - workflow-facing scripts now reject deprecated direct query/name flags unless `MEM_ALLOW_DIRECT_INPUT=1` is explicitly set for legacy/manual use

**Hot path (7 steps):**
```
0. Prepare files                -> prepare_sync_files.py --json (REQUIRED FIRST)
1. Fill conversation file       -> use str-replace-editor on conversation_file
2. Import summary               -> import_summary.py (+ constrained flag if network is unavailable/unknown)
3. Get UUID                     -> USE IMPORT OUTPUT (or get_latest_uuid.py fallback)
4. Fill extraction file         -> use str-replace-editor on extraction_file
5. Validate extraction          -> validate_extraction.py (REQUIRED)
6. Store with quality review    -> store_extraction.py (REQUIRED)
7. Verify                       -> query_memory.py --last 3
```

---

## Step 0: Prepare Files (REQUIRED FIRST)

```sh
{PYTHON_PATH} scripts/prepare_sync_files.py --project {PROJECT} --json
```

**Save the output.** Use these exact paths for all steps. This:
- Gets real system timestamp
- Archives prior sync JSON artifacts into `tmp/old/{timestamp}/`
- Creates empty conversation/extraction files with correct templates
- Resets helper files (entity.txt, search.txt, quality-answers.json)
- Guarantees UTF-8 encoding

---

## Step 1: Fill Conversation File

**Edit the conversation file** using str-replace-editor. Fill the `summary` object with your session summary:
```json
{
  "summary": {
    "session_id": "sync-abc123",
    "timestamp": "2026-03-18T12:00:00Z",
    "intent": "What the user wanted",
    "work_attempted": ["What the agent tried or did"],
    "outcomes": [{"type": "success", "description": "What happened"}],
    "fidelity": "summary"
  }
}
```

**Fidelity values:** `summary`, `paraphrased`, `reconstructed`, `llm-state`

`llm-state` is optional and should usually appear at most once per sync/session. Use it for one compact high-signal session synthesis when that is more accurate than a normal summary entry.

---

## Step 2: Import Summary

**Choose the import mode before running this step:**

- **Constrained mode (PREFERRED for agents):** use this when network access is unavailable, restricted, sandboxed, or unknown
- **Network mode:** use plain import only when you know outbound OpenTimestamps submission is allowed

**Constrained mode command:**
```sh
{PYTHON_PATH} scripts/import_summary.py --project {PROJECT} --file {CONVERSATION_FILE} --constrained-environment
```

**Network mode command:**
```sh
{PYTHON_PATH} scripts/import_summary.py --project {PROJECT} --file {CONVERSATION_FILE}
```

**Optional flags:**
- `--agent auggie` - Record which agent imported (or set LLM_AGENT_NAME env var)

**Rule:** If you are an autonomous agent and you have not positively confirmed outbound network access, use `--constrained-environment`.

---

## Step 3: Get Interaction UUID

**PREFERRED:** Use the UUID from Step 2 import output directly:
```
[OK] [1/1] Imported summary
   UUID: uuid-abc123def456    <-- USE THIS IN EXTRACTION FILE
```

**FALLBACK:** If you missed the import output:
```sh
{PYTHON_PATH} scripts/get_latest_uuid.py --project {PROJECT}
```

**⚠️ Important:** `get_latest_uuid.py` returns UNPROCESSED interactions only (by default).
- If you already ran `store_extraction.py`, those UUIDs won't appear
- Use `--all` to see processed interactions (legacy behavior)
- Best practice: capture UUID from import output to avoid this issue

---

## Step 4: Fill Extraction File

**Edit the extraction file** using str-replace-editor. Replace `"extractions": []` with your content.

**⚠️ TWO RULES THAT CAUSE 90% OF VALIDATION FAILURES:**

### Rule 1: Every entity in facts MUST exist in entities list

**Before writing any fact, enumerate ALL participants:**
- Source entity → must be in entities list
- Target entity → must be in entities list

**Common entity types (canonical):**
- `Feature`, `Bug`, `Task`, `Issue`, `Fix` - work items
- `File`, `Tool`, `Document`, `Config`, `Template` - artifacts
- `Procedure`, `Pattern`, `Principle` - methodologies
- `Event`, `Concept` - things that happened or abstract ideas
- `Technology`, `Platform`, `Service`, `API`, `Database` - systems

**Deprecated types (normalize automatically):**
- `Script` → `File`, `Configuration` → `Config`, `Process` → `Procedure`

**Common mistake:**
```json
// ❌ BAD: Facts reference "sync.md" but it's not in entities list
"facts": [{"source_entity": "Agent", "target_entity": "sync.md", ...}]
"entities": [{"name": "Agent", ...}]  // Missing sync.md!

// ✅ GOOD: All fact participants are in entities list
"facts": [{"source_entity": "Agent", "target_entity": "sync.md", ...}]
"entities": [
  {"name": "Agent", "type": "Concept", "summary": "..."},
  {"name": "sync.md", "type": "File", "summary": "Sync workflow documentation"}
]
```

### Rule 2: Only use relationship types from `_help_relationship_types` in the template

**The extraction template includes `_help_relationship_types` - use ONLY types listed there:**
- **Dependency:** `USES`, `DEPENDS_ON`, `BUILT_WITH`, `WRITTEN_IN`, `SUPPORTS`, `NOT_SUPPORTS`
- **Structure:** `IMPLEMENTS`, `CONTAINS`, `PART_OF`, `LOCATED_AT`
- **Lifecycle:** `CREATES`, `SUPERSEDES`
- **Documentation:** `DOCUMENTS`, `REFERENCES`
- **Causation:** `CAUSES`, `RESOLVES`
- **Security:** `VULNERABLE_TO`, `NOT_VULNERABLE_TO`, `MITIGATES`, `COMPROMISES`
- **Decisions:** `PREFERS`, `DECIDED`
- **Procedural:** `PRECEDES`, `RUNS`, `EXECUTES`, `HAS_STEP_RUN`, `RUNS_STEP`, `EXTRACTED_FROM`
- **Generic:** `RELATED_TO`, `SIMILAR_TO`

Synonyms are auto-normalized (e.g., `REQUIRES` → `DEPENDS_ON`, `LED_TO` → `CAUSES`).

---

**Example extraction file** (note: `_help_relationship_types` is in template, just fill `extractions`):
```json
{
  "project_name": "{PROJECT}",
  "extraction_version": "v1.0.0",
  "extraction_commit": "session-2026-03-13",
  "_help_relationship_types": { ... },
  "extractions": [
    {
      "interaction_uuid": "uuid-from-step-3",
      "entities": [
        {"name": "Entity Name", "type": "Concept", "summary": "Description"}
      ],
      "facts": [
        {
          "source_entity": "Entity Name",
          "target_entity": "Other Entity",
          "relationship_type": "RELATED_TO",
          "fact": "How they relate"
        }
      ]
    }
  ]
}
```

---

## Step 5: Validate Extraction (REQUIRED)

```sh
{PYTHON_PATH} scripts/validate_extraction.py --file {EXTRACTION_FILE}
```

**Common Errors:**
| Error | Cause | Fix |
|-------|-------|-----|
| `Invalid relationship type 'X'` | Used type not in canonical list | Check Step 4 for valid types |
| `Entity 'X' in fact but not in entities` | Missing entity definition | Add entity to entities list |
| `unrecognized arguments: --extraction-file` | Wrong flag name | Use `--file` not `--extraction-file` |

**If validation fails:** Add missing entities. Never delete facts to pass validation.

---

## Step 6: Store Extraction (REQUIRED)

**⚠️ Quality review is REQUIRED. You CANNOT skip it.**

### Step 6a: Run Store Command
```sh
{PYTHON_PATH} scripts/store_extraction.py --project {PROJECT} --extraction-file {EXTRACTION_FILE} --require-quality-review --quality-answers-file tmp/quality-answers.json
```

### Step 6b: If Quality Questions Generated

**Expected behavior:** If duplicates/contradictions detected, you'll see:
```
[INFO] Quality questions written to tmp/quality-questions.json
[ERROR] Duplicate check requires review
```

**This is NORMAL - proceed to fill answers:**

1. **View the questions:** `cat tmp/quality-questions.json`
2. **View the generated answers template:** `cat tmp/quality-answers.json`
3. **Fill the answers** using str-replace-editor (the template already includes `_questions_hash`, `question_index`, and `fact_index`)
4. **Re-run the SAME store command** - it reads the answers file automatically

**How to edit quality-answers.json with str_replace:**

The file is multiline JSON with one prefilled stub per question:
```
Line 1: {
Line 2:   "_questions_hash": "abc123def456",
Line 3:   "duplicates": [
Line 4:     {"question_index": 0, "is_duplicate": false, "duplicate_uuid": null, "reasoning": ""}
Line 5:   ],
Line 6:   "contradictions": [
Line 7:     {"fact_index": 0, "contradicted_fact_uuids": [], "reasoning": ""}
Line 8:   ]
Line 9: }
```

**⚠️ Common mistake:** Using line range 1-1 for multiline content. Match the ACTUAL line span.

**Correct str_replace:** match the actual multiline block currently in the file, not a guessed single-line shape.
```json
{
  "command": "str_replace",
  "path": "tmp/quality-answers.json",
  "old_str": "  \"duplicates\": [],\n  \"contradictions\": []",
  "old_str_start_line_number": 2,
  "old_str_end_line_number": 3,
  "new_str": "  \"duplicates\": [...],\n  \"contradictions\": [...]"
}
```

### Step 6c: Success Indicators
```
[INFO] Quality analysis complete!
[INFO] Storage complete - all facts stored successfully!
```

**Common Errors:**
| Error | Cause | Fix |
|-------|-------|-----|
| `No quality-check wrapper is configured` | Missing `--require-quality-review` flag | Add the flag |
| `Duplicate check failed` | quality-answers.json not filled | Fill the answers file |
| `File already exists` | Tried save-file instead of edit | Use str-replace-editor |

**Optional flags:**
- `--agent auggie` - Record which agent extracted (does NOT replace quality review flags)

---

## Step 7: Verify

**Use the entity mapping output from store_extraction.py** to verify by UUID (most reliable).

### Option A: UUID-based (PREFERRED - unambiguous)
```sh
# store_extraction.py outputs entity-mapping_{timestamp}.json with canonical UUIDs
# Use the canonical_uuid from the mapping for each entity:

{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --entity-uuid {UUID_FROM_MAPPING}
```

**Verify by disposition:**
- **CREATED**: Verify new entity exists with its facts
- **REUSED**: Verify existing entity now has new facts attached
- **ALIASED**: Verify alias resolves to canonical entity

### Option B: Quick check (simple cases, no duplicates)
```sh
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --last 3
```
Use only when entity names are short and no duplicates flagged.

### Option C: Name-based (FALLBACK - can fail on duplicates)
```sh
# ⚠️ WARNING: Fails loudly if duplicate entities exist
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --entity-file tmp/entity.txt
```

**Success signals:**
- Expected entity appears in output
- Facts show correct relationships
- No "not found" or zero results for entities you just stored
- No "Ambiguous" errors (if you see these, use UUID-based verification)

---

## If Needed

### Constrained Environment (no network or unknown network)
```sh
{PYTHON_PATH} scripts/import_summary.py --project {PROJECT} --file {CONVERSATION_FILE} --constrained-environment
```

Use this for:
- sandboxed agents
- air-gapped systems
- CI/test environments
- any environment where outbound network access is uncertain

### Handle Quality Questions
When store_extraction.py generates `tmp/quality-questions.json`:

**Step 1:** Run store_extraction.py - it will fail with:
```
Missing _questions_hash in answers file. Required value: 'abc123def456'
```

**Step 2:** Edit the generated answers file and keep the provided hash:
```json
{
  "_questions_hash": "abc123def456",
  "duplicates": [
    {"question_index": 0, "is_duplicate": true, "duplicate_uuid": "entity-xxx", "reasoning": "Same entity - already exists with matching description"}
  ],
  "contradictions": [
    {"fact_index": 0, "contradicted_fact_uuids": [], "reasoning": "No existing facts about this relationship"}
  ]
}
```

**Example reasoning for duplicates:**
- If duplicate: `"Same entity - already exists with matching description"`
- If NOT duplicate: `"Different concept - this describes X while existing describes Y"`

**Example reasoning for contradictions:**
- If no contradiction: `"No existing facts about this relationship"`
- If contradiction: `"Contradicts fact-uuid-X which states the opposite"`

 - `_questions_hash` - REQUIRED, generated automatically from the current questions file
- `question_index` - matches the index in quality-questions.json (0, 1, 2...)
- If `is_duplicate: true` - MUST provide `duplicate_uuid`
- If `is_duplicate: false` - entity will be created as new (different concept, same name)

**Step 3:** Re-run the SAME store command (it validates and reads the answers file)

### Windows File Creation
When creating helper files (entity.txt, search.txt, task.json, query.json), agents MUST use their save-file tool.
Do NOT use shell commands like `echo` to create these files - encoding issues. Use the agent's file tools.

**Overwrite rule:** The save-file tool cannot overwrite existing files. If a helper file already exists from a previous run, delete it first with remove-files tool, then create it.

### Platform Note
Use `{PYTHON_PATH}` from `mem.config.json`.
Use the exact file paths returned by `prepare_sync_files.py`.

---

## Anti-Patterns (DO NOT)

| Don't | Why |
|-------|-----|
| **Recreate prep-created files with save-file** | Prep script already created valid skeletons; edit in place |
| **Guess extraction schema from memory** | Use the skeleton from prepare_sync_files.py |
| **Use wrapper flow unless configured** | Check config first; manual extraction is default |
| Skip validate_extraction.py (Step 5) | Bad schema corrupts data; MUST run before store |
| Skip `--require-quality-review` flags | Duplicates/contradictions slip through |
| Use `--agent` without quality review flags | `--agent` only records who extracted; does NOT enable quality checks |
| Use --i-am-a-human-and-i-want-to-skip-quality-checks | AI agents must NEVER use this flag |
| Delete facts to pass validation | Loses information; add missing entities instead |
| Guess timestamps | Use prepare_sync_files.py output |
| Guess paths (data/ vs memory/) | Read from mem.config.json |
| Hardcode python_path | Read from mem.config.json |
| Use plain import when network access is unknown | Use `--constrained-environment` unless outbound access is confirmed |
| Use `--entity "Name With Spaces"` | Quote escaping fails; use `--entity-file` |
| Use shell `echo` for helper files | Encoding issues; use agent's file tools |

---

## Success Criteria

- [OK] Summary stored (import_summary.py returned success)
- [OK] Extraction validated (validate_extraction.py passed)
- [OK] Entities/facts stored (store_extraction.py completed)
- [OK] Quality review handled if triggered
- [OK] Verification passed (query_memory.py shows new data)
