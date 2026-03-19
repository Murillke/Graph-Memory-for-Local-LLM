"""
OpenTimestamps proof creation using the OFFICIAL Python client code.

This uses the same approach as the official opentimestamps-client:
- Adds random 16-byte nonce to prevent information leakage
- Builds Merkle tree
- Submits to pool servers
- Upgrades from calendar servers

Based on: https://github.com/opentimestamps/opentimestamps-client
"""

import os
import json
import io
import hashlib
from datetime import datetime, timezone

from opentimestamps.core.timestamp import Timestamp, DetachedTimestampFile, make_merkle_tree
from opentimestamps.core.op import OpSHA256, OpAppend
from opentimestamps.core.notary import BitcoinBlockHeaderAttestation
from opentimestamps.core.serialize import StreamSerializationContext, StreamDeserializationContext
from opentimestamps.calendar import RemoteCalendar

# Default pool servers (same as official client)
DEFAULT_CALENDAR_URLS = [
    'https://a.pool.opentimestamps.org',
    'https://b.pool.opentimestamps.org',
    'https://a.pool.eternitywall.com',
    'https://ots.btc.catallaxy.com'
]

# Calendar servers for upgrade (NOT pool servers!)
UPGRADE_CALENDAR_URLS = [
    'https://alice.btc.calendar.opentimestamps.org',
    'https://bob.btc.calendar.opentimestamps.org',
    'https://finney.calendar.eternitywall.com'
]


def _build_proof(
    content_hash,
    timestamp_str,
    proof_mode,
    attestation_status,
    note,
    network_mode=None,
    constraint_reason=None,
    ots_data=None,
    bitcoin_attestation=None,
    submission_error=None
):
    """Build a consistent timestamp proof envelope for all modes."""
    signature = hashlib.sha256(f"{content_hash}{timestamp_str}".encode()).hexdigest()

    proof = {
        'version': '2.0',
        'proof_type': 'timestamp',
        'content_hash': content_hash,
        'timestamp': timestamp_str,
        'signature': signature,
        'proof_mode': proof_mode,
        'attestation_status': attestation_status,
        'note': note
    }

    if network_mode:
        proof['network_mode'] = network_mode
    if constraint_reason:
        proof['constraint_reason'] = constraint_reason
    if ots_data:
        proof['ots_data'] = ots_data
    if bitcoin_attestation:
        proof['bitcoin_attestation'] = bitcoin_attestation
    if submission_error:
        proof['submission_error'] = submission_error

    return json.dumps(proof)


