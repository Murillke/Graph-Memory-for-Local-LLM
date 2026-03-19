#!/usr/bin/env python3
"""
Install Pre-Commit Sync Gate Hook

Installs a git pre-commit hook that blocks commits unless a recent
semantic sync checkpoint exists.

Part of the Semantic Commit Tracking feature.

Usage:
    python scripts/install_precommit_hook.py
    python scripts/install_precommit_hook.py --force  # Overwrite existing
"""

import argparse
import os
import stat
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tools.config import load_config


HOOK_CONTENT = '''#!/bin/sh
# Pre-Commit Sync Gate - Part of Semantic Commit Tracking
# This hook blocks commits unless a recent semantic sync checkpoint exists.
#
# To bypass (UNSUPPORTED - workflow violation):
#   git commit --no-verify
#
# To unblock properly:
#   1. Run sync.md
#   2. Commit immediately (within 2.5 minutes)

# Get the directory where this hook is located
HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$HOOK_DIR/../.." && pwd)"

# Change to repo root
cd "$REPO_ROOT"

# Run validator (path quoted for spaces)
"{python_path}" scripts/precommit_sync_validator.py

# Exit with validator's exit code
exit $?
'''


def get_git_hooks_dir() -> Path:
    """Find the .git/hooks directory."""
    # Try current directory first
    git_dir = Path(".git")
    if not git_dir.exists():
        # Try parent directories
        cwd = Path.cwd()
        for parent in [cwd] + list(cwd.parents):
            git_dir = parent / ".git"
            if git_dir.exists():
                break
        else:
            return None
    
    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)
    return hooks_dir


def install_hook(force: bool = False):
    """Install the pre-commit hook."""
    hooks_dir = get_git_hooks_dir()
    if hooks_dir is None:
        print("[ERROR] Not a git repository (no .git directory found)")
        sys.exit(1)
    
    hook_path = hooks_dir / "pre-commit"
    
    # Check if hook already exists
    if hook_path.exists() and not force:
        print(f"[ERROR] Pre-commit hook already exists: {hook_path}")
        print("        Use --force to overwrite")
        sys.exit(1)
    
    # Get python path from config
    try:
        config = load_config()
        python_path = config.get_python_path()
    except Exception:
        python_path = "python3"
    
    # Write hook
    hook_content = HOOK_CONTENT.format(python_path=python_path)
    hook_path.write_text(hook_content)
    
    # Make executable (Unix)
    if os.name != 'nt':
        hook_path.chmod(hook_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    
    print(f"[OK] Pre-commit hook installed: {hook_path}")
    print()
    print("The hook will block commits unless:")
    print("  1. Sync token file exists")
    print("  2. Last ExtractionBatch is within 2.5 minutes")
    print()
    print("To unblock: run sync.md, then commit immediately")


def main():
    parser = argparse.ArgumentParser(description="Install pre-commit sync gate hook")
    parser.add_argument("--force", action="store_true", help="Overwrite existing hook")
    
    args = parser.parse_args()
    install_hook(force=args.force)


if __name__ == "__main__":
    main()

