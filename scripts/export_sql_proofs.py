#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Export SQL interactions with merkle proofs.

This creates a compact, structured export of conversations that can be:
- Backed up selectively
- Shared with proofs
- Imported to other systems
- Used to rebuild graph

Usage:
    python scripts/export_sql_proofs.py --project my_project --output backup.json
    python scripts/export_sql_proofs.py --project my_project --output backup.json --limit 100
    python scripts/export_sql_proofs.py --project my_project --output backup.json --after 2026-03-01
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

from tools.sql_db import SQLDatabase
from tools.console_utils import safe_print


def export_interactions(sql_db: SQLDatabase, project_name: str, limit: int = None, after_date: str = None):
    """
    Export interactions with metadata.
    
    Returns dict with interactions and metadata.
    """
    safe_print(f"[EXPORT] Exporting interactions for project: {project_name}")
    
    # Build query
    query = """
        SELECT uuid, user_message, assistant_message, timestamp,
               content_hash, previous_hash, chain_index,
               file_hash, timestamp_proof,
               fidelity, source_note
        FROM interactions
        WHERE project_name = ?
    """
    params = [project_name]
    
    if after_date:
        query += " AND timestamp >= ?"
        params.append(after_date)
    
    query += " ORDER BY chain_index ASC"
    
    if limit:
        query += f" LIMIT {limit}"
    
    # Execute query
    conn = sql_db._get_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)
    
    interactions = []
    for row in cursor.fetchall():
        interactions.append({
            'uuid': row[0],
            'user_message': row[1],
            'assistant_message': row[2],
            'timestamp': row[3],
            'content_hash': row[4],
            'previous_hash': row[5],
            'chain_index': row[6],
            'file_hash': row[7],
            'timestamp_proof': row[8],
            'fidelity': row[9],
            'source_note': row[10]
        })
    
    conn.close()
    
    safe_print(f"[EXPORT] Exported {len(interactions)} interactions")
    
    return {
        'project_name': project_name,
        'export_date': datetime.now().isoformat(),
        'interaction_count': len(interactions),
        'interactions': interactions
    }


def main():
    parser = argparse.ArgumentParser(
        description='Export SQL interactions with proofs'
    )
    parser.add_argument('--project', required=True, help='Project name')
    parser.add_argument('--output', required=True, help='Output JSON file')
    parser.add_argument('--limit', type=int, help='Limit number of interactions')
    parser.add_argument('--after', help='Export only after this date (YYYY-MM-DD)')
    
    args = parser.parse_args()
    
    # Load config
    config_path = 'mem.config.json'
    if not os.path.exists(config_path):
        safe_print("[ERROR] mem.config.json not found!")
        sys.exit(1)
    
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    # Connect to database
    sql_db = SQLDatabase(config['database']['sql_path'])
    
    # Export interactions
    export_data = export_interactions(
        sql_db,
        args.project,
        limit=args.limit,
        after_date=args.after
    )
    
    # Save to file
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)
    
    safe_print(f"\n✅ Export complete!")
    safe_print(f"   File: {args.output}")
    safe_print(f"   Interactions: {export_data['interaction_count']}")


if __name__ == '__main__':
    main()

