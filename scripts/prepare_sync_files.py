#!/usr/bin/env python3
"""
Prepare temp files for sync workflow.

Creates/resets all temp files needed for a sync run:
- UUID-named conversation and extraction files (stable, won't be overwritten)
- Reusable helper files (entity.txt, search.txt, quality-answers.json, task helpers)

Returns paths as JSON for agents to use without guessing.

Usage:
    python scripts/prepare_sync_files.py --project llm_memory --json

    # Resume existing session (won't create new files)
    python scripts/prepare_sync_files.py --project llm_memory --json --session sync-a1b2c3d4

File Naming:
    Uses short UUID (8 chars) instead of timestamp to prevent accidental overwrites.
    Example: conversation_a1b2c3d4.json, extraction_a1b2c3d4.json
"""

import argparse
import json
import os
import shutil
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.config import load_config
from schema.relationship_types import RELATIONSHIP_CATEGORIES
from scripts.validate_extraction import CANONICAL_ENTITY_TYPES, ENTITY_TYPE_SYNONYMS


def generate_session_id() -> str:
    """Generate a short unique session ID (8 hex chars)."""
    return uuid.uuid4().hex[:8]


def generate_relationship_help() -> dict:
    """Generate _help_relationship_types from canonical source."""
    return {
        category: ", ".join(types)
        for category, types in RELATIONSHIP_CATEGORIES.items()
    }


def generate_entity_type_help() -> dict:
    """Generate _help_entity_types with canonical types and synonyms."""
    return {
        "canonical_types": CANONICAL_ENTITY_TYPES,
        "common_synonyms": {k: v for k, v in list(ENTITY_TYPE_SYNONYMS.items())[:10]},
        "_note": "Unknown types trigger warning but are accepted. Synonyms auto-normalize."
    }


def generate_extraction_structure_help() -> dict:
    """Generate _help_extraction_structure showing required fields."""
    return {
        "_example": {
            "interaction_uuid": "uuid-xxx (from import_summary.py output)",
            "entities": [
                {
                    "name": "Entity Name (required)",
                    "type": "one of canonical_types (required)",
                    "summary": "Brief description (required)"
                }
            ],
            "facts": [
                {
                    "source_entity": "must match an entity name in THIS extraction (required)",
                    "target_entity": "must match an entity name in THIS extraction (required)",
                    "relationship_type": "one of _help_relationship_types (required)",
                    "fact": "human-readable description of relationship (required)"
                }
            ]
        },
        "_rules": [
            "Each extraction must have interaction_uuid from the imported conversation",
            "Entity references in facts MUST exist in the SAME extraction's entities list",
            "Use examples/current-extraction.json as reference for complete examples"
        ]
    }


def is_timestamp_based_filename(filename: str) -> bool:
    """Check if filename uses old timestamp format (YYYY-MM-DD_HH-MM-SS)."""
    import re
    # Match conversation_2026-03-16_03-13-43.json or extraction_2026-03-16_03-13-43.json
    pattern = r'^(conversation|extraction|entity-mapping)_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.json$'
    return bool(re.match(pattern, filename))


def archive_old_sync_artifacts(
    tmp_path: Path,
    timestamp: str,
    archive_uuid_files: bool = False
) -> Tuple[Optional[str], List[str]]:
    """
    Move stale sync artifacts out of tmp/ into tmp/old/{timestamp}/.

    Args:
        tmp_path: Path to tmp directory
        timestamp: Timestamp for archive directory name
        archive_uuid_files: If False (default), only archive legacy timestamp-based files.
                           If True, archive all sync files including UUID-based ones.
    """
    archive_patterns = (
        "conversation_*.json",
        "extraction_*.json",
        "entity-mapping_*.json",
    )
    archive_names = {
        "quality-questions.json",
        "quality-answers.json",
    }

    candidates: List[Path] = []
    for pattern in archive_patterns:
        for path in tmp_path.glob(pattern):
            if path.is_file():
                # Only archive UUID-based files if explicitly requested
                if archive_uuid_files or is_timestamp_based_filename(path.name):
                    candidates.append(path)

    for name in archive_names:
        path = tmp_path / name
        if path.is_file():
            candidates.append(path)

    if not candidates:
        return None, []

    archive_dir = tmp_path / "old" / timestamp
    archive_dir.mkdir(parents=True, exist_ok=True)

    archived_files: List[str] = []
    for path in sorted(candidates):
        destination = archive_dir / path.name
        shutil.move(str(path), str(destination))
        archived_files.append(str(destination))

    return str(archive_dir), archived_files