def create_timestamp_proof_official(
    data_hash,
    submit_to_ots=True,
    constrained_environment=False,
    constraint_reason=None
):
    """
    Create a timestamp proof using the OFFICIAL Python client approach.
    
    This mimics what the official `ots stamp` command does:
    1. Create DetachedTimestampFile from hash
    2. Add random 16-byte nonce
    3. Build Merkle tree
    4. Submit to pool servers
    
    Args:
        data_hash: SHA-256 hash (hex string or bytes)
        submit_to_ots: If True, submit to OpenTimestamps calendars
    
    Returns:
        str: JSON-encoded timestamp proof
    """
    # Convert to bytes if needed
    if isinstance(data_hash, str):
        content_hash = data_hash
        hash_bytes = bytes.fromhex(data_hash)
    else:
        content_hash = data_hash.hex()
        hash_bytes = data_hash
    
    timestamp_str = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    
    if not submit_to_ots or constrained_environment:
        note = 'Local timestamp only (OpenTimestamps submission intentionally skipped)'
        return _build_proof(
            content_hash=content_hash,
            timestamp_str=timestamp_str,
            proof_mode='local',
            attestation_status='not_requested',
            note=note,
            network_mode='constrained' if constrained_environment else 'local_only',
            constraint_reason=constraint_reason
        )
    
    try:
        # Step 1: Create DetachedTimestampFile from hash
        # DetachedTimestampFile expects (file_hash_op, Timestamp)
        # We need to create a Timestamp from our hash bytes
        timestamp = Timestamp(hash_bytes)
        file_timestamp = DetachedTimestampFile(OpSHA256(), timestamp)

        # Step 2: Add nonce (CRITICAL - this is what we were missing!)
        # This prevents information leakage about adjacent files
        nonce = os.urandom(16)
        nonce_appended_stamp = file_timestamp.timestamp.ops.add(OpAppend(nonce))
        merkle_root = nonce_appended_stamp.ops.add(OpSHA256())

        # Step 3: Build Merkle tree (for single file, this is just the root)
        # make_merkle_tree expects a list of Timestamp objects
        merkle_roots = [merkle_root]
        merkle_tip = make_merkle_tree(merkle_roots)

        # Step 4: Submit to pool servers
        print(f"[INFO] Submitting to OpenTimestamps pool servers...")

        for calendar_url in DEFAULT_CALENDAR_URLS:
            try:
                calendar = RemoteCalendar(calendar_url)
                # Submit the merkle tip's message (the hash)
                calendar_timestamp = calendar.submit(merkle_tip.msg, timeout=10)
                merkle_tip.merge(calendar_timestamp)
                print(f"[OK] Submitted to {calendar_url}")
            except Exception as e:
                print(f"[WARN] Failed to submit to {calendar_url}: {e}")
        
        # Step 5: Serialize the timestamp to bytes
        timestamp_bytes = io.BytesIO()
        ctx = StreamSerializationContext(timestamp_bytes)
        file_timestamp.serialize(ctx)
        ots_data = timestamp_bytes.getvalue().hex()
        
        # Build proof
        print(f"[SUCCESS] Timestamp created with nonce and Merkle tree!")
        return _build_proof(
            content_hash=content_hash,
            timestamp_str=timestamp_str,
            proof_mode='ots',
            attestation_status='pending',
            note='Submitted to OpenTimestamps pool servers; Bitcoin attestation pending',
            network_mode='online',
            ots_data=ots_data
        )
        
    except Exception as e:
        # Graceful fallback - no traceback for agent-friendly output
        # Common failures: network unreachable, firewall, constrained environment
        error_msg = str(e)
        if "WinError 10061" in error_msg or "Connection refused" in error_msg:
            print(f"[INFO] OpenTimestamps servers unreachable (network constrained); using local timestamp")
        elif "empty timestamp" in error_msg.lower():
            print(f"[INFO] OpenTimestamps submission incomplete (no calendar response); using local timestamp")
        else:
            print(f"[WARN] OpenTimestamps submission failed: {error_msg}; using local timestamp")

        return _build_proof(
            content_hash=content_hash,
            timestamp_str=timestamp_str,
            proof_mode='local',
            attestation_status='submission_failed',
            note='OpenTimestamps submission failed; local timestamp proof retained',
            network_mode='online',
            submission_error=error_msg
        )


