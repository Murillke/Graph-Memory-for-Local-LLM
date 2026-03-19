#!/usr/bin/env python3
"""
Update the llm_memory_dist distribution folder with latest files.

Usage:
    python scripts/update_distribution.py
    python scripts/update_distribution.py --dry-run
    python scripts/update_distribution.py --target ../OtherProject/mem
"""

import os
import sys
import shutil
import argparse
from pathlib import Path

# Files/folders to sync
SYNC_ITEMS = {
    # Workflow files (root) - ALL .md files that agents use
    "sync.md": "sync.md",
    "init.md": "init.md",
    "history.md": "history.md",
    "remember.md": "remember.md",
    "remember-external.md": "remember-external.md",
    "export.md": "export.md",
    "search.md": "search.md",
    "search-external.md": "search-external.md",
    "verify.md": "verify.md",
    "import.md": "import.md",
    "merge.md": "merge.md",
    "status.md": "status.md",
    "visualize.md": "visualize.md",
    "dump.md": "dump.md",
    "extract.md": "extract.md",
    "recall.md": "recall.md",
    "backup.md": "backup.md",
    "consolidate.md": "consolidate.md",
    "stats.md": "stats.md",
    "tasks.md": "tasks.md",
    "timeline.md": "timeline.md",
    "import-documents.md": "import-documents.md",
    "verify_document.md": "verify_document.md",

    # Documentation files
    "README.md": "README.md",
    "LLM-INSTRUCTIONS.md": "LLM-INSTRUCTIONS.md",
    "COMMANDS.md": "COMMANDS.md",
    "KNOWN_ISSUES.md": "KNOWN_ISSUES.md",
    "TROUBLESHOOTING.md": "TROUBLESHOOTING.md",
    "WINDOWS-SETUP.md": "WINDOWS-SETUP.md",
    "CODE-GRAPH.md": "CODE-GRAPH.md",
    "requirements.txt": "requirements.txt",

    # Visualization
    "visualize_graph_d3.html": "visualize_graph_d3.html",

    # Scripts
    "scripts/import_summary.py": "scripts/import_summary.py",
    "scripts/store_extraction.py": "scripts/store_extraction.py",
    "scripts/validate_extraction.py": "scripts/validate_extraction.py",
    "scripts/query_memory.py": "scripts/query_memory.py",
    "scripts/show_interactions.py": "scripts/show_interactions.py",
    "scripts/export_history.py": "scripts/export_history.py",
    "scripts/export_graph.py": "scripts/export_graph.py",
    "scripts/health_check.py": "scripts/health_check.py",
    "scripts/verify_integrity.py": "scripts/verify_integrity.py",
    "scripts/sync.py": "scripts/sync.py",
    "scripts/recall.py": "scripts/recall.py",
    "scripts/search_helper.py": "scripts/search_helper.py",
    "scripts/rebuild_graph.py": "scripts/rebuild_graph.py",
    "scripts/merge_database.py": "scripts/merge_database.py",
    "scripts/import_project.py": "scripts/import_project.py",
    "scripts/compare_graphs.py": "scripts/compare_graphs.py",
    "scripts/code_during_conversation.py": "scripts/code_during_conversation.py",
    "scripts/conversations_for_commit.py": "scripts/conversations_for_commit.py",
    "scripts/link_code_to_memory.py": "scripts/link_code_to_memory.py",
    "scripts/git_post_commit_hook.py": "scripts/git_post_commit_hook.py",
    "scripts/install_git_hook.py": "scripts/install_git_hook.py",
    "scripts/generate_ownership_proof.py": "scripts/generate_ownership_proof.py",
    "scripts/verify_ownership_proof.py": "scripts/verify_ownership_proof.py",
    "scripts/verify_attested_entity.py": "scripts/verify_attested_entity.py",
    "scripts/verify_graph_timestamps.py": "scripts/verify_graph_timestamps.py",
    "scripts/export_sql_proofs.py": "scripts/export_sql_proofs.py",
    "scripts/import_sql_proofs.py": "scripts/import_sql_proofs.py",
    "scripts/submit_local_proofs_to_ots.py": "scripts/submit_local_proofs_to_ots.py",
    "scripts/tasks.py": "scripts/tasks.py",
    "scripts/prepare_sync_files.py": "scripts/prepare_sync_files.py",

    # Tools
    "tools/__init__.py": "tools/__init__.py",
    "tools/config.py": "tools/config.py",
    "tools/graph_db.py": "tools/graph_db.py",
    "tools/sql_db.py": "tools/sql_db.py",
    "tools/code_graph.py": "tools/code_graph.py",
    "tools/timestamp_proof.py": "tools/timestamp_proof.py",
    "tools/timestamp_proof_official.py": "tools/timestamp_proof_official.py",
    "tools/source_chain.py": "tools/source_chain.py",
    "tools/consolidation_reminder.py": "tools/consolidation_reminder.py",
    "tools/temp_cleanup_reminder.py": "tools/temp_cleanup_reminder.py",
    "tools/db_utils.py": "tools/db_utils.py",
    "tools/console_utils.py": "tools/console_utils.py",
    "tools/merkle_tree.py": "tools/merkle_tree.py",
    "tools/deduplication.py": "tools/deduplication.py",
    "tools/contradiction.py": "tools/contradiction.py",

    # Docs
    "docs/QUICK-START.md": "docs/QUICK-START.md",
    "docs/COMMANDS.md": "docs/COMMANDS.md",
    "docs/TESTING.md": "docs/TESTING.md",
    "docs/CONFIGURATION.md": "docs/CONFIGURATION.md",
    "docs/ARCHITECTURE.md": "docs/ARCHITECTURE.md",
    "docs/EXTRACTION-FORMAT-SPEC.md": "docs/EXTRACTION-FORMAT-SPEC.md",
    "docs/extraction-rules.md": "docs/extraction-rules.md",
    "docs/MEMORY-SYSTEM-INSTRUCTIONS.md": "docs/MEMORY-SYSTEM-INSTRUCTIONS.md",
    "docs/CRYPTO-PROOFS.md": "docs/CRYPTO-PROOFS.md",
    "docs/OWNERSHIP-PROOFS.md": "docs/OWNERSHIP-PROOFS.md",
    "docs/MERGE-VERIFICATION.md": "docs/MERGE-VERIFICATION.md",
    "docs/MULTI-MACHINE-SETUP.md": "docs/MULTI-MACHINE-SETUP.md",
    "docs/SYNC-WORKFLOW.md": "docs/SYNC-WORKFLOW.md",
    "docs/CODE-GRAPH.md": "docs/CODE-GRAPH.md",
    "docs/AI-SEARCH-HELPER.md": "docs/AI-SEARCH-HELPER.md",
    "docs/cross-project.md": "docs/cross-project.md",
    "docs/CROSS-PROJECT-KNOWLEDGE-SHARING.md": "docs/CROSS-PROJECT-KNOWLEDGE-SHARING.md",
    "docs/shared-database.md": "docs/shared-database.md",
    "docs/proof-model.md": "docs/proof-model.md",

    # Architecture
    "architecture/README.md": "architecture/README.md",
    "architecture/data-model.md": "architecture/data-model.md",
    "architecture/system-overview.md": "architecture/system-overview.md",
    "architecture/workflow-sync.md": "architecture/workflow-sync.md",

    # Schema
    "schema/code_graph_schema.cypher": "schema/code_graph_schema.cypher",

    # Examples
    "examples/mem.config.json": "examples/mem.config.json",
    "examples/conversation-example-with-comments.json": "examples/conversation-example-with-comments.json",
    "examples/current-extraction.json": "examples/current-extraction.json",
    "examples/quality-extraction.json": "examples/quality-extraction.json",
    "examples/mem.config-shared.json": "examples/mem.config-shared.json",
    "examples/mem.config-split-databases.json": "examples/mem.config-split-databases.json",

    # Integrations
    "integrations/openclaw.md": "integrations/openclaw.md",
    "integrations/openfang.md": "integrations/openfang.md",
}

