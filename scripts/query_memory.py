#!/usr/bin/env python3
"""
Query the memory graph for entities, facts, and relationships.

EXAMPLES:

  # List all entities
  python scripts/query_memory.py --project my-project --all

  # Get last 10 entities
  python scripts/query_memory.py --project my-project --last 10

  # Search (agent workflow: use file)
  python scripts/query_memory.py --project my-project --search-file tmp/search.txt

  # Get entity (agent workflow: use file)
  python scripts/query_memory.py --project my-project --entity-file tmp/entity.txt

  # JSON output
  python scripts/query_memory.py --project my-project --all --json

NOTE: Agent-facing workflows should use helper files for query/name input.
      Create helper files with prepare_sync_files.py or your agent's file tool.
      Do NOT use shell echo/Out-File on Windows (creates UTF-16).

DATABASE PATH:
  Default: ./memory/{project_name}.graph
  Override: --db ./path/to/database.graph

NOTE: Direct string query/name flags are disabled by default for workflow use.
      Set MEM_ALLOW_DIRECT_INPUT=1 only for legacy/manual compatibility.
"""

import sys
import os
import argparse
import json
from datetime import date, datetime

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tools.graph_db import GraphDatabase
from tools.config import load_config
from tools.console_utils import safe_print, setup_console_encoding

# Setup console encoding for Windows
setup_console_encoding()


