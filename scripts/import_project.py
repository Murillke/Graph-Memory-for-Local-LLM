"""
Import entire project from another database.

STATUS: PARTIAL IMPLEMENTATION
  - --list: WORKING (list projects in source database)
  - --check: WORKING (check for conflicts)
  - --import: NOT YET IMPLEMENTED
"""

import argparse
import sqlite3
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.config import load_config
from tools.graph_db import GraphDatabase
from tools.console_utils import safe_print


IMPORT_EXAMPLES = """
Examples:
  # List projects in source database
  python scripts/import_project.py --source-sql /path/to/interactions.db --source-graph /path/to/knowledge.kuzu --list

  # Check for conflicts before importing
  python scripts/import_project.py --source-sql /path/to/interactions.db --source-graph /path/to/knowledge.kuzu --project my_project --check

Status:
  IMPLEMENTED: --list, --check
  NOT YET IMPLEMENTED: --import (exits with error)
"""


class ImportArgumentParser(argparse.ArgumentParser):
    """Custom parser that prints examples on error."""
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: error: {message}\n{IMPORT_EXAMPLES}")


def list_projects(sql_db_path: str, graph_db_path: str):
    """
    List all projects in source database.
    """
    # Validate paths
    if not Path(sql_db_path).exists():
        safe_print(f"[ERROR] Source SQL database not found: {sql_db_path}")
        sys.exit(1)
    if not Path(graph_db_path).exists():
        safe_print(f"[ERROR] Source graph database not found: {graph_db_path}")
        sys.exit(1)

    # Get projects from SQL
    sql_conn = sqlite3.connect(sql_db_path)
    cursor = sql_conn.cursor()

    # Check if projects table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='projects'")
    if not cursor.fetchone():
        safe_print(f"[ERROR] No 'projects' table found in source database")
        sql_conn.close()
        sys.exit(1)

    cursor.execute("SELECT name, description, created_at FROM projects")
    projects = cursor.fetchall()

    if not projects:
        safe_print(f"\n[INFO] No projects found in source database")
        sql_conn.close()
        return

    safe_print(f"\n[PROJECTS FOUND]")

    # Open graph database once
    graph_db = GraphDatabase(graph_db_path)

    for project in projects:
        name, description, created_at = project

        # Get interaction count
        cursor.execute("SELECT COUNT(*) FROM interactions WHERE project_name = ?", (name,))
        interaction_count = cursor.fetchone()[0]

        # Get entity count from graph
        try:
            entities = graph_db.get_all_entities(name, limit=100000)
            entity_count = len(entities)
        except Exception:
            entity_count = "N/A"

        safe_print(f"\n  {name}")
        safe_print(f"    Description: {description or 'N/A'}")
        safe_print(f"    Interactions: {interaction_count}")
        safe_print(f"    Entities: {entity_count}")
        safe_print(f"    Created: {created_at}")

    sql_conn.close()
    safe_print(f"\n[ACTION] Choose project to import with --project flag\n")


