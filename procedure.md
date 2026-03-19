# mem/procedure.md - Execute a Procedure

**[API] PUBLIC API: This workflow file is your interface for executing procedures with audit trail.**

---

## [BOT] Config First

**Read `mem.config.json` before running any command:**
- Use `python_path` value for `{PYTHON_PATH}`
- Use `project_name` value for `{PROJECT}`
- Do not guess or substitute different values

---

## [BOT] LLM INSTRUCTIONS

**If you have been instructed to "follow procedure.md", "execute a procedure", or "run the {X} workflow", you are expected to:**

1. **Look up the procedure** (using recall_procedure.md patterns)
2. **Verify it is active** (not deprecated/superseded/invalid)
3. **Create execution records** as you perform each step
4. **Record outcomes** (success/failure) for audit

**You are capable of:**
- Looking up procedures via `query_memory.py`
- Managing execution records via `execute_procedure.py`
- Running Python scripts via launch-process tool
- Performing step actions and recording results

**CRITICAL: This script does NOT auto-execute procedure steps.**
- YOU (the agent) perform each step action
- The script records what happened for audit purposes
- Think of it as: "do the work, then log that you did it"

**CRITICAL: Multi-word arguments (ALWAYS use file-based flags):**
- Shell quoting is UNRELIABLE for multi-word values on PowerShell
- Use `--*-file` flags for procedure names, UUIDs, notes with spaces
- To create the file: use save-file tool (guarantees UTF-8)

**CRITICAL: Do NOT execute deprecated procedures.**
- If `lifecycle_status` is `deprecated`, `superseded`, or `invalid`: STOP
- Report to user: "This procedure is {status}. Cannot execute."

**Follow the instructions below to execute procedures with audit trail.**

---

## What This Does

Executes a procedure step-by-step while creating audit records:
- `ProcedureRun` - tracks the overall execution
- `StepRun` - tracks each step's execution
- Hashes computed on finalization for integrity
- Optional batching for OTS anchoring

---

## Prerequisites

- Memory system initialized (see [mem/init.md](init.md))
- Procedures extracted and stored (see [mem/sync.md](sync.md))
- Procedure is active (not deprecated/superseded/invalid)

---

## Failure Policy

**On step failure:**
1. Mark current StepRun as `failure`
2. Auto-skip remaining pending steps as `skipped`
3. Mark ProcedureRun as `failure`
4. **STOP** - execution ends

Use `--fail-step-and-run` to execute this policy in one command.

---

## Quick Start (Simplified Flow - Recommended)

**Phase 3 compound commands reduce friction.** Use these instead of the detailed flow below.

**Replace `{PYTHON_PATH}` and `{PROJECT}` with values from mem.config.json**

### 1. Start Run With All Steps

**Option A: JSON input file (RECOMMENDED)**
```powershell
# Create tmp/run.json:
# {
#   "procedure_uuid": "{PROCEDURE_UUID}",
#   "project": "{PROJECT}",
#   "agent": "auggie",
#   "invocation_context": "procedure_md"
# }
{PYTHON_PATH} scripts/execute_procedure.py --start-run-with-steps --input-file tmp/run.json --json
```

**Option B: Individual flags**
```sh
{PYTHON_PATH} scripts/execute_procedure.py --start-run-with-steps \
    --procedure-uuid {PROCEDURE_UUID} \
    --project {PROJECT} \
    --agent "auggie" \
    --invocation-context procedure_md \
    --json
```

**Returns:**
```json
{
  "run_uuid": "run-abc123",
  "procedure_name": "Deploy Workflow",
  "total_steps": 3,
  "steps": [
    {"step_run_uuid": "steprun-1", "step_number": 1, "action": "Run tests"},
    {"step_run_uuid": "steprun-2", "step_number": 2, "action": "Build container"},
    {"step_run_uuid": "steprun-3", "step_number": 3, "action": "Deploy"}
  ],
  "status": "ready"
}
```

### 2. For Each Step: Execute and Complete (Success Path)

**Do the action, then on SUCCESS:**

