#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compare two graph extractions to identify improvements or regressions.

This helps you:
- Compare Sonnet 4.5 vs 4.6 extraction quality
- Identify where new extraction logic is better/worse
- Find entities/facts that were added/removed/changed
- Evaluate extraction improvements

Usage:
    python scripts/compare_graphs.py --project my_project --old-backup graph.backup_20260305 --current graph
    python scripts/compare_graphs.py --project my_project --old-backup graph.backup_20260305 --current graph --detailed
"""

import sys
import os
import argparse
import json

# Fix Windows encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tools.graph_db import GraphDatabase
from tools.console_utils import safe_print


def get_entities(graph_db: GraphDatabase, project_name: str):
    """Get all entities from a graph."""
    query = f"""
        MATCH (p:Project {{name: '{project_name}'}})-[:HAS_ENTITY]->(e:Entity)
        RETURN e.name, e.summary, e.labels
    """
    
    result = graph_db.conn.execute(query)
    entities = {}
    
    while result.has_next():
        row = result.get_next()
        name = row[0]
        summary = row[1]
        labels = row[2]
        entities[name] = {'summary': summary, 'labels': labels}
    
    return entities


def get_facts(graph_db: GraphDatabase, project_name: str):
    """Get all facts from a graph."""
    query = f"""
        MATCH (p:Project {{name: '{project_name}'}})-[:HAS_ENTITY]->(e1:Entity)
        MATCH (e1)-[r:RELATES_TO]->(e2:Entity)
        RETURN e1.name, r.name, e2.name, r.fact
    """
    
    result = graph_db.conn.execute(query)
    facts = []
    
    while result.has_next():
        row = result.get_next()
        facts.append({
            'source': row[0],
            'type': row[1],
            'target': row[2],
            'fact': row[3]
        })
    
    return facts


def compare_entities(old_entities, new_entities, detailed=False):
    """Compare entities between two graphs."""
    safe_print("\n[ENTITIES]")
    
    old_names = set(old_entities.keys())
    new_names = set(new_entities.keys())
    
    added = new_names - old_names
    removed = old_names - new_names
    common = old_names & new_names
    
    safe_print(f"  Old graph: {len(old_names)} entities")
    safe_print(f"  New graph: {len(new_names)} entities")
    safe_print(f"  Added: {len(added)}")
    safe_print(f"  Removed: {len(removed)}")
    safe_print(f"  Common: {len(common)}")
    
    if detailed and added:
        safe_print(f"\n  Added entities:")
        for name in sorted(list(added))[:10]:
            safe_print(f"    + {name}")
        if len(added) > 10:
            safe_print(f"    ... and {len(added) - 10} more")
    
    if detailed and removed:
        safe_print(f"\n  Removed entities:")
        for name in sorted(list(removed))[:10]:
            safe_print(f"    - {name}")
        if len(removed) > 10:
            safe_print(f"    ... and {len(removed) - 10} more")


def compare_facts(old_facts, new_facts, detailed=False):
    """Compare facts between two graphs."""
    safe_print("\n[FACTS]")
    
    # Create fact signatures for comparison
    old_sigs = set((f['source'], f['type'], f['target']) for f in old_facts)
    new_sigs = set((f['source'], f['type'], f['target']) for f in new_facts)
    
    added = new_sigs - old_sigs
    removed = old_sigs - new_sigs
    common = old_sigs & new_sigs
    
    safe_print(f"  Old graph: {len(old_facts)} facts")
    safe_print(f"  New graph: {len(new_facts)} facts")
    safe_print(f"  Added: {len(added)}")
    safe_print(f"  Removed: {len(removed)}")
    safe_print(f"  Common: {len(common)}")
    
    if detailed and added:
        safe_print(f"\n  Added facts:")
        for sig in sorted(list(added))[:10]:
            safe_print(f"    + {sig[0]} → {sig[1]} → {sig[2]}")
        if len(added) > 10:
            safe_print(f"    ... and {len(added) - 10} more")
    
    if detailed and removed:
        safe_print(f"\n  Removed facts:")
        for sig in sorted(list(removed))[:10]:
            safe_print(f"    - {sig[0]} → {sig[1]} → {sig[2]}")
        if len(removed) > 10:
            safe_print(f"    ... and {len(removed) - 10} more")


def main():
    parser = argparse.ArgumentParser(
        description='Compare two graph extractions'
    )
    parser.add_argument('--project', required=True, help='Project name')
    parser.add_argument('--old-backup', required=True, help='Path to old graph backup')
    parser.add_argument('--current', required=True, help='Path to current graph')
    parser.add_argument('--detailed', action='store_true', help='Show detailed differences')
    
    args = parser.parse_args()
    
    safe_print(f"[COMPARE] Comparing graphs for project: {args.project}")
    safe_print(f"   Old: {args.old_backup}")
    safe_print(f"   New: {args.current}")
    
    # Connect to both graphs
    old_graph = GraphDatabase(args.old_backup)
    new_graph = GraphDatabase(args.current)
    
    # Get entities
    safe_print("\n[LOADING] Loading entities...")
    old_entities = get_entities(old_graph, args.project)
    new_entities = get_entities(new_graph, args.project)
    
    # Get facts
    safe_print("[LOADING] Loading facts...")
    old_facts = get_facts(old_graph, args.project)
    new_facts = get_facts(new_graph, args.project)
    
    # Compare
    compare_entities(old_entities, new_entities, args.detailed)
    compare_facts(old_facts, new_facts, args.detailed)
    
    safe_print(f"\n✅ Comparison complete!")


if __name__ == '__main__':
    main()

