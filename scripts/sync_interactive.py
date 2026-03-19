#!/usr/bin/env python3
"""
Interactive Memory Sync - Auggie extracts knowledge interactively.

This script shows Auggie the unprocessed interactions and prompts him to extract
entities and facts. Auggie uses his own LLM capabilities to do the extraction.

Usage:
    python3 scripts/sync_interactive.py --project "gml-llm"
    python3 scripts/sync_interactive.py --project "gml-llm" --limit 5
"""

import argparse
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tools.sql_db import SQLDatabase
from tools.config import load_config

from tools.console_utils import safe_print, setup_console_encoding

# Setup console encoding for Windows
setup_console_encoding()

def show_interactions_for_sync(
    project_name: str,
    limit: int = None,
    include_confidential: bool = False
):
    """
    Show unprocessed interactions and extraction instructions for Auggie.
    
    Args:
        project_name: Project name
        limit: Maximum number of interactions to show
        include_confidential: Include confidential interactions
    """
    safe_print("=" * 60)
    safe_print(f"[SYNC] Memory Sync for project '{project_name}'")
    safe_print("=" * 60)
    safe_print()
    
    # Initialize database
    config = load_config(project_name=project_name)
    sql_db = SQLDatabase(config.get_sql_db_path())
    
    # Get unprocessed interactions
    interactions = sql_db.get_unprocessed_interactions(
        project_name,
        include_confidential=include_confidential
    )
    
    if not interactions:
        safe_print("[OK] No unprocessed interactions found. Memory is up to date!")
        return
    
    if limit:
        interactions = interactions[:limit]
    
    safe_print(f"[DATA] Found {len(interactions)} unprocessed interaction(s)")
    safe_print()
    
    # Show each interaction with extraction instructions
    for i, interaction in enumerate(interactions, 1):
        uuid = interaction['uuid']
        chain_index = interaction['chain_index']
        user_msg = interaction['user_message']
        assistant_msg = interaction['assistant_message']
        timestamp = interaction['timestamp']
        
        safe_print("=" * 60)
        safe_print(f"Interaction #{chain_index} ({i}/{len(interactions)})")
        safe_print("=" * 60)
        safe_print(f"UUID: {uuid}")
        safe_print(f"Timestamp: {timestamp}")
        safe_print()
        safe_print(f" User:")
        safe_print(f"   {user_msg[:200]}{'...' if len(user_msg) > 200 else ''}")
        safe_print()
        safe_print(f"[AI] Assistant:")
        safe_print(f"   {assistant_msg[:200]}{'...' if len(assistant_msg) > 200 else ''}")
        safe_print()
    
    safe_print("=" * 60)
    safe_print("[AI] AUGGIE: Your Task")
    safe_print("=" * 60)
    safe_print()
    safe_print(f"Please extract entities and facts from these {len(interactions)} interaction(s).")
    safe_print()
    safe_print("For each interaction:")
    safe_print("1. Extract entities (name, type, summary)")
    safe_print("2. Extract facts (source, target, relationship, description)")
    safe_print()
    safe_print("Then create a JSON file with this format:")
    safe_print()
    safe_print('{')
    safe_print('  "project_name": "' + project_name + '",')
    safe_print('  "extraction_version": "v1.0.0",')
    safe_print('  "extraction_commit": "manual",')
    safe_print('  "extractions": [')
    safe_print('    {')
    safe_print('      "interaction_uuid": "uuid-...",')
    safe_print('      "entities": [')
    safe_print('        {"name": "...", "type": "...", "summary": "..."}')
    safe_print('      ],')
    safe_print('      "facts": [')
    safe_print('        {')
    safe_print('          "source_entity": "...",')
    safe_print('          "target_entity": "...",')
    safe_print('          "relationship_type": "...",')
    safe_print('          "fact": "..."')
    safe_print('        }')
    safe_print('      ]')
    safe_print('    }')
    safe_print('  ]')
    safe_print('}')
    safe_print()
    safe_print("Save the JSON file, then run:")
    safe_print(f"  python3 scripts/store_extraction.py --project \"{project_name}\" --extraction-file <your-file.json>")
    safe_print()
    safe_print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Show interactions for Auggie to extract knowledge")
    parser.add_argument("--project", required=True, help="Project name")
    parser.add_argument("--limit", type=int, help="Maximum number of interactions to show")
    parser.add_argument("--include-confidential", action="store_true", help="Include confidential interactions")
    
    args = parser.parse_args()
    
    show_interactions_for_sync(
        args.project,
        limit=args.limit,
        include_confidential=args.include_confidential
    )
