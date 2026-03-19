#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Timestamp Proof System

For now, this creates a simple timestamp proof structure containing:
- The content hash
- The timestamp when created
- A signature (hash of hash + timestamp)

Full OpenTimestamps Bitcoin attestation can be added later when we have
proper calendar server access and Bitcoin node integration.

This provides:
- Proof that we had the data at a specific time
- Tamper detection (signature verification)
- Foundation for future OTS integration
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path
import os
import sys

# Import OFFICIAL Python OpenTimestamps client implementation when available.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
try:
    from tools.timestamp_proof_official import (
        create_timestamp_proof_official,
        upgrade_timestamp_proof_official
    )
    OFFICIAL_OTS_AVAILABLE = True
except ModuleNotFoundError:
    create_timestamp_proof_official = None
    upgrade_timestamp_proof_official = None
    OFFICIAL_OTS_AVAILABLE = False


def create_timestamp_proof(
    data_hash,
    submit_to_ots=True,
    constrained_environment=False,
    constraint_reason=None
):
    """
    Create a timestamp proof for a hash.

    Creates a proof structure and optionally submits to OpenTimestamps.

    NOW USES JAVASCRIPT OPENTIMESTAMPS LIBRARY (the one that actually works!)

    Args:
        data_hash: bytes or hex string of the hash to timestamp
        submit_to_ots: If True, submit to OpenTimestamps calendar servers
        constrained_environment: If True, explicitly skip network timestamping
        constraint_reason: Optional explanation for why external attestation was skipped

    Returns:
        str: JSON-encoded timestamp proof, or None if failed
    """
    # Convert to hex string
    if isinstance(data_hash, bytes):
        content_hash = data_hash.hex()
    else:
        content_hash = data_hash

    timestamp_str = datetime.utcnow().isoformat()

    if not OFFICIAL_OTS_AVAILABLE:
        note = 'OpenTimestamps dependency unavailable; local timestamp proof only'
        network_mode = 'constrained' if constrained_environment else 'local_only'
        status = 'not_requested' if constrained_environment or not submit_to_ots else 'dependency_unavailable'
        signature = hashlib.sha256(f"{content_hash}{timestamp_str}".encode()).hexdigest()
        proof = {
            'version': '2.0',
            'proof_type': 'timestamp',
            'content_hash': content_hash,
            'timestamp': timestamp_str,
            'signature': signature,
            'proof_mode': 'local',
            'attestation_status': status,
            'network_mode': network_mode,
            'note': note,
        }
        if constraint_reason:
            proof['constraint_reason'] = constraint_reason
        return json.dumps(proof)

    # Use OFFICIAL Python OpenTimestamps client implementation
    return create_timestamp_proof_official(
        content_hash,
        submit_to_ots=submit_to_ots,
        constrained_environment=constrained_environment,
        constraint_reason=constraint_reason
    )


def submit_to_opentimestamps(hash_bytes):
    """
    Submit a hash to OpenTimestamps calendar servers using Python library.

    Uses calendar.submit() which properly registers the hash for Bitcoin submission.

    Args:
        hash_bytes: The hash to timestamp (as bytes, must be 32 bytes)

    Returns:
        bytes: Serialized timestamp data, or None if failed
    """
    try:
        from opentimestamps.core.timestamp import Timestamp
        from opentimestamps.core.serialize import StreamSerializationContext
        from opentimestamps.calendar import RemoteCalendar, DEFAULT_AGGREGATORS
        import io

        # Use the official default aggregators (pool servers, not calendar servers!)
        calendars = [RemoteCalendar(url) for url in DEFAULT_AGGREGATORS]

        # Submit to ALL calendars and merge results (like official client does)
        merged_timestamp = None
        success_count = 0

        for calendar in calendars:
            try:
                # Submit hash to calendar - this REGISTERS it for Bitcoin submission
                # Use 10 second timeout like the official client
                timestamp = calendar.submit(hash_bytes, timeout=10)

                if timestamp:
                    print(f"[INFO] Successfully submitted to {calendar.url}")
                    success_count += 1

                    # Merge timestamps from all calendars for redundancy
                    if merged_timestamp is None:
                        merged_timestamp = timestamp
                    else:
                        merged_timestamp.merge(timestamp)

            except Exception as e:
                # Try next calendar
                print(f"[DEBUG] Calendar {calendar.url} failed: {e}")
                continue

        # If at least one calendar succeeded, serialize the merged timestamp
        if merged_timestamp:
            buffer = io.BytesIO()
            ctx = StreamSerializationContext(buffer)
            merged_timestamp.serialize(ctx)
            ots_data = buffer.getvalue()

            print(f"[INFO] Submitted to {success_count}/{len(calendars)} calendars")
            return ots_data

        # All calendars failed
        print(f"[WARN] All OpenTimestamps calendars failed")
        return None

    except Exception as e:
        print(f"[WARN] OpenTimestamps submission error: {e}")
        return None


