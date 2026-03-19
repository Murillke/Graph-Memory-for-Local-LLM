# verify.md - Verify Cryptographic Integrity

**What this does:** Verify SQL hash chain, entity extraction proofs, and relationship derivation proofs.

---

## [BOT] Config First

**Read `mem.config.json` before running any command:**
- Use `python_path` value for `{PYTHON_PATH}`
- Use `project_name` value for `{PROJECT}`
- Do not guess or substitute different values

---

## Critical Warning

**[!] DO NOT run `--upgrade` inside an agent session!**

OpenTimestamps upgrade takes 5-30 minutes querying calendar servers. If the user asks for Bitcoin attestations, **print the command** and ask them to run manually:

```
Please run this manually (takes 5-30 minutes):
{PYTHON_PATH} scripts/verify_graph_standalone.py --project {PROJECT} --upgrade
```

**You CAN run:** `verify_integrity.py` (fast, seconds)
**You CANNOT run:** `verify_graph_standalone.py --upgrade` (slow, minutes)

---

## [BOT] Quick Reference

```sh
# Verify everything (recommended)
{PYTHON_PATH} scripts/verify_integrity.py --project {PROJECT} --all

# SQL hash chain only
{PYTHON_PATH} scripts/verify_integrity.py --project {PROJECT} --sql

# Graph proofs only
{PYTHON_PATH} scripts/verify_integrity.py --project {PROJECT} --graph
```

---

## What Gets Verified

| Component | What It Checks |
|-----------|----------------|
| **SQL Hash Chain** | Each interaction has SHA-256 hash linking to previous. Chain is complete, no gaps. |
| **Entity Proofs** | Each entity has extraction_proof with source interactions and hashes. |
| **Relationship Proofs** | Each fact has derivation_proof with source episodes and hashes. |

---

## Verify Everything

```sh
{PYTHON_PATH} scripts/verify_integrity.py --project {PROJECT} --all
```

**Expected output:**
```
[OK] Hash chain verified! (27 interactions)
[OK] All 37 entities verified!
[OK] All 21 relationships verified!

============================================================
[OK] ALL VERIFICATIONS PASSED!
============================================================
```

---

## Verify SQL Hash Chain Only

```sh
{PYTHON_PATH} scripts/verify_integrity.py --project {PROJECT} --sql
```

Checks: Each interaction links to previous via SHA-256 hash. Genesis has null previous_hash.

---

## Verify Graph Proofs Only

```sh
{PYTHON_PATH} scripts/verify_integrity.py --project {PROJECT} --graph
```

Checks: Entity extraction proofs and relationship derivation proofs.

---

## If Needed

### Verify specific entity
```sh
{PYTHON_PATH} scripts/verify_integrity.py --entity entity-abc123
```

### Verify specific relationship
```sh
{PYTHON_PATH} scripts/verify_integrity.py --relationship rel-xyz789
```

### Verbose output
```sh
{PYTHON_PATH} scripts/verify_integrity.py --project {PROJECT} --all --verbose
```

---

## OpenTimestamps Upgrade (User Only)

**[!] Run manually, NOT in agent session!**

This queries calendar servers to get Bitcoin blockchain attestations:

```sh
{PYTHON_PATH} scripts/verify_graph_standalone.py --project {PROJECT} --upgrade
```

**What it does:**
1. Queries OpenTimestamps calendar servers (alice, bob, finney)
2. Merges Bitcoin attestations into proofs
3. Saves upgraded proofs to database

**How often:** Daily for first week, then weekly.

**Why slow:** 3 servers x N proofs = many network requests (5-30 min).

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| "Hash chain broken" | Tampering or corruption | Contact admin |
| "No entities found" | Nothing synced yet | Run sync.md first |
| "Project not found" | Wrong project name | Check spelling |

---

## Success Criteria

- [OK] Hash chain verified
- [OK] Entity proofs verified
- [OK] Relationship proofs verified
- [OK] No tampering detected

