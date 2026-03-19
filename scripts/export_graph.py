#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Export knowledge graph to JSON for visualization.
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

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.graph_db import GraphDatabase
from tools.config import load_config


EXPORT_GRAPH_EXAMPLES = """
Examples:
  # Basic export (all entities)
  python scripts/export_graph.py --project llm_memory --output graph.json

  # Limit to 50 entities
  python scripts/export_graph.py --project llm_memory --output graph.json --limit 50

  # Last 7 days only
  python scripts/export_graph.py --project llm_memory --output recent.json --last-days 7

  # Entity-centered (use file for names with spaces)
  echo "My Entity" > tmp/center.txt
  python scripts/export_graph.py --project llm_memory --output centered.json --center-file tmp/center.txt --depth 2

Note: Open visualize_graph.html in browser and load the JSON file.
"""


class ExportGraphArgumentParser(argparse.ArgumentParser):
    """Custom parser that prints examples on error."""
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: error: {message}\n{EXPORT_GRAPH_EXAMPLES}")


def export_centered_graph(graph_db: GraphDatabase, project_name: str, center_name: str, depth: int, where_clause: str):
    """Export graph centered on a specific entity with depth control."""

    # Find center entity
    result = graph_db.conn.execute(f"""
        MATCH (p:Project {{name: '{project_name}'}})-[:HAS_ENTITY]->(e:Entity)
        WHERE e.name = '{center_name.replace("'", "''")}' AND e.deleted_at IS NULL
        RETURN e.uuid, e.name, e.labels, e.summary
        LIMIT 1
    """)

    if not result.has_next():
        print(f"  [ERROR] Center entity '{center_name}' not found!")
        print(f"  Tip: Use query_memory.py to search for entities first")
        print(f"  Example: python scripts/query_memory.py --project {project_name} --search {center_name}")
        return [], set()

    # Get center entity
    row = result.get_next()
    center_uuid = row[0]

    # Collect entities at each depth level
    all_uuids = {center_uuid}
    current_level = {center_uuid}

    # Traverse graph to specified depth
    current_depth = 0
    while current_level and (depth is None or current_depth < depth):
        # Get entities connected to current level
        uuid_list = "', '".join(current_level)
        result = graph_db.conn.execute(f"""
            MATCH (e1:Entity)-[r]-(e2:Entity)
            WHERE e1.uuid IN ['{uuid_list}']
              AND e2.deleted_at IS NULL
              AND {where_clause}
            RETURN DISTINCT e2.uuid
        """)

        next_level = set()
        while result.has_next():
            uuid = result.get_next()[0]
            if uuid not in all_uuids:
                next_level.add(uuid)
                all_uuids.add(uuid)

        current_level = next_level
        current_depth += 1

    # Get full entity data for all collected UUIDs
    uuid_list = "', '".join(all_uuids)
    result = graph_db.conn.execute(f"""
        MATCH (e:Entity)
        WHERE e.uuid IN ['{uuid_list}']
        RETURN e.uuid, e.name, e.labels, e.summary
    """)

    nodes = []
    while result.has_next():
        row = result.get_next()
        uuid = row[0]
        name = row[1]
        labels = row[2] if row[2] else []
        summary = row[3] if row[3] else ""

        # Handle labels
        if isinstance(labels, list) and len(labels) > 0:
            entity_type = labels[0]
        elif isinstance(labels, str) and labels:
            import ast
            try:
                parsed = ast.literal_eval(labels)
                entity_type = parsed[0] if parsed else 'Unknown'
            except:
                entity_type = labels if labels else 'Unknown'
        else:
            entity_type = 'Unknown'

        nodes.append({
            'id': uuid,
            'name': name,
            'type': entity_type,
            'summary': summary,
            'group': hash(entity_type) % 10,
            'is_center': uuid == center_uuid
        })

    return nodes, all_uuids


