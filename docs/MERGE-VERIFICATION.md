# Merge Verification and Provenance

How to reason about trust when memory artifacts are imported or merged from
another source.

See [proof-model.md](./proof-model.md) for the canonical proof vocabulary.

---

## Short Answer

Native data is easiest to verify.
Imported data can still be useful, but the trust story changes.

In proof-model terms:
- local SQL history gives you an **integrity proof**
- local graph artifacts give you **derivation proofs**
- imported artifacts may preserve provenance material, but they are not always
  locally re-verifiable against your own SQL history

---

## Native vs Imported

### Native Artifacts

Created from this system's own SQL history.

They can usually be checked locally with:
- SQL integrity proof
- entity derivation proofs
- relationship derivation proofs

### Imported or Merged Artifacts

Created elsewhere, then brought into this environment.

They may preserve:
- source hashes
- source interaction identifiers
- import metadata
- timestamp-proof fields

But local verification depends on what source material is available after import.

---

## Trust Levels

### Highest Trust

Use shared storage instead of merging:
- one shared `conversations.db`
- one graph file per project

This preserves normal local verification behavior.

### Medium Trust

Import graph artifacts while preserving source hashes and import metadata.

This gives:
- traceability
- chain-of-custody style metadata
- partial verification value

But it may not give full local re-verification against your current SQL store.

### Lowest Trust

Import artifacts with no preserved provenance fields.

This weakens:
- derivation confidence
- explainability
- later verification

---

## Recommended Approach

### Prefer Shared Storage

If machines or agents can access the same storage, prefer:

```json
{
  "database": {
    "sql_path": "/shared/memory/conversations.db",
    "graph_path": "/shared/memory/{project_name}.graph"
  }
}
```

This avoids most merge-verification ambiguity.

### Merge Only When Necessary

If you must merge:
- preserve source hashes
- preserve source interaction identifiers
- preserve import metadata
- clearly distinguish imported artifacts from native ones

---

## Practical Verification Model

### What You Can Say About Native Data

- local SQL integrity proof passed
- local entity derivation proofs passed
- local relationship derivation proofs passed

### What You Can Say About Imported Data

- import metadata is intact
- source hashes were preserved
- the artifact came from an external source
- local verification may require access to the source environment

Do not overstate imported data as fully locally verified unless you can actually
reconstruct that verification chain.

---

## Operational Guidance

If the goal is:

- **team collaboration**
  - use shared storage

- **occasional selective transfer**
  - import with explicit provenance metadata

- **continuous bidirectional sync**
  - avoid unless you are ready to manage conflict and provenance complexity

---

## Recommendation

For most setups:
- shared storage is better than merging
- merging is better than silent copy-paste
- provenance-preserving import is better than provenance-free import

---

## See Also

- [MULTI-MACHINE-SETUP.md](./MULTI-MACHINE-SETUP.md)
- [shared-database.md](./shared-database.md)
- [CRYPTO-PROOFS.md](./CRYPTO-PROOFS.md)
- [proof-model.md](./proof-model.md)