def check_conflict(project_name: str, current_sql_path: str, current_graph_path: str,
                   source_sql_path: str, source_graph_path: str):
    """
    Check if project already exists in current database and verify source project exists.
    """
    # Validate source paths
    if not Path(source_sql_path).exists():
        safe_print(f"[ERROR] Source SQL database not found: {source_sql_path}")
        sys.exit(1)
    if not Path(source_graph_path).exists():
        safe_print(f"[ERROR] Source graph database not found: {source_graph_path}")
        sys.exit(1)

    # Check source project exists
    source_sql = sqlite3.connect(source_sql_path)
    source_cursor = source_sql.cursor()
    source_cursor.execute("SELECT COUNT(*) FROM projects WHERE name = ?", (project_name,))
    source_exists = source_cursor.fetchone()[0] > 0

    if not source_exists:
        safe_print(f"[ERROR] Project '{project_name}' not found in source database")
        safe_print(f"[HINT] Use --list to see available projects")
        source_sql.close()
        sys.exit(1)

    # Get source stats
    source_cursor.execute("SELECT COUNT(*) FROM interactions WHERE project_name = ?", (project_name,))
    source_interactions = source_cursor.fetchone()[0]
    source_sql.close()

    source_graph = GraphDatabase(source_graph_path)
    try:
        entities = source_graph.get_all_entities(project_name, limit=100000)
        source_entities = len(entities)
    except Exception:
        source_entities = "N/A"

    # Check current database
    current_sql = sqlite3.connect(current_sql_path)
    cursor = current_sql.cursor()
    cursor.execute("SELECT COUNT(*) FROM projects WHERE name = ?", (project_name,))
    exists = cursor.fetchone()[0] > 0

    if not exists:
        safe_print(f"\n[OK] Project '{project_name}' does not exist in current database")
        safe_print(f"[OK] Safe to import")
        safe_print(f"\n[SOURCE PROJECT]")
        safe_print(f"  Interactions: {source_interactions}")
        safe_print(f"  Entities: {source_entities}")
        safe_print(f"\n[NOTE] --import is not yet implemented")
        current_sql.close()
        return

    # Project exists - show details
    safe_print(f"\n[WARNING] Project '{project_name}' already exists in current database!")

    # Current stats
    cursor.execute("SELECT COUNT(*) FROM interactions WHERE project_name = ?", (project_name,))
    current_interactions = cursor.fetchone()[0]

    current_graph = GraphDatabase(current_graph_path)
    try:
        entities = current_graph.get_all_entities(project_name, limit=100000)
        current_entities = len(entities)
    except Exception:
        current_entities = "N/A"

    safe_print(f"\n[CURRENT DATABASE]")
    safe_print(f"  Interactions: {current_interactions}")
    safe_print(f"  Entities: {current_entities}")

    safe_print(f"\n[SOURCE DATABASE]")
    safe_print(f"  Interactions: {source_interactions}")
    safe_print(f"  Entities: {source_entities}")

    safe_print(f"\n[OPTIONS] (when --import is implemented)")
    safe_print(f"  Import with different name: --rename new-name")

    current_sql.close()


def main():
    parser = ImportArgumentParser(
        description="Import project from another database",
        epilog=IMPORT_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--source-sql", required=True, help="Source SQL database path")
    parser.add_argument("--source-graph", required=True, help="Source graph database path")
    parser.add_argument("--project", help="Project name to import")
    parser.add_argument("--list", action="store_true", help="[WORKING] List projects in source database")
    parser.add_argument("--check", action="store_true", help="[WORKING] Check for conflicts")
    parser.add_argument("--import", dest="do_import", action="store_true", help="[NOT IMPLEMENTED] Execute import")
    parser.add_argument("--sql-db", help="Current SQL database path (overrides config)")
    parser.add_argument("--graph-db", help="Current graph database path (overrides config)")

    args = parser.parse_args()

    try:
        if args.list:
            list_projects(args.source_sql, args.source_graph)
            return

        if not args.project:
            safe_print(f"[ERROR] --project required (use --list to see available projects)")
            sys.exit(1)

        # Load config for current database
        config = load_config(project_name=args.project, cli_args={
            "sql_db": args.sql_db,
            "graph_db": args.graph_db
        })

        current_sql_path = config.get_sql_db_path()
        current_graph_path = config.get_graph_db_path()

        if args.check:
            check_conflict(args.project, current_sql_path, current_graph_path,
                          args.source_sql, args.source_graph)

        elif args.do_import:
            safe_print(f"[ERROR] --import is not yet implemented")
            safe_print(f"")
            safe_print(f"Currently supported:")
            safe_print(f"  --list   List projects in source database")
            safe_print(f"  --check  Check for conflicts before importing")
            safe_print(f"")
            safe_print(f"Not yet implemented:")
            safe_print(f"  --import  Execute the actual import")
            sys.exit(1)

        else:
            safe_print(f"[ERROR] Must specify --list, --check, or --import")
            sys.exit(1)

    except Exception as e:
        safe_print(f"[ERROR] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

