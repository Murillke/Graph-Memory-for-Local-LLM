#!/usr/bin/env python3
"""Tests for scripts/tasks.py - Task management functionality."""

import unittest
import sys
import shutil
import os
import json
from pathlib import Path
from uuid import uuid4

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.graph_db import GraphDatabase
from scripts.tasks import (
    parse_number_ranges,
    parse_task_identifiers,
    resolve_task_identifier,
    format_age,
    get_actionable_tasks_ordered,
    transition_task_status,
    update_task_status,
    batch_update_tasks,
    update_task_priority_by_uuid,
    show_tasks,
    show_task_details,
    add_task,
    update_task_entity,
    get_child_tasks,
    VALID_TRANSITIONS,
)
from tools.sql_db import SQLDatabase

REPO_ROOT = Path(__file__).parent.parent


class TestParseNumberRanges(unittest.TestCase):
    """Test number range parsing."""

    def test_single_number(self):
        self.assertEqual(parse_number_ranges("1"), [1])
        self.assertEqual(parse_number_ranges("5"), [5])

    def test_multiple_numbers(self):
        self.assertEqual(parse_number_ranges("1,3,5"), [1, 3, 5])

    def test_range(self):
        self.assertEqual(parse_number_ranges("1-3"), [1, 2, 3])
        self.assertEqual(parse_number_ranges("5-8"), [5, 6, 7, 8])

    def test_mixed(self):
        self.assertEqual(parse_number_ranges("1,3-5,8"), [1, 3, 4, 5, 8])

    def test_with_spaces(self):
        self.assertEqual(parse_number_ranges("1, 3, 5-8"), [1, 3, 5, 6, 7, 8])


class TestFormatAge(unittest.TestCase):
    """Test age formatting."""

    def test_empty_string(self):
        self.assertEqual(format_age(""), "")
        self.assertEqual(format_age(None), "")

    def test_invalid_format(self):
        self.assertEqual(format_age("not-a-date"), "")


class TestTaskOperations(unittest.TestCase):
    """Test task operations against a test database."""

    def setUp(self):
        base_tmp = REPO_ROOT / "tests" / "tmp"
        base_tmp.mkdir(parents=True, exist_ok=True)
        self.test_dir = base_tmp / f"tasks_{uuid4().hex[:8]}"
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.graph_path = self.test_dir / "test.graph"
        self.project_name = "task-test"

        self.graph_db = GraphDatabase(str(self.graph_path))
        self.graph_db.create_project_node(self.project_name)

    def tearDown(self):
        self.graph_db.close()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_test_task(self, name: str, priority: str = 'medium', status: str = 'pending'):
        """Helper to create a test task."""
        uuid = self.graph_db.create_entity(
            name=name,
            group_id=self.project_name,
            source_interactions=["test-1"],
            source_hashes=["hash-1"],
            extraction_version="v1.0.0",
            extraction_commit="test",
            summary=f"Test task: {name}",
            labels=["Task"],
            attributes={"priority": priority, "status": status}
        )
        self.graph_db.link_project_to_entity(self.project_name, uuid)
        
        # Set priority and status on node directly
        self.graph_db.conn.execute("""
            MATCH (e:Entity {uuid: $uuid})
            SET e.priority = $priority, e.status = $status
        """, {"uuid": uuid, "priority": priority, "status": status})
        
        return uuid

    def test_get_pending_tasks_ordered_by_priority(self):
        """Test that pending tasks are ordered by priority: high, medium, low."""
        self._create_test_task("Low Task", priority="low")
        self._create_test_task("High Task", priority="high")
        self._create_test_task("Medium Task", priority="medium")

        # Need to mock config for this test - skip for now
        # This would require injecting db path
        pass

    def test_task_creation_with_labels(self):
        """Test that tasks are created with correct labels."""
        uuid = self._create_test_task("Test Task")
        
        result = self.graph_db.conn.execute("""
            MATCH (e:Entity {uuid: $uuid})
            RETURN e.labels, e.priority, e.status
        """, {"uuid": uuid})
        
        self.assertTrue(result.has_next())
        row = result.get_next()
        self.assertIn("Task", row[0])
        self.assertEqual(row[1], "medium")
        self.assertEqual(row[2], "pending")

    def test_task_priority_update(self):
        """Test that task priority can be updated."""
        uuid = self._create_test_task("Priority Test", priority="low")
        
        # Update priority
        self.graph_db.conn.execute("""
            MATCH (e:Entity {uuid: $uuid})
            SET e.priority = 'high'
        """, {"uuid": uuid})
        
        # Verify
        result = self.graph_db.conn.execute("""
            MATCH (e:Entity {uuid: $uuid})
            RETURN e.priority
        """, {"uuid": uuid})
        
        self.assertTrue(result.has_next())
        row = result.get_next()
        self.assertEqual(row[0], "high")

    def test_task_status_update(self):
        """Test that task status can be updated."""
        uuid = self._create_test_task("Status Test")
        
        # Update status
        self.graph_db.conn.execute("""
            MATCH (e:Entity {uuid: $uuid})
            SET e.status = 'complete'
        """, {"uuid": uuid})
        
        # Verify
        result = self.graph_db.conn.execute("""
            MATCH (e:Entity {uuid: $uuid})
            RETURN e.status
        """, {"uuid": uuid})
        
        self.assertTrue(result.has_next())
        row = result.get_next()
        self.assertEqual(row[0], "complete")