def make_json_safe(value):
    """Recursively convert values to JSON-serializable types."""
    if isinstance(value, dict):
        return {key: make_json_safe(val) for key, val in value.items()}
    if isinstance(value, list):
        return [make_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [make_json_safe(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def print_entity(entity, verbose=False):
    """Print entity in human-readable format."""
    safe_print(f"\n[PACKAGE] {entity['name']}")
    safe_print(f"   UUID: {entity['uuid']}")
    if entity.get('summary'):
        safe_print(f"   Summary: {entity['summary']}")
    if entity.get('labels'):
        safe_print(f"   Labels: {', '.join(entity['labels'])}")
    if verbose and entity.get('extraction_version'):
        safe_print(f"   Extracted: {entity['extraction_version']} ({entity.get('extraction_commit', '')[:8]})")


def print_fact(fact):
    """Print fact in human-readable format."""
    safe_print(f"\n[IDEA] {fact['fact']}")
    if 'source_name' in fact:
        safe_print(f"   {fact['source_name']} -[{fact['relationship_type']}]-> {fact['target_name']}")
    if 'uuid' in fact:
        safe_print(f"   UUID: {fact['uuid']}")


def filter_entity_facts(facts, direction="both", relationship_type=None):
    """Apply direction and relationship-type filters to an entity's facts."""
    filtered = []
    for fact in facts:
        if direction != "both" and fact.get("direction") != direction:
            continue
        if relationship_type and fact.get("relationship_type") != relationship_type:
            continue
        filtered.append(fact)
    return filtered


def find_legacy_graph_paths(memory_dir, project_name):
    """Find legacy graph database paths for a project.

    Note: .db is NOT a legacy graph extension - it's SQLite (SQL database).
    Only .kuzu was the old KuzuDB extension before standardizing to .graph
    """
    legacy_paths = []
    for ext in ('.kuzu',):  # .db is SQL, not graph
        path = os.path.join(memory_dir, f'{project_name}{ext}')
        if os.path.exists(path):
            try:
                if os.path.getsize(path) == 0:
                    continue
            except OSError:
                pass
            legacy_paths.append(path)
    return legacy_paths


def read_text_file(path):
    """Read UTF-8 helper file content."""
    with open(path, 'r', encoding='utf-8') as f:
        return f.read().strip()


def apply_file_input(args, value_attr, file_attr, display_name):
    """Prefer helper-file input when provided."""
    file_path = getattr(args, file_attr)
    if not file_path:
        return

    direct_value = getattr(args, value_attr)
    if direct_value:
        safe_print(
            f"[WARNING] Both --{value_attr.replace('_', '-')} and --{file_attr.replace('_', '-')} were provided; "
            f"using --{file_attr.replace('_', '-')}.",
            file=sys.stderr,
        )
    setattr(args, value_attr, read_text_file(file_path))
    if not getattr(args, value_attr):
        safe_print(f"[ERROR] {display_name} helper file is empty: {file_path}", file=sys.stderr)
        sys.exit(1)


def warn_direct_input(raw_argv, direct_flag, file_flag, helper_path):
    """Reject direct string flags unless legacy compatibility is explicitly enabled."""
    if direct_flag in raw_argv and file_flag not in raw_argv:
        if os.getenv("MEM_ALLOW_DIRECT_INPUT") != "1":
            safe_print(
                f"[ERROR] {direct_flag} is disabled by default. "
                f"Write the value to {helper_path} and use {file_flag}. "
                f"Set MEM_ALLOW_DIRECT_INPUT=1 only for legacy/manual compatibility.",
                file=sys.stderr,
            )
            sys.exit(1)
        safe_print(
            f"[WARNING] {direct_flag} is allowed only because MEM_ALLOW_DIRECT_INPUT=1 is set. "
            f"Prefer {file_flag} with {helper_path}.",
            file=sys.stderr,
        )


def main():
    raw_argv = sys.argv[1:]
    parser = argparse.ArgumentParser(
        description='Query the knowledge graph memory system',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    # Database
    parser.add_argument('--db',
                       help='Path to graph database (default: auto-detect from --project)')
    parser.add_argument('--config', help='Path to config file (default: ./mem.config.json or MEM_CONFIG)')

    # Query type
    parser.add_argument('--project', help='Project name (required for most queries)')
    parser.add_argument('--search', help='Deprecated direct search string (use --search-file)')
    parser.add_argument('--search-file', help='File containing search query (workflow standard)')
    parser.add_argument('--label', help='Filter entities by label')
    parser.add_argument('--entity', help='Deprecated direct entity name (use --entity-file)')
    parser.add_argument('--entity-file', help='File containing entity name (workflow standard)')
    parser.add_argument('--entity-uuid', help='Get entity by UUID')
    parser.add_argument('--facts', help='Deprecated direct facts search string (use --facts-file)')
    parser.add_argument('--facts-file', help='File containing facts search query (workflow standard)')
    parser.add_argument('--related', action='store_true',
                       help='Get related entities (requires --entity-uuid)')
    parser.add_argument('--all', action='store_true',
                       help='Get all entities in project')

    # Cross-project queries
    parser.add_argument('--all-projects', action='store_true',
                       help='Search across ALL projects (use with search input)')
    parser.add_argument('--list-projects', action='store_true',
                       help='List all projects in database')

    # Procedural memory queries
    parser.add_argument('--procedures', action='store_true',
                       help='List all procedures in project')
    parser.add_argument('--procedure', help='Deprecated direct procedure name (use --procedure-file)')
    parser.add_argument('--procedure-file', help='File containing procedure name (workflow standard)')
    parser.add_argument('--search-procedures', help='Deprecated direct procedure search string (use --search-procedures-file)')
    parser.add_argument('--search-procedures-file', help='File containing procedure search query (workflow standard)')
    parser.add_argument('--include-deprecated', action='store_true',
                       help='Include deprecated/superseded/invalid procedures in results')

    # Options
    parser.add_argument('--direction', choices=['outgoing', 'incoming', 'both'],
                       default='both', help='Direction for --related (default: both)')
    parser.add_argument('--type', help='Filter by relationship type')
    parser.add_argument('--limit', type=int, default=50, help='Max results (default: 50)')
    parser.add_argument('--last', type=int, help='Get last N entities (most recent)')
    parser.add_argument('--export', help='Export results to JSON file')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')

    # Universal JSON input
    parser.add_argument('--input-file', help='JSON file with all parameters (RECOMMENDED)')

    args, unknown = parser.parse_known_args()

    # Check for unrecognized arguments (likely multi-word search terms split by shell)
    if unknown:
        print(f"[ERROR] Unrecognized arguments: {' '.join(unknown)}")
        print()
        print("This usually happens when search terms contain spaces.")
        print("The shell splits 'workflow hardening' into two separate arguments.")
        print()
        print("FIX: Use --search-file instead:")
        print("  1. Run: python scripts/prepare_sync_files.py --project PROJECT --json")
        print("  2. Edit tmp/search.txt with your query (use agent's file tool)")
        print("  3. Run: python scripts/query_memory.py --project PROJECT --search-file tmp/search.txt")
        print()
        print("For entity names, use --entity-file with tmp/entity.txt")
        sys.exit(1)

    # Load from JSON input file if provided
    if args.input_file:
        with open(args.input_file, 'r', encoding='utf-8') as f:
            data = json.loads(f.read())
        # Map JSON keys to args
        key_mapping = {
            'project': 'project',
            'search': 'search',
            'label': 'label',
            'entity': 'entity',
            'entity-uuid': 'entity_uuid',
            'entity_uuid': 'entity_uuid',
            'facts': 'facts',
            'procedure': 'procedure',
            'search-procedures': 'search_procedures',
            'search_procedures': 'search_procedures',
            'direction': 'direction',
            'type': 'type',
            'limit': 'limit',
            'last': 'last',
        }
        for json_key, attr_name in key_mapping.items():
            if json_key in data and not getattr(args, attr_name, None):
                setattr(args, attr_name, data[json_key])

    # Read helper files after JSON input so file-based workflow stays authoritative.
    apply_file_input(args, 'search', 'search_file', 'Search query')
    apply_file_input(args, 'entity', 'entity_file', 'Entity name')
    apply_file_input(args, 'facts', 'facts_file', 'Facts query')
    apply_file_input(args, 'procedure', 'procedure_file', 'Procedure name')
    apply_file_input(args, 'search_procedures', 'search_procedures_file', 'Procedure search query')

    warn_direct_input(raw_argv, '--search', '--search-file', 'tmp/search.txt')
    warn_direct_input(raw_argv, '--entity', '--entity-file', 'tmp/entity.txt')
    warn_direct_input(raw_argv, '--facts', '--facts-file', 'tmp/search.txt')
    warn_direct_input(raw_argv, '--procedure', '--procedure-file', 'tmp/proc.txt')
    warn_direct_input(raw_argv, '--search-procedures', '--search-procedures-file', 'tmp/search.txt')

    config = load_config(
        project_name=args.project,
        cli_args={"graph_db": args.db, "config": args.config},
        config_path=args.config,
    )
    memory_dir = config.get_memory_dir()

    # Handle --list-projects (doesn't need project name)
    if args.list_projects:
        if not args.db:
            args.db = config.get_graph_db_path()

    # Auto-detect database path from project name
    elif not args.db:
        if args.all_projects:
            # Use shared database for cross-project queries
            args.db = config.get_graph_db_path()
        elif args.entity_uuid:
            # UUID lookup can use the configured default project database.
            args.db = config.get_graph_db_path()
        elif args.project:
            args.db = config.get_graph_db_path(args.project)
            legacy_paths = find_legacy_graph_paths(memory_dir, args.project)

            if legacy_paths and not os.path.exists(args.db):
                safe_print(f"[ERROR] Canonical graph database not found: {args.db}", file=sys.stderr)
                safe_print("[ERROR] Legacy graph database path(s) detected:", file=sys.stderr)
                for path in legacy_paths:
                    safe_print(f"  - {path}", file=sys.stderr)
                safe_print("[ERROR] Run scripts/consolidate_graph_db_paths.py before querying.", file=sys.stderr)
                sys.exit(1)

            if legacy_paths and os.path.exists(args.db):
                safe_print(f"[ERROR] Duplicate graph databases detected for project '{args.project}'", file=sys.stderr)
                safe_print(f"[ERROR] Canonical path: {args.db}", file=sys.stderr)
                for path in legacy_paths:
                    safe_print(f"  - Legacy path still present: {path}", file=sys.stderr)
                safe_print("[ERROR] Run scripts/consolidate_graph_db_paths.py to resolve duplicates.", file=sys.stderr)
                sys.exit(1)

            if not os.path.exists(args.db):
                safe_print(f"[ERROR] Database not found: {args.db}", file=sys.stderr)
                safe_print(f"[ERROR] Run store_extraction.py first to create the database", file=sys.stderr)
                sys.exit(1)
        else:
            safe_print("[ERROR] Either --db or --project is required", file=sys.stderr)
            parser.print_help()
            sys.exit(1)

    # Validate database exists
    if not os.path.exists(args.db):
        safe_print(f"[ERROR] Database file not found: {args.db}", file=sys.stderr)
        sys.exit(1)

    # Check if database is empty
    db_size = os.path.getsize(args.db)
    if db_size < 50000:  # Less than 50KB is probably empty
        safe_print(f"[WARNING] Database appears empty or new: {args.db} ({db_size:,} bytes)", file=sys.stderr)

    if args.verbose:
        safe_print(f"[NOTE] Using database: {args.db} ({db_size:,} bytes)")

    # Connect to database
    db = GraphDatabase(args.db)
    
    results = None
    result_type = None

    # Execute query
    if args.list_projects:
        # List all projects in database
        try:
            result = db.conn.execute("""
                MATCH (p:Project)
                RETURN p.name, p.description, p.created_at
                ORDER BY p.name
            """)
            projects = []
            while result.has_next():
                row = result.get_next()
                projects.append({
                    'name': row[0],
                    'description': row[1] if row[1] else '',
                    'created_at': row[2]
                })

            if args.json:
                safe_print(json.dumps(make_json_safe(projects)))
            else:
                safe_print(f"\n[SEARCH] Projects in database:\n")
                for i, proj in enumerate(projects, 1):
                    safe_print(f"{i}. {proj['name']}")
                    if proj['description']:
                        safe_print(f"   Description: {proj['description']}")

                    # Count entities and facts for this project
                    entity_result = db.conn.execute("""
                        MATCH (p:Project {name: $project_name})-[:HAS_ENTITY]->(e:Entity)
                        WHERE e.deleted_at IS NULL
                        RETURN count(e)
                    """, {
                        "project_name": proj['name'],
                    })
                    entity_count = entity_result.get_next()[0] if entity_result.has_next() else 0

                    fact_result = db.conn.execute("""
                        MATCH (p:Project {name: $project_name})-[:HAS_ENTITY]->(e1:Entity)-[r:RELATES_TO]->(e2:Entity)
                        WHERE r.expired_at IS NULL
                        RETURN count(r)
                    """, {
                        "project_name": proj['name'],
                    })
                    fact_count = fact_result.get_next()[0] if fact_result.has_next() else 0

                    safe_print(f"   Entities: {entity_count}")
                    safe_print(f"   Facts: {fact_count}")
                    safe_print()

                safe_print(f"Total projects: {len(projects)}")
            return
        except Exception as e:
            safe_print(f"[ERROR] Failed to list projects: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.last:
        if not args.project:
            safe_print("Error: --last requires --project", file=sys.stderr)
            sys.exit(1)

        # Get last N entities (most recent)
        try:
            query = """
                MATCH (p:Project {name: $project_name})-[:HAS_ENTITY]->(e:Entity)
                WHERE e.deleted_at IS NULL
                RETURN e.uuid AS uuid, e.name AS name, e.summary AS summary,
                       e.labels AS labels, e.extraction_proof AS extraction_proof,
                       e.created_at AS created_at
                ORDER BY e.created_at DESC
                LIMIT $limit
            """
            result = db.conn.execute(query, {
                "project_name": args.project,
                "limit": args.last,
            })

            results = []
            while result.has_next():
                row = result.get_next()
                # Parse labels (JSON array string) but not extraction_proof (hash string)
                labels = []
                if row[3]:
                    try:
                        labels = json.loads(row[3]) if isinstance(row[3], str) else row[3]
                    except json.JSONDecodeError:
                        labels = [row[3]]  # Treat as single label if not JSON

                results.append({
                    'uuid': row[0],
                    'name': row[1],
                    'summary': row[2],
                    'labels': labels,
                    'extraction_proof': row[4] or '',  # Hash string, not JSON
                    'created_at': str(row[5])
                })

            result_type = 'entities'

            # Export if requested
            if args.export:
                with open(args.export, 'w') as f:
                    json.dump(results, f)
                safe_print(f"[SUCCESS] Exported {len(results)} entities to {args.export}")
                return

        except Exception as e:
            safe_print(f"[ERROR] Failed to get last entities: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.all:
        if not args.project:
            safe_print("Error: --all requires --project", file=sys.stderr)
            sys.exit(1)
        if args.type:
            results = db.search_facts(
                args.project,
                relationship_type=args.type,
                limit=args.limit
            )
            result_type = 'facts'
        else:
            results = db.get_all_entities(args.project, limit=args.limit)
            result_type = 'entities'
        
    elif args.search:
        if args.all_projects:
            # Cross-project search
            try:
                query_text = args.search.lower()
                result = db.conn.execute("""
                    MATCH (p:Project)-[:HAS_ENTITY]->(e:Entity)
                    WHERE e.deleted_at IS NULL
                      AND (lower(e.name) CONTAINS $query_text
                           OR lower(e.summary) CONTAINS $query_text)
                    RETURN p.name, e.uuid, e.name, e.summary, e.labels, e.created_at
                    ORDER BY e.created_at DESC
                    LIMIT $limit
                """, {
                    "query_text": query_text,
                    "limit": args.limit,
                })

                results_by_project = {}
                while result.has_next():
                    row = result.get_next()
                    project_name = row[0]
                    entity = {
                        'uuid': row[1],
                        'name': row[2],
                        'summary': row[3] if row[3] else '',
                        'labels': row[4] if row[4] else [],
                        'created_at': row[5]
                    }

                    if project_name not in results_by_project:
                        results_by_project[project_name] = []
                    results_by_project[project_name].append(entity)

                if args.json:
                    safe_print(json.dumps(make_json_safe(results_by_project)))
                else:
                    total_entities = sum(len(entities) for entities in results_by_project.values())
                    safe_print(f"\n[SEARCH] Searching across ALL projects for '{args.search}'...\n")

                    for project_name, entities in sorted(results_by_project.items()):
                        safe_print(f"[PROJECT: {project_name}]")
                        for entity in entities:
                            safe_print(f"  [ENTITY] {entity['name']} (Type: {', '.join(entity['labels']) if entity['labels'] else 'Unknown'})")
                            if entity['summary']:
                                safe_print(f"     Summary: {entity['summary']}")
                        safe_print()

                    safe_print(f"Total entities: {total_entities} (across {len(results_by_project)} projects)")
                return
            except Exception as e:
                safe_print(f"[ERROR] Cross-project search failed: {e}", file=sys.stderr)
                import traceback
                traceback.print_exc()
                sys.exit(1)
        elif not args.project:
            safe_print("Error: --search requires --project (or use --all-projects)", file=sys.stderr)
            sys.exit(1)
        else:
            results = db.search_entities(args.project, query=args.search, limit=args.limit)
            result_type = 'entities'
        
    elif args.label:
        if not args.project:
            safe_print("Error: --label requires --project", file=sys.stderr)
            sys.exit(1)
        results = db.get_entities_by_label(args.project, args.label, limit=args.limit)
        result_type = 'entities'
        
    elif args.entity:
        if not args.project:
            safe_print("Error: --entity requires --project", file=sys.stderr)
            sys.exit(1)
        try:
            entity = db.get_entity_by_name(args.project, args.entity)
        except ValueError as e:
            # Ambiguous entity name - fail loudly with guidance
            safe_print(f"\n[ERROR] {e}", file=sys.stderr)
            safe_print(f"\nUse --entity-uuid instead of --entity to query by UUID.", file=sys.stderr)
            sys.exit(1)
        if entity:
            # Get facts about this entity
            facts = filter_entity_facts(
                db.get_entity_facts(entity['uuid']),
                direction=args.direction,
                relationship_type=args.type
            )
            if args.json:
                safe_print(json.dumps(make_json_safe({'entity': entity, 'facts': facts})))
            else:
                print_entity(entity, verbose=args.verbose)
                if facts:
                    safe_print(f"\n   Facts ({len(facts)}):")
                    for fact in facts:
                        safe_print(f"      [{fact['direction']}] {fact['fact']}")
                else:
                    safe_print(f"\n   No facts found")
            return
        else:
            safe_print(f"Entity '{args.entity}' not found", file=sys.stderr)
            safe_print(f"", file=sys.stderr)
            safe_print(f"Usage: --entity-file should contain entity NAME, not hash.", file=sys.stderr)
            safe_print(f"  Example: echo 'GraphDatabase' > tmp/entity.txt", file=sys.stderr)
            safe_print(f"  Then: python scripts/query_memory.py --project PROJECT --entity-file tmp/entity.txt", file=sys.stderr)
            safe_print(f"", file=sys.stderr)
            safe_print(f"For UUID lookup, use --entity-uuid:", file=sys.stderr)
            safe_print(f"  Example: python scripts/query_memory.py --project PROJECT --entity-uuid entity-abc123def456", file=sys.stderr)
            sys.exit(1)
            
    elif args.entity_uuid:
        if args.related:
            results = db.get_related_entities(
                args.entity_uuid,
                direction=args.direction,
                relationship_type=args.type,
                limit=args.limit
            )
            result_type = 'entities'
        else:
            entity = db.get_entity_by_uuid(args.entity_uuid)
            if entity:
                results = [entity]
                result_type = 'entities'
            else:
                safe_print(f"Entity '{args.entity_uuid}' not found", file=sys.stderr)
                safe_print(f"", file=sys.stderr)
                safe_print(f"Usage: --entity-uuid requires full UUID format.", file=sys.stderr)
                safe_print(f"  Example: python scripts/query_memory.py --project PROJECT --entity-uuid entity-abc123def456", file=sys.stderr)
                safe_print(f"", file=sys.stderr)
                safe_print(f"For name-based lookup, use --entity-file:", file=sys.stderr)
                safe_print(f"  Example: echo 'GraphDatabase' > tmp/entity.txt", file=sys.stderr)
                safe_print(f"  Then: python scripts/query_memory.py --project PROJECT --entity-file tmp/entity.txt", file=sys.stderr)
                sys.exit(1)
                
    elif args.facts:
        if not args.project:
            safe_print("Error: --facts requires --project", file=sys.stderr)
            sys.exit(1)
        results = db.search_facts(
            args.project,
            query=args.facts,
            relationship_type=args.type,
            limit=args.limit
        )
        result_type = 'facts'

    elif args.type:
        if not args.project:
            safe_print("Error: --type requires --project", file=sys.stderr)
            sys.exit(1)
        results = db.search_facts(
            args.project,
            relationship_type=args.type,
            limit=args.limit
        )
        result_type = 'facts'

    # Procedural memory queries
    elif args.procedures:
        if not args.project:
            safe_print("Error: --procedures requires --project", file=sys.stderr)
            sys.exit(1)
        include_all = getattr(args, 'include_deprecated', False)
        results = db.get_procedures(args.project, limit=args.limit, include_all_lifecycle=include_all)
        if args.json:
            safe_print(json.dumps(make_json_safe(results)))
        else:
            lifecycle_note = " (including deprecated)" if include_all else ""
            safe_print(f"\n[PROCEDURES] Found {len(results)} procedures{lifecycle_note}:")
            for proc in results:
                attrs = proc.get('attributes', {})
                if isinstance(attrs, str):
                    attrs = json.loads(attrs) if attrs else {}
                goal = attrs.get('goal', 'No goal specified')
                triggers = attrs.get('trigger_phrases', [])
                lifecycle = attrs.get('lifecycle_status', 'active')
                safe_print(f"\n   {proc['name']}")
                if lifecycle != 'active':
                    safe_print(f"      [LIFECYCLE: {lifecycle}]")
                safe_print(f"      Goal: {goal}")
                if triggers:
                    safe_print(f"      Triggers: {', '.join(triggers)}")
        return

    elif args.procedure:
        if not args.project:
            safe_print("Error: --procedure requires --project", file=sys.stderr)
            sys.exit(1)
        # Get the procedure (include all lifecycle to allow looking up deprecated for audit)
        include_all = getattr(args, 'include_deprecated', False)
        procs = db.get_procedures(args.project, query=args.procedure, limit=1, include_all_lifecycle=include_all)
        if not procs:
            # If not found with default filter, check if it exists but is deprecated
            all_procs = db.get_procedures(args.project, query=args.procedure, limit=1, include_all_lifecycle=True)
            if all_procs:
                lifecycle = all_procs[0].get('attributes', {})
                if isinstance(lifecycle, str):
                    lifecycle = json.loads(lifecycle) if lifecycle else {}
                lifecycle_status = lifecycle.get('lifecycle_status', 'active')
                safe_print(f"Procedure '{args.procedure}' is {lifecycle_status}. Use --include-deprecated to view.", file=sys.stderr)
            else:
                safe_print(f"Procedure '{args.procedure}' not found", file=sys.stderr)
            sys.exit(1)
        proc = procs[0]
        # Get its steps
        steps = db.get_procedure_steps(proc['name'], args.project)

        if args.json:
            safe_print(json.dumps(make_json_safe({'procedure': proc, 'steps': steps})))
        else:
            attrs = proc.get('attributes', {})
            if isinstance(attrs, str):
                attrs = json.loads(attrs) if attrs else {}
            lifecycle = attrs.get('lifecycle_status', 'active')
            safe_print(f"\n[PROCEDURE] {proc['name']}")
            if lifecycle != 'active':
                safe_print(f"   [LIFECYCLE: {lifecycle}]")
            safe_print(f"   Goal: {attrs.get('goal', 'No goal specified')}")
            triggers = attrs.get('trigger_phrases', [])
            if triggers:
                safe_print(f"   Triggers: {', '.join(triggers)}")
            prereqs = attrs.get('prerequisites', [])
            if prereqs:
                safe_print(f"   Prerequisites: {', '.join(prereqs)}")
            safe_print(f"\n   Steps ({len(steps)}):")
            for step in steps:
                step_attrs = step.get('attributes', {})
                if isinstance(step_attrs, str):
                    step_attrs = json.loads(step_attrs) if step_attrs else {}
                step_num = step_attrs.get('step_number', '?')
                action = step_attrs.get('action', step.get('summary', 'No action'))
                safe_print(f"      {step_num}. {action}")
                scripts = step_attrs.get('script_refs', [])
                if scripts:
                    safe_print(f"         Scripts: {', '.join(scripts)}")
        return

    elif args.search_procedures:
        if not args.project:
            safe_print("Error: --search-procedures requires --project", file=sys.stderr)
            sys.exit(1)
        include_all = getattr(args, 'include_deprecated', False)
        results = db.search_procedures_by_step(args.project, args.search_procedures, limit=args.limit, include_all_lifecycle=include_all)
        if args.json:
            safe_print(json.dumps(make_json_safe(results)))
        else:
            lifecycle_note = " (including deprecated)" if include_all else ""
            safe_print(f"\n[SEARCH] Found {len(results)} procedures containing '{args.search_procedures}'{lifecycle_note}:")
            for proc in results:
                attrs = proc.get('attributes', {})
                if isinstance(attrs, str):
                    attrs = json.loads(attrs) if attrs else {}
                lifecycle = attrs.get('lifecycle_status', 'active')
                lifecycle_marker = f" [{lifecycle}]" if lifecycle != 'active' else ""
                safe_print(f"   - {proc['name']}{lifecycle_marker}: {proc.get('summary', '')}")
        return

    else:
        parser.print_help()
        sys.exit(1)
    
    # Output results
    if args.json:
        safe_print(json.dumps(make_json_safe(results)))
    else:
        if result_type == 'entities':
            safe_print(f"\n[SEARCH] Found {len(results)} entities:")
            for entity in results:
                print_entity(entity, verbose=args.verbose)
        elif result_type == 'facts':
            safe_print(f"\n[SEARCH] Found {len(results)} facts:")
            for fact in results:
                print_fact(fact)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        safe_print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        safe_print(f"\n[ERROR] Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

