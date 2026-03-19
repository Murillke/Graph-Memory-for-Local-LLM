#!/usr/bin/env python3
"""
Check which command MD files are missing the LLM INSTRUCTIONS section.
"""

import os
from pathlib import Path

# Command files in root
COMMAND_FILES = [
    'consolidate.md',
    'export.md',
    'import-documents.md',
    'import.md',
    'init.md',
    'merge.md',
    'recall.md',
    'remember-external.md',
    'remember.md',
    'search-external.md',
    'search.md',
    'status.md',
    'sync.md',
    'tasks.md',
    'verify.md',
    'visualize.md'
]

def check_file(filename):
    """Check if file has LLM INSTRUCTIONS section."""
    if not os.path.exists(filename):
        return False, "File not found"
    
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
    
    has_instructions = '## 🤖 LLM INSTRUCTIONS' in content or '## LLM INSTRUCTIONS' in content
    return has_instructions, "Has LLM INSTRUCTIONS" if has_instructions else "Missing LLM INSTRUCTIONS"

def main():
    print("="*60)
    print("Checking Command File Format")
    print("="*60)
    print()
    
    missing = []
    has_it = []
    
    for filename in COMMAND_FILES:
        has_instructions, status = check_file(filename)
        if has_instructions:
            has_it.append(filename)
            print(f"OK {filename}: {status}")
        else:
            missing.append(filename)
            print(f"MISSING {filename}: {status}")
    
    print()
    print("="*60)
    print(f"Summary:")
    print(f"  Has LLM INSTRUCTIONS: {len(has_it)}")
    print(f"  Missing LLM INSTRUCTIONS: {len(missing)}")
    print("="*60)
    
    if missing:
        print()
        print("Files missing LLM INSTRUCTIONS:")
        for f in missing:
            print(f"  - {f}")

if __name__ == "__main__":
    main()

