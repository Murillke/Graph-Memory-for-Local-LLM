#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Automatically review contradictions using LLM.

This script takes contradiction detection results and uses LLM to:
- Analyze each contradiction
- Decide which fact to invalidate (if any)
- Flag edge cases for human review
- Generate decisions file for automatic application

Usage:
    python scripts/auto_review_contradictions.py --input contradictions.json --output decisions.json
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


def create_review_prompt(contradiction: dict) -> str:
    """
    Create prompt for LLM to review a contradiction.
    """
    fact_a = contradiction['fact_a']
    fact_b = contradiction['fact_b']
    score = contradiction['score']
    scores = contradiction['scores']
    
    prompt = f"""You are reviewing a potential contradiction between two facts.

FACT A:
  Statement: {fact_a['fact']}
  Created: {fact_a['created_at']}
  UUID: {fact_a['uuid']}

FACT B:
  Statement: {fact_b['fact']}
  Created: {fact_b['created_at']}
  UUID: {fact_b['uuid']}

CONTRADICTION SCORE: {score:.2f}
  Semantic: {scores['semantic']:.2f}
  Temporal: {scores['temporal']:.2f}
  Keyword: {scores['keyword']:.2f}
  Clustering: {scores['clustering']:.2f}

TASK:
Analyze whether these facts truly contradict each other and decide what action to take.

Consider:
1. Do they actually contradict, or are they compatible?
2. Could both be true in different contexts?
3. Is one clearly more accurate/recent than the other?
4. Is this a temporal evolution (belief changed over time)?

RESPOND WITH JSON:
{{
  "is_contradiction": true/false,
  "confidence": 0.0-1.0,
  "action": "invalidate_a" | "invalidate_b" | "keep_both" | "needs_human",
  "reason": "Brief explanation of your decision",
  "edge_case": true/false,
  "edge_case_reason": "Why this needs human review (if edge_case=true)"
}}

GUIDELINES:
- confidence > 0.9: Auto-invalidate older fact
- confidence 0.7-0.9: Auto-invalidate with caution
- confidence < 0.7: Flag as edge case
- If both facts created same day: Flag as edge case
- If facts from different contexts: Flag as edge case
- If unsure: Flag as edge case

Your JSON response:"""
    
    return prompt


def review_contradiction_with_llm(contradiction: dict, config: dict) -> dict:
    """
    Use LLM to review a single contradiction.
    
    Returns decision dict.
    """
    # Create prompt
    prompt = create_review_prompt(contradiction)
    
    # TODO: Call LLM wrapper
    # For now, use heuristic-based decision
    
    score = contradiction['score']
    fact_a = contradiction['fact_a']
    fact_b = contradiction['fact_b']
    
    # Parse timestamps
    try:
        created_a = datetime.fromisoformat(fact_a['created_at'].replace('Z', '+00:00'))
        created_b = datetime.fromisoformat(fact_b['created_at'].replace('Z', '+00:00'))
        time_diff_days = abs((created_a - created_b).days)
    except:
        time_diff_days = 0
    
    # Decision logic
    decision = {
        'contradiction_index': contradiction.get('index', 0),
        'fact_a_uuid': fact_a['uuid'],
        'fact_b_uuid': fact_b['uuid'],
        'score': score
    }
    
    # High confidence contradiction
    if score >= 0.90:
        # Invalidate older fact
        if created_a < created_b:
            decision.update({
                'is_contradiction': True,
                'confidence': score,
                'action': 'invalidate_a',
                'invalidate_uuid': fact_a['uuid'],
                'superseded_by': fact_b['uuid'],
                'reason': f'High confidence contradiction (score: {score:.2f}), invalidating older fact',
                'edge_case': False
            })
        else:
            decision.update({
                'is_contradiction': True,
                'confidence': score,
                'action': 'invalidate_b',
                'invalidate_uuid': fact_b['uuid'],
                'superseded_by': fact_a['uuid'],
                'reason': f'High confidence contradiction (score: {score:.2f}), invalidating older fact',
                'edge_case': False
            })
    
    # Medium confidence
    elif score >= 0.70:
        # Check for edge cases
        if time_diff_days < 1:
            # Same day - edge case
            decision.update({
                'is_contradiction': True,
                'confidence': score,
                'action': 'needs_human',
                'reason': 'Medium confidence contradiction',
                'edge_case': True,
                'edge_case_reason': 'Both facts created on same day, unclear which is correct'
            })
        else:
            # Invalidate older
            if created_a < created_b:
                decision.update({
                    'is_contradiction': True,
                    'confidence': score,
                    'action': 'invalidate_a',
                    'invalidate_uuid': fact_a['uuid'],
                    'superseded_by': fact_b['uuid'],
                    'reason': f'Medium confidence contradiction (score: {score:.2f}), invalidating older fact',
                    'edge_case': False
                })
            else:
                decision.update({
                    'is_contradiction': True,
                    'confidence': score,
                    'action': 'invalidate_b',
                    'invalidate_uuid': fact_b['uuid'],
                    'superseded_by': fact_a['uuid'],
                    'reason': f'Medium confidence contradiction (score: {score:.2f}), invalidating older fact',
                    'edge_case': False
                })
    
    # Low confidence - edge case
    else:
        decision.update({
            'is_contradiction': False,
            'confidence': score,
            'action': 'needs_human',
            'reason': 'Low confidence, needs human review',
            'edge_case': True,
            'edge_case_reason': f'Low contradiction score ({score:.2f}), unclear if truly contradictory'
        })
    
    return decision


