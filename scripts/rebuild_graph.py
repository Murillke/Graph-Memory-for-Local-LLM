#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rebuild graph database from SQL conversations.

This allows you to:
- Test new extraction logic (e.g., Sonnet 4.6 vs 4.5)
- Fix extraction errors
- Start fresh with improved understanding
- Compare different extraction versions

Usage:
    python scripts/rebuild_graph.py --project my_project --backup-first
    python scripts/rebuild_graph.py --project my_project --dry-run
    python scripts/rebuild_graph.py --project my_project --after 2026-03-01
"""

import sys
import os
import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

# Fix Windows encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tools.sql_db import SQLDatabase
from tools.graph_db import GraphDatabase
from tools.config import load_config
from tools.console_utils import safe_print


def backup_graph(graph_path: str):
    """Create backup of graph database."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"{graph_path}.backup_{timestamp}"
    
    safe_print(f"[BACKUP] Creating backup...")
    safe_print(f"   From: {graph_path}")
    safe_print(f"   To: {backup_path}")
    
    # Copy entire directory
    if os.path.isdir(graph_path):
        shutil.copytree(graph_path, backup_path)
    else:
        shutil.copy2(graph_path, backup_path)
    
    safe_print(f"[BACKUP] ✅ Backup created")
    return backup_path


def clear_project_from_graph(graph_db: GraphDatabase, project_name: str):
    """Clear all entities and facts for a project."""
    safe_print(f"[CLEAR] Removing all entities and facts for project: {project_name}")
    
    # Delete all relationships first
    graph_db.conn.execute(f"""
        MATCH (p:Project {{name: '{project_name}'}})-[:HAS_ENTITY]->(e:Entity)
        MATCH (e)-[r:RELATES_TO]->()
        DELETE r
    """)
    
    # Delete all entities
    graph_db.conn.execute(f"""
        MATCH (p:Project {{name: '{project_name}'}})-[rel:HAS_ENTITY]->(e:Entity)
        DELETE rel, e
    """)
    
    safe_print(f"[CLEAR] ✅ Project cleared from graph")


def get_interactions_to_process(sql_db: SQLDatabase, project_name: str, after_date: str = None):
    """Get list of interactions to process."""
    query = """
        SELECT uuid, timestamp
        FROM interactions
        WHERE project_name = ?
    """
    params = [project_name]
    
    if after_date:
        query += " AND timestamp >= ?"
        params.append(after_date)
    
    query += " ORDER BY chain_index ASC"
    
    conn = sql_db._get_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)
    
    interactions = [(row[0], row[1]) for row in cursor.fetchall()]
    conn.close()
    
    return interactions


def main():
    parser = argparse.ArgumentParser(
        description='Rebuild graph database from SQL conversations'
    )
    parser.add_argument('--project', required=True, help='Project name')
    parser.add_argument('--backup-first', action='store_true', help='Create backup before rebuilding')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without doing it')
    parser.add_argument('--after', help='Only rebuild from this date forward (YYYY-MM-DD)')
    
    args = parser.parse_args()
    
    # Load config
    config = load_config(project_name=args.project)
    
    # Connect to databases
    sql_db = SQLDatabase(config.get_sql_db_path())
    graph_db = GraphDatabase(config.get_graph_db_path(args.project))
    
    # Get interactions to process
    interactions = get_interactions_to_process(sql_db, args.project, args.after)
    
    safe_print(f"[REBUILD] Project: {args.project}")
    safe_print(f"[REBUILD] Interactions to process: {len(interactions)}")
    
    if args.dry_run:
        safe_print(f"\n[DRY-RUN] Would rebuild graph from {len(interactions)} interactions")
        safe_print(f"[DRY-RUN] No changes made")
        return
    
    # Backup if requested
    if args.backup_first:
        backup_path = backup_graph(config.get_graph_db_path(args.project))
        safe_print(f"[INFO] Backup saved to: {backup_path}")
    
    # Clear project from graph
    clear_project_from_graph(graph_db, args.project)
    
    # Rebuild instructions
    safe_print(f"\n[REBUILD] Graph cleared. Now run extraction on conversations:")
    safe_print(f"\n   1. Extract knowledge from conversations (use your LLM)")
    safe_print(f"   2. Save to tmp/extraction.json")
    safe_print(f"   3. Run: python scripts/store_extraction.py --project {args.project} --extraction-file tmp/extraction.json")
    safe_print(f"\n   Repeat for each conversation or batch of conversations.")
    safe_print(f"\n✅ Ready for rebuild!")


if __name__ == '__main__':
    main()
