#!/usr/bin/env python3
"""
Export conversation history from the memory system.

Usage:
    # Export all interactions for a project
    python3 scripts/export_history.py --project "my-project"
    
    # Export as JSON
    python3 scripts/export_history.py --project "my-project" --json
    
    # Export to file
    python3 scripts/export_history.py --project "my-project" --output history.txt
    
    # Export with hash chain verification
    python3 scripts/export_history.py --project "my-project" --verify
    
    # Export only recent interactions
    python3 scripts/export_history.py --project "my-project" --limit 10

Output:
    Prints conversation history in human-readable format or JSON.
    Optionally verifies hash chain integrity.
"""

import sys
import os
import argparse
import json
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tools.sql_db import SQLDatabase

from tools.console_utils import safe_print, setup_console_encoding

# Setup console encoding for Windows
setup_console_encoding()


EXPORT_EXAMPLES = """
Examples:
  # Export last 10 interactions
  python scripts/export_history.py --project llm_memory --limit 10

  # Export all to file
  python scripts/export_history.py --project llm_memory --output history.txt

  # Export as JSON
  python scripts/export_history.py --project llm_memory --json

  # Verify hash chain before export
  python scripts/export_history.py --project llm_memory --verify
"""


class ExportArgumentParser(argparse.ArgumentParser):
    """Custom parser that prints examples on error."""
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: error: {message}\n{EXPORT_EXAMPLES}")


def format_interaction(interaction, index=None, show_hash=False):
    """Format interaction in human-readable format."""
    lines = []
    
    if index is not None:
        lines.append(f"\n{'='*60}")
        lines.append(f"Interaction #{index} (Chain Index: {interaction['chain_index']})")
        lines.append(f"{'='*60}")
    else:
        lines.append(f"\n{'='*60}")
    
    lines.append(f"UUID:      {interaction['uuid']}")
    lines.append(f"Timestamp: {interaction['timestamp']}")
    
    if show_hash:
        lines.append(f"Hash:      {interaction['content_hash'][:32]}...")
        if interaction['previous_hash']:
            lines.append(f"Previous:  {interaction['previous_hash'][:32]}...")
    
    lines.append(f"\n User:")
    lines.append(f"   {interaction['user_message']}")
    
    lines.append(f"\n[AI] Assistant:")
    lines.append(f"   {interaction['assistant_message']}")
    
    return '\n'.join(lines)


def main():
    parser = ExportArgumentParser(
        description='Export conversation history from the memory system',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EXPORT_EXAMPLES,
    )
    
    # Database
    parser.add_argument('--db', default='./memory/conversations.db',
                       help='Path to SQLite database (default: ./memory/conversations.db)')
    
    # Query
    parser.add_argument('--project', required=True, help='Project name')
    parser.add_argument('--limit', type=int, help='Limit number of interactions')
    parser.add_argument('--offset', type=int, default=0, help='Skip first N interactions')
    
    # Options
    parser.add_argument('--verify', action='store_true',
                       help='Verify hash chain before exporting')
    parser.add_argument('--show-hash', action='store_true',
                       help='Show content hashes in output')
    parser.add_argument('--json', action='store_true',
                       help='Output as JSON')
    parser.add_argument('--output', '-o', help='Write to file instead of stdout')
    
    args = parser.parse_args()
    
    # Connect to database
    db = SQLDatabase(args.db)
    
    # Verify project exists
    project = db.get_project_by_name(args.project)
    if not project:
        safe_print(f"Error: Project '{args.project}' not found", file=sys.stderr)
        sys.exit(1)
    
    # Verify hash chain if requested
    if args.verify:
        safe_print(f"[SEARCH] Verifying hash chain...", file=sys.stderr)
        result = db.verify_interaction_chain(args.project)
        if result['verified']:
            safe_print(f"[OK] Hash chain verified ({result['total_interactions']} interactions)", 
                  file=sys.stderr)
        else:
            safe_print(f"[ERROR] Hash chain verification FAILED!", file=sys.stderr)
            for error in result['errors']:
                safe_print(f"   {error}", file=sys.stderr)
            sys.exit(1)
    
    # Get interactions
    interactions = db.get_all_interactions(args.project)
    
    if not interactions:
        safe_print(f"No interactions found for project '{args.project}'", file=sys.stderr)
        sys.exit(0)
    
    # Apply offset and limit
    if args.offset:
        interactions = interactions[args.offset:]
    if args.limit:
        interactions = interactions[:args.limit]
    
    # Format output
    if args.json:
        output = json.dumps(interactions)
    else:
        lines = []
        lines.append(f"\n{'#'*60}")
        lines.append(f"# Conversation History: {args.project}")
        lines.append(f"# Total Interactions: {len(interactions)}")
        lines.append(f"# Exported: {datetime.now().isoformat()}")
        lines.append(f"{'#'*60}")
        
        for i, interaction in enumerate(interactions, 1):
            lines.append(format_interaction(
                interaction,
                index=i,
                show_hash=args.show_hash
            ))
        
        lines.append(f"\n{'#'*60}")
        lines.append(f"# End of History")
        lines.append(f"{'#'*60}\n")
        
        output = '\n'.join(lines)
    
    # Write output
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        safe_print(f"[OK] Exported {len(interactions)} interactions to {args.output}", 
              file=sys.stderr)
    else:
        safe_print(output)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        safe_print("\n\nInterrupted by user", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        safe_print(f"\n[ERROR] Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

