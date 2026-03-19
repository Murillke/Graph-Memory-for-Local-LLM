#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Consolidate Knowledge - Find Higher-Order Patterns in the Graph

Unlike Google's expensive LLM consolidation, this uses graph traversal
to find patterns, hubs, neighborhoods, and transitive relationships.
"""

import sys
import os
import argparse
import json
import hashlib
import uuid as uuid_lib
from pathlib import Path
from datetime import datetime, timedelta

# Fix Windows encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tools.graph_db import GraphDatabase
from tools.sql_db import SQLDatabase
from tools.console_utils import safe_print
from tools.config import load_config


CONSOLIDATE_EXAMPLES = """
Examples:
  # Basic consolidation (find hubs, neighborhoods, patterns)
  python scripts/consolidate_knowledge.py --project llm_memory

  # Find smaller hubs (3+ relationships)
  python scripts/consolidate_knowledge.py --project llm_memory --min-hub-size 3

  # Find transitive relationships (slower)
  python scripts/consolidate_knowledge.py --project llm_memory --find-transitive

  # Store insights with hash chain
  python scripts/consolidate_knowledge.py --project llm_memory --store

  # Cleanup old detections
  python scripts/consolidate_knowledge.py --project llm_memory --cleanup
"""


class ConsolidateArgumentParser(argparse.ArgumentParser):
    """Custom parser that prints examples on error."""
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: error: {message}\n{CONSOLIDATE_EXAMPLES}")


def calculate_facts_hash(facts):
    """Calculate combined hash of all facts (compact verification)."""
    if not facts:
        return hashlib.sha256(b'').hexdigest()

    # Hash each fact
    fact_hashes = [
        hashlib.sha256(json.dumps(fact, sort_keys=True).encode()).hexdigest()
        for fact in facts
    ]

    # Sort for deterministic order
    fact_hashes.sort()

    # Combine and hash
    combined = ''.join(fact_hashes)
    combined_hash = hashlib.sha256(combined.encode()).hexdigest()

    return combined_hash


def get_entity_with_facts(graph_db: GraphDatabase, entity_name: str, project_name: str):
    """Get entity and all its SEMANTIC facts for hash calculation.

    Note: Excludes consolidation-generated relationships (HUB_ENTITY, CLUSTER_MEMBER)
    to prevent self-contamination on repeated runs.
    """
    # Get entity
    query = """
        MATCH (p:Project {name: $project_name})-[:HAS_ENTITY]->(e:Entity {name: $entity_name})
        RETURN e.uuid, e.name, e.summary, e.labels
    """
    result = graph_db.conn.execute(query, {"project_name": project_name, "entity_name": entity_name})

    if not result.has_next():
        return None, []

    row = result.get_next()
    entity = {
        'uuid': row[0],
        'name': row[1],
        'summary': row[2],
        'labels': row[3]
    }

    # Get all SEMANTIC facts (excludes consolidation markers)
    query = """
        MATCH (e:Entity {uuid: $entity_uuid})-[r:RELATES_TO]->(t)
        WHERE r.name <> 'HUB_ENTITY'
          AND r.name <> 'CLUSTER_MEMBER'
          AND r.name <> 'TRANSITIVE_INFERENCE'
        RETURN r.uuid, r.name, r.fact, t.uuid
    """
    result = graph_db.conn.execute(query, {"entity_uuid": entity['uuid']})

    facts = []
    while result.has_next():
        row = result.get_next()
        facts.append({
            'uuid': row[0],
            'type': row[1],
            'fact': row[2],
            'target_uuid': row[3]
        })

    return entity, facts


def find_hubs(graph_db: GraphDatabase, project_name: str, min_size: int = 5):
    """Find entities with many relationships (hub entities).

    Note: Excludes consolidation-generated relationships (HUB_ENTITY, CLUSTER_MEMBER)
    to prevent self-contamination on repeated runs.
    """
    safe_print(f"\n[HUBS] Finding entities with {min_size}+ relationships...")

    # Count RELATES_TO relationships (both incoming AND outgoing), excluding consolidation markers
    # Hub = central concept = many connections in EITHER direction
    # CRITICAL: Both source and target of edges must be in the same project
    # This prevents self-contamination on repeated runs and cross-project leakage
    query = """
        MATCH (p:Project {name: $project_name})-[:HAS_ENTITY]->(e:Entity)
        OPTIONAL MATCH (p)-[:HAS_ENTITY]->(t_out:Entity)
        OPTIONAL MATCH (e)-[r_out:RELATES_TO]->(t_out)
        WHERE r_out.name <> 'HUB_ENTITY'
          AND r_out.name <> 'CLUSTER_MEMBER'
          AND r_out.name <> 'TRANSITIVE_INFERENCE'
        OPTIONAL MATCH (p)-[:HAS_ENTITY]->(s_in:Entity)
        OPTIONAL MATCH (s_in)-[r_in:RELATES_TO]->(e)
        WHERE r_in.name <> 'HUB_ENTITY'
          AND r_in.name <> 'CLUSTER_MEMBER'
          AND r_in.name <> 'TRANSITIVE_INFERENCE'
        WITH e, count(DISTINCT r_out) + count(DISTINCT r_in) as rel_count
        WHERE rel_count >= $min_size
        RETURN e.uuid as uuid, e.name as name, e.summary as summary, rel_count as count
        ORDER BY rel_count DESC
    """

    result = graph_db.conn.execute(query, {"project_name": project_name, "min_size": min_size})
    hubs = []

    while result.has_next():
        row = result.get_next()
        hubs.append({
            'uuid': row[0],
            'name': row[1],
            'summary': row[2],
            'count': row[3]
        })
    
    if hubs:
        safe_print(f"\n✅ Found {len(hubs)} hub entities:\n")
        for i, hub in enumerate(hubs, 1):
            safe_print(f"{i}. {hub['name']} ({hub['count']} relationships)")
            if hub['summary']:
                safe_print(f"   {hub['summary'][:80]}...")
    else:
        safe_print(f"\n⚠️  No hubs found with {min_size}+ relationships")
    
    return hubs


def find_transitive_relationships(graph_db: GraphDatabase, project_name: str, rel_type: str = 'ENABLES'):
    """Find A→B→C where A→C doesn't exist (transitive relationships).

    Note: This graph stores all facts as RELATES_TO with the semantic type in r.name.
    """
    safe_print(f"\n[TRANSITIVE] Finding {rel_type} chains...")

    # Use RELATES_TO (the actual edge type) and filter by r.name (the semantic type)
    # CRITICAL: All entities (a, b, c) must be in the same project
    query = f"""
        MATCH (p:Project {{name: $project_name}})-[:HAS_ENTITY]->(a:Entity)
        MATCH (p)-[:HAS_ENTITY]->(b:Entity)
        MATCH (p)-[:HAS_ENTITY]->(c:Entity)
        MATCH (a)-[r1:RELATES_TO]->(b)
        WHERE r1.name = $rel_type
        MATCH (b)-[r2:RELATES_TO]->(c)
        WHERE r2.name = $rel_type
        AND NOT EXISTS {{
            MATCH (a)-[r3:RELATES_TO]->(c)
            WHERE r3.name = $rel_type
        }}
        RETURN a.name AS a_name, b.name AS b_name, c.name AS c_name, r1.fact AS r1_fact, r2.fact AS r2_fact
        LIMIT 20
    """

    result = graph_db.conn.execute(query, {"project_name": project_name, "rel_type": rel_type})
    transitive = []
    
    while result.has_next():
        row = result.get_next()
        transitive.append({
            'a': row[0],
            'b': row[1],
            'c': row[2],
            'fact1': row[3],
            'fact2': row[4]
        })
    
    if transitive:
        safe_print(f"\n✅ Found {len(transitive)} transitive {rel_type} chains:\n")
        for i, trans in enumerate(transitive[:10], 1):
            safe_print(f"{i}. {trans['a']} → {trans['b']} → {trans['c']}")
            safe_print(f"   Implies: {trans['a']} transitively {rel_type} {trans['c']}")
    else:
        safe_print(f"\n⚠️  No transitive {rel_type} chains found")
    
    return transitive


def find_neighborhoods(graph_db: GraphDatabase, project_name: str, min_size: int = 5):
    """Find connected entity neighborhoods (ego networks).

    Note: Excludes Consolidation System entity and consolidation-generated
    relationships to prevent contamination.
    """
    safe_print(f"\n[NEIGHBORHOODS] Finding entity neighborhoods with {min_size}+ members...")

    # Exclude Consolidation System and consolidation relationship types
    # CRITICAL: Connected entities must also be in the same project
    query = """
        MATCH (p:Project {name: $project_name})-[:HAS_ENTITY]->(e:Entity)
        WHERE e.name <> 'Consolidation System'
        MATCH (p)-[:HAS_ENTITY]->(connected:Entity)
        MATCH (e)-[r:RELATES_TO]-(connected)
        WHERE r.name <> 'HUB_ENTITY'
          AND r.name <> 'CLUSTER_MEMBER'
          AND r.name <> 'TRANSITIVE_INFERENCE'
          AND connected.name <> 'Consolidation System'
        WITH e, collect(DISTINCT connected.name) as members
        WHERE size(members) >= $min_size
        RETURN e.name as center, e.summary as summary, members, size(members) as size
        ORDER BY size DESC
        LIMIT 10
    """

    result = graph_db.conn.execute(query, {"project_name": project_name, "min_size": min_size})
    clusters = []
    
    while result.has_next():
        row = result.get_next()
        clusters.append({
            'center': row[0],
            'summary': row[1],
            'members': row[2],
            'size': row[3]
        })
    
    if clusters:
        safe_print(f"\n[OK] Found {len(clusters)} neighborhoods:\n")
        for i, cluster in enumerate(clusters, 1):
            safe_print(f"{i}. {cluster['center']} ({cluster['size']} connected entities)")
            if cluster['summary']:
                safe_print(f"   {cluster['summary'][:80]}...")
            safe_print(f"   Connected to: {', '.join(cluster['members'][:5])}")
            if len(cluster['members']) > 5:
                safe_print(f"   ... and {len(cluster['members']) - 5} more")
    else:
        safe_print(f"\n[INFO] No neighborhoods found with {min_size}+ members")
    
    return clusters


def find_relationship_patterns(graph_db: GraphDatabase, project_name: str):
    """Find common SEMANTIC relationship patterns.

    Excludes consolidation-generated relationships (HUB_ENTITY, etc.)
    to keep the pattern report meaningful.
    """
    safe_print(f"\n[PATTERNS] Finding common relationship patterns...")

    # Exclude consolidation relationship types
    # CRITICAL: Both source and target must be in the same project
    query = """
        MATCH (p:Project {name: $project_name})-[:HAS_ENTITY]->(e:Entity)
        MATCH (p)-[:HAS_ENTITY]->(t:Entity)
        MATCH (e)-[r:RELATES_TO]->(t)
        WHERE r.name <> 'HUB_ENTITY'
          AND r.name <> 'CLUSTER_MEMBER'
          AND r.name <> 'TRANSITIVE_INFERENCE'
        WITH r.name as rel_type, count(*) as usage_count
        WHERE usage_count >= 3
        RETURN rel_type, usage_count
        ORDER BY usage_count DESC
        LIMIT 10
    """

    result = graph_db.conn.execute(query, {"project_name": project_name})
    patterns = []

    while result.has_next():
        row = result.get_next()
        patterns.append({
            'type': row[0],
            'count': row[1]
        })

    if patterns:
        safe_print(f"\n✅ Found {len(patterns)} common relationship patterns:\n")
        for i, pattern in enumerate(patterns, 1):
            safe_print(f"{i}. {pattern['type']}: used {pattern['count']} times")
    else:
        safe_print(f"\n⚠️  No common patterns found")

    return patterns


def get_last_hub_detection(graph_db: GraphDatabase, project_name: str):
    """Get the last hub detection for chain linking, scoped to project."""
    try:
        # HUB_ENTITY is stored as RELATES_TO with r.name = 'HUB_ENTITY'
        # CRITICAL: Must be project-scoped to avoid cross-project chain contamination
        query = """
            MATCH (p:Project {name: $project_name})-[:HAS_ENTITY]->(e:Entity)-[r:RELATES_TO]->(c:Entity {name: 'Consolidation System'})
            WHERE r.name = 'HUB_ENTITY'
            RETURN r.attributes
            ORDER BY r.valid_at DESC
            LIMIT 1
        """

        result = graph_db.conn.execute(query, {"project_name": project_name})
        if result.has_next():
            row = result.get_next()
            attributes = json.loads(row[0])
            return {
                'chain_index': attributes.get('hub_chain_index', 0),
                'hash': attributes.get('current_hub_hash')
            }
    except Exception:
        # HUB_ENTITY relationships don't exist yet
        pass

    return None


def ensure_consolidation_entity(graph_db: GraphDatabase, project_name: str):
    """Ensure a Consolidation entity exists for storing hub markers."""
    # Check if it exists
    result = graph_db.conn.execute(f"""
        MATCH (p:Project {{name: '{project_name}'}})-[:HAS_ENTITY]->(c:Entity {{name: 'Consolidation System'}})
        RETURN c.uuid
    """)

    if result.has_next():
        return result.get_next()[0]

    # Create it
    consolidation_uuid = str(uuid_lib.uuid4())
    graph_db.conn.execute(f"""
        MATCH (p:Project {{name: '{project_name}'}})
        CREATE (p)-[:HAS_ENTITY]->(c:Entity {{
            uuid: '{consolidation_uuid}',
            name: 'Consolidation System',
            summary: 'Virtual entity for storing consolidation insights (hubs, clusters, patterns)',
            labels: ['System'],
            extraction_timestamp_str: '{datetime.now().isoformat()}',
            timestamp_proof: NULL
        }})
    """)

    return consolidation_uuid


def invalidate_existing_hub_detection(graph_db: GraphDatabase, entity_uuid: str, invalid_at: str):
    """Mark existing active hub detection for entity as superseded."""
    # HUB_ENTITY is stored as RELATES_TO with r.name = 'HUB_ENTITY'
    # invalid_at must be set as timestamp() to match schema
    query = """
        MATCH (e:Entity {uuid: $entity_uuid})-[r:RELATES_TO]->(c:Entity {name: 'Consolidation System'})
        WHERE r.name = 'HUB_ENTITY' AND r.invalid_at IS NULL
        SET r.invalid_at = timestamp($invalid_at)
        RETURN count(r) as invalidated
    """
    try:
        result = graph_db.conn.execute(query, {"entity_uuid": entity_uuid, "invalid_at": invalid_at})
        if result.has_next():
            return result.get_next()[0]
    except Exception as e:
        safe_print(f"  [DEBUG] Invalidation error: {e}")
    return 0


def store_hub_detections(sql_db: SQLDatabase, graph_db: GraphDatabase, project_name: str, hubs: list):
    """Store hub detections with separate hash chain.

    When storing a new detection for an entity, invalidates (supersedes) any
    existing active detection for that same entity. This ensures cleanup can
    safely archive old detections.
    """
    safe_print(f"\n[STORE] Storing {len(hubs)} hub detections...")

    # Get last hub detection for chain
    last_detection = get_last_hub_detection(graph_db, project_name)
    hub_chain_index = (last_detection['chain_index'] + 1) if last_detection else 0
    previous_hub_hash = last_detection['hash'] if last_detection else None

    # Ensure consolidation entity exists
    consolidation_uuid = ensure_consolidation_entity(graph_db, project_name)

    stored_count = 0

    for hub in hubs:
        # Get entity and facts for hash calculation
        entity, facts = get_entity_with_facts(graph_db, hub['name'], project_name)
        if not entity:
            safe_print(f"[WARN] Entity {hub['name']} not found, skipping")
            continue

        # Calculate hashes
        entity_hash = hashlib.sha256(
            json.dumps(entity, sort_keys=True).encode()
        ).hexdigest()

        facts_hash = calculate_facts_hash(facts)

        # Create hub detection record
        detection_uuid = str(uuid_lib.uuid4())
        detected_at = datetime.now().isoformat()

        detection_data = {
            'detection_uuid': detection_uuid,
            'entity_uuid': entity['uuid'],
            'entity_name': entity['name'],
            'hub_score': hub['count'],
            'detected_at': detected_at,
            'source_entity_hash': entity_hash,
            'source_facts_hash': facts_hash,
            'source_facts_count': len(facts),
            'hub_chain_index': hub_chain_index,
            'previous_hub_hash': previous_hub_hash,
        }

        # Calculate current hub hash
        current_hub_hash = hashlib.sha256(
            json.dumps(detection_data, sort_keys=True).encode()
        ).hexdigest()

        detection_data['current_hub_hash'] = current_hub_hash

        # Store as RELATES_TO relationship to Consolidation System entity
        try:
            # Invalidate any existing active hub detection for this entity
            invalidated = invalidate_existing_hub_detection(graph_db, entity['uuid'], detected_at)
            if invalidated > 0:
                safe_print(f"  [SUPERSEDE] Invalidated {invalidated} prior detection(s) for {entity['name']}")

            # Store detection data in attributes (includes current_hub_hash)
            graph_db.create_relationship(
                source_uuid=entity['uuid'],
                target_uuid=consolidation_uuid,
                relationship_name='HUB_ENTITY',
                fact=f"{entity['name']} is a hub with {hub['count']} relationships (detected by consolidation)",
                episodes=[],  # Not linked to conversation chain!
                episode_hashes=[],
                group_id=project_name,
                valid_at=detected_at,
                invalid_at=None,
                attributes=detection_data,  # Contains all hub chain data!
                derivation_version='consolidation-v1.0.0',
                derivation_commit='hub-detection-separate-chain'
            )



            # Update for next hub in chain
            previous_hub_hash = current_hub_hash
            hub_chain_index += 1
            stored_count += 1

        except Exception as e:
            safe_print(f"[ERROR] Failed to store hub {entity['name']}: {e}")
            import traceback
            traceback.print_exc()

    safe_print(f"[STORE] ✅ Stored {stored_count}/{len(hubs)} hub detections")


def cleanup_old_hub_detections(graph_db: GraphDatabase, project_name: str, keep_days: int = 180):
    """Archive and delete SUPERSEDED hub detections older than keep_days.

    Only cleans up detections that have been invalidated (superseded by newer
    detections). Active detections (invalid_at IS NULL) are never cleaned up.
    """
    safe_print(f"\n[CLEANUP] Archiving superseded hub detections older than {keep_days} days...")

    cutoff = (datetime.now() - timedelta(days=keep_days)).isoformat()

    # Get superseded (invalidated) hub detections that are old enough to archive
    # Note: Only targets detections where invalid_at IS NOT NULL (superseded)
    # HUB_ENTITY is stored as RELATES_TO with r.name = 'HUB_ENTITY'
    # hub_score, detected_at are inside r.attributes JSON
    # CRITICAL: Must be project-scoped to avoid deleting other projects' detections
    query = """
        MATCH (p:Project {name: $project_name})-[:HAS_ENTITY]->(e:Entity)-[r:RELATES_TO]->(c:Entity {name: 'Consolidation System'})
        WHERE r.name = 'HUB_ENTITY'
        AND r.invalid_at IS NOT NULL
        AND r.invalid_at < $cutoff
        RETURN e.name, r.attributes, r.invalid_at
    """

    result = graph_db.conn.execute(query, {"cutoff": cutoff, "project_name": project_name})
    old_detections = []

    while result.has_next():
        row = result.get_next()
        # Parse attributes JSON for hub_score, detected_at
        attrs = row[1] if isinstance(row[1], dict) else json.loads(row[1]) if row[1] else {}
        old_detections.append({
            'entity_name': row[0],
            'hub_score': attrs.get('hub_score'),
            'detected_at': attrs.get('detected_at'),
            'invalid_at': str(row[2])
        })

    if old_detections:
        # Archive to file
        archive_file = f'hub_archive_{project_name}.jsonl'
        with open(archive_file, 'a') as f:
            for detection in old_detections:
                f.write(json.dumps(detection) + '\n')

        safe_print(f"[CLEANUP] Archived {len(old_detections)} superseded detections to {archive_file}")

        # Delete superseded detections from graph - project-scoped
        delete_query = """
            MATCH (p:Project {name: $project_name})-[:HAS_ENTITY]->(e:Entity)-[r:RELATES_TO]->(c:Entity {name: 'Consolidation System'})
            WHERE r.name = 'HUB_ENTITY'
            AND r.invalid_at IS NOT NULL
            AND r.invalid_at < $cutoff
            DELETE r
        """
        graph_db.conn.execute(delete_query, {"cutoff": cutoff, "project_name": project_name})

        safe_print(f"[CLEANUP] Deleted {len(old_detections)} superseded detections from graph")
    else:
        safe_print(f"[CLEANUP] No superseded detections to archive")


def main():
    parser = ConsolidateArgumentParser(
        description='Consolidate knowledge - find higher-order patterns in the graph',
        epilog=CONSOLIDATE_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--project', required=True, help='Project name')
    parser.add_argument('--min-hub-size', type=int, default=5, help='Minimum relationships for hub entities (default: 5)')
    parser.add_argument('--min-cluster-size', type=int, default=5, help='Minimum members for clusters (default: 5)')
    parser.add_argument('--find-transitive', action='store_true', help='Find transitive relationships (can be slow)')
    parser.add_argument('--graph-db', help='Path to graph database (overrides config)')
    parser.add_argument('--store', action='store_true', help='Store insights as derived facts with separate hash chain')
    parser.add_argument('--cleanup', action='store_true', help='Archive and delete hub detections (uses config settings or --archive-days)')
    parser.add_argument('--archive-days', type=int, help='Days to keep in graph before archiving (overrides config, default from config: 180)')

    args = parser.parse_args()

    # Load config using standard config loader
    config = load_config(project_name=args.project, cli_args={
        "graph_db": args.graph_db
    })

    # Connect to graph database
    graph_path = config.get_graph_db_path()
    graph_db = GraphDatabase(graph_path)

    safe_print("="*80)
    safe_print("KNOWLEDGE CONSOLIDATION")
    safe_print("="*80)
    safe_print(f"\nProject: {args.project}")
    safe_print(f"Finding higher-order patterns in the knowledge graph...\n")

    # Find hubs
    hubs = find_hubs(graph_db, args.project, args.min_hub_size)

    # Find neighborhoods (connected entity groups)
    clusters = find_neighborhoods(graph_db, args.project, args.min_cluster_size)

    # Find relationship patterns
    patterns = find_relationship_patterns(graph_db, args.project)

    # Find transitive relationships (optional, can be slow)
    transitive = []
    if args.find_transitive:
        transitive = find_transitive_relationships(graph_db, args.project, 'ENABLES')

    # Store insights if requested
    if args.store:
        sql_db = SQLDatabase(config.get_sql_db_path())
        store_hub_detections(sql_db, graph_db, args.project, hubs)
        # TODO: Store clusters and patterns similarly

    # Determine cleanup settings
    consolidation_config = config.get('consolidation', {})
    auto_cleanup = consolidation_config.get('auto_cleanup_enabled', False)
    archive_days = args.archive_days if args.archive_days is not None else consolidation_config.get('archive_after_days', 180)

    # Cleanup old detections if requested or auto-enabled
    should_cleanup = args.cleanup or (args.store and auto_cleanup)

    if should_cleanup:
        cleanup_old_hub_detections(graph_db, args.project, archive_days)

    # Summary
    safe_print("\n" + "="*80)
    safe_print("CONSOLIDATION SUMMARY")
    safe_print("="*80)
    safe_print(f"\n✅ Hub entities: {len(hubs)}")
    safe_print(f"[OK] Neighborhoods: {len(clusters)}")
    safe_print(f"✅ Common patterns: {len(patterns)}")
    if args.find_transitive:
        safe_print(f"✅ Transitive chains: {len(transitive)}")

    if args.store:
        safe_print(f"\n💾 Insights stored in graph with separate hash chain!")
        if auto_cleanup:
            safe_print(f"   Auto-cleanup enabled (archive after {archive_days} days)")
    else:
        safe_print(f"\n💡 Run with --store to save insights to graph")

    if should_cleanup:
        if args.cleanup:
            safe_print(f"🗑️  Cleaned up detections older than {archive_days} days (manual)")
        else:
            safe_print(f"🗑️  Cleaned up detections older than {archive_days} days (auto)")

    safe_print("\n💡 These insights show the structure of your knowledge graph!")
    safe_print("   - Hubs are central concepts")
    safe_print("   - Neighborhoods are connected entity groups")
    safe_print("   - Patterns show common relationships")
    if args.find_transitive:
        safe_print("   - Transitive chains show implied connections")

    # Update last run timestamp
    from tools.consolidation_reminder import update_last_run_timestamp
    update_last_run_timestamp()
    safe_print("\n✅ Consolidation timestamp updated")


if __name__ == '__main__':
    main()


