# File Input Standardization Inventory

Status: Phase 3 complete for workflow-facing scripts; deprecated direct query/name flags are disabled by default with legacy override

Purpose: enumerate repo surfaces that document or accept direct query/name inputs so the rollout does not stop in a mixed state.

## Hot Path Surfaces

Updated in this pass:
- `search.md`
- `recall.md`
- `docs/COMMANDS.md`
- `scripts/query_memory.py`
- `scripts/recall.py`

Already aligned or mostly aligned:
- `sync.md`
- `tasks.md`

## Remaining Repo Surfaces Updated In This Pass

Docs:
- `README.md`
- `remember.md`
- `remember-external.md`
- `search-external.md`
- `recall_procedure.md`
- `procedure.md`
- `docs/QUICK-START.md`
- `docs/AI-SEARCH-HELPER.md`
- `docs/shared-database.md`
- `docs/AUGMENT-INTEGRATION-DESIGN.md`
- `WINDOWS-SETUP.md`

Scripts:
- `scripts/detect_contradictions.py`
- `scripts/search_helper.py`
- `scripts/verify_attested_entity.py`
- `scripts/verify_graph_timestamps.py`

## Compatibility-Only Direct Input Surfaces

These still parse direct string flags for backward compatibility, but workflow use is blocked by default and helper-file input is the standard:
- `scripts/query_memory.py`
- `scripts/recall.py`
- `scripts/detect_contradictions.py`
- `scripts/verify_attested_entity.py`
- `scripts/verify_graph_timestamps.py`

Default enforcement now applies to these surfaces.
Legacy/manual override:
- `MEM_ALLOW_DIRECT_INPUT=1`

## Intentionally Not Converted In This Pass

These are either explanatory/historical references, distribution snapshots, unrelated UUID verification, or test coverage:
- `docs/PENDING-CRITICAL-FILE-INPUT-STANDARDIZATION-REVIEW.md`
- `scripts/verify_integrity.py`
- `docs/CRYPTO-PROOFS.md`
- `llm_memory_dist/`
- test fixtures in `tests/`

## Follow-Up

- remove compatibility-only direct flags entirely after the legacy override window closes
- optionally standardize distribution snapshot docs under `llm_memory_dist/` in a separate release-refresh pass
