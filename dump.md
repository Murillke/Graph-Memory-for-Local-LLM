# dump.md - Quick Conversation Dump

**What this does:** Saves conversation to SQL database with cryptographic timestamp. NO extraction.

**Use sync.md instead if you want full pipeline (dump + extraction).**

---

## [BOT] Config First

**Read `mem.config.json` before running any command:**
- Use `python_path` value for `{PYTHON_PATH}`
- Use `project_name` value for `{PROJECT}`
- Do not guess or substitute different values

---

## Quick Reference

**Step 0 (REQUIRED):** Run setup script:
```sh
{PYTHON_PATH} scripts/prepare_sync_files.py --project {PROJECT} --json
```

Use `conversation_file` from output. Ignore extraction_file (not needed for dump).

**Hot path (2 steps):**
```
0. Prepare files                -> prepare_sync_files.py --json
1. Fill conversation file       -> str-replace-editor
2. Import conversation          -> import_conversation.py
3. DONE! (~10 seconds)
```

---

## Step 0: Prepare Files

```sh
{PYTHON_PATH} scripts/prepare_sync_files.py --project {PROJECT} --json
```

Use values from `mem.config.json` for `{PROJECT}` and `{PYTHON_PATH}`.

Save the `conversation_file` path from output.

---

## Step 1: Fill Conversation File

Edit the conversation_file using str-replace-editor.

Replace `"exchanges": []` with your conversation:
```json
{
  "exchanges": [
    {
      "user": "User's message",
      "assistant": "Your response",
      "fidelity": "full"
    }
  ]
}
```

**Fidelity values:** `full`, `paraphrased`, `reconstructed`, `summary`

---

## Step 2: Import Conversation

**Choose the import mode before running this step:**

- **Constrained mode (PREFERRED for agents):** use this when network access is unavailable, restricted, sandboxed, or unknown
- **Network mode:** use plain import only when you know outbound OpenTimestamps submission is allowed

**Constrained mode command:**
```sh
{PYTHON_PATH} scripts/import_conversation.py --project {PROJECT} --file {CONVERSATION_FILE} --agent {AGENT} --constrained-environment
```

**Network mode command:**
```sh
{PYTHON_PATH} scripts/import_conversation.py --project {PROJECT} --file {CONVERSATION_FILE} --agent {AGENT}
```

Use values from config for `{PROJECT}` and `{PYTHON_PATH}`. Use conversation_file path from Step 0 output.

**Expected output:**
```
[OK] Stored interaction: uuid-abc123
[OTS] OpenTimestamps proof created
[OK] Conversation imported successfully!
```

**Rule:** If you are an autonomous agent and you have not positively confirmed outbound network access, use `--constrained-environment`.

---

## DONE!

Conversation is:
- [OK] Stored in SQL database
- [OK] Cryptographically timestamped
- [OK] Safe to exit

**Extraction happens later via extract.md or sync.md**

---

## If Needed

### Constrained Environment (no network)
```sh
{PYTHON_PATH} scripts/import_conversation.py --project {PROJECT} --file {CONVERSATION_FILE} --agent {AGENT} --constrained-environment --constraint-reason "No outbound network access"
```

### Recover Bitcoin Attestation Later
After using constrained environment, recover from network-capable runtime:
```sh
# Preview
{PYTHON_PATH} scripts/submit_local_proofs_to_ots.py --project {PROJECT} --dry-run

# Submit
{PYTHON_PATH} scripts/submit_local_proofs_to_ots.py --project {PROJECT}
```

Then wait 4-12 hours and run:
```sh
{PYTHON_PATH} scripts/verify_graph_standalone.py --project {PROJECT} --upgrade
```

---

## Anti-Patterns (DO NOT)

| Don't | Why |
|-------|-----|
| Guess timestamp | Use prepare_sync_files.py output |
| Create conversation file manually | Prep script already created it |
| Run extraction after dump | That's sync.md, not dump.md |
| Use shell echo for files | Encoding issues |
| Use plain import when network access is unknown | Use `--constrained-environment` unless outbound access is confirmed |
| Re-import same conversation file | Creates duplicate entries with new UUIDs |

---

## Idempotency

**Not safe to re-run.** Each import creates new interaction UUIDs. Re-importing the same conversation file creates duplicates in the database.

If you need to fix a conversation:
1. Note the UUID from the original import
2. The duplicate will have a different UUID - extraction should reference the correct one

---

## Success Criteria

- [OK] Conversation stored in SQL
- [OK] OpenTimestamps proof created
- [OK] Fast exit (~10 seconds)
