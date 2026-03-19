"""
Generate ownership proof for a project.

Proves you own data without revealing conversation content.
Uses Merkle tree of interaction hashes.
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.sql_db import SQLDatabase
from tools.merkle_tree import MerkleTree
from tools.config import load_config


def generate_ownership_proof(project_name: str, sql_db_path: str) -> dict:
    """
    Generate ownership proof for project.

    Args:
        project_name: Name of project
        sql_db_path: Path to SQL database

    Returns:
        Ownership proof dict
    """
    # Get all interactions for project
    db = SQLDatabase(sql_db_path)
    interactions = db.get_all_interactions(project_name)
    
    if not interactions:
        raise ValueError(f"No interactions found for project '{project_name}'")
    
    # Extract hashes
    hashes = [i['content_hash'] for i in interactions]
    
    # Build Merkle tree
    tree = MerkleTree(hashes)
    
    # Create proof
    proof = {
        "project_name": project_name,
        "merkle_root": tree.root,
        "timestamp": datetime.now().isoformat(),
        "interaction_count": len(hashes),
        "earliest_interaction": interactions[0]['timestamp'],
        "latest_interaction": interactions[-1]['timestamp'],
        "proof_version": "1.0.0"
    }
    
    return proof


def generate_entity_proof(project_name: str, entity_name: str, sql_db_path: str, graph_db_path: str) -> dict:
    """
    Generate proof that entity was extracted from real conversations.
    
    Args:
        project_name: Name of project
        entity_name: Name of entity
        sql_db_path: Path to SQL database
        graph_db_path: Path to graph database
    
    Returns:
        Entity proof dict
    """
    from tools.graph_db import GraphDatabase

    # Get entity and extraction proof
    graph_db = GraphDatabase(graph_db_path)
    
    # Query entity using GraphDatabase method
    entity = graph_db.get_entity_by_name(project_name, entity_name)

    if not entity:
        raise ValueError(f"Entity '{entity_name}' not found in project '{project_name}'")

    extraction_proof = entity.get('extraction_proof')
    if isinstance(extraction_proof, str):
        extraction_proof = json.loads(extraction_proof)

    if not extraction_proof:
        raise ValueError(f"Entity '{entity_name}' has no extraction proof")

    source_uuids = extraction_proof.get('source_interactions', [])

    # Get all interactions
    db = SQLDatabase(sql_db_path)
    interactions = db.get_all_interactions(project_name)
    
    # Build Merkle tree
    hashes = [i['content_hash'] for i in interactions]
    tree = MerkleTree(hashes)
    
    # Get proofs for source interactions
    source_proofs = []
    for uuid in source_uuids:
        # Find interaction index
        index = next((i for i, interaction in enumerate(interactions) if interaction['uuid'] == uuid), None)
        if index is not None:
            merkle_proof = tree.get_proof(index)
            source_proofs.append({
                "interaction_uuid": uuid,
                "interaction_hash": interactions[index]['content_hash'],
                "merkle_proof": merkle_proof
            })
    
    return {
        "entity": entity_name,
        "merkle_root": tree.root,
        "source_proofs": source_proofs,
        "timestamp": datetime.now().isoformat(),
        "proof_version": "1.0.0"
    }


def main():
    parser = argparse.ArgumentParser(description="Generate ownership proof")
    parser.add_argument("--project", required=True, help="Project name")
    parser.add_argument("--entity", help="Entity name (for entity proof)")
    parser.add_argument("--sql-db", help="SQL database path (overrides config)")
    parser.add_argument("--graph-db", help="Graph database path (overrides config)")
    parser.add_argument("--output", help="Output file (default: stdout)")
    
    args = parser.parse_args()
    
    # Load config
    config = load_config(project_name=args.project, cli_args={
        "sql_db": args.sql_db,
        "graph_db": args.graph_db
    })
    
    sql_db_path = config.get_sql_db_path()
    graph_db_path = config.get_graph_db_path()
    
    try:
        if args.entity:
            # Generate entity proof
            proof = generate_entity_proof(args.project, args.entity, sql_db_path, graph_db_path)
        else:
            # Generate ownership proof
            proof = generate_ownership_proof(args.project, sql_db_path)
        
        # Output
        proof_json = json.dumps(proof, indent=2)
        
        if args.output:
            with open(args.output, 'w') as f:
                f.write(proof_json)
            print(f"[SUCCESS] Proof written to {args.output}")
        else:
            print(proof_json)
    
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

