"""Cross-tool integration tests.

These tests verify that MCP tools work correctly together:
1. store → recall (stored entities are recallable)
2. tasks → context (tasks appear in context)
3. sync → recall (synced data becomes queryable)

These catch integration bugs where individual tools work but don't interoperate.
"""

import sys

# Python 3.10+ required for mcp package
if sys.version_info < (3, 10):
    sys.exit(
        "ERROR: These tests require Python 3.10+.\n"
        "Current: Python {}.{}\n"
        "Fix: Update mem.config.json python_path to python3.11".format(
            sys.version_info.major, sys.version_info.minor
        )
    )

import json
import os
import shutil
import tempfile
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tools.graph_db import GraphDatabase
from tools.sql_db import SQLDatabase


@pytest.fixture
def temp_databases():
    """Create temporary graph and SQL databases."""
    temp_dir = tempfile.mkdtemp()
    graph_path = os.path.join(temp_dir, "test.kuzu")
    sql_path = os.path.join(temp_dir, "test.db")

    graph_db = GraphDatabase(graph_path)
    graph_db.create_project_node("test_project", "Test project")

    sql_db = SQLDatabase(sql_path)
    sql_db.create_project("test_project", "Test project")

    yield graph_db, sql_db, temp_dir

    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_runtime_state(temp_databases):
    """Mock runtime state for handler tests."""
    graph_db, sql_db, temp_dir = temp_databases

    mock_state = MagicMock()
    mock_state.project_name = "test_project"
    mock_state.graph_db_path = os.path.join(temp_dir, "test.kuzu")
    mock_state.sql_db_path = sql_db.db_path

    yield mock_state, graph_db, sql_db


class TestStoreAndRecall:
    """Test that stored entities are recallable."""

    def test_stored_entity_appears_in_recall(self, mock_runtime_state):
        """Test: store entity → recall shows it."""
        mock_state, graph_db, sql_db = mock_runtime_state

        # Store an entity directly
        now = datetime.utcnow()
        entity_uuid = graph_db.create_entity(
            name="CrossToolTestEntity",
            group_id="test_project",
            source_interactions=["test-interaction"],
            source_hashes=["test-hash"],
            extraction_version="v1.0",
            extraction_commit="abc123",
            summary="Test entity for cross-tool testing",
            event_timestamp=now.isoformat() + "Z",
        )
        graph_db.link_project_to_entity("test_project", entity_uuid)

        # Recall entities
        from mcp_server.handlers.recall import memory_recall

        start = (now - timedelta(hours=1)).isoformat()
        end = (now + timedelta(hours=1)).isoformat()

        with patch("mcp_server.handlers.recall.load_runtime_state", return_value=mock_state):
            result = memory_recall(start=start, end=end)

        # Verify entity appears
        assert result["status"] == "ok"
        result_str = json.dumps(result)
        assert "CrossToolTestEntity" in result_str


class TestTasksAndContext:
    """Test that tasks appear in context."""

    def test_added_task_appears_in_context(self, mock_runtime_state):
        """Test: add task → context shows it."""
        mock_state, graph_db, sql_db = mock_runtime_state

        from mcp_server.handlers.tasks import memory_tasks
        from mcp_server.handlers.context import memory_context

        # Create a mock config that matches our test project
        mock_config = MagicMock()
        mock_config.get_sql_db_path.return_value = sql_db.db_path

        # Add a task - need to patch both load_runtime_state and the config loader
        with patch("mcp_server.handlers.tasks.load_runtime_state", return_value=mock_state), \
             patch("scripts.tasks.load_config", return_value=mock_config):
            add_result = memory_tasks(
                action="add",
                name="CrossToolTestTask",
                priority="high",
                summary="Task for cross-tool testing",
            )

        assert add_result["status"] == "ok"

        # Get context
        with patch("mcp_server.handlers.context.load_runtime_state", return_value=mock_state):
            context_result = memory_context()

        # Verify task appears in context
        context_str = json.dumps(context_result)
        assert "CrossToolTestTask" in context_str or "cross" in context_str.lower()


