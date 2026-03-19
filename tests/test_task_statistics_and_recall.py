#!/usr/bin/env python3
"""Tests for task statistics and recall task-activity integration."""

import io
import shutil
import sqlite3
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from typing import Optional
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts import recall as recall_script
from scripts import tasks as tasks_script
from tools.graph_db import GraphDatabase
from tools.sql_db import SQLDatabase


REPO_ROOT = Path(__file__).parent.parent


class FakeConfig:
    """Small config stub for tests that need SQL and graph paths."""

    def __init__(self, sql_path: str, graph_path: Optional[str] = None):
        self._sql_path = sql_path
        self._graph_path = graph_path

    def get_sql_db_path(self):
        return self._sql_path

    def get_graph_db_path(self, _project_name):
        if self._graph_path is None:
            raise AssertionError("graph path not configured for test")
        return self._graph_path


class TaskStatsBase(unittest.TestCase):
    def setUp(self):
        base_tmp = REPO_ROOT / "tests" / "tmp"
        base_tmp.mkdir(parents=True, exist_ok=True)
        self.test_dir = base_tmp / f"task_stats_{uuid4().hex[:8]}"
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.project_name = "task-stats-test"
        self.sql_path = self.test_dir / "conversations.db"
        self.sql_db = SQLDatabase(str(self.sql_path))

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def record_task_event(
        self,
        *,
        created_at: str,
        operation: str,
        task_name: str,
        task_uuid: Optional[str] = None,
        status_before: Optional[str] = None,
        status_after: Optional[str] = None,
        priority_before: Optional[str] = None,
        priority_after: Optional[str] = None,
    ):
        event_uuid = self.sql_db.record_task_operation(
            project_name=self.project_name,
            operation=operation,
            success=True,
            task_name=task_name,
            task_uuid=task_uuid,
            status_before=status_before,
            status_after=status_after,
            priority_before=priority_before,
            priority_after=priority_after,
        )
        conn = sqlite3.connect(self.sql_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE task_operations SET created_at = ? WHERE event_uuid = ?",
            (created_at, event_uuid),
        )
        conn.commit()
        conn.close()


class TestTaskOperationStats(TaskStatsBase):
    def setUp(self):
        super().setUp()
        self.record_task_event(
            created_at="2026-03-16T00:01:00",
            operation="add",
            task_name="Add API",
            task_uuid="entity-add12345",
            status_after="pending",
            priority_after="high",
        )
        self.record_task_event(
            created_at="2026-03-16T00:02:00",
            operation="in_progress",
            task_name="Add API",
            task_uuid="entity-add12345",
            status_before="pending",
            status_after="in_progress",
        )
        self.record_task_event(
            created_at="2026-03-16T00:03:00",
            operation="pending",
            task_name="Add API",
            task_uuid="entity-add12345",
            status_before="in_progress",
            status_after="pending",
        )
        self.record_task_event(
            created_at="2026-03-16T00:04:00",
            operation="complete",
            task_name="Add API",
            task_uuid="entity-add12345",
            status_before="pending",
            status_after="complete",
        )
        self.record_task_event(
            created_at="2026-03-16T00:05:00",
            operation="set_priority",
            task_name="Investigate bug",
            task_uuid="entity-bug12345",
            priority_before="medium",
            priority_after="high",
        )
        self.record_task_event(
            created_at="2026-03-16T00:06:00",
            operation="invalid",
            task_name="Wrong task",
            task_uuid="entity-skip1234",
            status_before="pending",
            status_after="invalid",
        )
        self.record_task_event(
            created_at="2026-03-16T00:07:00",
            operation="pending",
            task_name="Not paused",
            task_uuid="entity-pend1234",
            status_before="pending",
            status_after="pending",
        )

    def test_get_task_operations_filters_window_and_status(self):
        rows = self.sql_db.get_task_operations(
            project_name=self.project_name,
            start="2026-03-16T00:01:30",
            end="2026-03-16T00:07:30",
            status_after="pending",
        )
        self.assertEqual([row["task_name"] for row in rows], ["Add API", "Not paused"])

    def test_get_task_operation_stats_classifies_events(self):
        stats = self.sql_db.get_task_operation_stats(
            project_name=self.project_name,
            start="2026-03-16T00:00:00",
            end="2026-03-16T00:10:00",
        )
        self.assertEqual(stats["created"], 1)
        self.assertEqual(stats["started"], 1)
        self.assertEqual(stats["paused"], 1)
        self.assertEqual(stats["completed"], 1)
        self.assertEqual(stats["invalidated"], 1)
        self.assertEqual(stats["priority_changed"], 1)
        self.assertEqual(stats["total_events"], 6)

    def test_get_task_operation_stats_empty_window(self):
        stats = self.sql_db.get_task_operation_stats(
            project_name=self.project_name,
            start="2026-03-17T00:00:00",
            end="2026-03-17T23:59:59",
        )
        self.assertEqual(
            stats,
            {
                "created": 0,
                "started": 0,
                "paused": 0,
                "completed": 0,
                "invalidated": 0,
                "priority_changed": 0,
                "total_events": 0,
            },
        )


