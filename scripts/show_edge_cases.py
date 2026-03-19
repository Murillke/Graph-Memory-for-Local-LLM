#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Show edge cases that need human review.

This script displays contradictions/duplicates that the automated review
flagged as needing human judgment.

Usage:
    python scripts/show_edge_cases.py --input decisions.json
"""

import sys
import json
import argparse
from pathlib import Path

# Fix Windows encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')


def main():
    parser = argparse.ArgumentParser(
        description='Show edge cases that need human review'
    )
    parser.add_argument('--input', required=True, help='Input decisions JSON file')
    
    args = parser.parse_args()
    
    # Load decisions
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[ERROR] Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)
    
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    decisions = data.get('decisions', [])
    edge_cases = [d for d in decisions if d.get('edge_case', False)]
    
    print("="*80)
    print("EDGE CASES NEEDING HUMAN REVIEW")
    print("="*80)
    print(f"\nInput: {args.input}")
    print(f"Total decisions: {len(decisions)}")
    print(f"Edge cases: {len(edge_cases)}")
    
    if not edge_cases:
        print("\n✅ No edge cases! All contradictions were auto-processed.")
        return
    
    print(f"\n{'='*80}")
    print("EDGE CASES")
    print(f"{'='*80}\n")
    
    for i, decision in enumerate(edge_cases, 1):
        print(f"[{i}] Edge Case")
        print(f"    Score: {decision.get('score', 0):.2f}")
        print(f"    Confidence: {decision.get('confidence', 0):.2f}")
        print(f"    Reason: {decision.get('edge_case_reason', 'No reason provided')}")
        print(f"    Fact A UUID: {decision.get('fact_a_uuid')}")
        print(f"    Fact B UUID: {decision.get('fact_b_uuid')}")
        print()
    
    print(f"{'='*80}")
    print("NEXT STEPS")
    print(f"{'='*80}")
    print("\nTo handle these edge cases:")
    print("1. Review each case manually")
    print("2. Use detect_contradictions.py to see full details:")
    print(f"   python scripts/detect_contradictions.py --project llm_memory --threshold 0.60")
    print("3. Manually invalidate facts if needed:")
    print("   (Use graph database tools or custom script)")
    print(f"{'='*80}")


if __name__ == '__main__':
    main()

