# export.md - Export Conversation History

**What this does:** Export raw conversation history from SQL database (audit log).

**NOTE:** This exports SQL audit log, NOT graph memory. For memory queries, use [remember.md](remember.md).

---

## [BOT] Config First

**Read `mem.config.json` before running any command:**
- Use `python_path` value for `{PYTHON_PATH}`
- Use `project_name` value for `{PROJECT}`
- Do not guess or substitute different values

---

## Quick Reference

```sh
# Export all
{PYTHON_PATH} scripts/export_history.py --project {PROJECT}

# Export last N
{PYTHON_PATH} scripts/export_history.py --project {PROJECT} --limit 10

# Export to file
{PYTHON_PATH} scripts/export_history.py --project {PROJECT} --output history.txt

# Export as JSON
{PYTHON_PATH} scripts/export_history.py --project {PROJECT} --json
```

---

## Flags Reference

| Flag | Purpose |
|------|---------|
| `--project {NAME}` | Required. Project name |
| `--output {FILE}` | Save to file instead of stdout |
| `--json` | Output as JSON |
| `--verify` | Verify hash chain before export |
| `--show-hash` | Show content hashes and links |
| `--limit N` | Show only last N interactions |
| `--offset N` | Skip first N interactions |

---

## Export All Conversations

```sh
{PYTHON_PATH} scripts/export_history.py --project {PROJECT}
```

**Expected output:**
```
============================================================
Conversation History for '{PROJECT}'
============================================================

[1] 2026-03-03 14:23:45 (uuid-abc123)
User: Hello!
Assistant: Hi there!

Total interactions: 2
```

---

## Common Combinations

```sh
# Backup to file
{PYTHON_PATH} scripts/export_history.py --project {PROJECT} --output backup.txt

# Export for migration (JSON)
{PYTHON_PATH} scripts/export_history.py --project {PROJECT} --json --output export.json

# Audit trail with verification
{PYTHON_PATH} scripts/export_history.py --project {PROJECT} --verify --show-hash

# Paginate (skip 5, show next 10)
{PYTHON_PATH} scripts/export_history.py --project {PROJECT} --offset 5 --limit 10
```

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| "Project not found" | Check project name in config |
| "No interactions found" | Import conversations first (sync.md) |

---

## Success Criteria

- [OK] Interactions exported from SQL database
- [OK] Hash chain verified (if --verify used)
- [OK] Output saved to file (if --output used)

