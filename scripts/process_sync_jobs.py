#!/usr/bin/env python3
"""
Process async sync jobs from the queue.

This worker polls for queued sync jobs and executes the full sync pipeline:
1. Import summary
2. Validate extraction
3. Quality review (if required)
4. Store extraction
5. Verification (optional)

Usage:
    # Run continuously
    python3 scripts/process_sync_jobs.py --project llm_memory

    # Process one job and exit
    python3 scripts/process_sync_jobs.py --project llm_memory --once

    # Custom polling interval
    python3 scripts/process_sync_jobs.py --project llm_memory --poll-interval 5
"""

import sys
import os
import argparse
import json
import hashlib
import time
import tempfile
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tools.sql_db import SQLDatabase
from tools.config import load_config
from tools.graph_db import GraphDatabase

# Stage -> progress mapping
STAGE_PROGRESS = {
    "submitted": 0.0,
    "import_summary": 0.2,
    "validate_extraction": 0.4,
    "quality_review": 0.6,
    "store_extraction": 0.8,
    "verify": 0.95,
    "done": 1.0,
}


def log(msg: str, level: str = "INFO") -> None:
    """Log a message with timestamp."""
    ts = datetime.utcnow().isoformat() + "Z"
    print(f"[{ts}] [{level}] {msg}", file=sys.stderr)


def update_job_stage(sql_db: SQLDatabase, job_id: str, stage: str, status: str = "running") -> None:
    """Update job stage and progress."""
    progress = STAGE_PROGRESS.get(stage, 0.0)
    sql_db.update_sync_job_status(job_id, status=status, stage=stage, progress=progress)
    log(f"Job {job_id}: stage={stage}, progress={progress}")