def upgrade_timestamp_proof_official(timestamp_proof_json):
    """
    Upgrade a timestamp proof using the OFFICIAL Python client approach.
    
    This mimics what the official `ots upgrade` command does:
    1. Deserialize the timestamp
    2. Query calendar servers (NOT pool servers!)
    3. Merge responses
    4. Check for Bitcoin attestations
    
    Args:
        timestamp_proof_json: JSON-encoded timestamp proof
    
    Returns:
        str: Upgraded proof with Bitcoin attestation, or None if pending
    """
    try:
        proof = json.loads(timestamp_proof_json)
        
        # Check if already has Bitcoin attestation
        if 'bitcoin_attestation' in proof and proof['bitcoin_attestation']:
            return timestamp_proof_json
        
        # Check if proof has OTS data
        if 'ots_data' not in proof:
            print("[INFO] No ots_data to upgrade")
            return None
        
        # Deserialize the timestamp
        ots_bytes = bytes.fromhex(proof['ots_data'])

        # Check if this is a proper DetachedTimestampFile (new format) or raw Timestamp (old buggy format)
        # DetachedTimestampFile starts with magic header: 0x004f70656e54696d657374616d7073...
        # Old buggy format is just raw Timestamp data

        if ots_bytes.startswith(b'\x00OpenTimestamps\x00\x00Proof\x00'):
            # NEW FORMAT: Proper DetachedTimestampFile with magic header
            ctx = StreamDeserializationContext(io.BytesIO(ots_bytes))
            timestamp_file = DetachedTimestampFile.deserialize(ctx)
            timestamp = timestamp_file.timestamp
            content_hash = bytes.fromhex(proof['content_hash'])
        else:
            # OLD BUGGY FORMAT: Raw Timestamp data without magic header
            # Need to deserialize as raw Timestamp
            print("[INFO] Detected old format proof (raw Timestamp), using backward compatibility mode")
            content_hash = bytes.fromhex(proof['content_hash'])
            ctx = StreamDeserializationContext(io.BytesIO(ots_bytes))
            timestamp = Timestamp.deserialize(ctx, content_hash)
            # Create a fake DetachedTimestampFile for compatibility
            timestamp_file = None
        
        # Query CALENDAR servers (NOT pool servers!)
        print(f"[INFO] Querying calendar servers for attestations...")

        changed = False
        for calendar_url in UPGRADE_CALENDAR_URLS:
            try:
                calendar = RemoteCalendar(calendar_url)

                # Get all pending attestations and try to upgrade them
                for sub_stamp in _walk_timestamp(timestamp):
                    try:
                        upgraded_stamp = calendar.get_timestamp(sub_stamp.msg, timeout=10)
                        if upgraded_stamp:
                            sub_stamp.merge(upgraded_stamp)
                            changed = True
                            print(f"[OK] Got upgrade from {calendar_url}")
                    except Exception:
                        pass  # Calendar doesn't have this commitment

            except Exception as e:
                print(f"[WARN] Failed to query {calendar_url}: {e}")
        
        if not changed:
            print("[INFO] No new attestations available")
            return None
        
        # Check for Bitcoin attestations
        bitcoin_attestations = []
        for msg, attestation in timestamp.all_attestations():
            if isinstance(attestation, BitcoinBlockHeaderAttestation):
                bitcoin_attestations.append({
                    'height': attestation.height
                })

        if bitcoin_attestations:
            # Re-serialize the upgraded timestamp
            if timestamp_file:
                # NEW FORMAT: Serialize as DetachedTimestampFile
                timestamp_bytes = io.BytesIO()
                ctx = StreamSerializationContext(timestamp_bytes)
                timestamp_file.serialize(ctx)
                proof['ots_data'] = timestamp_bytes.getvalue().hex()
            else:
                # OLD FORMAT: Serialize as raw Timestamp
                timestamp_bytes = io.BytesIO()
                ctx = StreamSerializationContext(timestamp_bytes)
                timestamp.serialize(ctx)
                proof['ots_data'] = timestamp_bytes.getvalue().hex()

            # Add Bitcoin attestation info
            proof['bitcoin_attestation'] = bitcoin_attestations[0]
            proof['attestation_status'] = 'confirmed'
            proof['proof_mode'] = 'ots'

            print(f"[SUCCESS] Got Bitcoin attestation at block {bitcoin_attestations[0]['height']}!")
            return json.dumps(proof)
        else:
            # Updated but no Bitcoin attestation yet
            if timestamp_file:
                # NEW FORMAT
                timestamp_bytes = io.BytesIO()
                ctx = StreamSerializationContext(timestamp_bytes)
                timestamp_file.serialize(ctx)
                proof['ots_data'] = timestamp_bytes.getvalue().hex()
            else:
                # OLD FORMAT
                timestamp_bytes = io.BytesIO()
                ctx = StreamSerializationContext(timestamp_bytes)
                timestamp.serialize(ctx)
                proof['ots_data'] = timestamp_bytes.getvalue().hex()

            proof['attestation_status'] = 'pending'
            proof['proof_mode'] = 'ots'
            print("[INFO] Timestamp updated but no Bitcoin attestation yet")
            return json.dumps(proof)
        
    except Exception as e:
        # Graceful failure - no traceback for agent-friendly output
        error_msg = str(e)
        if "WinError 10061" in error_msg or "Connection refused" in error_msg:
            print(f"[INFO] OpenTimestamps calendar servers unreachable; upgrade skipped")
        else:
            print(f"[WARN] Failed to upgrade timestamp: {error_msg}")
        return None


def _walk_timestamp(timestamp):
    """Walk all sub-timestamps in a timestamp tree."""
    yield timestamp
    for op, sub_stamp in timestamp.ops.items():
        yield from _walk_timestamp(sub_stamp)