def main():
    parser = argparse.ArgumentParser(
        description='Automatically review contradictions using LLM'
    )
    parser.add_argument('--input', required=True, help='Input contradictions JSON file')
    parser.add_argument('--output', required=True, help='Output decisions JSON file')
    parser.add_argument('--min-score', type=float, default=0.60,
                       help='Minimum score to review (default: 0.60)')

    args = parser.parse_args()

    # Load config
    config_path = Path('mem.config.json')
    if not config_path.exists():
        print("[ERROR] mem.config.json not found!", file=sys.stderr)
        sys.exit(1)

    with open(config_path, 'r') as f:
        config = json.load(f)

    # Load contradictions
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[ERROR] Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    contradictions = data.get('contradictions', [])

    print("="*80)
    print("AUTOMATED CONTRADICTION REVIEW")
    print("="*80)
    print(f"\nInput: {args.input}")
    print(f"Contradictions to review: {len(contradictions)}")
    print(f"Minimum score: {args.min_score}")

    # Filter by score
    contradictions = [c for c in contradictions if c['score'] >= args.min_score]
    print(f"After filtering: {len(contradictions)}")

    # Add index to each
    for i, c in enumerate(contradictions):
        c['index'] = i

    # Review each contradiction
    print(f"\n[REVIEW] Analyzing contradictions...")
    decisions = []
    auto_count = 0
    edge_count = 0

    for i, contradiction in enumerate(contradictions, 1):
        print(f"  [{i}/{len(contradictions)}] Score: {contradiction['score']:.2f}", end=" ")

        decision = review_contradiction_with_llm(contradiction, config)
        decisions.append(decision)

        if decision['edge_case']:
            edge_count += 1
            print("→ EDGE CASE")
        else:
            auto_count += 1
            print(f"→ {decision['action'].upper()}")

    # Save decisions
    output_data = {
        'input_file': args.input,
        'timestamp': datetime.now().isoformat(),
        'total_reviewed': len(contradictions),
        'auto_processed': auto_count,
        'edge_cases': edge_count,
        'decisions': decisions
    }

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*80}")
    print("REVIEW SUMMARY")
    print(f"{'='*80}")
    print(f"Total reviewed:    {len(contradictions)}")
    print(f"Auto-processed:    {auto_count}")
    print(f"Edge cases:        {edge_count}")
    print(f"\nDecisions saved to: {args.output}")
    print(f"\nNext steps:")
    print(f"  1. Review edge cases: python scripts/show_edge_cases.py --input {args.output}")
    print(f"  2. Apply decisions: python scripts/apply_review_decisions.py --input {args.output}")
    print(f"{'='*80}")


if __name__ == '__main__':
    main()

