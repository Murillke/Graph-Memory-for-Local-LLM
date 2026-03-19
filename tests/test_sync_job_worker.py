"""Tests for sync job worker process."""

from __future__ import annotations

import sys

# Python 3.10+ required for mcp package
if sys.version_info < (3, 10):
    sys.exit(
        "ERROR: MCP tests require Python 3.10+.\n"
        "Current: Python {}.{}\n"
        "Fix: Update mem.config.json python_path to python3.11".format(
            sys.version_info.major, sys.version_info.minor
        )
    )

import json
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Setup path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tools.sql_db import SQLDatabase


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test.db")
    sql_db = SQLDatabase(db_path)
    sql_db.create_project("test_project", "Test project")
    yield sql_db, temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


class TestStaleJobRecovery:
    """Tests for stale job recovery."""

    def test_reset_stale_jobs(self, temp_db):
        """Test resetting stale running jobs."""
        sql_db, _ = temp_db
        
        # Create a job and manually set it to running with old timestamp
        sql_db.create_sync_job(job_id="stale-job", project_name="test_project", request_json="{}")
        
        # Claim it
        sql_db.claim_next_sync_job("test_project")
        
        # Manually set old updated_at to simulate stale job
        from datetime import datetime, timedelta
        old_time = (datetime.utcnow() - timedelta(minutes=60)).isoformat() + "Z"
        conn = sql_db._get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE sync_jobs SET updated_at = ? WHERE job_id = ?", (old_time, "stale-job"))
        conn.commit()
        conn.close()
        
        # Reset stale jobs
        count = sql_db.reset_stale_sync_jobs(timeout_minutes=30)
        assert count == 1
        
        # Verify job is back to queued
        job = sql_db.get_sync_job("stale-job")
        assert job["status"] == "queued"


class TestJobEvents:
    """Tests for job event tracking."""

    def test_events_recorded_on_create(self, temp_db):
        """Test that events are recorded when job is created."""
        sql_db, _ = temp_db
        
        sql_db.create_sync_job(job_id="job-1", project_name="test_project", request_json="{}")
        
        events = sql_db.get_sync_job_events("job-1")
        assert len(events) >= 1
        assert events[0]["event_type"] == "created"

    def test_events_recorded_on_claim(self, temp_db):
        """Test that events are recorded when job is claimed."""
        sql_db, _ = temp_db
        
        sql_db.create_sync_job(job_id="job-1", project_name="test_project", request_json="{}")
        sql_db.claim_next_sync_job("test_project")
        
        events = sql_db.get_sync_job_events("job-1")
        assert len(events) >= 2
        event_types = [e["event_type"] for e in events]
        assert "claimed" in event_types


def _make_summary_first_payload(
    session_id: str = "test-session",
    intent: str = "Test intent",
    work_attempted: list = None,
    outcomes: list = None,
    extractions: list = None,
    options: dict = None,
) -> dict:
    """Helper to create valid summary-first payloads for tests."""
    return {
        "schema_version": "summary-first-v1",
        "summary": {
            "session_id": session_id,
            "timestamp": "2026-03-18T12:00:00Z",
            "intent": intent,
            "work_attempted": work_attempted or ["Test work"],
            "outcomes": [{"type": "success", "description": "Test passed"}] if outcomes is None else outcomes,
            "fidelity": "summary",
        },
        "extraction": {"extractions": extractions or []},
        "options": options or {},
    }


