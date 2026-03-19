#!/usr/bin/env python3
"""
Get Latest Interaction UUID

Returns the UUID of the most recent UNPROCESSED interaction (default).
Useful when creating extraction.json files manually.

Usage:
    # Get latest unprocessed interaction (default)
    python scripts/get_latest_uuid.py --project llm_memory

    # Get Nth most recent unprocessed interaction
    python scripts/get_latest_uuid.py --project llm_memory --offset 1

    # Include processed interactions (legacy behavior)
    python scripts/get_latest_uuid.py --project llm_memory --all

Note:
    Default behavior returns unprocessed interactions only.
    If store_extraction.py has already processed an interaction,
    it will NOT appear in the default output.

    Use --all to restore legacy behavior (all interactions).
"""

import sys
import argparse

import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from tools.sql_db import SQLDatabase
from tools.config import load_config


def main():
    parser = argparse.ArgumentParser(
        description='Get latest interaction UUID (unprocessed only by default)',
        epilog='TIP: For sync workflow, prefer using the UUID from import_summary.py output directly.'
    )
    parser.add_argument('--project', required=True, help='Project name')
    parser.add_argument('--offset', type=int, default=0,
                        help='Offset from latest (0=latest, 1=second latest, etc.). Applies within selected set.')
    parser.add_argument('--show-content', action='store_true', help='Show interaction content preview')
    parser.add_argument('--all', action='store_true',
                        help='Include processed interactions (legacy behavior). '
                             'Default: only unprocessed interactions.')

    args = parser.parse_args()

    config = load_config(project_name=args.project)

    # Connect to database
    db = SQLDatabase(config.get_sql_db_path())

    # Get interactions based on mode
    if args.all:
        interactions = db.get_all_interactions(args.project)
        mode = "all"
    else:
        interactions = db.get_unprocessed_interactions(args.project)
        mode = "unprocessed"

    if not interactions:
        if args.all:
            print(f"No interactions found for project: {args.project}", file=sys.stderr)
        else:
            print(f"No unprocessed interactions found for project: {args.project}", file=sys.stderr)
            print(f"TIP: Use --all to include already-processed interactions.", file=sys.stderr)
            print(f"TIP: Or use the UUID from import_summary.py output directly.", file=sys.stderr)
        sys.exit(1)

    # Get the requested interaction (offset applies within selected set)
    if args.offset >= len(interactions):
        print(f"Offset {args.offset} is too large. Only {len(interactions)} {mode} interactions available.", file=sys.stderr)
        sys.exit(1)

    interaction = interactions[-(args.offset + 1)]

    # Output
    if args.show_content:
        print(f"UUID: {interaction['uuid']}")
        print(f"Processed: {interaction.get('processed', False)}")
        user_msg = interaction.get('user_message', '')
        assistant_msg = interaction.get('assistant_message', '')

        if user_msg:
            print(f"User: {user_msg[:80]}...")
        if assistant_msg:
            print(f"Assistant: {assistant_msg[:80]}...")
    else:
        print(interaction['uuid'])


if __name__ == "__main__":
    main()
