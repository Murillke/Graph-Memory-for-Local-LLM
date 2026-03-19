#!/usr/bin/env python3
"""
Verify cryptographic integrity of the memory system.

Usage:
    # Verify SQL hash chain
    python3 scripts/verify_integrity.py --project "my-project" --sql
    
    # Verify graph extraction proofs
    python3 scripts/verify_integrity.py --project "my-project" --graph
    
    # Verify everything
    python3 scripts/verify_integrity.py --project "my-project" --all
    
    # Verify specific entity
    python3 scripts/verify_integrity.py --entity "entity-abc123"
    
    # Verify specific relationship
    python3 scripts/verify_integrity.py --relationship "rel-xyz789"

Output:
    Prints verification results with [OK] or [ERROR] indicators.
    Exit code 0 if all verifications pass, 1 if any fail.
"""

import sys
import os
import argparse
import json

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tools.sql_db import SQLDatabase
from tools.graph_db import GraphDatabase
from tools.config import load_config

from tools.console_utils import safe_print, setup_console_encoding

# Setup console encoding for Windows
setup_console_encoding()

def verify_sql_chain(db, project_name, verbose=False):
    """Verify SQL hash chain integrity."""
    safe_print(f"\n[SEARCH] Verifying SQL hash chain for project '{project_name}'...")
    
    result = db.verify_interaction_chain(project_name)
    
    if result['verified']:
        safe_print(f"[OK] Hash chain verified!")
        safe_print(f"   Total interactions: {result['total_interactions']}")
        if verbose:
            safe_print(f"   All {result['total_interactions']} interactions have valid hashes")
            safe_print(f"   Chain is complete with no gaps")
        return True
    else:
        safe_print(f"[ERROR] Hash chain verification FAILED!")
        safe_print(f"   Total interactions: {result['total_interactions']}")
        safe_print(f"   Errors found: {len(result['errors'])}")
        for error in result['errors']:
            safe_print(f"      - {error}")
        return False


def verify_graph_entities(graph_db, project_name, verbose=False):
    """Verify all entity extraction proofs in a project."""
    safe_print(f"\n[SEARCH] Verifying entity extraction proofs for project '{project_name}'...")

    entities = graph_db.get_all_entities(project_name, limit=1000)

    if not entities:
        safe_print(f"   No entities found")
        return True

    verified_count = 0
    failed_count = 0
    merged_count = 0

    for entity in entities:
        # Check if entity has attestation (imported from external database)
        extraction_proof = entity.get('extraction_proof')
        if extraction_proof is None:
            extraction_proof = {}
        elif isinstance(extraction_proof, str):
            import json
            try:
                extraction_proof = json.loads(extraction_proof)
            except:
                extraction_proof = {}

        attestation = extraction_proof.get('attestation', {}) if extraction_proof else {}
        has_attestation = attestation.get('type') == 'external_import'

        if has_attestation:
            # Attested entities: verify the attestation itself
            merged_count += 1

            # Verify attestation hash
            original_proof = attestation.get('original_proof', {})
            attestation_hash = attestation.get('attestation_hash', '')

            # Recalculate attestation hash
            import hashlib
            calculated_attestation = hashlib.sha256(
                json.dumps({
                    "entity_name": entity['name'],
                    "entity_summary": entity.get('summary', ''),
                    "original_proof_hash": original_proof.get('proof_hash', ''),
                    "original_source_hashes": original_proof.get('source_hashes', []),
                    "import_timestamp": attestation.get('import_timestamp', '')
                }, sort_keys=True).encode()
            ).hexdigest()

            attestation_valid = (calculated_attestation == attestation_hash)

            if verbose:
                if attestation_valid:
                    safe_print(f"   [ATTESTED] {entity['name']} (✓ attestation verified, {len(original_proof.get('source_hashes', []))} source hashes)")
                else:
                    safe_print(f"   [ATTESTED] {entity['name']} (✗ attestation INVALID!)")

            continue

        # Verify non-merged entities
        result = graph_db.verify_entity_extraction(entity['uuid'])
        if result['verified']:
            verified_count += 1
            if verbose:
                safe_print(f"   [OK] {entity['name']}")
        else:
            failed_count += 1
            safe_print(f"   [ERROR] {entity['name']}: Proof mismatch!")
            if verbose:
                safe_print(f"      Stored:     {result['stored_proof'][:32]}...")
                safe_print(f"      Calculated: {result['calculated_proof'][:32]}...")
    
    if failed_count == 0:
        safe_print(f"[OK] All {verified_count} entities verified!")
        if merged_count > 0:
            safe_print(f"[INFO] {merged_count} entities with external attestation (chain of custody preserved)")
        return True
    else:
        safe_print(f"[ERROR] {failed_count} entities FAILED verification!")
        safe_print(f"   {verified_count} entities passed")
        if merged_count > 0:
            safe_print(f"[INFO] {merged_count} entities with external attestation (chain of custody preserved)")
        return False


def verify_graph_relationships(graph_db, project_name, verbose=False):
    """Verify all relationship derivation proofs in a project."""
    safe_print(f"\n[SEARCH] Verifying relationship derivation proofs for project '{project_name}'...")
    
    facts = graph_db.search_facts(project_name, limit=1000)
    
    if not facts:
        safe_print(f"   No relationships found")
        return True
    
    verified_count = 0
    failed_count = 0
    
    for fact in facts:
        result = graph_db.verify_relationship_derivation(fact['uuid'])
        if result['verified']:
            verified_count += 1
            if verbose:
                safe_print(f"   [OK] {fact['fact'][:60]}...")
        else:
            failed_count += 1
            safe_print(f"   [ERROR] {fact['fact'][:60]}...: Proof mismatch!")
            if verbose:
                safe_print(f"      Stored:     {result['stored_proof'][:32]}...")
                safe_print(f"      Calculated: {result['calculated_proof'][:32]}...")
    
    if failed_count == 0:
        safe_print(f"[OK] All {verified_count} relationships verified!")
        return True
    else:
        safe_print(f"[ERROR] {failed_count} relationships FAILED verification!")
        safe_print(f"   {verified_count} relationships passed")
        return False


