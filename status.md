# status.md - Check Memory Status

**What this does:** Shows how many interactions are stored vs processed.

---

## [BOT] Config First

**Read `mem.config.json` before running any command:**
- Use `python_path` value for `{PYTHON_PATH}`
- Use `project_name` value for `{PROJECT}`
- Do not guess or substitute different values

---

## Quick Reference

```sh
{PYTHON_PATH} scripts/sync.py --project {PROJECT} --status
```

**If unprocessed > 0:** Follow extract.md

---

## Run Status Check

```sh
{PYTHON_PATH} scripts/sync.py --project {PROJECT} --status
```

**Expected output:**
```
============================================================
[DATA] Memory Status for '{PROJECT}'
============================================================
Total interactions:       691
Processed:                286
Unprocessed:              405

[WARNING]  405 interaction(s) pending extraction

Next steps:
  Follow extract.md, or run:
    {PYTHON_PATH} scripts/extract_pending.py --project {PROJECT}
```

---

## What It Means

| Field | Description |
|-------|-------------|
| **Total interactions** | Conversations stored in SQL database |
| **Processed** | Interactions that have been extracted (entities/facts created) |
| **Unprocessed** | Interactions pending extraction |

---

## What To Do Next

| Status | Action |
|--------|--------|
| Unprocessed = 0 | ✓ All caught up |
| Unprocessed > 0 | Follow [extract.md](extract.md) to process pending conversations |

---

## Troubleshooting

**"Project not found"**
- Project doesn't exist yet
- Run sync.md first to create project and store conversation

**"Total interactions: 0"**
- No conversations stored yet
- Run sync.md or dump.md to import conversations

---

## Success Criteria

- [OK] Status command runs
- [OK] Output shows Total/Processed/Unprocessed counts
- [OK] If unprocessed > 0, user knows to run extract.md

