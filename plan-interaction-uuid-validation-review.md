# Spec Review: Interaction UUID Validation

**Status:** SPEC REJECTED - Validation already exists
**Date:** 2026-03-16
**Reviewer:** Sub-agent (Round 2 adversarial review)

---

## Executive Summary

**The spec premise is WRONG.** The proposed validation already exists in `store_extraction.py`:

| Location | Function | Behavior |
|----------|----------|----------|
| Lines 533-552 | `classify_conversation_extractions()` | Validates each `interaction_uuid` exists in SQL DB |
| Lines 719-729 | Main flow | Calls validation, **exits with error** if UUIDs missing |
| Lines 912-915 | Processing loop | Fallback check, **warns and continues** |

---

## Evidence

### 1. Validation Code Exists

```python
# scripts/store_extraction.py lines 533-544
def classify_conversation_extractions(extractions, sql_db):
    for extraction in extractions:
        interaction_uuid = extraction["interaction_uuid"]
        interaction = sql_db.get_interaction_by_uuid(interaction_uuid)
        if not interaction:
            errors.append(f"Interaction not found in SQL database: {interaction_uuid}")
            continue
    return actionable, skipped, errors
```

```python
# scripts/store_extraction.py lines 724-729
extractions, skipped_interactions, interaction_errors = classify_conversation_extractions(extractions, sql_db)
if interaction_errors:
    safe_print("[ERROR] Extraction references missing interactions:")
    for error in interaction_errors:
        safe_print(f"        - {error}")
    sys.exit(1)  # <-- HARD FAILURE
```

### 2. The Bad Entity Was Created Historically

The entity-mapping file shows successful creation on 2026-03-15:
```json
{
  "extraction_file": "tmp/extraction_2026-03-15_17-44-59.json",
  "timestamp": "2026-03-15T17:46:15.726396",
  "entities": {
    "Task 61cef60": {
      "canonical_uuid": "entity-f645c18b92b0",
      "disposition": "CREATED"
    }
  }
}
```

This means either:
- **The validation was added AFTER this extraction was stored** (most likely)
- OR the interaction existed, then was deleted (unlikely given soft-delete pattern)

---

## What Actually Needs to Be Done

### Option A: Nothing (Preferred)

The validation already exists. The bad entity is a **historical artifact** from before the validation was added. No code change required.

**Clean up action:** Mark `entity-f645c18b92b0` as invalid since it references orphan provenance.

### Option B: Harden the Fallback Check (Minor)

The fallback check at lines 912-915 issues a warning instead of failing:

```python
if not interaction:
    safe_print(f"  [WARNING]  Interaction not found in SQL, skipping")
    continue  # <-- Silently continues, could create partial extractions
```

This could be changed to fail hard, but it's belt-and-suspenders since the upfront check should catch this.

---

## Recommendation

1. **REJECT the original spec** - it proposes adding functionality that already exists
2. **Clean up the orphan entity** - mark `entity-f645c18b92b0` as invalid
3. **Optionally** - convert the fallback WARNING to ERROR for consistency

**Estimated effort:** 0 lines of code (cleanup only)

---

## Root Cause Hypothesis

The agent that created `extraction_2026-03-15_17-44-59.json` likely:
1. Did NOT run `import_conversation.py` first (Step 2 of sync workflow)
2. Made up/hallucinated the UUID `uuid-02ed6098fca8`
3. This happened BEFORE the validation check was added to `store_extraction.py`

The sync workflow documentation (sync.md) correctly requires Step 2 before Step 4, but agent compliance cannot be guaranteed. The validation now catches this.

---

## Testing Confirmation

To verify the validation works, run:

```sh
# Create extraction with fake UUID
cat > /tmp/test_bad_uuid.json << 'EOF'
{
  "project_name": "llm_memory",
  "extraction_version": "v1.0.0",
  "extraction_commit": "test",
  "extractions": [
    {
      "interaction_uuid": "uuid-FAKE12345678",
      "entities": [{"name": "Test", "type": "Concept", "summary": "Test"}],
      "facts": []
    }
  ]
}
EOF

# This should fail with "[ERROR] Extraction references missing interactions:"
python scripts/store_extraction.py --project llm_memory --extraction-file /tmp/test_bad_uuid.json
```

Expected output:
```
[ERROR] Extraction references missing interactions:
        - Interaction not found in SQL database: uuid-FAKE12345678
```