class TestPayloadValidation:
    """Tests for payload validation in handlers."""

    def test_valid_summary_first_payload(self):
        """Test that valid summary-first payload passes validation."""
        from mcp_server.handlers.sync import _validate_sync_payload

        payload = _make_summary_first_payload()

        errors = _validate_sync_payload(payload)
        assert len(errors) == 0

    def test_missing_schema_version_rejected(self):
        """Test that missing schema_version is rejected."""
        from mcp_server.handlers.sync import _validate_sync_payload

        payload = {
            "summary": {"session_id": "x", "timestamp": "x", "intent": "x", "work_attempted": [], "outcomes": [], "fidelity": "summary"},
            "extraction": {"extractions": []},
        }

        errors = _validate_sync_payload(payload)
        assert any("schema_version" in e.lower() for e in errors)

    def test_legacy_format_rejected(self):
        """Test that legacy transcript format is rejected."""
        from mcp_server.handlers.sync import _validate_sync_payload

        payload = {
            "conversation": {"exchanges": [{"user": "hi", "assistant": "hello"}]},
            "extraction": {"extractions": []},
        }

        errors = _validate_sync_payload(payload)
        assert any("schema_version" in e.lower() or "legacy" in e.lower() for e in errors)

    def test_missing_summary_rejected(self):
        """Test that missing summary is rejected."""
        from mcp_server.handlers.sync import _validate_sync_payload

        payload = {
            "schema_version": "summary-first-v1",
            "extraction": {"extractions": []},
        }

        errors = _validate_sync_payload(payload)
        assert any("summary" in e.lower() for e in errors)

    def test_missing_extraction(self):
        """Test that missing extraction is rejected."""
        from mcp_server.handlers.sync import _validate_sync_payload

        payload = {
            "schema_version": "summary-first-v1",
            "summary": {"session_id": "x", "timestamp": "x", "intent": "x", "work_attempted": [], "outcomes": [], "fidelity": "summary"},
        }

        errors = _validate_sync_payload(payload)
        assert any("extraction" in e.lower() for e in errors)

    def test_contradictory_quality_flags(self):
        """Test that contradictory quality flags are rejected."""
        from mcp_server.handlers.sync import _validate_sync_payload

        payload = _make_summary_first_payload(options={
            "skip_quality_check": True,
            "require_quality_review": True,
        })

        errors = _validate_sync_payload(payload)
        assert any("invalid combination" in e.lower() for e in errors)

    def test_fidelity_full_rejected(self):
        """Test that fidelity='full' is rejected in summary-first."""
        from mcp_server.handlers.sync import _validate_sync_payload

        payload = _make_summary_first_payload()
        payload["summary"]["fidelity"] = "full"

        errors = _validate_sync_payload(payload)
        assert any("fidelity" in e.lower() for e in errors)

    def test_fidelity_transcript_rejected(self):
        """Test that fidelity='transcript' is rejected in summary-first."""
        from mcp_server.handlers.sync import _validate_sync_payload

        payload = _make_summary_first_payload()
        payload["summary"]["fidelity"] = "transcript"

        errors = _validate_sync_payload(payload)
        assert any("fidelity" in e.lower() for e in errors)

    def test_network_sync_submit_requires_payload_hash(self, temp_db):
        """Network sync submissions must include payload_hash."""
        sql_db, _ = temp_db
        from mcp_server.handlers.sync import memory_sync_submit

        mock_state = MagicMock()
        mock_state.project_name = "test_project"
        mock_state.sql_db_path = sql_db.db_path
        mock_state.mcp_config = MagicMock(network_mode="private")

        payload = _make_summary_first_payload()
        with patch("mcp_server.handlers.sync.load_runtime_state", return_value=mock_state):
            response = memory_sync_submit(
                summary=payload["summary"],
                extraction=payload["extraction"],
                options={},
            )

        assert response["status"] == "error"
        assert response["type"] == "validation"
        assert "payload_hash" in response["message"]

    def test_network_sync_submit_requires_client_cert_fingerprint(self, temp_db):
        """Network sync submissions must include authoritative cert identity."""
        sql_db, _ = temp_db
        from mcp_server.handlers.sync import memory_sync_submit

        mock_state = MagicMock()
        mock_state.project_name = "test_project"
        mock_state.sql_db_path = sql_db.db_path
        mock_state.mcp_config = MagicMock(network_mode="private")

        payload = _make_summary_first_payload()
        with patch("mcp_server.handlers.sync.load_runtime_state", return_value=mock_state):
            response = memory_sync_submit(
                summary=payload["summary"],
                extraction=payload["extraction"],
                options={},
                payload_hash="abc123",
            )

        assert response["status"] == "error"
        assert response["type"] == "validation"
        assert "client certificate metadata" in response["message"]


