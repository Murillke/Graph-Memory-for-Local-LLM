"""MCP handlers for async sync job management."""

from __future__ import annotations

import json
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from tools.sql_db import SQLDatabase

from .common import (
    Response,
    fail,
    get_current_network_cert_metadata,
    load_runtime_state,
    ok,
    require_project,
)


# Valid statuses for sync jobs
VALID_STATUSES = {"queued", "running", "waiting_for_quality_review", "complete", "failed", "cancelled"}

# Progress mapping per stage
STAGE_PROGRESS = {
    "submitted": 0.0,
    "import_summary": 0.2,
    "validate_extraction": 0.4,
    "quality_review": 0.6,
    "store_extraction": 0.8,
    "verify": 0.95,
    "done": 1.0,
}


def _validate_sync_payload(payload: Dict[str, Any]) -> List[str]:
    """
    Validate the sync submission payload. Returns list of errors.

    Summary-first format ONLY. Legacy transcript format is not supported.
    """
    errors = []

    # Must be summary-first format
    if payload.get("schema_version") != "summary-first-v1":
        errors.append("schema_version must be 'summary-first-v1'. Legacy transcript format is not supported.")
        return errors

    # Required: summary object
    summary = payload.get("summary")
    if not summary:
        errors.append("Missing required 'summary' section")
        return errors

    # Required summary fields
    required_summary_fields = ["session_id", "timestamp", "intent", "work_attempted", "outcomes", "fidelity"]
    for field in required_summary_fields:
        if field not in summary:
            errors.append(f"summary.{field} is required")

    # Fidelity must not be 'full' or 'transcript'
    fidelity = summary.get("fidelity", "")
    if fidelity in ("full", "transcript"):
        errors.append(f"fidelity='{fidelity}' is not allowed. Use 'summary', 'paraphrased', or 'reconstructed'")

    # Required: extraction object
    if "extraction" not in payload:
        errors.append("Missing required 'extraction' section")
    else:
        ext = payload.get("extraction", {})
        if "extractions" not in ext:
            errors.append("extraction.extractions is required")

    # Options validation
    opts = payload.get("options", {})
    skip_qc = opts.get("skip_quality_check", False)
    require_qr = opts.get("require_quality_review", False)
    if skip_qc and require_qr:
        errors.append("skip_quality_check=true and require_quality_review=true is an invalid combination")

    return errors


