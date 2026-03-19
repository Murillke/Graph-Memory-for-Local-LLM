#!/usr/bin/env python3
"""
Migration: Add task-specific fields to Entity table.

Adds:
- priority STRING (high, medium, low)
- status STRING (pending, complete, invalid)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.graph_db import GraphDatabase
import argparse


def migrate(project_name: str):
    """Add task fields to Entity table."""
    
    db_path = f"./memory/{project_name}.kuzu"
    print(f"Migrating database: {db_path}")
    
    db = GraphDatabase(db_path)
    
    try:
        # Add priority column
        print("Adding 'priority' column...")
        try:
            db.conn.execute("ALTER TABLE Entity ADD priority STRING")
            print("  OK Added priority column")
        except Exception as e:
            if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                print("  - Column already exists, skipping")
            else:
                print(f"  ! Error: {e}")

        # Add status column
        print("Adding 'status' column...")
        try:
            db.conn.execute("ALTER TABLE Entity ADD status STRING")
            print("  OK Added status column")
        except Exception as e:
            if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                print("  - Column already exists, skipping")
            else:
                print(f"  ! Error: {e}")

        print("\nOK Migration complete!")
        
    except Exception as e:
        print(f"\nERROR Migration failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add task fields to Entity table")
    parser.add_argument("--project", required=True, help="Project name")
    
    args = parser.parse_args()
    migrate(args.project)

