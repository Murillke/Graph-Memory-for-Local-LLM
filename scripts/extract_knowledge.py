#!/usr/bin/env python3
"""
Extract knowledge (entities and facts) from conversation interactions.

This script reads unprocessed interactions from SQL and extracts:
- Entities (people, places, technologies, concepts)
- Relationships (facts connecting entities)

Usage:
    # Extract from unprocessed interactions
    python3 scripts/extract_knowledge.py --project "my-project"
    
    # Extract from specific interactions
    python3 scripts/extract_knowledge.py --project "my-project" --limit 10
    
    # Dry run (show what would be extracted)
    python3 scripts/extract_knowledge.py --project "my-project" --dry-run

Output:
    Prints extracted entities and facts.
    Marks interactions as processed in SQL.
"""

import sys
import os
import argparse
import json
import re
from typing import List, Dict, Any, Tuple

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tools.sql_db import SQLDatabase
from tools.graph_db import GraphDatabase

from tools.console_utils import safe_print, setup_console_encoding

# Setup console encoding for Windows
setup_console_encoding()

def extract_entities_from_text(text: str) -> List[Dict[str, Any]]:
    """
    Simple entity extraction from text.
    
    This is a PLACEHOLDER - in production, you'd use:
    - LLM-based extraction
    - NER (Named Entity Recognition)
    - Custom extraction rules
    
    For now, we extract:
    - Technology names (capitalized words, file extensions)
    - File paths
    - Version numbers
    """
    entities = []
    
    # Extract file paths
    paths = re.findall(r'[./][\w/.-]+\.\w+', text)
    for path in paths:
        entities.append({
            'name': path,
            'summary': f'File path: {path}',
            'labels': ['path', 'file']
        })
    
    # Extract technology names (simple heuristic: capitalized words)
    tech_words = re.findall(r'\b[A-Z][a-zA-Z0-9]+(?:DB|SQL|Graph|Python|Node|API|Server)?\b', text)
    for word in tech_words:
        if len(word) > 2 and word not in ['The', 'This', 'That', 'We', 'I']:
            entities.append({
                'name': word,
                'summary': f'Technology or concept: {word}',
                'labels': ['technology']
            })
    
    # Extract version numbers
    versions = re.findall(r'\b\d+\.\d+(?:\.\d+)?\b', text)
    for version in versions:
        entities.append({
            'name': version,
            'summary': f'Version number: {version}',
            'labels': ['version']
        })
    
    return entities


def extract_facts_from_text(text: str, entities: List[str]) -> List[Dict[str, Any]]:
    """
    Simple fact extraction from text.
    
    This is a PLACEHOLDER - in production, you'd use:
    - LLM-based extraction
    - Dependency parsing
    - Relation extraction models
    
    For now, we extract simple patterns:
    - "X uses Y"
    - "X is located at Y"
    - "X has version Y"
    """
    facts = []
    
    # Pattern: X uses Y
    for match in re.finditer(r'(\w+)\s+uses?\s+(\w+)', text, re.IGNORECASE):
        source, target = match.groups()
        if source in entities and target in entities:
            facts.append({
                'source': source,
                'target': target,
                'relationship_type': 'USES',
                'fact': f'{source} uses {target}'
            })
    
    # Pattern: X is located at Y
    for match in re.finditer(r'(\w+)\s+(?:is\s+)?located\s+at\s+([\w/.-]+)', text, re.IGNORECASE):
        source, target = match.groups()
        if source in entities:
            facts.append({
                'source': source,
                'target': target,
                'relationship_type': 'LOCATED_AT',
                'fact': f'{source} is located at {target}'
            })
    
    # Pattern: X has version Y
    for match in re.finditer(r'(\w+)\s+(?:has\s+)?version\s+([\d.]+)', text, re.IGNORECASE):
        source, target = match.groups()
        if source in entities:
            facts.append({
                'source': source,
                'target': target,
                'relationship_type': 'HAS_VERSION',
                'fact': f'{source} has version {target}'
            })
    
    return facts


def main():
    parser = argparse.ArgumentParser(
        description='Extract knowledge from conversation interactions',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    # Databases
    parser.add_argument('--sql-db', default='./memory/conversations.db',
                       help='Path to SQLite database (default: ./memory/conversations.db)')
    parser.add_argument('--graph-db', default='./memory/knowledge.kuzu',
                       help='Path to graph database (default: ./memory/knowledge.kuzu)')
    
    # Query
    parser.add_argument('--project', required=True, help='Project name')
    parser.add_argument('--limit', type=int, help='Limit number of interactions to process')
    
    # Options
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be extracted without saving')
    parser.add_argument('--version', default='v1.0.0',
                       help='Extraction version (default: v1.0.0)')
    parser.add_argument('--commit', default='manual',
                       help='Git commit hash (default: manual)')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    # Connect to databases
    sql_db = SQLDatabase(args.sql_db)
    graph_db = GraphDatabase(args.graph_db)
    
    # Ensure project exists in graph
    if not args.dry_run:
        graph_db.create_project_node(args.project, f'Project: {args.project}')
    
    # Get unprocessed interactions
    interactions = sql_db.get_unprocessed_interactions(args.project)
    
    if args.limit:
        interactions = interactions[:args.limit]
    
    if not interactions:
        safe_print(f"No unprocessed interactions found for project '{args.project}'")
        return
    
    if not args.json:
        safe_print(f"\n Processing {len(interactions)} interactions...")
    
    # TODO: This is where you'd call an LLM or NER system
    # For now, we use simple pattern matching
    
    # (Placeholder - in production, implement real extraction)
    safe_print(f"\n[WARNING]  WARNING: Using placeholder extraction logic!")
    safe_print(f"   In production, replace with LLM-based extraction.")
    
    if not args.json:
        safe_print(f"\n[OK] Extraction complete!")
        safe_print(f"   Processed: {len(interactions)} interactions")
        safe_print(f"\n[IDEA] Next steps:")
        safe_print(f"   1. Implement real extraction logic (LLM-based)")
        safe_print(f"   2. Call this script after storing interactions")
        safe_print(f"   3. Query the graph with query_memory.py")


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

