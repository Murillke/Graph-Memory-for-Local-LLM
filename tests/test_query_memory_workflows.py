#!/usr/bin/env python3
"""Regression tests for query_memory workflow behaviors."""

import shutil
import subprocess
import sys
import unittest
import json
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.graph_db import GraphDatabase


REPO_ROOT = Path(__file__).parent.parent


class TestQueryMemoryWorkflows(unittest.TestCase):
    """Exercise documented search workflow combinations."""

    def setUp(self):
        base_tmp = REPO_ROOT / "tests" / "tmp"
        base_tmp.mkdir(parents=True, exist_ok=True)
        self.test_dir = base_tmp / f"query_workflows_{uuid4().hex[:8]}"
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.graph_path = self.test_dir / "test.graph"
        self.project_name = "query-workflow-test"

        self.graph_db = GraphDatabase(str(self.graph_path))
        self.graph_db.create_project_node(self.project_name)

        self.alpha_uuid = self.graph_db.create_entity(
            name="Alpha Entity",
            group_id=self.project_name,
            source_interactions=["test-1"],
            source_hashes=["hash-1"],
            extraction_version="v1.0.0",
            extraction_commit="test",
            summary="Primary workflow entity",
            labels=["Task"],
        )
        self.beta_uuid = self.graph_db.create_entity(
            name="Beta Entity",
            group_id=self.project_name,
            source_interactions=["test-2"],
            source_hashes=["hash-2"],
            extraction_version="v1.0.0",
            extraction_commit="test",
            summary="Secondary workflow entity",
            labels=["Bug"],
        )
        self.gamma_uuid = self.graph_db.create_entity(
            name="Gamma Entity",
            group_id=self.project_name,
            source_interactions=["test-3"],
            source_hashes=["hash-3"],
            extraction_version="v1.0.0",
            extraction_commit="test",
            summary="Incoming relationship source",
            labels=["Feature"],
        )

        for entity_uuid in (self.alpha_uuid, self.beta_uuid, self.gamma_uuid):
            self.graph_db.link_project_to_entity(self.project_name, entity_uuid)

        self.graph_db.create_relationship(
            source_uuid=self.alpha_uuid,
            target_uuid=self.beta_uuid,
            relationship_name="USES",
            fact="Alpha Entity uses Beta Entity",
            group_id=self.project_name,
            episodes=["test-2"],
            episode_hashes=["hash-2"],
            derivation_version="v1.0.0",
            derivation_commit="test",
            valid_at="2026-03-14T00:00:00",
        )
        self.graph_db.create_relationship(
            source_uuid=self.gamma_uuid,
            target_uuid=self.alpha_uuid,
            relationship_name="BLOCKS",
            fact="Gamma Entity blocks Alpha Entity",
            group_id=self.project_name,
            episodes=["test-3"],
            episode_hashes=["hash-3"],
            derivation_version="v1.0.0",
            derivation_commit="test",
            valid_at="2026-03-14T00:05:00",
        )

        self.entity_file = self.test_dir / "entity.txt"
        self.entity_file.write_text("Alpha Entity", encoding="utf-8")
        self.config_path = self.test_dir / "mem.config.json"
        self.config_path.write_text(json.dumps({
            "project_name": self.project_name,
            "python_path": sys.executable,
            "database": {
                "sql_path": "./memory/conversations.db",
                "graph_path": str(self.graph_path),
            },
            "paths": {
                "tmp_dir": "./tmp",
                "memory_dir": "./memory",
            },
        }), encoding="utf-8")
        self.graph_db.close()
        self.graph_db = None

    def tearDown(self):
        if self.graph_db is not None:
            self.graph_db.close()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def run_cli(self, *args):
        command = [
            sys.executable,
            str(REPO_ROOT / "scripts" / "query_memory.py"),
            "--db",
            str(self.graph_path),
            *args,
        ]
        return subprocess.run(
            command,
            cwd=self.test_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )

    def test_entity_direction_filter_is_applied(self):
        result = self.run_cli(
            "--project",
            self.project_name,
            "--entity-file",
            str(self.entity_file),
            "--direction",
            "incoming",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("[incoming] Gamma Entity blocks Alpha Entity", result.stdout)
        self.assertNotIn("[outgoing] Alpha Entity uses Beta Entity", result.stdout)

    def test_entity_relationship_type_filter_is_applied(self):
        result = self.run_cli(
            "--project",
            self.project_name,
            "--entity-file",
            str(self.entity_file),
            "--type",
            "USES",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("[outgoing] Alpha Entity uses Beta Entity", result.stdout)
        self.assertNotIn("[incoming] Gamma Entity blocks Alpha Entity", result.stdout)

    def test_type_only_search_returns_facts(self):
        result = self.run_cli(
            "--project",
            self.project_name,
            "--type",
            "USES",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("[SEARCH] Found 1 facts:", result.stdout)
        self.assertIn("Alpha Entity -[USES]-> Beta Entity", result.stdout)

    def test_entity_uuid_related_works_without_project_when_db_is_given(self):
        result = self.run_cli(
            "--entity-uuid",
            self.alpha_uuid,
            "--related",
            "--direction",
            "incoming",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("[SEARCH] Found 1 entities:", result.stdout)
        self.assertIn("Gamma Entity", result.stdout)


if __name__ == "__main__":
    unittest.main()
