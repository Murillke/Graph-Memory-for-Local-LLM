#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Recall - Time-Aware Memory Query

Query entities from specific time periods with hour-level precision.
Like remembering what you knew at a specific point in time!

Features:
    - Hour-level precision (YYYY-MM-DDTHH:MM:SS)
    - Timestamps shown by default
    - Configurable entity limit
    - Focus on specific entities

Usage:
    # Query by date range
    python scripts/recall.py --project llm_memory --start 2026-03-03 --end 2026-03-06

    # Query by date + time (hour-level precision)
    python scripts/recall.py --project llm_memory --start 2026-03-06T00:00:00 --end 2026-03-06T02:00:00

    # Hide timestamps (shown by default)
    python scripts/recall.py --project llm_memory --start 2026-03-06 --end 2026-03-06 --hide-time

    # Show more entities (default: 50)
    python scripts/recall.py --project llm_memory --start 2026-03-06 --end 2026-03-06 --limit 100

    # Focus on specific entity
    python scripts/recall.py --project llm_memory --start 2026-03-03 --end 2026-03-06 --entity-file tmp/entity.txt
"""
import sys
import os
import argparse
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class RecallArgumentError(Exception):
    """Raised when recall arguments are invalid, triggers fallback behavior."""
    pass

from tools.console_utils import safe_print, setup_console_encoding
from tools.config import load_config
from tools.db_utils import open_kuzu_database
from tools.sql_db import SQLDatabase, get_task_event_display_label, get_task_short_hash

# Setup console encoding for Windows
setup_console_encoding()


RECALL_EXAMPLES = """Examples:
  Query by date range:
    python scripts/recall.py --project llm_memory --start 2026-03-03 --end 2026-03-06

  Query by date + time (hour-level precision):
    python scripts/recall.py --project llm_memory --start 2026-03-06T00:00:00 --end 2026-03-06T02:00:00

  Focus on a specific entity:
    python scripts/recall.py --project llm_memory --start 2026-03-03 --end 2026-03-06 --entity-file tmp/entity.txt

  Last 4 hours (if current time is 4:00 PM on March 13):
    # Run Get-Date first, then calculate: 4:00 PM - 4 hours = 12:00 PM
    .\\python313\\python.exe scripts\\recall.py --project llm_memory --start 2026-03-13T12:00:00 --end 2026-03-13T16:00:00
