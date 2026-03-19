#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Detect contradictions in existing facts using multi-method weighted scoring.

This script finds contradicting facts in the graph using:
- Semantic contradiction (40%)
- Temporal analysis (30%)
- Keyword contradiction (20%)
- Graph clustering (10%)

Usage:
    python scripts/detect_contradictions.py --project llm_memory --threshold 0.60
    python scripts/detect_contradictions.py --project llm_memory --threshold 0.90 --auto-invalidate
    python scripts/detect_contradictions.py --project llm_memory --entity-file tmp/entity.txt --threshold 0.70
"""

import sys
import os
import json
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Set

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


def get_keyword_contradiction_score(fact_a: Dict, fact_b: Dict) -> float:
    """
    Check for opposite keywords in facts.
    
    Returns score 0.0-1.0
    """
    opposites = [
        ('good', 'bad'),
        ('fast', 'slow'),
        ('works', 'broken'),
        ('enables', 'prevents'),
        ('causes', 'solves'),
        ('true', 'false'),
        ('yes', 'no'),
        ('increase', 'decrease'),
        ('start', 'stop'),
        ('correct', 'incorrect'),
        ('valid', 'invalid'),
    ]
    
    fact_a_lower = fact_a['fact'].lower()
    fact_b_lower = fact_b['fact'].lower()
    
    for word_a, word_b in opposites:
        if (word_a in fact_a_lower and word_b in fact_b_lower) or \
           (word_b in fact_a_lower and word_a in fact_b_lower):
            return 0.8
    
    return 0.0


def get_temporal_contradiction_score(fact_a: Dict, fact_b: Dict) -> float:
    """
    Check if facts contradict in temporal context.
    
    Returns score 0.0-1.0
    """
    # Same entities involved?
    if not (fact_a.get('source_uuid') == fact_b.get('source_uuid') and 
            fact_a.get('target_uuid') == fact_b.get('target_uuid')):
        return 0.0
    
    # Parse timestamps
    try:
        created_a = datetime.fromisoformat(fact_a['created_at'].replace('Z', '+00:00'))
        created_b = datetime.fromisoformat(fact_b['created_at'].replace('Z', '+00:00'))
        time_diff = abs((created_a - created_b).days)
    except:
        return 0.0
    
    # Created close together → likely contradiction
    if time_diff < 7:
        return 0.8
    
    # Created far apart → likely evolution/change
    elif time_diff > 365:
        return 0.5  # Still flag, but lower confidence
    
    # Medium time gap
    else:
        return 0.6


def get_clustering_contradiction_score(
    fact_a: Dict,
    fact_b: Dict,
    graph_db: GraphDatabase
) -> float:
    """
    Score based on graph structure and neighborhood divergence.
    
    Returns score 0.0-1.0
    """
    score = 0.0
    
    # Same entities involved?
    if fact_a.get('source_uuid') == fact_b.get('source_uuid') and \
       fact_a.get('target_uuid') == fact_b.get('target_uuid'):
        score += 0.5
    
    # Opposite relationship types?
    opposite_pairs = [
        ('CAUSES', 'PREVENTS'),
        ('ENABLES', 'BLOCKS'),
        ('SOLVES', 'CREATES'),
        ('INCREASES', 'DECREASES'),
    ]
    
    rel_a = fact_a.get('name', '')
    rel_b = fact_b.get('name', '')
    
    for rel_type_a, rel_type_b in opposite_pairs:
        if (rel_a == rel_type_a and rel_b == rel_type_b) or \
           (rel_a == rel_type_b and rel_b == rel_type_a):
            score += 0.3
    
    # TODO: Implement neighborhood divergence
    # This requires getting all neighbors of source/target entities
    # and calculating divergence score
    
    return min(score, 1.0)


def get_semantic_contradiction_score(fact_a: Dict, fact_b: Dict) -> float:
    """
    Detect semantic contradiction.

    For now, uses simple heuristics. Could be enhanced with:
    - LLM-based detection
    - Embedding similarity + negation detection

    Returns score 0.0-1.0
    """
    fact_a_text = fact_a['fact'].lower()
    fact_b_text = fact_b['fact'].lower()

    # Remove common words for better overlap calculation
    stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being'}

    # Check for negation patterns
    has_negation = (
        ('not' in fact_a_text and 'not' not in fact_b_text) or
        ('not' in fact_b_text and 'not' not in fact_a_text) or
        ("n't" in fact_a_text and "n't" not in fact_b_text) or
        ("n't" in fact_b_text and "n't" not in fact_a_text) or
        ('does not' in fact_a_text and 'does not' not in fact_b_text) or
        ('does not' in fact_b_text and 'does not' not in fact_a_text)
    )

    if has_negation:
        # Check if they're about the same thing
        # Simple word overlap check (excluding stop words and negation words)
        words_a = set(fact_a_text.split()) - stop_words - {'not', "n't", 'does'}
        words_b = set(fact_b_text.split()) - stop_words - {'not', "n't", 'does'}

        if words_a and words_b:
            overlap = len(words_a & words_b) / max(len(words_a), len(words_b))

            if overlap > 0.4:
                return 0.7

    # TODO: Enhance with LLM or embeddings

    return 0.0


def calculate_contradiction_score(
    fact_a: Dict,
    fact_b: Dict,
    graph_db: GraphDatabase
) -> float:
    """
    Combine all methods with weights.

    Weights:
    - Semantic: 40%
    - Temporal: 30%
    - Keyword: 20%
    - Clustering: 10%

    Returns score 0.0-1.0
    """
    semantic_score = get_semantic_contradiction_score(fact_a, fact_b)
    temporal_score = get_temporal_contradiction_score(fact_a, fact_b)
    keyword_score = get_keyword_contradiction_score(fact_a, fact_b)
    clustering_score = get_clustering_contradiction_score(fact_a, fact_b, graph_db)

    final_score = (
        semantic_score * 0.40 +      # 40% semantic
        temporal_score * 0.30 +      # 30% temporal
        keyword_score * 0.20 +       # 20% keywords
        clustering_score * 0.10      # 10% graph clustering
    )

    return final_score


def get_all_facts(graph_db: GraphDatabase, project_name: str, entity_name: str = None) -> List[Dict]:
    """
    Get all facts from the graph, optionally filtered by entity.
    """
    if entity_name:
        # Get facts involving specific entity
        result = graph_db.conn.execute(f"""
            MATCH (source:Entity)-[r:RELATES_TO]->(target:Entity)
            WHERE r.invalid_at IS NULL
              AND (source.name = '{entity_name.replace("'", "''")}'
                   OR target.name = '{entity_name.replace("'", "''")}')
            RETURN r.uuid, r.name, r.fact, source.uuid, target.uuid,
                   r.created_at, r.valid_at, r.invalid_at
        """)
    else:
        # Get all facts
        result = graph_db.conn.execute(f"""
            MATCH (source:Entity)-[r:RELATES_TO]->(target:Entity)
            WHERE r.invalid_at IS NULL
            RETURN r.uuid, r.name, r.fact, source.uuid, target.uuid,
                   r.created_at, r.valid_at, r.invalid_at
        """)

    facts = []
    while result.has_next():
        row = result.get_next()
        facts.append({
            'uuid': row[0],
            'name': row[1],
            'fact': row[2],
            'source_uuid': row[3],
            'target_uuid': row[4],
            'created_at': str(row[5]),
            'valid_at': str(row[6]),
            'invalid_at': str(row[7]) if row[7] else None
        })

    return facts


def detect_contradictions(
    graph_db: GraphDatabase,
    project_name: str,
    entity_name: str = None,
    threshold: float = 0.60
) -> List[Dict]:
    """
    Detect contradictions in existing facts.

    Returns list of contradiction pairs with scores.
    """
    print(f"\n[SEARCH] Finding contradictions...")
    if entity_name:
        print(f"   Entity filter: {entity_name}")
    print(f"   Threshold: {threshold}")

    # Get all facts
    facts = get_all_facts(graph_db, project_name, entity_name)
    print(f"   Found {len(facts)} facts to analyze")

    contradictions = []
    total_comparisons = 0

    # Compare each pair
    for i, fact_a in enumerate(facts):
        for fact_b in facts[i+1:]:
            total_comparisons += 1

            # Calculate contradiction score
            score = calculate_contradiction_score(fact_a, fact_b, graph_db)

            if score >= threshold:
                contradictions.append({
                    'fact_a': fact_a,
                    'fact_b': fact_b,
                    'score': score,
                    'scores': {
                        'semantic': get_semantic_contradiction_score(fact_a, fact_b),
                        'temporal': get_temporal_contradiction_score(fact_a, fact_b),
                        'keyword': get_keyword_contradiction_score(fact_a, fact_b),
                        'clustering': get_clustering_contradiction_score(fact_a, fact_b, graph_db)
                    }
                })

    print(f"   Comparisons: {total_comparisons}")
    print(f"   Contradictions found: {len(contradictions)}")

    # Sort by score (highest first)
    contradictions.sort(key=lambda x: x['score'], reverse=True)

    return contradictions


def main():
    raw_argv = sys.argv[1:]
    parser = argparse.ArgumentParser(
        description='Detect contradictions in existing facts using multi-method scoring'
    )
    parser.add_argument('--project', required=True, help='Project name')
    parser.add_argument('--entity', help='Deprecated direct entity name (use --entity-file)')
    parser.add_argument('--entity-file', help='File containing entity name (workflow standard)')
    parser.add_argument('--threshold', type=float, default=0.60,
                       help='Minimum contradiction score (0.0-1.0, default: 0.60)')
    parser.add_argument('--auto-invalidate', type=float,
                       help='Auto-invalidate contradictions above this score (e.g., 0.90)')
    parser.add_argument('--output', help='Output JSON file (optional)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without making changes')

    args = parser.parse_args()

    if args.entity_file:
        with open(args.entity_file, 'r', encoding='utf-8') as f:
            args.entity = f.read().strip()
        if not args.entity:
            parser.error(f"Entity helper file is empty: {args.entity_file}")
    elif '--entity' in raw_argv:
        if os.getenv("MEM_ALLOW_DIRECT_INPUT") != "1":
            parser.error("Direct --entity is disabled by default. Use --entity-file tmp/entity.txt. Set MEM_ALLOW_DIRECT_INPUT=1 only for legacy/manual compatibility.")
        print("[WARNING] --entity is allowed only because MEM_ALLOW_DIRECT_INPUT=1 is set. Prefer --entity-file tmp/entity.txt.", file=sys.stderr)

    config = load_config(project_name=args.project)
    graph_db = GraphDatabase(config.get_graph_db_path(args.project))

    print("="*80)
    print("CONTRADICTION DETECTION")
    print("="*80)

    # Detect contradictions
    contradictions = detect_contradictions(
        graph_db,
        args.project,
        args.entity,
        args.threshold
    )

    if not contradictions:
        print("\n[OK] No contradictions found above threshold!")
        return

    # Display results
    print(f"\n{'='*80}")
    print(f"RESULTS: {len(contradictions)} contradictions found")
    print(f"{'='*80}\n")

    for i, contra in enumerate(contradictions, 1):
        print(f"[{i}] Score: {contra['score']:.2f}")
        print(f"    Fact A: {contra['fact_a']['fact']}")
        print(f"      Created: {contra['fact_a']['created_at']}")
        print(f"      UUID: {contra['fact_a']['uuid']}")
        print(f"    Fact B: {contra['fact_b']['fact']}")
        print(f"      Created: {contra['fact_b']['created_at']}")
        print(f"      UUID: {contra['fact_b']['uuid']}")
        print(f"    Breakdown:")
        print(f"      Semantic: {contra['scores']['semantic']:.2f} (40%)")
        print(f"      Temporal: {contra['scores']['temporal']:.2f} (30%)")
        print(f"      Keyword:  {contra['scores']['keyword']:.2f} (20%)")
        print(f"      Clustering: {contra['scores']['clustering']:.2f} (10%)")
        print()

    # Auto-invalidate if requested
    if args.auto_invalidate:
        high_confidence = [c for c in contradictions if c['score'] >= args.auto_invalidate]

        if high_confidence:
            print(f"\n[AUTO] {len(high_confidence)} contradictions above {args.auto_invalidate} threshold")

            for contra in high_confidence:
                # Invalidate older fact
                fact_a_time = datetime.fromisoformat(contra['fact_a']['created_at'].replace('Z', '+00:00'))
                fact_b_time = datetime.fromisoformat(contra['fact_b']['created_at'].replace('Z', '+00:00'))

                if fact_a_time < fact_b_time:
                    older = contra['fact_a']
                    newer = contra['fact_b']
                else:
                    older = contra['fact_b']
                    newer = contra['fact_a']

                if args.dry_run:
                    print(f"[DRY RUN] Would invalidate: {older['fact']}")
                    print(f"          Superseded by: {newer['fact']}")
                else:
                    invalidate_facts(
                        graph_db,
                        [older['uuid']],
                        datetime.now().isoformat(),
                        superseded_by=newer['uuid']
                    )
                    print(f"[OK] Invalidated: {older['fact']}")
                    print(f"     Superseded by: {newer['fact']}")

    # Save to file if requested
    if args.output:
        output_data = {
            'project': args.project,
            'entity_filter': args.entity,
            'threshold': args.threshold,
            'timestamp': datetime.now().isoformat(),
            'contradictions': contradictions
        }

        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        print(f"\n[OK] Results saved to: {args.output}")

    print(f"\n{'='*80}")
    print("CONTRADICTION DETECTION COMPLETE")
    print(f"{'='*80}")


if __name__ == '__main__':
    main()
