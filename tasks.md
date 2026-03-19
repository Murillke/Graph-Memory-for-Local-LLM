# tasks.md - Task Management

**What this does:** Query and manage TODO items stored in the knowledge graph.

Tasks are automatically extracted from conversations during sync (patterns like "we need to implement X", "TODO: add Y"). You can also add tasks manually.

[!] **BEFORE STARTING: Check COMMANDS.md to see if a different command better fits the user's request!**

---

## [BOT] Config First

**Read `mem.config.json` before running any command:**
- Use `python_path` value for `{PYTHON_PATH}`
- Use `project_name` value for `{PROJECT}`
- Do not guess or substitute different values

---

## LLM Instructions

**Default shows ALL active tasks** (pending + in_progress) - nothing truncated.

**Hot path:**
```
1. Show all tasks  -> tasks.py --project {PROJECT}
2. With summaries  -> tasks.py --project {PROJECT} -v
3. Show stats      -> tasks.py --stats today
4. Show created    -> tasks.py --created-between --from <start> --to <end>
5. Show details    -> tasks.py --details <hash>  # e.g., --details 1fab266
6. Edit task       -> tasks.py --edit <hash> ... # e.g., --edit 1fab266 --name-file tmp/task.txt
7. Start task      -> tasks.py --start <hash>    # e.g., --start 1fab266
8. Mark done       -> tasks.py --done <hash>     # e.g., --done c7dec3e
9. Mark invalid    -> tasks.py --skip <hash>     # e.g., --skip abc1234
```

**CRITICAL:** Operations use **hash identifiers only**, NOT numbers!
- Numbers are display-only for human readability
- Hash IDs (first 7 chars of UUID) are shown in brackets: `1. [1fab266] Task name`
- Hash IDs are STABLE - they don't shift when task lists change
- Numbers shift after every mutation - NEVER use them for operations

```
CORRECT:   --done 1fab266    --start 1fab266    --details 1fab266    --edit 1fab266
WRONG:     --done 1          --start 1          --details 1          --edit 1
```

**CRITICAL:** For string-bearing task edits, prefer file-based input.
- Use helper files for `--name`, `--summary`, and `--details`
- Recommended: `tmp/task.txt`, `tmp/summary.txt`, `tmp/details.txt`
- Use direct inline values only for very short, simple strings
- Dependency hashes remain inline or in a helper file because they are identifiers, not prose

**CRITICAL:** Always print/display the full output from `tasks.py` commands!
- You need the hash IDs from the output to perform any operations
- If you don't print the output, you'll have to re-run the command to get hashes
- Never summarize or truncate the task list - show it verbatim

If the user says "all tasks", interpret that as "all active tasks" unless they explicitly ask for completed/invalid too.

### Path Context

**If this repo is a submodule (host mode):**
- Working from: `{host_workspace}/mem/`
- Config file: `./mem.config.json`

**If this repo is standalone:**
- Working from repo root
- Config file: `./mem.config.json`

### Prerequisites

1. [OK] Read `mem.config.json` for `python_path` and `project_name`
2. [OK] Run `prepare_sync_files.py --project {PROJECT} --json` before helper-file workflows so `tmp/task.txt`, `tmp/summary.txt`, `tmp/task.json`, and `tmp/batch.json` are fresh

---

## Show Tasks (3 Display Levels)

**Read `python_path` from config, then:**

### Level 1 - Quick List (default)
```sh
# Show all active tasks (in_progress + pending, globally numbered)
{PYTHON_PATH} scripts/tasks.py --project {PROJECT}
```

**Expected output:**
```
================================================================================
TASKS - llm_memory (active)
================================================================================
#   Hash      Pri    Name                                          Status   Age
--------------------------------------------------------------------------------
1.  [6326de0] MEDIUM Task Statistics and Recall Integration        IN_PROG  8h
2.  [eef8cf2] HIGH   Task Operations OTS Provenance                PENDING  7h
3.  [0a41fe4] HIGH   Re-review and Update Command/Script Checklists PENDING  8h
4.  [bf4d29f] MEDIUM MCP Workflow Test Harness                     PENDING  4h

Showing 4 active tasks (1 in_progress, 3 pending)
```

**The hash in brackets `[6326de0]` is what you use for ALL operations:**
```sh
# CORRECT - use the hash from brackets
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --details 6326de0
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --edit 6326de0 --name-file tmp/task.txt
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --start eef8cf2
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --done bf4d29f

# WRONG - numbers don't work
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --details 1   # ERROR!
```

