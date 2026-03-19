# Timestamp Proofs

See [proof-model.md](./proof-model.md) for the canonical proof taxonomy. This
document covers **timestamp proofs** and their optional **external
attestation** state.

## Overview

The LLM Memory system includes a timestamp proof system that provides a
tamper-evident local timestamp claim for a content hash.

By itself, a timestamp proof does **not** prove external anchoring. That
stronger claim belongs to **external attestation** via OpenTimestamps and, when
available, Bitcoin confirmation.

## How It Works

### Proof Structure

Each timestamp proof is a JSON object containing:

```json
{
  "version": "2.0",
  "proof_type": "timestamp",
  "content_hash": "abc123...",
  "timestamp": "2026-03-07T19:00:30.244747",
  "signature": "def456...",
  "proof_mode": "ots",
  "attestation_status": "pending",
  "note": "Submitted to OpenTimestamps pool servers; Bitcoin attestation pending"
}
```

**Fields:**
- `version` - Proof format version
- `proof_type` - Currently `"timestamp"`
- `content_hash` - SHA256 hash of the content being timestamped
- `timestamp` - ISO 8601 timestamp when proof was created
- `signature` - SHA256 hash of (content_hash + timestamp) for tamper detection
- `proof_mode` - `"ots"` for OpenTimestamps-backed proofs, `"local"` for local-only proofs
- `attestation_status` - `"pending"`, `"confirmed"`, `"not_requested"`, or `"submission_failed"`
- `note` - Human-readable description

Optional fields:
- `network_mode` - `"online"`, `"constrained"`, or `"local_only"`
- `constraint_reason` - Why external attestation was intentionally skipped
- `ots_data` - Serialized OpenTimestamps payload
- `bitcoin_attestation` - Bitcoin block attestation when available
- `submission_error` - Error details if OpenTimestamps submission failed

### Verification

To verify a timestamp proof:

1. **Check structure** - Ensure all required fields are present
2. **Verify content hash** - Hash matches the data
3. **Verify signature** - SHA256(content_hash + timestamp) matches signature

If all checks pass, the timestamp proof is locally valid and demonstrates:
- The proof payload has not been tampered with
- The content hash matches the signed payload
- The system recorded a local timestamp claim for that content hash

### Storage

Timestamp proofs are stored in:

**SQL Database (`conversations.db`):**
- `interactions.timestamp_proof` - Proof for the conversation file
- `interactions.file_hash` - Hash of the conversation file

**Graph Database (`{project}.graph`):**
- `Entity.timestamp_proof` - Proof for entity creation
- `RELATES_TO.timestamp_proof` - Proof for relationship creation

## Usage

### Automatic Generation

Timestamp proofs are automatically generated when:
- Importing conversations (`import_conversation.py`)
- Storing extractions (`store_extraction.py`)

### Manual Verification

```python
from tools.timestamp_proof import verify_timestamp_proof

# Verify a proof
verified, timestamp, message = verify_timestamp_proof(
    data_hash="abc123...",
    timestamp_proof_json='{"version": "1.0", ...}'
)

if verified:
    print(f"Verified: {message}")
    print(f"Timestamp: {timestamp}")
else:
    print(f"Failed: {message}")
```

### Creating Proofs

```python
from tools.timestamp_proof import create_timestamp_proof_for_content

# Create proof for content
content_hash, timestamp_proof = create_timestamp_proof_for_content(
    "This is my content"
)

print(f"Hash: {content_hash}")
print(f"Proof: {timestamp_proof}")
```

## External Attestation

Timestamp proofs can optionally be upgraded with external attestation.

- `proof_mode = "local"` means no OpenTimestamps submission was used
- `proof_mode = "ots"` means the proof carries OpenTimestamps-related state
- `attestation_status = "pending"` means submission happened but Bitcoin-level confirmation is not available yet
- `attestation_status = "confirmed"` means external attestation is available
- `attestation_status = "not_requested"` means the system intentionally stayed local-only
- `attestation_status = "submission_failed"` means an external upgrade was attempted but did not complete

Do not collapse these states into a generic "verified" claim.

## OpenTimestamps Integration

The current implementation supports local timestamp proofs and tracks
OpenTimestamps-related state when available.

**Constrained environments:** If a runtime cannot make outbound network requests, use:

```bash
python scripts/import_conversation.py --project llm_memory --file tmp/conversation.json --constrained-environment --constraint-reason "No outbound network access in this runtime"
```

This still creates a tamper-evident local timestamp proof, but the proof is
explicitly marked as local-only so later verification can distinguish:
- intentionally local-only
- pending Bitcoin confirmation
- network submission failure
- fully confirmed Bitcoin attestation

**Migration path:**
1. Current proofs remain valid
2. Add OpenTimestamps calendar server submission
3. Upgrade proofs with Bitcoin attestations
4. Maintain backward compatibility

## Security Properties

### Current Implementation

- **Tamper Detection** - Signature verification detects modifications
- **Hash Chain** - Interactions link via `previous_hash`
- **Merkle Tree** - Entities link via parent hashes
- **Trust Required** - Local timestamp proofs are not externally attested by default

### With External Attestation

- **Tamper Detection** - Signature verification
- **Hash Chain** - Interaction linking
- **Merkle Tree** - Entity linking
- **External Attestation** - OpenTimestamps / Bitcoin can anchor the timestamp claim
- **Publicly Verifiable** - Anyone can verify the attested timestamp claim

## Verification Scripts

### Verify All Timestamps (Requires SQL)

```bash
python scripts/verify_integrity.py --project llm_memory
```

### Verify Graph Timestamps (Requires SQL)

```bash
python scripts/verify_graph_timestamps.py --project llm_memory
```

### Verify Graph Standalone (NO SQL Required!)

```bash
python scripts/verify_graph_standalone.py --project llm_memory
```

**This script verifies the graph WITHOUT needing the SQL database!**

Verifies:
- Source chain integrity (hash chain)
- Timestamp proof structure
- External attestation status when present
- Entity relationships
- Complete cryptographic verification

**Use this to prove your graph is valid even if SQL is deleted!**

### Verify with OpenTimestamps Upgrade

```bash
python scripts/verify_graph_standalone.py --project llm_memory --upgrade
```

**With `--upgrade` flag:**
- Attempts to upgrade timestamp proofs with Bitcoin attestation
- Contacts OpenTimestamps calendar servers
- Gets Bitcoin blockchain proof (if enough time has passed)
- Shows `pending` if it is too soon

**This upgrades local timestamp claims with external attestation when possible.**

## Technical Details

### Proof Generation

```python
def create_timestamp_proof(data_hash):
    timestamp = datetime.now().isoformat()
    signature = sha256(data_hash + timestamp)

    return {
        "version": "1.0",
        "content_hash": data_hash,
        "timestamp": timestamp,
        "signature": signature,
    }
```

### Proof Verification

```python
def verify_timestamp_proof(data_hash, proof):
    # Check structure
    if not all_fields_present(proof):
        return False

    # Verify hash
    if proof["content_hash"] != data_hash:
        return False

    # Verify signature
    expected = sha256(proof["content_hash"] + proof["timestamp"])
    if proof["signature"] != expected:
        return False

    return True
```

## See Also

- [proof-model.md](./proof-model.md)
- [CRYPTO-PROOFS.md](./CRYPTO-PROOFS.md)
