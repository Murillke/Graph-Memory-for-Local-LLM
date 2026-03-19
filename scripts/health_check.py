#!/usr/bin/env python3
"""
Health check for llm_memory system.
Verifies installation and configuration.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tools.console_utils import safe_print, setup_console_encoding
from tools.config import load_config

# Setup console encoding for Windows
setup_console_encoding()


def check_python_version():
    """Check if Python version is supported."""
    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"
    
    safe_print(f"Python version: {version_str}")
    
    if version.major != 3:
        safe_print("  [ERROR] FAIL: Python 3 required")
        return False
    
    if version.minor < 8:
        safe_print(f"  [ERROR] FAIL: Python 3.8+ required (you have 3.{version.minor})")
        return False
    
    if version.minor >= 14:
        safe_print(f"  [ERROR] FAIL: Python 3.14+ not supported (kuzu limitation)")
        safe_print(f"     Install Python 3.13 or earlier")
        return False
    
    safe_print(f"  [OK] OK: Python {version.major}.{version.minor} is supported")
    return True


def check_kuzu():
    """Check if kuzu is installed."""
    safe_print("Checking kuzu installation...")
    
    try:
        import kuzu
        safe_print(f"  [OK] OK: kuzu installed (version {kuzu.__version__})")
        return True
    except ImportError:
        safe_print("  [ERROR] FAIL: kuzu not installed")
        safe_print("     Run: pip install kuzu")
        return False


def check_memory_directory():
    """Check if memory directory exists."""
    safe_print("Checking memory directory...")
    
    if os.path.exists('memory'):
        safe_print("  [OK] OK: memory/ directory exists")
        return True
    else:
        safe_print("  [WARNING]  WARNING: memory/ directory not found")
        safe_print("     Will be created automatically on first use")
        return True  # Not critical


def check_console_encoding():
    """Check if console encoding works."""
    safe_print("Checking console encoding...")
    
    try:
        # Try to print emoji
        test_str = "[OK] [RED] [WARNING]"
        safe_print(f"  Test: {test_str}")
        safe_print("  [OK] OK: Console encoding working")
        return True
    except Exception as e:
        safe_print(f"  [WARNING]  WARNING: Console encoding issue: {e}")
        safe_print("     This is OK - safe_print() will handle it")
        return True  # Not critical


def check_database_creation():
    """Check if we can create a test database."""
    safe_print("Checking database creation...")

    try:
        import kuzu
        import shutil
        from pathlib import Path

        # Use the workspace tmp/ directory so the check works in sandboxed runtimes.
        workspace_tmp = Path('tmp')
        workspace_tmp.mkdir(exist_ok=True)
        test_db_path = workspace_tmp / 'health_check_test.graph'

        if test_db_path.exists():
            shutil.rmtree(test_db_path, ignore_errors=True)

        try:
            # Create test database
            db = kuzu.Database(str(test_db_path))
            conn = kuzu.Connection(db)

            # Try a simple query
            conn.execute("CREATE NODE TABLE IF NOT EXISTS TestNode (id INT64 PRIMARY KEY)")

            # Clean up
            conn = None
            db = None
        finally:
            if test_db_path.exists():
                shutil.rmtree(test_db_path, ignore_errors=True)

        safe_print("  [OK] OK: Can create databases")
        return True
    except Exception as e:
        safe_print(f"  [ERROR] FAIL: Cannot create database: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_database_consistency():
    """Check for database file inconsistencies."""
    config = load_config()
    memory_dir = config.get_memory_dir()
    if not os.path.exists(memory_dir):
        safe_print("  [NOTE] No memory directory yet (will be created on first use)")
        return True

    # Find all database files
    db_files = {}
    for f in os.listdir(memory_dir):
        if f.endswith(('.graph', '.kuzu', '.db')) and not f.startswith('test') and f != 'conversations.db':
            path = os.path.join(memory_dir, f)
            size = os.path.getsize(path)
            project = f.replace('.graph', '').replace('.kuzu', '').replace('.db', '')

            if project not in db_files:
                db_files[project] = []
            db_files[project].append((f, size))

    if not db_files:
        safe_print("  [NOTE] No project databases found yet")
        return True

    # Check for duplicates
    issues = []
    for project, files in db_files.items():
        if len(files) > 1:
            # Multiple files for same project
            files_sorted = sorted(files, key=lambda x: x[1], reverse=True)
            largest = files_sorted[0]
            others = files_sorted[1:]

            safe_print(f"  [ERROR] Multiple databases for project '{project}':")
            safe_print(f"     {largest[0]} ({largest[1]:,} bytes) <- LARGEST")
            for fname, fsize in others:
                safe_print(f"     {fname} ({fsize:,} bytes)")
            issues.append(project)

    if issues:
        safe_print(f"  [ERROR] Found {len(issues)} project(s) with multiple graph database files")
        safe_print(f"     Canonical extension is .graph")
        safe_print(f"     Run: python scripts/consolidate_graph_db_paths.py --dry-run")
        safe_print(f"     Then: python scripts/consolidate_graph_db_paths.py --project <name> --prefer-largest --apply")
        return False
    else:
        safe_print(f"  [OK] OK: No database inconsistencies found")
        return True


def main():
    safe_print("=" * 60)
    safe_print("LLM MEMORY SYSTEM - HEALTH CHECK")
    safe_print("=" * 60)
    safe_print()
    
    checks = [
        ("Python Version", check_python_version),
        ("Kuzu Installation", check_kuzu),
        ("Memory Directory", check_memory_directory),
        ("Console Encoding", check_console_encoding),
        ("Database Creation", check_database_creation),
        ("Database Consistency", check_database_consistency),
    ]
    
    results = []
    for name, check_func in checks:
        safe_print(f"[{len(results) + 1}/{len(checks)}] {name}")
        result = check_func()
        results.append(result)
        safe_print()
    
    safe_print("=" * 60)
    safe_print("SUMMARY")
    safe_print("=" * 60)
    safe_print()
    
    passed = sum(results)
    total = len(results)
    
    if all(results):
        safe_print("[OK] ALL CHECKS PASSED!")
        safe_print()
        safe_print("Your system is ready to use.")
        safe_print()
        safe_print("Next steps:")
        safe_print("  1. Store your first interaction:")
        safe_print("     python scripts/store_interaction.py \\")
        safe_print("         --project 'my-project' \\")
        safe_print("         --user 'Hello!' \\")
        safe_print("         --assistant 'Hi there!'")
        safe_print()
        safe_print("  2. Query it:")
        safe_print("     python scripts/query_memory.py --project 'my-project' --all")
        safe_print()
        return 0
    else:
        safe_print(f"[WARNING]  {passed}/{total} checks passed")
        safe_print()
        safe_print("Please fix the failed checks above before using the system.")
        safe_print()
        safe_print("For help, see:")
        safe_print("  - README.md")
        safe_print("  - WINDOWS-SETUP.md (Windows users)")
        safe_print("  - CONSISTENCY-ISSUES.md (troubleshooting)")
        safe_print()
        return 1


if __name__ == '__main__':
    sys.exit(main())

