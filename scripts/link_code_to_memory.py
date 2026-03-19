#!/usr/bin/env python3
"""
Link commits to conversation memory using LLM-powered semantic correlation.

This analyzes commits and finds related entities/interactions based on:
- Temporal proximity (12-hour window)
- Semantic matching (commit message, file names, keywords)
- Confidence scoring
"""

import sys
import os
import argparse
from datetime import datetime, timedelta
import json

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tools.code_graph import CodeGraphDB
import kuzu


def get_commit_details(code_graph, commit_hash):
    """Get commit details from code graph."""
    try:
        result = code_graph.conn.execute("""
            MATCH (c:Commit {hash: $hash})
            RETURN c.hash, c.message, c.author, c.timestamp, c.branch
        """, {'hash': commit_hash})
        
        if result.has_next():
            row = result.get_next()
            return {
                'hash': row[0],
                'message': row[1],
                'author': row[2],
                'timestamp': row[3],
                'branch': row[4]
            }
        return None
    except Exception as e:
        print(f"[ERROR] Failed to get commit details: {e}")
        return None


def get_commit_files(code_graph, commit_hash):
    """Get files modified in commit."""
    try:
        result = code_graph.conn.execute("""
            MATCH (c:Commit {hash: $hash})-[r:MODIFIED]->(f:File)
            RETURN f.path, r.lines_added, r.lines_removed, r.change_type
        """, {'hash': commit_hash})
        
        files = []
        while result.has_next():
            row = result.get_next()
            files.append({
                'path': row[0],
                'lines_added': row[1],
                'lines_removed': row[2],
                'change_type': row[3]
            })
        return files
    except Exception as e:
        print(f"[ERROR] Failed to get commit files: {e}")
        return []


def get_entities_in_window(conversation_db, commit_timestamp, window_hours=12):
    """Get entities created within time window of commit."""
    try:
        # Calculate time window
        start_time = commit_timestamp - timedelta(hours=window_hours)
        end_time = commit_timestamp + timedelta(hours=2)  # 2 hours after
        
        result = conversation_db.execute("""
            MATCH (e:Entity)
            WHERE e.created_at >= $start AND e.created_at <= $end
            RETURN e.uuid, e.name, e.type, e.summary, e.created_at
            ORDER BY e.created_at DESC
        """, {
            'start': start_time,
            'end': end_time
        })
        
        entities = []
        while result.has_next():
            row = result.get_next()
            entities.append({
                'uuid': row[0],
                'name': row[1],
                'type': row[2],
                'summary': row[3],
                'created_at': row[4]
            })
        return entities
    except Exception as e:
        print(f"[ERROR] Failed to get entities: {e}")
        return []