def memory_sync_submit(
    summary: Dict[str, Any],
    extraction: Dict[str, Any],
    attachments: Optional[Dict[str, Any]] = None,
    options: Optional[Dict[str, Any]] = None,
    payload_hash: Optional[str] = None,
) -> Response:
    """
    Submit a sync payload for async processing. Returns job_id immediately.

    Summary-first format ONLY:
    - summary: {session_id, timestamp, intent, work_attempted, outcomes, fidelity}
    - extraction: {extractions: [...]}
    - attachments: optional, purged after extraction
    """
    options = options or {}

    # Build payload - summary-first only
    payload = {
        "schema_version": "summary-first-v1",
        "summary": summary,
        "extraction": extraction,
        "attachments": attachments or {},
        "options": options,
    }

    # Validate payload structure
    errors = _validate_sync_payload(payload)
    if errors:
        return fail("validation", "Invalid sync payload", errors=errors)

    try:
        state = load_runtime_state()
        project_name = require_project(state)
        sql_db = SQLDatabase(state.sql_db_path)
        mcp_config = getattr(state, "mcp_config", None)
        transport_type = "network" if getattr(mcp_config, "network_mode", None) == "private" else "stdio"

        if transport_type == "network" and not payload_hash:
            return fail("validation", "Network sync submission requires payload_hash")

        cert_metadata = get_current_network_cert_metadata() if transport_type == "network" else None
        cert_metadata = cert_metadata or {}
        fingerprint = cert_metadata.get("fingerprint")

        if transport_type == "network" and not fingerprint:
            return fail(
                "validation",
                "Network sync submission requires authoritative client certificate metadata",
            )

        # Check if fingerprint is banned (security enforcement)
        if transport_type == "network" and fingerprint:
            from mcp_server.security import (
                is_fingerprint_banned,
                sanitize_person_entities,
                record_violation,
            )
            from tools.graph_db import GraphDatabase

            graph_db = GraphDatabase(state.graph_db_path)
            is_banned, ban_expires, violation_count = is_fingerprint_banned(graph_db, fingerprint)

            if is_banned:
                return fail(
                    "security",
                    f"Certificate banned until {ban_expires.isoformat()} due to {violation_count} security violation(s)",
                )

            # Sanitize Person entities and detect spoofing
            extraction_data = extraction or {}
            sanitized_extraction, violations = sanitize_person_entities(extraction_data, fingerprint)

            if violations:
                # Record violations (durable in graph forever)
                for v in violations:
                    record_violation(graph_db, require_project(state), fingerprint, v)

                # Reject the submission
                return fail(
                    "security",
                    f"Identity spoofing detected: claimed identity does not match certificate. "
                    f"This violation has been recorded. You are now banned for {10 * (2 ** len(violations))} minutes.",
                )

            # Use sanitized extraction
            if extraction:
                extraction = sanitized_extraction

        # Generate job ID
        job_id = f"sync-job-{uuid.uuid4().hex[:12]}"

        # Determine quality review settings
        # NOTE: skip_quality_check only controls whether the job PAUSES for human review.
        # It does NOT skip the actual quality validation inside store_extraction.py.
        # AI agents cannot skip quality checks - that requires the human-only flag.
        skip_qc = options.get("skip_quality_check", False)
        require_qr = options.get("require_quality_review", True)
        quality_review_required = require_qr and not skip_qc

        # Create the job
        sql_db.create_sync_job(
            job_id=job_id,
            project_name=project_name,
            request_json=json.dumps(payload),
            payload_hash=payload_hash,
            transport_type=transport_type,
            client_cert_fingerprint=cert_metadata.get("fingerprint"),
            client_cert_subject=cert_metadata.get("subject"),
            client_cert_serial=cert_metadata.get("serial"),
            client_cert_issuer=cert_metadata.get("issuer"),
            client_cert_not_before=cert_metadata.get("not_before"),
            client_cert_not_after=cert_metadata.get("not_after"),
            # These remain SQL-only operational fields. Network provenance is
            # anchored to client_cert_fingerprint, not human-readable names.
            submitted_by_agent=options.get("submitted_by_agent"),
            submitted_by_model=options.get("submitted_by_model"),
            quality_review_required=quality_review_required,
            constrained_environment=options.get("constrained_environment", False),
        )

        return ok({
            "job_id": job_id,
            "status": "queued",
            "stage": "submitted",
            "progress": 0.0,
            "transport_type": transport_type,
            "message": "Sync job queued for processing",
        })

    except LookupError as exc:
        return fail("config", str(exc))
    except Exception as exc:
        return fail("internal", f"Failed to create sync job: {exc}")


def memory_sync_status(job_id: str) -> Response:
    """Get the current status of a sync job."""
    try:
        state = load_runtime_state()
        sql_db = SQLDatabase(state.sql_db_path)

        job = sql_db.get_sync_job(job_id)
        if not job:
            return fail("not_found", f"Sync job not found: {job_id}")

        return ok({
            "job_id": job["job_id"],
            "status": job["status"],
            "stage": job["stage"],
            "progress": job["progress"],
            "transport_type": job.get("transport_type"),
            "payload_hash_verified": bool(job.get("payload_hash_verified")),
            "raw_request_purged_at": job.get("raw_request_purged_at"),
            "raw_conversation_purged_at": job.get("raw_conversation_purged_at"),
            "created_at": job["created_at"],
            "started_at": job["started_at"],
            "completed_at": job["completed_at"],
            "updated_at": job["updated_at"],
        })

    except LookupError as exc:
        return fail("config", str(exc))
    except Exception as exc:
        return fail("internal", f"Failed to get job status: {exc}")


