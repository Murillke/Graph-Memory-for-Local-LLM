# history.md - View Conversation History

**What this does:** View recent conversations from SQL audit log.

**Use case:** Agent recovery after context loss, reviewing past work, debugging.

**NOTE:** This queries SQL audit log (raw text), NOT graph memory. For extracted knowledge, use [remember.md](remember.md).

---

## [BOT] Config First

**Read `mem.config.json` before running any command:**
- Use `python_path` value for `{PYTHON_PATH}`
- Use `project_name` value for `{PROJECT}`
- Do not guess or substitute different values

---

## Quick Reference

```sh
# Last 10 interactions
{PYTHON_PATH} scripts/show_interactions.py --project {PROJECT} --last 10

# Last 3 sessions (grouped)
{PYTHON_PATH} scripts/show_interactions.py --project {PROJECT} --sessions 3

# Full content (not truncated)
{PYTHON_PATH} scripts/show_interactions.py --project {PROJECT} --sessions 3 --full

# Specific interaction by UUID
{PYTHON_PATH} scripts/show_interactions.py --project {PROJECT} --uuid abc123
```

---

## Flags Reference

| Flag | Purpose |
|------|---------|
| `--project {NAME}` | Required. Project name |
| `--last N` | Show last N interactions (default: 5) |
| `--sessions N` | Show last N sessions (grouped by timestamp) |
| `--uuid {PREFIX}` | Show specific interaction by UUID prefix |
| `--full` | Full content (default: truncated to 200 chars) |
| `--json` | Output as JSON |

---

## Agent Recovery Workflow

If you lost context and need to recover:

```sh
# 1. See what you were working on
{PYTHON_PATH} scripts/show_interactions.py --project {PROJECT} --last 10

# 2. Get full details of specific conversation
{PYTHON_PATH} scripts/show_interactions.py --project {PROJECT} --uuid {UUID} --full

# 3. Check extracted entities
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --last 10
```

---

## Common Combinations

```sh
# Save to file for review
{PYTHON_PATH} scripts/show_interactions.py --project {PROJECT} --last 10 --json > tmp/recent_history.json

# Full session details
{PYTHON_PATH} scripts/show_interactions.py --project {PROJECT} --sessions 3 --full --json
```

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| "No interactions found" | Check project name, verify database exists |
| "Database is locked" | Another script running; wait and retry |
| "UUID not found" | Check UUID prefix; use --last 10 to see recent |

---

## Success Criteria

- [OK] Interactions display with timestamps
- [OK] Full mode shows complete content
- [OK] Sessions group related interactions
- [OK] JSON output is valid