class TestTaskStatsCLI(TaskStatsBase):
    def test_normalize_stats_window_custom_and_rolling(self):
        start, end = tasks_script.normalize_stats_window(
            "week",
            now=tasks_script.datetime(2026, 3, 16, 12, 30, 0),
        )
        self.assertEqual(start, "2026-03-10T00:00:00")
        self.assertEqual(end, "2026-03-16T23:59:59")

        custom_start, custom_end = tasks_script.normalize_stats_window(
            "custom",
            from_value="2026-03-10",
            to_value="2026-03-16",
        )
        self.assertEqual(custom_start, "2026-03-10T00:00:00")
        self.assertEqual(custom_end, "2026-03-16T23:59:59")

    def test_render_task_stats_verbose_output(self):
        self.record_task_event(
            created_at="2026-03-16T01:23:45",
            operation="complete",
            task_name="Ship feature",
            task_uuid="entity-abc123456789",
            status_before="in_progress",
            status_after="complete",
        )
        fake_config = FakeConfig(str(self.sql_path))
        output = io.StringIO()
        with patch("scripts.tasks.load_config", return_value=fake_config):
            with redirect_stdout(output):
                result = tasks_script.render_task_stats(
                    self.project_name,
                    "today",
                    "2026-03-16T00:00:00",
                    "2026-03-16T23:59:59",
                    verbose=True,
                )
        text = output.getvalue()
        self.assertEqual(result, 0)
        self.assertIn("TASK STATS - task-stats-test", text)
        self.assertIn("Completed:        1", text)
        self.assertIn("2026-03-16T01:23:45", text)
        self.assertIn("COMPLETED [abc1234]  Ship feature", text)

    def test_stats_main_rejects_mutation_combination(self):
        with self.assertRaises(SystemExit) as exc:
            tasks_script.main(["--project", "demo", "--stats", "today", "--done", "abc1234"])
        self.assertEqual(exc.exception.code, 2)


class TestGraphCreatedBetween(unittest.TestCase):
    def setUp(self):
        base_tmp = REPO_ROOT / "tests" / "tmp"
        base_tmp.mkdir(parents=True, exist_ok=True)
        self.test_dir = base_tmp / f"task_created_{uuid4().hex[:8]}"
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.project_name = "task-created-test"
        self.graph_path = self.test_dir / "memory.graph"
        self.graph_db = GraphDatabase(str(self.graph_path))
        self.graph_db.create_project_node(self.project_name)

    def tearDown(self):
        self.graph_db.close()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_task(self, name: str, created_at: str, status: str = "pending"):
        entity_uuid = self.graph_db.create_entity(
            name=name,
            group_id=self.project_name,
            source_interactions=["test-1"],
            source_hashes=["hash-1"],
            extraction_version="v1.0.0",
            extraction_commit="test",
            summary=f"Summary for {name}",
            labels=["Task"],
            attributes={},
            priority="medium",
            status=status,
        )
        self.graph_db.link_project_to_entity(self.project_name, entity_uuid)
        self.graph_db.conn.execute(
            """
            MATCH (e:Entity {uuid: $uuid})
            SET e.created_at = timestamp($created_at)
            """,
            {"uuid": entity_uuid, "created_at": created_at},
        )
        return entity_uuid

    def test_show_tasks_created_between_uses_graph_created_at(self):
        self._create_task("Inside Window", "2026-03-16T10:30:00")
        self._create_task("Outside Window", "2026-03-18T10:30:00")
        fake_config = FakeConfig(sql_path=str(self.test_dir / "unused.db"), graph_path=str(self.graph_path))
        output = io.StringIO()
        with patch("scripts.tasks.load_config", return_value=fake_config):
            with redirect_stdout(output):
                result = tasks_script.show_tasks_created_between(
                    self.project_name,
                    "2026-03-16T00:00:00",
                    "2026-03-16T23:59:59",
                )
        text = output.getvalue()
        self.assertEqual(result, 0)
        self.assertIn("TASKS CREATED - task-created-test", text)
        self.assertIn("Inside Window", text)
        self.assertNotIn("Outside Window", text)
        self.assertIn("Total created tasks: 1", text)

    def test_created_between_main_requires_explicit_window(self):
        with self.assertRaises(SystemExit) as exc:
            tasks_script.main(["--project", "demo", "--created-between", "--from", "2026-03-10"])
        self.assertEqual(exc.exception.code, 2)