def memory_sync_result(job_id: str) -> Response:
    """Get the result of a completed sync job."""
    try:
        state = load_runtime_state()
        sql_db = SQLDatabase(state.sql_db_path)

        job = sql_db.get_sync_job(job_id)
        if not job:
            return fail("not_found", f"Sync job not found: {job_id}")

        # Check if job is terminal
        if job["status"] not in ("complete", "failed", "cancelled"):
            return fail(
                "validation",
                f"Job is not complete. Current status: {job['status']}",
            )

        # Parse result/error JSON
        result_data = None
        error_data = None
        if job["result_json"]:
            try:
                result_data = json.loads(job["result_json"])
            except json.JSONDecodeError:
                result_data = {"raw": job["result_json"]}
        if job["error_json"]:
            try:
                error_data = json.loads(job["error_json"])
            except json.JSONDecodeError:
                error_data = {"raw": job["error_json"]}

        return ok({
            "job_id": job["job_id"],
            "status": job["status"],
            "result": result_data,
            "error": error_data,
            "transport_type": job.get("transport_type"),
            "payload_hash": job.get("payload_hash"),
            "payload_hash_verified": bool(job.get("payload_hash_verified")),
            "client_cert_fingerprint": job.get("client_cert_fingerprint"),
            "client_cert_subject": job.get("client_cert_subject"),
            "source_interaction_uuid": job["source_interaction_uuid"],
            "extraction_batch_uuid": job["extraction_batch_uuid"],
            "created_at": job["created_at"],
            "completed_at": job["completed_at"],
        })

    except LookupError as exc:
        return fail("config", str(exc))
    except Exception as exc:
        return fail("internal", f"Failed to get job result: {exc}")


def memory_sync_list(
    status: Optional[str] = None,
    limit: int = 20,
) -> Response:
    """List sync jobs for the current project."""
    # Validate status if provided
    if status and status not in VALID_STATUSES:
        return fail("validation", f"Invalid status filter: {status}")

    try:
        state = load_runtime_state()
        project_name = require_project(state)
        sql_db = SQLDatabase(state.sql_db_path)

        jobs = sql_db.list_sync_jobs(project_name, status=status, limit=limit)

        # Build summary list
        job_list = []
        for job in jobs:
            job_list.append({
                "job_id": job["job_id"],
                "status": job["status"],
                "stage": job["stage"],
                "progress": job["progress"],
                "transport_type": job.get("transport_type"),
                "created_at": job["created_at"],
                "updated_at": job["updated_at"],
            })

        return ok({
            "project_name": project_name,
            "count": len(job_list),
            "jobs": job_list,
        })

    except LookupError as exc:
        return fail("config", str(exc))
    except Exception as exc:
        return fail("internal", f"Failed to list sync jobs: {exc}")


def memory_sync_submit_quality_review(
    job_id: str,
    answers: Dict[str, Any],
) -> Response:
    """Submit quality review answers for a paused job, allowing it to resume."""
    try:
        state = load_runtime_state()
        sql_db = SQLDatabase(state.sql_db_path)

        job = sql_db.get_sync_job(job_id)
        if not job:
            return fail("not_found", f"Sync job not found: {job_id}")

        # Verify job is in correct state
        if job["status"] != "waiting_for_quality_review":
            return fail(
                "validation",
                f"Job is not waiting for quality review. Current status: {job['status']}",
            )

        # Write answers to job's temp directory
        job_dir = Path(tempfile.gettempdir()) / "sync-jobs" / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        answers_file = job_dir / "quality-answers.json"
        answers_file.write_text(json.dumps(answers))

        # Transition job from waiting_for_quality_review -> queued
        # Worker will pick it up on next poll and resume from quality_review stage
        sql_db.update_sync_job_status(job_id, status="queued")

        return ok({
            "job_id": job_id,
            "status": "queued",
            "message": "Quality review answers submitted. Job will resume on next worker poll.",
        })

    except LookupError as exc:
        return fail("config", str(exc))
    except Exception as exc:
        return fail("internal", f"Failed to submit quality review: {exc}")