class TestProgressMapping:
    """Tests for stage-to-progress mapping."""

    def test_stage_progress_values(self):
        """Test that all stages have valid progress values."""
        from mcp_server.handlers.sync import STAGE_PROGRESS

        assert STAGE_PROGRESS["submitted"] == 0.0
        assert STAGE_PROGRESS["import_summary"] == 0.2
        assert STAGE_PROGRESS["validate_extraction"] == 0.4
        assert STAGE_PROGRESS["quality_review"] == 0.6
        assert STAGE_PROGRESS["store_extraction"] == 0.8
        assert STAGE_PROGRESS["verify"] == 0.95
        assert STAGE_PROGRESS["done"] == 1.0


class TestPythonPathUsage:
    """Tests for configured Python path usage."""

    def test_get_python_path_from_config(self):
        """Test that worker reads Python path from config."""
        from scripts.process_sync_jobs import get_python_path

        # Mock config with python_path
        mock_config = MagicMock()
        mock_config.get_python_path.return_value = "python3.11"

        path = get_python_path(mock_config)
        assert path == "python3.11"

    def test_get_python_path_fallback(self):
        """Test fallback when config has no python_path method."""
        from scripts.process_sync_jobs import get_python_path

        # Mock config without get_python_path
        mock_config = MagicMock(spec=[])

        path = get_python_path(mock_config)
        assert path == "python3"