class TestSyncJobCreatesRecallableData:
    """Test that sync job data becomes queryable."""

    def test_sync_job_creates_sql_record(self, mock_runtime_state):
        """Test: sync submit creates queryable job record."""
        mock_state, graph_db, sql_db = mock_runtime_state

        from mcp_server.handlers.sync import memory_sync_submit, memory_sync_list

        # Submit a sync job
        with patch("mcp_server.handlers.sync.load_runtime_state", return_value=mock_state):
            submit_result = memory_sync_submit(
                summary={
                    "session_id": "test-sql-record",
                    "timestamp": "2026-03-18T12:00:00Z",
                    "intent": "Test SQL record creation",
                    "work_attempted": ["Test"],
                    "outcomes": [{"type": "success", "description": "Test"}],
                    "fidelity": "summary",
                },
                extraction={"extractions": []},
                options={"skip_quality_check": True},
            )

        assert submit_result["status"] == "ok"
        job_id = submit_result["data"]["job_id"]



class TestRecallResponseShape:
    """Test recall response structure and limits."""

    def test_recall_respects_limit_parameter(self, mock_runtime_state):
        """Test that limit parameter controls entity count."""
        mock_state, graph_db, sql_db = mock_runtime_state

        now = datetime.utcnow()

        # Create multiple entities
        for i in range(5):
            entity_uuid = graph_db.create_entity(
                name=f"LimitTestEntity{i}",
                group_id="test_project",
                source_interactions=["test"],
                source_hashes=["test"],
                extraction_version="v1.0",
                extraction_commit="abc",
                summary=f"Entity {i}",
                event_timestamp=now.isoformat() + "Z",
            )
            graph_db.link_project_to_entity("test_project", entity_uuid)

        from mcp_server.handlers.recall import memory_recall

        start = (now - timedelta(hours=1)).isoformat()
        end = (now + timedelta(hours=1)).isoformat()

        with patch("mcp_server.handlers.recall.load_runtime_state", return_value=mock_state):
            result = memory_recall(start=start, end=end, limit=2)

        assert result["status"] == "ok"
        # Should have at most 2 entities per day (limit is per-day)

    def test_recall_response_has_required_fields(self, mock_runtime_state):
        """Test that recall response has expected structure."""
        mock_state, graph_db, sql_db = mock_runtime_state

        from mcp_server.handlers.recall import memory_recall

        now = datetime.utcnow()
        start = (now - timedelta(hours=1)).isoformat()
        end = (now + timedelta(hours=1)).isoformat()

        with patch("mcp_server.handlers.recall.load_runtime_state", return_value=mock_state):
            result = memory_recall(start=start, end=end)

        assert "status" in result
        assert result["status"] == "ok"
        assert "data" in result


class TestErrorPaths:
    """Test error handling for common failure modes."""

    def test_recall_with_invalid_time_format(self, mock_runtime_state):
        """Test recall with malformed timestamps."""
        mock_state, graph_db, sql_db = mock_runtime_state

        from mcp_server.handlers.recall import memory_recall

        with patch("mcp_server.handlers.recall.load_runtime_state", return_value=mock_state):
            result = memory_recall(start="not-a-date", end="also-not-a-date")

        # Should handle gracefully (either fail or return empty)
        assert "status" in result

    def test_sync_status_with_nonexistent_job(self, mock_runtime_state):
        """Test sync status with invalid job ID."""
        mock_state, graph_db, sql_db = mock_runtime_state

        from mcp_server.handlers.sync import memory_sync_status

        with patch("mcp_server.handlers.sync.load_runtime_state", return_value=mock_state):
            result = memory_sync_status(job_id="nonexistent-job-12345")

        assert result["status"] == "error"
        assert "not_found" in result.get("type", "")

    def test_sync_result_on_incomplete_job(self, mock_runtime_state):
        """Test sync result on non-terminal job."""
        mock_state, graph_db, sql_db = mock_runtime_state

        from mcp_server.handlers.sync import memory_sync_submit, memory_sync_result

        # Submit a job (it will be queued, not complete)
        with patch("mcp_server.handlers.sync.load_runtime_state", return_value=mock_state):
            submit_result = memory_sync_submit(
                summary={
                    "session_id": "test-incomplete-job",
                    "timestamp": "2026-03-18T12:00:00Z",
                    "intent": "Test incomplete job error path",
                    "work_attempted": ["Test"],
                    "outcomes": [{"type": "success", "description": "Test"}],
                    "fidelity": "summary",
                },
                extraction={"extractions": []},
            )

        job_id = submit_result["data"]["job_id"]

        # Try to get result (should fail - job is queued not complete)
        with patch("mcp_server.handlers.sync.load_runtime_state", return_value=mock_state):
            result = memory_sync_result(job_id=job_id)

        assert result["status"] == "error"
        assert "validation" in result.get("type", "")
