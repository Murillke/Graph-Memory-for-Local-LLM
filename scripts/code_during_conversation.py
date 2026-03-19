#!/usr/bin/env python3
"""
Show code changes that happened during a conversation/interaction.

Finds commits within the time window of an interaction.
"""

import sys
import os
import argparse
from datetime import timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tools.code_graph import CodeGraphDB
import kuzu


def main():
    parser = argparse.ArgumentParser(description='Show code changes during conversation')
    parser.add_argument('--interaction', required=True, help='Interaction UUID')
    parser.add_argument('--project', default='llm_memory', help='Project name')
    parser.add_argument('--window-hours', type=int, default=12, help='Time window (hours)')
    
    args = parser.parse_args()
    
    # Open code graph (same database as conversation graph!)
    code_graph = CodeGraphDB(args.project)

    # Use same connection for both
    conversation_conn = code_graph.conn
    
    # Get interaction details
    result = conversation_conn.execute("""
        MATCH (i:Interaction {uuid: $uuid})
        RETURN i.uuid, i.timestamp, i.user_message, i.assistant_message
    """, {'uuid': args.interaction})
    
    if not result.has_next():
        print(f"[ERROR] Interaction not found: {args.interaction}")
        return 1
    
    row = result.get_next()
    interaction = {
        'uuid': row[0],
        'timestamp': row[1],
        'user_message': row[2],
        'assistant_message': row[3]
    }
    
    print(f"[INFO] Interaction: {interaction['uuid']}")
    print(f"Time: {interaction['timestamp']}")
    print(f"User: {interaction['user_message'][:80]}...")
    print()
    
    # Calculate time window
    start_time = interaction['timestamp'] - timedelta(hours=args.window_hours)
    end_time = interaction['timestamp'] + timedelta(hours=2)
    
    # Find commits in time window
    result = code_graph.conn.execute("""
        MATCH (c:Commit)
        WHERE c.timestamp >= $start AND c.timestamp <= $end
        RETURN c.hash, c.message, c.author, c.timestamp
        ORDER BY c.timestamp DESC
    """, {'start': start_time, 'end': end_time})
    
    commits = []
    while result.has_next():
        row = result.get_next()
        commits.append({
            'hash': row[0],
            'message': row[1],
            'author': row[2],
            'timestamp': row[3]
        })
    
    if not commits:
        print(f"[INFO] No commits found in {args.window_hours}-hour window")
        return 0
    
    print(f"Commits in time window ({len(commits)}):")
    print("="*80)
    
    for commit in commits:
        time_diff = (commit['timestamp'] - interaction['timestamp']).total_seconds() / 3600
        if time_diff < 0:
            time_str = f"{abs(time_diff):.1f}h before"
        else:
            time_str = f"{time_diff:.1f}h after"
        
        print(f"\n{commit['hash'][:8]} - {time_str}")
        print(f"  {commit['message']}")
        print(f"  by {commit['author']} at {commit['timestamp']}")
        
        # Get files changed
        file_result = code_graph.conn.execute("""
            MATCH (c:Commit {hash: $hash})-[r:MODIFIED]->(f:File)
            RETURN f.path, r.change_type
        """, {'hash': commit['hash']})
        
        files = []
        while file_result.has_next():
            file_row = file_result.get_next()
            files.append({'path': file_row[0], 'type': file_row[1]})
        
        if files:
            print(f"  Files ({len(files)}):")
            for f in files[:3]:
                print(f"    {f['type']:8} {f['path']}")
            if len(files) > 3:
                print(f"    ... and {len(files) - 3} more")
    
    # Only close once (same connection)
    code_graph.close()
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