**Filtered views:**
```sh
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --in-progress
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --pending
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --high
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --medium
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --low
```

**Output:** Task number, name, age (in_progress shows "started 2h ago")

**Closed-task history (explicit, discouraged on the regular user path):**
```sh
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --all-statuses
```

This includes:
- `complete`
- `invalid`

**Tasks completed in a time window:**
```sh
# Show tasks completed yesterday
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --completed-between --from 2026-03-15 --to 2026-03-15
```

**Expected output:**
```
================================================================================
TASKS COMPLETED - llm_memory
================================================================================
Window: 2026-03-15T00:00:00 -> 2026-03-15T23:59:59

1. [52acfe0] Standardize Entity Types
   Completed: 2026-03-15T23:36:14

2. [398693c] Standardize Template JSON Format for LLM Editing
   Completed: 2026-03-15T23:11:45

3. [b148695] Add llm-state fidelity support
   Completed: 2026-03-15T20:51:22

Total completed: 3
```

This queries the `task_operations` table. Use for questions like "What did I complete yesterday?"

**Filtered views and numbering:** When using filters like `--pending` or `--in-progress`, task numbers are preserved from the global actionable list. This means you may see gaps (e.g., tasks numbered 2, 3, 4 when task 1 is in-progress). Numbers are for display only - **always use hash IDs for operations** (e.g., `--done 1fab266` not `--done 2`).

### Level 2 - With Summaries
```sh
# Add -v or --verbose to include task summaries
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --pending -v
```

**Output:** Task number, name, age, + full summary text

### Level 3 - Full Context
```sh
# Show detailed context for a specific task by hash ID (from task list)
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --details 6326de0
```

**Expected output:**
```
================================================================================
TASK DETAILS - llm_memory
================================================================================

Name:     Task Statistics and Recall Integration
Hash:     6326de0
Priority: MEDIUM
Status:   in_progress (started 2h ago)
Created:  2026-03-15T19:21:08

Summary:
  Add --stats flag to tasks.py for viewing task completion statistics...

Related Facts:
  - Task Statistics and Recall Integration --[IMPLEMENTS]--> recall.py

Related Entities:
  - recall.py (File) - Modified 3h ago
  - tasks.py (File) - Modified 1h ago
```

**CRITICAL:** Use the hash `6326de0` from brackets, NOT the display number `1`.

---

## Edit Existing Task

**Use hash identifiers from the task list output.**

**Recommended helper files:**
```sh
# Refresh helper files first
{PYTHON_PATH} scripts/prepare_sync_files.py --project {PROJECT} --json
```

Use these files when needed:
- `tmp/task.txt` for the new task name
- `tmp/summary.txt` for the new summary
- `tmp/details.txt` for detailed notes
- `tmp/blocked-by.txt` for comma-separated blocker hashes
- `tmp/parent.txt` for a single parent-task hash

**Rename task:**
```sh
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --edit 6326de0 --name-file tmp/task.txt
```

**Update summary:**
```sh
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --edit 6326de0 --summary-file tmp/summary.txt
```

**Update details:**
```sh
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --edit 6326de0 --details-file tmp/details.txt
```

**Set blockers:**
```sh
# Inline hash list
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --edit 6326de0 --blocked-by eef8cf2,0a41fe4

# Or via file containing: eef8cf2,0a41fe4
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --edit 6326de0 --blocked-by-file tmp/blocked-by.txt
```

**Clear blockers:**
```sh
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --edit 6326de0 --clear-blocked-by
```

**Set parent task / make subtask:**
```sh
# Inline parent hash
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --edit 6326de0 --parent eef8cf2

# Or via file containing one hash
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --edit 6326de0 --parent-file tmp/parent.txt
```

**Clear parent task:**
```sh
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --edit 6326de0 --clear-parent
```

**Combined edit:**
```sh
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --edit 6326de0 --summary-file tmp/summary.txt --details-file tmp/details.txt
```

**Rules:**
- `--edit` always takes the target task hash first
- `--blocked-by` takes a comma-separated hash list with no spaces required
- `--parent` takes exactly one hash
- `--clear-blocked-by` and `--clear-parent` remove existing values
- The script rejects invalid hashes, self-blocking, self-parenting, and direct parent cycles