```sh
{PYTHON_PATH} scripts/execute_procedure.py --complete-step-and-advance \
    --step-run-uuid {CURRENT_STEP_RUN_UUID} \
    --status success \
    --json
```

**NOTE:** `--complete-step-and-advance` only accepts `--status success`.
For failures, use `--fail-step-and-run` (see below).

**Returns next step info:**
```json
{
  "completed_step_run_uuid": "steprun-1",
  "completed_status": "success",
  "next_step_run_uuid": "steprun-2",
  "next_step_number": 2,
  "next_action": "Build container",
  "run_complete": false
}
```

**On last step, `run_complete: true`** - proceed to finalize run.

### 3. On Failure: Fail Step and Run

```sh
{PYTHON_PATH} scripts/execute_procedure.py --fail-step-and-run \
    --step-run-uuid {CURRENT_STEP_RUN_UUID} \
    --result-note-file tmp/failure_note.txt \
    --json
```

**This command:**
1. Marks the current step as `failure`
2. Auto-skips any remaining pending steps as `skipped`
3. Finalizes the run as `failure`

**Returns:**
```json
{
  "step_run_uuid": "steprun-1",
  "step_status": "failure",
  "skipped_steps": [
    {"step_run_uuid": "steprun-2", "step_number": 2},
    {"step_run_uuid": "steprun-3", "step_number": 3}
  ],
  "run_uuid": "run-abc123",
  "run_status": "failure",
  "run_hash": "abc..."
}
```

### 4. Finalize Run (Success Path)

```powershell
{PYTHON_PATH} scripts/execute_procedure.py --complete-run \
    --run-uuid {RUN_UUID} \
    --status success \
    --json
```

---

## Detailed Instructions (Original Flow)

### Step 1: Get Current System Time

**Windows:**
```powershell
Get-Date
```

### Step 2: Look Up Procedure

Use `query_memory.py` to find the procedure:

```sh
# For multi-word procedure names, use file-based input
# (Create file with save-file tool first)
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --procedure-file tmp/proc_name.txt --json
```

**Expected output:**
```json
{
  "procedure": {
    "uuid": "entity-abc123",
    "name": "Deploy Workflow",
    "attributes": {
      "lifecycle_status": "active",
      "goal": "Deploy application to production"
    }
  },
  "steps": [
    {"uuid": "entity-step1", "attributes": {"step_number": 1, "action": "Run tests"}},
    {"uuid": "entity-step2", "attributes": {"step_number": 2, "action": "Build container"}}
  ]
}
```

### Step 3: Verify Procedure is Active

**Check `lifecycle_status` from the JSON response.**

If `lifecycle_status` is NOT `active` (or missing, which defaults to active):
```
[STOP] Procedure '{name}' has lifecycle_status='{status}'.
DO NOT EXECUTE deprecated/superseded/invalid procedures.
```

### Step 4: Start Procedure Run

```sh
{PYTHON_PATH} scripts/execute_procedure.py --start-run \
    --procedure-uuid {PROCEDURE_UUID} \
    --project {PROJECT} \
    --agent "auggie" \
    --invocation-context procedure_md \
    --json
```

**Expected output:**
```json
{"run_uuid": "run-abc123", "status": "created"}
```

**Save the `run_uuid` for subsequent commands.**

### Step 5: For Each Step - Execute and Record

For each step in the procedure (in order by `step_number`):

#### 5a. Start Step Run

```sh
{PYTHON_PATH} scripts/execute_procedure.py --start-step \
    --run-uuid {RUN_UUID} \
    --step-uuid {STEP_UUID} \
    --step-number {N} \
    --json
```

**Expected output:**
```json
{"step_run_uuid": "steprun-def456", "status": "created"}
```

#### 5b. Execute the Step Action

**YOU perform the action described in the step's `action` attribute.**

For example, if step says "Run tests":
- You run the test command
- You observe the result

#### 5c. Complete Step Run

**On success:**
```sh
{PYTHON_PATH} scripts/execute_procedure.py --complete-step \
    --step-run-uuid {STEP_RUN_UUID} \
    --status success \
    --json
```