"""


class RecallArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        safe_print(f"{self.prog}: error: {message}\n\n{RECALL_EXAMPLES}", file=sys.stderr)
        # Don't exit - raise exception so we can show fallback results
        raise RecallArgumentError(message)


def build_parser():
    parser = RecallArgumentParser(
        description='Time-aware memory query - recall what you knew at a specific time',
        epilog=RECALL_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--project', required=True, help='Project name')
    parser.add_argument(
        '--start',
        required=True,
        help='Start date/time (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)'
    )
    parser.add_argument(
        '--end',
        required=True,
        help='End date/time (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)'
    )
    parser.add_argument('--entity', help='Deprecated direct entity name (use --entity-file)')
    parser.add_argument('--entity-file', help='File containing entity name (workflow standard)')
    parser.add_argument('--graph-db', help='Path to graph database (overrides config)')
    parser.add_argument('--limit', type=int, default=50, help='Max entities to show per day (default: 50)')
    parser.add_argument('--hide-time', action='store_true', help='Hide timestamps (shown by default)')
    parser.add_argument('--hide-task-activity', action='store_true', help='Hide task activity section for the recall window')
    return parser


def normalize_recall_time(value: str, *, is_end: bool) -> str:
    """Return an inclusive ISO timestamp for recall queries."""
    return value if 'T' in value else f"{value}T23:59:59" if is_end else f"{value}T00:00:00"


def get_last_entity_timestamp(conn, project_name: str) -> str:
    """Get the timestamp of the most recently added entity."""
    result = conn.execute("""
        MATCH (p:Project {name: $project_name})-[:HAS_ENTITY]->(e:Entity)
        RETURN e.extraction_timestamp_str
        ORDER BY e.extraction_timestamp_str DESC
        LIMIT 1
    """, {"project_name": project_name})

    if result.has_next():
        return str(result.get_next()[0])
    return None


def run_fallback_recall(project_name: str, graph_db_path: str = None, hours: int = 4):
    """Run a fallback recall showing last N hours since the most recent entity."""
    config = load_config(project_name=project_name, cli_args={"graph_db": graph_db_path})
    graph_path = graph_db_path or config.get_graph_db_path(project_name)

    db, conn = open_kuzu_database(graph_path)

    last_ts = get_last_entity_timestamp(conn, project_name)
    if not last_ts:
        safe_print("\n" + "="*80)
        safe_print("FALLBACK RECALL - No entities found in database")
        safe_print("="*80)
        return

    # Parse the timestamp and calculate range
    try:
        if 'T' in last_ts:
            end_dt = datetime.fromisoformat(last_ts.replace('Z', ''))
        else:
            end_dt = datetime.fromisoformat(last_ts)
    except ValueError:
        end_dt = datetime.utcnow()

    start_dt = end_dt - timedelta(hours=hours)

    start_time = start_dt.strftime("%Y-%m-%dT%H:%M:%S")
    end_time = end_dt.strftime("%Y-%m-%dT%H:%M:%S")

    safe_print("\n" + "="*80)
    safe_print("FALLBACK RECALL - Showing last {} hours of memories".format(hours))
    safe_print("="*80)
    safe_print(f"\nAuto-detected range: {start_time} to {end_time}")
    safe_print(f"(Based on most recent entity at {last_ts})\n")

    total_entities = get_total_entity_count(conn, project_name, start_time, end_time)
    entities_by_day = collect_entities(conn, project_name, start_time, end_time)
    print_entities_by_day(
        entities_by_day,
        limit=50,
        hide_time=False,
        total_count=total_entities,
    )

    # Summary
    safe_print(f"\n\n{'='*80}")
    safe_print("📊 FALLBACK SUMMARY")
    safe_print(f"{'='*80}")
    total_shown = sum(len(entities) for entities in entities_by_day.values())
    safe_print(f"Total entities in last {hours} hours: {total_shown}")
    safe_print(f"Days with activity: {len(entities_by_day)}")


def collect_entities(conn, project_name: str, start_time: str, end_time: str):
    """Return entities grouped by day for the requested window, newest first."""
    result = conn.execute("""
        MATCH (p:Project {name: $project_name})-[:HAS_ENTITY]->(e:Entity)
        WHERE e.extraction_timestamp_str >= $start_time
          AND e.extraction_timestamp_str <= $end_time
        RETURN e.name, e.extraction_timestamp_str, e.summary
        ORDER BY e.extraction_timestamp_str DESC
    """, {
        "project_name": project_name,
        "start_time": start_time,
        "end_time": end_time,
    })

    entities_by_day = {}
    while result.has_next():
        row = result.get_next()
        name = row[0]
        created_at = str(row[1])
        summary = row[2] if len(row) > 2 else ""
        date = created_at.split('T')[0] if 'T' in created_at else created_at.split()[0]
        entities_by_day.setdefault(date, []).append({
            'name': name,
            'created_at': created_at,
            'summary': summary,
        })
    return entities_by_day


def get_total_entity_count(conn, project_name: str, start_time: str, end_time: str) -> int:
    """Return total entity count for the recall window."""
    result = conn.execute("""
        MATCH (p:Project {name: $project_name})-[:HAS_ENTITY]->(e:Entity)
        WHERE e.extraction_timestamp_str >= $start_time
          AND e.extraction_timestamp_str <= $end_time
        RETURN count(e)
    """, {
        "project_name": project_name,
        "start_time": start_time,
        "end_time": end_time,
    })
    return result.get_next()[0] if result.has_next() else 0


def print_entities_by_day(entities_by_day, *, limit: int, hide_time: bool, total_count: int):
    """Render recall entities grouped by day, newest day first."""
    shown_total = 0
    for date in sorted(entities_by_day.keys(), reverse=True):
        safe_print(f"\n{'='*80}")
        safe_print(f"📅 {date} - {len(entities_by_day[date])} entities")
        safe_print(f"{'='*80}")

        shown_for_day = min(len(entities_by_day[date]), limit)
        shown_total += shown_for_day
        for i, entity in enumerate(entities_by_day[date][:limit], 1):
            safe_print(f"\n{i}. {entity['name']}")
            if not hide_time:
                safe_print(f"   ⏰ {entity['created_at']}")
            if entity['summary']:
                safe_print(f"   {entity['summary'][:100]}...")

        if len(entities_by_day[date]) > limit:
            safe_print(f"\n   ... and {len(entities_by_day[date]) - limit} more entities (use --limit to see more)")

    safe_print(f"\nShowing {shown_total} of {total_count} entities in window (per-day limit: {limit})")
    if shown_total < total_count:
        safe_print("Recall output was truncated. Increase --limit to see more entities.")


def print_task_activity(project_name: str, start_time: str, end_time: str):
    """Render task activity for the recall window. Returns event count."""
    config = load_config(project_name=project_name)
    sql_db = SQLDatabase(config.get_sql_db_path())
    operations = sql_db.get_task_operations(project_name=project_name, start=start_time, end=end_time)
    if not operations:
        return 0

    safe_print(f"\n\n{'='*80}")
    safe_print("TASK ACTIVITY")
    safe_print(f"{'='*80}")

    shown = 0
    for row in operations[:20]:
        label = get_task_event_display_label(row)
        short_hash = get_task_short_hash(row.get("task_uuid"))
        hash_str = f" [{short_hash}]" if short_hash else ""
        safe_print("")
        safe_print(str(row.get("created_at", "")))
        safe_print(f"  {label}{hash_str} {row.get('task_name', '(unknown)')}")
        shown += 1

    if len(operations) > shown:
        safe_print(f"\n... and {len(operations) - shown} more task events")

    return len(operations)


def main(argv=None):
    raw_argv = argv if argv is not None else sys.argv[1:]
    parser = build_parser()

    try:
        args = parser.parse_args(raw_argv)
    except RecallArgumentError:
        # Argument parsing failed - run fallback recall
        # Try to extract project name from args
        project_name = None
        graph_db = None
        for i, arg in enumerate(raw_argv):
            if arg == '--project' and i + 1 < len(raw_argv):
                project_name = raw_argv[i + 1]
            elif arg == '--graph-db' and i + 1 < len(raw_argv):
                graph_db = raw_argv[i + 1]

        if project_name:
            run_fallback_recall(project_name, graph_db, hours=4)
        else:
            safe_print("\n[FALLBACK] Could not run fallback - no --project specified", file=sys.stderr)

        return 2  # Still return error code so LLMs know args were wrong

    # Prefer helper-file input for deterministic workflows.
    entity_name = args.entity
    if args.entity_file:
        if args.entity:
            safe_print("[WARNING] Both --entity and --entity-file were provided; using --entity-file.", file=sys.stderr)
        with open(args.entity_file, 'r', encoding='utf-8') as f:
            entity_name = f.read().strip()
        if not entity_name:
            parser.error(f"Entity helper file is empty: {args.entity_file}")
    elif '--entity' in raw_argv:
        if os.getenv("MEM_ALLOW_DIRECT_INPUT") != "1":
            parser.error("Direct --entity is disabled by default. Use --entity-file tmp/entity.txt. Set MEM_ALLOW_DIRECT_INPUT=1 only for legacy/manual compatibility.")
        safe_print(
            "[WARNING] --entity is allowed only because MEM_ALLOW_DIRECT_INPUT=1 is set. Prefer --entity-file tmp/entity.txt.",
            file=sys.stderr,
        )

    # Update args.entity with file content if provided
    if entity_name:
        args.entity = entity_name
    
    config = load_config(project_name=args.project, cli_args={"graph_db": args.graph_db})
    graph_path = args.graph_db or config.get_graph_db_path(args.project)
    
    # Connect to database
    db, conn = open_kuzu_database(graph_path)
    
    safe_print("="*80)
    safe_print("RECALL - Time-Aware Memory Query")
    safe_print("="*80)
    safe_print(f"\nQuerying knowledge from {args.start} to {args.end}...\n")

    # Normalize time strings (add T00:00:00 if only date provided)
    start_time = normalize_recall_time(args.start, is_end=False)
    end_time = normalize_recall_time(args.end, is_end=True)
    total_entities = get_total_entity_count(conn, args.project, start_time, end_time)
    entities_by_day = collect_entities(conn, args.project, start_time, end_time)
    print_entities_by_day(
        entities_by_day,
        limit=args.limit,
        hide_time=args.hide_time,
        total_count=total_entities,
    )
    
    # If specific entity requested, show its relationships
    if args.entity:
        safe_print(f"\n\n{'='*80}")
        safe_print(f"🕸️  RELATIONSHIPS - {args.entity}")
        safe_print(f"{'='*80}")
        
        # Get outgoing relationships
        result = conn.execute("""
            MATCH (e:Entity {name: $entity_name})-[r:RELATES_TO]->(target:Entity)
            RETURN r.name, target.name, r.fact
            LIMIT 10
        """, {
            "entity_name": args.entity,
        })
        
        outgoing = []
        while result.has_next():
            row = result.get_next()
            rel_type = row[0]
            target_name = row[1]
            fact = row[2] if len(row) > 2 else ""
            outgoing.append((rel_type, target_name, fact))
        
        # Get incoming relationships
        result = conn.execute("""
            MATCH (source:Entity)-[r:RELATES_TO]->(e:Entity {name: $entity_name})
            RETURN r.name, source.name, r.fact
            LIMIT 10
        """, {
            "entity_name": args.entity,
        })
        
        incoming = []
        while result.has_next():
            row = result.get_next()
            rel_type = row[0]
            source_name = row[1]
            fact = row[2] if len(row) > 2 else ""
            incoming.append((rel_type, source_name, fact))
        
        # Display
        if outgoing:
            safe_print(f"\n  Outgoing connections ({len(outgoing)}):")
            for rel_type, target, fact in outgoing:
                safe_print(f"    → {rel_type} → {target}")
                if fact:
                    safe_print(f"      \"{fact[:80]}...\"")
        
        if incoming:
            safe_print(f"\n  Incoming connections ({len(incoming)}):")
            for rel_type, source, fact in incoming:
                safe_print(f"    ← {rel_type} ← {source}")
                if fact:
                    safe_print(f"      \"{fact[:80]}...\"")
        
        if not outgoing and not incoming:
            safe_print("    (No relationships found)")
    
    task_event_count = 0
    if not args.hide_task_activity:
        task_event_count = print_task_activity(args.project, start_time, end_time)

    # Summary
    safe_print(f"\n\n{'='*80}")
    safe_print("📊 SUMMARY")
    safe_print(f"{'='*80}")
    total_entities = sum(len(entities) for entities in entities_by_day.values())
    safe_print(f"Total entities from {args.start} to {args.end}: {total_entities}")
    safe_print(f"Days with activity: {len(entities_by_day)}")
    for date in sorted(entities_by_day.keys()):
        safe_print(f"  {date}: {len(entities_by_day[date])} entities")
    if not args.hide_task_activity:
        safe_print(f"Task events in window: {task_event_count}")


if __name__ == "__main__":
    sys.exit(main())