**Expected output:**
```text
TASK UPDATED:
  OK #3 [6326de0] Task name
  Fields changed: summary, details
```

---

## Task Statistics

Task activity statistics come from SQL `task_operations`, not the graph task node state.

```sh
# Rolling windows
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --stats today
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --stats week
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --stats month

# Custom inclusive window
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --stats custom --from 2026-03-10 --to 2026-03-16

# Include per-event rows
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --stats today --verbose
```

**What is counted:**
- `Created` = `operation = add`
- `Started` = `status_after = in_progress`
- `Paused` = `status_before = in_progress` and `status_after = pending`
- `Completed` = `status_after = complete`
- `Invalidated` = `status_after = invalid`
- `Priority changed` = `operation = set_priority`

**Window semantics:**
- `today` = local day start through local day end
- `week` = rolling last 7 days
- `month` = rolling last 30 days
- `custom` = explicit inclusive `--from` / `--to`

---

## Tasks Created In A Time Window

Use this when you specifically want graph-backed task creation time, so the query still works even if SQL task history is unavailable.

```sh
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --created-between --from 2026-03-10 --to 2026-03-16
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --created-between --from 2026-03-16T00:00:00 --to 2026-03-16T12:00:00
```

Behavior:
- queries graph `Entity.created_at`
- filters only entities labeled `Task`
- uses inclusive `--from` / `--to`
- returns created tasks even if SQL `task_operations` is missing

---

## Task Statuses

| Status | Description |
|--------|-------------|
| `pending` | Default. Task is waiting to be worked on. |
| `in_progress` | Task is actively being worked on. Shows "started X ago" in age display. |
| `complete` | Task is finished. |
| `invalid` | Task was incorrectly extracted (not a real task). |

---

## Mark Task Complete

**Use hash identifiers from task list output:**

```sh
# Hash-based (required) - use hash shown in brackets [1fab266]
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --done 1fab266

# Name-based (legacy, rejects duplicate names)
# Create tmp/task.txt with task name, then:
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --complete-file tmp/task.txt
```

---

## Mark Task Invalid

Use this when the AI incorrectly identified something as a task.

**Use hash identifiers:**

```sh
# Hash-based (required)
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --skip abc1234

# Name-based (legacy, rejects duplicate names)
# Create tmp/task.txt with task name, then:
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --invalid-file tmp/task.txt
```

---

## Status Operations by Hash (Required)

**Use hash IDs from task list output (shown in brackets `[1fab266]`):**

```sh
# Start a task (pending -> in_progress)
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --start 1fab266
```

**Expected output:**
```
Task 'MCP Workflow Test Harness' status changed: pending -> in_progress
```

```sh
# Start multiple tasks
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --start 1fab266,c7dec3e

# Pause a task (in_progress -> pending)
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --pause 1fab266

# Mark single task done
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --done c7dec3e

# Mark multiple tasks done
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --done 1fab266,c7dec3e,abc1234

# Mark tasks as invalid (not real tasks)
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --skip def5678,ghi9012
```

**IMPORTANT:** Numbers are NOT accepted for operations. Always use hash identifiers.

**State transitions:**
```
pending -> in_progress  (--start)     OK, sets started_at
pending -> complete     (--done)      OK
pending -> invalid      (--skip)      OK
in_progress -> complete (--done)      OK
in_progress -> invalid  (--skip)      OK
in_progress -> pending  (--pause)     OK, clears started_at
```

---

## Change Task Priority

**Use hash identifiers:**

```sh
# Change single task to HIGH priority
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --set-priority 1fab266 --to high

# Change multiple tasks to LOW priority
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --set-priority c7dec3e,abc1234 --to low
```

---

## Batch by JSON File (Alternative)

**Use JSON file for multiple tasks by name:**

Create `tmp/batch.json`:
```json
{
  "tasks": [
    "Task Name 1",
    "Task Name 2",
    "Task Name 3"
  ]
}
```

**Batch complete:**
```sh
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --batch-complete-file tmp/batch.json
```

**Batch invalidate:**
```sh
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --batch-invalid-file tmp/batch.json
```

---

## Add New Task Manually

**Recommended (JSON file - single file with all fields):**
```sh
# First run prepare_sync_files.py --project {PROJECT} --json, then edit tmp/task.json:
# {
#   "name": "Implement feature X",
#   "summary": "Add ability to do X with Y integration",
#   "priority": "high"
# }

{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --add-file tmp/task.json
```