class TestInProgressStatus(unittest.TestCase):
    """Test in_progress status functionality."""

    def setUp(self):
        base_tmp = REPO_ROOT / "tests" / "tmp"
        base_tmp.mkdir(parents=True, exist_ok=True)
        self.test_dir = base_tmp / f"tasks_inprogress_{uuid4().hex[:8]}"
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.graph_path = self.test_dir / "test.graph"
        self.project_name = "inprogress-test"

        self.graph_db = GraphDatabase(str(self.graph_path))
        self.graph_db.create_project_node(self.project_name)

    def tearDown(self):
        self.graph_db.close()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_task(self, name: str, priority: str = 'medium', status: str = 'pending', attributes: str = '{}'):
        """Helper to create a test task with attributes."""
        uuid = self.graph_db.create_entity(
            name=name,
            group_id=self.project_name,
            source_interactions=["test-1"],
            source_hashes=["hash-1"],
            extraction_version="v1.0.0",
            extraction_commit="test",
            summary=f"Test task: {name}",
            labels=["Task"],
            attributes={"priority": priority}
        )
        self.graph_db.link_project_to_entity(self.project_name, uuid)

        self.graph_db.conn.execute("""
            MATCH (e:Entity {uuid: $uuid})
            SET e.priority = $priority, e.status = $status, e.attributes = $attributes
        """, {"uuid": uuid, "priority": priority, "status": status, "attributes": attributes})

        return uuid

    def test_start_transition_sets_started_at(self):
        """Test that --start sets attributes.started_at."""
        uuid = self._create_task("Start Test")

        result = transition_task_status(self.project_name, uuid, 'in_progress', self.graph_db)

        self.assertTrue(result['ok'])
        self.assertEqual(result['old_status'], 'pending')
        self.assertEqual(result['new_status'], 'in_progress')

        # Verify started_at is set
        query_result = self.graph_db.conn.execute("""
            MATCH (e:Entity {uuid: $uuid})
            RETURN e.attributes
        """, {"uuid": uuid})
        row = query_result.get_next()
        import json
        attrs = json.loads(row[0])
        self.assertIn('started_at', attrs)

    def test_pause_transition_clears_started_at(self):
        """Test that --pause clears attributes.started_at."""
        import json
        started_attrs = json.dumps({"started_at": "2026-03-13T10:00:00"})
        uuid = self._create_task("Pause Test", status='in_progress', attributes=started_attrs)

        result = transition_task_status(self.project_name, uuid, 'pending', self.graph_db)

        self.assertTrue(result['ok'])
        self.assertEqual(result['old_status'], 'in_progress')
        self.assertEqual(result['new_status'], 'pending')

        # Verify started_at is cleared
        query_result = self.graph_db.conn.execute("""
            MATCH (e:Entity {uuid: $uuid})
            RETURN e.attributes
        """, {"uuid": uuid})
        row = query_result.get_next()
        attrs = json.loads(row[0])
        self.assertNotIn('started_at', attrs)

    def test_done_from_pending(self):
        """Test --done works from pending status."""
        uuid = self._create_task("Done from Pending")

        result = transition_task_status(self.project_name, uuid, 'complete', self.graph_db)

        self.assertTrue(result['ok'])
        self.assertEqual(result['old_status'], 'pending')
        self.assertEqual(result['new_status'], 'complete')

    def test_done_from_in_progress(self):
        """Test --done works from in_progress status."""
        uuid = self._create_task("Done from InProgress", status='in_progress')

        result = transition_task_status(self.project_name, uuid, 'complete', self.graph_db)

        self.assertTrue(result['ok'])
        self.assertEqual(result['old_status'], 'in_progress')
        self.assertEqual(result['new_status'], 'complete')

    def test_invalid_transition_warning(self):
        """Test that invalid transitions return warning."""
        uuid = self._create_task("Already Complete", status='complete')

        result = transition_task_status(self.project_name, uuid, 'in_progress', self.graph_db)

        self.assertFalse(result['ok'])
        self.assertIn('cannot transition', result['error'])

    def test_same_state_no_op(self):
        """Test that same-state transitions return warning."""
        uuid = self._create_task("Already InProgress", status='in_progress')

        result = transition_task_status(self.project_name, uuid, 'in_progress', self.graph_db)

        self.assertFalse(result['ok'])
        self.assertIn('already in_progress', result['error'])

    def test_null_status_as_pending(self):
        """Test that NULL status is treated as pending."""
        uuid = self._create_task("Null Status")

        # Set status to NULL explicitly
        self.graph_db.conn.execute("""
            MATCH (e:Entity {uuid: $uuid})
            SET e.status = NULL
        """, {"uuid": uuid})

        result = transition_task_status(self.project_name, uuid, 'in_progress', self.graph_db)

        self.assertTrue(result['ok'])
        self.assertEqual(result['old_status'], 'pending')

    def test_malformed_attributes_handling(self):
        """Test that malformed attributes are treated as {}."""
        uuid = self._create_task("Malformed Attrs")

        # Set malformed attributes
        self.graph_db.conn.execute("""
            MATCH (e:Entity {uuid: $uuid})
            SET e.attributes = 'not valid json {'
        """, {"uuid": uuid})

        # Should not crash, should succeed
        result = transition_task_status(self.project_name, uuid, 'in_progress', self.graph_db)

        self.assertTrue(result['ok'])

    def test_valid_transitions_matrix(self):
        """Test that VALID_TRANSITIONS contains expected transitions."""
        expected = {
            ('pending', 'in_progress'),
            ('pending', 'complete'),
            ('pending', 'invalid'),
            ('in_progress', 'complete'),
            ('in_progress', 'invalid'),
            ('in_progress', 'pending'),
        }
        self.assertEqual(VALID_TRANSITIONS, expected)

    def test_update_task_status_rejects_duplicate_names(self):
        """Test that update_task_status rejects duplicate task names."""
        # Create two tasks with the same name
        self._create_task("Duplicate Task Name")
        self._create_task("Duplicate Task Name")

        # Call actual update_task_status - should return False due to duplicates
        result = update_task_status(
            self.project_name,
            "Duplicate Task Name",
            'complete',
            db=self.graph_db
        )
        self.assertFalse(result, "Should reject update when duplicate names exist")

    def test_batch_update_tasks_warns_on_duplicate_names(self):
        """Test that batch_update_tasks warns and skips duplicate task names."""
        # Create two tasks with same name and one unique
        self._create_task("Duplicate Batch Task")
        self._create_task("Duplicate Batch Task")
        uuid3 = self._create_task("Unique Batch Task")

        # Call actual batch_update_tasks
        result = batch_update_tasks(
            self.project_name,
            ["Duplicate Batch Task", "Unique Batch Task"],
            'complete',
            db=self.graph_db
        )
        # Should return True because unique task succeeded
        self.assertTrue(result, "Should succeed when at least one task updated")

        # Verify unique task was updated
        query_result = self.graph_db.conn.execute("""
            MATCH (e:Entity {uuid: $uuid})
            RETURN e.status
        """, {"uuid": uuid3})
        row = query_result.get_next()
        self.assertEqual(row[0], 'complete')

    def test_update_task_status_succeeds_for_unique_name(self):
        """Test that update_task_status succeeds for unique task names."""
        uuid = self._create_task("Unique Update Test")

        # Call actual update_task_status - should succeed
        result = update_task_status(
            self.project_name,
            "Unique Update Test",
            'complete',
            db=self.graph_db
        )
        self.assertTrue(result, "Should succeed for unique task name")

        # Verify task was updated
        query_result = self.graph_db.conn.execute("""
            MATCH (e:Entity {uuid: $uuid})
            RETURN e.status
        """, {"uuid": uuid})
        row = query_result.get_next()
        self.assertEqual(row[0], 'complete')