def handle_claim_authorship(
    target_uuid: str,
    claim_type: str = "authored",
    signature: Optional[str] = None,
    claim_timestamp: Optional[str] = None,
) -> Response:
    """
    Submit a signed authorship claim for an entity or fact.

    The client must sign the claim with their private key to prove ownership.

    Flow:
    1. Client creates claim: {"target_uuid": "...", "claim_type": "authored", "timestamp": "..."}
    2. Client signs canonical JSON with private key
    3. Client submits claim + signature here
    4. Server verifies signature against cert's public key
    5. Server stores AuthorshipClaim in graph (permanent)

    Args:
        target_uuid: UUID of entity or fact being claimed
        claim_type: Type of claim (default: "authored")
        signature: Base64-encoded signature of the claim
        claim_timestamp: ISO timestamp of when claim was made

    Returns:
        Response with claim_uuid if successful
    """
    try:
        state = load_runtime_state()

        # Get transport type
        transport_type = "stdio"
        if state.network_cert_ctx_var:
            cert_metadata = get_current_network_cert_metadata()
            if cert_metadata and cert_metadata.get("fingerprint"):
                transport_type = "network"

        # Authorship claims require network transport with cert
        if transport_type != "network":
            return fail(
                "validation",
                "Authorship claims require network transport with client certificate",
            )

        cert_metadata = get_current_network_cert_metadata() or {}
        fingerprint = cert_metadata.get("fingerprint")

        if not fingerprint:
            return fail(
                "validation",
                "No client certificate fingerprint available",
            )

        if not signature:
            return fail(
                "validation",
                "Signature required for authorship claim",
            )

        # Build the claim
        from mcp_server.security import verify_and_store_authorship_claim
        from tools.graph_db import GraphDatabase

        claim = {
            "target_uuid": target_uuid,
            "claim_type": claim_type,
            "timestamp": claim_timestamp or datetime.now(timezone.utc).isoformat(),
        }

        # Get cert PEM if available for verification
        cert_pem = cert_metadata.get("cert_pem")
        if isinstance(cert_pem, str):
            cert_pem = cert_pem.encode()

        graph_db = GraphDatabase(state.graph_db_path)
        success, message, claim_uuid = verify_and_store_authorship_claim(
            graph_db=graph_db,
            project_name=require_project(state),
            claim=claim,
            signature_b64=signature,
            cert_fingerprint=fingerprint,
            cert_pem=cert_pem,
        )

        if not success:
            return fail("validation", message)

        return ok({
            "claim_uuid": claim_uuid,
            "target_uuid": target_uuid,
            "claimant_fingerprint": fingerprint[:12],
            "message": message,
        })

    except LookupError as exc:
        return fail("config", str(exc))
    except Exception as exc:
        return fail("internal", f"Failed to submit authorship claim: {exc}")


def handle_get_authorship_claims(target_uuid: str) -> Response:
    """
    Get all authorship claims for a target entity or fact.

    Args:
        target_uuid: UUID of entity or fact

    Returns:
        Response with list of claims
    """
    try:
        state = load_runtime_state()

        from mcp_server.security import get_authorship_claims
        from tools.graph_db import GraphDatabase

        graph_db = GraphDatabase(state.graph_db_path)
        claims = get_authorship_claims(graph_db, target_uuid)

        return ok({
            "target_uuid": target_uuid,
            "claims": claims,
            "count": len(claims),
        })

    except LookupError as exc:
        return fail("config", str(exc))
    except Exception as exc:
        return fail("internal", f"Failed to get authorship claims: {exc}")
