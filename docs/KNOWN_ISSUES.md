# Known Issues & Technical Debt

**Identified by:** Codex (2026-03-10)
**Last updated:** 2026-03-14
**Status:** Partially addressed

---

## 1. Config Handling Inconsistency - PARTIALLY FIXED

**Problem:** Scripts use different config loading methods.

**Status:** ~75 scripts now use `load_config()` from `tools/config.py`. However:
- ~9 scripts still read `mem.config.json` directly
- Some scripts have hardcoded `./memory/` default paths in argparse

**Remaining work:**
- Migrate remaining scripts to `load_config()`
- Remove hardcoded path defaults

---

## 2. Kuzu Locking / Retry Logic - FIXED ✓

**Problem:** KuzuDB file locking issues with concurrent access.

**Status:** RESOLVED. `tools/db_utils.py` now provides `with_kuzu_retry()` decorator with exponential backoff. Used by graph database operations.

---

## 3. Database Path Ambiguity - LOW PRIORITY

**Problem:** Duplicate graph files (`.kuzu` vs `.graph` extensions).

**Status:** Mostly resolved. Config now uses `{project_name}.graph` convention. Legacy `.kuzu` files may exist from old runs but are not actively created.

**Remaining work:**
- Cleanup script for legacy `.kuzu` files (optional)

---

## 4. Proof/Timestamp Semantics Mixed - OPEN

**Problem:** Multiple proof concepts spread across docs/scripts:
- SQL hash chain integrity
- Extraction/derivation proofs
- Local timestamp proofs
- OTS submission state
- Bitcoin attestation state

**Impact:** Conceptual confusion, harder to understand/maintain.

**Fix needed:**
- Create `docs/PROOF-TYPES.md` with clear hierarchy
- Standardize terminology across all docs

---

## 5. Workflow Correctness - PARTIALLY FIXED

**Problem:** Correctness requires operator knowledge.

**Status:** Improved with examples-on-error pattern added to 12+ scripts. Workflow docs reviewed and updated.

**Remaining work:**
- Add more validation guards in scripts
- Pre-flight checks for common mistakes

---

## 6. Docs/Implementation Drift - PARTIALLY FIXED

**Problem:** Documentation doesn't match code.

**Status:** 16+ workflow docs reviewed and updated (2026-03-13). Path conventions standardized in reviewed docs.

**Remaining work:**
- Periodic review to prevent drift
- Consider doc version timestamps

---

## 7. Cypher String Interpolation - OPEN

**Problem:** Data interpolated directly into Cypher strings:
- Some escaping present but inconsistent
- Brittle with quotes and unusual entity text
- `graph_db.py` and related scripts affected

**Impact:** Edge-case bugs, maintainability issues.

**Fix needed:**
- Use parameterized queries everywhere
- Add escaping utility function
- Audit all Cypher query construction

---

## 8. Uneven Test Coverage - OPEN

**Problem:** Tests exist but don't cover highest-friction workflows:
- End-to-end multi-step sync
- Config resolution edge cases
- Lock contention scenarios

**Fix needed:**
- Add integration tests for full workflows
- Add concurrent access tests

---

## Priority Order (Updated)

1. ~~Kuzu Locking~~ - FIXED
2. **Config Handling** - Partially fixed, finish migration
3. **Cypher Escaping** - Correctness risk
4. **Proof Semantics** - Documentation clarity
5. **Test Coverage** - Long-term quality
6. ~~Workflow Guards~~ - Mostly addressed
7. ~~Docs Drift~~ - Mostly addressed
8. ~~DB Path Ambiguity~~ - Low priority now

---

## Notes

- System is functional and actively used
- Focus on issues that affect agent reliability
- Original review by Codex (2026-03-10), updated after workflow hardening (2026-03-14)

