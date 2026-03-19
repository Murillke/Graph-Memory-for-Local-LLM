# CHECKLIST-SCRIPT-IMPLEMENTATION

> ⚠️ **DO NOT DELETE** - This is a reusable validation tool for ALL script implementations.
> Use this checklist when creating NEW scripts or re-validating EXISTING ones.

**Purpose:** Validate that Python scripts have proper execution guarantees (config handling, DB operations, error messages, CLI args).

**What this checks:** The CODE, not the documentation.

**Derived from:** 100+ sync.md test failures and fixes (2026-03-14)

---

## ✅ PRE-EXECUTION GUARANTEES

| # | Check | Failure If Missing |
|---|-------|-------------------|
| 1 | [ ] Command reads config FIRST via `load_config(project_name=)` | Wrong database, wrong paths |
| 2 | [ ] All file paths derived from config, NOT hardcoded | Files not found, wrong project |
| 3 | [ ] `--project` flag is REQUIRED, not optional | Silent wrong-project writes |
| 4 | [ ] Script validates project exists before proceeding | Cryptic errors later |

---

## ✅ FILE OPERATION GUARANTEES

| # | Check | Failure If Missing |
|---|-------|-------------------|
| 5 | [ ] Workflow template files use the current repo template format (editable JSON written predictably by `prepare_sync_files.py`) | Agents patch the wrong shape |
| 6 | [ ] Help/template JSON matches the current hot-path workflow files and script output | Docs drift from real templates |
| 7 | [ ] All writes use `encoding="utf-8"` | Encoding errors on special chars |
| 8 | [ ] Existing files checked before overwrite (or explicit unlink) | Partial writes, corruption |

---

## ✅ DATABASE OPERATION GUARANTEES

| # | Check | Failure If Missing |
|---|-------|-------------------|
| 9 | [ ] Uses `get_unprocessed_*` by default, `--all` for legacy | Returns stale/processed data |
| 10 | [ ] Marks records as processed AFTER successful operation | Duplicate processing |
| 11 | [ ] Database connections closed in finally block | Lock errors |
| 12 | [ ] Query results checked for empty before proceeding | Index errors on empty |

---

## ✅ VALIDATION GUARANTEES

| # | Check | Failure If Missing |
|---|-------|-------------------|
| 13 | [ ] Relationship types validated against canonical list (30 types) | Invalid type errors |
| 14 | [ ] All entities in facts exist in entities list | "Entity not found" errors |
| 15 | [ ] Error messages include SUGGESTED FIX, not just error | Agent loops on same error |
| 16 | [ ] Empty/optional fields don't fail validation | False validation failures |

---

## ✅ CLI ARGUMENT GUARANTEES

| # | Check | Failure If Missing |
|---|-------|-------------------|
| 17 | [ ] Flag names match documentation EXACTLY | "Unrecognized argument" |
| 18 | [ ] File-backed helper input is supported where the workflow requires it (`--*-file`, batch JSON, temp helpers) | Quote escaping breaks input |
| 19 | [ ] Mutually exclusive groups have clear error messages | Confusing parser errors |
| 20 | [ ] Help text shows EXACT usage example | Agent guesses wrong |
| 20a | [ ] Agent-facing help does not document deprecated direct query/name inputs as the primary workflow | Agent uses rejected flags |

---

## ✅ QUALITY REVIEW GUARANTEES (if applicable)

| # | Check | Failure If Missing |
|---|-------|-------------------|
| 21 | [ ] Quality review is REQUIRED - blocks storage until answered | Duplicates slip through |
| 21a | [ ] Quality answers structurally match questions (indices, required fields) | Malformed/stale answers bypass review |
| 21b | [ ] Quality answers `_questions_hash` matches questions hash | Stale answers from previous run accepted |
| 21c | [ ] `is_duplicate=true` requires `duplicate_uuid` | Duplicate marked but no target UUID |
| 22 | [ ] Quality questions written to predictable path | Agent can't find questions |
| 23 | [ ] Quality answers template is valid JSON | Parse errors |
| 24 | [ ] Re-running command with answers file works | Workflow breaks mid-step |
| 24a | [ ] AI-only flows do NOT rely on human-only skip flags | Agent violates workflow contract |