def prepare_sync_files(
    project_name: str,
    tmp_dir: str = "tmp",
    session_id: Optional[str] = None,
    archive: bool = True
) -> dict:
    """
    Prepare all temp files for a sync run.

    Args:
        project_name: Project name for extraction metadata
        tmp_dir: Temp directory path
        session_id: Optional existing session ID to resume (e.g., "sync-a1b2c3d4")
                    If provided, will reuse existing files instead of creating new ones.
        archive: Whether to archive old sync artifacts (default True, False for resume)

    Returns dict with all file paths and metadata.
    """
    # Ensure tmp directory exists
    tmp_path = Path(tmp_dir)
    tmp_path.mkdir(parents=True, exist_ok=True)

    # Generate or parse session ID
    if session_id:
        # Resume existing session
        if session_id.startswith("sync-"):
            short_id = session_id[5:]  # Strip "sync-" prefix
        else:
            short_id = session_id
        workflow_session_id = f"sync-{short_id}"
        is_resume = True
    else:
        # New session with UUID
        short_id = generate_session_id()
        workflow_session_id = f"sync-{short_id}"
        is_resume = False

    # UUID-based files (stable, won't be accidentally overwritten)
    conversation_file = tmp_path / f"conversation_{short_id}.json"
    extraction_file = tmp_path / f"extraction_{short_id}.json"

    # Check if resuming an existing session
    if is_resume:
        if conversation_file.exists() and extraction_file.exists():
            # Return existing files without modification
            return {
                "session_id": short_id,
                "workflow_session_id": workflow_session_id,
                "project_name": project_name,
                "conversation_file": str(conversation_file),
                "extraction_file": str(extraction_file),
                "entity_file": str(tmp_path / "entity.txt"),
                "search_file": str(tmp_path / "search.txt"),
                "task_file": str(tmp_path / "task.txt"),
                "summary_file": str(tmp_path / "summary.txt"),
                "task_json_file": str(tmp_path / "task.json"),
                "batch_file": str(tmp_path / "batch.json"),
                "quality_answers_file": str(tmp_path / "quality-answers.json"),
                "archive_dir": None,
                "archived_files": [],
                "status": "resumed",
                "is_resume": True
            }
        else:
            # Session ID provided but files don't exist
            raise FileNotFoundError(
                f"Session {workflow_session_id} not found. "
                f"Expected files: {conversation_file}, {extraction_file}"
            )

    # Archive old artifacts only for new sessions
    archive_dir = None
    archived_files = []
    if archive:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        archive_dir, archived_files = archive_old_sync_artifacts(tmp_path, timestamp)
    
    # Reusable helper files (reset each run)
    entity_file = tmp_path / "entity.txt"
    search_file = tmp_path / "search.txt"
    task_file = tmp_path / "task.txt"
    summary_file = tmp_path / "summary.txt"
    task_json_file = tmp_path / "task.json"
    batch_file = tmp_path / "batch.json"
    quality_answers_file = tmp_path / "quality-answers.json"
    
    # Delete and recreate reusable helper files (empty, UTF-8)
    for f in [entity_file, search_file, task_file, summary_file]:
        if f.exists():
            f.unlink()
        f.write_text("", encoding="utf-8")

    # Task JSON helper templates should also be fresh each run.
    for f in [task_json_file, batch_file]:
        if f.exists():
            f.unlink()

    task_json_template = {
        "name": "",
        "summary": "",
        "priority": "medium"
    }
    task_json_file.write_text(
        json.dumps(task_json_template, indent=2) + "\n",
        encoding="utf-8"
    )

    batch_template = {
        "tasks": []
    }
    batch_file.write_text(
        json.dumps(batch_template, indent=2) + "\n",
        encoding="utf-8"
    )
    
    # Quality answers is an editable workflow artifact, so keep it multiline.
    if quality_answers_file.exists():
        quality_answers_file.unlink()
    quality_answers_template = {
        "duplicates": [],
        "contradictions": []
    }
    quality_answers_file.write_text(
        json.dumps(quality_answers_template, indent=2) + "\n",
        encoding="utf-8"
    )
    
    # Create editable summary-first template as multiline JSON.
    conversation_template = {
        "workflow_session_id": workflow_session_id,
        "_help_fidelity_values": "summary, paraphrased, reconstructed, llm-state",
        "summary": {
            "session_id": workflow_session_id,
            "timestamp": "",
            "intent": "",
            "work_attempted": [],
            "outcomes": [],
            "fidelity": "summary"
        }
    }
    conversation_file.write_text(
        json.dumps(conversation_template, indent=2) + "\n",
        encoding="utf-8"
    )

    # Create editable extraction template as multiline JSON.
    extraction_template = {
        "project_name": project_name,
        "workflow_session_id": workflow_session_id,
        "extraction_version": "v1.0.0",
        "extraction_commit": f"session-{short_id}",
        "_help_entity_types": generate_entity_type_help(),
        "_help_relationship_types": generate_relationship_help(),
        "_help_extraction_structure": generate_extraction_structure_help(),
        "extractions": []
    }
    extraction_file.write_text(
        json.dumps(extraction_template, indent=2) + "\n",
        encoding="utf-8"
    )

    return {
        "session_id": short_id,
        "workflow_session_id": workflow_session_id,
        "project_name": project_name,
        "conversation_file": str(conversation_file),
        "extraction_file": str(extraction_file),
        "entity_file": str(entity_file),
        "search_file": str(search_file),
        "task_file": str(task_file),
        "summary_file": str(summary_file),
        "task_json_file": str(task_json_file),
        "batch_file": str(batch_file),
        "quality_answers_file": str(quality_answers_file),
        "archive_dir": archive_dir,
        "archived_files": archived_files,
        "status": "ready",
        "is_resume": False
    }


