"""Tests for MCP sync handlers."""

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


@pytest.fixture
def mock_runtime_state(temp_db):
    """Mock the runtime state for handler tests."""
    sql_db, temp_dir = temp_db
    
    mock_state = MagicMock()
    mock_state.project_name = "test_project"
    mock_state.sql_db_path = sql_db.db_path
    mock_state.graph_db_path = os.path.join(temp_dir, "graph.db")
    
    with patch("mcp_server.handlers.sync.load_runtime_state", return_value=mock_state):
        yield sql_db, mock_state


class TestSyncJobCreation:
    """Tests for sync job creation and SQL storage."""

    def test_create_sync_job(self, temp_db):
        """Test creating a sync job directly in SQL."""
        sql_db, _ = temp_db
        
        job_id = sql_db.create_sync_job(
            job_id="test-job-001",
            project_name="test_project",
            request_json='{"test": "data"}',
            submitted_by_agent="test_agent",
        )
        
        assert job_id == "test-job-001"
        
        job = sql_db.get_sync_job("test-job-001")
        assert job is not None
        assert job["status"] == "queued"
        assert job["stage"] == "submitted"
        assert job["progress"] == 0.0
        assert job["project_name"] == "test_project"
        assert job["transport_type"] == "stdio"
        assert job["payload_hash_verified"] == 0

    def test_list_sync_jobs(self, temp_db):
        """Test listing sync jobs."""
        sql_db, _ = temp_db
        
        # Create multiple jobs
        sql_db.create_sync_job(job_id="job-1", project_name="test_project", request_json="{}")
        sql_db.create_sync_job(job_id="job-2", project_name="test_project", request_json="{}")
        sql_db.create_sync_job(job_id="job-3", project_name="test_project", request_json="{}")
        
        jobs = sql_db.list_sync_jobs("test_project")
        assert len(jobs) == 3
        
        # Test status filter
        sql_db.update_sync_job_status("job-1", status="complete")
        queued_jobs = sql_db.list_sync_jobs("test_project", status="queued")
        assert len(queued_jobs) == 2


class TestSyncJobClaiming:
    """Tests for job claiming logic."""

    def test_claim_next_job(self, temp_db):
        """Test claiming the next queued job."""
        sql_db, _ = temp_db
        
        sql_db.create_sync_job(job_id="job-1", project_name="test_project", request_json="{}")
        
        job = sql_db.claim_next_sync_job("test_project")
        assert job is not None
        assert job["job_id"] == "job-1"
        assert job["status"] == "running"
        
        # Second claim should return None (job already claimed)
        job2 = sql_db.claim_next_sync_job("test_project")
        assert job2 is None

    def test_claim_respects_fifo(self, temp_db):
        """Test that claiming respects FIFO order."""
        sql_db, _ = temp_db
        
        import time
        sql_db.create_sync_job(job_id="job-old", project_name="test_project", request_json="{}")
        time.sleep(0.01)  # Ensure different timestamps
        sql_db.create_sync_job(job_id="job-new", project_name="test_project", request_json="{}")
        
        job = sql_db.claim_next_sync_job("test_project")
        assert job["job_id"] == "job-old"  # Oldest job claimed first


class TestSyncJobStatusUpdates:
    """Tests for job status transitions."""

    def test_update_status_and_stage(self, temp_db):
        """Test updating job status and stage."""
        sql_db, _ = temp_db
        
        sql_db.create_sync_job(job_id="job-1", project_name="test_project", request_json="{}")
        
        sql_db.update_sync_job_status("job-1", status="running", stage="import_summary", progress=0.2)
        
        job = sql_db.get_sync_job("job-1")
        assert job["status"] == "running"
        assert job["stage"] == "import_summary"
        assert job["progress"] == 0.2

    def test_store_result(self, temp_db):
        """Test storing job result."""
        sql_db, _ = temp_db
        
        sql_db.create_sync_job(job_id="job-1", project_name="test_project", request_json="{}")
        
        result = {"success": True, "entities_created": 5}
        sql_db.store_sync_job_result("job-1", json.dumps(result))
        
        job = sql_db.get_sync_job("job-1")
        assert job["result_json"] is not None
        assert json.loads(job["result_json"]) == result

    def test_store_error(self, temp_db):
        """Test storing job error."""
        sql_db, _ = temp_db
        
        sql_db.create_sync_job(job_id="job-1", project_name="test_project", request_json="{}")
        
        error = {"type": "validation", "message": "Invalid payload"}
        sql_db.store_sync_job_error("job-1", json.dumps(error))
        
        job = sql_db.get_sync_job("job-1")
        assert job["error_json"] is not None
        assert json.loads(job["error_json"]) == error

    def test_purge_sync_job_raw_data(self, temp_db):
        """Test purging request_json after successful downstream persistence."""
        sql_db, _ = temp_db
        sql_db.create_sync_job(
            job_id="job-1",
            project_name="test_project",
            request_json='{"secret":"data"}',
            transport_type="network",
            payload_hash="abc123",
        )

        assert sql_db.purge_sync_job_raw_data("job-1")
        job = sql_db.get_sync_job("job-1")
        assert job["request_json"] == "__PURGED__"
        assert job["raw_request_purged_at"] is not None

    def test_purge_interaction_content(self, temp_db):
        """Test purging raw interaction content with the network marker."""
        sql_db, _ = temp_db
        sql_db.store_interaction({
            "uuid": "uuid-111111111111",
            "project_name": "test_project",
            "user_message": "secret user text",
            "assistant_message": "secret assistant text",
        })

        assert sql_db.purge_interaction_content("uuid-111111111111")
        interaction = sql_db.get_interaction_by_uuid("uuid-111111111111")
        assert interaction["user_message"] == "__PURGED_NETWORK_MCP__"
        assert interaction["assistant_message"] == "__PURGED_NETWORK_MCP__"

        verification = sql_db.verify_interaction_chain("test_project")
        assert verification["verified"] is True
        assert verification["purged_interactions"] == 1
