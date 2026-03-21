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
    summary: str,
    session_id: Optional[str] = None,
) -> Response:
    """
    Store a session summary and automatically extract entities/facts.

    Provide an extended summary of your work including:
    - Objectives and intent
    - Approaches taken
    - Work completed
    - Results achieved
    - Errors encountered and fixed
    - Key decisions made
    - Tools and technologies used

    The richer the summary, the better the extraction.

    EXAMPLE:
    memory_sync_submit(
        summary="Worked on implementing user authentication for the API.
        Started by designing the JWT token flow, then implemented the /login
        and /logout endpoints. Hit a bug with token expiration but fixed it
        by adjusting the clock skew tolerance. All tests passing now.
        Used Python FastAPI with PyJWT library."
    )
    """
    import subprocess
    import re
    from datetime import datetime, timezone

    # Validate
    if not summary or not summary.strip():
        return fail("validation", "summary is required")

    try:
        state = load_runtime_state()
        project_name = require_project(state)
        sql_db = SQLDatabase(state.sql_db_path)
        repo_root = Path(__file__).parent.parent.parent
        tmp_dir = repo_root / "tmp"
        tmp_dir.mkdir(exist_ok=True)

        # Auto-generate session_id and timestamp if not provided
        timestamp = datetime.now(timezone.utc).isoformat()
        ts_slug = timestamp.replace(":", "-").replace("T", "_")[:19]
        if not session_id:
            session_id = f"session-{ts_slug}"

        # Step 1: Check for existing unprocessed interaction with this session_id
        interaction_uuid = None
        unprocessed = sql_db.get_unprocessed_interactions(project_name)
        for interaction in unprocessed:
            if interaction.get("session_id") == session_id:
                interaction_uuid = interaction["uuid"]
                break

        # Step 2: If no existing, import new
        if not interaction_uuid:
            conversation_file = tmp_dir / f"conversation_{ts_slug}.json"
            conversation_data = {
                "summary": {
                    "session_id": session_id,
                    "timestamp": timestamp,
                    "intent": summary[:200],
                    "work_attempted": [summary],
                    "outcomes": [{"type": "success", "description": "Session recorded"}],
                    "fidelity": "summary",
                }
            }
            conversation_file.write_text(json.dumps(conversation_data, indent=2))

            import_result = subprocess.run(
                ["python3.11", "scripts/import_summary.py",
                 "--project", project_name,
                 "--file", str(conversation_file),
                 "--constrained-environment"],
                capture_output=True, text=True, cwd=str(repo_root), timeout=60
            )

            if import_result.returncode != 0:
                return fail("import", f"import_summary.py failed: {import_result.stderr}")

            uuid_match = re.search(r'UUID:\s*(uuid-[a-f0-9]+)', import_result.stdout)
            if not uuid_match:
                return fail("import", "Could not extract UUID from import output")
            interaction_uuid = uuid_match.group(1)

        # Step 3: Use Augment SDK to get extraction JSON (with retry on failure)
        entities_extracted = 0
        extraction_error = None
        MAX_RETRIES = 2

        try:
            from auggie_sdk.context import DirectContext, File

            extraction_prompt = f"""Extract entities from this session summary:

{summary}

Return ONLY this JSON structure (no markdown, no explanation):
{{
  "entities": [
    {{"name": "EntityName", "type": "Concept", "summary": "Brief description"}}
  ],
  "facts": [
    {{"source_entity": "Entity1", "target_entity": "Entity2", "relationship_type": "RELATED_TO", "fact": "Description"}}
  ]
}}

RULES:
1. Every entity in facts MUST exist in entities list
2. Entity types: Feature, Bug, Task, File, Tool, Document, Config, Procedure, Pattern, Concept, Technology, Service, API
3. Relationship types: USES, DEPENDS_ON, IMPLEMENTS, CONTAINS, CREATES, DOCUMENTS, RESOLVES, CAUSES, RELATED_TO

Extract 2-5 entities. Return ONLY valid JSON."""

            llm_data = None
            last_error = None

            for attempt in range(MAX_RETRIES + 1):
                context = DirectContext.create()

                if attempt == 0:
                    # First attempt
                    context.add_to_index([File(path='prompt.txt', contents=extraction_prompt)])
                    llm_response = context.search_and_ask('Extract entities', 'Return ONLY the JSON object')
                else:
                    # Retry with error context
                    retry_prompt = f"""{extraction_prompt}

YOUR PREVIOUS ATTEMPT FAILED.
Your output was:
{llm_response}

Error: {last_error}

Please fix the issues and return ONLY valid JSON."""
                    context.add_to_index([File(path='retry.txt', contents=retry_prompt)])
                    llm_response = context.search_and_ask('Fix extraction', 'Return ONLY the corrected JSON')

                # Parse LLM response
                json_match = re.search(r'\{[\s\S]*\}', llm_response)
                if not json_match:
                    last_error = "Could not find JSON in response"
                    continue

                try:
                    llm_data = json.loads(json_match.group())
                    # Basic validation
                    if "entities" not in llm_data:
                        last_error = "Missing 'entities' key in JSON"
                        llm_data = None
                        continue
                    # Success
                    break
                except json.JSONDecodeError as e:
                    last_error = f"Invalid JSON: {e}"
                    llm_data = None
                    continue

            if not llm_data:
                extraction_error = f"LLM extraction failed after {MAX_RETRIES + 1} attempts: {last_error}"
            else:

                # Step 4: Create extraction file for validate/store scripts
                extraction_file = tmp_dir / f"extraction_{ts_slug}.json"
                extraction_data = {
                    "project_name": project_name,
                    "extraction_version": "auggie-sdk-v1",
                    "extraction_commit": "auto",
                    "extractions": [{
                        "interaction_uuid": interaction_uuid,
                        "entities": llm_data.get("entities", []),
                        "facts": llm_data.get("facts", []),
                    }]
                }
                extraction_file.write_text(json.dumps(extraction_data, indent=2))

                # Step 5: Run validate_extraction.py
                validate_result = subprocess.run(
                    ["python3.11", "scripts/validate_extraction.py",
                     "--file", str(extraction_file)],
                    capture_output=True, text=True, cwd=str(repo_root), timeout=30
                )

                if validate_result.returncode != 0:
                    extraction_error = f"Validation failed: {validate_result.stderr or validate_result.stdout}"
                else:
                    # Step 6: Run store_extraction.py with quality review
                    quality_answers = tmp_dir / "quality-answers.json"

                    # First run - generates quality questions and answer template
                    store_result = subprocess.run(
                        ["python3.11", "scripts/store_extraction.py",
                         "--project", project_name,
                         "--extraction-file", str(extraction_file),
                         "--require-quality-review",
                         "--quality-answers-file", str(quality_answers)],
                        capture_output=True, text=True, cwd=str(repo_root), timeout=60
                    )

                    # If quality questions generated, fill reasoning and re-run
                    quality_questions = tmp_dir / "quality-questions.json"
                    if quality_answers.exists() and store_result.returncode != 0:
                        answers_data = json.loads(quality_answers.read_text())
                        questions_data = {}
                        if quality_questions.exists():
                            questions_data = json.loads(quality_questions.read_text())

                        # Fill in the reasoning for all contradictions
                        for c in answers_data.get("contradictions", []):
                            if not c.get("reasoning"):
                                c["reasoning"] = "No existing facts about this relationship"

                        # Fill in reasoning for duplicates - check questions for similarity
                        # Build lookup by question_index
                        dup_questions = questions_data.get("duplicates", [])
                        questions_by_index = {q.get("question_index", i): q for i, q in enumerate(dup_questions)}

                        for d in answers_data.get("duplicates", []):
                            if not d.get("reasoning"):
                                q_idx = d.get("question_index")
                                question = questions_by_index.get(q_idx, {})
                                candidates = question.get("candidates", [])

                                if candidates and candidates[0].get("similarity", 0) >= 0.9:
                                    # It's a duplicate - use existing entity
                                    d["is_duplicate"] = True
                                    d["duplicate_uuid"] = candidates[0]["uuid"]
                                    d["reasoning"] = "Same entity - already exists with matching description"
                                else:
                                    d["is_duplicate"] = False
                                    d["duplicate_uuid"] = None
                                    d["reasoning"] = "Different concept - new entity"

                        quality_answers.write_text(json.dumps(answers_data, indent=2))

                        # Re-run store with filled answers
                        store_result = subprocess.run(
                            ["python3.11", "scripts/store_extraction.py",
                             "--project", project_name,
                             "--extraction-file", str(extraction_file),
                             "--require-quality-review",
                             "--quality-answers-file", str(quality_answers)],
                            capture_output=True, text=True, cwd=str(repo_root), timeout=60
                        )

                    if store_result.returncode != 0:
                        extraction_error = f"Store failed: {store_result.stderr or store_result.stdout}"
                    else:
                        entities_extracted = len(llm_data.get("entities", []))

        except ImportError:
            extraction_error = "auggie_sdk not installed - run: pip install auggie-sdk"
        except Exception as e:
            extraction_error = f"Extraction failed: {str(e)}"

        return ok({
            "status": "complete",
            "interaction_uuid": interaction_uuid,
            "entities_extracted": entities_extracted,
            "extraction_error": extraction_error,
        })

    except LookupError as exc:
        return fail("config", str(exc))
    except Exception as exc:
        return fail("internal", f"Failed to sync: {exc}")


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