def calculate_confidence(commit, entities, files):
    """
    Calculate confidence score for commit-entity correlation.
    
    Returns list of (entity, confidence, reasoning) tuples.
    """
    correlations = []
    
    commit_time = commit['timestamp']
    commit_msg = commit['message'].lower()
    file_paths = [f['path'].lower() for f in files]
    
    for entity in entities:
        entity_time = entity['created_at']
        entity_name = entity['name'].lower()
        entity_summary = entity['summary'].lower()
        
        # Calculate temporal proximity score (0-100)
        time_diff = abs((commit_time - entity_time).total_seconds())
        hours_diff = time_diff / 3600
        
        if hours_diff < 0.5:  # Within 30 minutes
            temporal_score = 100
        elif hours_diff < 2:  # Within 2 hours
            temporal_score = 80
        elif hours_diff < 6:  # Within 6 hours
            temporal_score = 60
        elif hours_diff < 12:  # Within 12 hours
            temporal_score = 40
        else:
            temporal_score = 20
        
        # Calculate semantic score (0-100)
        semantic_score = 0
        semantic_reasons = []
        
        # Check if entity name in commit message
        if entity_name in commit_msg:
            semantic_score += 50
            semantic_reasons.append(f"Entity name '{entity['name']}' in commit message")
        
        # Check if keywords from entity in commit message
        entity_keywords = set(entity_name.split()) | set(entity_summary.split())
        commit_keywords = set(commit_msg.split())
        common_keywords = entity_keywords & commit_keywords
        
        if len(common_keywords) > 2:
            semantic_score += 30
            semantic_reasons.append(f"{len(common_keywords)} matching keywords")
        elif len(common_keywords) > 0:
            semantic_score += 15
            semantic_reasons.append(f"{len(common_keywords)} matching keyword(s)")
        
        # Check if entity keywords in file paths
        for file_path in file_paths:
            for keyword in entity_keywords:
                if len(keyword) > 3 and keyword in file_path:
                    semantic_score += 10
                    semantic_reasons.append(f"Keyword '{keyword}' in file path")
                    break
        
        # Cap semantic score at 100
        semantic_score = min(semantic_score, 100)
        
        # Combined confidence (weighted average)
        # Temporal is more important (60%) than semantic (40%)
        confidence = int(temporal_score * 0.6 + semantic_score * 0.4)
        
        # Build reasoning
        reasoning_parts = [
            f"Temporal: {hours_diff:.1f}h before commit ({temporal_score}%)",
            f"Semantic: {semantic_score}%"
        ]
        if semantic_reasons:
            reasoning_parts.extend(semantic_reasons)
        
        reasoning = " | ".join(reasoning_parts)
        
        correlations.append((entity, confidence, reasoning))
    
    # Sort by confidence (highest first)
    correlations.sort(key=lambda x: x[1], reverse=True)
    
    return correlations


def main():
    parser = argparse.ArgumentParser(description='Link commit to conversation memory')
    parser.add_argument('--commit', required=True, help='Commit hash')
    parser.add_argument('--project', default='llm_memory', help='Project name')
    parser.add_argument('--min-confidence', type=int, default=40, help='Minimum confidence score (0-100)')
    
    args = parser.parse_args()
    
    print(f"[INFO] Analyzing commit: {args.commit[:8]}")
    print("="*80)
    
    # Open code graph
    code_graph = CodeGraphDB(args.project)
    
    # Get commit details
    commit = get_commit_details(code_graph, args.commit)
    if not commit:
        print(f"[ERROR] Commit not found: {args.commit}")
        return 1
    
    print(f"Message: {commit['message']}")
    print(f"Author: {commit['author']}")
    print(f"Time: {commit['timestamp']}")
    print(f"Branch: {commit['branch']}")
    print()
    
    # Get commit files
    files = get_commit_files(code_graph, args.commit)
    print(f"Files changed: {len(files)}")
    for f in files[:5]:  # Show first 5
        print(f"  {f['change_type']:8} {f['path']}")
    if len(files) > 5:
        print(f"  ... and {len(files) - 5} more")
    print()
    
    # Use the same database connection (code and conversation in same DB!)
    conversation_conn = code_graph.conn
    
    # Get entities in time window
    entities = get_entities_in_window(conversation_conn, commit['timestamp'])
    print(f"Entities in 12-hour window: {len(entities)}")
    print()
    
    if not entities:
        print("[INFO] No entities found in time window.")
        print("[SUGGESTION] Run sync.md to capture recent work in memory.")
        return 0
    
    # Calculate correlations
    correlations = calculate_confidence(commit, entities, files)
    
    # Filter by minimum confidence
    high_confidence = [(e, c, r) for e, c, r in correlations if c >= args.min_confidence]
    
    if not high_confidence:
        print(f"[INFO] No entities with confidence >= {args.min_confidence}%")
        print()
        print("Top 3 candidates:")
        for entity, confidence, reasoning in correlations[:3]:
            print(f"  {confidence}% - {entity['name']}")
            print(f"         {reasoning}")
        return 0
    
    print(f"Related entities (confidence >= {args.min_confidence}%):")
    print("="*80)
    
    for entity, confidence, reasoning in high_confidence:
        print(f"\n{confidence}% - {entity['name']} ({entity['type']})")
        print(f"  Created: {entity['created_at']}")
        print(f"  Summary: {entity['summary'][:100]}...")
        print(f"  Reasoning: {reasoning}")
    
    # Only close once (same connection)
    code_graph.close()
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