def export_graph(graph_db: GraphDatabase, project_name: str, limit: int = None,
                last_days: int = None, start_date: str = None, end_date: str = None,
                center_entity: str = None, depth: int = None,
                entity_types: list = None, exclude_types: list = None,
                from_documents: bool = False):
    """
    Export graph to JSON format for visualization with smart filtering.

    Args:
        graph_db: Graph database connection
        project_name: Project name
        limit: Max number of entities
        last_days: Only entities from last N days
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        center_entity: Export entities connected to this entity
        depth: How many layers deep to follow connections (default: all)
        entity_types: Only include these entity types
        exclude_types: Exclude these entity types
        from_documents: Only entities from ExternalSource documents

    Returns dict with nodes and links.
    """
    print(f"Exporting graph for project: {project_name}")

    # Build WHERE clause for filtering
    where_clauses = []

    # Time-based filtering
    if last_days:
        from datetime import datetime, timedelta
        cutoff_date = (datetime.now() - timedelta(days=last_days)).isoformat()
        where_clauses.append(f"e.created_at >= timestamp('{cutoff_date}')")
        print(f"  Filter: Last {last_days} days (since {cutoff_date[:10]})")
    elif start_date and end_date:
        where_clauses.append(f"e.created_at >= timestamp('{start_date}') AND e.created_at <= timestamp('{end_date}')")
        print(f"  Filter: {start_date} to {end_date}")

    # Type filtering
    if entity_types:
        type_conditions = " OR ".join([f"e.labels CONTAINS '{t}'" for t in entity_types])
        where_clauses.append(f"({type_conditions})")
        print(f"  Filter: Types = {', '.join(entity_types)}")

    if exclude_types:
        for t in exclude_types:
            where_clauses.append(f"NOT e.labels CONTAINS '{t}'")
        print(f"  Filter: Exclude types = {', '.join(exclude_types)}")

    # Document filtering
    if from_documents:
        where_clauses.append("e.labels CONTAINS 'ExternalSource'")
        print(f"  Filter: From documents only")

    where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"

    # Get entities (nodes)
    if center_entity:
        # Entity-centered export with depth control
        print(f"  Filter: Centered on '{center_entity}' (depth: {depth if depth else 'all'})")
        nodes, entity_uuids = export_centered_graph(graph_db, project_name, center_entity, depth, where_clause)
        if not nodes:
            # Return empty graph if center not found
            return {'nodes': [], 'links': []}
    else:
        # Regular export
        result = graph_db.conn.execute(f"""
            MATCH (p:Project {{name: '{project_name}'}})-[:HAS_ENTITY]->(e:Entity)
            WHERE {where_clause} AND e.deleted_at IS NULL
            RETURN e.uuid, e.name, e.labels, e.summary
            {'LIMIT ' + str(limit) if limit else ''}
        """)
    
    nodes = []
    entity_uuids = set()
    
    while result.has_next():
        row = result.get_next()
        uuid = row[0]
        name = row[1]
        labels = row[2] if row[2] else []
        summary = row[3] if row[3] else ""

        # Handle labels - could be list or string
        if isinstance(labels, list) and len(labels) > 0:
            entity_type = labels[0]
        elif isinstance(labels, str) and labels:
            # If it's a string representation of a list, try to parse it
            import ast
            try:
                parsed = ast.literal_eval(labels)
                entity_type = parsed[0] if parsed else 'Unknown'
            except:
                entity_type = labels if labels else 'Unknown'
        else:
            entity_type = 'Unknown'

        nodes.append({
            'id': uuid,
            'name': name,
            'type': entity_type,
            'summary': summary,
            'group': hash(entity_type) % 10
        })
        entity_uuids.add(uuid)
    
    print(f"  Entities: {len(nodes)}")
    
    # Get relationships (links)
    uuid_list = "', '".join(entity_uuids)
    result = graph_db.conn.execute(f"""
        MATCH (source:Entity)-[r:RELATES_TO]->(target:Entity)
        WHERE source.uuid IN ['{uuid_list}'] AND target.uuid IN ['{uuid_list}']
        AND r.invalid_at IS NULL
        RETURN source.uuid, target.uuid, r.name, r.fact
    """)
    
    links = []
    while result.has_next():
        row = result.get_next()
        source = row[0]
        target = row[1]
        rel_type = row[2]
        fact = row[3]
        
        links.append({
            'source': source,
            'target': target,
            'type': rel_type,
            'fact': fact
        })
    
    print(f"  Relationships: {len(links)}")
    
    return {
        'nodes': nodes,
        'links': links,
        'metadata': {
            'project': project_name,
            'node_count': len(nodes),
            'link_count': len(links)
        }
    }


def main():
    parser = ExportGraphArgumentParser(
        description='Export knowledge graph to JSON for visualization with smart filtering',
        epilog=EXPORT_GRAPH_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--project', required=True, help='Project name')
    parser.add_argument('--output', required=True, help='Output JSON file')
    parser.add_argument('--limit', type=int, help='Limit number of entities')

    # Time-based filtering
    parser.add_argument('--last-days', type=int, help='Only entities from last N days')
    parser.add_argument('--start', help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', help='End date (YYYY-MM-DD)')

    # Entity-centered export
    parser.add_argument('--center', help='Center on specific entity name (use --center-file for names with spaces)')
    parser.add_argument('--center-file', help='File containing entity name to center on (RECOMMENDED: avoids quote issues)')
    parser.add_argument('--depth', type=int, help='How many layers deep to follow connections (default: all)')

    # Type filtering
    parser.add_argument('--types', help='Comma-separated list of entity types to include')
    parser.add_argument('--exclude-types', help='Comma-separated list of entity types to exclude')

    # Document filtering
    parser.add_argument('--from-documents', action='store_true', help='Only entities from ExternalSource documents')

    args = parser.parse_args()

    # Read center entity from file if provided
    center_entity = args.center
    if args.center_file:
        with open(args.center_file, 'r', encoding='utf-8') as f:
            center_entity = f.read().strip()

    # Parse type lists
    entity_types = args.types.split(',') if args.types else None
    exclude_types = args.exclude_types.split(',') if args.exclude_types else None
    
    config = load_config(project_name=args.project)
    graph_db = GraphDatabase(config.get_graph_db_path(args.project))

    # Export graph with filters
    graph_data = export_graph(
        graph_db,
        args.project,
        limit=args.limit,
        last_days=args.last_days,
        start_date=args.start,
        end_date=args.end,
        center_entity=center_entity,
        depth=args.depth,
        entity_types=entity_types,
        exclude_types=exclude_types,
        from_documents=args.from_documents
    )
    
    # Save to file
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(graph_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Graph exported to: {args.output}")
    print(f"   Open visualize_graph.html in a browser to view!")


if __name__ == '__main__':
    main()
