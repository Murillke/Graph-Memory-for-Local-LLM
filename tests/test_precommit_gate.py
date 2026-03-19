#!/usr/bin/env python3
"""
Tests for Pre-Commit Sync Gate

Tests the precommit_sync_validator.py, sync.py --complete flow,
and related components.
"""

import os
import sys
import unittest
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scripts.precommit_sync_validator import (
    validate_sync, 
    SYNC_TOKEN_FILE, 
    FRESHNESS_WINDOW_MINUTES
)
from scripts.sync import (
    create_sync_token,
    create_heartbeat_batch,
    sync_complete,
    SYNC_TOKEN_FILE as SYNC_TOKEN_FILE_FROM_SYNC
)


class TestPrecommitGate(unittest.TestCase):
    """Test the pre-commit sync gate validation logic."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.token_path = Path(SYNC_TOKEN_FILE)
        # Ensure clean state
        if self.token_path.exists():
            self.token_path.unlink()
    
    def tearDown(self):
        """Clean up after tests."""
        if self.token_path.exists():
            self.token_path.unlink()
    
    def test_token_paths_match(self):
        """Verify token file paths are consistent across modules."""
        self.assertEqual(SYNC_TOKEN_FILE, SYNC_TOKEN_FILE_FROM_SYNC)
    
    # =========================================================================
    # Essential Tests (v1)
    # =========================================================================
    
    def test_1_missing_token_blocks(self):
        """Test: missing token -> block."""
        # Ensure no token
        if self.token_path.exists():
            self.token_path.unlink()
        
        is_valid, reason = validate_sync("llm_memory")
        
        self.assertFalse(is_valid)
        self.assertIn("token", reason.lower())
    
    def test_2_fresh_success_batch_with_token_allows(self):
        """Test: fresh success batch + token -> allow."""
        # Create token
        create_sync_token("llm_memory", "test_agent")

        # Mock a fresh success batch
        fresh_batch = {
            "batch_uuid": "batch-test-success",
            "created_at": datetime.now(),
            "result": "success"
        }

        with patch('tools.graph_db.GraphDatabase') as mock_gdb:
            mock_instance = MagicMock()
            mock_instance.get_latest_valid_batch.return_value = fresh_batch
            mock_gdb.return_value = mock_instance

            is_valid, reason = validate_sync("llm_memory")

        self.assertTrue(is_valid)
        self.assertIn("fresh", reason.lower())
    
    def test_3_fresh_heartbeat_batch_with_token_allows(self):
        """Test: fresh heartbeat batch + token -> allow."""
        create_sync_token("llm_memory", "test_agent")

        fresh_batch = {
            "batch_uuid": "batch-test-heartbeat",
            "created_at": datetime.now(),
            "result": "heartbeat"
        }

        with patch('tools.graph_db.GraphDatabase') as mock_gdb:
            mock_instance = MagicMock()
            mock_instance.get_latest_valid_batch.return_value = fresh_batch
            mock_gdb.return_value = mock_instance

            is_valid, reason = validate_sync("llm_memory")

        self.assertTrue(is_valid)
    
    def test_4_stale_valid_batch_with_token_blocks(self):
        """Test: stale valid batch + token -> block."""
        create_sync_token("llm_memory", "test_agent")

        # Create stale batch (older than freshness window)
        stale_time = datetime.now() - timedelta(minutes=FRESHNESS_WINDOW_MINUTES + 1)
        stale_batch = {
            "batch_uuid": "batch-test-stale",
            "created_at": stale_time,
            "result": "success"
        }

        with patch('tools.graph_db.GraphDatabase') as mock_gdb:
            mock_instance = MagicMock()
            mock_instance.get_latest_valid_batch.return_value = stale_batch
            mock_gdb.return_value = mock_instance

            is_valid, reason = validate_sync("llm_memory")

        self.assertFalse(is_valid)
        self.assertIn("too old", reason.lower())
    
    def test_5_partial_batch_with_token_blocks(self):
        """Test: partial batch + token -> block (get_latest_valid_batch filters these out)."""
        create_sync_token("llm_memory", "test_agent")

        # get_latest_valid_batch only returns success/heartbeat
        # So if there's only a partial batch, it returns None
        with patch('tools.graph_db.GraphDatabase') as mock_gdb:
            mock_instance = MagicMock()
            mock_instance.get_latest_valid_batch.return_value = None  # No valid batch
            mock_gdb.return_value = mock_instance

            is_valid, reason = validate_sync("llm_memory")

        self.assertFalse(is_valid)
        self.assertIn("no sync history", reason.lower())


class TestSyncComplete(unittest.TestCase):
    """Test the sync.py --complete flow."""

    def setUp(self):
        """Set up test fixtures."""
        self.token_path = Path(SYNC_TOKEN_FILE)
        if self.token_path.exists():
            self.token_path.unlink()

    def tearDown(self):
        """Clean up after tests."""
        if self.token_path.exists():
            self.token_path.unlink()

    def test_6_sync_complete_creates_heartbeat_when_unprocessed_zero(self):
        """Test: sync.py --complete with unprocessed == 0 creates heartbeat + token."""
        # Mock SQL to return unprocessed == 0
        mock_counts = {"total": 10, "processed": 10, "unprocessed": 0}

        with patch('tools.sql_db.SQLDatabase') as mock_sql, \
             patch('tools.graph_db.GraphDatabase') as mock_gdb:

            # Setup SQL mock
            mock_sql_instance = MagicMock()
            mock_sql_instance.get_interaction_counts.return_value = mock_counts
            mock_sql.return_value = mock_sql_instance

            # Setup Graph mock to track create_extraction_batch calls
            mock_gdb_instance = MagicMock()
            mock_gdb_instance.create_extraction_batch.return_value = "batch-heartbeat-test"
            mock_gdb.return_value = mock_gdb_instance

            # Run sync_complete
            sync_complete("llm_memory", "test_agent", "test_model")

            # Verify heartbeat was created
            mock_gdb_instance.create_extraction_batch.assert_called_once()
            call_kwargs = mock_gdb_instance.create_extraction_batch.call_args
            self.assertEqual(call_kwargs.kwargs.get('result'), 'heartbeat')

            # Verify token was created
            self.assertTrue(self.token_path.exists())

    def test_sync_complete_skips_heartbeat_when_unprocessed_nonzero(self):
        """Test: sync.py --complete with unprocessed > 0 skips heartbeat, creates token."""
        mock_counts = {"total": 10, "processed": 8, "unprocessed": 2}

        with patch('tools.sql_db.SQLDatabase') as mock_sql, \
             patch('tools.graph_db.GraphDatabase') as mock_gdb:

            mock_sql_instance = MagicMock()
            mock_sql_instance.get_interaction_counts.return_value = mock_counts
            mock_sql.return_value = mock_sql_instance

            mock_gdb_instance = MagicMock()
            mock_gdb.return_value = mock_gdb_instance

            sync_complete("llm_memory", "test_agent", "test_model")

            # Verify heartbeat was NOT created
            mock_gdb_instance.create_extraction_batch.assert_not_called()

            # Token should still be created
            self.assertTrue(self.token_path.exists())


class TestTokenDeletion(unittest.TestCase):
    """Test token deletion on successful validation."""

    def setUp(self):
        """Set up test fixtures."""
        self.token_path = Path(SYNC_TOKEN_FILE)

    def tearDown(self):
        """Clean up after tests."""
        if self.token_path.exists():
            self.token_path.unlink()

    def test_7_token_deleted_on_successful_validation(self):
        """Test: token deletion on successful validation (via main entrypoint)."""
        from scripts.precommit_sync_validator import main

        # Create token
        create_sync_token("llm_memory", "test_agent")
        self.assertTrue(self.token_path.exists())

        # Mock fresh batch
        fresh_batch = {
            "batch_uuid": "batch-test",
            "created_at": datetime.now(),
            "result": "success"
        }

        with patch('tools.graph_db.GraphDatabase') as mock_gdb, \
             patch('sys.argv', ['precommit_sync_validator.py', '--project', 'llm_memory']), \
             patch('sys.exit') as mock_exit:

            mock_instance = MagicMock()
            mock_instance.get_latest_valid_batch.return_value = fresh_batch
            mock_gdb.return_value = mock_instance

            # Call actual main() which should delete token on success
            main()

            # Verify exit(0) was called (success)
            mock_exit.assert_called_with(0)

        # Token should be deleted by main()
        self.assertFalse(self.token_path.exists())


# =========================================================================
# Edge Case Tests
# =========================================================================

class TestEdgeCases(unittest.TestCase):
    """Edge case tests for the pre-commit gate."""

    def setUp(self):
        """Set up test fixtures."""
        self.token_path = Path(SYNC_TOKEN_FILE)
        if self.token_path.exists():
            self.token_path.unlink()

    def tearDown(self):
        """Clean up after tests."""
        if self.token_path.exists():
            self.token_path.unlink()

    def test_iso_format_timestamp_string(self):
        """Test: validator handles ISO format timestamp strings."""
        create_sync_token("llm_memory", "test_agent")

        # Return timestamp as ISO string (as stored in kuzu)
        iso_timestamp = datetime.now().isoformat()
        fresh_batch = {
            "batch_uuid": "batch-test-iso",
            "created_at": iso_timestamp,
            "result": "success"
        }

        with patch('tools.graph_db.GraphDatabase') as mock_gdb:
            mock_instance = MagicMock()
            mock_instance.get_latest_valid_batch.return_value = fresh_batch
            mock_gdb.return_value = mock_instance

            is_valid, reason = validate_sync("llm_memory")

        self.assertTrue(is_valid)

    def test_token_content_includes_metadata(self):
        """Test: token file contains project and agent metadata."""
        create_sync_token("test_project", "test_agent")

        content = self.token_path.read_text()

        self.assertIn("test_project", content)
        self.assertIn("test_agent", content)
        self.assertIn("Created:", content)

    def test_tmp_directory_created_if_missing(self):
        """Test: token creation handles missing parent directory."""
        import shutil

        # Use workspace-local path to avoid Windows %TEMP% permission issues
        test_base = Path(__file__).parent / "tmp_test_precommit"
        nonexistent_subdir = test_base / "nonexistent" / "nested"
        test_token_path = nonexistent_subdir / "test_token.tmp"

        # Clean up any leftover from previous run
        if test_base.exists():
            shutil.rmtree(test_base)

        try:
            # Verify parent doesn't exist
            self.assertFalse(nonexistent_subdir.exists())

            # Patch SYNC_TOKEN_FILE to use our test path
            with patch('scripts.sync.SYNC_TOKEN_FILE', str(test_token_path)):
                from scripts.sync import create_sync_token

                # Should create parent directories and not raise
                create_sync_token("llm_memory", "test")

                # Verify directory and file were created
                self.assertTrue(nonexistent_subdir.exists())
                self.assertTrue(test_token_path.exists())
        finally:
            if test_base.exists():
                shutil.rmtree(test_base)


# Note: get_latest_valid_batch filtering (success/heartbeat only) is tested
# indirectly via test_5_partial_batch_with_token_blocks. A direct integration
# test would require a real graph fixture, which is out of scope for unit tests.


if __name__ == "__main__":
    unittest.main()

