#!/usr/bin/env python3
"""
Store a conversation interaction in the memory system.

Usage:
    python3 scripts/store_interaction.py \\
        --project "my-project" \\
        --user "We are using LadybugDB" \\
        --assistant "Great choice!"

    # With path (auto-associates path with project)
    python3 scripts/store_interaction.py \\
        --path "/Users/me/project" \\
        --user "We are using LadybugDB" \\
        --assistant "Great choice!"

Output:
    Prints the interaction UUID and content hash.
"""

import sys
import os
import argparse
import json
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tools.sql_db import SQLDatabase
from tools.config import load_config

from tools.console_utils import safe_print, setup_console_encoding

# Setup console encoding for Windows
setup_console_encoding()

def main():
    parser = argparse.ArgumentParser(
        description='Store a conversation interaction in the memory system',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    # Project identification
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--project', help='Project name')
    group.add_argument('--path', help='File path (will auto-lookup or create project)')
    
    # Interaction content
    parser.add_argument('--user', required=True, help='User message')
    parser.add_argument('--assistant', required=True, help='Assistant message')
    
    # Optional
    parser.add_argument('--db', help='Path to SQLite database (default: from config)')
    parser.add_argument('--json', action='store_true',
                       help='Output as JSON instead of human-readable')
    
    args = parser.parse_args()

    project_for_config = args.project or (os.path.basename(args.path.rstrip('/\\')) if args.path else None)
    config = load_config(project_name=project_for_config, cli_args={"sql_db": args.db})
    args.db = config.get_sql_db_path()
    
    # Connect to database
    db = SQLDatabase(args.db)
    
    # Get or create project
    if args.path:
        # Lookup project by path
        project = db.get_project_by_path(args.path)
        if not project:
            # Create project from path
            project_name = os.path.basename(args.path.rstrip('/'))
            db.create_project(project_name, f"Project at {args.path}")
            db.associate_path_with_project(args.path, project_name)
            if not args.json:
                safe_print(f"[OK] Created new project: {project_name}")
        else:
            project_name = project['name']
    else:
        project_name = args.project
        # Check if project exists
        project = db.get_project_by_name(project_name)
        if not project:
            db.create_project(project_name, f"Project: {project_name}")
            if not args.json:
                safe_print(f"[OK] Created new project: {project_name}")
    
    # Store interaction
    interaction = {
        'project_name': project_name,
        'user_message': args.user,
        'assistant_message': args.assistant
    }
    
    uuid = db.store_interaction(interaction)
    
    # Get the stored interaction to show hash
    stored = db.get_interaction_by_uuid(uuid)
    
    # Output
    if args.json:
        safe_print(json.dumps({
            'uuid': uuid,
            'project_name': project_name,
            'content_hash': stored['content_hash'],
            'chain_index': stored['chain_index'],
            'timestamp': stored['timestamp']
        }, indent=2))
    else:
        safe_print(f"\n[OK] Interaction stored successfully!")
        safe_print(f"\n[LIST] Details:")
        safe_print(f"   UUID:         {uuid}")
        safe_print(f"   Project:      {project_name}")
        safe_print(f"   Chain Index:  {stored['chain_index']}")
        safe_print(f"   Content Hash: {stored['content_hash'][:16]}...")
        safe_print(f"   Timestamp:    {stored['timestamp']}")
        safe_print(f"\n[COMMENT] Content:")
        safe_print(f"   User:      {args.user[:60]}{'...' if len(args.user) > 60 else ''}")
        safe_print(f"   Assistant: {args.assistant[:60]}{'...' if len(args.assistant) > 60 else ''}")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        safe_print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        safe_print(f"\n[ERROR] Error: {e}", file=sys.stderr)
        sys.exit(1)

