#!/usr/bin/env python3
"""
Consolidate legacy graph database paths into the canonical `.graph` extension.

This script:
1. Scans `memory/` for graph databases with `.graph`, `.kuzu`, and `.db`
2. Detects duplicate graph databases for the same project
3. Moves a single legacy database to the canonical `.graph` path when safe
4. Refuses to guess when multiple legacy databases exist for the same project

Usage:
    python scripts/consolidate_graph_db_paths.py --dry-run
    python scripts/consolidate_graph_db_paths.py --project llm_memory
    python scripts/consolidate_graph_db_paths.py --apply
    python scripts/consolidate_graph_db_paths.py --project llm_memory --prefer-largest --apply
    python scripts/consolidate_graph_db_paths.py --project llm_memory --prefer-ext kuzu --apply
"""

import argparse
import os
import shutil
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tools.config import load_config


# Note: .db is SQL database (SQLite), not a graph database extension
GRAPH_EXTENSIONS = ('.graph', '.kuzu')
SQL_FILENAMES = {'conversations.db', 'interactions.db'}


def path_size(path):
    """Get recursive size for a file or directory."""
    path_obj = Path(path)
    if not path_obj.exists():
        return 0
    if path_obj.is_file():
        return path_obj.stat().st_size
    return sum(p.stat().st_size for p in path_obj.rglob('*') if p.is_file())


def collect_graph_databases(memory_dir):
    """Collect graph database candidates by project name."""
    projects = defaultdict(list)
    for entry in Path(memory_dir).iterdir():
        if entry.name in SQL_FILENAMES:
            continue
        suffix = ''.join(entry.suffixes)
        if suffix not in GRAPH_EXTENSIONS:
            continue
        project_name = entry.name[:-len(suffix)] if suffix else entry.name
        projects[project_name].append({
            'path': str(entry),
            'suffix': suffix,
            'size': path_size(entry),
        })
    return projects


def canonical_path(memory_dir, project_name):
    """Return canonical graph path for a project."""
    return str(Path(memory_dir) / f'{project_name}.graph')


def move_path(src, dst):
    """Move a file or directory to destination, replacing empty destination only."""
    dst_path = Path(dst)
    src_path = Path(src)
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src_path), str(dst_path))


def choose_preferred_entry(entries, prefer_ext=None, prefer_largest=False):
    """Choose a preferred legacy entry when duplicates exist."""
    if prefer_ext:
        for item in entries:
            if item['suffix'] == f'.{prefer_ext}':
                return item
        return None

    if prefer_largest:
        return max(entries, key=lambda item: item['size'])

    return None


def main():
    parser = argparse.ArgumentParser(description='Consolidate graph database paths to .graph')
    parser.add_argument('--project', help='Limit to a single project')
    parser.add_argument('--dry-run', action='store_true', help='Show planned actions only')
    parser.add_argument('--apply', action='store_true', help='Apply changes')
    parser.add_argument('--prefer-ext', choices=['graph', 'kuzu'],
                        help='When duplicates exist, choose this extension as the source of truth')
    parser.add_argument('--prefer-largest', action='store_true',
                        help='When duplicates exist, choose the largest graph database')
    args = parser.parse_args()

    if args.dry_run and args.apply:
        print("[ERROR] Use either --dry-run or --apply, not both.", file=sys.stderr)
        sys.exit(1)

    apply_changes = args.apply and not args.dry_run

    config = load_config(project_name=args.project)
    memory_dir = config.get_memory_dir()

    if not os.path.exists(memory_dir):
        print(f"[ERROR] Memory directory not found: {memory_dir}", file=sys.stderr)
        sys.exit(1)

    projects = collect_graph_databases(memory_dir)
    if args.project:
        projects = {args.project: projects.get(args.project, [])}

    print("=" * 72)
    print("Consolidate Graph Database Paths")
    print("=" * 72)
    print(f"Memory directory: {memory_dir}")
    print(f"Mode: {'APPLY' if apply_changes else 'DRY RUN'}")

    errors = []
    actions = []

    for project_name, paths in sorted(projects.items()):
        if not paths:
            continue

        target = canonical_path(memory_dir, project_name)
        canonical_entries = [item for item in paths if item['suffix'] == '.graph']
        legacy_entries = [item for item in paths if item['suffix'] in ('.kuzu', '.db')]

        print(f"\nProject: {project_name}")
        for item in sorted(paths, key=lambda entry: entry['path']):
            print(f"  - {item['path']} ({item['size']:,} bytes)")

        if len(paths) == 1 and canonical_entries:
            print("  [OK] Already on canonical .graph path")
            continue

        if canonical_entries and legacy_entries:
            errors.append(
                f"{project_name}: canonical .graph exists alongside legacy paths"
            )
            print("  [ERROR] Canonical .graph exists alongside legacy paths; manual cleanup required")
            continue

        if len(legacy_entries) > 1:
            selected = choose_preferred_entry(
                legacy_entries,
                prefer_ext=args.prefer_ext,
                prefer_largest=args.prefer_largest
            )

            if not selected:
                errors.append(
                    f"{project_name}: multiple legacy graph databases exist ({', '.join(item['suffix'] for item in legacy_entries)})"
                )
                print("  [ERROR] Multiple legacy graph databases found; refusing to guess which to keep")
                continue

            actions.append((selected['path'], target))
            skipped = [item['path'] for item in legacy_entries if item['path'] != selected['path']]
            print(f"  [PLAN] Move {selected['path']} -> {target}")
            print("  [NOTE] Keep/remove manually after verification:")
            for path in skipped:
                print(f"    - {path}")
            continue

        if len(legacy_entries) == 1 and not canonical_entries:
            src = legacy_entries[0]['path']
            if legacy_entries[0]['suffix'] == '.db':
                errors.append(
                    f"{project_name}: lone .db file is ambiguous; inspect manually or rerun with --prefer-ext db"
                )
                print("  [ERROR] Lone .db file is ambiguous; refusing to treat it as a graph DB automatically")
                continue
            actions.append((src, target))
            print(f"  [PLAN] Move {src} -> {target}")
            continue

        errors.append(f"{project_name}: unhandled graph database state")
        print("  [ERROR] Unhandled graph database state")

    if errors:
        print("\nProblems detected:")
        for error in errors:
            print(f"  - {error}")

    if apply_changes and actions and not errors:
        for src, dst in actions:
            move_path(src, dst)
            print(f"[OK] Moved {src} -> {dst}")
    elif not actions and not errors:
        print("\n[OK] No consolidation needed.")

    if errors:
        print("\n[FAIL] Consolidation did not complete automatically.")
        sys.exit(1)

    print("\n[OK] Consolidation check complete.")


if __name__ == '__main__':
    main()