def run_subprocess(cmd: list, cwd: str, timeout: int = 300) -> tuple:
    """Run a subprocess and capture output. Returns (success, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Subprocess timed out"
    except Exception as e:
        return False, "", str(e)


def get_python_path(config: Any) -> str:
    """Get the configured Python interpreter path."""
    # Try to get from config, fall back to python3
    try:
        return config.get_python_path() or "python3"
    except AttributeError:
        return "python3"


def canonicalize_sync_payload(
    summary: Dict[str, Any],
    extraction: Dict[str, Any],
    attachments: Dict[str, Any],
    options: Dict[str, Any],
) -> str:
    """Return canonical JSON for request-integrity hashing."""
    payload = {
        "schema_version": "summary-first-v1",
        "summary": summary,
        "extraction": extraction,
        "attachments": attachments,
        "options": options,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _extract_created_entity_uuids(stdout: str) -> List[str]:
    """Parse created/reused entity UUIDs from store_extraction stdout."""
    import re

    created = []
    reused = []
    for line in stdout.splitlines():
        if "Created entity:" in line:
            match = re.search(r"\((entity-[a-z0-9]+)\)", line, re.IGNORECASE)
            if match:
                created.append(match.group(1))
        elif "Using existing entity:" in line:
            match = re.search(r"\((entity-[a-z0-9]+)\)", line, re.IGNORECASE)
            if match:
                reused.append(match.group(1))
    return created, reused


def _deterministic_uuid(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"


def create_sync_batch_provenance(
    sql_db: SQLDatabase,
    graph_db: GraphDatabase,
    job: Dict[str, Any],
    project_name: str,
    extraction: Dict[str, Any],
    source_interaction_uuid: Optional[str],
    extraction_batch_uuid: Optional[str],
    created_entity_uuids: List[str],
    related_entity_uuids: List[str],
) -> str:
    """Create or update durable graph provenance for a successful network sync."""
    interaction = sql_db.get_interaction_by_uuid(source_interaction_uuid) if source_interaction_uuid else None
    source_hash = interaction["content_hash"] if interaction else ""
    event_timestamp = job.get("created_at") or datetime.utcnow().isoformat() + "Z"
    sync_batch_uuid = _deterministic_uuid("entity", job["job_id"], "syncbatch")

    attributes = {
        "transport": "network",
        "payload_hash": job.get("payload_hash"),
        "payload_hash_verified": bool(job.get("payload_hash_verified")),
        "submitted_at": job.get("created_at"),
        "source_interaction_uuid": source_interaction_uuid,
        "extraction_batch_uuid": extraction_batch_uuid,
        "client_cert_fingerprint": job.get("client_cert_fingerprint"),
        "client_cert_subject": job.get("client_cert_subject"),
        "client_cert_serial": job.get("client_cert_serial"),
        "client_cert_issuer": job.get("client_cert_issuer"),
        "client_cert_not_before": job.get("client_cert_not_before"),
        "client_cert_not_after": job.get("client_cert_not_after"),
        "raw_request_purged_at": job.get("raw_request_purged_at"),
        "raw_conversation_purged_at": job.get("raw_conversation_purged_at"),
        "job_id": job["job_id"],
    }
    # Keep human-readable submitter fields out of durable provenance. For
    # network MCP, SyncBatch identity is cert-bound and survives SQL loss.

    if graph_db.get_entity_by_uuid(sync_batch_uuid, track_access=False) is None:
        graph_db.create_entity(
            name=f"SyncBatch-{job['job_id']}",
            summary=f"Network sync batch for {job['job_id']}",
            labels=["SyncBatch"],
            attributes=attributes,
            source_interactions=[source_interaction_uuid] if source_interaction_uuid else [],
            source_hashes=[source_hash] if source_hash else [],
            source_chain=[{
                "source_uuid": source_interaction_uuid,
                "source_hash": source_hash,
                "source_type": "conversation",
            }] if source_interaction_uuid and source_hash else [],
            group_id=project_name,
            extraction_version=extraction.get("extraction_version", "v1.0.0"),
            extraction_commit=extraction.get("extraction_commit", f"sync-job-{job['job_id']}"),
            uuid=sync_batch_uuid,
            event_timestamp=event_timestamp,
            extraction_batch_uuid=extraction_batch_uuid,
        )
        graph_db.link_project_to_entity(project_name, sync_batch_uuid)

    relationship_specs = [("CREATES", created_entity_uuids), ("RELATED_TO", related_entity_uuids)]
    episodes = [source_interaction_uuid] if source_interaction_uuid else []
    episode_hashes = [source_hash] if source_hash else []
    valid_at = interaction["timestamp"] if interaction and interaction.get("timestamp") else event_timestamp
    derivation_version = extraction.get("extraction_version", "v1.0.0")
    derivation_commit = extraction.get("extraction_commit", f"sync-job-{job['job_id']}")

    for rel_name, target_uuids in relationship_specs:
        for target_uuid in target_uuids:
            if target_uuid == sync_batch_uuid:
                continue
            rel_uuid = _deterministic_uuid("rel", sync_batch_uuid, rel_name, target_uuid)
            if graph_db.get_relationship_by_uuid(rel_uuid) is not None:
                continue
            graph_db.create_relationship(
                source_uuid=sync_batch_uuid,
                target_uuid=target_uuid,
                relationship_name=rel_name,
                fact=f"SyncBatch {job['job_id']} {rel_name.lower()} {target_uuid}",
                group_id=project_name,
                episodes=episodes,
                episode_hashes=episode_hashes,
                derivation_version=derivation_version,
                derivation_commit=derivation_commit,
                valid_at=valid_at,
                uuid=rel_uuid,
                extraction_batch_uuid=extraction_batch_uuid,
            )

    return sync_batch_uuid


def process_job(sql_db: SQLDatabase, job: Dict[str, Any], config: Any, repo_root: str) -> bool:
    """Process a single sync job. Returns True on success, False on failure, None if paused."""
    job_id = job["job_id"]
    project_name = job["project_name"]
    python_path = get_python_path(config)

    try:
        request = json.loads(job["request_json"])
    except json.JSONDecodeError as e:
        fail_job(sql_db, job_id, "validation", f"Invalid request JSON: {e}")
        return False

    summary = request.get("summary", {})
    extraction = request.get("extraction", {})
    attachments = request.get("attachments", {})
    options = request.get("options", {})
    transport_type = job.get("transport_type") or "stdio"

    # Extract quality review settings
    skip_qc = options.get("skip_quality_check", False)
    quality_review_required = bool(job["quality_review_required"]) and not skip_qc

    # Create temp directory for job artifacts
    job_dir = Path(tempfile.gettempdir()) / "sync-jobs" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    # Check if this is a resumed job (has quality answers)
    quality_answers_file = job_dir / "quality-answers.json"
    is_resumed = quality_answers_file.exists()
    current_stage = job.get("stage", "submitted")

    # Track UUIDs locally (will be persisted and re-fetched for final result)
    source_interaction_uuid = job.get("source_interaction_uuid")
    extraction_batch_uuid = job.get("extraction_batch_uuid")
    created_entity_uuids: List[str] = []
    related_entity_uuids: List[str] = []

    if transport_type == "network":
        expected_hash = job.get("payload_hash")
        if not expected_hash:
            fail_job(sql_db, job_id, "integrity", "Network sync missing payload_hash")
            return False

        computed_hash = hashlib.sha256(
            canonicalize_sync_payload(summary, extraction, attachments, options).encode("utf-8")
        ).hexdigest()
        if computed_hash != expected_hash:
            fail_job(sql_db, job_id, "integrity", "Payload hash mismatch")
            return False
        sql_db.update_sync_job_status(job_id, payload_hash_verified=True)

    try:
        # Stage 1: Import summary (skip if resuming past this stage)
        if current_stage in ("submitted", "import_summary"):
            update_job_stage(sql_db, job_id, "import_summary")
            summary_file = job_dir / "summary.json"
            summary_file.write_text(json.dumps({"summary": summary}))

            success, stdout, stderr = run_subprocess(
                [python_path, "scripts/import_summary.py", "--project", project_name, "--file", str(summary_file)],
                cwd=repo_root,
            )
            if not success:
                fail_job(sql_db, job_id, "import_failure", f"Summary import failed: {stderr}")
                return False

            # Extract interaction UUID from output (format: uuid-XXXXXXXXXXXX)
            for line in stdout.split("\n"):
                # Look for uuid-XXXX format (12 hex chars after prefix)
                if "uuid-" in line.lower():
                    import re
                    match = re.search(r'uuid-[a-f0-9]{12}', line, re.IGNORECASE)
                    if match:
                        source_interaction_uuid = match.group(0)
                        break

            if source_interaction_uuid:
                sql_db.update_sync_job_status(job_id, source_interaction_uuid=source_interaction_uuid)

        # Stage 2: Validate extraction
        if current_stage in ("submitted", "import_summary", "validate_extraction"):
            update_job_stage(sql_db, job_id, "validate_extraction")
            ext_file = job_dir / "extraction.json"
            ext_file.write_text(json.dumps(extraction))

            success, stdout, stderr = run_subprocess(
                [python_path, "scripts/validate_extraction.py", "--file", str(ext_file)],
                cwd=repo_root,
            )
            if not success:
                fail_job(sql_db, job_id, "validation_failure", f"Extraction validation failed: {stderr}")
                return False

        # Stage 3: Quality review
        update_job_stage(sql_db, job_id, "quality_review")
        ext_file = job_dir / "extraction.json"
        if not ext_file.exists():
            ext_file.write_text(json.dumps(extraction))

        if quality_review_required and not is_resumed:
            # Pause job for quality review - set to waiting_for_quality_review
            log(f"Job {job_id}: Pausing for quality review")
            sql_db.update_sync_job_status(job_id, status="waiting_for_quality_review", stage="quality_review", progress=0.6)
            # Return None to indicate job is paused (not failed, not complete)
            return None

        # Stage 4: Store extraction
        update_job_stage(sql_db, job_id, "store_extraction")

        # Build store command with appropriate flags
        store_cmd = [python_path, "scripts/store_extraction.py", "--project", project_name, "--extraction-file", str(ext_file)]

        # IMPORTANT: Quality check behavior clarification
        # - The "skip_quality_check" option in the MCP API only controls whether the async
        #   job PAUSES for human quality review (waiting_for_quality_review state).
        # - It does NOT skip the actual quality validation inside store_extraction.py.
        # - AI agents cannot skip quality checks: --skip-quality-check is DEPRECATED, and
        #   --i-am-a-human-and-i-want-to-skip-quality-checks is explicitly forbidden for AI.
        # - If store_extraction.py runs its internal quality checks and they fail or require
        #   human input, the job will fail (not pause).
        # - To provide pre-computed quality answers, use --quality-answers-file.

        if is_resumed and quality_answers_file.exists():
            store_cmd.extend(["--quality-answers-file", str(quality_answers_file)])

        success, stdout, stderr = run_subprocess(store_cmd, cwd=repo_root)
        if not success:
            fail_job(sql_db, job_id, "store_failure", f"Extraction storage failed: {stderr}")
            return False

        # Extract extraction batch UUID from store output (format: batch-XXXXXXXXXXXX)
        # Output line looks like: "  Batch UUID: batch-4cf4c07d5102"
        import re
        for line in stdout.split("\n"):
            if "batch" in line.lower() and "uuid" in line.lower():
                match = re.search(r'batch-[a-f0-9]{12}', line, re.IGNORECASE)
                if match:
                    extraction_batch_uuid = match.group(0)
                    break

        if extraction_batch_uuid:
            sql_db.update_sync_job_status(job_id, extraction_batch_uuid=extraction_batch_uuid)

        created_entity_uuids, related_entity_uuids = _extract_created_entity_uuids(stdout)

        # Stage 5: Verification (optional)
        if options.get("run_verification", False):
            update_job_stage(sql_db, job_id, "verify")
            success, stdout, stderr = run_subprocess(
                [python_path, "scripts/query_memory.py", "--project", project_name, "--last", "3"],
                cwd=repo_root,
            )
            if not success:
                log(f"Job {job_id}: Verification warning: {stderr}", "WARN")

        if transport_type == "network":
            if not sql_db.purge_sync_job_raw_data(job_id):
                fail_job(sql_db, job_id, "privacy", "Failed to purge sync_jobs.request_json")
                return False

            raw_request_purged_at = sql_db.get_sync_job(job_id).get("raw_request_purged_at")

            raw_conversation_purged_at = None
            if source_interaction_uuid:
                if not sql_db.purge_interaction_content(source_interaction_uuid):
                    fail_job(sql_db, job_id, "privacy", f"Failed to purge interaction content for {source_interaction_uuid}")
                    return False
                raw_conversation_purged_at = datetime.utcnow().isoformat() + "Z"
                sql_db.update_sync_job_status(job_id, raw_conversation_purged_at=raw_conversation_purged_at)

            # Refresh job with purge metadata before durable provenance write.
            job = sql_db.get_sync_job(job_id)
            graph_db = GraphDatabase(config.get_graph_db_path(project_name))
            try:
                sync_batch_uuid = create_sync_batch_provenance(
                    sql_db=sql_db,
                    graph_db=graph_db,
                    job=job,
                    project_name=project_name,
                    extraction=extraction,
                    source_interaction_uuid=source_interaction_uuid,
                    extraction_batch_uuid=extraction_batch_uuid,
                    created_entity_uuids=created_entity_uuids,
                    related_entity_uuids=related_entity_uuids,
                )
            except Exception as exc:
                fail_job(sql_db, job_id, "provenance", f"Failed to create SyncBatch provenance: {exc}")
                return False
        else:
            sync_batch_uuid = None

        # Complete
        update_job_stage(sql_db, job_id, "done", status="complete")
        stages_completed = ["import_summary", "validate_extraction", "store_extraction"]
        if is_resumed:
            stages_completed.insert(2, "quality_review")
        result = {
            "source_interaction_uuid": source_interaction_uuid,
            "extraction_batch_uuid": extraction_batch_uuid,
            "sync_batch_uuid": sync_batch_uuid,
            "payload_hash_verified": bool(job.get("payload_hash_verified")),
            "transport_type": transport_type,
            "stages_completed": stages_completed,
            "quality_review_completed": is_resumed,
        }
        sql_db.store_sync_job_result(job_id, json.dumps(result))
        log(f"Job {job_id}: Completed successfully")
        return True

    except Exception as e:
        fail_job(sql_db, job_id, "internal", f"Unexpected error: {e}")
        return False


def fail_job(sql_db: SQLDatabase, job_id: str, error_type: str, message: str) -> None:
    """Mark a job as failed with error details."""
    error = {"type": error_type, "message": message}
    sql_db.store_sync_job_error(job_id, json.dumps(error))
    sql_db.update_sync_job_status(job_id, status="failed")
    log(f"Job {job_id}: Failed - {error_type}: {message}", "ERROR")


def worker_loop(
    sql_db: SQLDatabase,
    config: Any,
    repo_root: str,
    project_name: Optional[str] = None,
    poll_interval: float = 2.0,
    max_jobs: Optional[int] = None,
    once: bool = False,
) -> int:
    """Main worker loop. Returns number of jobs processed."""
    jobs_processed = 0

    # Reset stale jobs on startup
    reset_count = sql_db.reset_stale_sync_jobs(timeout_minutes=30)
    if reset_count > 0:
        log(f"Reset {reset_count} stale jobs to queued")

    while True:
        # Check max jobs limit
        if max_jobs is not None and jobs_processed >= max_jobs:
            log(f"Reached max jobs limit ({max_jobs})")
            break

        # Try to claim a job
        job = sql_db.claim_next_sync_job(project_name)

        if job:
            log(f"Claimed job {job['job_id']}")
            result = process_job(sql_db, job, config, repo_root)
            jobs_processed += 1

            if result is True:
                log(f"Job {job['job_id']} completed")
            elif result is None:
                log(f"Job {job['job_id']} paused for quality review")
            else:
                log(f"Job {job['job_id']} failed", "ERROR")

            # Immediate next poll after job completion
            if once:
                break
            continue

        # No job found
        if once:
            log("No jobs in queue (--once mode)")
            break

        # Wait before next poll
        time.sleep(poll_interval)

    return jobs_processed


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Process async sync jobs")
    parser.add_argument("--project", help="Project name filter (optional)")
    parser.add_argument("--config", help="Path to mem.config.json")
    parser.add_argument("--poll-interval", type=float, default=2.0, help="Seconds between polls (default: 2)")
    parser.add_argument("--max-jobs", type=int, help="Maximum jobs to process before exiting")
    parser.add_argument("--once", action="store_true", help="Process one job and exit")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    args = parser.parse_args(argv)

    # Load config
    try:
        config = load_config(config_path=args.config)
    except Exception as e:
        log(f"Failed to load config: {e}", "ERROR")
        return 1

    # Get project name from args or config
    project_name = args.project or config.get_project_name()

    # Get paths
    sql_db_path = config.get_sql_db_path()
    repo_root = str(Path(__file__).parent.parent)

    log(f"Starting sync job worker for project: {project_name or 'all'}")
    log(f"SQL database: {sql_db_path}")
    log(f"Poll interval: {args.poll_interval}s")

    sql_db = SQLDatabase(sql_db_path)

    try:
        jobs_processed = worker_loop(
            sql_db=sql_db,
            config=config,
            repo_root=repo_root,
            project_name=project_name,
            poll_interval=args.poll_interval,
            max_jobs=args.max_jobs,
            once=args.once,
        )
        log(f"Worker finished. Jobs processed: {jobs_processed}")
        return 0
    except KeyboardInterrupt:
        log("Worker interrupted by user")
        return 0
    except Exception as e:
        log(f"Worker error: {e}", "ERROR")
        return 1


if __name__ == "__main__":
    sys.exit(main())
