"""Tests for recall.py fallback behavior on invalid arguments."""

import os
import sys
import shutil
import tempfile
import subprocess
from datetime import datetime, timedelta

import pytest

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from scripts.recall import (
    RecallArgumentError,
    get_last_entity_timestamp,
    run_fallback_recall,
)
from tools.graph_db import GraphDatabase


@pytest.fixture
def temp_graph_db():
    """Create a temporary graph database with test entities."""
    temp_dir = tempfile.mkdtemp()
    graph_path = os.path.join(temp_dir, "test_recall.kuzu")

    graph_db = GraphDatabase(graph_path)
    graph_db.create_project_node("test_project", "Test project")

    # Add some test entities with timestamps
    now = datetime.utcnow()
    timestamps = [
        (now - timedelta(hours=2)).isoformat() + "Z",
        (now - timedelta(hours=1)).isoformat() + "Z",
        now.isoformat() + "Z",
    ]

    for i, ts in enumerate(timestamps):
        entity_uuid = graph_db.create_entity(
            name=f"TestEntity{i}",
            group_id="test_project",
            source_interactions=["test-interaction"],
            source_hashes=["test-hash"],
            extraction_version="v1.0.0",
            extraction_commit="test-commit",
            summary=f"Test entity {i}",
            event_timestamp=ts,
        )
        graph_db.link_project_to_entity("test_project", entity_uuid)

    yield graph_path, temp_dir, timestamps[-1]  # Return path, dir, and most recent timestamp

    shutil.rmtree(temp_dir, ignore_errors=True)


class TestRecallArgumentError:
    """Tests for the RecallArgumentError exception."""

    def test_exception_is_raised_on_invalid_args(self):
        """Test that invalid args raise RecallArgumentError."""
        from scripts.recall import build_parser
        
        parser = build_parser()
        
        with pytest.raises(RecallArgumentError):
            parser.parse_args(['--project', 'test', '--last', '1'])

    def test_exception_is_raised_on_missing_required_args(self):
        """Test that missing required args raise RecallArgumentError."""
        from scripts.recall import build_parser
        
        parser = build_parser()
        
        with pytest.raises(RecallArgumentError):
            parser.parse_args(['--project', 'test'])  # Missing --start and --end


class TestGetLastEntityTimestamp:
    """Tests for the get_last_entity_timestamp function."""

    def test_returns_most_recent_timestamp(self, temp_graph_db):
        """Test that it returns the most recent entity timestamp."""
        graph_path, _, expected_ts = temp_graph_db
        
        from tools.graph_db import open_kuzu_database
        db, conn = open_kuzu_database(graph_path)
        
        result = get_last_entity_timestamp(conn, "test_project")
        
        assert result == expected_ts

    def test_returns_none_for_empty_project(self, temp_graph_db):
        """Test that it returns None for project with no entities."""
        graph_path, _, _ = temp_graph_db
        
        from tools.graph_db import open_kuzu_database
        db, conn = open_kuzu_database(graph_path)
        
        result = get_last_entity_timestamp(conn, "nonexistent_project")
        
        assert result is None


class TestFallbackBehavior:
    """Tests for the CLI fallback behavior."""

    def test_invalid_args_returns_error_code_2(self):
        """Test that invalid args return exit code 2."""
        result = subprocess.run(
            [sys.executable, 'scripts/recall.py', '--project', 'llm_memory', '--last', '1'],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(__file__)),
        )
        
        assert result.returncode == 2

    def test_invalid_args_shows_error_message(self):
        """Test that invalid args show error message."""
        result = subprocess.run(
            [sys.executable, 'scripts/recall.py', '--project', 'llm_memory', '--last', '1'],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(__file__)),
        )
        
        assert 'error:' in result.stderr

    def test_invalid_args_shows_fallback_output(self):
        """Test that invalid args still show fallback results."""
        result = subprocess.run(
            [sys.executable, 'scripts/recall.py', '--project', 'llm_memory', '--last', '1'],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(__file__)),
        )
        
        # Should contain fallback header
        assert 'FALLBACK RECALL' in result.stdout or 'FALLBACK' in result.stderr

    def test_missing_project_shows_fallback_message(self):
        """Test that missing --project explains why fallback can't run."""
        result = subprocess.run(
            [sys.executable, 'scripts/recall.py', '--last', '1'],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(__file__)),
        )
        
        assert result.returncode == 2
        assert 'no --project specified' in result.stderr

