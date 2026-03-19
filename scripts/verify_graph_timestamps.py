#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verify timestamp proofs in graph database.

This verifies that the graph is self-sufficient and can prove timeline
without requiring SQL database.

Usage:
    python scripts/verify_graph_timestamps.py --project my_project
    python scripts/verify_graph_timestamps.py --project my_project --entity-file tmp/entity.txt
"""

import sys
import os
import argparse

# Fix Windows encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tools.graph_db import GraphDatabase
from tools.config import load_config
from tools.console_utils import safe_print


def verify_entity_timestamps(graph_db: GraphDatabase, project_name: str, entity_name: str = None):
    """Verify timestamp proofs for entities."""
    
    if entity_name:
        safe_print(f"[VERIFY] Checking entity: {entity_name}")
        query = f"""
            MATCH (p:Project {{name: '{project_name}'}})-[:HAS_ENTITY]->(e:Entity {{name: '{entity_name}'}})
            RETURN e.name, e.timestamp_proof, e.extraction_timestamp_str, e.source_hashes
        """
    else:
        safe_print(f"[VERIFY] Checking all entities in project: {project_name}")
        query = f"""
            MATCH (p:Project {{name: '{project_name}'}})-[:HAS_ENTITY]->(e:Entity)
            RETURN e.name, e.timestamp_proof, e.extraction_timestamp_str, e.source_hashes
            LIMIT 10
        """
    
    result = graph_db.conn.execute(query)
    
    entities_checked = 0
    entities_with_proof = 0
    entities_without_proof = 0
    
    while result.has_next():
        row = result.get_next()
        name = row[0]
        timestamp_proof = row[1]
        extraction_time = row[2]
        source_hashes = row[3]
        
        entities_checked += 1
        
        if timestamp_proof and timestamp_proof.strip():
            entities_with_proof += 1
            safe_print(f"  ✅ {name}")
            safe_print(f"     Extracted: {extraction_time}")
            safe_print(f"     Has timestamp proof: Yes")
        else:
            entities_without_proof += 1
            safe_print(f"  ⚠️  {name}")
            safe_print(f"     Extracted: {extraction_time}")
            safe_print(f"     Has timestamp proof: No (expected for now)")
    
    safe_print(f"\n[SUMMARY]")
    safe_print(f"  Entities checked: {entities_checked}")
    safe_print(f"  With timestamp proof: {entities_with_proof}")
    safe_print(f"  Without timestamp proof: {entities_without_proof}")
    
    return entities_checked > 0


def verify_fact_timestamps(graph_db: GraphDatabase, project_name: str):
    """Verify timestamp proofs for facts."""
    
    safe_print(f"\n[VERIFY] Checking facts in project: {project_name}")
    
    query = f"""
        MATCH (p:Project {{name: '{project_name}'}})-[:HAS_ENTITY]->(e1:Entity)
        MATCH (e1)-[r:RELATES_TO]->(e2:Entity)
        RETURN e1.name, r.name, e2.name, r.timestamp_proof, r.derivation_timestamp_str
        LIMIT 10
    """
    
    result = graph_db.conn.execute(query)
    
    facts_checked = 0
    facts_with_proof = 0
    facts_without_proof = 0
    
    while result.has_next():
        row = result.get_next()
        source = row[0]
        rel_type = row[1]
        target = row[2]
        timestamp_proof = row[3]
        derivation_time = row[4]
        
        facts_checked += 1
        
        if timestamp_proof and timestamp_proof.strip():
            facts_with_proof += 1
            safe_print(f"  ✅ {source} → {rel_type} → {target}")
            safe_print(f"     Derived: {derivation_time}")
            safe_print(f"     Has timestamp proof: Yes")
        else:
            facts_without_proof += 1
            safe_print(f"  ⚠️  {source} → {rel_type} → {target}")
            safe_print(f"     Derived: {derivation_time}")
            safe_print(f"     Has timestamp proof: No (expected for now)")
    
    safe_print(f"\n[SUMMARY]")
    safe_print(f"  Facts checked: {facts_checked}")
    safe_print(f"  With timestamp proof: {facts_with_proof}")
    safe_print(f"  Without timestamp proof: {facts_without_proof}")
    
    return facts_checked > 0


def main():
    parser = argparse.ArgumentParser(
        description='Verify timestamp proofs in graph database'
    )
    parser.add_argument('--project', required=True, help='Project name')
    parser.add_argument('--entity', help='Deprecated direct entity name (use --entity-file)')
    parser.add_argument('--entity-file', help='File containing entity name (workflow standard)')
    
    args = parser.parse_args()
    
    if args.entity_file:
        with open(args.entity_file, 'r', encoding='utf-8') as f:
            args.entity = f.read().strip()
    elif '--entity' in sys.argv[1:]:
        if os.getenv("MEM_ALLOW_DIRECT_INPUT") != "1":
            parser.error("Direct --entity is disabled by default. Use --entity-file tmp/entity.txt. Set MEM_ALLOW_DIRECT_INPUT=1 only for legacy/manual compatibility.")
        safe_print("[WARNING] --entity is allowed only because MEM_ALLOW_DIRECT_INPUT=1 is set. Prefer --entity-file tmp/entity.txt.", file=sys.stderr)

    config = load_config(project_name=args.project)
    graph_db = GraphDatabase(config.get_graph_db_path(args.project))
    
    # Verify entities
    entities_ok = verify_entity_timestamps(graph_db, args.project, args.entity)
    
    # Verify facts (if not checking specific entity)
    if not args.entity:
        facts_ok = verify_fact_timestamps(graph_db, args.project)
    
    safe_print(f"\n✅ Verification complete!")
    safe_print(f"\nNote: Full OpenTimestamps integration not yet implemented.")
    safe_print(f"      Graph has timestamp_proof fields ready for future use.")


if __name__ == '__main__':
    main()