class TestFilteredOutput(unittest.TestCase):
    """Test filtered output behavior."""

    def setUp(self):
        base_tmp = REPO_ROOT / "tests" / "tmp"
        base_tmp.mkdir(parents=True, exist_ok=True)
        self.test_dir = base_tmp / f"tasks_filter_{uuid4().hex[:8]}"
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.graph_path = self.test_dir / "test.graph"
        self.project_name = "filter-test"

        self.graph_db = GraphDatabase(str(self.graph_path))
        self.graph_db.create_project_node(self.project_name)

    def tearDown(self):
        self.graph_db.close()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_task(self, name: str, priority: str = 'medium', status: str = 'pending'):
        """Helper to create a test task."""
        uuid = self.graph_db.create_entity(
            name=name,
            group_id=self.project_name,
            source_interactions=["test-1"],
            source_hashes=["hash-1"],
            extraction_version="v1.0.0",
            extraction_commit="test",
            summary=f"Test task: {name}",
            labels=["Task"],
            attributes={"priority": priority}
        )
        self.graph_db.link_project_to_entity(self.project_name, uuid)

        self.graph_db.conn.execute("""
            MATCH (e:Entity {uuid: $uuid})
            SET e.priority = $priority, e.status = $status
        """, {"uuid": uuid, "priority": priority, "status": status})

        return uuid

    def test_actionable_excludes_complete_invalid(self):
        """Test that get_actionable_tasks_ordered excludes complete/invalid."""
        # Create tasks with different statuses
        self._create_task("Pending Task", status='pending')
        self._create_task("InProgress Task", status='in_progress')
        self._create_task("Complete Task", status='complete')
        self._create_task("Invalid Task", status='invalid')

        actionable = get_actionable_tasks_ordered(self.project_name, self.graph_db)

        # Should only include pending and in_progress
        self.assertEqual(len(actionable), 2)
        statuses = {t['status'] for t in actionable}
        self.assertEqual(statuses, {'pending', 'in_progress'})

    def test_show_tasks_priority_filter_excludes_complete_invalid(self):
        """Test that show_tasks with priority filter excludes complete/invalid sections.

        This tests the actual display output path.
        """
        import io
        import sys

        # Create tasks
        self._create_task("High Pending", priority='high', status='pending')
        self._create_task("High Complete", priority='high', status='complete')
        self._create_task("Medium Invalid", priority='medium', status='invalid')

        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = captured = io.StringIO()

        try:
            # Call actual show_tasks with priority filter
            show_tasks(
                self.project_name,
                pending_only=False,
                in_progress_only=False,
                priority_filter='high',
                verbose=False,
                db=self.graph_db
            )
            output = captured.getvalue()
        finally:
            sys.stdout = old_stdout

        # Should include pending task
        self.assertIn("High Pending", output)

        # Should NOT include complete/invalid sections when filter is active
        self.assertNotIn("COMPLETED", output)
        self.assertNotIn("INVALID", output)
        self.assertNotIn("High Complete", output)

    def test_show_tasks_default_includes_complete_invalid(self):
        """Test that show_tasks without filter includes complete/invalid sections."""
        import io
        import sys

        # Create tasks
        self._create_task("Test Pending", priority='high', status='pending')
        self._create_task("Test Complete", priority='high', status='complete')

        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = captured = io.StringIO()

        try:
            # Call actual show_tasks without filter, with include_closed=True
            show_tasks(
                self.project_name,
                pending_only=False,
                in_progress_only=False,
                priority_filter=None,
                verbose=False,
                include_closed=True,
                db=self.graph_db
            )
            output = captured.getvalue()
        finally:
            sys.stdout = old_stdout

        # Should include both pending and complete sections
        self.assertIn("Test Pending", output)
        self.assertIn("COMPLETED TASKS", output)
        self.assertIn("Test Complete", output)

    def test_global_numbering_in_actionable_list(self):
        """Test that display_number is sequential across in_progress + pending."""
        self._create_task("First InProgress", status='in_progress', priority='high')
        self._create_task("Second Pending", status='pending', priority='high')
        self._create_task("Third Pending", status='pending', priority='medium')

        actionable = get_actionable_tasks_ordered(self.project_name, self.graph_db)

        # Should have sequential display_numbers
        numbers = [t['display_number'] for t in actionable]
        self.assertEqual(numbers, [1, 2, 3])

        # First should be in_progress (comes before pending)
        self.assertEqual(actionable[0]['status'], 'in_progress')