**On failure:**
```sh
{PYTHON_PATH} scripts/execute_procedure.py --complete-step \
    --step-run-uuid {STEP_RUN_UUID} \
    --status failure \
    --result-note-file tmp/failure_note.txt \
    --json
```

Then proceed to Step 6 to mark the procedure run as failed.

### Step 6: Complete Procedure Run

After all steps complete successfully:

```sh
{PYTHON_PATH} scripts/execute_procedure.py --complete-run \
    --run-uuid {RUN_UUID} \
    --status success \
    --json
```

**Expected output:**
```json
{"run_uuid": "run-abc123", "status": "success", "run_hash": "abc123..."}
```

**On failure (if any step failed):**
```sh
{PYTHON_PATH} scripts/execute_procedure.py --complete-run \
    --run-uuid {RUN_UUID} \
    --status failure \
    --result-note-file tmp/failure_note.txt \
    --json
```

### Step 7: (Optional) Create Run Batch for Audit Anchoring

If you want to anchor this run for audit:

```sh
{PYTHON_PATH} scripts/execute_procedure.py --batch-runs \
    --run-uuids {RUN_UUID} \
    --project {PROJECT} \
    --agent "auggie" \
    --json
```

**Expected output:**
```json
{
  "batch_uuid": "runbatch-xyz789",
  "batch_hash": "def456...",
  "batch_index": 1,
  "note": "timestamp_proof not submitted (constrained environment). Hash created locally."
}
```

---

## Error Messages and What They Mean

| Error | Cause | Fix |
|-------|-------|-----|
| `Procedure '{name}' not found` | Procedure doesn't exist | Use `--procedures` to list available |
| `lifecycle_status='{status}'` | Procedure is deprecated | DO NOT EXECUTE. Find active replacement |
| `Invalid invocation_context` | Wrong context value | Use: procedure_md, manual, script, conversation, api |
| `ProcedureStep belongs to procedure '{other}'` | Wrong step UUID | Check step belongs to this procedure |
| `ProcedureRun is already finalized` | Run already completed | Cannot modify finalized runs |
| `StepRun is already finalized` | Step already completed | Cannot modify finalized steps |
| `StepRun is not finalized` | Step incomplete | Complete all steps before finalizing run |
| `ProcedureRun is not finalized (run_hash is NULL)` | Run incomplete | Finalize run before batching |
| `ProcedureRun is already in batch` | Already batched | Runs can only be batched once |

---

## Common Patterns

### Execute a Known Procedure

```
1. query_memory.py --procedure-file tmp/proc_name.txt --json
2. Verify lifecycle_status is active
3. execute_procedure.py --start-run ...
4. For each step: --start-step, DO ACTION, --complete-step
5. execute_procedure.py --complete-run ...
6. (Optional) --batch-runs for audit
```

### Handle Step Failure

```
1. Step action fails
2. --complete-step --status failure --result-note-file tmp/error.txt
3. --complete-run --status failure --result-note-file tmp/error.txt
4. STOP - do not continue to remaining steps
5. Report failure to user
```

### Batch Multiple Runs

If you executed multiple procedures in a session:

```sh
{PYTHON_PATH} scripts/execute_procedure.py --batch-runs \
    --run-uuids-file tmp/run_uuids.txt \
    --project {PROJECT} \
    --agent "auggie" \
    --json
```

Where `tmp/run_uuids.txt` contains one run UUID per line.

---

## Troubleshooting

### "Cannot finalize ProcedureRun - StepRun not finalized"

All steps must be finalized before the run can be finalized.
Check which step is incomplete and call `--complete-step` on it.

### "ProcedureRun is already finalized"

The run was already completed. Finalization is a one-time operation.
You cannot modify a finalized run.

### "timestamp_proof not submitted"

This is expected in constrained environments. The hash is created locally.
When OTS submission is available, the batch can be anchored later.

---

## Related Workflows

- [recall_procedure.md](recall_procedure.md) - Look up procedures without executing
- [sync.md](sync.md) - Extract procedures from conversations
- [remember.md](remember.md) - Query general entities/facts

---

## See Also

- [architecture/procedural-memory-design.md](architecture/procedural-memory-design.md) - Design reference