def verify_timestamp_proof(data_hash, timestamp_proof_json):
    """
    Verify a timestamp proof.

    Checks:
    1. Proof structure is valid
    2. Content hash matches
    3. Signature is valid (hash of content_hash + timestamp)

    Args:
        data_hash: bytes or hex string of the hash
        timestamp_proof_json: JSON-encoded timestamp proof

    Returns:
        tuple: (verified: bool, timestamp: datetime or None, message: str)
    """
    try:
        # Convert hex string if needed
        if isinstance(data_hash, str):
            content_hash = data_hash
        else:
            content_hash = data_hash.hex()

        # Parse proof
        proof = json.loads(timestamp_proof_json)

        # Check structure
        required_fields = ['version', 'content_hash', 'timestamp', 'signature']
        if not all(field in proof for field in required_fields):
            return False, None, "Invalid proof structure"

        # Check content hash matches
        if proof['content_hash'] != content_hash:
            return False, None, "Content hash mismatch"

        # Verify signature
        signature_input = f"{proof['content_hash']}{proof['timestamp']}"
        expected_signature = hashlib.sha256(signature_input.encode()).hexdigest()

        if proof['signature'] != expected_signature:
            return False, None, "Invalid signature - proof may be tampered"

        # Parse timestamp
        try:
            timestamp_dt = datetime.fromisoformat(proof['timestamp'])
        except:
            timestamp_dt = None

        return True, timestamp_dt, f"Verified: proof created at {proof['timestamp']}"

    except json.JSONDecodeError:
        return False, None, "Invalid JSON proof"
    except Exception as e:
        return False, None, f"Verification failed: {e}"


def create_timestamp_proof_for_content(content):
    """
    Create a timestamp proof for content (convenience function).

    Args:
        content: String or bytes to timestamp

    Returns:
        tuple: (content_hash: str, timestamp_proof: str or None)
    """
    # Hash the content
    if isinstance(content, str):
        content_bytes = content.encode('utf-8')
    else:
        content_bytes = content

    content_hash = hashlib.sha256(content_bytes).hexdigest()

    # Create timestamp proof
    timestamp_proof = create_timestamp_proof(content_hash)

    return content_hash, timestamp_proof


def save_timestamp_proof_to_file(timestamp_proof_json, filename):
    """
    Save timestamp proof to a .tsp file.

    Args:
        timestamp_proof_json: JSON-encoded timestamp proof
        filename: Path to save .tsp file

    Returns:
        bool: True if successful
    """
    try:
        with open(filename, 'w') as f:
            f.write(timestamp_proof_json)
        return True
    except Exception as e:
        print(f"[WARN] Failed to save timestamp proof to file: {e}")
        return False


def load_timestamp_proof_from_file(filename):
    """
    Load timestamp proof from a .tsp file.

    Args:
        filename: Path to .tsp file

    Returns:
        str: JSON-encoded timestamp proof, or None if failed
    """
    try:
        with open(filename, 'r') as f:
            return f.read()
    except Exception as e:
        print(f"[WARN] Failed to load timestamp proof from file: {e}")
        return None


def upgrade_timestamp_proof(timestamp_proof_json):
    """
    Try to upgrade a timestamp proof with OpenTimestamps Bitcoin attestation.

    This contacts OpenTimestamps calendar servers to get Bitcoin blockchain
    attestation. If the proof is too recent (< 10 minutes), returns None.

    NOW USES OFFICIAL Python OpenTimestamps client implementation!

    Args:
        timestamp_proof_json: JSON-encoded timestamp proof

    Returns:
        str: Upgraded proof with Bitcoin attestation, or None if pending
    """
    if not OFFICIAL_OTS_AVAILABLE:
        return None

    # Use OFFICIAL Python OpenTimestamps client implementation
    return upgrade_timestamp_proof_official(timestamp_proof_json)