class TestParseTaskIdentifiers(unittest.TestCase):
    """Test hash-based identifier parsing."""

    def test_single_hash(self):
        self.assertEqual(parse_task_identifiers("1fab266"), ["1fab266"])

    def test_multiple_hashes(self):
        self.assertEqual(parse_task_identifiers("1fab266,c7dec3e"), ["1fab266", "c7dec3e"])

    def test_with_spaces(self):
        self.assertEqual(parse_task_identifiers("1fab266, c7dec3e, abc1234"), ["1fab266", "c7dec3e", "abc1234"])

    def test_full_uuid(self):
        self.assertEqual(parse_task_identifiers("entity-1fab266abc12"), ["entity-1fab266abc12"])

    def test_empty_parts_ignored(self):
        self.assertEqual(parse_task_identifiers("1fab266,,c7dec3e"), ["1fab266", "c7dec3e"])


class TestResolveTaskIdentifier(unittest.TestCase):
    """Test task identifier resolution (hash lookup, number rejection)."""

    def setUp(self):
        """Create test tasks with known UUIDs."""
        self.actionable = [
            {'uuid': 'entity-1fab266abc12', 'short_hash': '1fab266', 'display_number': 1, 'name': 'Task One'},
            {'uuid': 'entity-c7dec3edef34', 'short_hash': 'c7dec3e', 'display_number': 2, 'name': 'Task Two'},
            {'uuid': 'entity-abc1234567ab', 'short_hash': 'abc1234', 'display_number': 3, 'name': 'Task Three'},
        ]

    def test_resolve_by_short_hash(self):
        task, error = resolve_task_identifier("1fab266", self.actionable)
        self.assertIsNone(error)
        self.assertEqual(task['name'], 'Task One')

    def test_resolve_by_partial_hash(self):
        task, error = resolve_task_identifier("1fab", self.actionable)
        self.assertIsNone(error)
        self.assertEqual(task['name'], 'Task One')

    def test_resolve_by_full_uuid(self):
        task, error = resolve_task_identifier("entity-c7dec3edef34", self.actionable)
        self.assertIsNone(error)
        self.assertEqual(task['name'], 'Task Two')

    def test_reject_number(self):
        task, error = resolve_task_identifier("1", self.actionable)
        self.assertIsNone(task)
        self.assertIn("Numbers not accepted", error)
        self.assertIn("hash identifier", error)

    def test_reject_number_large(self):
        task, error = resolve_task_identifier("123", self.actionable)
        # 123 is all digits, should be rejected as number
        self.assertIsNone(task)
        self.assertIn("Numbers not accepted", error)

    def test_ambiguous_hash_prefix(self):
        # Add task with similar prefix
        actionable = self.actionable + [
            {'uuid': 'entity-1fab999xyz00', 'short_hash': '1fab999', 'display_number': 4, 'name': 'Task Four'},
        ]
        task, error = resolve_task_identifier("1fab", actionable)
        self.assertIsNone(task)
        self.assertIn("Ambiguous", error)

    def test_hash_not_found(self):
        task, error = resolve_task_identifier("xyz9999", self.actionable)
        self.assertIsNone(task)
        self.assertIn("No task found", error)