class TestRecallTaskActivity(TaskStatsBase):
    def setUp(self):
        super().setUp()
        self.graph_path = self.test_dir / "memory.graph"
        graph_db = GraphDatabase(str(self.graph_path))
        graph_db.create_project_node(self.project_name)
        entity_uuid = graph_db.create_entity(
            name="Recall Entity",
            group_id=self.project_name,
            source_interactions=["test-1"],
            source_hashes=["hash-1"],
            extraction_version="v1.0.0",
            extraction_commit="test",
            summary="Entity visible in recall output",
            labels=["Concept"],
            attributes={},
        )
        graph_db.link_project_to_entity(self.project_name, entity_uuid)
        graph_db.conn.execute(
            """
            MATCH (e:Entity {uuid: $uuid})
            SET e.extraction_timestamp_str = $timestamp
            """,
            {"uuid": entity_uuid, "timestamp": "2026-03-16T00:30:00"},
        )
        graph_db.close()

        self.record_task_event(
            created_at="2026-03-16T00:11:02",
            operation="add",
            task_name="Task Statistics and Recall Integration",
            task_uuid="entity-6326de0abc12",
            status_after="pending",
        )

    def test_recall_includes_task_activity(self):
        fake_config = FakeConfig(str(self.sql_path), str(self.graph_path))
        output = io.StringIO()
        with patch("scripts.recall.load_config", return_value=fake_config):
            with redirect_stdout(output):
                recall_script.main([
                    "--project",
                    self.project_name,
                    "--graph-db",
                    str(self.graph_path),
                    "--start",
                    "2026-03-16",
                    "--end",
                    "2026-03-16",
                ])
        text = output.getvalue()
        self.assertIn("Recall Entity", text)
        self.assertIn("TASK ACTIVITY", text)
        self.assertIn("CREATED [6326de0] Task Statistics and Recall Integration", text)
        self.assertIn("Task events in window: 1", text)

    def test_recall_hide_task_activity(self):
        fake_config = FakeConfig(str(self.sql_path), str(self.graph_path))
        output = io.StringIO()
        with patch("scripts.recall.load_config", return_value=fake_config):
            with redirect_stdout(output):
                recall_script.main([
                    "--project",
                    self.project_name,
                    "--graph-db",
                    str(self.graph_path),
                    "--start",
                    "2026-03-16",
                    "--end",
                    "2026-03-16",
                    "--hide-task-activity",
                ])
        text = output.getvalue()
        self.assertIn("Recall Entity", text)
        self.assertNotIn("TASK ACTIVITY", text)
        self.assertNotIn("Task events in window", text)

    def test_recall_limit_prefers_most_recent_entities(self):
        graph_db = GraphDatabase(str(self.graph_path))
        older_uuid = graph_db.create_entity(
            name="Older Recall Entity",
            group_id=self.project_name,
            source_interactions=["test-older"],
            source_hashes=["hash-older"],
            extraction_version="v1.0.0",
            extraction_commit="test",
            summary="Older entity",
            labels=["Concept"],
            attributes={},
        )
        newer_uuid = graph_db.create_entity(
            name="Newer Recall Entity",
            group_id=self.project_name,
            source_interactions=["test-newer"],
            source_hashes=["hash-newer"],
            extraction_version="v1.0.0",
            extraction_commit="test",
            summary="Newer entity",
            labels=["Concept"],
            attributes={},
        )
        graph_db.link_project_to_entity(self.project_name, older_uuid)
        graph_db.link_project_to_entity(self.project_name, newer_uuid)
        graph_db.conn.execute(
            """
            MATCH (e:Entity {uuid: $uuid})
            SET e.extraction_timestamp_str = $timestamp
            """,
            {"uuid": older_uuid, "timestamp": "2026-03-16T00:05:00"},
        )
        graph_db.conn.execute(
            """
            MATCH (e:Entity {uuid: $uuid})
            SET e.extraction_timestamp_str = $timestamp
            """,
            {"uuid": newer_uuid, "timestamp": "2026-03-16T23:55:00"},
        )
        graph_db.close()

        fake_config = FakeConfig(str(self.sql_path), str(self.graph_path))
        output = io.StringIO()
        with patch("scripts.recall.load_config", return_value=fake_config):
            with redirect_stdout(output):
                recall_script.main([
                    "--project",
                    self.project_name,
                    "--graph-db",
                    str(self.graph_path),
                    "--start",
                    "2026-03-16",
                    "--end",
                    "2026-03-16",
                    "--limit",
                    "1",
                    "--hide-task-activity",
                ])
        text = output.getvalue()
        self.assertIn("Newer Recall Entity", text)
        self.assertNotIn("Older Recall Entity", text)
        self.assertIn("Showing 1 of 3 entities in window (per-day limit: 1)", text)
        self.assertIn("Recall output was truncated. Increase --limit to see more entities.", text)


if __name__ == "__main__":
    unittest.main()
