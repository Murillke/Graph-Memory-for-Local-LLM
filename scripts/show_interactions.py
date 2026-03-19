#!/usr/bin/env python3
"""
Show recent interactions from SQL conversation history.
"""

import sys
import os
import argparse
import sqlite3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from tools.config import Config


HISTORY_EXAMPLES = """
Examples:
  # Last 10 interactions
  python scripts/show_interactions.py --project llm_memory --last 10

  # Last 3 sessions (grouped)
  python scripts/show_interactions.py --project llm_memory --sessions 3

  # Full content (not truncated)
  python scripts/show_interactions.py --project llm_memory --sessions 3 --full

  # Specific interaction by UUID
  python scripts/show_interactions.py --project llm_memory --uuid abc123
"""


class HistoryArgumentParser(argparse.ArgumentParser):
    """Custom parser that prints examples on error."""
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: error: {message}\n{HISTORY_EXAMPLES}")


def main():
    parser = HistoryArgumentParser(
        description='Show SQL conversation history',
        epilog=HISTORY_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--project', required=True, help='Project name')
    parser.add_argument('--last', type=int, default=5, help='Number of recent interactions (default: 5)')
    parser.add_argument('--sessions', type=int, help='Number of recent conversation sessions (grouped by timestamp)')
    parser.add_argument('--uuid', help='Show specific interaction by UUID')
    parser.add_argument('--full', action='store_true', help='Show full message content (default: truncated)')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    args = parser.parse_args()

    config = Config(project_name=args.project)
    sql_path = config.get('database.sql_path', './memory/conversations.db')
    
    if not os.path.exists(sql_path):
        print(f"[ERROR] SQL database not found: {sql_path}")
        sys.exit(1)

    conn = sqlite3.connect(sql_path)
    cursor = conn.cursor()

    if args.sessions:
        # Get distinct session timestamps (truncated to second)
        cursor.execute('''
            SELECT DISTINCT substr(timestamp, 1, 19) as session_ts
            FROM interactions
            WHERE project_name = ?
            ORDER BY session_ts DESC
            LIMIT ?
        ''', (args.project, args.sessions))

        session_timestamps = [row[0] for row in cursor.fetchall()]

        if not session_timestamps:
            print(f"[INFO] No sessions found for project: {args.project}")
            sys.exit(0)

        print(f"Last {len(session_timestamps)} conversation sessions for project '{args.project}':\n")

        for session_ts in reversed(session_timestamps):
            cursor.execute('''
                SELECT uuid, timestamp, user_message, assistant_message
                FROM interactions
                WHERE project_name = ? AND timestamp LIKE ?
                ORDER BY timestamp ASC
            ''', (args.project, f'{session_ts}%'))

            rows = cursor.fetchall()
            print(f"{'='*60}")
            print(f"SESSION: {session_ts} ({len(rows)} exchanges)")
            print(f"{'='*60}")

            for row in rows:
                uuid, timestamp, user_msg, asst_msg = row

                if args.full:
                    user_display = user_msg
                    asst_display = asst_msg
                else:
                    user_display = (user_msg[:150] + '...') if len(user_msg) > 150 else user_msg
                    asst_display = (asst_msg[:150] + '...') if len(asst_msg) > 150 else asst_msg

                print(f"\n[{uuid[:16]}...]")
                print(f"USER: {user_display}")
                print(f"ASST: {asst_display}")
            print()

    elif args.uuid:
        cursor.execute('''
            SELECT uuid, timestamp, user_message, assistant_message, project_name
            FROM interactions 
            WHERE uuid LIKE ?
            LIMIT 1
        ''', (f'{args.uuid}%',))
        row = cursor.fetchone()
        if row:
            print(f"UUID: {row[0]}")
            print(f"Timestamp: {row[1]}")
            print(f"Project: {row[4]}")
            print(f"\n=== USER ===\n{row[2]}")
            print(f"\n=== ASSISTANT ===\n{row[3]}")
        else:
            print(f"[ERROR] No interaction found matching UUID: {args.uuid}")
            sys.exit(1)
    else:
        cursor.execute('''
            SELECT uuid, timestamp, user_message, assistant_message
            FROM interactions 
            WHERE project_name = ?
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (args.project, args.last))
        
        rows = cursor.fetchall()
        
        if not rows:
            print(f"[INFO] No interactions found for project: {args.project}")
            sys.exit(0)

        if args.json:
            import json
            output = []
            for row in rows:
                output.append({
                    'uuid': row[0],
                    'timestamp': row[1],
                    'user': row[2],
                    'assistant': row[3]
                })
            print(json.dumps(output))
        else:
            print(f"Last {len(rows)} interactions for project '{args.project}':\n")
            for row in reversed(rows):  # Show oldest first
                uuid, timestamp, user_msg, asst_msg = row
                
                if args.full:
                    user_display = user_msg
                    asst_display = asst_msg
                else:
                    user_display = (user_msg[:200] + '...') if len(user_msg) > 200 else user_msg
                    asst_display = (asst_msg[:200] + '...') if len(asst_msg) > 200 else asst_msg
                
                print(f"=== {timestamp} ({uuid[:16]}...) ===")
                print(f"USER: {user_display}")
                print(f"ASST: {asst_display}")
                print()

    conn.close()

if __name__ == '__main__':
    main()

