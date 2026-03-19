#!/usr/bin/env python3
"""
Clean up old temporary JSON files.

Removes conversation_*.json and extraction_*.json files older than configured days.

Usage:
    # Clean up files older than 30 days (default from config)
    python scripts/cleanup_temp_files.py

    # Clean up files older than 7 days
    python scripts/cleanup_temp_files.py --days 7

    # Dry run (show what would be deleted)
    python scripts/cleanup_temp_files.py --dry-run
"""

import sys
import os
import json
import argparse
from pathlib import Path
from datetime import datetime, timedelta


def cleanup_temp_files(tmp_dir='./tmp', keep_days=30, dry_run=False):
    """
    Clean up old temp files.
    
    Args:
        tmp_dir: Directory containing temp files
        keep_days: Keep files newer than this many days
        dry_run: If True, only show what would be deleted
    
    Returns:
        Number of files deleted
    """
    if not os.path.exists(tmp_dir):
        print(f"[INFO] Temp directory not found: {tmp_dir}")
        return 0
    
    # Calculate cutoff date
    cutoff_date = datetime.now() - timedelta(days=keep_days)
    
    print(f"{'='*60}")
    print(f"Cleaning up temp files older than {keep_days} days")
    print(f"Cutoff date: {cutoff_date.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    print()
    
    # Find temp files
    patterns = ['conversation_*.json', 'extraction_*.json']
    files_to_delete = []
    
    for pattern in patterns:
        for file_path in Path(tmp_dir).glob(pattern):
            # Get file modification time
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            
            if mtime < cutoff_date:
                files_to_delete.append((file_path, mtime))
    
    if not files_to_delete:
        print(f"[OK] No old temp files to clean up!")
        return 0
    
    # Sort by modification time
    files_to_delete.sort(key=lambda x: x[1])
    
    print(f"Found {len(files_to_delete)} files to clean up:")
    print()
    
    deleted_count = 0
    
    for file_path, mtime in files_to_delete:
        age_days = (datetime.now() - mtime).days
        
        if dry_run:
            print(f"[DRY RUN] Would delete: {file_path.name} (age: {age_days} days)")
        else:
            try:
                file_path.unlink()
                print(f"[DELETED] {file_path.name} (age: {age_days} days)")
                deleted_count += 1
            except Exception as e:
                print(f"[ERROR] Failed to delete {file_path.name}: {e}")
    
    print()
    print(f"{'='*60}")
    
    if dry_run:
        print(f"[DRY RUN] Would delete {len(files_to_delete)} files")
    else:
        print(f"[OK] Cleanup complete! Deleted {deleted_count} files")
        
        # Update last cleanup timestamp in config
        try:
            with open('mem.config.json', 'r') as f:
                config = json.load(f)
            
            if 'temp_file_cleanup' not in config:
                config['temp_file_cleanup'] = {}
            
            config['temp_file_cleanup']['last_cleanup_timestamp'] = datetime.now().isoformat()
            
            with open('mem.config.json', 'w') as f:
                json.dump(config, f, indent=2)
            
            print(f"[OK] Updated last_cleanup_timestamp in config")
        except Exception as e:
            print(f"[WARNING] Failed to update config: {e}")
    
    print(f"{'='*60}")
    
    return deleted_count


def main():
    parser = argparse.ArgumentParser(description="Clean up old temp files")
    parser.add_argument("--days", type=int, help="Keep files newer than this many days (default: from config)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without deleting")
    
    args = parser.parse_args()
    
    # Load config
    keep_days = args.days
    
    if keep_days is None:
        try:
            with open('mem.config.json', 'r') as f:
                config = json.load(f)
            keep_days = config.get('temp_file_cleanup', {}).get('keep_days', 30)
        except Exception:
            keep_days = 30
    
    # Run cleanup
    cleanup_temp_files(keep_days=keep_days, dry_run=args.dry_run)


if __name__ == "__main__":
    main()