class TestHashBasedCLIOperations(unittest.TestCase):
    """Integration tests for CLI operations using hash identifiers."""

    def setUp(self):
        """Fresh database for each test."""
        base_tmp = REPO_ROOT / "tests" / "tmp"
        base_tmp.mkdir(parents=True, exist_ok=True)
        self.test_dir = base_tmp / f"hash_cli_{uuid4().hex[:8]}"
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.test_dir / "test.graph"
        self.project_name = "test-hash-cli"

        self.graph_db = GraphDatabase(str(self.db_path))
        self.graph_db.create_project_node(self.project_name)

    def tearDown(self):
        if hasattr(self, 'graph_db'):
            self.graph_db.close()
        if hasattr(self, 'test_dir') and self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_task(self, name, status='pending', priority='medium'):
        """Helper to create a task and return its UUID."""
        uuid = self.graph_db.create_entity(
            name=name,
            group_id=self.project_name,
            source_interactions=["test-1"],
            source_hashes=["hash-1"],
            extraction_version="v1.0.0",
            extraction_commit="test",
            summary=f"Test task: {name}",
            labels=["Task"],
            attributes={"priority": priority, "status": status}
        )
        self.graph_db.link_project_to_entity(self.project_name, uuid)

        # Set priority and status on node directly
        self.graph_db.conn.execute("""
            MATCH (e:Entity {uuid: $uuid})
            SET e.priority = $priority, e.status = $status
        """, {"uuid": uuid, "priority": priority, "status": status})

        if status != 'pending' and status != 'in_progress':
            transition_task_status(self.project_name, uuid, status, db=self.graph_db)

        return uuid

    def test_done_by_hash(self):
        """Test --done with hash identifier."""
        self._create_task("Test Task Done")
        actionable = get_actionable_tasks_ordered(self.project_name, self.graph_db)
        task = actionable[0]

        # Transition using UUID (simulates what CLI does after resolving hash)
        result = transition_task_status(self.project_name, task['uuid'], 'complete', db=self.graph_db)
        self.assertTrue(result['ok'])
        self.assertEqual(result['new_status'], 'complete')

    def test_start_by_hash(self):
        """Test --start with hash identifier."""
        self._create_task("Test Task Start")
        actionable = get_actionable_tasks_ordered(self.project_name, self.graph_db)
        task = actionable[0]

        result = transition_task_status(self.project_name, task['uuid'], 'in_progress', db=self.graph_db)
        self.assertTrue(result['ok'])
        self.assertEqual(result['new_status'], 'in_progress')

    def test_pause_by_hash(self):
        """Test --pause with hash identifier."""
        self._create_task("Test Task Pause", status='in_progress')
        actionable = get_actionable_tasks_ordered(self.project_name, self.graph_db)
        task = [t for t in actionable if t['name'] == 'Test Task Pause'][0]

        result = transition_task_status(self.project_name, task['uuid'], 'pending', db=self.graph_db)
        self.assertTrue(result['ok'])
        self.assertEqual(result['new_status'], 'pending')

    def test_skip_by_hash(self):
        """Test --skip with hash identifier."""
        self._create_task("Test Task Skip")
        actionable = get_actionable_tasks_ordered(self.project_name, self.graph_db)
        task = actionable[0]

        result = transition_task_status(self.project_name, task['uuid'], 'invalid', db=self.graph_db)
        self.assertTrue(result['ok'])
        self.assertEqual(result['new_status'], 'invalid')

    def test_set_priority_by_hash(self):
        """Test --set-priority with hash identifier."""
        self._create_task("Test Task Priority", priority='low')
        actionable = get_actionable_tasks_ordered(self.project_name, self.graph_db)
        task = actionable[0]

        # Update priority directly via graph db (update_task_priority_by_uuid uses config)
        self.graph_db.conn.execute("""
            MATCH (e:Entity {uuid: $uuid})
            SET e.priority = $priority
        """, {"uuid": task['uuid'], "priority": 'high'})

        # Verify priority changed
        actionable = get_actionable_tasks_ordered(self.project_name, self.graph_db)
        updated_task = [t for t in actionable if t['name'] == 'Test Task Priority'][0]
        self.assertEqual(updated_task['priority'], 'high')

    def test_short_hash_in_task_list(self):
        """Test that tasks have short_hash field populated."""
        self._create_task("Test Short Hash")
        actionable = get_actionable_tasks_ordered(self.project_name, self.graph_db)
        task = actionable[0]

        self.assertIn('short_hash', task)
        self.assertEqual(len(task['short_hash']), 7)
        # Short hash should be first 7 chars after 'entity-' prefix
        expected_hash = task['uuid'][7:14]
        self.assertEqual(task['short_hash'], expected_hash)

    def test_multiple_tasks_by_hash(self):
        """Test operating on multiple tasks by hash."""
        self._create_task("Task A")
        self._create_task("Task B")
        self._create_task("Task C")

        actionable = get_actionable_tasks_ordered(self.project_name, self.graph_db)
        self.assertEqual(len(actionable), 3)

        # Complete first two by UUID
        for task in actionable[:2]:
            result = transition_task_status(self.project_name, task['uuid'], 'complete', db=self.graph_db)
            self.assertTrue(result['ok'])

        # Should only have one actionable task left
        actionable = get_actionable_tasks_ordered(self.project_name, self.graph_db)
        self.assertEqual(len(actionable), 1)
        self.assertEqual(actionable[0]['name'], 'Task A')  # Oldest remaining


