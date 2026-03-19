#!/usr/bin/env python3
"""
Pre-Commit Sync Validator

Validates that a recent semantic sync checkpoint exists before allowing commit.
Part of the Semantic Commit Tracking feature.

Exit codes:
    0 = Commit allowed (token + fresh timestamp)
    1 = Commit blocked (missing token or stale timestamp)

Usage (called by pre-commit hook):
    python scripts/precommit_sync_validator.py --project <project>
"""

import argparse
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tools.config import load_config

# Token file path (must match sync.py)
SYNC_TOKEN_FILE = "tmp/_____COMMIT_BLOCKED_UNTIL_SYNC_COMPLETES_____.tmp"

# Freshness window in minutes
FRESHNESS_WINDOW_MINUTES = 2.5


def print_blocked(project: str, reason: str):
    """Print blocked message in LLM-parseable format."""
    print("=" * 64)
    print("COMMIT BLOCKED: semantic sync required")
    print("=" * 64)
    print(f"Project: {project}")
    print(f"Reason: {reason}")
    print()
    print("ACTION REQUIRED:")
    print("  1. Run sync.md NOW (token will be auto-created)")
    print("  2. Commit IMMEDIATELY")
    print()
    print(f"WINDOW: You have {FRESHNESS_WINDOW_MINUTES} minutes from sync completion to commit.")
    print("        Do NOT add more work between sync and commit.")
    print()
    print("EMERGENCY FALLBACK (only if auto-create fails):")
    print(f"  Create: {SYNC_TOKEN_FILE}")
    print("=" * 64)


def validate_sync(project_name: str) -> tuple[bool, str]:
    """
    Validate that sync is fresh enough for commit.
    
    Returns:
        (is_valid, reason)
    """
    # Layer 1: Check token file exists
    token_path = Path(SYNC_TOKEN_FILE)
    if not token_path.exists():
        return False, "token file missing - run sync.md first"
    
    # Layer 2: Check graph timestamp
    try:
        from tools.graph_db import GraphDatabase
        config = load_config(project_name=project_name)
        graph_db = GraphDatabase(config.get_graph_db_path())
        
        latest_batch = graph_db.get_latest_valid_batch(project_name)
        graph_db.close()
        
        if latest_batch is None:
            return False, f"no sync history for project '{project_name}'"
        
        # Parse timestamp and check freshness
        created_at = latest_batch["created_at"]
        if isinstance(created_at, str):
            # Handle ISO format string
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        
        now = datetime.now(created_at.tzinfo) if created_at.tzinfo else datetime.now()
        age = now - created_at
        age_minutes = age.total_seconds() / 60
        
        if age_minutes > FRESHNESS_WINDOW_MINUTES:
            return False, f"sync too old ({age_minutes:.1f} min ago, max {FRESHNESS_WINDOW_MINUTES} min)"
        
        return True, f"sync fresh ({age_minutes:.1f} min ago)"
        
    except Exception as e:
        return False, f"error checking graph: {e}"


def main():
    parser = argparse.ArgumentParser(description="Pre-commit sync validator")
    parser.add_argument("--project", help="Project name (reads from mem.config.json if not specified)")
    
    args = parser.parse_args()
    
    # Get project name from config if not specified
    project_name = args.project
    if not project_name:
        try:
            config = load_config()
            project_name = config.get("project_name", "default")
        except Exception:
            print_blocked("unknown", "could not determine project name")
            sys.exit(1)
    
    # Validate
    is_valid, reason = validate_sync(project_name)
    
    if is_valid:
        # Delete token file on success
        token_path = Path(SYNC_TOKEN_FILE)
        if token_path.exists():
            token_path.unlink()
        print(f"[OK] Commit allowed - {reason}")
        sys.exit(0)
    else:
        print_blocked(project_name, reason)
        sys.exit(1)


if __name__ == "__main__":
    main()

