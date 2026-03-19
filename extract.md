# extract.md - Extract Knowledge from Pending Conversations

**What this does:** Extract entities/facts from conversations that were dumped but not yet processed.

**Use sync.md instead if you're doing dump + extraction in one session.**

---

## [BOT] Config First

**Read `mem.config.json` before running any command:**
- Use `python_path` value for `{PYTHON_PATH}`
- Use `project_name` value for `{PROJECT}`
- Do not guess or substitute different values

---

## Quick Reference

**Step 0:** Prepare files
```sh
{PYTHON_PATH} scripts/prepare_sync_files.py --project {PROJECT} --json
```
Use `extraction_file` from output. Ignore `conversation_file`.

**[!] CRITICAL RULES:**
- **Edit prep-created files in place** - Do NOT recreate with save-file
- **Editable prep-created JSON files are multiline** - match the actual block on disk when editing
- **Copy UUIDs from extract_pending.py** - Do NOT guess or fabricate
- **The skeleton is valid** - Only add extractions to the `"extractions": []` array
- **If JSON gets corrupted** - Re-run prepare_sync_files.py for fresh skeleton

**Hot path:**
```
0. Prepare files                -> prepare_sync_files.py --json
1. Find pending                 -> extract_pending.py
2. Fill extraction file         -> str-replace-editor (use UUIDs from step 1)
3. Validate extraction          -> validate_extraction.py (REQUIRED)
4. Store with quality review    -> store_extraction.py (REQUIRED)
5. Verify                       -> query_memory.py --last 3
```

---

## Step 0: Prepare Files

```sh
{PYTHON_PATH} scripts/prepare_sync_files.py --project {PROJECT} --json
```

Save the `extraction_file` path from output.

---

## Step 1: Find Pending Conversations

```sh
{PYTHON_PATH} scripts/extract_pending.py --project {PROJECT} --limit 5
```

**Expected output:**
```
============================================================
PENDING EXTRACTIONS (3)
============================================================

UUID: uuid-c150208adf13
  Time: 2026-03-03T15:19:21
  User: Hello dude, in here there is a concept...

UUID: uuid-5bfd03e9dc15
  Time: 2026-03-03T16:07:22
  User: Can you tell me how many projects...

============================================================
Copy UUID(s) above into your extraction file's interaction_uuid field
============================================================
```

**Copy the UUIDs** - you'll need them for step 2.

---

## Step 2: Fill Extraction File

Edit the `extraction_file` from Step 0 using str-replace-editor.

Replace `"extractions": []` with your extractions, using the UUIDs from Step 1:
*Example extraction file:*
```json
{
  "project_name": "{PROJECT}",
  "extraction_version": "v1.0.0",
  "extraction_commit": "session-2026-03-13",
  "extractions": [
    {
      "interaction_uuid": "uuid-c150208adf13",
      "entities": [
        {"name": "Entity Name", "type": "Concept", "summary": "Description"}
      ],
      "facts": [
        {
          "source_entity": "Entity Name",
          "target_entity": "Other Entity",
          "relationship_type": "RELATED_TO",
          "fact": "How they relate"
        }
      ]
    }
  ]
}
```

**Entity Rules:**
- Every entity referenced in facts MUST exist in the same extraction's entities list
- Use canonical entity types only. Common examples: `Project`, `Technology`, `Tool`, `Database`, `File`, `Document`, `Config`, `Concept`, `Pattern`, `Task`, `Bug`, `Issue`, `Fix`, `Procedure`
- `Workflow`, `Process`, and `Pipeline` should be written as `Procedure`
- `Configuration` should be written as `Config`

**Fact Rules:**
- `source_entity` and `target_entity` must exactly match names in the SAME extraction block
- Facts cannot reference entities from other extraction blocks
- Use valid `relationship_type` values (common: `USES`, `DEPENDS_ON`, `IMPLEMENTS`, `DOCUMENTS`, `CAUSES`, `RESOLVES`, `RELATED_TO`; full list: `schema/relationship_types.py`)

**Validate early:** Create smallest valid extraction first, run validation, then expand.

---

## Step 3: Validate Extraction (REQUIRED)

```sh
{PYTHON_PATH} scripts/validate_extraction.py --file {EXTRACTION_FILE}
```

**If validation fails:** Add missing entities. Never delete facts to pass validation.

---

## Step 4: Store with Quality Review (REQUIRED)

```sh
{PYTHON_PATH} scripts/store_extraction.py --project {PROJECT} --extraction-file {EXTRACTION_FILE} --require-quality-review --quality-answers-file tmp/quality-answers.json
```

**If quality questions generated:** Check `tmp/quality-questions.json`, answer in `tmp/quality-answers.json`, re-run.

**Example quality answer reasoning:**

For duplicates:
- If duplicate: `"Same entity - already exists with matching description"`
- If NOT duplicate: `"Different concept - this describes X while existing describes Y"`

For contradictions:
- If no contradiction: `"No existing facts about this relationship"`
- If contradiction: `"Contradicts fact-uuid-X which states the opposite"`

---

## Step 5: Verify

```sh
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --last 3
```

---

## If Needed

### Process all pending (no limit)
```sh
{PYTHON_PATH} scripts/extract_pending.py --project {PROJECT} --all
```

### Process specific conversation
```sh
{PYTHON_PATH} scripts/extract_pending.py --project {PROJECT} --uuid uuid-abc123
```

### Entity verification (names with spaces)
```sh
# Edit tmp/entity.txt with entity name (use str-replace-editor)
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --entity-file tmp/entity.txt
```

---

## Anti-Patterns (DO NOT)

| Don't | Why |
|-------|-----|
| **Recreate prep-created files with save-file** | Prep script already created valid skeleton; edit in place |
| **Guess extraction schema from memory** | Use the skeleton from prepare_sync_files.py |
| **Guess or fabricate UUIDs** | Copy from extract_pending.py output |
| Skip validate_extraction.py | Bad schema corrupts data |
| Skip --require-quality-review | Duplicates slip through |
| Use --i-am-a-human-and-i-want-to-skip-quality-checks | AI agents must NEVER use |
| Delete facts to pass validation | Add missing entities instead |

---

## Success Criteria

- [OK] Pending UUIDs found via extract_pending.py
- [OK] Extraction validated
- [OK] Entities/facts stored
- [OK] Quality review handled if triggered
- [OK] Verification passed