def main():
    parser = argparse.ArgumentParser(description='Update distribution folder')
    parser.add_argument('--target', default='llm_memory_dist',
                        help='Target distribution folder (default: llm_memory_dist)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be copied without copying')
    args = parser.parse_args()

    src_root = Path(__file__).parent.parent
    dst_root = Path(args.target)
    
    if not dst_root.is_absolute():
        dst_root = src_root / dst_root

    print(f"Source: {src_root}")
    print(f"Target: {dst_root}")
    print()

    copied = 0
    skipped = 0
    missing = 0

    for src_rel, dst_rel in SYNC_ITEMS.items():
        src_path = src_root / src_rel
        dst_path = dst_root / dst_rel
        
        if not src_path.exists():
            print(f"[MISSING] {src_rel}")
            missing += 1
            continue
        
        # Check if needs update
        if dst_path.exists():
            src_mtime = src_path.stat().st_mtime
            dst_mtime = dst_path.stat().st_mtime
            if src_mtime <= dst_mtime:
                skipped += 1
                continue
        
        if args.dry_run:
            print(f"[WOULD COPY] {src_rel} -> {dst_rel}")
        else:
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_path, dst_path)
            print(f"[COPIED] {src_rel}")
        copied += 1

    print()
    print(f"Copied: {copied}, Skipped (up-to-date): {skipped}, Missing: {missing}")
    
    if args.dry_run:
        print("\n(Dry run - no files were actually copied)")

if __name__ == '__main__':
    main()