# Old helper functions below are kept for backward compatibility
# but are no longer used by the main functions above

def get_opentimestamps_attestation_DEPRECATED(ots_data_hex, content_hash_hex):
    """
    Try to upgrade OpenTimestamps data and get Bitcoin attestation.

    Uses the Python library to deserialize, upgrade, and parse attestations.

    Args:
        ots_data_hex: Hex-encoded raw timestamp data (from /digest endpoint)
        content_hash_hex: The original content hash that was timestamped

    Returns:
        tuple: (upgraded_ots_hex, attestation_dict) or (None, None) if not ready
    """
    try:
        from opentimestamps.core.timestamp import Timestamp
        from opentimestamps.core.serialize import StreamDeserializationContext, StreamSerializationContext
        from opentimestamps.core.notary import BitcoinBlockHeaderAttestation
        from opentimestamps.calendar import RemoteCalendar
        import io

        # The /digest endpoint returns RAW timestamp data, not a full OTS file
        # We need to deserialize it as a Timestamp object
        ots_data = bytes.fromhex(ots_data_hex)
        content_hash = bytes.fromhex(content_hash_hex)

        # Deserialize the timestamp (raw format from /digest)
        ctx = StreamDeserializationContext(io.BytesIO(ots_data))
        timestamp = Timestamp.deserialize(ctx, content_hash)

        # Try to get upgraded timestamp from CALENDAR servers (NOT pool servers!)
        # Pool servers are for submission, calendar servers are for querying attestations
        calendars = [
            RemoteCalendar('https://alice.btc.calendar.opentimestamps.org'),
            RemoteCalendar('https://bob.btc.calendar.opentimestamps.org'),
            RemoteCalendar('https://finney.calendar.eternitywall.com')
        ]

        upgraded = False
        for calendar in calendars:
            try:
                # get_timestamp(hash) returns updated timestamp with Bitcoin attestations
                new_timestamp = calendar.get_timestamp(content_hash)
                if new_timestamp:
                    # Merge new attestations into our timestamp
                    timestamp.merge(new_timestamp)
                    upgraded = True
                    print(f"[INFO] Got attestations from {calendar.url}")
            except Exception as e:
                # "Not found" means not ready yet, which is normal
                if "Not found" not in str(e):
                    print(f"[DEBUG] Calendar {calendar.url} get_timestamp: {e}")
                continue

        # Check for Bitcoin attestations
        attestations = list(timestamp.all_attestations())
        bitcoin_attestations = [a for a in attestations if isinstance(a, BitcoinBlockHeaderAttestation)]

        if bitcoin_attestations:
            # Got Bitcoin attestation!
            first_attestation = bitcoin_attestations[0]

            # Serialize the upgraded timestamp back (raw format)
            out_ctx = StreamSerializationContext(io.BytesIO())
            timestamp.serialize(out_ctx)
            upgraded_ots_hex = out_ctx.getvalue().hex()

            # Extract block height
            block_height = first_attestation.height if hasattr(first_attestation, 'height') else None

            attestation_dict = {
                'block': block_height,
                'verified': True,
                'attestation_count': len(bitcoin_attestations)
            }

            return upgraded_ots_hex, attestation_dict
        else:
            # No Bitcoin attestation yet
            print("[DEBUG] No Bitcoin attestation found yet")
            return None, None

    except Exception as e:
        print(f"[WARN] Failed to upgrade attestation: {e}")
        import traceback
        traceback.print_exc()
        return None, None


def has_bitcoin_attestation(timestamp_proof_json):
    """
    Check if a timestamp proof has Bitcoin attestation.

    Args:
        timestamp_proof_json: JSON-encoded timestamp proof

    Returns:
        bool: True if has Bitcoin attestation
    """
    try:
        proof = json.loads(timestamp_proof_json)
        return 'bitcoin_attestation' in proof
    except:
        return False


def get_attestation_status(timestamp_proof_json):
    """Get attestation status from a timestamp proof."""
    try:
        proof = json.loads(timestamp_proof_json)
        return proof.get('attestation_status', 'unknown')
    except Exception:
        return 'invalid'
