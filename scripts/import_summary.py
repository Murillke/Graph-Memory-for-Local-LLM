#!/usr/bin/env python3
"""
Import a summary-first sync payload from JSON into the memory system.

Usage:
    python3 scripts/import_summary.py --project "my-project" --file summary.json
    cat summary.json | python3 scripts/import_summary.py --project "my-project" --stdin

JSON Format:
    {
        "summary": {
            "session_id": "sync-abc123",
            "timestamp": "2026-03-18T12:00:00Z",
            "intent": "What the user wanted",
            "work_attempted": ["Reviewed docs", "Patched code"],
            "outcomes": [{"type": "success", "description": "Tests passed"}],
            "fidelity": "summary"
        }
    }
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.config import load_config
from tools.console_utils import safe_print, setup_console_encoding
from tools.sql_db import SQLDatabase

try:
    import opentimestamps as ots  # noqa: F401
    HAS_OTS = True
except ImportError:
    HAS_OTS = False

setup_console_encoding()

ALLOWED_FIDELITY = {"summary", "paraphrased", "reconstructed", "llm-state"}

IMPORT_EXAMPLES = """
Examples:
  python scripts/import_summary.py --project llm_memory --file tmp/conversation_2026-03-13_15-00-00.json --constrained-environment
  python scripts/import_summary.py --project llm_memory --file tmp/conversation_2026-03-13_15-00-00.json
