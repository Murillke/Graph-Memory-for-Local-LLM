#!/usr/bin/env python3
"""
Clean up test databases from memory/ folder.

This script removes all test databases that were created in the wrong location
(memory/ instead of tests/tmp/).

Run this after fixing the test files to use tests/tmp/.
"""

import os
import shutil


def cleanup_test_databases():
    """Remove test databases from memory/ folder."""
    
    memory_dir = "./memory"
    
    if not os.path.exists(memory_dir):
        print("memory/ directory not found")
        return
    
    # Patterns for test files
    test_patterns = [
        "test",
        "health_check",
        "integration-test"
    ]
    
    removed_files = []
    removed_dirs = []
    
    # List all files in memory/
    for item in os.listdir(memory_dir):
        item_path = os.path.join(memory_dir, item)
        
        # Check if it's a test file
        is_test = any(pattern in item.lower() for pattern in test_patterns)
        
        if is_test:
            if os.path.isdir(item_path):
                # Remove directory
                shutil.rmtree(item_path)
                removed_dirs.append(item)
                print(f"Removed directory: {item}")
            else:
                # Remove file
                os.remove(item_path)
                removed_files.append(item)
                print(f"Removed file: {item}")
    
    print(f"\n{'='*60}")
    print(f"Cleanup complete!")
    print(f"{'='*60}")
    print(f"Removed {len(removed_files)} files")
    print(f"Removed {len(removed_dirs)} directories")
    
    if removed_files:
        print(f"\nFiles removed:")
        for f in removed_files:
            print(f"  - {f}")
    
    if removed_dirs:
        print(f"\nDirectories removed:")
        for d in removed_dirs:
            print(f"  - {d}")


if __name__ == "__main__":
    print("="*60)
    print("Cleaning up test databases from memory/")
    print("="*60)
    print()
    
    cleanup_test_databases()

