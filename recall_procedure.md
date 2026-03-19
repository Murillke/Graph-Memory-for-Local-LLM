# mem/recall_procedure.md - Recall a Procedure

**[API] PUBLIC API: This workflow file is your interface for looking up procedures (how-to workflows).**

---

## [BOT] Config First

**Read `mem.config.json` before running any command:**
- Use `python_path` value for `{PYTHON_PATH}`
- Use `project_name` value for `{PROJECT}`
- Do not guess or substitute different values

---

## [BOT] LLM INSTRUCTIONS

**If you have been instructed to "follow recall_procedure.md", "recall a procedure", or "find how to do X", you are expected to:**

1. **Identify what to search for** (procedure name, script name, step keyword, or trigger phrase)
2. **Run query_memory.py** with the file-based procedural workflow inputs to find matching procedures
3. **Interpret the results** and present the procedure with its steps

**You are capable of:**
- Listing all procedures in a project with `--procedures`
- Getting a specific procedure with its steps with `--procedure-file tmp/proc.txt`
- Searching procedures by step content with `--search-procedures-file tmp/search.txt`
- Running Python scripts via launch-process tool

**CRITICAL: Query/name arguments use file-based flags:**
- Shell quoting is UNRELIABLE for multi-word values on PowerShell
- ALWAYS use `--*-file` flags for procedure names with spaces:
  - `--procedure-file tmp/proc.txt` for procedure lookups
  - `--search-procedures-file tmp/search.txt` for procedure search terms
- To create the file (PowerShell UTF-8):
  ```powershell
  [System.IO.File]::WriteAllText("tmp/proc.txt", "My Workflow")
  ```
- Direct `--procedure` / `--search-procedures` flags remain backward compatibility only and are not part of the approved workflow
- Deprecated direct procedure flags are rejected by default
- Set `MEM_ALLOW_DIRECT_INPUT=1` only for legacy/manual compatibility

**CRITICAL: Lifecycle filtering (retrieval safety):**
- By default, deprecated/superseded/invalid procedures are EXCLUDED
- This protects you from using broken or outdated workflows
- Use `--include-deprecated` only for audit/history review
- Missing lifecycle_status is treated as "active" (backward compatibility)

**Follow the instructions below to recall procedures.**

---

## What This Does

Queries the GRAPH database for procedures (step-by-step workflows) and their steps.

**Use cases:**
- "How do I sync memory?"
- "What procedure uses import_conversation.py?"
- "Show me the deployment workflow"

---

## Prerequisites

- Memory system initialized (see [mem/init.md](init.md))
- Conversations synced with procedural content (see [mem/sync.md](sync.md))
- Project name

---

## Instructions

**Replace `{PYTHON_PATH}` and `{PROJECT}` with values from mem.config.json**

### List All Active Procedures

```sh
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --procedures
```

**Expected output:**
```
[PROCEDURES] Found 3 procedures:

   Sync Workflow
      Goal: Store conversation and extract knowledge to graph database
      Triggers: follow sync.md, run memory sync

   Deploy Workflow
      Goal: Deploy application to production
      Triggers: deploy app, push to prod
```

---

### Get a Specific Procedure with Steps

```sh
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --procedure-file tmp/proc.txt
```

**Expected output:**
```
[PROCEDURE] Sync Workflow
   Goal: Store conversation and extract knowledge to graph database
   Triggers: follow sync.md, run memory sync
   Prerequisites: mem.config.json exists

   Steps (3):
      1. Read sync.md and mem.config.json for configuration
      2. Run import_conversation.py with conversation JSON
         Scripts: import_conversation.py
      3. Run store_extraction.py to persist entities/facts
         Scripts: store_extraction.py
```

---

### Search Procedures by Step Content

Use this when you remember part of a workflow (script name, action, etc.):

```sh
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --search-procedures-file tmp/search.txt
```

**Expected output:**
```
[SEARCH] Found 1 procedures containing 'store_extraction':
   - Sync Workflow: Store conversation and extract knowledge to graph database
```

---

### View Deprecated/Historical Procedures (Audit Mode)

**WARNING:** Only use this for audit or review. Deprecated procedures may be broken or unsafe.

```sh
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --procedures --include-deprecated
```

**Expected output:**
```
[PROCEDURES] Found 4 procedures (including deprecated):

   Sync Workflow
      Goal: Store conversation and extract knowledge

   Old Sync Workflow
      [LIFECYCLE: deprecated]
      Goal: Previous version of sync workflow

   Broken Deploy
      [LIFECYCLE: invalid]
      Goal: Deploy workflow that no longer works
```

---

### JSON Output

Add `--json` for machine-readable output:

```sh
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --procedure-file tmp/proc.txt --json
```

**Expected output:**
```json
{
  "procedure": {
    "name": "Sync Workflow",
    "summary": "Workflow for syncing conversation memory",
    "attributes": {
      "goal": "Store conversation and extract knowledge",
      "trigger_phrases": ["follow sync.md"],
      "lifecycle_status": "active"
    }
  },
  "steps": [
    {"name": "Sync Workflow / Step 1", "attributes": {"step_number": 1, "action": "..."}},
    {"name": "Sync Workflow / Step 2", "attributes": {"step_number": 2, "action": "..."}}
  ]
}
```

---

## Common Recall Patterns

| User says... | What to search |
|--------------|----------------|
| "How do I sync memory?" | `--search-procedures-file tmp/search.txt` or `--procedures` then filter |
| "What uses import_conversation.py?" | `--search-procedures-file tmp/search.txt` |
| "Show me the deploy steps" | `--procedure-file tmp/proc.txt` |
| "What workflows do we have?" | `--procedures` |
| "Why was X deprecated?" | `--procedure-file tmp/proc.txt --include-deprecated` |

---

## Troubleshooting

### "Procedure not found"

1. Check spelling - use `--procedures` to list all available
2. If it exists but is deprecated, the error will suggest `--include-deprecated`
3. Procedure may not have been extracted yet - check if sync.md was run

### No procedures returned

1. Verify project name is correct
2. Run sync.md to extract procedures from conversations
3. Check that conversations contain procedural content ("how to do X")

### Found deprecated procedure on accident

This shouldn't happen - default retrieval excludes deprecated procedures.
If you see deprecated procedures without `--include-deprecated`, report as bug.

---

## Related Workflows

- [sync.md](sync.md) - Extract procedures from conversations
- [remember.md](remember.md) - Query general entities/facts
- [dump.md](dump.md) - Capture conversations with procedural content

---

## See Also

- [docs/PROCEDURAL-MEMORY-DESIGN.md](docs/PROCEDURAL-MEMORY-DESIGN.md) - Design reference
- [docs/EXTRACTION-FORMAT-SPEC.md](docs/EXTRACTION-FORMAT-SPEC.md) - Procedure entity format