"""


class ImportArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: error: {message}\n{IMPORT_EXAMPLES}")


def generate_timestamp_proof(
    file_content: str,
    constrained_environment: bool = False,
    constraint_reason: Optional[str] = None,
) -> tuple[str, Optional[str]]:
    file_hash = hashlib.sha256(file_content.encode("utf-8")).hexdigest()
    try:
        from tools.timestamp_proof import create_timestamp_proof

        timestamp_proof = create_timestamp_proof(
            file_hash,
            constrained_environment=constrained_environment,
            constraint_reason=constraint_reason,
        )
        return file_hash, timestamp_proof
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] Failed to generate timestamp proof: {exc}")
        return file_hash, None


def fail_preflight(message: str) -> None:
    safe_print(f"[ERROR] {message}", file=sys.stderr)
    sys.exit(1)


def validate_summary_payload(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    summary = data.get("summary")
    if not isinstance(summary, dict):
        return ["JSON must have a 'summary' object"]

    required = ["session_id", "timestamp", "intent", "work_attempted", "outcomes", "fidelity"]
    for field in required:
        if field not in summary:
            errors.append(f"summary.{field} is required")

    if "intent" in summary and (not isinstance(summary["intent"], str) or not summary["intent"].strip()):
        errors.append("summary.intent must be a non-empty string")

    if "timestamp" in summary and (not isinstance(summary["timestamp"], str) or not summary["timestamp"].strip()):
        errors.append("summary.timestamp must be a non-empty string")

    if "session_id" in summary and (not isinstance(summary["session_id"], str) or not summary["session_id"].strip()):
        errors.append("summary.session_id must be a non-empty string")

    if "work_attempted" in summary and not isinstance(summary["work_attempted"], list):
        errors.append("summary.work_attempted must be a list")

    if "outcomes" in summary and not isinstance(summary["outcomes"], list):
        errors.append("summary.outcomes must be a list")

    fidelity = summary.get("fidelity")
    if fidelity not in ALLOWED_FIDELITY:
        errors.append(f"summary.fidelity must be one of {sorted(ALLOWED_FIDELITY)}")

    return errors


def _build_assistant_summary(summary: dict[str, Any]) -> str:
    payload = {
        "work_attempted": summary.get("work_attempted", []),
        "outcomes": summary.get("outcomes", []),
    }
    for key in ("assistant_attempt", "actions_taken", "process_sequences", "entities", "tasks", "open_questions"):
        if key in summary:
            payload[key] = summary[key]
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def main():
    parser = ImportArgumentParser(
        description="Import a summary-first JSON payload into the memory system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=IMPORT_EXAMPLES,
    )
    parser.add_argument("--project", required=True, help="Project name")
    parser.add_argument("--config", help="Path to config file")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", help="JSON file with summary payload")
    group.add_argument("--stdin", action="store_true", help="Read JSON from stdin")
    parser.add_argument("--db", help="Path to SQLite database")
    parser.add_argument(
        "--constrained-environment",
        action="store_true",
        help="Skip OpenTimestamps network submission and record a local-only proof explicitly",
    )
    parser.add_argument("--constraint-reason", help="Optional explanation stored in the timestamp proof")
    parser.add_argument("--json", action="store_true", help="Output as JSON instead of human-readable")
    parser.add_argument("--agent", dest="imported_by_agent", help="Agent name importing this summary")
    parser.add_argument("--model", dest="imported_by_model", help="Model name importing this summary")
    args = parser.parse_args()

    args.imported_by_agent = args.imported_by_agent or os.environ.get("LLM_AGENT_NAME")
    args.imported_by_model = args.imported_by_model or os.environ.get("LLM_AGENT_MODEL")

    config = load_config(
        project_name=args.project,
        cli_args={"sql_db": args.db, "config": args.config},
        config_path=args.config,
    )
    args.db = config.get_sql_db_path()

    db_parent = Path(args.db).parent
    if not db_parent.exists():
        fail_preflight(f"Database directory does not exist: {db_parent}")

    try:
        if args.stdin:
            data = json.load(sys.stdin)
            file_content = json.dumps(data, sort_keys=True)
        else:
            with open(args.file, "r", encoding="utf-8") as handle:
                file_content = handle.read()
                data = json.loads(file_content)
    except json.JSONDecodeError as exc:
        fail_preflight(f"Invalid summary JSON: {exc}")
    except Exception as exc:  # noqa: BLE001
        fail_preflight(f"Failed to read summary input: {exc}")

    validation_errors = validate_summary_payload(data)
    if validation_errors:
        for error in validation_errors:
            safe_print(f"[ERROR] {error}", file=sys.stderr)
        sys.exit(1)

    file_hash, timestamp_proof = generate_timestamp_proof(
        file_content,
        constrained_environment=args.constrained_environment,
        constraint_reason=args.constraint_reason,
    )
    if timestamp_proof and not args.json:
        proof_data = json.loads(timestamp_proof)
        safe_print("[OK] Generated timestamp proof")
        safe_print(f"   File hash: {file_hash}")
        safe_print(f"   Mode: {proof_data.get('proof_mode', 'unknown')}")
        safe_print(f"   Attestation status: {proof_data.get('attestation_status', 'unknown')}")

    summary = data["summary"]
    workflow_session_id = data.get("workflow_session_id")
    db = SQLDatabase(args.db)

    if not db.get_project_by_name(args.project):
        db.create_project(args.project, f"Project: {args.project}")

    interaction_uuid = db.store_interaction(
        {
            "project_name": args.project,
            "user_message": summary["intent"],
            "assistant_message": _build_assistant_summary(summary),
            "timestamp": summary["timestamp"],
            "session_id": workflow_session_id or summary["session_id"],
            "file_hash": file_hash,
            "timestamp_proof": timestamp_proof,
            "fidelity": summary.get("fidelity", "summary"),
            "source_note": "summary-first import",
            "imported_by_agent": args.imported_by_agent,
            "imported_by_model": args.imported_by_model,
            "context_data": json.dumps(summary, ensure_ascii=False, sort_keys=True),
        }
    )

    if args.json:
        print(json.dumps({"status": "ok", "uuid": interaction_uuid, "file_hash": file_hash}))
        return

    safe_print("[OK] [1/1] Imported summary")
    safe_print(f"   UUID: {interaction_uuid}")
    safe_print(f"   Intent: {summary['intent'][:60]}{'...' if len(summary['intent']) > 60 else ''}")
    safe_print("")
    safe_print("============================================================")
    safe_print("[DATA] Import Summary")
    safe_print("============================================================")
    safe_print(f"Project:          {args.project}")
    safe_print("Total Summaries:  1")
    safe_print("[OK] Imported:      1")
    safe_print("[ERROR] Failed:        0")
    safe_print("")
    safe_print("[OK] Summary imported successfully!")


if __name__ == "__main__":
    main()
