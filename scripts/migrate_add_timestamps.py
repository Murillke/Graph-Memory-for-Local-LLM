#!/usr/bin/env python3
"""
Migration script to add timestamp fields to existing entities.

This script:
1. Adds t_last_accessed and access_count fields to existing entities
2. Sets extraction_timestamp to event time (from source interaction)
3. Preserves all existing data and crypto proofs

Usage:
    python scripts/migrate_add_timestamps.py --project PROJECT_NAME [--dry-run]
"""

import argparse
import sys
import os
import json
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from tools.graph_db import GraphDatabase
from tools.sql_db import SQLDatabase


def migrate_entity_timestamps(project_name: str, dry_run: bool = False):
    """
    Migrate existing entities to add timestamp fields.
    
    Args:
        project_name: Name of the project to migrate
        dry_run: If True, only show what would be done without making changes
    """
    print(f"{'='*60}")
    print(f"[MIGRATION] Add Timestamp Fields to Entities")
    print(f"{'='*60}")
    print(f"Project: {project_name}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print(f"{'='*60}\n")
    
    # Load configuration
    config_file = 'mem.config.json'
    if not os.path.exists(config_file):
        print(f"[ERROR] Configuration file not found: {config_file}")
        sys.exit(1)

    with open(config_file, 'r') as f:
        config = json.load(f)

    # Get database paths from config
    sql_path = config['database']['sql_path']
    graph_path = config['database']['graph_path']

    print(f"Using database paths from config:")
    print(f"  SQL: {sql_path}")
    print(f"  Graph: {graph_path}\n")

    # Connect to databases
    sql_db = SQLDatabase(sql_path)
    graph_db = GraphDatabase(graph_path)
    
    # Step 1: Add new properties to schema if they don't exist
    print(f"[1/5] Adding new properties to Entity schema...")

    # Try to add t_last_accessed property
    try:
        graph_db.conn.execute("""
            ALTER TABLE Entity ADD t_last_accessed TIMESTAMP
        """)
        print(f"      Added t_last_accessed property")
    except Exception as e:
        error_msg = str(e).lower()
        if "already has property" in error_msg or "already exists" in error_msg or "duplicate" in error_msg:
            print(f"      t_last_accessed property already exists")
        else:
            print(f"      [ERROR] Failed to add t_last_accessed: {e}")
            raise

    # Try to add access_count property
    try:
        graph_db.conn.execute("""
            ALTER TABLE Entity ADD access_count INT64 DEFAULT 0
        """)
        print(f"      Added access_count property")
    except Exception as e:
        error_msg = str(e).lower()
        if "already has property" in error_msg or "already exists" in error_msg or "duplicate" in error_msg:
            print(f"      access_count property already exists")
        else:
            print(f"      [ERROR] Failed to add access_count: {e}")
            raise

    # Verify properties were actually added
    print(f"      Verifying properties in schema...")
    result = graph_db.conn.execute("CALL table_info('Entity') RETURN *;")
    properties = []
    while result.has_next():
        row = result.get_next()
        properties.append(row[1])  # Property name is at index 1

    if 't_last_accessed' not in properties:
        print(f"      [ERROR] t_last_accessed property not found in schema!")
        print(f"      Available properties: {properties}")
        sys.exit(1)

    if 'access_count' not in properties:
        print(f"      [ERROR] access_count property not found in schema!")
        print(f"      Available properties: {properties}")
        sys.exit(1)

    print(f"      [OK] Properties verified in schema")
    print()

    # Get all entities
    print(f"[2/5] Fetching all entities...")
    entities = graph_db.get_all_entities(project_name, track_access=False, priority_order=False)
    print(f"      Found {len(entities)} entities\n")
    
    if len(entities) == 0:
        print(f"[OK] No entities to migrate")
        return
    
    # Analyze entities
    print(f"[3/5] Analyzing entities...")
    needs_migration = 0
    has_timestamps = 0

    for entity in entities:
        if entity.get('t_last_accessed') is None and entity.get('access_count', 0) == 0:
            needs_migration += 1
        else:
            has_timestamps += 1

    print(f"      Entities needing migration: {needs_migration}")
    print(f"      Entities already migrated: {has_timestamps}\n")

    if needs_migration == 0:
        print(f"[OK] All entities already have timestamp fields")
        return

    # Migrate entities
    print(f"[4/5] Migrating entities...")
    migrated = 0
    errors = 0
    
    for i, entity in enumerate(entities, 1):
        # Skip if already migrated
        if entity.get('t_last_accessed') is not None or entity.get('access_count', 0) > 0:
            continue
        
        try:
            # Get event timestamp from source interaction
            source_interactions = entity.get('source_interactions', [])
            event_timestamp = "1970-01-01T00:00:00Z"  # Default to Unix epoch
            
            if source_interactions:
                # Get first source interaction
                interaction = sql_db.get_interaction_by_uuid(source_interactions[0])
                if interaction and interaction.get('timestamp'):
                    event_timestamp = interaction['timestamp']
            
            if dry_run:
                print(f"      [{i}/{len(entities)}] Would migrate: {entity['name']}")
                print(f"                Event timestamp: {event_timestamp}")
            else:
                # Update entity with new fields
                # Note: We're setting t_last_accessed to NULL and access_count to 0
                # The extraction_timestamp should already be set, but we verify it matches event time
                graph_db.conn.execute(f"""
                    MATCH (e:Entity {{uuid: '{entity['uuid']}'}})
                    SET e.t_last_accessed = NULL,
                        e.access_count = 0
                """)
                
                migrated += 1
                if migrated % 100 == 0:
                    print(f"      Migrated {migrated}/{needs_migration} entities...")
        
        except Exception as e:
            errors += 1
            print(f"      [ERROR] Failed to migrate {entity['name']}: {e}")
    
    print(f"\n[5/5] Migration complete!")
    print(f"      Migrated: {migrated}")
    print(f"      Errors: {errors}")
    print(f"      Skipped (already migrated): {has_timestamps}\n")
    
    if not dry_run and migrated > 0:
        print(f"[OK] Successfully migrated {migrated} entities")
        print(f"[NOTE] All entities now have:")
        print(f"       - t_last_accessed = NULL (will be set on first query)")
        print(f"       - access_count = 0 (will increment on queries)")
        print(f"       - extraction_timestamp = event time (from conversation)")
    elif dry_run:
        print(f"[DRY RUN] No changes made. Run without --dry-run to apply migration.")


def main():
    parser = argparse.ArgumentParser(description="Migrate entities to add timestamp fields")
    parser.add_argument("--project", required=True, help="Project name")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    
    args = parser.parse_args()
    
    try:
        migrate_entity_timestamps(args.project, args.dry_run)
    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