---

## ✅ VERIFICATION GUARANTEES

| # | Check | Failure If Missing |
|---|-------|-------------------|
| 25 | [ ] Verification uses UUID (`--entity-uuid`), not bare name | Ambiguous lookup returns wrong entity |
| 25a | [ ] Read-path lookup is project-scoped | Cross-project name collision |
| 25b | [ ] Read-path fails loudly on duplicate same-name matches | Silent wrong-entity return |
| 25c | [ ] Entity mapping output shows disposition (CREATED/REUSED/ALIASED) | Can't verify what actually happened |
| 25d | [ ] Verification language is scoped to what the script actually proved | Overstated verification claims |

---

## ✅ DOCUMENTATION GUARANTEES

| # | Check | Failure If Missing |
|---|-------|-------------------|
| 26 | [ ] DO NOT IMPROVISE banner at top of workflow doc | Agent invents wrong approach |
| 27 | [ ] `_help_*` fields generated from canonical source, not hardcoded | Help drifts from validator |
| 28 | [ ] Single source of truth for valid values | Multiple lists drift independently |
| 29 | [ ] Common errors table with exact error → fix mapping | Agent wastes time debugging |
| 30 | [ ] Working code sample for EVERY operation | Agent guesses syntax |
| 31 | [ ] Line numbers specified for multiline str_replace | Wrong line range errors |
| 31a | [ ] Command docs and script help agree on file-backed inputs, quality-review flags, and constrained-environment requirements | Docs and code diverge |

---

## ✅ AGENT BEHAVIOR GUARANTEES

| # | Check | Failure If Missing |
|---|-------|-------------------|
| 32 | [ ] Workflow doc says "view file before editing" | Blind edits fail |
| 33 | [ ] Workflow doc says "copy commands exactly" | Flag name errors |
| 34 | [ ] Pre-flight checklist with checkboxes at top of workflow doc | Agent skips steps |
| 35 | [ ] Time estimate ("2-3 min if follow, 10+ if improvise") | Agent doesn't realize they're failing |
| 36 | [ ] Network-sensitive commands explicitly tell the agent when to use `--constrained-environment` | Wrong timestamp/attestation mode |

---

## 📋 CANONICAL RELATIONSHIP TYPES (Reference)

Generated from `schema/relationship_types.py` - single source of truth.
See `_help_relationship_types` in extraction templates for categorized list.

---

## 📋 FAILURE → FIX QUICK REFERENCE

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `Invalid relationship type 'X'` | Invented type | Use only 30 canonical types |
| `target_entity 'X' not found` | Missing entity | Add entity to entities list |
| `unrecognized arguments: --extraction-file` | Wrong flag | Use `--file` not `--extraction-file` |
| `No replacement was performed` | Didn't view file / wrong line range | View file first, match exact content |
| `Duplicate check failed` | Didn't fill quality-answers.json | Fill the answers file |
| `File already exists` | Used save-file on existing | Use str-replace-editor |
| `No unprocessed interactions` | Already processed | Use `--all` or capture UUID from import |
| `Quality review required` | Missing flag | Add `--require-quality-review` |

---

## 🔄 HOW TO USE THIS CHECKLIST

**When implementing a NEW hot path command:**
1. Go through checks 1-33
2. Each unchecked item = potential failure mode
3. Fix before releasing

**When debugging a FAILING hot path:**
1. Find the error in "FAILURE → FIX" table
2. Check which guarantee was violated
3. Fix the implementation

**When adding to an EXISTING hot path:**
1. Re-verify affected guarantees
2. Update documentation to match
3. Test with fresh agent