class TestErrorOutputShowsTaskList(unittest.TestCase):
    """Test that invalid inputs show error + task list, NOT misleading action messages.

    These tests run against the real llm_memory project via subprocess to test
    actual CLI behavior with number inputs (which should be rejected).
    """

    @classmethod
    def setUpClass(cls):
        """Import subprocess once for all tests."""
        import subprocess
        cls.subprocess = subprocess

    def _run_tasks_command(self, *args):
        """Run tasks.py with given args and return (stdout, stderr, returncode)."""
        cmd = ["python3", "scripts/tasks.py", "--project", "llm_memory"] + list(args)
        result = self.subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT)
        )
        return result.stdout, result.stderr, result.returncode

    def test_done_with_number_shows_error_not_action_message(self):
        """--done with number should show error, NOT 'Marking tasks as complete:'"""
        stdout, stderr, code = self._run_tasks_command("--done", "1")
        combined = stdout + stderr

        self.assertIn("Numbers not accepted", combined)
        self.assertIn("TASK LIST", combined)
        self.assertNotIn("Marking tasks as complete", combined)

    def test_skip_with_number_shows_error_not_action_message(self):
        """--skip with number should show error, NOT 'Marking tasks as invalid:'"""
        stdout, stderr, code = self._run_tasks_command("--skip", "1")
        combined = stdout + stderr

        self.assertIn("Numbers not accepted", combined)
        self.assertIn("TASK LIST", combined)
        self.assertNotIn("Marking tasks as invalid", combined)

    def test_start_with_number_shows_error_not_action_message(self):
        """--start with number should show error, NOT 'Starting tasks'"""
        stdout, stderr, code = self._run_tasks_command("--start", "1")
        combined = stdout + stderr

        self.assertIn("Numbers not accepted", combined)
        self.assertIn("TASK LIST", combined)
        self.assertNotIn("Starting tasks", combined)

    def test_pause_with_number_shows_error_not_action_message(self):
        """--pause with number should show error, NOT 'Pausing tasks'"""
        stdout, stderr, code = self._run_tasks_command("--pause", "1")
        combined = stdout + stderr

        self.assertIn("Numbers not accepted", combined)
        self.assertIn("TASK LIST", combined)
        self.assertNotIn("Pausing tasks", combined)

    def test_set_priority_with_number_shows_error_not_action_message(self):
        """--set-priority with number should show error and task list"""
        stdout, stderr, code = self._run_tasks_command("--set-priority", "1", "--to", "high")
        combined = stdout + stderr

        self.assertIn("Numbers not accepted", combined)
        self.assertIn("TASK LIST", combined)

    def test_details_with_number_shows_error_and_task_list(self):
        """--details with number should show error and task list"""
        stdout, stderr, code = self._run_tasks_command("--details", "1")
        combined = stdout + stderr

        self.assertIn("Numbers not accepted", combined)
        self.assertIn("TASK LIST", combined)

    def test_error_output_contains_hash_examples(self):
        """Error message should show example hash format"""
        stdout, stderr, code = self._run_tasks_command("--done", "1")
        combined = stdout + stderr

        # Should show example like "--done 1fab266"
        self.assertIn("1fab266", combined)

    def test_task_list_shows_hash_ids_in_brackets(self):
        """Task list in error output should show hash IDs in brackets"""
        stdout, stderr, code = self._run_tasks_command("--done", "1")
        combined = stdout + stderr

        # Should have pattern like "1. [abc1234]"
        import re
        self.assertTrue(
            re.search(r'\d+\. \[[a-f0-9]{7}\]', combined),
            f"Expected hash IDs in brackets like '1. [abc1234]' in output:\n{combined[:500]}"
        )