class TestQualityReviewPause:
    """Tests for quality review pause behavior."""

    def test_job_pauses_when_quality_review_required(self, temp_db):
        """Test that process_job() returns None and sets waiting_for_quality_review."""
        sql_db, temp_dir = temp_db

        # Import process_job
        from scripts.process_sync_jobs import process_job

        # Create job with quality review required
        request = _make_summary_first_payload(options={"skip_quality_check": False})
        sql_db.create_sync_job(
            job_id="qr-job",
            project_name="test_project",
            request_json=json.dumps(request),
            quality_review_required=True,
        )

        # Claim the job
        job = sql_db.claim_next_sync_job("test_project")
        assert job is not None

        # Mock config and subprocess to avoid real execution
        mock_config = MagicMock()
        mock_config.get_python_path.return_value = "python3"

        with patch("scripts.process_sync_jobs.run_subprocess") as mock_subprocess:
            # Mock successful import and validation stages (use production UUID format)
            mock_subprocess.return_value = (True, "Created interaction: uuid-71a9e013410a", "")

            # Process the job - should pause at quality review
            result = process_job(sql_db, job, mock_config, temp_dir)

        # Verify job paused (returns None)
        assert result is None

        # Verify job status is waiting_for_quality_review
        job = sql_db.get_sync_job("qr-job")
        assert job["status"] == "waiting_for_quality_review"
        assert job["stage"] == "quality_review"

    def test_job_skips_quality_review_when_flag_set(self, temp_db):
        """Test that process_job() completes without pausing when skip_quality_check is true."""
        sql_db, temp_dir = temp_db

        from scripts.process_sync_jobs import process_job

        request = _make_summary_first_payload(options={"skip_quality_check": True})
        sql_db.create_sync_job(
            job_id="skip-qr-job",
            project_name="test_project",
            request_json=json.dumps(request),
            quality_review_required=False,
        )

        job = sql_db.claim_next_sync_job("test_project")
        assert job is not None

        mock_config = MagicMock()
        mock_config.get_python_path.return_value = "python3"

        with patch("scripts.process_sync_jobs.run_subprocess") as mock_subprocess:
            # Use production batch UUID format for store output
            mock_subprocess.return_value = (True, "  Batch UUID: batch-4cf4c07d5102", "")
            result = process_job(sql_db, job, mock_config, temp_dir)

        # Verify job completed (returns True, not None)
        assert result is True

        job = sql_db.get_sync_job("skip-qr-job")
        assert job["status"] == "complete"

    def test_quality_review_resume_via_mcp_tool(self, temp_db):
        """Test that memory_sync_submit_quality_review moves job to queued."""
        sql_db, temp_dir = temp_db

        # Create a job already in waiting_for_quality_review state
        request = _make_summary_first_payload()
        sql_db.create_sync_job(
            job_id="paused-job",
            project_name="test_project",
            request_json=json.dumps(request),
            quality_review_required=True,
        )
        sql_db.update_sync_job_status("paused-job", status="waiting_for_quality_review", stage="quality_review")

        # Mock the MCP handler's runtime state
        from mcp_server.handlers.sync import memory_sync_submit_quality_review

        mock_state = MagicMock()
        mock_state.sql_db_path = sql_db.db_path

        with patch("mcp_server.handlers.sync.load_runtime_state", return_value=mock_state):
            response = memory_sync_submit_quality_review(
                job_id="paused-job",
                answers={"quality_ok": True},
            )

        # Verify response is OK
        assert response["status"] == "ok"
        assert response["data"]["status"] == "queued"

        # Verify job is now queued (ready for worker pickup)
        job = sql_db.get_sync_job("paused-job")
        assert job["status"] == "queued"

    def test_full_pause_resume_path_with_quality_answers_file(self, temp_db):
        """Test full pause -> submit answers -> resume -> verify --quality-answers-file is passed."""
        sql_db, temp_dir = temp_db

        import uuid as uuid_module
        from pathlib import Path

        from scripts.process_sync_jobs import process_job
        from mcp_server.handlers.sync import memory_sync_submit_quality_review

        # Use unique job ID to avoid collision with previous test artifacts
        job_id = f"full-resume-job-{uuid_module.uuid4().hex[:8]}"

        # Clean up any stale artifacts from previous runs
        job_dir = Path(tempfile.gettempdir()) / "sync-jobs" / job_id
        if job_dir.exists():
            shutil.rmtree(job_dir)

        request = _make_summary_first_payload(options={"skip_quality_check": False})
        sql_db.create_sync_job(
            job_id=job_id,
            project_name="test_project",
            request_json=json.dumps(request),
            quality_review_required=True,
        )

        # Step 1: Claim and process - should pause
        job = sql_db.claim_next_sync_job("test_project")
        mock_config = MagicMock()
        mock_config.get_python_path.return_value = "python3"

        with patch("scripts.process_sync_jobs.run_subprocess") as mock_subprocess:
            # Use production UUID format
            mock_subprocess.return_value = (True, "Created interaction: uuid-bea2fc3b8eef", "")
            result = process_job(sql_db, job, mock_config, temp_dir)

        assert result is None  # Paused
        job = sql_db.get_sync_job(job_id)
        assert job["status"] == "waiting_for_quality_review"

        # Step 2: Submit quality review answers via MCP tool
        mock_state = MagicMock()
        mock_state.sql_db_path = sql_db.db_path

        with patch("mcp_server.handlers.sync.load_runtime_state", return_value=mock_state):
            response = memory_sync_submit_quality_review(
                job_id=job_id,
                answers={"approved": True, "notes": "Looks good"},
            )

        assert response["status"] == "ok"
        job = sql_db.get_sync_job(job_id)
        assert job["status"] == "queued"

        # Step 3: Re-claim and process - should resume and pass --quality-answers-file
        job = sql_db.claim_next_sync_job("test_project")
        assert job is not None
        assert job["job_id"] == job_id

        captured_commands = []
        def capture_subprocess(cmd, cwd, timeout=300):
            captured_commands.append(cmd)
            # Use production batch UUID format
            return (True, "  Batch UUID: batch-9f8e7d6c5b4a", "")

        with patch("scripts.process_sync_jobs.run_subprocess", side_effect=capture_subprocess):
            result = process_job(sql_db, job, mock_config, temp_dir)

        # Verify job completed
        assert result is True
        job = sql_db.get_sync_job(job_id)
        assert job["status"] == "complete"

        # Verify --quality-answers-file was passed to store_extraction
        store_cmds = [cmd for cmd in captured_commands if "store_extraction.py" in str(cmd)]
        assert len(store_cmds) >= 1
        store_cmd = store_cmds[0]
        assert "--quality-answers-file" in store_cmd

        # Verify the answers file path is in the command
        answers_file_idx = store_cmd.index("--quality-answers-file")
        answers_file_path = store_cmd[answers_file_idx + 1]
        assert "quality-answers.json" in answers_file_path