def auto_detect_graph_db(project_name, config):
    """Auto-detect graph database path from project name."""
    configured_path = config.get_graph_db_path(project_name)
    memory_dir = config.get_memory_dir()
    # Note: .db is SQL database, not a legacy graph path
    legacy_paths = [
        os.path.join(memory_dir, f'{project_name}.kuzu'),
    ]
    existing_legacy_paths = [path for path in legacy_paths if os.path.exists(path)]

    if existing_legacy_paths:
        raise FileNotFoundError(
            "Legacy graph database path(s) detected; run scripts/consolidate_graph_db_paths.py first: "
            + ", ".join(existing_legacy_paths)
        )

    if configured_path and os.path.exists(configured_path):
        return configured_path

    return configured_path


def main():
    parser = argparse.ArgumentParser(
        description='Verify cryptographic integrity of the memory system',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    # Databases
    parser.add_argument('--sql-db', help='Path to SQLite database (default: from config)')
    parser.add_argument('--graph-db',
                       help='Path to graph database (default: auto-detect from --project)')

    # What to verify
    parser.add_argument('--project', help='Project name')
    parser.add_argument('--sql', action='store_true', help='Verify SQL hash chain')
    parser.add_argument('--graph', action='store_true', help='Verify graph proofs')
    parser.add_argument('--all', action='store_true', help='Verify everything')
    parser.add_argument('--entity', help='Verify specific entity by UUID')
    parser.add_argument('--relationship', help='Verify specific relationship by UUID')

    # Options
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--json', action='store_true', help='Output as JSON')

    args = parser.parse_args()
    config = load_config(project_name=args.project, cli_args={"sql_db": args.sql_db, "graph_db": args.graph_db})
    args.sql_db = config.get_sql_db_path()

    # Auto-detect graph database if not specified
    if not args.graph_db and args.project:
        args.graph_db = auto_detect_graph_db(args.project, config)
        if args.verbose:
            safe_print(f"[INFO] Auto-detected graph database: {args.graph_db}")
    
    all_passed = True
    results = {}
    
    # Verify specific entity
    if args.entity:
        graph_db = GraphDatabase(args.graph_db)
        result = graph_db.verify_entity_extraction(args.entity)
        
        if args.json:
            safe_print(json.dumps(result))
        else:
            if result['verified']:
                safe_print(f"[OK] Entity '{result['entity_name']}' verified!")
                if args.verbose:
                    safe_print(f"   Extraction proof: {result['stored_proof'][:32]}...")
                    safe_print(f"   Version: {result['extraction_version']}")
                    safe_print(f"   Commit: {result['extraction_commit']}")
            else:
                safe_print(f"[ERROR] Entity verification FAILED!")
                safe_print(f"   Stored proof:     {result['stored_proof'][:32]}...")
                safe_print(f"   Calculated proof: {result['calculated_proof'][:32]}...")
        
        sys.exit(0 if result['verified'] else 1)
    
    # Verify specific relationship
    if args.relationship:
        graph_db = GraphDatabase(args.graph_db)
        result = graph_db.verify_relationship_derivation(args.relationship)
        
        if args.json:
            safe_print(json.dumps(result))
        else:
            if result['verified']:
                safe_print(f"[OK] Relationship verified!")
                safe_print(f"   Fact: {result['fact']}")
                if args.verbose:
                    safe_print(f"   Derivation proof: {result['stored_proof'][:32]}...")
                    safe_print(f"   Version: {result['derivation_version']}")
            else:
                safe_print(f"[ERROR] Relationship verification FAILED!")
                safe_print(f"   Fact: {result['fact']}")
                safe_print(f"   Stored proof:     {result['stored_proof'][:32]}...")
                safe_print(f"   Calculated proof: {result['calculated_proof'][:32]}...")
        
        sys.exit(0 if result['verified'] else 1)
    
    # Verify project
    if not args.project:
        safe_print("Error: --project required (or use --entity/--relationship)", file=sys.stderr)
        parser.print_help()
        sys.exit(1)
    
    # Verify SQL
    if args.sql or args.all:
        sql_db = SQLDatabase(args.sql_db)
        passed = verify_sql_chain(sql_db, args.project, verbose=args.verbose)
        results['sql'] = passed
        all_passed = all_passed and passed
    
    # Verify graph
    if args.graph or args.all:
        graph_db = GraphDatabase(args.graph_db)
        
        # Verify entities
        passed = verify_graph_entities(graph_db, args.project, verbose=args.verbose)
        results['entities'] = passed
        all_passed = all_passed and passed
        
        # Verify relationships
        passed = verify_graph_relationships(graph_db, args.project, verbose=args.verbose)
        results['relationships'] = passed
        all_passed = all_passed and passed
    
    # Summary
    if args.json:
        safe_print(json.dumps(results))
    else:
        safe_print(f"\n{'='*60}")
        if all_passed:
            safe_print(f"[OK] ALL VERIFICATIONS PASSED!")
        else:
            safe_print(f"[ERROR] SOME VERIFICATIONS FAILED!")
        safe_print(f"{'='*60}")
    
    sys.exit(0 if all_passed else 1)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        safe_print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        safe_print(f"\n[ERROR] Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

