"""
Verify ownership proof.

Verifies Merkle proofs without needing access to original data.
"""

import argparse
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.merkle_tree import MerkleTree


def verify_ownership_proof(proof: dict, sql_db_path: str = None) -> bool:
    """
    Verify ownership proof.

    If sql_db_path is provided, verifies the merkle root matches the actual data.
    If not provided, only checks proof structure (portable verification).

    Args:
        proof: Ownership proof dict
        sql_db_path: Optional path to SQL database for full verification

    Returns:
        True if valid, False otherwise
    """
    required_fields = ['project_name', 'merkle_root', 'interaction_count', 'timestamp']

    for field in required_fields:
        if field not in proof:
            print(f"[ERROR] Missing required field: {field}")
            return False

    print(f"[INFO] Project: {proof['project_name']}")
    print(f"[INFO] Merkle Root: {proof['merkle_root']}")
    print(f"[INFO] Interaction Count: {proof['interaction_count']}")
    print(f"[INFO] Timestamp: {proof['timestamp']}")

    if 'earliest_interaction' in proof:
        print(f"[INFO] Earliest: {proof['earliest_interaction']}")
    if 'latest_interaction' in proof:
        print(f"[INFO] Latest: {proof['latest_interaction']}")

    # If database path provided, do FULL verification
    if sql_db_path:
        from tools.sql_db import SQLDatabase

        print(f"[INFO] Verifying against database: {sql_db_path}")

        db = SQLDatabase(sql_db_path)
        interactions = db.get_all_interactions(proof['project_name'])

        # Check interaction count
        if len(interactions) != proof['interaction_count']:
            print(f"[ERROR] Interaction count mismatch: proof says {proof['interaction_count']}, DB has {len(interactions)}")
            return False

        # Regenerate merkle root from actual data
        if len(interactions) > 0:
            hashes = [i['content_hash'] for i in interactions]
            tree = MerkleTree(hashes)
            actual_root = tree.root

            if actual_root != proof['merkle_root']:
                print(f"[ERROR] Merkle root mismatch!")
                print(f"[ERROR] Claimed: {proof['merkle_root']}")
                print(f"[ERROR] Actual:  {actual_root}")
                return False

            print(f"[SUCCESS] Merkle root verified against database!")

        print(f"[SUCCESS] Full ownership proof verified!")
    else:
        print(f"[WARNING] No database provided - only checking proof structure")
        print(f"[SUCCESS] Ownership proof is well-formed (not verified against data)")

    return True


def verify_entity_proof(proof: dict) -> bool:
    """
    Verify entity extraction proof.
    
    Args:
        proof: Entity proof dict
    
    Returns:
        True if valid, False otherwise
    """
    required_fields = ['entity', 'merkle_root', 'source_proofs']
    
    for field in required_fields:
        if field not in proof:
            print(f"[ERROR] Missing required field: {field}")
            return False
    
    print(f"[INFO] Entity: {proof['entity']}")
    print(f"[INFO] Merkle Root: {proof['merkle_root']}")
    print(f"[INFO] Source Proofs: {len(proof['source_proofs'])}")
    
    # Verify each source proof
    for i, source_proof in enumerate(proof['source_proofs']):
        interaction_hash = source_proof['interaction_hash']
        merkle_proof = source_proof['merkle_proof']
        merkle_root = proof['merkle_root']
        
        # Convert merkle_proof to list of tuples
        proof_tuples = [(p[0], p[1]) for p in merkle_proof]
        
        # Create dummy tree just for verification
        # We don't need the full tree, just the verify_proof method
        dummy_tree = MerkleTree([interaction_hash])  # Single leaf tree
        
        # Verify proof
        is_valid = dummy_tree.verify_proof(interaction_hash, proof_tuples, merkle_root)
        
        if is_valid:
            print(f"[SUCCESS] Source proof {i+1}/{len(proof['source_proofs'])} verified")
        else:
            print(f"[ERROR] Source proof {i+1}/{len(proof['source_proofs'])} INVALID")
            return False
    
    print(f"[SUCCESS] All source proofs verified")
    print(f"[SUCCESS] Entity '{proof['entity']}' was extracted from verified conversations")
    return True


def main():
    parser = argparse.ArgumentParser(description="Verify ownership proof")
    parser.add_argument("--proof-file", required=True, help="Proof file (JSON)")
    parser.add_argument("--type", choices=['ownership', 'entity'], default='ownership', help="Proof type")
    parser.add_argument("--db", help="SQL database path for full verification (optional)")

    args = parser.parse_args()

    try:
        # Load proof
        with open(args.proof_file, 'r') as f:
            proof = json.load(f)

        # Verify based on type
        if args.type == 'ownership':
            is_valid = verify_ownership_proof(proof, args.db)
        else:
            is_valid = verify_entity_proof(proof)
        
        if is_valid:
            print(f"\n[SUCCESS] Proof is VALID")
            sys.exit(0)
        else:
            print(f"\n[ERROR] Proof is INVALID")
            sys.exit(1)
    
    except FileNotFoundError:
        print(f"[ERROR] Proof file not found: {args.proof_file}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"[ERROR] Invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

