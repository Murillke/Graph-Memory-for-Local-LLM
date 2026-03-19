"""
Tests for Task Operations OTS Provenance.

Tests the event_hash computation, verification, and OTS proof storage.
"""

import hashlib
import tempfile
import unittest
from pathlib import Path

from tools.sql_db import SQLDatabase


class TestTaskOperationsOTS(unittest.TestCase):
    """Tests for task operations OTS provenance."""

    def setUp(self):
        """Create temp database for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = SQLDatabase(str(self.db_path))

    def test_event_hash_computed_on_record(self):
        """Test that event_hash is computed when recording task operation."""
        event_uuid = self.db.record_task_operation(
            project_name="test",
            operation="add",
            success=True,
            task_name="Test Task",
            task_uuid="task-abc123",
            status_before=None,
            status_after="pending",
        )
        
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT event_hash FROM task_operations WHERE event_uuid = ?", (event_uuid,))
        row = cursor.fetchone()
        conn.close()
        
        self.assertIsNotNone(row[0])
        self.assertEqual(len(row[0]), 64)  # SHA256 hex = 64 chars

    def test_event_hash_uses_pipe_delimiter(self):
        """Test that event_hash uses pipe delimiter as specified."""
        event_uuid = self.db.record_task_operation(
            project_name="test",
            operation="transition",
            success=True,
            task_name="Test Task",
            task_uuid="task-xyz",
            status_before="pending",
            status_after="complete",
        )
        
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT task_uuid, operation, status_before, status_after, created_at, event_hash FROM task_operations WHERE event_uuid = ?",
            (event_uuid,)
        )
        row = cursor.fetchone()
        conn.close()
        
        task_uuid, operation, status_before, status_after, created_at, stored_hash = row
        
        # Manually compute expected hash
        hash_input = f"{task_uuid or ''}|{operation}|{status_before or ''}|{status_after or ''}|{created_at}"
        expected_hash = hashlib.sha256(hash_input.encode('utf-8')).hexdigest()
        
        self.assertEqual(stored_hash, expected_hash)

    def test_event_hash_handles_nulls(self):
        """Test that null fields are handled as empty strings in hash."""
        event_uuid = self.db.record_task_operation(
            project_name="test",
            operation="lookup",
            success=False,
            task_name="Missing Task",
            task_uuid=None,  # Null
            status_before=None,  # Null
            status_after=None,  # Null
        )
        
        is_valid, message = self.db.verify_task_operation_hash(event_uuid)
        self.assertTrue(is_valid)
        self.assertEqual(message, "Hash verified")

    def test_verify_detects_tampering(self):
        """Test that verification detects tampered records."""
        event_uuid = self.db.record_task_operation(
            project_name="test",
            operation="add",
            success=True,
            task_name="Test Task",
            task_uuid="task-123",
            status_after="pending",
        )
        
        # Tamper with the record
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE task_operations SET status_after = 'hacked' WHERE event_uuid = ?",
            (event_uuid,)
        )
        conn.commit()
        conn.close()
        
        is_valid, message = self.db.verify_task_operation_hash(event_uuid)
        self.assertFalse(is_valid)
        self.assertIn("mismatch", message.lower())

    def test_get_pending_ots(self):
        """Test getting operations pending OTS submission."""
        # Create operations
        for i in range(3):
            self.db.record_task_operation(
                project_name="test",
                operation="add",
                success=True,
                task_name=f"Task {i}",
                task_uuid=f"task-{i}",
            )
        
        pending = self.db.get_task_operations_pending_ots()
        self.assertEqual(len(pending), 3)
        for p in pending:
            self.assertIn("event_uuid", p)
            self.assertIn("event_hash", p)

    def test_update_ots_proof(self):
        """Test updating operation with OTS proof."""
        event_uuid = self.db.record_task_operation(
            project_name="test",
            operation="add",
            success=True,
            task_name="Test Task",
        )
        
        # Update with OTS proof
        updated = self.db.update_task_operation_ots(
            event_uuid=event_uuid,
            ots_proof="mock_ots_proof_bytes",
            ots_merkle_root="abc123merkle",
            ots_batch_index=0,
        )
        self.assertTrue(updated)
        
        # Verify it's no longer pending
        pending = self.db.get_task_operations_pending_ots()
        pending_uuids = [p["event_uuid"] for p in pending]
        self.assertNotIn(event_uuid, pending_uuids)


if __name__ == "__main__":
    unittest.main()

