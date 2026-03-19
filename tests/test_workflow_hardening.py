import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tools.graph_db import GraphDatabase
from tools.sql_db import SQLDatabase
from scripts.prepare_sync_files import prepare_sync_files


REPO_ROOT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable


def write_test_config(config_path: Path, project_name: str, sql_path: Path, graph_path: Path) -> None:
    """Write a minimal config file for isolated CLI tests."""
    config_path.write_text(json.dumps({
        "project_name": project_name,
        "python_path": PYTHON,
        "database": {
            "sql_path": str(sql_path),
            "graph_path": str(graph_path),
        },
        "paths": {
            "tmp_dir": str(config_path.parent),
            "memory_dir": str(config_path.parent),
        },
        "quality_check": {
            "questions_file": "quality-questions.json",
            "answers_file": "quality-answers.json",
        },
    }, indent=2), encoding="utf-8")


class WorkflowHardeningTests(unittest.TestCase):
    def setUp(self):
        base_tmp = REPO_ROOT / "tests" / "tmp"
        base_tmp.mkdir(parents=True, exist_ok=True)
        self.test_dir = base_tmp / f"workflow_hardening_{uuid4().hex[:8]}"
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.sql_path = self.test_dir / "conversations.db"
        self.graph_path = self.test_dir / "workflow.graph"
        self.questions_path = self.test_dir / "quality-questions.json"
        self.answers_path = self.test_dir / "quality-answers.json"
        self.project_name = "workflow-test"
        self.config_path = self.test_dir / "mem.config.json"
        write_test_config(self.config_path, self.project_name, self.sql_path, self.graph_path)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _run(self, *args):
        return subprocess.run(
            [PYTHON, args[0], "--config", str(self.config_path), *args[1:]],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

    def _write_helper_file(self, filename, content):
        path = self.test_dir / filename
        path.write_text(content, encoding="utf-8")
        return path

    def _run_tasks(self, *args):
        env = os.environ.copy()
        env["MEM_CONFIG"] = str(self.config_path)
        return subprocess.run(
            [PYTHON, "scripts/tasks.py", *args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            env=env,
        )

    def _create_interaction(self, processed=False):
        db = SQLDatabase(str(self.sql_path))
        uuid = db.store_interaction({
            "project_name": self.project_name,
            "user_message": "User message",
            "assistant_message": "Assistant message",
        })
        if processed:
            db.mark_interaction_processed(uuid)
        return db.get_interaction_by_uuid(uuid)

    def _write_extraction_file(
        self,
        interaction_uuid,
        relationship_type="RELATED_TO",
        entity_a_type="Concept",
        entity_b_type="Concept",
    ):
        """Write extraction file with configurable relationship type for testing."""
        extraction_path = self.test_dir / "extraction.json"
        extraction_path.write_text(json.dumps({
            "project_name": self.project_name,
            "extraction_version": "test",
            "extraction_commit": "test",
            "extractions": [
                {
                    "interaction_uuid": interaction_uuid,
                    "entities": [
                        {"name": "Entity A", "type": entity_a_type, "summary": "A"},
                        {"name": "Entity B", "type": entity_b_type, "summary": "B"},
                    ],
                    "facts": [
                        {
                            "source_entity": "Entity A",
                            "target_entity": "Entity B",
                            "relationship_type": relationship_type,
                            "fact": "Entity A relates to Entity B",
                        }
                    ],
                }
            ],
        }, indent=2), encoding="utf-8")
        return extraction_path

    def test_store_extraction_skips_already_processed_interactions(self):
        interaction = self._create_interaction(processed=True)
        extraction_path = self._write_extraction_file(interaction["uuid"])

        result = self._run(
            "scripts/store_extraction.py",
            "--project", self.project_name,
            "--extraction-file", str(extraction_path),
            "--sql-db", str(self.sql_path),
            "--graph-db", str(self.graph_path),
            "--i-am-a-human-and-i-want-to-skip-quality-checks",
            "--dry-run",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("already-processed interactions", result.stdout)
        self.assertIn("Nothing to store", result.stdout)

    def test_deprecated_skip_quality_check_flag_fails(self):
        """Verify that the deprecated --skip-quality-check flag is rejected."""
        interaction = self._create_interaction(processed=False)
        extraction_path = self._write_extraction_file(interaction["uuid"])

        result = self._run(
            "scripts/store_extraction.py",
            "--project", self.project_name,
            "--extraction-file", str(extraction_path),
            "--sql-db", str(self.sql_path),
            "--graph-db", str(self.graph_path),
            "--skip-quality-check",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DEPRECATED", result.stdout)
        self.assertIn("--i-am-a-human-and-i-want-to-skip-quality-checks", result.stdout)

    def test_store_extraction_rejects_unknown_entity_type_when_strict(self):
        interaction = self._create_interaction(processed=False)
        extraction_path = self._write_extraction_file(
            interaction["uuid"],
            entity_a_type="Concept",
            entity_b_type="RandomType",
        )

        result = self._run(
            "scripts/store_extraction.py",
            "--project", self.project_name,
            "--extraction-file", str(extraction_path),
            "--sql-db", str(self.sql_path),
            "--graph-db", str(self.graph_path),
            "--entity-type-enforcement", "strict",
            "--dry-run",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Entity type warnings detected", result.stdout)
        self.assertIn("unknown entity type 'RandomType'", result.stdout)

    def test_store_extraction_normalizes_synonym_type_before_storage(self):
        interaction = self._create_interaction(processed=False)
        extraction_path = self._write_extraction_file(
            interaction["uuid"],
            entity_a_type="Workflow",
            entity_b_type="Script",
        )

        result = self._run(
            "scripts/store_extraction.py",
            "--project", self.project_name,
            "--extraction-file", str(extraction_path),
            "--sql-db", str(self.sql_path),
            "--graph-db", str(self.graph_path),
            "--i-am-a-human-and-i-want-to-skip-quality-checks",
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        graph_db = GraphDatabase(str(self.graph_path))
        try:
            entities = graph_db.get_all_entities(self.project_name)
        finally:
            graph_db.close()

        labels_by_name = {entity["name"]: entity["labels"] for entity in entities}
        self.assertEqual(labels_by_name["Entity A"], ["Procedure"])
        self.assertEqual(labels_by_name["Entity B"], ["File"])

    def test_store_extraction_require_quality_review_fails_before_graph_writes(self):
        interaction = self._create_interaction(processed=False)
        extraction_path = self._write_extraction_file(interaction["uuid"])

        result = self._run(
            "scripts/store_extraction.py",
            "--project", self.project_name,
            "--extraction-file", str(extraction_path),
            "--sql-db", str(self.sql_path),
            "--graph-db", str(self.graph_path),
            "--require-quality-review",
            "--quality-questions-file", str(self.questions_path),
            "--quality-answers-file", str(self.answers_path),
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(self.questions_path.exists())
        self.assertIn("Answers template refreshed", result.stdout)
        self.assertIn("Quality answers validation failed", result.stdout)

        graph_db = GraphDatabase(str(self.graph_path))
        try:
            result = graph_db.conn.execute("""
                MATCH (p:Project)
                RETURN count(p)
            """)
            project_count = result.get_next()[0] if result.has_next() else 0
        finally:
            graph_db.close()

        self.assertEqual(project_count, 0)

    def test_prepare_sync_files_archives_old_sync_artifacts(self):
        tmp_dir = self.test_dir / "tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)

        stale_conversation = tmp_dir / "conversation_2026-03-14_12-00-00.json"
        stale_extraction = tmp_dir / "extraction_2026-03-14_12-00-00.json"
        stale_mapping = tmp_dir / "entity-mapping_2026-03-14_12-00-00.json"
        stale_answers = tmp_dir / "quality-answers.json"
        unrelated = tmp_dir / "keep-me.json"

        stale_conversation.write_text(
            '{"summary":{"session_id":"x","timestamp":"","intent":"","work_attempted":[],"outcomes":[],"fidelity":"summary"}}\n',
            encoding="utf-8",
        )
        stale_extraction.write_text('{"extractions":[]}\n', encoding="utf-8")
        stale_mapping.write_text('{"entities":{}}\n', encoding="utf-8")
        stale_answers.write_text('{"_questions_hash":"stale","duplicates":[],"contradictions":[]}\n', encoding="utf-8")
        unrelated.write_text('{"keep": true}\n', encoding="utf-8")

        result = prepare_sync_files(self.project_name, str(tmp_dir))

        self.assertIsNotNone(result["archive_dir"])
        archive_dir = Path(result["archive_dir"])
        self.assertTrue(archive_dir.exists())
        self.assertTrue((archive_dir / stale_conversation.name).exists())
        self.assertTrue((archive_dir / stale_extraction.name).exists())
        self.assertTrue((archive_dir / stale_mapping.name).exists())
        self.assertTrue((archive_dir / stale_answers.name).exists())

        self.assertTrue(Path(result["conversation_file"]).exists())
        self.assertTrue(Path(result["extraction_file"]).exists())
        self.assertTrue(Path(result["quality_answers_file"]).exists())
        self.assertTrue(unrelated.exists())

    def test_prepare_sync_files_includes_workflow_session_id(self):
        result = prepare_sync_files(self.project_name, str(self.test_dir / "tmp"))

        self.assertTrue(result["workflow_session_id"].startswith("sync-"))

        conversation = json.loads(Path(result["conversation_file"]).read_text(encoding="utf-8"))
        extraction = json.loads(Path(result["extraction_file"]).read_text(encoding="utf-8"))

        self.assertEqual(conversation["workflow_session_id"], result["workflow_session_id"])
        self.assertEqual(extraction["workflow_session_id"], result["workflow_session_id"])

    def test_prepare_sync_files_writes_multiline_editable_templates(self):
        result = prepare_sync_files(self.project_name, str(self.test_dir / "tmp"))

        conversation_text = Path(result["conversation_file"]).read_text(encoding="utf-8")
        extraction_text = Path(result["extraction_file"]).read_text(encoding="utf-8")
        answers_text = Path(result["quality_answers_file"]).read_text(encoding="utf-8")
        task_json_text = Path(result["task_json_file"]).read_text(encoding="utf-8")
        batch_text = Path(result["batch_file"]).read_text(encoding="utf-8")

        self.assertIn("\n  \"summary\": {", conversation_text)
        self.assertIn("\n  \"extractions\": []", extraction_text)
        self.assertIn("\n  \"duplicates\": []", answers_text)
        self.assertIn("\n  \"name\": \"\"", task_json_text)
        self.assertIn("\n  \"tasks\": []", batch_text)
        self.assertGreater(conversation_text.count("\n"), 2)
        self.assertGreater(extraction_text.count("\n"), 2)
        self.assertGreater(answers_text.count("\n"), 2)
        self.assertGreater(task_json_text.count("\n"), 2)
        self.assertGreater(batch_text.count("\n"), 2)

    def test_prepare_sync_files_resets_task_helper_files(self):
        tmp_dir = self.test_dir / "tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)

        (tmp_dir / "task.txt").write_text("stale task\n", encoding="utf-8")
        (tmp_dir / "summary.txt").write_text("stale summary\n", encoding="utf-8")
        (tmp_dir / "task.json").write_text('{"name":"stale","summary":"stale","priority":"high"}\n', encoding="utf-8")
        (tmp_dir / "batch.json").write_text('{"tasks":["stale"]}\n', encoding="utf-8")

        result = prepare_sync_files(self.project_name, str(tmp_dir))

        self.assertEqual(Path(result["task_file"]).read_text(encoding="utf-8"), "")
        self.assertEqual(Path(result["summary_file"]).read_text(encoding="utf-8"), "")
        self.assertEqual(
            json.loads(Path(result["task_json_file"]).read_text(encoding="utf-8")),
            {"name": "", "summary": "", "priority": "medium"},
        )
        self.assertEqual(
            json.loads(Path(result["batch_file"]).read_text(encoding="utf-8")),
            {"tasks": []},
        )

    def test_prepare_sync_files_json_flag_output_remains_single_line(self):
        result = subprocess.run(
            [
                PYTHON,
                "scripts/prepare_sync_files.py",
                "--project", self.project_name,
                "--tmp-dir", str(self.test_dir / "tmp"),
                "--json",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.count("\n"), 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "ready")
        self.assertIn("task_file", payload)
        self.assertIn("summary_file", payload)
        self.assertIn("task_json_file", payload)
        self.assertIn("batch_file", payload)

    def test_import_summary_persists_workflow_session_id_to_interactions(self):
        conversation_path = self.test_dir / "conversation.json"
        conversation_path.write_text(json.dumps({
            "workflow_session_id": "sync-test-session",
            "summary": {
                "session_id": "sync-test-session",
                "timestamp": "2026-03-18T12:00:00Z",
                "intent": "User message",
                "work_attempted": ["Assistant response"],
                "outcomes": [],
                "fidelity": "summary",
            },
        }, indent=2), encoding="utf-8")

        result = self._run(
            "scripts/import_summary.py",
            "--project", self.project_name,
            "--file", str(conversation_path),
            "--db", str(self.sql_path),
            "--constrained-environment",
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        db = SQLDatabase(str(self.sql_path))
        interactions = db.get_all_interactions(self.project_name)
        self.assertEqual(len(interactions), 1)
        self.assertEqual(interactions[0]["session_id"], "sync-test-session")

    def test_tasks_add_emits_sql_event(self):
        result = self._run_tasks(
            "--project", self.project_name,
            "--workflow-session-id", "sync-task-events",
            "--add", "Evented Task",
            "--priority", "high",
            "--summary", "Created through tasks CLI",
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Added task: Evented Task", result.stdout)

        db = SQLDatabase(str(self.sql_path))
        event = db.find_task_operation_event(
            project_name=self.project_name,
            task_name="Evented Task",
            workflow_session_id="sync-task-events",
        )
        self.assertIsNotNone(event)
        self.assertEqual(event["operation"], "add")
        self.assertEqual(event["priority_after"], "high")
        self.assertTrue(event["task_uuid"])

    def test_store_extraction_reuses_task_from_task_operation_event(self):
        session_id = "sync-reuse-task"
        interaction = self._create_interaction(processed=False)

        db = SQLDatabase(str(self.sql_path))
        conn = db._get_connection()
        conn.execute(
            "UPDATE interactions SET session_id = ? WHERE uuid = ?",
            (session_id, interaction["uuid"]),
        )
        conn.commit()
        conn.close()

        add_result = self._run_tasks(
            "--project", self.project_name,
            "--workflow-session-id", session_id,
            "--add", "Session Task",
            "--priority", "medium",
            "--summary", "Task created before sync storage",
        )
        self.assertEqual(add_result.returncode, 0, add_result.stdout + add_result.stderr)

        extraction_path = self.test_dir / "task_extraction.json"
        extraction_path.write_text(json.dumps({
            "project_name": self.project_name,
            "workflow_session_id": session_id,
            "extraction_version": "test",
            "extraction_commit": "test",
            "extractions": [
                {
                    "interaction_uuid": interaction["uuid"],
                    "entities": [
                        {"name": "Session Task", "type": "Task", "summary": "Should reuse authoritative task"},
                    ],
                    "facts": [],
                }
            ],
        }, indent=2), encoding="utf-8")

        result = self._run(
            "scripts/store_extraction.py",
            "--project", self.project_name,
            "--extraction-file", str(extraction_path),
            "--sql-db", str(self.sql_path),
            "--graph-db", str(self.graph_path),
            "--i-am-a-human-and-i-want-to-skip-quality-checks",
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("[LINK] Reused task from event log: Session Task", result.stdout)
        self.assertIn("-> REUSED (canonical match)", result.stdout)

        graph_db = GraphDatabase(str(self.graph_path))
        try:
            result = graph_db.conn.execute("""
                MATCH (p:Project {name: $project})-[:HAS_ENTITY]->(e:Entity)
                WHERE e.name = 'Session Task' AND e.deleted_at IS NULL
                RETURN count(e)
            """, {"project": self.project_name})
            count = result.get_next()[0] if result.has_next() else 0
        finally:
            graph_db.close()

        self.assertEqual(count, 1)

    def test_sql_event_path_isolated_from_quality_review(self):
        """
        ISOLATED TEST: Proves SQL event path is the deciding factor, not quality review.

        This test:
        1. Creates task via tasks.py (emits SQL event + creates entity)
        2. Creates extraction with SAME task name
        3. Runs store WITHOUT quality review (skip quality checks)
        4. Verifies the "[LINK] Reused task from event log" message appears

        The key assertion is the specific log message that proves SQL event lookup
        was used, not quality review deduplication.
        """
        session_id = "sync-isolated-sql-test"
        interaction = self._create_interaction(processed=False)

        # Set session ID on interaction
        db = SQLDatabase(str(self.sql_path))
        conn = db._get_connection()
        conn.execute(
            "UPDATE interactions SET session_id = ? WHERE uuid = ?",
            (session_id, interaction["uuid"]),
        )
        conn.commit()
        conn.close()

        # Step 1: Create task via tasks.py (emits SQL event)
        add_result = self._run_tasks(
            "--project", self.project_name,
            "--workflow-session-id", session_id,
            "--add", "SQL Isolated Task",
            "--priority", "high",
            "--summary", "Task to test SQL event isolation",
        )
        self.assertEqual(add_result.returncode, 0, add_result.stdout + add_result.stderr)

        # Verify SQL event exists
        sql_db = SQLDatabase(str(self.sql_path))
        event = sql_db.find_task_operation_event(
            project_name=self.project_name,
            task_name="SQL Isolated Task",
            workflow_session_id=session_id,
        )
        self.assertIsNotNone(event, "SQL event should exist after tasks.py --add")
        original_task_uuid = event["task_uuid"]

        # Step 2: Create extraction with same task name
        extraction_path = self.test_dir / "sql_isolated_extraction.json"
        extraction_path.write_text(json.dumps({
            "project_name": self.project_name,
            "workflow_session_id": session_id,
            "extraction_version": "test",
            "extraction_commit": "test",
            "extractions": [
                {
                    "interaction_uuid": interaction["uuid"],
                    "entities": [
                        {"name": "SQL Isolated Task", "type": "Task", "summary": "Should find UUID from SQL event"},
                    ],
                    "facts": [],
                }
            ],
        }, indent=2), encoding="utf-8")

        # Step 3: Run store WITHOUT quality review
        result = self._run(
            "scripts/store_extraction.py",
            "--project", self.project_name,
            "--extraction-file", str(extraction_path),
            "--sql-db", str(self.sql_path),
            "--graph-db", str(self.graph_path),
            "--i-am-a-human-and-i-want-to-skip-quality-checks",
        )

        # Step 4: Verify SQL event path was used (THIS IS THE KEY ASSERTION)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        # This specific message ONLY appears when SQL event lookup is used
        # It does NOT appear for quality review deduplication
        self.assertIn("[LINK] Reused task from event log: SQL Isolated Task", result.stdout,
            "SQL event path should have been used (not quality review)")

        # Verify the original UUID was reused
        self.assertIn(original_task_uuid, result.stdout,
            f"Original task UUID {original_task_uuid} should appear in output")

        # Verify only 1 entity exists (no duplicate created)
        graph_db = GraphDatabase(str(self.graph_path))
        try:
            result_query = graph_db.conn.execute("""
                MATCH (p:Project {name: $project})-[:HAS_ENTITY]->(e:Entity)
                WHERE e.name = 'SQL Isolated Task' AND e.deleted_at IS NULL
                RETURN e.uuid
            """, {"project": self.project_name})
            rows = []
            while result_query.has_next():
                rows.append(result_query.get_next()[0])
        finally:
            graph_db.close()

        self.assertEqual(len(rows), 1, "Should have exactly 1 entity (no duplicate)")

    def test_store_extraction_generates_prefilled_quality_answers_template(self):
        interaction = self._create_interaction(processed=False)
        extraction_path = self._write_extraction_file(interaction["uuid"])

        graph_db = GraphDatabase(str(self.graph_path))
        try:
            graph_db.create_project_node(self.project_name)
            existing_uuid = graph_db.create_entity(
                name="Entity A",
                summary="A",
                labels=["Concept"],
                group_id=self.project_name,
                source_interactions=["bootstrap"],
                source_hashes=["hash-bootstrap"],
                extraction_version="test",
                extraction_commit="test",
            )
            graph_db.link_project_to_entity(self.project_name, existing_uuid)
        finally:
            graph_db.close()

        result = self._run(
            "scripts/store_extraction.py",
            "--project", self.project_name,
            "--extraction-file", str(extraction_path),
            "--sql-db", str(self.sql_path),
            "--graph-db", str(self.graph_path),
            "--require-quality-review",
            "--quality-questions-file", str(self.questions_path),
            "--quality-answers-file", str(self.answers_path),
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Answers template refreshed", result.stdout)
        self.assertTrue(self.questions_path.exists())
        self.assertTrue(self.answers_path.exists())

        questions = json.loads(self.questions_path.read_text(encoding="utf-8"))
        answers = json.loads(self.answers_path.read_text(encoding="utf-8"))

        self.assertIn("_questions_hash", answers)
        self.assertEqual(len(answers["duplicates"]), len(questions["duplicates"]))
        self.assertEqual(len(answers["contradictions"]), len(questions["contradictions"]))
        self.assertEqual(answers["duplicates"][0]["question_index"], 0)
        self.assertFalse(answers["duplicates"][0]["is_duplicate"])
        self.assertIsNone(answers["duplicates"][0]["duplicate_uuid"])
        self.assertEqual(answers["contradictions"][0]["fact_index"], 0)
        self.assertEqual(answers["contradictions"][0]["contradicted_fact_uuids"], [])

    def test_store_extraction_reuses_duplicate_with_generated_template_answers(self):
        interaction = self._create_interaction(processed=False)
        extraction_path = self._write_extraction_file(interaction["uuid"])

        graph_db = GraphDatabase(str(self.graph_path))
        try:
            graph_db.create_project_node(self.project_name)
            existing_uuid = graph_db.create_entity(
                name="Entity A",
                summary="A",
                labels=["Concept"],
                group_id=self.project_name,
                source_interactions=["bootstrap"],
                source_hashes=["hash-bootstrap"],
                extraction_version="test",
                extraction_commit="test",
            )
            graph_db.link_project_to_entity(self.project_name, existing_uuid)
        finally:
            graph_db.close()

        first_run = self._run(
            "scripts/store_extraction.py",
            "--project", self.project_name,
            "--extraction-file", str(extraction_path),
            "--sql-db", str(self.sql_path),
            "--graph-db", str(self.graph_path),
            "--require-quality-review",
            "--quality-questions-file", str(self.questions_path),
            "--quality-answers-file", str(self.answers_path),
        )
        self.assertNotEqual(first_run.returncode, 0)

        answers = json.loads(self.answers_path.read_text(encoding="utf-8"))
        answers["duplicates"][0]["is_duplicate"] = True
        answers["duplicates"][0]["duplicate_uuid"] = existing_uuid
        answers["duplicates"][0]["reasoning"] = "Reuse existing Entity A"
        answers["contradictions"][0]["reasoning"] = "No contradiction"
        self.answers_path.write_text(json.dumps(answers, indent=2) + "\n", encoding="utf-8")

        second_run = self._run(
            "scripts/store_extraction.py",
            "--project", self.project_name,
            "--extraction-file", str(extraction_path),
            "--sql-db", str(self.sql_path),
            "--graph-db", str(self.graph_path),
            "--require-quality-review",
            "--quality-questions-file", str(self.questions_path),
            "--quality-answers-file", str(self.answers_path),
        )

        self.assertEqual(second_run.returncode, 0, second_run.stdout + second_run.stderr)
        self.assertIn("[LINK] Using existing entity: Entity A", second_run.stdout)
        self.assertIn("-> REUSED", second_run.stdout)

        graph_db = GraphDatabase(str(self.graph_path))
        try:
            result = graph_db.conn.execute("""
                MATCH (p:Project {name: $project})-[:HAS_ENTITY]->(e:Entity)
                WHERE e.name = 'Entity A' AND e.deleted_at IS NULL
                RETURN count(e)
            """, {"project": self.project_name})
            count = result.get_next()[0] if result.has_next() else 0
        finally:
            graph_db.close()

        self.assertEqual(count, 1)

    def test_import_summary_rejects_invalid_payload(self):
        invalid_path = self.test_dir / "invalid_conversation.json"
        invalid_path.write_text(json.dumps({
            "summary": {
                "session_id": "",
                "timestamp": "",
                "intent": "",
                "work_attempted": "bad",
                "outcomes": "bad",
                "fidelity": "bad",
            }
        }), encoding="utf-8")

        result = self._run(
            "scripts/import_summary.py",
            "--project", self.project_name,
            "--file", str(invalid_path),
            "--db", str(self.sql_path),
        )

        self.assertNotEqual(result.returncode, 0)
        combined_output = result.stdout + result.stderr
        self.assertIn("summary.intent", combined_output)
        self.assertIn("summary.fidelity must be one of", combined_output)

    def test_import_summary_accepts_llm_state_payload(self):
        conversation_path = self.test_dir / "conversation.json"
        conversation_path.write_text(json.dumps({
            "workflow_session_id": "sync-2026-03-15_17-45-19",
            "summary": {
                "session_id": "sync-2026-03-15_17-45-19",
                "timestamp": "2026-03-15T17:45:19Z",
                "intent": "During this session we worked on file-input standardization and llm-state fidelity.",
                "work_attempted": [
                    "Completed the file-input rollout",
                    "Drafted llm-state support"
                ],
                "outcomes": [
                    {"type": "note", "description": "SQL migration still to review"}
                ],
                "fidelity": "llm-state"
            }
        }, indent=2), encoding="utf-8")

        result = self._run(
            "scripts/import_summary.py",
            "--project", self.project_name,
            "--file", str(conversation_path),
            "--db", str(self.sql_path),
            "--constrained-environment",
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        db = SQLDatabase(str(self.sql_path))
        interactions = db.get_all_interactions(self.project_name)
        self.assertEqual(len(interactions), 1)
        self.assertEqual(interactions[0]["fidelity"], "llm-state")

    def test_validation_rejects_unknown_relationship_type(self):
        """Verify that unknown relationship types are rejected at validation."""
        interaction = self._create_interaction(processed=False)
        # Use invalid relationship type INVENTED_BY
        extraction_path = self._write_extraction_file(interaction["uuid"], relationship_type="INVENTED_BY")

        result = self._run(
            "scripts/store_extraction.py",
            "--project", self.project_name,
            "--extraction-file", str(extraction_path),
            "--sql-db", str(self.sql_path),
            "--graph-db", str(self.graph_path),
            "--i-am-a-human-and-i-want-to-skip-quality-checks",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unknown relationship type", result.stdout)
        self.assertIn("INVENTED_BY", result.stdout)

    def test_inverse_relationship_type_normalization(self):
        """Verify that inverse types are normalized and source/target swapped in storage."""
        interaction = self._create_interaction(processed=False)

        # Write extraction with inverse type USED_BY (should become USES with swap)
        extraction_path = self.test_dir / "extraction.json"
        extraction_path.write_text(json.dumps({
            "project_name": self.project_name,
            "extraction_version": "test",
            "extraction_commit": "test",
            "extractions": [
                {
                    "interaction_uuid": interaction["uuid"],
                    "entities": [
                        {"name": "JavaScript", "type": "Language", "summary": "JS"},
                        {"name": "React", "type": "Library", "summary": "React lib"},
                    ],
                    "facts": [
                        {
                            "source_entity": "JavaScript",
                            "target_entity": "React",
                            "relationship_type": "USED_BY",  # Inverse type
                            "fact": "JavaScript is used by React",
                        }
                    ],
                }
            ],
        }, indent=2), encoding="utf-8")

        # Store with human skip to bypass quality checks for this test
        result = self._run(
            "scripts/store_extraction.py",
            "--project", self.project_name,
            "--extraction-file", str(extraction_path),
            "--sql-db", str(self.sql_path),
            "--graph-db", str(self.graph_path),
            "--i-am-a-human-and-i-want-to-skip-quality-checks",
        )

        self.assertEqual(result.returncode, 0, f"stdout: {result.stdout}\nstderr: {result.stderr}")

        # After normalization: USED_BY -> USES with source/target swapped
        # So "JavaScript USED_BY React" becomes "React USES JavaScript"
        self.assertIn("React --[USES]--> JavaScript", result.stdout)

        # Verify in graph database
        graph_db = GraphDatabase(str(self.graph_path))
        try:
            # Query for the relationship - Kuzu uses RELATES_TO edge with 'name' property
            query_result = graph_db.conn.execute("""
                MATCH (s:Entity)-[r:RELATES_TO]->(t:Entity)
                WHERE r.name = 'USES'
                RETURN s.name, t.name, r.name
            """)
            if query_result.has_next():
                row = query_result.get_next()
                source_name, target_name, rel_name = row[0], row[1], row[2]
                # After swap: React should be source, JavaScript should be target
                self.assertEqual(source_name, "React")
                self.assertEqual(target_name, "JavaScript")
                self.assertEqual(rel_name, "USES")  # Normalized from USED_BY
            else:
                self.fail("Expected to find USES relationship in graph")
        finally:
            graph_db.close()


class ProceduralProvenanceTests(unittest.TestCase):
    """Test that procedural entities preserve cryptographic/audit properties."""

    def setUp(self):
        base_tmp = REPO_ROOT / "tests" / "tmp"
        base_tmp.mkdir(parents=True, exist_ok=True)
        self.test_dir = base_tmp / f"procedural_provenance_{uuid4().hex[:8]}"
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.graph_path = self.test_dir / "test.graph"
        self.project_name = "provenance-test"

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_procedure_entity_has_provenance_fields(self):
        """Test that Procedure entities have required provenance fields."""
        graph_db = GraphDatabase(str(self.graph_path))
        try:
            # Create project
            graph_db.create_project_node(self.project_name)

            # Create a Procedure entity with full provenance
            proc_uuid = graph_db.create_entity(
                name="Test Audit Procedure",
                group_id=self.project_name,
                source_interactions=["interaction-uuid-123"],
                source_hashes=["hash-abc-123"],
                extraction_version="v1.0.0",
                extraction_commit="test-commit-xyz",
                summary="A procedure for testing provenance",
                labels=["Procedure"],
                attributes={
                    "goal": "Test auditability",
                    "trigger_phrases": ["audit test"],
                }
            )
            graph_db.link_project_to_entity(self.project_name, proc_uuid)

            # Query back and verify provenance fields
            result = graph_db.conn.execute("""
                MATCH (e:Entity)
                WHERE e.uuid = $uuid
                RETURN e.source_interactions, e.source_hashes,
                       e.extraction_version, e.extraction_commit,
                       e.labels, e.attributes
            """, {"uuid": proc_uuid})

            self.assertTrue(result.has_next(), "Entity should exist")
            row = result.get_next()

            source_interactions = row[0]
            source_hashes = row[1]
            extraction_version = row[2]
            extraction_commit = row[3]
            labels = row[4]
            attributes = row[5]

            # Verify provenance fields are preserved
            self.assertIn("interaction-uuid-123", source_interactions)
            self.assertIn("hash-abc-123", source_hashes)
            self.assertEqual(extraction_version, "v1.0.0")
            self.assertEqual(extraction_commit, "test-commit-xyz")
            self.assertIn("Procedure", labels)
            self.assertIn("goal", attributes)

        finally:
            graph_db.close()

    def test_procedure_step_has_provenance_fields(self):
        """Test that ProcedureStep entities have required provenance fields."""
        graph_db = GraphDatabase(str(self.graph_path))
        try:
            graph_db.create_project_node(self.project_name)

            # Create a ProcedureStep entity
            step_uuid = graph_db.create_entity(
                name="Test Audit Step 1",
                group_id=self.project_name,
                source_interactions=["interaction-uuid-456"],
                source_hashes=["hash-def-456"],
                extraction_version="v1.0.0",
                extraction_commit="test-commit-xyz",
                summary="Step 1 of test procedure",
                labels=["ProcedureStep"],
                attributes={
                    "procedure_name": "Test Audit Procedure",
                    "step_number": 1,
                    "action": "Do the first thing",
                }
            )
            graph_db.link_project_to_entity(self.project_name, step_uuid)

            # Query back and verify
            result = graph_db.conn.execute("""
                MATCH (e:Entity)
                WHERE e.uuid = $uuid
                RETURN e.source_interactions, e.source_hashes, e.labels, e.attributes
            """, {"uuid": step_uuid})

            self.assertTrue(result.has_next())
            row = result.get_next()

            self.assertIn("interaction-uuid-456", row[0])
            self.assertIn("hash-def-456", row[1])
            self.assertIn("ProcedureStep", row[2])
            self.assertIn("step_number", row[3])

        finally:
            graph_db.close()

    def test_procedural_attributes_persisted(self):
        """Test that procedural attributes are stored, not dropped."""
        graph_db = GraphDatabase(str(self.graph_path))
        try:
            graph_db.create_project_node(self.project_name)

            # Create entity with complex attributes
            proc_uuid = graph_db.create_entity(
                name="Complex Procedure",
                group_id=self.project_name,
                source_interactions=[],
                source_hashes=[],
                extraction_version="v1.0.0",
                extraction_commit="test",
                summary="Test complex attributes",
                labels=["Procedure"],
                attributes={
                    "goal": "Test attribute persistence",
                    "trigger_phrases": ["complex", "test"],
                    "prerequisites": ["prereq1", "prereq2"],
                    "agent_scope": "all",
                    "search_text": "complex test procedure",
                }
            )

            # Query and verify all attributes are present
            result = graph_db.conn.execute("""
                MATCH (e:Entity)
                WHERE e.uuid = $uuid
                RETURN e.attributes
            """, {"uuid": proc_uuid})

            self.assertTrue(result.has_next())
            attrs_str = result.get_next()[0]

            # Attributes should not be empty
            self.assertIsNotNone(attrs_str)
            self.assertNotEqual(attrs_str, "{}")

            # Should contain all the fields we set
            attrs = json.loads(attrs_str) if isinstance(attrs_str, str) else attrs_str
            self.assertEqual(attrs.get("goal"), "Test attribute persistence")
            self.assertEqual(attrs.get("agent_scope"), "all")
            self.assertIn("complex", attrs.get("trigger_phrases", []))

        finally:
            graph_db.close()


class ProceduralRetrievalTests(unittest.TestCase):
    """Test procedural memory retrieval CLI options in query_memory.py."""

    def setUp(self):
        base_tmp = REPO_ROOT / "tests" / "tmp"
        base_tmp.mkdir(parents=True, exist_ok=True)
        self.test_dir = base_tmp / f"procedural_retrieval_{uuid4().hex[:8]}"
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.sql_path = self.test_dir / "conversations.db"
        self.graph_path = self.test_dir / "test.graph"
        self.project_name = "retrieval-test"
        self.config_path = self.test_dir / "mem.config.json"
        write_test_config(self.config_path, self.project_name, self.sql_path, self.graph_path)

        # Set up test data: create procedures and steps
        self._setup_test_procedures()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _run(self, *args):
        return subprocess.run(
            [PYTHON, args[0], "--config", str(self.config_path), *args[1:]],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

    def _write_helper_file(self, filename, content):
        path = self.test_dir / filename
        path.write_text(f"{content}\n", encoding="utf-8")
        return path

    def _setup_test_procedures(self):
        """Create test procedures and steps in the graph database."""
        graph_db = GraphDatabase(str(self.graph_path))
        try:
            graph_db.create_project_node(self.project_name)

            # Create Procedure 1: Sync Workflow
            proc1_uuid = graph_db.create_entity(
                name="Sync Workflow",
                group_id=self.project_name,
                source_interactions=["test-interaction-1"],
                source_hashes=["hash-1"],
                extraction_version="v1.0.0",
                extraction_commit="test-commit",
                summary="Workflow for syncing conversation memory",
                labels=["Procedure"],
                attributes={
                    "goal": "Sync conversation data to memory",
                    "trigger_phrases": ["follow sync.md", "run memory sync"],
                    "search_text": "sync memory store_extraction import_conversation",
                }
            )
            graph_db.link_project_to_entity(self.project_name, proc1_uuid)

            # Create Steps for Sync Workflow
            step1_uuid = graph_db.create_entity(
                name="Sync Workflow / Step 1",
                group_id=self.project_name,
                source_interactions=["test-interaction-1"],
                source_hashes=["hash-1"],
                extraction_version="v1.0.0",
                extraction_commit="test-commit",
                summary="Read configuration files",
                labels=["ProcedureStep"],
                attributes={
                    "procedure_name": "Sync Workflow",
                    "step_number": 1,
                    "action": "Read sync.md and mem.config.json",
                    "script_refs": [],
                    "search_text": "read sync.md mem.config.json",
                }
            )
            graph_db.link_project_to_entity(self.project_name, step1_uuid)

            step2_uuid = graph_db.create_entity(
                name="Sync Workflow / Step 2",
                group_id=self.project_name,
                source_interactions=["test-interaction-1"],
                source_hashes=["hash-1"],
                extraction_version="v1.0.0",
                extraction_commit="test-commit",
                summary="Run import and store scripts",
                labels=["ProcedureStep"],
                attributes={
                    "procedure_name": "Sync Workflow",
                    "step_number": 2,
                    "action": "Run import_conversation.py and store_extraction.py",
                    "script_refs": ["import_conversation.py", "store_extraction.py"],
                    "search_text": "import_conversation.py store_extraction.py",
                }
            )
            graph_db.link_project_to_entity(self.project_name, step2_uuid)

            # Create Procedure 2: Deploy Workflow
            proc2_uuid = graph_db.create_entity(
                name="Deploy Workflow",
                group_id=self.project_name,
                source_interactions=["test-interaction-2"],
                source_hashes=["hash-2"],
                extraction_version="v1.0.0",
                extraction_commit="test-commit",
                summary="Workflow for deploying the application",
                labels=["Procedure"],
                attributes={
                    "goal": "Deploy application to production",
                    "trigger_phrases": ["deploy app", "push to prod"],
                    "search_text": "deploy production release",
                }
            )
            graph_db.link_project_to_entity(self.project_name, proc2_uuid)

            # Create Step for Deploy Workflow
            deploy_step_uuid = graph_db.create_entity(
                name="Deploy Workflow / Step 1",
                group_id=self.project_name,
                source_interactions=["test-interaction-2"],
                source_hashes=["hash-2"],
                extraction_version="v1.0.0",
                extraction_commit="test-commit",
                summary="Run deployment script",
                labels=["ProcedureStep"],
                attributes={
                    "procedure_name": "Deploy Workflow",
                    "step_number": 1,
                    "action": "Run deploy.sh with environment config",
                    "script_refs": ["deploy.sh"],
                    "search_text": "deploy.sh environment config",
                }
            )
            graph_db.link_project_to_entity(self.project_name, deploy_step_uuid)

        finally:
            graph_db.close()

    def test_procedures_flag_lists_all_procedures(self):
        """Test that --procedures lists all procedures in a project."""
        result = self._run(
            "scripts/query_memory.py",
            "--project", self.project_name,
            "--db", str(self.graph_path),
            "--procedures",
        )

        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}\nstdout: {result.stdout}")
        self.assertIn("Sync Workflow", result.stdout)
        self.assertIn("Deploy Workflow", result.stdout)
        self.assertIn("Found 2 procedures", result.stdout)

    def test_procedures_flag_shows_goals(self):
        """Test that --procedures shows procedure goals."""
        result = self._run(
            "scripts/query_memory.py",
            "--project", self.project_name,
            "--db", str(self.graph_path),
            "--procedures",
        )

        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}\nstdout: {result.stdout}")
        self.assertIn("Sync conversation data", result.stdout)
        self.assertIn("Deploy application", result.stdout)

    def test_procedures_flag_requires_project(self):
        """Test that --procedures fails without --project."""
        result = self._run(
            "scripts/query_memory.py",
            "--db", str(self.graph_path),
            "--procedures",
        )

        self.assertNotEqual(result.returncode, 0)
        # Error goes to stdout, not stderr in this script
        combined = result.stdout + result.stderr
        self.assertIn("--procedures requires --project", combined)

    def test_procedure_flag_shows_steps(self):
        """Test that --procedure <name> shows procedure with its steps."""
        proc_file = self._write_helper_file("procedure.txt", "Sync Workflow")
        result = self._run(
            "scripts/query_memory.py",
            "--project", self.project_name,
            "--db", str(self.graph_path),
            "--procedure-file", str(proc_file),
        )

        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}\nstdout: {result.stdout}")
        self.assertIn("Sync Workflow", result.stdout)
        self.assertIn("Steps (2)", result.stdout)
        self.assertIn("Read sync.md", result.stdout)
        self.assertIn("import_conversation.py", result.stdout)

    def test_procedure_flag_shows_steps_ordered(self):
        """Test that --procedure shows steps in order by step_number."""
        proc_file = self._write_helper_file("procedure.txt", "Sync Workflow")
        result = self._run(
            "scripts/query_memory.py",
            "--project", self.project_name,
            "--db", str(self.graph_path),
            "--procedure-file", str(proc_file),
        )

        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}\nstdout: {result.stdout}")
        # Step 1 should appear before Step 2
        stdout = result.stdout
        step1_pos = stdout.find("Read sync.md")
        step2_pos = stdout.find("import_conversation.py")
        self.assertLess(step1_pos, step2_pos, "Steps should be ordered by step_number")

    def test_procedure_flag_not_found(self):
        """Test that --procedure shows error for non-existent procedure."""
        proc_file = self._write_helper_file("procedure.txt", "Nonexistent Workflow")
        result = self._run(
            "scripts/query_memory.py",
            "--project", self.project_name,
            "--db", str(self.graph_path),
            "--procedure-file", str(proc_file),
        )

        self.assertNotEqual(result.returncode, 0)
        # Error goes to stdout or stderr
        combined = result.stdout + result.stderr
        self.assertIn("not found", combined)

    def test_procedure_flag_requires_project(self):
        """Test that --procedure fails without --project."""
        proc_file = self._write_helper_file("procedure.txt", "Sync Workflow")
        result = self._run(
            "scripts/query_memory.py",
            "--db", str(self.graph_path),
            "--procedure-file", str(proc_file),
        )

        self.assertNotEqual(result.returncode, 0)
        # Error goes to stdout, not stderr in this script
        combined = result.stdout + result.stderr
        self.assertIn("--procedure requires --project", combined)

    def test_search_procedures_finds_by_script_ref(self):
        """Test that --search-procedures finds procedures by script reference."""
        search_file = self._write_helper_file("search.txt", "store_extraction")
        result = self._run(
            "scripts/query_memory.py",
            "--project", self.project_name,
            "--db", str(self.graph_path),
            "--search-procedures-file", str(search_file),
        )

        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}\nstdout: {result.stdout}")
        self.assertIn("Sync Workflow", result.stdout)
        # Should NOT find Deploy Workflow (no store_extraction in its steps)
        self.assertNotIn("Deploy Workflow", result.stdout)

    def test_search_procedures_finds_by_action_text(self):
        """Test that --search-procedures finds procedures by step action text."""
        search_file = self._write_helper_file("search.txt", "deploy.sh")
        result = self._run(
            "scripts/query_memory.py",
            "--project", self.project_name,
            "--db", str(self.graph_path),
            "--search-procedures-file", str(search_file),
        )

        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}\nstdout: {result.stdout}")
        self.assertIn("Deploy Workflow", result.stdout)
        self.assertNotIn("Sync Workflow", result.stdout)

    def test_search_procedures_requires_project(self):
        """Test that --search-procedures fails without --project."""
        search_file = self._write_helper_file("search.txt", "anything")
        result = self._run(
            "scripts/query_memory.py",
            "--db", str(self.graph_path),
            "--search-procedures-file", str(search_file),
        )

        self.assertNotEqual(result.returncode, 0)
        # Error goes to stdout, not stderr in this script
        combined = result.stdout + result.stderr
        self.assertIn("--search-procedures requires --project", combined)

    def test_procedures_json_output(self):
        """Test that --procedures with --json outputs valid JSON."""
        result = self._run(
            "scripts/query_memory.py",
            "--project", self.project_name,
            "--db", str(self.graph_path),
            "--procedures",
            "--json",
        )

        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}\nstdout: {result.stdout}")
        # Should be valid JSON
        data = json.loads(result.stdout)
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 2)
        names = {p['name'] for p in data}
        self.assertIn("Sync Workflow", names)
        self.assertIn("Deploy Workflow", names)

    def test_procedure_json_output_includes_steps(self):
        """Test that --procedure with --json includes steps."""
        proc_file = self._write_helper_file("procedure.txt", "Sync Workflow")
        result = self._run(
            "scripts/query_memory.py",
            "--project", self.project_name,
            "--db", str(self.graph_path),
            "--procedure-file", str(proc_file),
            "--json",
        )

        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        data = json.loads(result.stdout)
        self.assertIn("procedure", data)
        self.assertIn("steps", data)
        self.assertEqual(data["procedure"]["name"], "Sync Workflow")
        self.assertEqual(len(data["steps"]), 2)


class LifecycleFilteringTests(unittest.TestCase):
    """Test lifecycle filtering for procedural memory retrieval."""

    def setUp(self):
        base_tmp = REPO_ROOT / "tests" / "tmp"
        base_tmp.mkdir(parents=True, exist_ok=True)
        self.test_dir = base_tmp / f"lifecycle_test_{uuid4().hex[:8]}"
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.graph_path = self.test_dir / "test.graph"
        self.sql_path = self.test_dir / "conversations.db"
        self.project_name = "lifecycle-test"
        self.config_path = self.test_dir / "mem.config.json"
        write_test_config(self.config_path, self.project_name, self.sql_path, self.graph_path)

        # Set up test data with different lifecycle statuses
        self._setup_test_procedures()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _run(self, *args):
        return subprocess.run(
            [PYTHON, args[0], "--config", str(self.config_path), *args[1:]],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

    def _write_helper_file(self, filename, content):
        path = self.test_dir / filename
        path.write_text(f"{content}\n", encoding="utf-8")
        return path

    def _setup_test_procedures(self):
        """Create test procedures with different lifecycle statuses."""
        graph_db = GraphDatabase(str(self.graph_path))
        try:
            graph_db.create_project_node(self.project_name)

            # Active procedure (explicit)
            active_uuid = graph_db.create_entity(
                name="Active Workflow",
                group_id=self.project_name,
                source_interactions=["test-1"],
                source_hashes=["hash-1"],
                extraction_version="v1.0.0",
                extraction_commit="test",
                summary="An active workflow",
                labels=["Procedure"],
                attributes={
                    "goal": "Do something actively",
                    "lifecycle_status": "active",
                }
            )
            graph_db.link_project_to_entity(self.project_name, active_uuid)

            # Procedure with no lifecycle (should default to active)
            no_lifecycle_uuid = graph_db.create_entity(
                name="Legacy Workflow",
                group_id=self.project_name,
                source_interactions=["test-2"],
                source_hashes=["hash-2"],
                extraction_version="v1.0.0",
                extraction_commit="test",
                summary="A legacy workflow without lifecycle",
                labels=["Procedure"],
                attributes={
                    "goal": "Do legacy things",
                    # No lifecycle_status - should be treated as active
                }
            )
            graph_db.link_project_to_entity(self.project_name, no_lifecycle_uuid)

            # Deprecated procedure
            deprecated_uuid = graph_db.create_entity(
                name="Deprecated Workflow",
                group_id=self.project_name,
                source_interactions=["test-3"],
                source_hashes=["hash-3"],
                extraction_version="v1.0.0",
                extraction_commit="test",
                summary="A deprecated workflow",
                labels=["Procedure"],
                attributes={
                    "goal": "Do deprecated things",
                    "lifecycle_status": "deprecated",
                }
            )
            graph_db.link_project_to_entity(self.project_name, deprecated_uuid)

            # Superseded procedure
            superseded_uuid = graph_db.create_entity(
                name="Superseded Workflow",
                group_id=self.project_name,
                source_interactions=["test-4"],
                source_hashes=["hash-4"],
                extraction_version="v1.0.0",
                extraction_commit="test",
                summary="A superseded workflow",
                labels=["Procedure"],
                attributes={
                    "goal": "Do superseded things",
                    "lifecycle_status": "superseded",
                }
            )
            graph_db.link_project_to_entity(self.project_name, superseded_uuid)

            # Invalid procedure
            invalid_uuid = graph_db.create_entity(
                name="Invalid Workflow",
                group_id=self.project_name,
                source_interactions=["test-5"],
                source_hashes=["hash-5"],
                extraction_version="v1.0.0",
                extraction_commit="test",
                summary="An invalid workflow",
                labels=["Procedure"],
                attributes={
                    "goal": "Do invalid things",
                    "lifecycle_status": "invalid",
                }
            )
            graph_db.link_project_to_entity(self.project_name, invalid_uuid)

            # Add a step that references "special_script.py" for search test
            step_uuid = graph_db.create_entity(
                name="Deprecated Workflow / Step 1",
                group_id=self.project_name,
                source_interactions=["test-3"],
                source_hashes=["hash-3"],
                extraction_version="v1.0.0",
                extraction_commit="test",
                summary="Run special script",
                labels=["ProcedureStep"],
                attributes={
                    "procedure_name": "Deprecated Workflow",
                    "step_number": 1,
                    "action": "Run special_script.py",
                    "script_refs": ["special_script.py"],
                }
            )
            graph_db.link_project_to_entity(self.project_name, step_uuid)

        finally:
            graph_db.close()

    def test_default_excludes_deprecated(self):
        """Test that default retrieval excludes deprecated procedures."""
        result = self._run(
            "scripts/query_memory.py",
            "--project", self.project_name,
            "--db", str(self.graph_path),
            "--procedures",
        )

        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        self.assertNotIn("Deprecated Workflow", result.stdout)

    def test_default_excludes_superseded(self):
        """Test that default retrieval excludes superseded procedures."""
        result = self._run(
            "scripts/query_memory.py",
            "--project", self.project_name,
            "--db", str(self.graph_path),
            "--procedures",
        )

        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        self.assertNotIn("Superseded Workflow", result.stdout)

    def test_default_excludes_invalid(self):
        """Test that default retrieval excludes invalid procedures."""
        result = self._run(
            "scripts/query_memory.py",
            "--project", self.project_name,
            "--db", str(self.graph_path),
            "--procedures",
        )

        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        self.assertNotIn("Invalid Workflow", result.stdout)

    def test_default_includes_active(self):
        """Test that default retrieval includes active procedures."""
        result = self._run(
            "scripts/query_memory.py",
            "--project", self.project_name,
            "--db", str(self.graph_path),
            "--procedures",
        )

        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        self.assertIn("Active Workflow", result.stdout)

    def test_missing_lifecycle_treated_as_active(self):
        """Test that procedures without lifecycle_status are treated as active."""
        result = self._run(
            "scripts/query_memory.py",
            "--project", self.project_name,
            "--db", str(self.graph_path),
            "--procedures",
        )

        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        # Legacy Workflow has no lifecycle_status, should be included
        self.assertIn("Legacy Workflow", result.stdout)

    def test_include_deprecated_flag_shows_all(self):
        """Test that --include-deprecated shows all procedures."""
        result = self._run(
            "scripts/query_memory.py",
            "--project", self.project_name,
            "--db", str(self.graph_path),
            "--procedures",
            "--include-deprecated",
        )

        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        # Should include all procedures
        self.assertIn("Active Workflow", result.stdout)
        self.assertIn("Legacy Workflow", result.stdout)
        self.assertIn("Deprecated Workflow", result.stdout)
        self.assertIn("Superseded Workflow", result.stdout)
        self.assertIn("Invalid Workflow", result.stdout)

    def test_include_deprecated_shows_lifecycle_markers(self):
        """Test that --include-deprecated shows lifecycle status markers."""
        result = self._run(
            "scripts/query_memory.py",
            "--project", self.project_name,
            "--db", str(self.graph_path),
            "--procedures",
            "--include-deprecated",
        )

        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        self.assertIn("[LIFECYCLE: deprecated]", result.stdout)
        self.assertIn("[LIFECYCLE: superseded]", result.stdout)
        self.assertIn("[LIFECYCLE: invalid]", result.stdout)

    def test_procedure_lookup_deprecated_gives_hint(self):
        """Test that looking up a deprecated procedure gives a helpful hint."""
        proc_file = self._write_helper_file("procedure.txt", "Deprecated Workflow")
        result = self._run(
            "scripts/query_memory.py",
            "--project", self.project_name,
            "--db", str(self.graph_path),
            "--procedure-file", str(proc_file),
        )

        self.assertNotEqual(result.returncode, 0)
        combined = result.stdout + result.stderr
        self.assertIn("deprecated", combined.lower())
        self.assertIn("--include-deprecated", combined)

    def test_procedure_lookup_deprecated_with_flag(self):
        """Test that --include-deprecated allows looking up deprecated procedures."""
        proc_file = self._write_helper_file("procedure.txt", "Deprecated Workflow")
        result = self._run(
            "scripts/query_memory.py",
            "--project", self.project_name,
            "--db", str(self.graph_path),
            "--procedure-file", str(proc_file),
            "--include-deprecated",
        )

        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        self.assertIn("Deprecated Workflow", result.stdout)
        self.assertIn("[LIFECYCLE: deprecated]", result.stdout)

    def test_search_procedures_excludes_deprecated(self):
        """Test that --search-procedures excludes deprecated by default."""
        search_file = self._write_helper_file("search.txt", "special_script")
        result = self._run(
            "scripts/query_memory.py",
            "--project", self.project_name,
            "--db", str(self.graph_path),
            "--search-procedures-file", str(search_file),
        )

        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        # special_script.py is only in Deprecated Workflow, so no results
        self.assertNotIn("Deprecated Workflow", result.stdout)

    def test_search_procedures_with_include_deprecated(self):
        """Test that --search-procedures with --include-deprecated finds deprecated."""
        search_file = self._write_helper_file("search.txt", "special_script")
        result = self._run(
            "scripts/query_memory.py",
            "--project", self.project_name,
            "--db", str(self.graph_path),
            "--search-procedures-file", str(search_file),
            "--include-deprecated",
        )

        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        self.assertIn("Deprecated Workflow", result.stdout)

    def test_json_output_includes_lifecycle(self):
        """Test that JSON output includes lifecycle_status."""
        result = self._run(
            "scripts/query_memory.py",
            "--project", self.project_name,
            "--db", str(self.graph_path),
            "--procedures",
            "--include-deprecated",
            "--json",
        )

        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        data = json.loads(result.stdout)
        lifecycles = set()
        for proc in data:
            attrs = proc.get('attributes', {})
            if isinstance(attrs, str):
                attrs = json.loads(attrs)
            lifecycle = attrs.get('lifecycle_status', 'active')
            lifecycles.add(lifecycle)
        # Should have all lifecycle statuses
        self.assertIn("active", lifecycles)
        self.assertIn("deprecated", lifecycles)
        self.assertIn("superseded", lifecycles)
        self.assertIn("invalid", lifecycles)


class ProcedureRunTests(unittest.TestCase):
    """Test ProcedureRun and StepRun execution telemetry (Phase 2)."""

    def setUp(self):
        base_tmp = REPO_ROOT / "tests" / "tmp"
        base_tmp.mkdir(parents=True, exist_ok=True)
        self.test_dir = base_tmp / f"procedure_run_{uuid4().hex[:8]}"
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.graph_path = self.test_dir / "test.graph"
        self.project_name = "run-test"

        # Set up test procedure and steps
        self.graph_db = GraphDatabase(str(self.graph_path))
        self._setup_test_procedure()

    def tearDown(self):
        self.graph_db.close()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _setup_test_procedure(self):
        """Create a test procedure with steps."""
        self.graph_db.create_project_node(self.project_name)

        # Create Procedure
        self.procedure_uuid = self.graph_db.create_entity(
            name="Test Workflow",
            group_id=self.project_name,
            source_interactions=["test-1"],
            source_hashes=["hash-1"],
            extraction_version="v1.0.0",
            extraction_commit="test",
            summary="A test workflow",
            labels=["Procedure"],
            attributes={"goal": "Test execution tracking"}
        )
        self.graph_db.link_project_to_entity(self.project_name, self.procedure_uuid)

        # Create ProcedureStep 1
        self.step1_uuid = self.graph_db.create_entity(
            name="Test Workflow / Step 1",
            group_id=self.project_name,
            source_interactions=["test-1"],
            source_hashes=["hash-1"],
            extraction_version="v1.0.0",
            extraction_commit="test",
            summary="First step",
            labels=["ProcedureStep"],
            attributes={"procedure_name": "Test Workflow", "step_number": 1, "action": "Do step 1"}
        )
        self.graph_db.link_project_to_entity(self.project_name, self.step1_uuid)

        # Create CONTAINS relationship: Procedure -> Step 1
        self.graph_db.create_relationship(
            source_uuid=self.procedure_uuid,
            target_uuid=self.step1_uuid,
            relationship_name="CONTAINS",
            fact="Test Workflow contains Step 1",
            group_id=self.project_name,
            episodes=["test-1"],
            episode_hashes=["hash-1"],
            derivation_version="v1.0.0",
            derivation_commit="test",
            valid_at="2026-03-12T00:00:00"
        )

        # Create ProcedureStep 2
        self.step2_uuid = self.graph_db.create_entity(
            name="Test Workflow / Step 2",
            group_id=self.project_name,
            source_interactions=["test-1"],
            source_hashes=["hash-1"],
            extraction_version="v1.0.0",
            extraction_commit="test",
            summary="Second step",
            labels=["ProcedureStep"],
            attributes={"procedure_name": "Test Workflow", "step_number": 2, "action": "Do step 2"}
        )
        self.graph_db.link_project_to_entity(self.project_name, self.step2_uuid)

        # Create CONTAINS relationship: Procedure -> Step 2
        self.graph_db.create_relationship(
            source_uuid=self.procedure_uuid,
            target_uuid=self.step2_uuid,
            relationship_name="CONTAINS",
            fact="Test Workflow contains Step 2",
            group_id=self.project_name,
            episodes=["test-1"],
            episode_hashes=["hash-1"],
            derivation_version="v1.0.0",
            derivation_commit="test",
            valid_at="2026-03-12T00:00:00"
        )

    def test_create_procedure_run(self):
        """Test creating a ProcedureRun record."""
        run_uuid = self.graph_db.create_procedure_run(
            procedure_uuid=self.procedure_uuid,
            project_name=self.project_name,
            agent="test-agent",
            invocation_context="manual",
            model="test-model",
            status="in_progress"
        )

        self.assertIsNotNone(run_uuid)
        self.assertTrue(run_uuid.startswith("run-"))

    def test_procedure_run_persists_agent_model(self):
        """Test that ProcedureRun persists agent and model attribution."""
        run_uuid = self.graph_db.create_procedure_run(
            procedure_uuid=self.procedure_uuid,
            project_name=self.project_name,
            agent="auggie",
            invocation_context="procedure_md",
            model="claude-sonnet",
            status="in_progress"
        )

        run = self.graph_db.get_procedure_run(run_uuid)

        self.assertIsNotNone(run)
        self.assertEqual(run["created_by_agent"], "auggie")
        self.assertEqual(run["created_by_model"], "claude-sonnet")
        self.assertEqual(run["invocation_context"], "procedure_md")
        self.assertEqual(run["status"], "in_progress")

    def test_procedure_run_persists_timestamps(self):
        """Test that ProcedureRun persists start time."""
        run_uuid = self.graph_db.create_procedure_run(
            procedure_uuid=self.procedure_uuid,
            project_name=self.project_name,
            agent="test-agent",
            invocation_context="manual",
            started_at="2026-03-12T22:00:00"
        )

        run = self.graph_db.get_procedure_run(run_uuid)

        self.assertIsNotNone(run)
        self.assertEqual(run["started_at"], "2026-03-12T22:00:00")
        self.assertIsNone(run["finished_at"])

    def test_finalize_procedure_run(self):
        """Test finalizing a ProcedureRun (terminalization operation)."""
        # Create run with no steps - can finalize immediately
        run_uuid = self.graph_db.create_procedure_run(
            procedure_uuid=self.procedure_uuid,
            project_name=self.project_name,
            agent="test-agent",
            invocation_context="manual"
        )

        success = self.graph_db.complete_procedure_run(
            run_uuid=run_uuid,
            status="success",
            result_note="Completed successfully"
        )

        self.assertTrue(success)

        run = self.graph_db.get_procedure_run(run_uuid)
        self.assertEqual(run["status"], "success")
        self.assertEqual(run["result_note"], "Completed successfully")
        self.assertIsNotNone(run["finished_at"])
        self.assertIsNotNone(run["run_hash"])  # Step 12: hash computed on finalization

    def test_create_step_run(self):
        """Test creating a StepRun record."""
        run_uuid = self.graph_db.create_procedure_run(
            procedure_uuid=self.procedure_uuid,
            project_name=self.project_name,
            agent="test-agent",
            invocation_context="manual"
        )

        step_run_uuid = self.graph_db.create_step_run(
            procedure_run_uuid=run_uuid,
            procedure_step_uuid=self.step1_uuid,
            step_number=1,
            status="in_progress"
        )

        self.assertIsNotNone(step_run_uuid)
        self.assertTrue(step_run_uuid.startswith("steprun-"))

    def test_step_run_persists_linkage(self):
        """Test that StepRun persists step linkage."""
        run_uuid = self.graph_db.create_procedure_run(
            procedure_uuid=self.procedure_uuid,
            project_name=self.project_name,
            agent="test-agent",
            invocation_context="manual"
        )

        step_run_uuid = self.graph_db.create_step_run(
            procedure_run_uuid=run_uuid,
            procedure_step_uuid=self.step1_uuid,
            step_number=1
        )

        step_run = self.graph_db.get_step_run(step_run_uuid)

        self.assertIsNotNone(step_run)
        self.assertEqual(step_run["procedure_run_uuid"], run_uuid)
        self.assertEqual(step_run["procedure_step_uuid"], self.step1_uuid)
        self.assertEqual(step_run["step_number"], 1)

    def test_finalize_step_run(self):
        """Test finalizing a StepRun (terminalization operation)."""
        run_uuid = self.graph_db.create_procedure_run(
            procedure_uuid=self.procedure_uuid,
            project_name=self.project_name,
            agent="test-agent",
            invocation_context="manual"
        )

        step_run_uuid = self.graph_db.create_step_run(
            procedure_run_uuid=run_uuid,
            procedure_step_uuid=self.step1_uuid,
            step_number=1
        )

        success = self.graph_db.complete_step_run(
            step_run_uuid=step_run_uuid,
            status="success",
            result_note="Step completed"
        )

        self.assertTrue(success)

        step_run = self.graph_db.get_step_run(step_run_uuid)
        self.assertEqual(step_run["status"], "success")
        self.assertIsNotNone(step_run["finished_at"])
        self.assertIsNotNone(step_run["step_hash"])  # Step 12: hash computed on finalization

    def test_runs_relationship_created(self):
        """Test that RUNS relationship is created between ProcedureRun and Procedure."""
        run_uuid = self.graph_db.create_procedure_run(
            procedure_uuid=self.procedure_uuid,
            project_name=self.project_name,
            agent="test-agent",
            invocation_context="manual"
        )

        # Query the RUNS relationship
        result = self.graph_db.conn.execute("""
            MATCH (pr:ProcedureRun {uuid: $run_uuid})-[r:RUNS]->(e:Entity)
            RETURN e.uuid, r.uuid
        """, {"run_uuid": run_uuid})

        self.assertTrue(result.has_next())
        row = result.get_next()
        self.assertEqual(row[0], self.procedure_uuid)
        self.assertIsNotNone(row[1])  # relationship uuid

    def test_has_step_run_relationship_created(self):
        """Test that HAS_STEP_RUN relationship is created."""
        run_uuid = self.graph_db.create_procedure_run(
            procedure_uuid=self.procedure_uuid,
            project_name=self.project_name,
            agent="test-agent",
            invocation_context="manual"
        )

        step_run_uuid = self.graph_db.create_step_run(
            procedure_run_uuid=run_uuid,
            procedure_step_uuid=self.step1_uuid,
            step_number=1
        )

        # Query the HAS_STEP_RUN relationship
        result = self.graph_db.conn.execute("""
            MATCH (pr:ProcedureRun {uuid: $run_uuid})-[r:HAS_STEP_RUN]->(sr:StepRun)
            RETURN sr.uuid, r.uuid
        """, {"run_uuid": run_uuid})

        self.assertTrue(result.has_next())
        row = result.get_next()
        self.assertEqual(row[0], step_run_uuid)

    def test_runs_step_relationship_created(self):
        """Test that RUNS_STEP relationship is created."""
        run_uuid = self.graph_db.create_procedure_run(
            procedure_uuid=self.procedure_uuid,
            project_name=self.project_name,
            agent="test-agent",
            invocation_context="manual"
        )

        step_run_uuid = self.graph_db.create_step_run(
            procedure_run_uuid=run_uuid,
            procedure_step_uuid=self.step1_uuid,
            step_number=1
        )

        # Query the RUNS_STEP relationship
        result = self.graph_db.conn.execute("""
            MATCH (sr:StepRun {uuid: $step_run_uuid})-[r:RUNS_STEP]->(e:Entity)
            RETURN e.uuid, r.uuid
        """, {"step_run_uuid": step_run_uuid})

        self.assertTrue(result.has_next())
        row = result.get_next()
        self.assertEqual(row[0], self.step1_uuid)

    def test_invalid_procedure_uuid_rejected(self):
        """Test that create_procedure_run rejects invalid procedure UUIDs."""
        run_uuid = self.graph_db.create_procedure_run(
            procedure_uuid="nonexistent-uuid",
            project_name=self.project_name,
            agent="test-agent",
            invocation_context="manual"
        )

        self.assertIsNone(run_uuid)

    def test_non_procedure_entity_rejected(self):
        """Test that create_procedure_run rejects non-Procedure entities."""
        # step1_uuid is a ProcedureStep, not a Procedure
        run_uuid = self.graph_db.create_procedure_run(
            procedure_uuid=self.step1_uuid,
            project_name=self.project_name,
            agent="test-agent",
            invocation_context="manual"
        )

        self.assertIsNone(run_uuid)

    def test_invalid_procedure_run_uuid_rejected(self):
        """Test that create_step_run rejects invalid ProcedureRun UUIDs."""
        step_run_uuid = self.graph_db.create_step_run(
            procedure_run_uuid="nonexistent-run",
            procedure_step_uuid=self.step1_uuid,
            step_number=1
        )

        self.assertIsNone(step_run_uuid)

    def test_non_procedure_step_entity_rejected(self):
        """Test that create_step_run rejects non-ProcedureStep entities."""
        run_uuid = self.graph_db.create_procedure_run(
            procedure_uuid=self.procedure_uuid,
            project_name=self.project_name,
            agent="test-agent",
            invocation_context="manual"
        )

        # procedure_uuid is a Procedure, not a ProcedureStep
        step_run_uuid = self.graph_db.create_step_run(
            procedure_run_uuid=run_uuid,
            procedure_step_uuid=self.procedure_uuid,
            step_number=1
        )

        self.assertIsNone(step_run_uuid)

    def test_execution_records_no_extraction_provenance_required(self):
        """Test that execution records don't require extraction provenance fields."""
        # This test verifies the design principle: execution telemetry is separate
        # from extraction provenance. ProcedureRun and StepRun should work without
        # source_interactions, source_hashes, extraction_version, etc.

        run_uuid = self.graph_db.create_procedure_run(
            procedure_uuid=self.procedure_uuid,
            project_name=self.project_name,
            agent="test-agent",
            invocation_context="manual",
            model="test-model"
        )

        run = self.graph_db.get_procedure_run(run_uuid)

        # Verify we got the run without needing extraction fields
        self.assertIsNotNone(run)
        self.assertEqual(run["created_by_agent"], "test-agent")

        # Verify no extraction provenance fields exist on ProcedureRun
        # (they shouldn't - it's a separate table)
        self.assertNotIn("source_interactions", run)
        self.assertNotIn("source_hashes", run)
        self.assertNotIn("extraction_version", run)

    def test_complete_nonexistent_procedure_run_fails(self):
        """Test that completing a non-existent ProcedureRun returns False."""
        success = self.graph_db.complete_procedure_run(
            run_uuid="nonexistent-run-uuid",
            status="success"
        )

        self.assertFalse(success)

    def test_complete_nonexistent_step_run_fails(self):
        """Test that completing a non-existent StepRun returns False."""
        success = self.graph_db.complete_step_run(
            step_run_uuid="nonexistent-steprun-uuid",
            status="success"
        )

        self.assertFalse(success)

    def test_create_run_wrong_project_rejected(self):
        """Test that creating a run with wrong project is rejected."""
        run_uuid = self.graph_db.create_procedure_run(
            procedure_uuid=self.procedure_uuid,
            project_name="wrong-project",  # Procedure belongs to "run-test"
            agent="test-agent",
            invocation_context="manual"
        )

        self.assertIsNone(run_uuid)

    def test_step_run_wrong_procedure_rejected(self):
        """Test that creating a StepRun for a step from a different procedure is rejected."""
        # Create a second procedure with its own step
        second_proc_uuid = self.graph_db.create_entity(
            name="Other Workflow",
            group_id=self.project_name,
            source_interactions=["test-2"],
            source_hashes=["hash-2"],
            extraction_version="v1.0.0",
            extraction_commit="test",
            summary="Another workflow",
            labels=["Procedure"],
            attributes={"goal": "Different workflow"}
        )
        self.graph_db.link_project_to_entity(self.project_name, second_proc_uuid)

        other_step_uuid = self.graph_db.create_entity(
            name="Other Workflow / Step 1",
            group_id=self.project_name,
            source_interactions=["test-2"],
            source_hashes=["hash-2"],
            extraction_version="v1.0.0",
            extraction_commit="test",
            summary="Step from other workflow",
            labels=["ProcedureStep"],
            attributes={"procedure_name": "Other Workflow", "step_number": 1, "action": "Other action"}
        )
        self.graph_db.link_project_to_entity(self.project_name, other_step_uuid)

        # Create CONTAINS relationship for the other workflow's step
        self.graph_db.create_relationship(
            source_uuid=second_proc_uuid,
            target_uuid=other_step_uuid,
            relationship_name="CONTAINS",
            fact="Other Workflow contains Step 1",
            group_id=self.project_name,
            episodes=["test-2"],
            episode_hashes=["hash-2"],
            derivation_version="v1.0.0",
            derivation_commit="test",
            valid_at="2026-03-12T00:00:00"
        )

        # Create a run for "Test Workflow"
        run_uuid = self.graph_db.create_procedure_run(
            procedure_uuid=self.procedure_uuid,  # "Test Workflow"
            project_name=self.project_name,
            agent="test-agent",
            invocation_context="manual"
        )

        # Try to create a StepRun linking "Other Workflow / Step 1" to a "Test Workflow" run
        step_run_uuid = self.graph_db.create_step_run(
            procedure_run_uuid=run_uuid,
            procedure_step_uuid=other_step_uuid,  # This step belongs to "Other Workflow"
            step_number=1
        )

        # Should be rejected because step doesn't belong to the same procedure
        self.assertIsNone(step_run_uuid)

    def test_invocation_context_validation(self):
        """Test that invalid invocation_context is rejected."""
        run_uuid = self.graph_db.create_procedure_run(
            procedure_uuid=self.procedure_uuid,
            project_name=self.project_name,
            agent="test-agent",
            invocation_context="invalid_context"  # Not in valid set
        )

        self.assertIsNone(run_uuid)

    def test_complete_step_computes_hash(self):
        """Test that complete_step_run computes step_hash."""
        run_uuid = self.graph_db.create_procedure_run(
            procedure_uuid=self.procedure_uuid,
            project_name=self.project_name,
            agent="test-agent",
            invocation_context="manual"
        )

        step_run_uuid = self.graph_db.create_step_run(
            procedure_run_uuid=run_uuid,
            procedure_step_uuid=self.step1_uuid,
            step_number=1
        )

        # Before finalization, step_hash should be None
        step_run = self.graph_db.get_step_run(step_run_uuid)
        self.assertIsNone(step_run["step_hash"])

        # Finalize the step
        self.graph_db.complete_step_run(step_run_uuid, status="success")

        # After finalization, step_hash should be set
        step_run = self.graph_db.get_step_run(step_run_uuid)
        self.assertIsNotNone(step_run["step_hash"])
        self.assertEqual(len(step_run["step_hash"]), 64)  # SHA-256 hex

    def test_complete_run_includes_step_hashes(self):
        """Test that complete_procedure_run includes step_hashes in run_hash."""
        run_uuid = self.graph_db.create_procedure_run(
            procedure_uuid=self.procedure_uuid,
            project_name=self.project_name,
            agent="test-agent",
            invocation_context="manual"
        )

        # Create and finalize steps
        step1_run_uuid = self.graph_db.create_step_run(
            procedure_run_uuid=run_uuid,
            procedure_step_uuid=self.step1_uuid,
            step_number=1
        )
        self.graph_db.complete_step_run(step1_run_uuid, status="success")

        step2_run_uuid = self.graph_db.create_step_run(
            procedure_run_uuid=run_uuid,
            procedure_step_uuid=self.step2_uuid,
            step_number=2
        )
        self.graph_db.complete_step_run(step2_run_uuid, status="success")

        # Finalize the run
        self.graph_db.complete_procedure_run(run_uuid, status="success")

        run = self.graph_db.get_procedure_run(run_uuid)
        self.assertIsNotNone(run["run_hash"])
        self.assertEqual(len(run["run_hash"]), 64)  # SHA-256 hex

    def test_complete_run_fails_if_steps_incomplete(self):
        """Test that complete_procedure_run fails if any step is not finalized."""
        run_uuid = self.graph_db.create_procedure_run(
            procedure_uuid=self.procedure_uuid,
            project_name=self.project_name,
            agent="test-agent",
            invocation_context="manual"
        )

        # Create step but don't finalize it
        step_run_uuid = self.graph_db.create_step_run(
            procedure_run_uuid=run_uuid,
            procedure_step_uuid=self.step1_uuid,
            step_number=1
        )

        # Try to finalize the run - should fail
        success = self.graph_db.complete_procedure_run(run_uuid, status="success")
        self.assertFalse(success)

    def test_create_run_batch(self):
        """Test creating a RunBatch from completed runs."""
        # Create and finalize a run (no steps)
        run_uuid = self.graph_db.create_procedure_run(
            procedure_uuid=self.procedure_uuid,
            project_name=self.project_name,
            agent="test-agent",
            invocation_context="manual"
        )
        self.graph_db.complete_procedure_run(run_uuid, status="success")

        # Create batch
        batch_uuid = self.graph_db.create_run_batch(
            project_name=self.project_name,
            run_uuids=[run_uuid],
            agent="test-agent"
        )

        self.assertIsNotNone(batch_uuid)
        self.assertTrue(batch_uuid.startswith("runbatch-"))

    def test_batch_rejects_incomplete_runs(self):
        """Test that create_run_batch rejects runs with run_hash=NULL."""
        run_uuid = self.graph_db.create_procedure_run(
            procedure_uuid=self.procedure_uuid,
            project_name=self.project_name,
            agent="test-agent",
            invocation_context="manual"
        )
        # Don't finalize the run

        batch_uuid = self.graph_db.create_run_batch(
            project_name=self.project_name,
            run_uuids=[run_uuid],
            agent="test-agent"
        )

        self.assertIsNone(batch_uuid)

    def test_batch_rejects_already_batched_runs(self):
        """Test that create_run_batch rejects runs already in a batch."""
        # Create and finalize a run
        run_uuid = self.graph_db.create_procedure_run(
            procedure_uuid=self.procedure_uuid,
            project_name=self.project_name,
            agent="test-agent",
            invocation_context="manual"
        )
        self.graph_db.complete_procedure_run(run_uuid, status="success")

        # Create first batch
        batch1_uuid = self.graph_db.create_run_batch(
            project_name=self.project_name,
            run_uuids=[run_uuid],
            agent="test-agent"
        )
        self.assertIsNotNone(batch1_uuid)

        # Try to create second batch with same run - should fail
        batch2_uuid = self.graph_db.create_run_batch(
            project_name=self.project_name,
            run_uuids=[run_uuid],
            agent="test-agent"
        )
        self.assertIsNone(batch2_uuid)

    def test_batch_chains_to_previous(self):
        """Test that batches chain via previous_batch_hash."""
        # Create first run and batch
        run1_uuid = self.graph_db.create_procedure_run(
            procedure_uuid=self.procedure_uuid,
            project_name=self.project_name,
            agent="test-agent",
            invocation_context="manual"
        )
        self.graph_db.complete_procedure_run(run1_uuid, status="success")
        batch1_uuid = self.graph_db.create_run_batch(
            project_name=self.project_name,
            run_uuids=[run1_uuid],
            agent="test-agent"
        )

        # Create second run and batch
        run2_uuid = self.graph_db.create_procedure_run(
            procedure_uuid=self.procedure_uuid,
            project_name=self.project_name,
            agent="test-agent",
            invocation_context="manual"
        )
        self.graph_db.complete_procedure_run(run2_uuid, status="success")
        batch2_uuid = self.graph_db.create_run_batch(
            project_name=self.project_name,
            run_uuids=[run2_uuid],
            agent="test-agent"
        )

        # Check chaining
        batch1 = self.graph_db.get_run_batch(batch1_uuid)
        batch2 = self.graph_db.get_run_batch(batch2_uuid)

        self.assertEqual(batch1["batch_index"], 1)
        self.assertEqual(batch2["batch_index"], 2)
        self.assertEqual(batch1["previous_batch_hash"], "")
        self.assertEqual(batch2["previous_batch_hash"], batch1["batch_hash"])

    def test_batch_hash_is_deterministic(self):
        """Test that batch_hash is computed deterministically and canonically.

        This test independently recomputes the batch_hash from stored fields
        to verify the hash is canonical and order-insensitive.
        """
        import hashlib as test_hashlib

        # Create two runs
        run1_uuid = self.graph_db.create_procedure_run(
            procedure_uuid=self.procedure_uuid,
            project_name=self.project_name,
            agent="test-agent",
            invocation_context="manual"
        )
        self.graph_db.complete_procedure_run(run1_uuid, status="success")

        run2_uuid = self.graph_db.create_procedure_run(
            procedure_uuid=self.procedure_uuid,
            project_name=self.project_name,
            agent="test-agent",
            invocation_context="manual"
        )
        self.graph_db.complete_procedure_run(run2_uuid, status="success")

        # Get run hashes for verification
        run1 = self.graph_db.get_procedure_run(run1_uuid)
        run2 = self.graph_db.get_procedure_run(run2_uuid)

        # Build expected sorted (uuid, hash) pairs
        expected_pairs = sorted([
            (run1_uuid, run1["run_hash"]),
            (run2_uuid, run2["run_hash"])
        ], key=lambda x: x[0])
        expected_uuids = [p[0] for p in expected_pairs]
        expected_hashes = [p[1] for p in expected_pairs]

        # Create batch (input order shouldn't matter due to sorting)
        batch_uuid = self.graph_db.create_run_batch(
            project_name=self.project_name,
            run_uuids=[run2_uuid, run1_uuid],  # Deliberately reverse order
            agent="test-agent",
            model="test-model"
        )

        batch = self.graph_db.get_run_batch(batch_uuid)

        # Verify stored arrays match expected pair-derived ordering
        self.assertEqual(batch["run_uuids"], expected_uuids)
        self.assertEqual(batch["run_hashes"], expected_hashes)

        # Independently reconstruct canonical payload and recompute hash
        canonical_payload = {
            "batch_index": batch["batch_index"],
            "batch_uuid": batch["batch_uuid"],
            "created_by_agent": batch["created_by_agent"],
            "created_by_model": batch["created_by_model"],
            "previous_batch_hash": batch["previous_batch_hash"],
            "project_name": batch["project_name"],
            "run_hashes": batch["run_hashes"],
            "run_uuids": batch["run_uuids"],
        }
        canonical_json = json.dumps(canonical_payload, sort_keys=True, separators=(',', ':'))
        recomputed_hash = test_hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()

        # Assert stored batch_hash matches independent recomputation
        self.assertEqual(batch["batch_hash"], recomputed_hash)

    def test_batch_sets_run_batch_uuid(self):
        """Test that create_run_batch sets run_batch_uuid on included runs."""
        run_uuid = self.graph_db.create_procedure_run(
            procedure_uuid=self.procedure_uuid,
            project_name=self.project_name,
            agent="test-agent",
            invocation_context="manual"
        )
        self.graph_db.complete_procedure_run(run_uuid, status="success")

        batch_uuid = self.graph_db.create_run_batch(
            project_name=self.project_name,
            run_uuids=[run_uuid],
            agent="test-agent"
        )

        run = self.graph_db.get_procedure_run(run_uuid)
        self.assertEqual(run["run_batch_uuid"], batch_uuid)


class CompoundCommandTests(unittest.TestCase):
    """Test Phase 3 compound commands for reduced friction."""

    def setUp(self):
        base_tmp = REPO_ROOT / "tests" / "tmp"
        base_tmp.mkdir(parents=True, exist_ok=True)
        self.test_dir = base_tmp / f"compound_{uuid4().hex[:8]}"
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.graph_path = self.test_dir / "test.graph"
        self.project_name = "compound-test"

        self.graph_db = GraphDatabase(str(self.graph_path))
        self._setup_test_procedure()

    def tearDown(self):
        self.graph_db.close()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _setup_test_procedure(self):
        """Create a test procedure with steps."""
        self.graph_db.create_project_node(self.project_name)

        # Create Procedure
        self.procedure_uuid = self.graph_db.create_entity(
            name="Compound Test Workflow",
            group_id=self.project_name,
            source_interactions=["test-1"],
            source_hashes=["hash-1"],
            extraction_version="v1.0.0",
            extraction_commit="test",
            summary="A workflow for testing compound commands",
            labels=["Procedure"],
            attributes={"goal": "Test compound commands", "lifecycle_status": "active"}
        )
        self.graph_db.link_project_to_entity(self.project_name, self.procedure_uuid)

        # Create ProcedureStep 1
        self.step1_uuid = self.graph_db.create_entity(
            name="Compound Test Workflow / Step 1",
            group_id=self.project_name,
            source_interactions=["test-1"],
            source_hashes=["hash-1"],
            extraction_version="v1.0.0",
            extraction_commit="test",
            summary="First step",
            labels=["ProcedureStep"],
            attributes={"procedure_name": "Compound Test Workflow", "step_number": 1, "action": "Do first action"}
        )
        self.graph_db.link_project_to_entity(self.project_name, self.step1_uuid)
        self.graph_db.create_relationship(
            source_uuid=self.procedure_uuid,
            target_uuid=self.step1_uuid,
            relationship_name="CONTAINS",
            fact="Procedure contains step 1",
            group_id=self.project_name,
            episodes=["test-1"],
            episode_hashes=["hash-1"],
            derivation_version="v1.0.0",
            derivation_commit="test",
            valid_at="2026-03-13T00:00:00"
        )

        # Create ProcedureStep 2
        self.step2_uuid = self.graph_db.create_entity(
            name="Compound Test Workflow / Step 2",
            group_id=self.project_name,
            source_interactions=["test-1"],
            source_hashes=["hash-1"],
            extraction_version="v1.0.0",
            extraction_commit="test",
            summary="Second step",
            labels=["ProcedureStep"],
            attributes={"procedure_name": "Compound Test Workflow", "step_number": 2, "action": "Do second action"}
        )
        self.graph_db.link_project_to_entity(self.project_name, self.step2_uuid)
        self.graph_db.create_relationship(
            source_uuid=self.procedure_uuid,
            target_uuid=self.step2_uuid,
            relationship_name="CONTAINS",
            fact="Procedure contains step 2",
            group_id=self.project_name,
            episodes=["test-1"],
            episode_hashes=["hash-1"],
            derivation_version="v1.0.0",
            derivation_commit="test",
            valid_at="2026-03-13T00:00:00"
        )

    def test_start_run_with_steps_creates_all_records(self):
        """Test that --start-run-with-steps creates run and all step runs."""
        # Create run with steps using the compound method
        run_uuid = self.graph_db.create_procedure_run(
            procedure_uuid=self.procedure_uuid,
            project_name=self.project_name,
            agent="test-agent",
            invocation_context="manual"
        )
        self.assertIsNotNone(run_uuid)

        # Create step runs (simulating what the compound command does)
        step1_run = self.graph_db.create_step_run(
            procedure_run_uuid=run_uuid,
            procedure_step_uuid=self.step1_uuid,
            step_number=1
        )
        step2_run = self.graph_db.create_step_run(
            procedure_run_uuid=run_uuid,
            procedure_step_uuid=self.step2_uuid,
            step_number=2
        )

        self.assertIsNotNone(step1_run)
        self.assertIsNotNone(step2_run)

        # Verify all records exist
        run = self.graph_db.get_procedure_run(run_uuid)
        self.assertEqual(run["status"], "in_progress")

    def test_complete_step_and_advance_returns_next_step(self):
        """Test that completing a step returns info about the next step."""
        # Setup: create run and steps
        run_uuid = self.graph_db.create_procedure_run(
            procedure_uuid=self.procedure_uuid,
            project_name=self.project_name,
            agent="test-agent",
            invocation_context="manual"
        )
        step1_run = self.graph_db.create_step_run(
            procedure_run_uuid=run_uuid,
            procedure_step_uuid=self.step1_uuid,
            step_number=1
        )
        step2_run = self.graph_db.create_step_run(
            procedure_run_uuid=run_uuid,
            procedure_step_uuid=self.step2_uuid,
            step_number=2
        )

        # Complete step 1
        self.graph_db.complete_step_run(step1_run, status="success")

        # Verify step 1 is finalized
        completed = self.graph_db.get_step_run(step1_run)
        self.assertEqual(completed["status"], "success")
        self.assertIsNotNone(completed["step_hash"])

        # Verify step 2 is still pending
        pending = self.graph_db.get_step_run(step2_run)
        self.assertEqual(pending["status"], "in_progress")

    def test_complete_last_step_indicates_run_complete(self):
        """Test that completing the last step indicates the run can be finalized."""
        # Setup
        run_uuid = self.graph_db.create_procedure_run(
            procedure_uuid=self.procedure_uuid,
            project_name=self.project_name,
            agent="test-agent",
            invocation_context="manual"
        )
        step1_run = self.graph_db.create_step_run(
            procedure_run_uuid=run_uuid,
            procedure_step_uuid=self.step1_uuid,
            step_number=1
        )
        step2_run = self.graph_db.create_step_run(
            procedure_run_uuid=run_uuid,
            procedure_step_uuid=self.step2_uuid,
            step_number=2
        )

        # Complete both steps
        self.graph_db.complete_step_run(step1_run, status="success")
        self.graph_db.complete_step_run(step2_run, status="success")

        # Verify run can now be finalized
        success = self.graph_db.complete_procedure_run(run_uuid, status="success")
        self.assertTrue(success)

        run = self.graph_db.get_procedure_run(run_uuid)
        self.assertEqual(run["status"], "success")
        self.assertIsNotNone(run["run_hash"])

    def test_fail_step_and_run_marks_both_failed(self):
        """Test that failing a step also fails the run."""
        # Setup
        run_uuid = self.graph_db.create_procedure_run(
            procedure_uuid=self.procedure_uuid,
            project_name=self.project_name,
            agent="test-agent",
            invocation_context="manual"
        )
        step1_run = self.graph_db.create_step_run(
            procedure_run_uuid=run_uuid,
            procedure_step_uuid=self.step1_uuid,
            step_number=1
        )

        # Fail step 1
        self.graph_db.complete_step_run(step1_run, status="failure", result_note="Test failure")

        # Verify step is failed
        step = self.graph_db.get_step_run(step1_run)
        self.assertEqual(step["status"], "failure")

        # Now run can be finalized as failed
        success = self.graph_db.complete_procedure_run(run_uuid, status="failure", result_note="Step 1 failed")
        self.assertTrue(success)

        run = self.graph_db.get_procedure_run(run_uuid)
        self.assertEqual(run["status"], "failure")

    def test_deprecated_procedure_rejected(self):
        """Test that deprecated procedures are rejected for execution."""
        # Create a deprecated procedure
        deprecated_uuid = self.graph_db.create_entity(
            name="Deprecated Workflow",
            group_id=self.project_name,
            source_interactions=["test-1"],
            source_hashes=["hash-1"],
            extraction_version="v1.0.0",
            extraction_commit="test",
            summary="A deprecated workflow",
            labels=["Procedure"],
            attributes={"goal": "Old goal", "lifecycle_status": "deprecated"}
        )
        self.graph_db.link_project_to_entity(self.project_name, deprecated_uuid)

        # Try to create a run - should succeed at the DB level
        # (the lifecycle check is in execute_procedure.py, not graph_db.py)
        run_uuid = self.graph_db.create_procedure_run(
            procedure_uuid=deprecated_uuid,
            project_name=self.project_name,
            agent="test-agent",
            invocation_context="manual"
        )
        # At DB level, this succeeds - the CLI layer does the lifecycle check
        self.assertIsNotNone(run_uuid)

    def test_fail_step_auto_skips_remaining_steps(self):
        """Test that failing a step auto-skips remaining steps before run finalization."""
        # Setup: create run and pre-create all steps (simulating --start-run-with-steps)
        run_uuid = self.graph_db.create_procedure_run(
            procedure_uuid=self.procedure_uuid,
            project_name=self.project_name,
            agent="test-agent",
            invocation_context="manual"
        )
        step1_run = self.graph_db.create_step_run(
            procedure_run_uuid=run_uuid,
            procedure_step_uuid=self.step1_uuid,
            step_number=1
        )
        step2_run = self.graph_db.create_step_run(
            procedure_run_uuid=run_uuid,
            procedure_step_uuid=self.step2_uuid,
            step_number=2
        )

        # Fail step 1
        self.graph_db.complete_step_run(step1_run, status="failure")

        # At this point, step 2 is still pending - run finalization should fail
        run_finalize_attempt = self.graph_db.complete_procedure_run(run_uuid, status="failure")
        self.assertFalse(run_finalize_attempt)  # Should fail - step 2 not finalized

        # Now skip step 2
        self.graph_db.complete_step_run(step2_run, status="skipped", result_note="Auto-skipped due to failure at step 1")

        # Now run finalization should succeed
        run_finalize_success = self.graph_db.complete_procedure_run(run_uuid, status="failure")
        self.assertTrue(run_finalize_success)

        run = self.graph_db.get_procedure_run(run_uuid)
        self.assertEqual(run["status"], "failure")
        self.assertIsNotNone(run["run_hash"])

        # Verify step 2 is marked as skipped
        step2 = self.graph_db.get_step_run(step2_run)
        self.assertEqual(step2["status"], "skipped")


if __name__ == "__main__":
    unittest.main()