class TestProductionUuidFormats:
    """Tests for production UUID format parsing."""

    def test_parses_uuid_prefix_format(self, temp_db):
        """Test that worker parses uuid-XXXXXXXXXXXX format correctly."""
        sql_db, temp_dir = temp_db

        from scripts.process_sync_jobs import process_job

        request = _make_summary_first_payload(options={"skip_quality_check": True})
        sql_db.create_sync_job(
            job_id="uuid-format-test",
            project_name="test_project",
            request_json=json.dumps(request),
            quality_review_required=False,
        )

        job = sql_db.claim_next_sync_job("test_project")
        mock_config = MagicMock()
        mock_config.get_python_path.return_value = "python3"

        with patch("scripts.process_sync_jobs.run_subprocess") as mock_subprocess:
            def return_production_output(cmd, cwd, timeout=300):
                if "import_summary" in str(cmd):
                    return (True, "Created interaction: uuid-71a9e013410a\nDone.", "")
                elif "store_extraction" in str(cmd):
                    return (True, "  Batch UUID: batch-4cf4c07d5102\n[OK]", "")
                return (True, "", "")

            mock_subprocess.side_effect = return_production_output
            result = process_job(sql_db, job, mock_config, temp_dir)

        assert result is True

        # Verify production-format UUIDs were captured
        job = sql_db.get_sync_job("uuid-format-test")
        assert job["source_interaction_uuid"] == "uuid-71a9e013410a"
        assert job["extraction_batch_uuid"] == "batch-4cf4c07d5102"

        # Verify result JSON also has them
        result_data = json.loads(job["result_json"])
        assert result_data["source_interaction_uuid"] == "uuid-71a9e013410a"
        assert result_data["extraction_batch_uuid"] == "batch-4cf4c07d5102"

    def test_skip_quality_check_does_not_pass_human_flag(self, temp_db):
        """Test that skip_quality_check=True does NOT pass the human-only flag.

        NOTE: skip_quality_check only controls whether the job pauses for human review.
        It does NOT skip actual quality validation inside store_extraction.py.
        AI agents cannot skip quality checks - that requires the human-only flag.
        """
        sql_db, temp_dir = temp_db

        from scripts.process_sync_jobs import process_job

        request = _make_summary_first_payload(options={"skip_quality_check": True})
        sql_db.create_sync_job(
            job_id="skip-flag-test",
            project_name="test_project",
            request_json=json.dumps(request),
            quality_review_required=False,  # This is what skip_quality_check actually affects
        )

        job = sql_db.claim_next_sync_job("test_project")
        mock_config = MagicMock()
        mock_config.get_python_path.return_value = "python3"

        captured_commands = []
        def capture_subprocess(cmd, cwd, timeout=300):
            captured_commands.append(cmd)
            return (True, "", "")

        with patch("scripts.process_sync_jobs.run_subprocess", side_effect=capture_subprocess):
            process_job(sql_db, job, mock_config, temp_dir)

        # Find store_extraction command
        store_cmds = [cmd for cmd in captured_commands if "store_extraction.py" in str(cmd)]
        assert len(store_cmds) >= 1
        store_cmd = store_cmds[0]

        # Verify AI agent does NOT use any skip flags (human-only or deprecated)
        assert "--i-am-a-human-and-i-want-to-skip-quality-checks" not in store_cmd
        assert "--skip-quality-check" not in store_cmd

        # The actual quality validation in store_extraction.py will still run.
        # skip_quality_check only prevents the job from pausing at waiting_for_quality_review.


