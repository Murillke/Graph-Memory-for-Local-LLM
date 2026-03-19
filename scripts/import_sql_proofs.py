#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Import SQL interactions from export file.

This imports interactions that were exported with export_sql_proofs.py.
Verifies hash chain integrity during import.

Usage:
    python scripts/import_sql_proofs.py --input backup.json
    python scripts/import_sql_proofs.py --input backup.json --verify-only
"""

import sys
import os
import argparse
import json
import hashlib

# Fix Windows encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tools.sql_db import SQLDatabase
from tools.console_utils import safe_print


def verify_hash_chain(interactions):
    """Verify hash chain integrity."""
    safe_print("[VERIFY] Verifying hash chain...")
    
    for i, interaction in enumerate(interactions):
        # Check previous_hash links correctly
        if i > 0:
            expected_prev = interactions[i-1]['content_hash']
            actual_prev = interaction['previous_hash']
            
            if expected_prev != actual_prev:
                safe_print(f"[ERROR] Hash chain broken at index {i}!")
                safe_print(f"   Expected previous: {expected_prev}")
                safe_print(f"   Actual previous: {actual_prev}")
                return False
        else:
            # First interaction should have no previous
            if interaction['previous_hash'] is not None:
                safe_print(f"[ERROR] First interaction has previous_hash!")
                return False
    
    safe_print(f"[VERIFY] ✅ Hash chain verified ({len(interactions)} interactions)")
    return True


def import_interactions(sql_db: SQLDatabase, export_data, verify_only=False):
    """Import interactions from export data."""
    project_name = export_data['project_name']
    interactions = export_data['interactions']
    
    safe_print(f"[IMPORT] Importing {len(interactions)} interactions for project: {project_name}")
    
    # Verify hash chain first
    if not verify_hash_chain(interactions):
        safe_print("[ERROR] Hash chain verification failed!")
        return False
    
    if verify_only:
        safe_print("[VERIFY] Verification complete (no import)")
        return True
    
    # Get or create project
    project = sql_db.get_project_by_name(project_name)
    if not project:
        sql_db.create_project(project_name, f"Project: {project_name}")
        safe_print(f"[OK] Created project: {project_name}")
    
    # Import interactions
    imported = 0
    skipped = 0
    
    for interaction in interactions:
        # Check if already exists
        existing = sql_db.get_interaction_by_uuid(interaction['uuid'])
        if existing:
            skipped += 1
            continue
        
        # Import interaction
        sql_db.store_interaction({
            'uuid': interaction['uuid'],
            'project_name': project_name,
            'user_message': interaction['user_message'],
            'assistant_message': interaction['assistant_message'],
            'timestamp': interaction['timestamp'],
            'content_hash': interaction['content_hash'],
            'previous_hash': interaction['previous_hash'],
            'chain_index': interaction['chain_index'],
            'file_hash': interaction.get('file_hash'),
            'timestamp_proof': interaction.get('timestamp_proof'),
            'fidelity': interaction.get('fidelity', 'full'),
            'source_note': interaction.get('source_note')
        })
        imported += 1
    
    safe_print(f"[IMPORT] ✅ Imported: {imported}, Skipped (already exist): {skipped}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description='Import SQL interactions from export file'
    )
    parser.add_argument('--input', required=True, help='Input JSON file from export_sql_proofs.py')
    parser.add_argument('--verify-only', action='store_true', help='Only verify, do not import')
    
    args = parser.parse_args()
    
    # Load export file
    if not os.path.exists(args.input):
        safe_print(f"[ERROR] File not found: {args.input}")
        sys.exit(1)
    
    with open(args.input, 'r', encoding='utf-8') as f:
        export_data = json.load(f)
    
    # Load config
    config_path = 'mem.config.json'
    if not os.path.exists(config_path):
        safe_print("[ERROR] mem.config.json not found!")
        sys.exit(1)
    
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    # Connect to database
    sql_db = SQLDatabase(config['database']['sql_path'])
    
    # Import interactions
    success = import_interactions(sql_db, export_data, verify_only=args.verify_only)
    
    if success:
        safe_print(f"\n✅ {'Verification' if args.verify_only else 'Import'} complete!")
    else:
        safe_print(f"\n❌ {'Verification' if args.verify_only else 'Import'} failed!")
        sys.exit(1)


if __name__ == '__main__':
    main()

