#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apply automated review decisions.

This script takes decisions from auto_review_contradictions.py and applies them:
- Invalidates facts as decided
- Sets superseded_by relationships
- Skips edge cases (for human review)
- Logs all actions

Usage:
    python scripts/apply_review_decisions.py --input decisions.json
    python scripts/apply_review_decisions.py --input decisions.json --dry-run
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# Fix Windows encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.graph_db import GraphDatabase
from tools.config import load_config
from tools.contradiction import invalidate_facts


def main():
    parser = argparse.ArgumentParser(
        description='Apply automated review decisions'
    )
    parser.add_argument('--input', required=True, help='Input decisions JSON file')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without making changes')
    parser.add_argument('--skip-edge-cases', action='store_true', default=True,
                       help='Skip edge cases (default: true)')
    
    args = parser.parse_args()
    
    config = load_config()
    graph_db = GraphDatabase(config.get_graph_db_path())
    
    # Load decisions
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[ERROR] Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)
    
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    decisions = data.get('decisions', [])
    
    print("="*80)
    print("APPLYING REVIEW DECISIONS")
    print("="*80)
    print(f"\nInput: {args.input}")
    print(f"Total decisions: {len(decisions)}")
    print(f"Dry run: {args.dry_run}")
    print(f"Skip edge cases: {args.skip_edge_cases}")
    
    # Filter decisions
    if args.skip_edge_cases:
        to_apply = [d for d in decisions if not d.get('edge_case', False)]
        skipped = [d for d in decisions if d.get('edge_case', False)]
        print(f"\nDecisions to apply: {len(to_apply)}")
        print(f"Edge cases skipped: {len(skipped)}")
    else:
        to_apply = decisions
        skipped = []
    
    # Apply decisions
    print(f"\n[APPLY] Processing decisions...")
    applied_count = 0
    error_count = 0
    
    for i, decision in enumerate(to_apply, 1):
        action = decision.get('action')
        
        if action in ['invalidate_a', 'invalidate_b']:
            invalidate_uuid = decision.get('invalidate_uuid')
            superseded_by = decision.get('superseded_by')
            reason = decision.get('reason', 'No reason provided')
            
            print(f"\n[{i}/{len(to_apply)}] {action.upper()}")
            print(f"  Invalidating: {invalidate_uuid}")
            print(f"  Superseded by: {superseded_by}")
            print(f"  Reason: {reason}")
            
            if args.dry_run:
                print(f"  [DRY RUN] Would invalidate fact")
                applied_count += 1
            else:
                try:
                    invalidate_facts(
                        graph_db,
                        [invalidate_uuid],
                        datetime.now().isoformat(),
                        superseded_by=superseded_by
                    )
                    print(f"  ✅ Applied")
                    applied_count += 1
                except Exception as e:
                    print(f"  ❌ Error: {e}")
                    error_count += 1
        
        elif action == 'keep_both':
            print(f"\n[{i}/{len(to_apply)}] KEEP_BOTH")
            print(f"  Reason: {decision.get('reason', 'No reason')}")
            print(f"  ✅ No action needed")
            applied_count += 1
        
        elif action == 'needs_human':
            print(f"\n[{i}/{len(to_apply)}] NEEDS_HUMAN")
            print(f"  Reason: {decision.get('reason', 'No reason')}")
            print(f"  ⚠️  Skipped (edge case)")
    
    # Summary
    print(f"\n{'='*80}")
    print("APPLICATION SUMMARY")
    print(f"{'='*80}")
    print(f"Decisions applied:  {applied_count}")
    print(f"Errors:             {error_count}")
    print(f"Edge cases skipped: {len(skipped)}")
    
    if skipped:
        print(f"\nEdge cases need human review:")
        print(f"  Run: python scripts/show_edge_cases.py --input {args.input}")
    
    print(f"{'='*80}")


if __name__ == '__main__':
    main()
