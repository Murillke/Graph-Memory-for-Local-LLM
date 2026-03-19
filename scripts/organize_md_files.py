#!/usr/bin/env python3
"""
Organize MD files in root directory.

Moves documentation files to docs/ and research files to docs/research/,
keeping only command files in root.
"""

import os
import shutil


# Command files that should stay in root
COMMAND_FILES = [
    'recall.md',
    'sync.md',
    'tasks.md',
    'import.md',
    'import-documents.md',
    'search.md',
    'search-external.md',  # Search across all projects
    'consolidate.md',
    'export.md',
    'merge.md',
    'verify.md',
    'visualize.md',
    'remember.md',
    'remember-external.md',  # Remember across all projects
    'status.md',
    'init.md',
    'README.md'  # Standard to keep in root
]

# Documentation files to move to docs/
DOCS_FILES = [
    'ARCHITECTURE.md',
    'CHANGELOG.md',
    'CONTRIBUTING.md',
    'GETTING-STARTED.md',
    'INSTALLATION.md',
    'QUICK-REFERENCE.md',
    'START-HERE.md',
    'WORKFLOWS.md',
    'LLM-INTEGRATION.md',
    'DIAGRAMS.md',
    'DOCUMENTATION-INDEX.md',
    'SCRIPTS-REFERENCE.md',
    'WHATS-NEW.md'
]

# Research/analysis files to move to docs/research/
RESEARCH_FILES = [
    'ALIAS-CONTRADICTION-PROOFS-ANALYSIS.md',
    'CHANGELOG-TIMESTAMP-SCHEMA.md',
    'COMMAND-FILES-SUMMARY.md',
    'DATABASE-PATH-FIX.md',
    'EXTRACTION-WRAPPERS-INTEGRATED.md',
    'EXTRACTION-WRAPPERS-SUMMARY.md',
    'MEMORY-LITERAL-STRINGS.md',
    'MEMORY-TYPES-STATUS.md',
    'QUALITY-CHECK-STRATEGY.md',
    'RESEARCH-EPISODIC-MEMORY.md'
]

# Files to delete (duplicates)
DELETE_FILES = [
    'index.md'
]


def organize_files():
    """Organize MD files."""
    
    # Ensure directories exist
    os.makedirs('./docs', exist_ok=True)
    os.makedirs('./docs/research', exist_ok=True)
    
    moved_to_docs = []
    moved_to_research = []
    deleted = []
    
    # Move documentation files
    for file in DOCS_FILES:
        if os.path.exists(file):
            dest = os.path.join('./docs', file)
            if os.path.exists(dest):
                print(f"Skipping {file} (already exists in docs/)")
            else:
                shutil.move(file, dest)
                moved_to_docs.append(file)
                print(f"Moved {file} -> docs/")
    
    # Move research files
    for file in RESEARCH_FILES:
        if os.path.exists(file):
            dest = os.path.join('./docs/research', file)
            if os.path.exists(dest):
                print(f"Skipping {file} (already exists in docs/research/)")
            else:
                shutil.move(file, dest)
                moved_to_research.append(file)
                print(f"Moved {file} -> docs/research/")
    
    # Delete duplicate files
    for file in DELETE_FILES:
        if os.path.exists(file):
            os.remove(file)
            deleted.append(file)
            print(f"Deleted {file}")
    
    print(f"\n{'='*60}")
    print(f"Organization complete!")
    print(f"{'='*60}")
    print(f"Moved to docs/: {len(moved_to_docs)} files")
    print(f"Moved to docs/research/: {len(moved_to_research)} files")
    print(f"Deleted: {len(deleted)} files")
    print(f"\nCommand files remaining in root: {len(COMMAND_FILES)}")


if __name__ == "__main__":
    print("="*60)
    print("Organizing MD files")
    print("="*60)
    print()
    
    organize_files()

