#!/usr/bin/env python3
"""
Extract knowledge from pending conversations.

Finds conversations that have been dumped (in SQL with timestamps)
but not yet extracted (no entities in graph).

Usage:
    # Extract all pending (up to 50)
    python scripts/extract_pending.py --project llm_memory

    # Extract with custom limit
    python scripts/extract_pending.py --project llm_memory --limit 10

    # Extract all (no limit)
    python scripts/extract_pending.py --project llm_memory --all

    # Extract specific conversation
    python scripts/extract_pending.py --project llm_memory --uuid uuid-abc123
"""

import sys
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.sql_db import SQLDatabase
from tools.config import load_config


EXTRACT_PENDING_EXAMPLES = """
Examples:
  # Find pending conversations (up to 50)
  python scripts/extract_pending.py --project llm_memory

  # Find with custom limit
  python scripts/extract_pending.py --project llm_memory --limit 10

  # Find all pending (no limit)
  python scripts/extract_pending.py --project llm_memory --all

  # Check specific conversation
  python scripts/extract_pending.py --project llm_memory --uuid uuid-abc123

Note: Copy the UUIDs from output into your extraction file.
"""


class ExtractPendingArgumentParser(argparse.ArgumentParser):
    """Custom parser that prints examples on error."""
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: error: {message}\n{EXTRACT_PENDING_EXAMPLES}")


def find_pending_conversations(sql_db, project_name, limit=50):
    """
    Find conversations that need extraction.

    Uses SQL's processed flag (set by store_extraction.py after successful extraction).

    Returns list of pending interaction dicts.
    """
    print(f"\n[SEARCH] Finding pending conversations for project: {project_name}")

    # Get unprocessed interactions from SQL (processed=FALSE)
    pending_interactions = sql_db.get_unprocessed_interactions(project_name)

    if not pending_interactions:
        print(f"[INFO] No pending extractions for project: {project_name}")
        return []

    print(f"[INFO] Found {len(pending_interactions)} pending extractions")

    # Format output
    pending = []
    for interaction in pending_interactions:
        pending.append({
            'uuid': interaction['uuid'],
            'user_msg': interaction.get('user_message', ''),
            'assistant_msg': interaction.get('assistant_message', ''),
            'timestamp': interaction.get('timestamp', '')
        })

    # Apply limit
    if limit and len(pending) > limit:
        print(f"[INFO] Limiting to {limit} conversations")
        pending = pending[:limit]

    return pending


def main():
    parser = ExtractPendingArgumentParser(
        description="Extract knowledge from pending conversations",
        epilog=EXTRACT_PENDING_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--project", required=True, help="Project name")
    parser.add_argument("--limit", type=int, default=50, help="Max conversations to process (default: 50)")
    parser.add_argument("--all", action="store_true", help="Process all pending (no limit)")
    parser.add_argument("--uuid", help="Extract specific conversation by UUID")
    
    args = parser.parse_args()
    
    config = load_config(project_name=args.project)
    sql_db = SQLDatabase(config.get_sql_db_path())

    # Find pending conversations
    limit = None if args.all else args.limit

    if args.uuid:
        # Get specific conversation
        interaction = sql_db.get_interaction_by_uuid(args.uuid)
        if not interaction:
            print(f"\n[ERROR] Interaction not found: {args.uuid}")
            sys.exit(1)
        if interaction.get('processed'):
            print(f"\n[INFO] Interaction already processed: {args.uuid}")
            sys.exit(0)
        pending = [{
            'uuid': interaction['uuid'],
            'user_msg': interaction.get('user_message', ''),
            'assistant_msg': interaction.get('assistant_message', ''),
            'timestamp': interaction.get('timestamp', '')
        }]
    else:
        # Find all pending
        pending = find_pending_conversations(sql_db, args.project, limit)

    if not pending:
        print(f"\n[OK] No pending extractions!")
        sys.exit(0)

    # Output pending UUIDs for agent to use
    print(f"\n{'='*60}")
    print(f"PENDING EXTRACTIONS ({len(pending)})")
    print(f"{'='*60}")
    for conv in pending:
        user_preview = conv['user_msg'][:60].replace('\n', ' ')
        print(f"\nUUID: {conv['uuid']}")
        print(f"  Time: {conv['timestamp']}")
        print(f"  User: {user_preview}...")

    print(f"\n{'='*60}")
    print(f"Copy UUID(s) above into your extraction file's interaction_uuid field")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