**Alternative (separate files):**
```sh
# First run prepare_sync_files.py --project {PROJECT} --json, then fill tmp/task.txt and tmp/summary.txt:
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --add-file tmp/task.txt --priority high --summary-file tmp/summary.txt
```

[!] **ALWAYS use file-based input.** Direct `--add` breaks with spaces in task names.

---

## Task Extraction

Tasks are automatically extracted from conversations when you run `sync.md`.

**Patterns recognized:**
- "We need to implement X"
- "TODO: Add feature Y"
- "Should create script Z"
- "Next step is to build W"
- "We are missing X"
- "Let's implement X"

**After sync, you'll see:**
```
================================================================================
NEW TASKS IDENTIFIED (5):
================================================================================

  1. [HIGH] Implement External Document Import
  2. [MEDIUM] Add document hash verification
  3. [LOW] Create extract_document.py script
  4. [MEDIUM] Update store_extraction.py for documents
  5. [LOW] Add document type detection

12 pending tasks total

Run: {PYTHON_PATH} scripts/tasks.py --project {PROJECT}
================================================================================
```

---

## Integration with Workflow

1. **During conversation** - Mention tasks naturally
2. **Run sync.md** - Tasks are auto-extracted
3. **Review task summary** - See new tasks after sync
4. **Mark complete/invalid** - Update task status
5. **Query tasks** - Use `tasks.py` anytime

---

## Examples

### Full Workflow

**Replace `{PYTHON_PATH}` and `{PROJECT}` with values from `mem.config.json`:**

```sh
# 1. Have conversation with TODOs
# 2. Run sync (use timestamped files!)
{PYTHON_PATH} scripts/import_conversation.py --project {PROJECT} --file tmp/conversation_YYYY-MM-DD_HH-MM-SS.json --agent {AGENT}
{PYTHON_PATH} scripts/store_extraction.py --project {PROJECT} --extraction-file tmp/extraction_YYYY-MM-DD_HH-MM-SS.json --agent {AGENT}

# 3. See task summary (automatic)
# NEW TASKS IDENTIFIED (3): ...

# 4. View actionable tasks (shows hash IDs in brackets)
{PYTHON_PATH} scripts/tasks.py --project {PROJECT}
# Output: 1. [1fab266] [HIGH] Task name...

# 5. Start working on task (use hash from output)
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --start 1fab266

# 6. Mark task complete (use hash)
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --done 1fab266

# 7. Mark task invalid (use hash)
{PYTHON_PATH} scripts/tasks.py --project {PROJECT} --skip c7dec3e
```

---

## Troubleshooting

**"Numbers not accepted. Use hash identifier..."**
- Operations require hash IDs (e.g., `1fab266`), not numbers
- Run `tasks.py --project {PROJECT}` to see hash IDs in brackets

**"Invalid hash '...'"**
- Re-run `tasks.py --project {PROJECT}` and copy the exact hash shown in brackets
- For blockers, every hash in `--blocked-by` must resolve or the whole edit is rejected

**"Task cannot block itself" / "Task cannot be its own parent"**
- Remove the target task hash from `--blocked-by`
- Use a different task hash for `--parent`

**"Direct parent cycle detected"**
- The chosen parent already has the current task as its parent
- Clear one side first, then apply the intended parent relationship

**"No task found matching hash"**
- Verify hash prefix from task list output
- Use at least 3-4 characters for uniqueness

**"Multiple tasks with same name. Use hash instead."**
- Name-based operations (--complete-file) reject duplicate task names
- Use hash-based operations (--done <hash>) instead - they use UUID identity

**"Task not found"**
- For name-based operations, check exact task name spelling
- Task names are case-sensitive

**"Invalid priority value"**
- Priority must be one of: high, medium, low
- Default is medium if not specified

---

## Success Criteria

- [OK] Task list displays with priorities
- [OK] Task status updates reflected in query results
- [OK] Completed tasks move to completed section

---

## Notes

- Tasks are stored as Entity nodes with type "Task"
- Tasks have `priority` and `status` fields
- Task blockers are stored in `attributes.blocked_by`
- Parent/subtask structure is stored in `attributes.parent_task_uuid`
- Tasks are linked to source interactions
- Tasks are part of the knowledge graph
- Can query tasks with Cypher if needed
