# Proof Model

## Purpose

This document is the canonical vocabulary for what the memory system proves,
and what it does **not** prove.

Use it when interpreting verification output or making trust claims.

---

## Proof Taxonomy

This is the canonical terminology for the repo. Other docs should qualify
"proof" using one of the terms below rather than using the word generically.

| Term | Proves | Scope |
|------|--------|-------|
| **Integrity proof** | Append-only interaction history | SQL hash chain |
| **Derivation proof** | Entity or fact was derived from specific source hashes | Graph entities and relationships |
| **Timestamp proof** | A content hash was locally signed at a claimed time | Per proof-bearing artifact |
| **External attestation** | A timestamp proof was anchored externally | OpenTimestamps / Bitcoin |

---

## 1. Integrity Proof

**Implemented by:** SQL hash chain in `interactions`

**Proves:**
- interactions have not been modified
- interactions have not been reordered
- interactions have not been deleted from the middle of the chain without detection

**Does not prove:**
- that the interaction was externally timestamped
- that the graph extraction was correct
- that the content is semantically true

---

## 2. Derivation Proof

**Implemented by:**
- `extraction_proof` on entities
- `derivation_proof` on relationships

**Proves:**
- the stored entity/fact was tied to specific source hashes
- the graph artifact can be checked against those source hashes later

**Does not prove:**
- that the extraction logic was "correct" in a human sense
- that the source hashes themselves were externally attested
- that the fact is still current unless temporal fields also support that interpretation

---

## 3. Timestamp Proof

**Implemented by:** `timestamp_proof`

**Proves:**
- a content hash was locally signed at a claimed timestamp
- the proof payload has not been tampered with if signature verification passes

**Does not prove by itself:**
- that a Bitcoin anchor exists
- that an OpenTimestamps submission succeeded
- that the timestamp is trustless

Think of this as a **local timestamp claim with tamper evidence**.

---

## 4. External Attestation

**Implemented by:** OpenTimestamps submission state and later Bitcoin attestation state

**Proves:**
- the timestamp proof was anchored externally
- once confirmed, the content hash existed no later than the attested blockchain time

**Does not prove:**
- that extraction/derivation logic was correct
- that the SQL chain is intact unless that is verified separately

Think of this as a **trust upgrade for timestamp claims**, not a replacement
for integrity or derivation verification.

---

## Verification Layers

### `verify_integrity.py`

Verifies:
- SQL **integrity proof**
- graph **derivation proofs**

It does **not** primarily answer whether something is Bitcoin-attested.

### `verify_graph_standalone.py`

Verifies:
- graph-internal source-chain consistency
- graph **timestamp proof** structure
- external attestation status when available

It does **not** prove the original SQL interaction history unless SQL is also
verified separately.

---

## Common Misunderstandings

**"Verified" does not always mean Bitcoin-attested.**
- A derivation proof can verify even when timestamp proof is only local.

**A timestamp proof is not the same as an external attestation.**
- Local signature: yes
- Bitcoin anchor: maybe not

**Standalone graph verification is not the same as full-history verification.**
- It proves graph-contained evidence is internally coherent.
- It does not prove the original SQL history unless that chain is also checked.

---

## Trust Claims

Safe claims:
- "The SQL interaction history passed integrity verification."
- "This entity/fact passed derivation verification."
- "This timestamp proof is locally valid."
- "This proof has external OpenTimestamps / Bitcoin attestation."

Unsafe claims:
- "Verified" without saying which layer
- "Bitcoin-proven" when only local timestamp proof exists
- "History-proven" when only standalone graph verification was run

---

## See Also

- [timestamp-proofs.md](./timestamp-proofs.md)
- [sync.md](../sync.md)
- [dump.md](../dump.md)
