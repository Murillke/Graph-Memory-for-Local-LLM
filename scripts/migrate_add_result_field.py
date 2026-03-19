#!/usr/bin/env python3
"""
Migration: Add result field to ExtractionBatch

This migration adds the 'result' column to the ExtractionBatch table
for existing databases. Sets default value to 'success' for existing records.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tools.config import load_config
import kuzu


def migrate(project_name: str):
    """Add result field to ExtractionBatch table."""
    config = load_config(project_name=project_name)
    db_path = config.get_graph_db_path()
    
    print(f"[INFO] Opening database: {db_path}")
    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    
    # Check if column exists
    try:
        result = conn.execute("""
            MATCH (b:ExtractionBatch)
            RETURN b.result
            LIMIT 1
        """)
        print("[INFO] Column 'result' already exists")
        return
    except Exception as e:
        if "Cannot find property result" not in str(e) and "Property result is not found" not in str(e):
            raise
        print(f"[INFO] Column does not exist, will add it")
    
    print("[INFO] Adding 'result' column to ExtractionBatch...")
    
    # Add column with default value
    try:
        conn.execute("""
            ALTER TABLE ExtractionBatch ADD result STRING DEFAULT 'success'
        """)
        print("[OK] Column added successfully")
    except Exception as e:
        print(f"[ERROR] Failed to add column: {e}")
        raise
    
    # Update existing records
    try:
        conn.execute("""
            MATCH (b:ExtractionBatch)
            WHERE b.result IS NULL
            SET b.result = 'success'
        """)
        print("[OK] Updated existing records with default value 'success'")
    except Exception as e:
        print(f"[WARNING] Could not update existing records: {e}")
    
    print("[OK] Migration complete")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Add result field to ExtractionBatch")
    parser.add_argument("--project", default="llm_memory", help="Project name")
    args = parser.parse_args()
    
    migrate(args.project)

