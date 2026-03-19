"""
Verify an attested entity against its source database.

For entities imported from external databases, this script can verify
the original extraction proof if you have access to the source database.
"""

import argparse
import json
import sys
import os
from pathlib import Path
import hashlib
import sqlite3

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.config import load_config
from tools.graph_db import GraphDatabase


def verify_attested_entity(entity_name: str, project_name: str, 
                           current_graph_db: str, source_sql_db: str):
    """
    Verify an attested entity against source database.
    
    Args:
        entity_name: Name of entity to verify
        project_name: Project name
        current_graph_db: Path to current graph database
        source_sql_db: Path to source SQL database
    
    Returns:
        Verification result dict
    """
    # Get entity from current database
    graph_db = GraphDatabase(current_graph_db)
    conn = graph_db.conn
    
    query = """
    MATCH (p:Project {name: $project_name})-[:HAS_ENTITY]->(e:Entity {name: $entity_name})
    RETURN e.uuid AS uuid, e.name AS name, e.summary AS summary,
           e.extraction_proof AS extraction_proof
    """
    
    result = conn.execute(query, {"project_name": project_name, "entity_name": entity_name})
    df = result.get_as_df()
    conn.close()
    
    if df.empty:
        return {"verified": False, "error": f"Entity '{entity_name}' not found"}
    
    entity = df.iloc[0]
    extraction_proof = json.loads(entity['extraction_proof'])
    
    # Check if entity has attestation
    attestation = extraction_proof.get('attestation', {})
    if attestation.get('type') != 'external_import':
        return {"verified": False, "error": "Entity is not attested (not imported from external database)"}
    
    # Get original proof
    original_proof = attestation.get('original_proof', {})
    original_source_hashes = original_proof.get('source_hashes', [])
    
    print(f"[INFO] Entity: {entity_name}")
    print(f"[INFO] Original source hashes: {len(original_source_hashes)}")
    
    # Verify source hashes exist in source database
    sql_conn = sqlite3.connect(source_sql_db)
    cursor = sql_conn.cursor()
    
    found_hashes = []
    missing_hashes = []
    
    for source_hash in original_source_hashes:
        cursor.execute("SELECT uuid, timestamp FROM interactions WHERE content_hash = ?", (source_hash,))
        row = cursor.fetchone()
        if row:
            found_hashes.append({
                "hash": source_hash,
                "uuid": row[0],
                "timestamp": row[1]
            })
        else:
            missing_hashes.append(source_hash)
    
    sql_conn.close()
    
    # Verify attestation hash
    calculated_attestation = hashlib.sha256(
        json.dumps({
            "entity_name": entity['name'],
            "entity_summary": entity['summary'],
            "original_proof_hash": original_proof.get('proof_hash', ''),
            "original_source_hashes": original_source_hashes,
            "import_timestamp": attestation.get('import_timestamp', '')
        }, sort_keys=True).encode()
    ).hexdigest()
    
    attestation_valid = (calculated_attestation == attestation.get('attestation_hash', ''))
    
    return {
        "verified": len(missing_hashes) == 0 and attestation_valid,
        "entity_name": entity_name,
        "attestation_valid": attestation_valid,
        "total_source_hashes": len(original_source_hashes),
        "found_hashes": len(found_hashes),
        "missing_hashes": len(missing_hashes),
        "found_interactions": found_hashes,
        "original_proof_hash": original_proof.get('proof_hash', ''),
        "import_timestamp": attestation.get('import_timestamp', '')
    }


def main():
    parser = argparse.ArgumentParser(description="Verify attested entity against source database")
    parser.add_argument("--entity", help="Deprecated direct entity name (use --entity-file)")
    parser.add_argument("--entity-file", help="File containing entity name (workflow standard)")
    parser.add_argument("--project", required=True, help="Project name")
    parser.add_argument("--source-sql", required=True, help="Source SQL database path")
    parser.add_argument("--graph-db", help="Current graph database path (overrides config)")

    args = parser.parse_args()

    # Read entity from file if provided
    entity_name = args.entity
    if args.entity_file:
        with open(args.entity_file, 'r', encoding='utf-8') as f:
            entity_name = f.read().strip()
    elif "--entity" in sys.argv[1:]:
        if os.getenv("MEM_ALLOW_DIRECT_INPUT") != "1":
            parser.error("Direct --entity is disabled by default. Use --entity-file tmp/entity.txt. Set MEM_ALLOW_DIRECT_INPUT=1 only for legacy/manual compatibility.")
        print("[WARNING] --entity is allowed only because MEM_ALLOW_DIRECT_INPUT=1 is set. Prefer --entity-file tmp/entity.txt.", file=sys.stderr)

    if not entity_name:
        parser.error("Either --entity or --entity-file is required")

    args.entity = entity_name
    
    # Load config
    config = load_config(project_name=args.project, cli_args={"graph_db": args.graph_db})
    graph_db_path = config.get_graph_db_path()
    
    try:
        result = verify_attested_entity(args.entity, args.project, graph_db_path, args.source_sql)
        
        if result.get('error'):
            print(f"[ERROR] {result['error']}")
            sys.exit(1)
        
        print(f"\n[VERIFICATION RESULTS]")
        print(f"  Entity: {result['entity_name']}")
        print(f"  Attestation valid: {'✓' if result['attestation_valid'] else '✗'}")
        print(f"  Source hashes: {result['found_hashes']}/{result['total_source_hashes']} found")
        print(f"  Import timestamp: {result['import_timestamp']}")
        
        if result['found_interactions']:
            print(f"\n[SOURCE INTERACTIONS]")
            for interaction in result['found_interactions']:
                print(f"  - {interaction['uuid']} ({interaction['timestamp']})")
        
        if result['verified']:
            print(f"\n[SUCCESS] Entity verified against source database!")
            print(f"[INFO] This entity was extracted from {result['total_source_hashes']} interactions in the source database")
            sys.exit(0)
        else:
            print(f"\n[ERROR] Verification FAILED!")
            if result['missing_hashes'] > 0:
                print(f"[ERROR] {result['missing_hashes']} source hashes not found in source database")
            sys.exit(1)
    
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