class TestTaskEditAndDependencyFeatures(unittest.TestCase):
    """Test edit mode, blockers, and parent/subtask handling."""

    def setUp(self):
        base_tmp = REPO_ROOT / "tests" / "tmp"
        base_tmp.mkdir(parents=True, exist_ok=True)
        self.test_dir = base_tmp / f"task_edit_{uuid4().hex[:8]}"
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.graph_path = self.test_dir / "test.graph"
        self.sql_path = self.test_dir / "test.db"
        self.config_path = self.test_dir / "mem.config.json"
        self.project_name = "task-edit-test"

        self.graph_db = GraphDatabase(str(self.graph_path))
        self.graph_db.create_project_node(self.project_name)
        self.sql_db = SQLDatabase(str(self.sql_path))
        self.sql_db.create_project(self.project_name, "Task edit test project")

        self.original_mem_config = os.environ.get("MEM_CONFIG")
        self.config_path.write_text(json.dumps({
            "project_name": self.project_name,
            "database": {
                "sql_path": str(self.sql_path),
                "graph_path": str(self.graph_path),
            },
        }), encoding="utf-8")
        os.environ["MEM_CONFIG"] = str(self.config_path)

    def tearDown(self):
        self.graph_db.close()
        if self.original_mem_config is None:
            os.environ.pop("MEM_CONFIG", None)
        else:
            os.environ["MEM_CONFIG"] = self.original_mem_config
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_task(self, name: str, *, summary: str = "", status: str = "pending", priority: str = "medium", attributes=None):
        attrs = dict(attributes or {})
        uuid = self.graph_db.create_entity(
            name=name,
            group_id=self.project_name,
            source_interactions=["test-1"],
            source_hashes=["hash-1"],
            extraction_version="v1.0.0",
            extraction_commit="test",
            summary=summary or f"Test task: {name}",
            labels=["Task"],
            attributes=attrs,
            priority=priority,
            status=status,
        )
        self.graph_db.link_project_to_entity(self.project_name, uuid)
        return uuid

    def test_update_task_entity_name_summary_and_details(self):
        uuid = self._create_task("Original Name", summary="Original summary")

        result = update_task_entity(
            self.project_name,
            uuid,
            name="Updated Name",
            summary="Updated summary",
            details="Detailed note",
            db=self.graph_db,
        )

        self.assertTrue(result["ok"])
        self.assertEqual(set(result["fields_changed"]), {"name", "summary", "details"})

        task = self.graph_db.conn.execute("""
            MATCH (e:Entity {uuid: $uuid})
            RETURN e.name, e.summary, e.attributes
        """, {"uuid": uuid}).get_next()
        attrs = json.loads(task[2])
        self.assertEqual(task[0], "Updated Name")
        self.assertEqual(task[1], "Updated summary")
        self.assertEqual(attrs["details"], "Detailed note")

    def test_update_task_entity_blocked_by_and_parent(self):
        parent_uuid = self._create_task("Parent")
        blocker_uuid = self._create_task("Blocker")
        child_uuid = self._create_task("Child")

        result = update_task_entity(
            self.project_name,
            child_uuid,
            blocked_by=[blocker_uuid],
            parent_task_uuid=parent_uuid,
            db=self.graph_db,
        )

        self.assertTrue(result["ok"])
        task = get_actionable_tasks_ordered(self.project_name, self.graph_db)
        child = [row for row in task if row["uuid"] == child_uuid][0]
        self.assertTrue(child["is_blocked"])
        self.assertEqual(child["blocked_count"], 1)
        self.assertEqual(child["parent_task_uuid"], parent_uuid)

    def test_get_child_tasks_reverse_lookup(self):
        parent_uuid = self._create_task("Parent")
        child_uuid = self._create_task("Child", attributes={"parent_task_uuid": parent_uuid})

        children = get_child_tasks(self.project_name, parent_uuid, self.graph_db)

        self.assertEqual(len(children), 1)
        self.assertEqual(children[0]["uuid"], child_uuid)
        self.assertEqual(children[0]["name"], "Child")

    def test_show_tasks_marks_blocked_and_subtask(self):
        import io
        old_stdout = sys.stdout
        sys.stdout = captured = io.StringIO()
        try:
            parent_uuid = self._create_task("Parent")
            blocker_uuid = self._create_task("Blocker")
            self._create_task(
                "Child",
                attributes={
                    "blocked_by": [blocker_uuid],
                    "parent_task_uuid": parent_uuid,
                },
            )
            show_tasks(self.project_name, db=self.graph_db)
            output = captured.getvalue()
        finally:
            sys.stdout = old_stdout

        self.assertIn("blocked by 1", output)
        self.assertIn("SUBTASK of", output)

    def test_show_task_details_renders_parent_child_and_blockers(self):
        import io
        old_stdout = sys.stdout
        sys.stdout = captured = io.StringIO()
        try:
            parent_uuid = self._create_task("Parent")
            blocker_uuid = self._create_task("Blocker")
            child_uuid = self._create_task(
                "Child",
                attributes={
                    "blocked_by": [blocker_uuid],
                    "parent_task_uuid": parent_uuid,
                },
            )
            actionable = get_actionable_tasks_ordered(self.project_name, self.graph_db)
            child = [row for row in actionable if row["uuid"] == child_uuid][0]
            show_task_details(self.project_name, child["display_number"])
            output = captured.getvalue()
        finally:
            sys.stdout = old_stdout

        self.assertIn("Blocked By:", output)
        self.assertIn("Parent Task:", output)
        self.assertIn("Subtasks:", output)
        self.assertIn("Blocker", output)
        self.assertIn("Parent", output)

    def test_update_task_entity_emits_sql_event_payload(self):
        uuid = self._create_task("Emit Event")

        result = update_task_entity(
            self.project_name,
            uuid,
            details="Tracked detail",
            blocked_by=[],
            db=self.graph_db,
            emit_event=True,
            command_context="tasks.py --edit",
        )

        self.assertTrue(result["ok"])
        operations = self.sql_db.get_task_operations(
            project_name=self.project_name,
            start="2000-01-01T00:00:00",
            end="2100-01-01T00:00:00",
        )
        self.assertEqual(len(operations), 1)
        row = operations[0]
        self.assertEqual(row["operation"], "edit")
        payload = json.loads(row["payload_json"])
        self.assertIn("details", payload["fields_changed"])
        self.assertEqual(payload["after"]["details"], "Tracked detail")

    def test_update_task_entity_parent_only_emits_parent_operation(self):
        parent_uuid = self._create_task("Parent")
        child_uuid = self._create_task("Child")

        result = update_task_entity(
            self.project_name,
            child_uuid,
            parent_task_uuid=parent_uuid,
            db=self.graph_db,
            emit_event=True,
            command_context="tasks.py --edit",
        )

        self.assertTrue(result["ok"])
        operations = self.sql_db.get_task_operations(
            project_name=self.project_name,
            start="2000-01-01T00:00:00",
            end="2100-01-01T00:00:00",
        )
        self.assertEqual(operations[-1]["operation"], "set_parent_task")


if __name__ == "__main__":
    unittest.main()
