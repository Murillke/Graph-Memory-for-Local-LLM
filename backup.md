# backup.md - Memory Backup & Restore

**What this does:** Create and restore encrypted backups of your memory system.

---

## [BOT] Config First

**Read `mem.config.json` before running any command:**
- Use `python_path` value for `{PYTHON_PATH}`
- Use `project_name` value for `{PROJECT}`
- Do not guess or substitute different values

---

## Quick Reference

**Secure backup (recommended):**
```sh
{PYTHON_PATH} scripts/backup_secure.py --project {PROJECT} --output backups/backup.zip --prompt
```

**Restore:**
```sh
{PYTHON_PATH} scripts/backup_secure.py --restore backups/backup.zip --prompt
```

---

## Prerequisites

Before backup:
1. [OK] No active writers (scripts running import/store)

Before restore:
1. [!] **STOP all active writers** (sync, import, store scripts)
2. [!] **Take a safety backup** of current state BEFORE restoring
3. [OK] Confirm target path is correct
4. [OK] Verify backup file exists and has non-zero size

---

## Secure Backup

Use `backup_secure.py` for encrypted, portable backups:

```sh
# Backup with password prompt
{PYTHON_PATH} scripts/backup_secure.py --project {PROJECT} --output backups/backup.zip --prompt

# Backup with password from file
{PYTHON_PATH} scripts/backup_secure.py --project {PROJECT} --output backups/backup.zip --password-file tmp/pass.txt

# Restore to staging directory (safe default)
{PYTHON_PATH} scripts/backup_secure.py --restore backups/backup.zip --prompt

# Restore with explicit overwrite
{PYTHON_PATH} scripts/backup_secure.py --restore backups/backup.zip --restore-to memory/ --allow-overwrite --prompt
```

**Features:**
- AES-256 encryption (compatible with 7zip, WinRAR)
- Safe restore to staging directory by default

---

## Commit Hash Password Mode

Instead of remembering a password, use the latest commit SHA from a repo you choose.

**Step 1: Configure your repo (one time)**
```sh
{PYTHON_PATH} scripts/backup_secure.py --project {PROJECT} --set-repo github.com/some-user/obscure-repo

{PYTHON_PATH} scripts/backup_secure.py --project {PROJECT} --show-repo
```

**Step 2: Backup**
```sh
{PYTHON_PATH} scripts/backup_secure.py --project {PROJECT} --output backups/backup.zip --use-commit-hash
```

**Step 3: Restore**
```sh
{PYTHON_PATH} scripts/backup_secure.py --restore backups/backup.zip --use-commit-hash --project {PROJECT}
```

---

## Quick Restore

[!] **DANGER: Restore overwrites current data. Read Prerequisites above first!**

### Step 1: Safety backup
```sh
{PYTHON_PATH} scripts/backup_secure.py --project {PROJECT} --output backups/safety-backup.zip --prompt
```

### Step 2: Restore
```sh
{PYTHON_PATH} scripts/backup_secure.py --restore backups/backup.zip --prompt
```

### Step 3: Verify
```sh
{PYTHON_PATH} scripts/verify_integrity.py --project {PROJECT} --all
```

---

## What Gets Backed Up

**Files backed up:**
- `memory/conversations.db` - SQL database
- `memory/{PROJECT}.graph/` - Graph database folder
- `mem.config.json` - Configuration (optional)

**Total size:** Usually < 10 MB

---

## Verify Backup

After restore, verify integrity:

```sh
{PYTHON_PATH} scripts/verify_integrity.py --project {PROJECT} --all
```

**Success Criteria:**
- [OK] Backup file exists with non-zero size
- [OK] SQL hash chain verification passes
- [OK] Graph proof verification passes

---

## Automated Backups

Use your OS scheduler to run `backup_secure.py` daily.

Example cron entry (daily at 2 AM):
```
0 2 * * * cd /path/to/repo && {PYTHON_PATH} scripts/backup_secure.py --project {PROJECT} --output backups/daily.zip --password-file /secure/pass.txt
```

Replace `{PYTHON_PATH}` and `{PROJECT}` with values from `mem.config.json`.

---

## Troubleshooting

**"File is locked" / "Access denied"**
- Stop all running scripts (import, store, sync)
- Wait a few seconds and retry

**"Backup is empty or corrupted"**
- Check disk space
- Verify source files exist in `memory/` folder

**"Hash chain verification failed after restore"**
- The backup may be incomplete or corrupted
- Restore from a different backup

**"Graph proofs invalid after restore"**
- Ensure the entire `.graph` directory was restored
- Check file permissions on restored files

---

## Anti-Patterns (DO NOT)

| Don't | Why |
|-------|-----|
| Use shell echo for password files | Encoding issues; use agent's file tools |
| Restore without safety backup | Data loss risk |
| Skip verification after restore | May have corrupted data |