def main():
    parser = argparse.ArgumentParser(
        description="Prepare temp files for sync workflow",
        epilog="Example: python scripts/prepare_sync_files.py --project llm_memory --json"
    )
    parser.add_argument("--project", required=True, help="Project name")
    parser.add_argument("--json", action="store_true", help="Output as JSON (recommended)")
    parser.add_argument("--tmp-dir", default="tmp", help="Temp directory (default: tmp)")
    parser.add_argument(
        "--session",
        help="Resume existing session by ID (e.g., 'sync-a1b2c3d4' or just 'a1b2c3d4')"
    )
    parser.add_argument(
        "--no-archive",
        action="store_true",
        help="Don't archive old sync files (useful for debugging)"
    )

    args = parser.parse_args()

    try:
        result = prepare_sync_files(
            args.project,
            args.tmp_dir,
            session_id=args.session,
            archive=not args.no_archive
        )

        if args.json:
            print(json.dumps(result))
        else:
            print(f"Session ID: {result['session_id']}")
            print(f"Workflow Session: {result['workflow_session_id']}")
            print(f"Conversation: {result['conversation_file']}")
            print(f"Extraction: {result['extraction_file']}")
            print(f"Entity helper: {result['entity_file']}")
            print(f"Search helper: {result['search_file']}")
            print(f"Task helper: {result['task_file']}")
            print(f"Task JSON helper: {result['task_json_file']}")
            print(f"Task batch helper: {result['batch_file']}")
            print(f"Quality answers: {result['quality_answers_file']}")
            if result["archive_dir"]:
                print(f"Archived old files to: {result['archive_dir']}")
                print(f"Archived count: {len(result['archived_files'])}")
            print(f"\nStatus: {result['status']}")

            if result.get('is_resume'):
                print("\n[RESUMED] Using existing session files.")
            else:
                print("\nNext steps:")
                print("1. Fill conversation file with summary content")
                print("2. Run import_summary.py")
                print("3. Get UUID with get_latest_uuid.py")
                print("4. Fill extraction file with entities/facts")
                print("5. Run validate_extraction.py")
                print("6. Run store_extraction.py with --require-quality-review")
                print("7. Verify with query_memory.py")
                print(f"\nTo resume this session later:")
                print(f"  python scripts/prepare_sync_files.py --project {args.project} --session {result['session_id']}")

        sys.exit(0)

    except FileNotFoundError as e:
        if args.json:
            print(json.dumps({"error": str(e), "status": "session_not_found"}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    except Exception as e:
        if args.json:
            print(json.dumps({"error": str(e), "status": "failed"}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
