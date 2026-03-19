# verify_document.md - Document Hash Verification

**What this does:** Verify document integrity by checking if the file has been modified since last import.

---

## [BOT] Config First

**Read `mem.config.json` before running any command:**
- Use `python_path` value for `{PYTHON_PATH}`
- Use `project_name` value for `{PROJECT}`
- Do not guess or substitute different values

---

## Purpose

This workflow helps you:
- Detect if a document has been modified
- Verify document integrity
- Track document changes over time
- Ensure imported documents haven't been tampered with

## How It Works

1. Calculates SHA-256 hash of the current file
2. Queries graph database for previous imports of this document
3. Compares current hash with stored hash(es)
4. Reports if document has been modified

---

## Quick Reference

**Replace `{PYTHON_PATH}` and `{PROJECT}` with values from mem.config.json**

```sh
# Verify a document
{PYTHON_PATH} scripts/verify_document.py --project {PROJECT} --file path/to/document.pdf
```

---

## Examples

### Verify a PDF document

```sh
{PYTHON_PATH} scripts/verify_document.py --project {PROJECT} --file docs/whitepaper.pdf
```

**Expected output (unchanged):**
```
Calculating hash for: docs/whitepaper.pdf
Current hash: abc123...

Querying database for previous imports...

================================================================================
VERIFICATION RESULTS
================================================================================

Found 1 previous import(s):

1. Whitepaper - Blockchain Technology
   Imported: 2026-03-09 10:30:00
   Stored hash: abc123...
   [OK] Hash matches - document unchanged

================================================================================
[SUCCESS] Document integrity verified - no changes detected
```

**Expected output (modified):**
```
Calculating hash for: docs/whitepaper.pdf
Current hash: def456...

Querying database for previous imports...

================================================================================
VERIFICATION RESULTS
================================================================================

Found 1 previous import(s):

1. Whitepaper - Blockchain Technology
   Imported: 2026-03-09 10:30:00
   Stored hash: abc123...
   [MODIFIED] Hash mismatch - document has been modified!

================================================================================
[WARNING] Document has been modified since last import!
The file content has changed. Consider re-importing if changes are intentional.
```

---

### Verify a Markdown file

```sh
{PYTHON_PATH} scripts/verify_document.py --project {PROJECT} --file notes/meeting.md
```

---

### Verify document not yet imported

```sh
{PYTHON_PATH} scripts/verify_document.py --project {PROJECT} --file new_document.txt
```

**Expected output:**
```
[NOT FOUND] No previous imports found for 'new_document.txt'
This document has not been imported yet.

To import: {PYTHON_PATH} scripts/import_document.py --project {PROJECT} --file new_document.txt
```

---

## Use Cases

### 1. Verify Document Before Re-Import

Before re-importing a document, check if it has changed:

```sh
# Check if document changed
{PYTHON_PATH} scripts/verify_document.py --project {PROJECT} --file contract.pdf

# If modified, re-import
{PYTHON_PATH} scripts/import_document.py --project {PROJECT} --file contract.pdf
```

---

### 2. Audit Document Integrity

Verify critical documents haven't been tampered with:

```sh
{PYTHON_PATH} scripts/verify_document.py --project {PROJECT} --file legal/agreement.pdf
```

---

### 3. Track Document Versions

Check if a document has been updated since last import:

```sh
{PYTHON_PATH} scripts/verify_document.py --project {PROJECT} --file specs/requirements.md
```

---

## Exit Codes

- **0**: Document unchanged or not found
- **1**: Document has been modified

This allows scripting:

```sh
{PYTHON_PATH} scripts/verify_document.py --project {PROJECT} --file doc.pdf
if [ $? -eq 1 ]; then
    echo "Document modified! Re-importing..."
    {PYTHON_PATH} scripts/import_document.py --project {PROJECT} --file doc.pdf
fi
```

---

## Notes

- Uses SHA-256 hash for verification
- Compares against ALL previous imports (if document was imported multiple times)
- File name matching is case-sensitive
- Only checks documents imported with `import_document.py` (Document entities)

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| "Project not found" | Check project name in config |
| "File not found" | Verify file path is correct |
| "No previous imports" | Document hasn't been imported yet |

---

## Success Criteria

- [OK] Script runs without errors
- [OK] Hash verification completes
- [OK] Correct status reported (unchanged/modified/not found)

---

## Related Workflows

- **Import Document**: `import-documents.md`
- **Query Memory**: `remember.md`

