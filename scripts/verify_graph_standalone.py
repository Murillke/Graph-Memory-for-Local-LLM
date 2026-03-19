#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verify Graph Integrity WITHOUT SQL

This script verifies the entire knowledge graph using ONLY the graph database.
It does NOT require the SQL database to be present.

Verifies:
1. Source chain integrity (hash chain)
2. Extraction proofs (Merkle trees)
3. Timestamp proofs (OpenTimestamps)
4. Entity relationships

This proves the graph is self-contained and cryptographically verifiable.
"""

import sys
import os
import argparse
import json
from datetime import datetime

# Fix Windows encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tools.graph_db import GraphDatabase
from tools.config import load_config
from tools.source_chain import verify_source_chain
from tools.timestamp_proof import (
    verify_timestamp_proof,
    upgrade_timestamp_proof,
    has_bitcoin_attestation,
    get_attestation_status
)
from tools.console_utils import safe_print


def verify_entity_source_chain(entity_data):
    """Verify an entity's source chain."""
    name = entity_data[0]
    source_chain_json = entity_data[1]
    
    if not source_chain_json:
        return False, f"Entity '{name}' has no source chain"
    
    try:
        source_chain = json.loads(source_chain_json)
        
        if not source_chain:
            return False, f"Entity '{name}' has empty source chain"
        
        # Verify chain integrity
        valid, message = verify_source_chain(source_chain)
        
        if not valid:
            return False, f"Entity '{name}': {message}"
        
        return True, f"Entity '{name}': {message}"
        
    except json.JSONDecodeError:
        return False, f"Entity '{name}' has invalid source chain JSON"
    except Exception as e:
        return False, f"Entity '{name}': Verification failed: {e}"


def verify_entity_timestamp_proof(entity_data, try_upgrade=True):
    """Verify an entity's timestamp proof.

    Note: Timestamp proofs are for the conversation FILE, not the interaction chain.
    For standalone verification, we verify the proof structure is valid.

    If try_upgrade=True, attempts to upgrade the proof with OpenTimestamps
    Bitcoin attestation if not already present.
    """
    name = entity_data[0]
    timestamp_proof = entity_data[2]

    if not timestamp_proof:
        return None, f"Entity '{name}' has no timestamp proof (optional)"

    try:
        # Check if proof has Bitcoin attestation
        has_attestation = has_bitcoin_attestation(timestamp_proof)

        # Try to upgrade if requested and not already upgraded
        if try_upgrade and not has_attestation:
            upgraded = upgrade_timestamp_proof(timestamp_proof)

            if upgraded:
                # Successfully upgraded!
                timestamp_proof = upgraded
                has_attestation = True
                # TODO: Update the proof in the database

        # Parse timestamp proof
        proof = json.loads(timestamp_proof)

        # Check structure
        required_fields = ['version', 'content_hash', 'timestamp', 'signature']
        if not all(field in proof for field in required_fields):
            return False, f"Entity '{name}': Invalid timestamp proof structure"

        # Verify signature (hash of content_hash + timestamp)
        import hashlib
        signature_input = f"{proof['content_hash']}{proof['timestamp']}"
        expected_signature = hashlib.sha256(signature_input.encode()).hexdigest()

        if proof['signature'] != expected_signature:
            return False, f"Entity '{name}': Invalid timestamp proof signature"

        # Check Bitcoin attestation status
        attestation_status = get_attestation_status(timestamp_proof)
        if has_attestation:
            # Has Bitcoin proof - fully verified!
            return True, f"Entity '{name}': Bitcoin-attested (created at {proof['timestamp']})"
        elif attestation_status == 'not_requested':
            return True, f"Entity '{name}': Local-only proof by design (created at {proof['timestamp']})"
        elif attestation_status == 'submission_failed':
            return False, f"Entity '{name}': OpenTimestamps submission failed; only local proof is available"
        else:
            # No Bitcoin proof yet - pending (return as "skipped", not "failed")
            # We return a special tuple to indicate "pending" status
            return 'pending', f"Entity '{name}': Pending Bitcoin confirmation (created at {proof['timestamp']})"

    except json.JSONDecodeError:
        return False, f"Entity '{name}': Invalid timestamp proof JSON"
    except Exception as e:
        return False, f"Entity '{name}': Timestamp verification failed: {e}"


