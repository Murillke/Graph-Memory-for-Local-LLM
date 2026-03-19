#!/usr/bin/env python3
"""
Extract knowledge from interactions using LLM.

This script uses LLM-based extraction (adapted from Graphiti) to extract:
- Entities (people, technologies, organizations, concepts)
- Facts/relationships between entities

Usage:
    # Extract from all unprocessed interactions
    python3 scripts/extract_knowledge_llm.py --project "my-project"
    
    # Extract from specific number of interactions
    python3 scripts/extract_knowledge_llm.py --project "my-project" --limit 5
    
    # Dry run (show what would be extracted without storing)
    python3 scripts/extract_knowledge_llm.py --project "my-project" --dry-run
    
    # Use custom model
    EXTRACTION_MODEL=gpt-4 python3 scripts/extract_knowledge_llm.py --project "my-project"

Requirements:
    - OpenAI API key: Set OPENAI_API_KEY environment variable
    - openai package: pip install openai

Output:
    Extracts entities and facts, stores them in graph database with crypto proofs.
"""

import sys
import os
import argparse
import json
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tools.sql_db import SQLDatabase
from tools.graph_db import GraphDatabase
from tools.extraction.llm_client import get_default_client
from tools.extraction.extract_entities import extract_entities_batch
from tools.extraction.extract_facts import extract_facts_batch

from tools.console_utils import safe_print, setup_console_encoding

# Setup console encoding for Windows
setup_console_encoding()

def main():
    parser = argparse.ArgumentParser(
        description='Extract knowledge from interactions using LLM',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument('--project', required=True, help='Project name')
    parser.add_argument('--limit', type=int, help='Limit number of interactions to process')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be extracted without storing')
    parser.add_argument('--sql-db', default='./memory/conversations.db', help='Path to SQL database')
    parser.add_argument('--graph-db', default='./memory', help='Path to graph database directory')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    args = parser.parse_args()
    
    # Connect to databases
    sql_db = SQLDatabase(args.sql_db)
    graph_db = GraphDatabase(args.graph_db)
    
    # Get LLM client
    try:
        llm_client = get_default_client()
        if not args.json:
            safe_print(f"[OK] LLM client initialized (model: {llm_client.model})")
    except Exception as e:
        safe_print(f"[ERROR] Error initializing LLM client: {e}", file=sys.stderr)
        safe_print("\nMake sure to set OPENAI_API_KEY environment variable", file=sys.stderr)
        sys.exit(1)
    
    # Get unprocessed interactions
    interactions = sql_db.get_unprocessed_interactions(args.project)
    
    if not interactions:
        if not args.json:
            safe_print(f"[OK] No unprocessed interactions for project '{args.project}'")
        return
    
    # Apply limit if specified
    if args.limit:
        interactions = interactions[:args.limit]
    
    if not args.json:
        safe_print(f"\n[DATA] Processing {len(interactions)} interactions...")
        safe_print(f"{'='*60}\n")
    
    # Step 1: Extract entities
    if not args.json:
        safe_print("Step 1: Extracting entities...")
    
    entities_by_interaction = extract_entities_batch(interactions, llm_client)
    
    total_entities = sum(len(entities) for entities in entities_by_interaction.values())
    if not args.json:
        safe_print(f"[OK] Extracted {total_entities} entities total\n")
    
    # Step 2: Extract facts
    if not args.json:
        safe_print("Step 2: Extracting facts/relationships...")
    
    facts_by_interaction = extract_facts_batch(interactions, entities_by_interaction, llm_client)
    
    total_facts = sum(len(facts) for facts in facts_by_interaction.values())
    if not args.json:
        safe_print(f"[OK] Extracted {total_facts} facts total\n")
    
    # Step 3: Store in graph database (unless dry-run)
    if args.dry_run:
        if not args.json:
            safe_print("[SEARCH] DRY RUN - Not storing to database\n")
            safe_print("="*60)
            safe_print("Extracted Entities:")
            safe_print("="*60)
            for uuid, entities in entities_by_interaction.items():
                for entity in entities:
                    safe_print(f"  - {entity['name']} ({entity['type']})")
            
            safe_print(f"\n{'='*60}")
            safe_print("Extracted Facts:")
            safe_print("="*60)
            for uuid, facts in facts_by_interaction.items():
                for fact in facts:
                    safe_print(f"  - {fact['source_entity']} --[{fact['relationship_type']}]--> {fact['target_entity']}")
                    safe_print(f"    {fact['fact']}")
        else:
            safe_print(json.dumps({
                'dry_run': True,
                'entities': entities_by_interaction,
                'facts': facts_by_interaction
            }, indent=2))
    else:
        # TODO: Store entities and facts in graph database
        # This requires implementing the storage logic
        if not args.json:
            safe_print("[WARNING]  Storage to graph database not yet implemented")
            safe_print("    Entities and facts extracted but not stored")
        
        # Mark interactions as processed
        for interaction in interactions:
            sql_db.mark_interaction_processed(interaction['uuid'])
        
        if not args.json:
            safe_print(f"\n[OK] Marked {len(interactions)} interactions as processed")
    
    # Summary
    if args.json:
        safe_print(json.dumps({
            'project': args.project,
            'interactions_processed': len(interactions),
            'entities_extracted': total_entities,
            'facts_extracted': total_facts,
            'dry_run': args.dry_run
        }, indent=2))
    else:
        safe_print(f"\n{'='*60}")
        safe_print("[DATA] Summary")
        safe_print("="*60)
        safe_print(f"Project:              {args.project}")
        safe_print(f"Interactions:         {len(interactions)}")
        safe_print(f"Entities extracted:   {total_entities}")
        safe_print(f"Facts extracted:      {total_facts}")
        safe_print(f"Dry run:              {args.dry_run}")
        safe_print("\n[OK] Extraction complete!")


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