class TestNetworkIntegrityAndProvenance:
    """Tests for network-mode integrity, purge, and SyncBatch provenance."""

    def test_network_job_hash_mismatch_fails(self, temp_db):
        """Network jobs fail before processing when payload_hash mismatches."""
        sql_db, temp_dir = temp_db
        from scripts.process_sync_jobs import process_job

        request = _make_summary_first_payload()
        sql_db.create_sync_job(
            job_id="network-mismatch",
            project_name="test_project",
            request_json=json.dumps(request),
            payload_hash="deadbeef",
            transport_type="network",
            quality_review_required=False,
        )

        job = sql_db.claim_next_sync_job("test_project")
        mock_config = MagicMock()
        mock_config.get_python_path.return_value = "python3"
        mock_config.get_graph_db_path.return_value = os.path.join(temp_dir, "graph.kuzu")

        result = process_job(sql_db, job, mock_config, temp_dir)
        assert result is False
        job = sql_db.get_sync_job("network-mismatch")
        assert job["status"] == "failed"
        assert json.loads(job["error_json"])["type"] == "integrity"

    def test_network_job_purges_and_writes_syncbatch(self, temp_db):
        """Successful network jobs purge raw data and create deterministic SyncBatch provenance."""
        sql_db, temp_dir = temp_db
        from scripts.process_sync_jobs import process_job
        from scripts.process_sync_jobs import canonicalize_sync_payload

        request = _make_summary_first_payload(extractions=[])
        request["extraction"] = {
            "extraction_version": "v1.0.0",
            "extraction_commit": "session-test",
            "extractions": [],
        }
        payload_hash = __import__("hashlib").sha256(
            canonicalize_sync_payload(
                request["summary"],
                request["extraction"],
                request.get("attachments", {}),
                request["options"],
            ).encode("utf-8")
        ).hexdigest()

        sql_db.store_interaction({
            "uuid": "uuid-71a9e013410a",
            "project_name": "test_project",
            "user_message": "raw user",
            "assistant_message": "raw assistant",
        })
        sql_db.create_sync_job(
            job_id="network-success",
            project_name="test_project",
            request_json=json.dumps(request),
            payload_hash=payload_hash,
            transport_type="network",
            client_cert_fingerprint="sha256:testfingerprint",
            client_cert_subject="CN=test-client",
            quality_review_required=False,
        )

        job = sql_db.claim_next_sync_job("test_project")
        mock_config = MagicMock()
        mock_config.get_python_path.return_value = "python3"
        mock_config.get_graph_db_path.return_value = os.path.join(temp_dir, "graph.kuzu")

        mock_graph = MagicMock()
        mock_graph.get_entity_by_uuid.return_value = None
        mock_graph.get_relationship_by_uuid.return_value = None

        def fake_subprocess(cmd, cwd, timeout=300):
            cmd_text = " ".join(str(part) for part in cmd)
            if "import_summary.py" in cmd_text:
                return True, "Created interaction: uuid-71a9e013410a", ""
            if "validate_extraction.py" in cmd_text:
                return True, "VALIDATION PASSED", ""
            if "store_extraction.py" in cmd_text:
                return True, (
                    "[OK] Created entity: Network MCP (entity-a2079b04f8ff)\n"
                    "[LINK] Using existing entity: docs/MCP-NETWORK-POSTURE.md (entity-63ea6ad2c8bb)\n"
                    "  Batch UUID: batch-4cf4c07d5102\n"
                ), ""
            return True, "", ""

        with patch("scripts.process_sync_jobs.run_subprocess", side_effect=fake_subprocess), \
             patch("scripts.process_sync_jobs.GraphDatabase", return_value=mock_graph):
            result = process_job(sql_db, job, mock_config, temp_dir)

        assert result is True
        job = sql_db.get_sync_job("network-success")
        assert job["status"] == "complete"
        assert job["payload_hash_verified"] == 1
        assert job["request_json"] == "__PURGED__"
        assert job["raw_request_purged_at"] is not None
        assert job["raw_conversation_purged_at"] is not None

        interaction = sql_db.get_interaction_by_uuid("uuid-71a9e013410a")
        assert interaction["user_message"] == "__PURGED_NETWORK_MCP__"
        assert interaction["assistant_message"] == "__PURGED_NETWORK_MCP__"

        assert mock_graph.create_entity.called
        syncbatch_kwargs = mock_graph.create_entity.call_args.kwargs
        assert syncbatch_kwargs["labels"] == ["SyncBatch"]
        assert syncbatch_kwargs["attributes"]["transport"] == "network"
        assert syncbatch_kwargs["attributes"]["payload_hash"] == payload_hash
        assert syncbatch_kwargs["attributes"]["client_cert_fingerprint"] == "sha256:testfingerprint"

        rel_names = [call.kwargs["relationship_name"] for call in mock_graph.create_relationship.call_args_list]
        assert "CREATES" in rel_names
        assert "RELATED_TO" in rel_names
