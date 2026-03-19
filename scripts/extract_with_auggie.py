#!/usr/bin/env python3
"""
Extract knowledge from interactions - Interactive mode with Auggie.

This script reads interactions and presents them to you (or Auggie) for extraction.
Auggie can then extract entities and facts using his own LLM capabilities.

Usage:
    python3 scripts/extract_with_auggie.py --project "my-project"

How it works:
    1. Reads unprocessed interactions from SQL
    2. Shows them to you/Auggie
    3. You provide the extracted entities and facts (as JSON)
    4. Script stores them in the graph database

This is the "human-in-the-loop" approach where Auggie does the thinking,
not an external API.
"""

import sys
import os
import argparse
import json

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tools.sql_db import SQLDatabase
from tools.graph_db import GraphDatabase

from tools.console_utils import safe_print, setup_console_encoding

# Setup console encoding for Windows
setup_console_encoding()

def main():
    parser = argparse.ArgumentParser(
        description='Extract knowledge with Auggie (interactive)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument('--project', required=True, help='Project name')
    parser.add_argument('--limit', type=int, default=5, help='Number of interactions to show (default: 5)')
    parser.add_argument('--sql-db', default='./memory/conversations.db', help='Path to SQL database')
    parser.add_argument('--graph-db', default='./memory/gml-llm.db', help='Path to graph database')
    
    args = parser.parse_args()
    
    # Connect to databases
    sql_db = SQLDatabase(args.sql_db)
    graph_db = GraphDatabase(args.graph_db)
    
    # Get unprocessed interactions
    interactions = sql_db.get_unprocessed_interactions(args.project)
    
    if not interactions:
        safe_print(f"[OK] No unprocessed interactions for project '{args.project}'")
        return
    
    # Apply limit
    interactions = interactions[:args.limit]
    
    safe_print(f"\n{'='*60}")
    safe_print(f"[DATA] Showing {len(interactions)} unprocessed interactions")
    safe_print(f"{'='*60}\n")
    
    # Show interactions
    for i, interaction in enumerate(interactions, 1):
        safe_print(f"Interaction #{i} (UUID: {interaction['uuid']})")
        safe_print(f"Timestamp: {interaction['timestamp']}")
        safe_print(f"\n User:")
        safe_print(f"   {interaction['user_message']}")
        safe_print(f"\n[AI] Assistant:")
        safe_print(f"   {interaction['assistant_message']}")
        safe_print(f"\n{'-'*60}\n")
    
    safe_print(f"\n{'='*60}")
    safe_print("[AI] AUGGIE: Please extract entities and facts from these interactions")
    safe_print("="*60)
    safe_print("\nFor each interaction, provide:")
    safe_print("1. Entities (name, type, summary)")
    safe_print("2. Facts (source_entity, target_entity, relationship_type, fact)")
    safe_print("\nExample format:")
    safe_print(json.dumps({
        "interaction_uuid": "uuid-123",
        "entities": [
            {"name": "React", "type": "Technology", "summary": "JavaScript library for UIs"},
            {"name": "Python", "type": "Technology", "summary": "Programming language"}
        ],
        "facts": [
            {
                "source_entity": "LadybugDB",
                "target_entity": "Python",
                "relationship_type": "BUILT_WITH",
                "fact": "LadybugDB is built with Python"
            }
        ]
    }, indent=2))
    
    safe_print("\n\n[NOTE] Auggie will now analyze these interactions and provide extraction results...")
    safe_print("(This is where Auggie would use his LLM capabilities to extract knowledge)")
    safe_print("\n[WARNING]  TODO: Implement the actual extraction and storage logic")


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