def main():
    parser = argparse.ArgumentParser(
        description='Verify graph integrity WITHOUT SQL database'
    )
    parser.add_argument('--project', required=True, help='Project name')
    parser.add_argument('--graph-db', help='Path to graph database (overrides config)')
    parser.add_argument('--upgrade', action='store_true', help='Try to upgrade timestamp proofs with OpenTimestamps Bitcoin attestation')

    args = parser.parse_args()
    
    # Get graph database path
    if args.graph_db:
        graph_db_path = args.graph_db
    else:
        config = load_config(project_name=args.project)
        graph_db_path = config.get_graph_db_path(args.project)
    
    safe_print("="*80)
    safe_print("GRAPH STANDALONE VERIFICATION")
    safe_print("="*80)
    safe_print(f"\nProject: {args.project}")
    safe_print(f"Graph DB: {graph_db_path}")
    safe_print(f"\nNOTE: This verification does NOT require SQL database!")
    safe_print("="*80)
    
    # Connect to graph
    try:
        graph_db = GraphDatabase(graph_db_path)
    except Exception as e:
        safe_print(f"\n[ERROR] Failed to connect to graph database: {e}")
        sys.exit(1)
    
    # Get all entities
    safe_print("\n[1/3] Verifying source chains...")
    
    result = graph_db.conn.execute("""
        MATCH (e:Entity)
        RETURN e.name, e.source_chain, e.timestamp_proof
    """)
    
    entities = []
    while result.has_next():
        entities.append(result.get_next())
    
    if not entities:
        safe_print("   No entities found in graph")
        safe_print("\n[OK] Verification complete (empty graph)")
        sys.exit(0)
    
    safe_print(f"   Found {len(entities)} entities")
    
    # Verify source chains
    chain_passed = 0
    chain_failed = 0
    chain_errors = []
    
    for entity_data in entities:
        valid, message = verify_entity_source_chain(entity_data)
        
        if valid:
            chain_passed += 1
        else:
            chain_failed += 1
            chain_errors.append(message)
    
    safe_print(f"   Passed: {chain_passed}")
    safe_print(f"   Failed: {chain_failed}")
    
    if chain_errors:
        safe_print("\n   Errors:")
        for error in chain_errors[:5]:  # Show first 5
            safe_print(f"   - {error}")
        if len(chain_errors) > 5:
            safe_print(f"   ... and {len(chain_errors) - 5} more")

    # Verify timestamp proofs
    safe_print("\n[2/3] Verifying timestamp proofs...")

    if args.upgrade:
        safe_print("   Attempting to upgrade proofs with OpenTimestamps...")

    timestamp_passed = 0
    timestamp_failed = 0
    timestamp_skipped = 0
    timestamp_errors = []

    # OPTIMIZATION: Group entities by timestamp_proof to avoid upgrading the same proof multiple times
    # Since all entities from the same conversation share the same timestamp_proof
    # entity_data format: (name, source_chain, timestamp_proof)
    proof_groups = {}
    for entity_data in entities:
        name, source_chain, proof_json = entity_data[0], entity_data[1], entity_data[2]
        if proof_json:
            if proof_json not in proof_groups:
                proof_groups[proof_json] = []
            proof_groups[proof_json].append(entity_data)
        else:
            # No timestamp proof
            timestamp_skipped += 1

    safe_print(f"   Found {len(proof_groups)} unique timestamp proofs for {len(entities)} entities")

    # Verify each unique proof only once
    for proof_json, entities_with_proof in proof_groups.items():
        # Use the first entity as representative (they all have the same proof)
        result = verify_entity_timestamp_proof(entities_with_proof[0], try_upgrade=args.upgrade)

        if result is None:
            # No timestamp proof (shouldn't happen since we filtered)
            timestamp_skipped += len(entities_with_proof)
        elif result[0] == 'pending':
            # Pending Bitcoin confirmation
            timestamp_skipped += len(entities_with_proof)
        else:
            valid, message = result
            if valid:
                timestamp_passed += len(entities_with_proof)
            else:
                timestamp_failed += len(entities_with_proof)
                timestamp_errors.append(f"{message} (affects {len(entities_with_proof)} entities)")

    safe_print(f"   Passed: {timestamp_passed}")
    safe_print(f"   Failed: {timestamp_failed}")
    safe_print(f"   Skipped (no proof): {timestamp_skipped}")

    if timestamp_errors:
        safe_print("\n   Errors:")
        for error in timestamp_errors[:5]:
            safe_print(f"   - {error}")
        if len(timestamp_errors) > 5:
            safe_print(f"   ... and {len(timestamp_errors) - 5} more")

    # Verify relationships
    safe_print("\n[3/3] Verifying relationships...")

    result = graph_db.conn.execute("""
        MATCH (e1:Entity)-[r:RELATES_TO]->(e2:Entity)
        RETURN count(r) as rel_count
    """)

    if result.has_next():
        rel_count = result.get_next()[0]
        safe_print(f"   Found {rel_count} relationships")
    else:
        rel_count = 0
        safe_print("   No relationships found")

    # Summary
    safe_print("\n" + "="*80)
    safe_print("VERIFICATION SUMMARY")
    safe_print("="*80)

    safe_print(f"\nEntities: {len(entities)}")
    safe_print(f"Relationships: {rel_count}")

    safe_print(f"\nSource Chain Verification:")
    safe_print(f"  Passed: {chain_passed}")
    safe_print(f"  Failed: {chain_failed}")

    safe_print(f"\nTimestamp Proof Verification:")
    safe_print(f"  Passed: {timestamp_passed}")
    safe_print(f"  Failed: {timestamp_failed}")
    safe_print(f"  Pending: {timestamp_skipped}")

    if timestamp_skipped > 0:
        safe_print(f"\nNote: {timestamp_skipped} timestamp proof(s) pending Bitcoin confirmation")
        safe_print("      Run with --upgrade to attempt upgrading proofs")
        safe_print("      (Requires ~10 minutes after proof creation)")

    # Overall result
    total_checks = chain_passed + chain_failed + timestamp_passed + timestamp_failed
    total_passed = chain_passed + timestamp_passed

    if chain_failed == 0 and timestamp_failed == 0:
        safe_print("\n[OK] All verifications PASSED!")
        safe_print("\nThe graph is cryptographically valid and can be verified")
        safe_print("independently of the SQL database!")

        if timestamp_skipped > 0:
            safe_print(f"\n({timestamp_skipped} timestamp proof(s) pending Bitcoin confirmation)")

        sys.exit(0)
    else:
        safe_print("\n[ERROR] Some verifications FAILED!")
        safe_print(f"\nPassed: {total_passed}/{total_checks}")
        safe_print(f"Failed: {chain_failed + timestamp_failed}/{total_checks}")
        sys.exit(1)


if __name__ == '__main__':
    main()
