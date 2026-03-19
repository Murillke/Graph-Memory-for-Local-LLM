import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from tools.sql_db import SQLDatabase


class LLMStateFidelitySQLTests(unittest.TestCase):
    def test_store_interaction_accepts_llm_state_on_new_db(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "conversations.db"
            db = SQLDatabase(str(db_path))
            db.create_project("test-project", "Test project")

            uuid = db.store_interaction({
                "project_name": "test-project",
                "user_message": "During this session we worked on import validation.",
                "assistant_message": "Completed validation changes and left migration work open.",
                "fidelity": "llm-state",
            })

            stored = db.get_interaction_by_uuid(uuid)
            self.assertEqual(stored["fidelity"], "llm-state")

    def test_existing_db_is_migrated_to_allow_llm_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "legacy.db"
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE projects (
                    name TEXT PRIMARY KEY,
                    description TEXT,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uuid TEXT UNIQUE NOT NULL,
                    project_name TEXT NOT NULL,
                    user_message TEXT NOT NULL,
                    assistant_message TEXT NOT NULL,
                    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    content_hash TEXT NOT NULL,
                    previous_hash TEXT,
                    chain_index INTEGER NOT NULL,
                    processed BOOLEAN DEFAULT FALSE,
                    extracted_at DATETIME,
                    session_id TEXT,
                    interaction_number INTEGER,
                    response_time_ms INTEGER,
                    token_count INTEGER,
                    fidelity TEXT DEFAULT 'summary' CHECK(fidelity IN ('summary', 'paraphrased', 'reconstructed')),
                    source_note TEXT,
                    context_data TEXT,
                    confidential BOOLEAN DEFAULT FALSE,
                    deleted_at DATETIME DEFAULT NULL
                )
            """)
            cursor.execute(
                "INSERT INTO projects (name, description) VALUES (?, ?)",
                ("test-project", "Legacy project"),
            )
            cursor.execute("""
                INSERT INTO interactions (
                    uuid, project_name, user_message, assistant_message, timestamp,
                    content_hash, previous_hash, chain_index, processed, extracted_at,
                    session_id, interaction_number, response_time_ms, token_count,
                    fidelity, source_note, context_data, confidential, deleted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "uuid-legacy0001",
                "test-project",
                "Legacy user",
                "Legacy assistant",
                "2026-03-15T10:00:00",
                "legacy-hash",
                None,
                1,
                0,
                None,
                None,
                None,
                None,
                None,
                "summary",
                None,
                None,
                0,
                None,
            ))
            conn.commit()
            conn.close()

            db = SQLDatabase(str(db_path))
            uuid = db.store_interaction({
                "project_name": "test-project",
                "user_message": "Session state",
                "assistant_message": "Migration succeeded.",
                "fidelity": "llm-state",
            })

            stored = db.get_interaction_by_uuid(uuid)
            self.assertEqual(stored["fidelity"], "llm-state")

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT sql FROM sqlite_master
                WHERE type = 'table' AND name = 'interactions'
            """)
            interactions_sql = cursor.fetchone()[0]
            conn.close()

            self.assertIn("'llm-state'", interactions_sql)


class LLMStateFidelityTemplateTests(unittest.TestCase):
    def test_prepare_sync_files_advertises_llm_state(self):
        from scripts.prepare_sync_files import prepare_sync_files

        with tempfile.TemporaryDirectory() as tmpdir:
            result = prepare_sync_files("test-project", tmpdir)
            conversation = json.loads(Path(result["conversation_file"]).read_text(encoding="utf-8"))
            self.assertIn("llm-state", conversation["_help_fidelity_values"])


if __name__ == "__main__":
    unittest.main()
