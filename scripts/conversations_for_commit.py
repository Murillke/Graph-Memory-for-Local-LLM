#!/usr/bin/env python3
"""
Show conversations related to a commit.

Uses LLM-powered semantic correlation to find relevant entities/interactions.
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# This is essentially a wrapper around link_code_to_memory.py
from scripts.link_code_to_memory import (
    get_commit_details,
    get_commit_files,
    get_entities_in_window,
    calculate_confidence
)
from tools.code_graph import CodeGraphDB
import kuzu


def main():
    parser = argparse.ArgumentParser(description='Show conversations related to commit')
    parser.add_argument('--commit', required=True, help='Commit hash')
    parser.add_argument('--project', default='llm_memory', help='Project name')
    parser.add_argument('--min-confidence', type=int, default=50, help='Minimum confidence score')
    
    args = parser.parse_args()
    
    print(f"[INFO] Finding conversations for commit: {args.commit[:8]}")
    print("="*80)
    
    # Open code graph
    code_graph = CodeGraphDB(args.project)
    
    # Get commit details
    commit = get_commit_details(code_graph, args.commit)
    if not commit:
        print(f"[ERROR] Commit not found: {args.commit}")
        return 1
    
    print(f"Commit: {commit['hash'][:8]}")
    print(f"Message: {commit['message']}")
    print(f"Time: {commit['timestamp']}")
    print()
    
    # Get commit files
    files = get_commit_files(code_graph, args.commit)
    
    # Use same connection (code and conversation in same DB!)
    conversation_conn = code_graph.conn
    
    # Get entities in time window
    entities = get_entities_in_window(conversation_conn, commit['timestamp'])
    
    if not entities:
        print("[INFO] No entities found in 12-hour window around commit.")
        print("[SUGGESTION] Run sync.md to capture conversations in memory.")
        conversation_conn.close()
        code_graph.close()
        return 0
    
    # Calculate correlations
    correlations = calculate_confidence(commit, entities, files)
    
    # Filter by confidence
    high_confidence = [(e, c, r) for e, c, r in correlations if c >= args.min_confidence]
    
    if not high_confidence:
        print(f"[INFO] No entities with confidence >= {args.min_confidence}%")
        print()
        print("Try lowering --min-confidence or check if sync.md was run recently.")
        conversation_conn.close()
        code_graph.close()
        return 0
    
    print(f"Related entities (confidence >= {args.min_confidence}%):")
    print("="*80)
    
    for entity, confidence, reasoning in high_confidence:
        print(f"\n{confidence}% - {entity['name']} ({entity['type']})")
        print(f"  UUID: {entity['uuid']}")
        print(f"  Created: {entity['created_at']}")
        print(f"  Summary: {entity['summary'][:150]}...")
        print(f"  Reasoning: {reasoning}")
        
        # Get interaction for this entity
        interaction_result = conversation_conn.execute("""
            MATCH (i:Interaction)-[:EXTRACTED]->(e:Entity {uuid: $uuid})
            RETURN i.uuid, i.user_message
        """, {'uuid': entity['uuid']})
        
        if interaction_result.has_next():
            int_row = interaction_result.get_next()
            print(f"  Interaction: {int_row[0]}")
            print(f"  User message: {int_row[1][:100]}...")
    
    # Only close once (same connection)
    code_graph.close()
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

