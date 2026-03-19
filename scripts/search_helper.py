#!/usr/bin/env python3
"""
Helper script for AI to search with multi-word terms.

Usage:
    1. Write search term to tmp/search_term.txt
    2. Run this script with project name

Example:
    # Edit tmp/search_term.txt with your query
    python scripts/search_helper.py --project llm_memory
"""
import sys
import subprocess
import argparse
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Search helper for multi-word terms")
    parser.add_argument('--project', required=True, help='Project name')
    parser.add_argument('--search-file', default='tmp/search_term.txt', help='File containing search term')
    parser.add_argument('--entity', action='store_true', help='Search by entity name instead of text search')
    parser.add_argument('--related', action='store_true', help='Get related entities')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    # Read search term from file
    search_file = Path(args.search_file)
    if not search_file.exists():
        # Create tmp directory if it doesn't exist
        search_file.parent.mkdir(parents=True, exist_ok=True)

        # Create file with helpful placeholder
        with open(search_file, 'w', encoding='utf-8') as f:
            f.write("your search term here")

        print(f"[INFO] Created search file: {args.search_file}", file=sys.stderr)
        print(f"[INFO] Edit the file with your search term, then run again:", file=sys.stderr)
        print(f"       Write your term to {args.search_file} with a UTF-8-safe file tool", file=sys.stderr)
        print(f"       python scripts/search_helper.py --project {args.project}", file=sys.stderr)
        sys.exit(1)

    with open(search_file, 'r', encoding='utf-8') as f:
        search_term = f.read().strip()

    if not search_term or search_term == "your search term here":
        print(f"[ERROR] Search file contains placeholder text: {args.search_file}", file=sys.stderr)
        print(f"[INFO] Edit the file with your actual search term:", file=sys.stderr)
        print(f"       Write your term to {args.search_file} with a UTF-8-safe file tool", file=sys.stderr)
        sys.exit(1)
    
    # Build command
    cmd = [
        sys.executable,
        'scripts/query_memory.py',
        '--project', args.project
    ]
    
    if args.entity:
        cmd.extend(['--entity-file', str(search_file)])
    else:
        cmd.extend(['--search-file', str(search_file)])
    
    if args.related:
        cmd.append('--related')
    
    if args.json:
        cmd.append('--json')
    
    if args.verbose:
        cmd.append('--verbose')
    
    # Run command
    result = subprocess.run(cmd, capture_output=False)
    sys.exit(result.returncode)


if __name__ == '__main__':
    main()
