# import-documents.md - Import External Documents

> **[EXPERIMENTAL]** This feature works for basic document import but has limited query support.

**What this does:** Import external documents (PDF, DOCX, TXT, etc.) into the knowledge graph with version tracking.

---

## [BOT] Config First

**Read `mem.config.json` before running any command:**
- Use `python_path` value for `{PYTHON_PATH}`
- Use `project_name` value for `{PROJECT}`
- Do not guess or substitute different values

---

## LLM Instructions

**Quick reference:**
```
1. Read config           -> mem.config.json
2. Create helper files   -> Use save-file tool (NOT echo)
3. Import document       -> import_document.py --file X
4. (Optional) Extract    -> Add --extract flag
```

**[!] For names/summaries with spaces:** Create `tmp/name.txt` and `tmp/summary.txt` using your save-file tool. Do NOT use shell echo.

---

## Basic Import

```sh
{PYTHON_PATH} scripts/import_document.py --project {PROJECT} --file document.pdf
```

Uses filename as document name by default.

---

## Import with Custom Name/Summary

**Step 1:** Create helper files (agent uses save-file tool):
- `tmp/name.txt` - Document name
- `tmp/summary.txt` - Document summary

**Step 2:** Import with file-based input:
```sh
{PYTHON_PATH} scripts/import_document.py --project {PROJECT} --file document.pdf --name-file tmp/name.txt --summary-file tmp/summary.txt
```

---

## Import with Auto-Extraction

```sh
{PYTHON_PATH} scripts/import_document.py --project {PROJECT} --file document.pdf --extract
```

Extracts knowledge using AI after import. Uses `tools.extraction.llm_client.get_default_client()`.

---

## Force Re-Import

```sh
{PYTHON_PATH} scripts/import_document.py --project {PROJECT} --file document.pdf --force
```

Re-imports even if file hash hasn't changed. Useful when extraction logic improves.

---

## Version Tracking Model

Documents are versioned automatically by content hash:

| Action | Result |
|--------|--------|
| First import | Creates version 1 |
| Edit file, re-import | Creates version 2, marks v1 as replaced |
| No changes, re-import | Skips (hash matches) |

**Version metadata:**
- All versions tracked in graph
- Old versions marked `status: "replaced"` with `deleted_at` timestamp
- Only active version entities remain queryable

---

## What It Does

1. Calculates file hash (SHA256)
2. Checks for existing versions by name
3. Skips import if unchanged (unless `--force`)
4. Creates new version if changed
5. Marks old version as replaced
6. Extracts text from document
7. Creates Entity node with `labels=["ExternalSource", "Document"]`
8. Creates OpenTimestamps proof
9. Saves content to `tmp/{uuid}_content.txt`
10. (If `--extract`) Extracts knowledge using AI

---

## Querying Documents

Documents are Entity nodes with `labels` containing "ExternalSource":

```cypher
-- Find all documents
MATCH (doc:Entity)
WHERE doc.group_id = "{PROJECT}"
  AND doc.labels CONTAINS "ExternalSource"
  AND doc.deleted_at IS NULL
RETURN doc.name, doc.summary

-- Find by name
MATCH (doc:Entity)
WHERE doc.group_id = "{PROJECT}"
  AND doc.labels CONTAINS "ExternalSource"
  AND doc.name = "My Document"
RETURN doc
```

---

## Supported Formats

| Format | Extension | Notes |
|--------|-----------|-------|
| Text | `.txt`, `.md`, `.json`, `.xml`, `.csv`, `.py`, `.js`, `.sql`, `.yaml` | Direct read |
| PDF | `.pdf` | Requires PyPDF2 |
| Word | `.docx` | Requires python-docx |

---

## Anti-Patterns (DO NOT)

| Don't | Why |
|-------|-----|
| Use `echo` for helper files | Creates UTF-16 on Windows, breaks scripts |
| Use `--name "multi word"` | Quote escaping unreliable |
| Use `--summary "text"` | Quote escaping unreliable |
| Skip `--force` when re-extracting | Won't update if hash matches |

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| "File not found" | Check path, use absolute if needed |
| "Unsupported format" | Check format list, install PyPDF2/python-docx |
| "Extraction failed" | Check LLM wrapper in config |
| "Hash already exists" | Use `--force` to re-import |

---

## Success Criteria

- [OK] ExternalSource entity created in graph
- [OK] Content saved to `tmp/{uuid}_content.txt`
- [OK] Version tracking works (new version if changed)
- [OK] If `--extract`: entities/facts created

