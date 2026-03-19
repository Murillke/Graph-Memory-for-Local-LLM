"""
SQLite database operations for interaction storage with hash chain.
"""

import sqlite3
import hashlib
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path
import uuid as uuid_module


FIDELITY_VALUES = ("summary", "paraphrased", "reconstructed", "llm-state")

TASK_EVENT_PRIORITY = (
    ("created", lambda row: row.get("operation") == "add"),
    ("priority_changed", lambda row: row.get("operation") == "set_priority"),
    ("completed", lambda row: row.get("status_after") == "complete"),
    ("invalidated", lambda row: row.get("status_after") == "invalid"),
    ("started", lambda row: row.get("status_after") == "in_progress"),
    (
        "paused",
        lambda row: row.get("status_before") == "in_progress" and row.get("status_after") == "pending",
    ),
)

TASK_EVENT_DISPLAY_LABELS = {
    "created": "CREATED",
    "priority_changed": "PRIORITY CHANGED",
    "completed": "COMPLETED",
    "invalidated": "INVALIDATED",
    "started": "STARTED",
    "paused": "PAUSED",
}


def classify_task_operation(row: Dict[str, Any]) -> Optional[str]:
    """Classify a task operation row into a canonical event type."""
    for event_type, predicate in TASK_EVENT_PRIORITY:
        try:
            if predicate(row):
                return event_type
        except Exception:
            continue
    return None


def get_task_event_display_label(row: Dict[str, Any]) -> str:
    """Return a human-friendly label for a task operation row."""
    event_type = classify_task_operation(row)
    if event_type:
        return TASK_EVENT_DISPLAY_LABELS[event_type]
    operation = (row.get("operation") or "").strip()
    return operation.upper() if operation else "UNKNOWN"


def get_task_short_hash(task_uuid: Optional[str]) -> str:
    """Return the stable short hash used by the task CLI when available."""
    if not task_uuid:
        return ""
    unique_part = task_uuid[7:] if task_uuid.startswith("entity-") else task_uuid
    return unique_part[:7]


class SQLDatabase:
    """SQLite database for storing interactions with cryptographic hash chain."""

    def __init__(self, db_path: str = "./memory/conversations.db"):
        self.db_path = db_path
        self._ensure_db_exists()

    def _ensure_db_exists(self):
        """Create database and tables if they don't exist."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create projects table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                name TEXT PRIMARY KEY,
                description TEXT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create project_paths table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS project_paths (
                path TEXT PRIMARY KEY,
                project_name TEXT NOT NULL,
                machine_id TEXT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_name) REFERENCES projects(name)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_project_name
            ON project_paths(project_name)
        """)

        self._create_interactions_table(cursor)
        self._create_interaction_indexes(cursor)
        self._create_sync_job_tables(cursor)

        # Create task operation event table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_operations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_uuid TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL,
                project_name TEXT NOT NULL,
                operation TEXT NOT NULL,
                success INTEGER NOT NULL,
                task_uuid TEXT,
                task_name TEXT NOT NULL,
                status_before TEXT,
                status_after TEXT,
                priority_before TEXT,
                priority_after TEXT,
                workflow_session_id TEXT,
                source_interaction_uuid TEXT,
                source_interaction_hash TEXT,
                command_context TEXT,
                payload_json TEXT,
                event_hash TEXT,
                ots_proof TEXT,
                ots_merkle_root TEXT,
                ots_batch_index INTEGER
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_operations_project_time
            ON task_operations(project_name, created_at)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_operations_project_task_name
            ON task_operations(project_name, task_name)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_operations_project_task_uuid
            ON task_operations(project_name, task_uuid)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_operations_session
            ON task_operations(project_name, workflow_session_id)
        """)

        # Create triggers to prevent unauthorized modifications
        # These act like "stored procedures" to enforce write protection

        # Prevent UPDATE on hash chain fields (immutable after creation)
        self._create_interaction_triggers(cursor)

        # Prevent UPDATE on projects (immutable after creation)
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS prevent_project_update
            BEFORE UPDATE ON projects
            FOR EACH ROW
            WHEN OLD.name != NEW.name
            BEGIN
                SELECT RAISE(ABORT, 'Project name is immutable. Cannot rename projects.');
            END
        """)

        conn.commit()
        conn.close()

        # Run migrations
        self._run_migrations()

    def _fidelity_check_constraint(self) -> str:
        values = ", ".join(f"'{value}'" for value in FIDELITY_VALUES)
        return f"CHECK(fidelity IN ({values}))"

    def _create_interactions_table(self, cursor: sqlite3.Cursor) -> None:
        """Create the interactions table with the current fidelity constraint."""
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT UNIQUE NOT NULL,
                project_name TEXT NOT NULL,
                user_message TEXT NOT NULL,
                assistant_message TEXT NOT NULL,
                timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

                -- Hash chain
                content_hash TEXT NOT NULL,
                previous_hash TEXT,
                chain_index INTEGER NOT NULL,

                -- Timestamp proof (OpenTimestamps)
                file_hash TEXT,
                timestamp_proof TEXT,

                -- Processing status
                processed BOOLEAN DEFAULT FALSE,
                extracted_at DATETIME,

                -- Agent identity (who imported this interaction)
                imported_by_agent TEXT,
                imported_by_model TEXT,

                -- Optional metadata
                session_id TEXT,
                interaction_number INTEGER,
                response_time_ms INTEGER,
                token_count INTEGER,

                -- Data fidelity tracking
                fidelity TEXT DEFAULT 'summary' {self._fidelity_check_constraint()},
                source_note TEXT,
                context_data TEXT,

                -- Privacy/confidentiality flag
                confidential BOOLEAN DEFAULT FALSE,

                -- Soft delete
                deleted_at DATETIME DEFAULT NULL
            )
        """)

    def _create_interaction_indexes(self, cursor: sqlite3.Cursor) -> None:
        """Create indexes for interactions table."""
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_project ON interactions(project_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON interactions(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_processed ON interactions(processed)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_uuid ON interactions(uuid)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chain ON interactions(project_name, chain_index)")

    def _create_sync_job_tables(self, cursor: sqlite3.Cursor) -> None:
        """Create sync_jobs and sync_job_events tables for async MCP sync."""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sync_jobs (
                job_id TEXT PRIMARY KEY,
                project_name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                stage TEXT,
                progress REAL NOT NULL DEFAULT 0.0,
                submitted_by_agent TEXT,
                submitted_by_model TEXT,
                request_json TEXT NOT NULL,
                payload_hash TEXT,
                payload_hash_verified INTEGER NOT NULL DEFAULT 0,
                transport_type TEXT NOT NULL DEFAULT 'stdio',
                raw_request_purged_at TEXT,
                raw_conversation_purged_at TEXT,
                client_cert_fingerprint TEXT,
                client_cert_subject TEXT,
                client_cert_serial TEXT,
                client_cert_issuer TEXT,
                client_cert_not_before TEXT,
                client_cert_not_after TEXT,
                result_json TEXT,
                error_json TEXT,
                source_interaction_uuid TEXT,
                extraction_batch_uuid TEXT,
                quality_review_required INTEGER NOT NULL DEFAULT 1,
                constrained_environment INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                updated_at TEXT NOT NULL
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sync_jobs_project ON sync_jobs(project_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sync_jobs_status ON sync_jobs(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sync_jobs_created ON sync_jobs(created_at)")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sync_job_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                project_name TEXT NOT NULL,
                event_type TEXT NOT NULL,
                stage TEXT,
                message TEXT,
                payload_json TEXT,
                created_at TEXT NOT NULL
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sync_job_events_job ON sync_job_events(job_id)")

    def _create_interaction_triggers(self, cursor: sqlite3.Cursor) -> None:
        """Create write-protection triggers for interactions table."""
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS prevent_hash_chain_update
            BEFORE UPDATE ON interactions
            FOR EACH ROW
            WHEN OLD.content_hash != NEW.content_hash
                OR OLD.previous_hash != NEW.previous_hash
                OR OLD.chain_index != NEW.chain_index
            BEGIN
                SELECT RAISE(ABORT, 'Hash chain fields are immutable. Cannot update content_hash, previous_hash, or chain_index.');
            END
        """)

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS prevent_content_update
            BEFORE UPDATE ON interactions
            FOR EACH ROW
            WHEN OLD.timestamp != NEW.timestamp
                OR (
                    (OLD.user_message != NEW.user_message OR OLD.assistant_message != NEW.assistant_message)
                    AND NOT (
                        NEW.user_message = '__PURGED_NETWORK_MCP__'
                        AND NEW.assistant_message = '__PURGED_NETWORK_MCP__'
                    )
                )
            BEGIN
                SELECT RAISE(ABORT, 'Conversation content is immutable. Cannot update user_message, assistant_message, or timestamp.');
            END
        """)

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS prevent_hard_delete
            BEFORE DELETE ON interactions
            BEGIN
                SELECT RAISE(ABORT, 'Hard deletes not allowed. Use soft delete by setting deleted_at timestamp.');
            END
        """)

    def _drop_interaction_integrity_objects(self, cursor: sqlite3.Cursor) -> None:
        """Drop interactions indexes/triggers before a table replacement migration."""
        for trigger in (
            "prevent_hash_chain_update",
            "prevent_content_update",
            "prevent_hard_delete",
        ):
            cursor.execute(f"DROP TRIGGER IF EXISTS {trigger}")

        for index in (
            "idx_project",
            "idx_timestamp",
            "idx_processed",
            "idx_uuid",
            "idx_chain",
        ):
            cursor.execute(f"DROP INDEX IF EXISTS {index}")

    def _interactions_table_supports_fidelity(self, cursor: sqlite3.Cursor, fidelity_value: str) -> bool:
        """Return True when the interactions table CHECK constraint includes the value."""
        cursor.execute("""
            SELECT sql FROM sqlite_master
            WHERE type = 'table' AND name = 'interactions'
        """)
        row = cursor.fetchone()
        if not row or not row[0]:
            return False
        return f"'{fidelity_value}'" in row[0]

    def _migrate_interactions_table(self, cursor: sqlite3.Cursor) -> None:
        """Replace the interactions table so fidelity CHECK matches the current schema."""
        print("[MIGRATION] Updating interactions fidelity constraint to include llm-state...")
        self._drop_interaction_integrity_objects(cursor)
        cursor.execute("ALTER TABLE interactions RENAME TO interactions_legacy")
        self._create_interactions_table(cursor)
        cursor.execute("""
            INSERT INTO interactions (
                id, uuid, project_name, user_message, assistant_message, timestamp,
                content_hash, previous_hash, chain_index,
                file_hash, timestamp_proof,
                processed, extracted_at,
                imported_by_agent, imported_by_model,
                session_id, interaction_number, response_time_ms, token_count,
                fidelity, source_note, context_data,
                confidential, deleted_at
            )
            SELECT
                id, uuid, project_name, user_message, assistant_message, timestamp,
                content_hash, previous_hash, chain_index,
                file_hash, timestamp_proof,
                processed, extracted_at,
                imported_by_agent, imported_by_model,
                session_id, interaction_number, response_time_ms, token_count,
                fidelity, source_note, context_data,
                confidential, deleted_at
            FROM interactions_legacy
        """)
        cursor.execute("DROP TABLE interactions_legacy")
        self._create_interaction_indexes(cursor)
        self._create_interaction_triggers(cursor)
        print("[MIGRATION] ✅ interactions fidelity constraint updated")

    def _run_migrations(self):
        """Run database migrations to add new columns if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Check if file_hash column exists
        cursor.execute("PRAGMA table_info(interactions)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'file_hash' not in columns:
            print("[MIGRATION] Adding file_hash column to interactions table...")
            cursor.execute("ALTER TABLE interactions ADD COLUMN file_hash TEXT")
            conn.commit()
            print("[MIGRATION] ✅ file_hash column added")

        if 'timestamp_proof' not in columns:
            print("[MIGRATION] Adding timestamp_proof column to interactions table...")
            cursor.execute("ALTER TABLE interactions ADD COLUMN timestamp_proof TEXT")
            conn.commit()
            print("[MIGRATION] ✅ timestamp_proof column added")

        if 'imported_by_agent' not in columns:
            print("[MIGRATION] Adding imported_by_agent column to interactions table...")
            cursor.execute("ALTER TABLE interactions ADD COLUMN imported_by_agent TEXT")
            conn.commit()
            print("[MIGRATION] ✅ imported_by_agent column added")

        if 'imported_by_model' not in columns:
            print("[MIGRATION] Adding imported_by_model column to interactions table...")
            cursor.execute("ALTER TABLE interactions ADD COLUMN imported_by_model TEXT")
            conn.commit()
            print("[MIGRATION] ✅ imported_by_model column added")

        if not self._interactions_table_supports_fidelity(cursor, "llm-state"):
            self._migrate_interactions_table(cursor)
            conn.commit()

        # Ensure updated trigger definition that permits purge-marker redaction.
        cursor.execute("DROP TRIGGER IF EXISTS prevent_content_update")
        self._create_interaction_triggers(cursor)
        conn.commit()

        # sync_jobs migrations
        cursor.execute("PRAGMA table_info(sync_jobs)")
        sync_job_columns = [row[1] for row in cursor.fetchall()]

        sync_job_migrations = {
            "payload_hash": "ALTER TABLE sync_jobs ADD COLUMN payload_hash TEXT",
            "payload_hash_verified": "ALTER TABLE sync_jobs ADD COLUMN payload_hash_verified INTEGER NOT NULL DEFAULT 0",
            "transport_type": "ALTER TABLE sync_jobs ADD COLUMN transport_type TEXT NOT NULL DEFAULT 'stdio'",
            "raw_request_purged_at": "ALTER TABLE sync_jobs ADD COLUMN raw_request_purged_at TEXT",
            "raw_conversation_purged_at": "ALTER TABLE sync_jobs ADD COLUMN raw_conversation_purged_at TEXT",
            "client_cert_fingerprint": "ALTER TABLE sync_jobs ADD COLUMN client_cert_fingerprint TEXT",
            "client_cert_subject": "ALTER TABLE sync_jobs ADD COLUMN client_cert_subject TEXT",
            "client_cert_serial": "ALTER TABLE sync_jobs ADD COLUMN client_cert_serial TEXT",
            "client_cert_issuer": "ALTER TABLE sync_jobs ADD COLUMN client_cert_issuer TEXT",
            "client_cert_not_before": "ALTER TABLE sync_jobs ADD COLUMN client_cert_not_before TEXT",
            "client_cert_not_after": "ALTER TABLE sync_jobs ADD COLUMN client_cert_not_after TEXT",
        }

        for column_name, alter_sql in sync_job_migrations.items():
            if column_name not in sync_job_columns:
                print(f"[MIGRATION] Adding {column_name} column to sync_jobs table...")
                cursor.execute(alter_sql)
                conn.commit()
                print(f"[MIGRATION] ✅ {column_name} column added")

        conn.close()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _calculate_interaction_hash(self, interaction: Dict[str, Any]) -> str:
        """
        Calculate SHA-256 hash of interaction content.

        Includes agent identity fields (imported_by_agent, imported_by_model) in the hash.
        For legacy data where these fields are NULL, they contribute empty strings to
        maintain hash compatibility.
        """
        content = "|".join([
            str(interaction["uuid"]),
            str(interaction["project_name"]),
            str(interaction["user_message"]),
            str(interaction["assistant_message"]),
            str(interaction["timestamp"]),
            str(interaction["chain_index"]),
            str(interaction.get("previous_hash") or ""),
            # Agent identity fields (v2 - added for provenance tracking)
            str(interaction.get("imported_by_agent") or ""),
            str(interaction.get("imported_by_model") or "")
        ])
        return hashlib.sha256(content.encode()).hexdigest()

    def get_project_from_path(self, path: str) -> Optional[str]:
        """Look up which project a path belongs to."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT project_name FROM project_paths WHERE path = ?",
            (path,)
        )
        row = cursor.fetchone()
        conn.close()

        return row["project_name"] if row else None

    def get_project_by_path(self, path: str) -> Optional[Dict[str, Any]]:
        """Get project by path (returns full project dict)."""
        project_name = self.get_project_from_path(path)
        if project_name:
            return self.get_project_by_name(project_name)
        return None

    def get_project_by_name(self, project_name: str) -> Optional[Dict[str, Any]]:
        """Get project by name."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT name, description, created_at FROM projects WHERE name = ?",
            (project_name,)
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                "name": row[0],
                "description": row[1],
                "created_at": row[2]
            }
        return None

    def create_project(self, name: str, description: Optional[str] = None) -> bool:
        """Create a new project. Returns True if created, False if already exists."""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "INSERT INTO projects (name, description) VALUES (?, ?)",
                (name, description)
            )
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            conn.close()
            return False

    def associate_path_with_project(
        self,
        path: str,
        project_name: str,
        machine_id: Optional[str] = None
    ) -> bool:
        """Map a path to a project. Returns True if created, False if already exists."""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "INSERT INTO project_paths (path, project_name, machine_id) VALUES (?, ?, ?)",
                (path, project_name, machine_id)
            )
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            conn.close()
            return False

    def _get_last_interaction(self, project_name: str) -> Optional[Dict[str, Any]]:
        """Get the last interaction in the chain for a project."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM interactions
            WHERE project_name = ? AND deleted_at IS NULL
            ORDER BY chain_index DESC
            LIMIT 1
        """, (project_name,))

        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else None

    def store_interaction(self, interaction: Dict[str, Any]) -> str:
        """
        Store a conversation interaction with hash chain.

        Args:
            interaction: Dict with keys:
                - uuid (optional, will be generated)
                - project_name
                - user_message
                - assistant_message
                - timestamp (optional, will use current time)
                - session_id (optional)
                - interaction_number (optional)
                - response_time_ms (optional)
                - token_count (optional)
                - context_data (optional)
                - fidelity (optional, default 'summary'): 'summary', 'paraphrased', 'reconstructed', 'llm-state'
                - source_note (optional): Description of data source/quality
                - confidential (optional, default False): Mark as confidential to exclude from extraction
                - imported_by_agent (optional): Agent name that imported this (e.g., "codex", "auggie")
                - imported_by_model (optional): Model name (e.g., "o3", "claude-opus-4-20250514")

        Returns:
            UUID of stored interaction
        """
        import uuid as uuid_module

        # Generate UUID if not provided
        if "uuid" not in interaction:
            interaction["uuid"] = f"uuid-{uuid_module.uuid4().hex[:12]}"

        # Use current timestamp if not provided
        if "timestamp" not in interaction:
            interaction["timestamp"] = datetime.now().isoformat()

        # Get last interaction in chain
        last = self._get_last_interaction(interaction["project_name"])

        if last:
            interaction["chain_index"] = last["chain_index"] + 1
            interaction["previous_hash"] = last["content_hash"]
        else:
            interaction["chain_index"] = 1
            interaction["previous_hash"] = None

        # Calculate content hash (includes agent identity fields)
        interaction["content_hash"] = self._calculate_interaction_hash(interaction)

        # Store to database
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO interactions (
                uuid, project_name, user_message, assistant_message, timestamp,
                content_hash, previous_hash, chain_index,
                file_hash, timestamp_proof,
                imported_by_agent, imported_by_model,
                session_id, interaction_number, response_time_ms, token_count, context_data,
                fidelity, source_note, confidential
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            interaction["uuid"],
            interaction["project_name"],
            interaction["user_message"],
            interaction["assistant_message"],
            interaction["timestamp"],
            interaction["content_hash"],
            interaction["previous_hash"],
            interaction["chain_index"],
            interaction.get("file_hash"),
            interaction.get("timestamp_proof"),
            interaction.get("imported_by_agent"),
            interaction.get("imported_by_model"),
            interaction.get("session_id"),
            interaction.get("interaction_number"),
            interaction.get("response_time_ms"),
            interaction.get("token_count"),
            interaction.get("context_data"),
            interaction.get("fidelity", "summary"),
            interaction.get("source_note"),
            interaction.get("confidential", False)
        ))

        conn.commit()
        conn.close()

        return interaction["uuid"]

    def get_unprocessed_interactions(
        self,
        project_name: str,
        include_confidential: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get interactions that haven't been extracted yet.

        CRITICAL: Returns interactions in chronological order (by chain_index)
        to prevent temporal contamination of knowledge extraction.

        Args:
            project_name: Project name
            include_confidential: If False (default), excludes confidential interactions

        Returns:
            List of unprocessed interactions in chronological order
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        confidential_filter = "" if include_confidential else "AND confidential = FALSE"

        cursor.execute(f"""
            SELECT * FROM interactions
            WHERE project_name = ?
              AND processed = FALSE
              AND deleted_at IS NULL
              {confidential_filter}
            ORDER BY chain_index ASC
        """, (project_name,))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def mark_interaction_processed(self, uuid: str) -> bool:
        """Mark a single interaction as processed."""
        return self.mark_interactions_processed([uuid]) > 0

    def mark_interactions_processed(self, uuids: List[str]) -> int:
        """Mark interactions as processed. Returns number of interactions marked."""
        conn = self._get_connection()
        cursor = conn.cursor()

        placeholders = ",".join(["?" for _ in uuids])
        cursor.execute(f"""
            UPDATE interactions
            SET processed = TRUE, extracted_at = CURRENT_TIMESTAMP
            WHERE uuid IN ({placeholders})
        """, uuids)

        count = cursor.rowcount
        conn.commit()
        conn.close()

        return count

    def mark_interaction_confidential(self, uuid: str, confidential: bool = True) -> bool:
        """
        Mark an interaction as confidential or non-confidential.

        Args:
            uuid: Interaction UUID
            confidential: True to mark as confidential, False to unmark

        Returns:
            True if interaction was updated, False if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE interactions
            SET confidential = ?
            WHERE uuid = ?
        """, (confidential, uuid))

        count = cursor.rowcount
        conn.commit()
        conn.close()

        return count > 0

    def get_all_interactions(self, project_name: str) -> List[Dict[str, Any]]:
        """Get all interactions for a project (for rebuild)."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM interactions
            WHERE project_name = ? AND deleted_at IS NULL
            ORDER BY chain_index ASC
        """, (project_name,))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_interaction_counts(self, project_name: str) -> Dict[str, int]:
        """Get total, processed, and unprocessed interaction counts for a project."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN processed = TRUE THEN 1 ELSE 0 END) AS processed,
                SUM(CASE WHEN processed = FALSE THEN 1 ELSE 0 END) AS unprocessed
            FROM interactions
            WHERE project_name = ?
              AND deleted_at IS NULL
        """, (project_name,))

        row = cursor.fetchone()
        conn.close()

        total = row["total"] if row and row["total"] is not None else 0
        processed = row["processed"] if row and row["processed"] is not None else 0
        unprocessed = row["unprocessed"] if row and row["unprocessed"] is not None else 0

        return {
            "total": int(total),
            "processed": int(processed),
            "unprocessed": int(unprocessed),
        }

    def get_interaction_by_uuid(self, uuid: str) -> Optional[Dict[str, Any]]:
        """Get interaction by UUID."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM interactions WHERE uuid = ?",
            (uuid,)
        )

        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else None



    def verify_interaction_chain(self, project_name: str) -> Dict[str, Any]:
        """
        Verify integrity of interaction hash chain.

        Returns:
            {
                "verified": bool,
                "total_interactions": int,
                "chain_length": int,
                "errors": [...]
            }
        """
        interactions = self.get_all_interactions(project_name)

        results = {
            "verified": True,
            "total_interactions": len(interactions),
            "chain_length": len(interactions),
            "purged_interactions": 0,
            "errors": []
        }

        for i, interaction in enumerate(interactions):
            if (
                interaction.get("user_message") == "__PURGED_NETWORK_MCP__"
                and interaction.get("assistant_message") == "__PURGED_NETWORK_MCP__"
            ):
                results["purged_interactions"] += 1
                continue

            # Recalculate hash
            expected_hash = self._calculate_interaction_hash(interaction)

            # Verify hash matches
            if expected_hash != interaction["content_hash"]:
                results["verified"] = False
                results["errors"].append({
                    "type": "hash_mismatch",
                    "interaction_uuid": interaction["uuid"],
                    "chain_index": interaction["chain_index"],
                    "expected": expected_hash,
                    "actual": interaction["content_hash"]
                })

            # Verify chain link
            if i > 0:
                if interaction["previous_hash"] != interactions[i-1]["content_hash"]:
                    results["verified"] = False
                    results["errors"].append({
                        "type": "chain_broken",
                        "interaction_uuid": interaction["uuid"],
                        "chain_index": interaction["chain_index"],
                        "expected_previous": interactions[i-1]["content_hash"],
                        "actual_previous": interaction["previous_hash"]
                    })

            # Verify chain index is sequential
            if interaction["chain_index"] != i + 1:
                results["verified"] = False
                results["errors"].append({
                    "type": "index_mismatch",
                    "interaction_uuid": interaction["uuid"],
                    "expected_index": i + 1,
                    "actual_index": interaction["chain_index"]
                })

        return results

    def record_task_operation(
        self,
        *,
        project_name: str,
        operation: str,
        success: bool,
        task_name: str,
        task_uuid: Optional[str] = None,
        status_before: Optional[str] = None,
        status_after: Optional[str] = None,
        priority_before: Optional[str] = None,
        priority_after: Optional[str] = None,
        workflow_session_id: Optional[str] = None,
        source_interaction_uuid: Optional[str] = None,
        source_interaction_hash: Optional[str] = None,
        command_context: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Record a successful or attempted task operation event with provenance hash."""
        event_uuid = f"taskop-{uuid_module.uuid4().hex[:12]}"
        created_at = datetime.now().isoformat()

        # Compute event_hash for tamper-evident provenance (per OTS spec)
        hash_input = f"{task_uuid or ''}|{operation}|{status_before or ''}|{status_after or ''}|{created_at}"
        event_hash = hashlib.sha256(hash_input.encode('utf-8')).hexdigest()

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO task_operations (
                event_uuid, created_at, project_name, operation, success,
                task_uuid, task_name,
                status_before, status_after,
                priority_before, priority_after,
                workflow_session_id,
                source_interaction_uuid, source_interaction_hash,
                command_context, payload_json,
                event_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event_uuid,
            created_at,
            project_name,
            operation,
            1 if success else 0,
            task_uuid,
            task_name,
            status_before,
            status_after,
            priority_before,
            priority_after,
            workflow_session_id,
            source_interaction_uuid,
            source_interaction_hash,
            command_context,
            json.dumps(payload or {}, sort_keys=True),
            event_hash,
        ))
        conn.commit()
        conn.close()
        return event_uuid

    def verify_task_operation_hash(self, event_uuid: str) -> tuple[bool, str]:
        """
        Verify a task operation's event_hash has not been tampered with.

        Returns (is_valid, message).
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT task_uuid, operation, status_before, status_after, created_at, event_hash
            FROM task_operations WHERE event_uuid = ?
        """, (event_uuid,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return False, f"Event not found: {event_uuid}"

        task_uuid, operation, status_before, status_after, created_at, stored_hash = row

        if not stored_hash:
            return False, "No event_hash stored (pre-OTS record)"

        # Recompute hash
        hash_input = f"{task_uuid or ''}|{operation}|{status_before or ''}|{status_after or ''}|{created_at}"
        recomputed = hashlib.sha256(hash_input.encode('utf-8')).hexdigest()

        if recomputed != stored_hash:
            return False, f"Hash mismatch - record tampered. Expected {recomputed[:16]}..., got {stored_hash[:16]}..."

        return True, "Hash verified"

    def get_task_operations_pending_ots(self, limit: int = 100) -> list[Dict[str, Any]]:
        """Get task operations that have event_hash but no OTS proof yet."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT event_uuid, event_hash, created_at
            FROM task_operations
            WHERE event_hash IS NOT NULL AND ots_proof IS NULL
            ORDER BY created_at ASC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [{"event_uuid": r[0], "event_hash": r[1], "created_at": r[2]} for r in rows]

    def update_task_operation_ots(
        self,
        event_uuid: str,
        ots_proof: str,
        ots_merkle_root: Optional[str] = None,
        ots_batch_index: Optional[int] = None,
    ) -> bool:
        """Update a task operation with OTS proof data."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE task_operations
            SET ots_proof = ?, ots_merkle_root = ?, ots_batch_index = ?
            WHERE event_uuid = ?
        """, (ots_proof, ots_merkle_root, ots_batch_index, event_uuid))
        updated = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return updated

    def find_task_operation_event(
        self,
        *,
        project_name: str,
        task_name: str,
        workflow_session_id: Optional[str] = None,
        reference_timestamp: Optional[str] = None,
        lookback_hours: int = 12,
    ) -> Optional[Dict[str, Any]]:
        """
        Find the best matching successful task operation event for a task name.

        Preference order:
        1. Exact workflow_session_id match
        2. Recent successful exact-name event within lookback window
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        if workflow_session_id:
            cursor.execute("""
                SELECT * FROM task_operations
                WHERE project_name = ?
                  AND success = 1
                  AND workflow_session_id = ?
                  AND task_name = ?
                ORDER BY created_at DESC
                LIMIT 2
            """, (project_name, workflow_session_id, task_name))
            rows = cursor.fetchall()
            if len(rows) == 1:
                conn.close()
                return dict(rows[0])
            if len(rows) > 1:
                conn.close()
                raise ValueError(
                    f"Multiple task operation events matched task '{task_name}' "
                    f"in workflow session '{workflow_session_id}'"
                )

        if reference_timestamp:
            try:
                reference_dt = datetime.fromisoformat(str(reference_timestamp).replace("Z", "+00:00"))
                earliest_dt = reference_dt.timestamp() - (lookback_hours * 3600)
                earliest_iso = datetime.fromtimestamp(earliest_dt).isoformat()
                latest_iso = reference_dt.isoformat()
                cursor.execute("""
                    SELECT * FROM task_operations
                    WHERE project_name = ?
                      AND success = 1
                      AND task_name = ?
                      AND created_at BETWEEN ? AND ?
                    ORDER BY created_at DESC
                    LIMIT 2
                """, (project_name, task_name, earliest_iso, latest_iso))
                rows = cursor.fetchall()
                if len(rows) == 1:
                    conn.close()
                    return dict(rows[0])
                if len(rows) > 1:
                    conn.close()
                    raise ValueError(
                        f"Multiple recent task operation events matched task '{task_name}' "
                        f"within {lookback_hours}h fallback window"
                    )
            except ValueError:
                raise
            except Exception:
                pass

        conn.close()
        return None

    def get_task_operations(
        self,
        *,
        project_name: str,
        start: str,
        end: str,
        operation: Optional[str] = None,
        task_name: Optional[str] = None,
        status_before: Optional[str] = None,
        status_after: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return successful task operations for a project and inclusive time window."""
        conn = self._get_connection()
        cursor = conn.cursor()

        query = [
            "SELECT * FROM task_operations",
            "WHERE project_name = ?",
            "  AND success = 1",
            "  AND created_at BETWEEN ? AND ?",
        ]
        params: List[Any] = [project_name, start, end]

        if operation is not None:
            query.append("  AND operation = ?")
            params.append(operation)
        if task_name is not None:
            query.append("  AND task_name = ?")
            params.append(task_name)
        if status_before is not None:
            query.append("  AND status_before = ?")
            params.append(status_before)
        if status_after is not None:
            query.append("  AND status_after = ?")
            params.append(status_after)

        query.append("ORDER BY created_at ASC")
        cursor.execute("\n".join(query), params)
        rows = cursor.fetchall()
        conn.close()

        results: List[Dict[str, Any]] = []
        for row in rows:
            try:
                results.append(dict(row))
            except Exception:
                continue
        return results

    def get_task_operation_stats(
        self,
        *,
        project_name: str,
        start: str,
        end: str,
    ) -> Dict[str, int]:
        """Aggregate task activity counts for a project and inclusive time window."""
        counts = {
            "created": 0,
            "started": 0,
            "paused": 0,
            "completed": 0,
            "invalidated": 0,
            "priority_changed": 0,
            "total_events": 0,
        }

        for row in self.get_task_operations(project_name=project_name, start=start, end=end):
            event_type = classify_task_operation(row)
            if not event_type:
                continue
            counts[event_type] += 1
            counts["total_events"] += 1

        return counts

    # -------------------------------------------------------------------------
    # Sync Job Methods (MCP Async Sync)
    # -------------------------------------------------------------------------

    def create_sync_job(
        self,
        *,
        job_id: str,
        project_name: str,
        request_json: str,
        payload_hash: Optional[str] = None,
        transport_type: str = "stdio",
        client_cert_fingerprint: Optional[str] = None,
        client_cert_subject: Optional[str] = None,
        client_cert_serial: Optional[str] = None,
        client_cert_issuer: Optional[str] = None,
        client_cert_not_before: Optional[str] = None,
        client_cert_not_after: Optional[str] = None,
        submitted_by_agent: Optional[str] = None,
        submitted_by_model: Optional[str] = None,
        quality_review_required: bool = True,
        constrained_environment: bool = False,
    ) -> str:
        """Create a new sync job in queued status. Returns job_id."""
        now = datetime.utcnow().isoformat() + "Z"
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO sync_jobs (
                job_id, project_name, status, stage, progress,
                submitted_by_agent, submitted_by_model,
                request_json, payload_hash, payload_hash_verified, transport_type,
                client_cert_fingerprint, client_cert_subject, client_cert_serial,
                client_cert_issuer, client_cert_not_before, client_cert_not_after,
                quality_review_required, constrained_environment,
                created_at, updated_at
            ) VALUES (?, ?, 'queued', 'submitted', 0.0, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id, project_name, submitted_by_agent, submitted_by_model,
                request_json, payload_hash, transport_type,
                client_cert_fingerprint, client_cert_subject, client_cert_serial,
                client_cert_issuer, client_cert_not_before, client_cert_not_after,
                1 if quality_review_required else 0,
                1 if constrained_environment else 0, now, now
            ),
        )
        conn.commit()
        conn.close()
        self._append_sync_job_event(job_id, project_name, "created", "submitted", "Job created")
        return job_id

    def get_sync_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a sync job by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sync_jobs WHERE job_id = ?", (job_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def list_sync_jobs(
        self,
        project_name: str,
        *,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List sync jobs for a project, optionally filtered by status."""
        conn = self._get_connection()
        cursor = conn.cursor()
        if status:
            cursor.execute(
                """SELECT * FROM sync_jobs
                   WHERE project_name = ? AND status = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (project_name, status, limit),
            )
        else:
            cursor.execute(
                """SELECT * FROM sync_jobs
                   WHERE project_name = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (project_name, limit),
            )
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def claim_next_sync_job(self, project_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Atomically claim the next queued job. Returns the job or None."""
        now = datetime.utcnow().isoformat() + "Z"
        conn = self._get_connection()
        cursor = conn.cursor()

        # Find oldest queued job
        if project_name:
            cursor.execute(
                """SELECT job_id FROM sync_jobs
                   WHERE status = 'queued' AND project_name = ?
                   ORDER BY created_at ASC LIMIT 1""",
                (project_name,),
            )
        else:
            cursor.execute(
                """SELECT job_id FROM sync_jobs
                   WHERE status = 'queued'
                   ORDER BY created_at ASC LIMIT 1"""
            )
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None

        job_id = row["job_id"]

        # Atomic claim: update only if still queued
        cursor.execute(
            """UPDATE sync_jobs
               SET status = 'running', started_at = ?, updated_at = ?
               WHERE job_id = ? AND status = 'queued'""",
            (now, now, job_id),
        )
        if cursor.rowcount == 0:
            conn.close()
            return None  # Another worker claimed it

        conn.commit()

        # Re-fetch the job
        cursor.execute("SELECT * FROM sync_jobs WHERE job_id = ?", (job_id,))
        job = cursor.fetchone()
        conn.close()

        if job:
            self._append_sync_job_event(
                job_id, job["project_name"], "claimed", job["stage"], "Job claimed by worker"
            )
        return dict(job) if job else None

    def update_sync_job_status(
        self,
        job_id: str,
        *,
        status: Optional[str] = None,
        stage: Optional[str] = None,
        progress: Optional[float] = None,
        source_interaction_uuid: Optional[str] = None,
        extraction_batch_uuid: Optional[str] = None,
        payload_hash_verified: Optional[bool] = None,
        raw_request_purged_at: Optional[str] = None,
        raw_conversation_purged_at: Optional[str] = None,
        client_cert_fingerprint: Optional[str] = None,
        client_cert_subject: Optional[str] = None,
        client_cert_serial: Optional[str] = None,
        client_cert_issuer: Optional[str] = None,
        client_cert_not_before: Optional[str] = None,
        client_cert_not_after: Optional[str] = None,
    ) -> bool:
        """Update sync job status/stage/progress. Returns True if updated."""
        now = datetime.utcnow().isoformat() + "Z"
        conn = self._get_connection()
        cursor = conn.cursor()

        updates = ["updated_at = ?"]
        params: List[Any] = [now]

        if status is not None:
            updates.append("status = ?")
            params.append(status)
            if status == "complete":
                updates.append("completed_at = ?")
                params.append(now)
        if stage is not None:
            updates.append("stage = ?")
            params.append(stage)
        if progress is not None:
            updates.append("progress = ?")
            params.append(progress)
        if source_interaction_uuid is not None:
            updates.append("source_interaction_uuid = ?")
            params.append(source_interaction_uuid)
        if extraction_batch_uuid is not None:
            updates.append("extraction_batch_uuid = ?")
            params.append(extraction_batch_uuid)
        if payload_hash_verified is not None:
            updates.append("payload_hash_verified = ?")
            params.append(1 if payload_hash_verified else 0)
        if raw_request_purged_at is not None:
            updates.append("raw_request_purged_at = ?")
            params.append(raw_request_purged_at)
        if raw_conversation_purged_at is not None:
            updates.append("raw_conversation_purged_at = ?")
            params.append(raw_conversation_purged_at)
        if client_cert_fingerprint is not None:
            updates.append("client_cert_fingerprint = ?")
            params.append(client_cert_fingerprint)
        if client_cert_subject is not None:
            updates.append("client_cert_subject = ?")
            params.append(client_cert_subject)
        if client_cert_serial is not None:
            updates.append("client_cert_serial = ?")
            params.append(client_cert_serial)
        if client_cert_issuer is not None:
            updates.append("client_cert_issuer = ?")
            params.append(client_cert_issuer)
        if client_cert_not_before is not None:
            updates.append("client_cert_not_before = ?")
            params.append(client_cert_not_before)
        if client_cert_not_after is not None:
            updates.append("client_cert_not_after = ?")
            params.append(client_cert_not_after)

        params.append(job_id)
        cursor.execute(
            f"UPDATE sync_jobs SET {', '.join(updates)} WHERE job_id = ?",
            params,
        )
        updated = cursor.rowcount > 0
        conn.commit()
        conn.close()

        if updated and (status or stage):
            job = self.get_sync_job(job_id)
            if job:
                self._append_sync_job_event(
                    job_id, job["project_name"],
                    f"status_{status}" if status else f"stage_{stage}",
                    stage or job.get("stage"),
                    f"Status: {status}, Stage: {stage}"
                )
        return updated

    def purge_sync_job_raw_data(self, job_id: str, marker: str = "__PURGED__") -> bool:
        """Purge raw request_json from a sync job after successful downstream persistence."""
        now = datetime.utcnow().isoformat() + "Z"
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE sync_jobs SET request_json = ?, raw_request_purged_at = ?, updated_at = ? WHERE job_id = ?",
            (marker, now, now, job_id),
        )
        updated = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return updated

    def purge_interaction_content(self, interaction_uuid: str, marker: str = "__PURGED_NETWORK_MCP__") -> bool:
        """Replace raw interaction content with the network purge marker."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE interactions
            SET user_message = ?, assistant_message = ?
            WHERE uuid = ?
            """,
            (marker, marker, interaction_uuid),
        )
        updated = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return updated

    def store_sync_job_result(self, job_id: str, result_json: str) -> bool:
        """Store the final result JSON for a completed job."""
        now = datetime.utcnow().isoformat() + "Z"
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE sync_jobs SET result_json = ?, updated_at = ? WHERE job_id = ?",
            (result_json, now, job_id),
        )
        updated = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return updated

    def store_sync_job_error(self, job_id: str, error_json: str) -> bool:
        """Store error JSON for a failed job."""
        now = datetime.utcnow().isoformat() + "Z"
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE sync_jobs SET error_json = ?, updated_at = ? WHERE job_id = ?",
            (error_json, now, job_id),
        )
        updated = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return updated

    def _append_sync_job_event(
        self,
        job_id: str,
        project_name: str,
        event_type: str,
        stage: Optional[str],
        message: Optional[str] = None,
        payload_json: Optional[str] = None,
    ) -> None:
        """Append an event to sync_job_events."""
        now = datetime.utcnow().isoformat() + "Z"
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO sync_job_events
               (job_id, project_name, event_type, stage, message, payload_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (job_id, project_name, event_type, stage, message, payload_json, now),
        )
        conn.commit()
        conn.close()

    def get_sync_job_events(self, job_id: str) -> List[Dict[str, Any]]:
        """Get all events for a sync job."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM sync_job_events WHERE job_id = ? ORDER BY created_at ASC",
            (job_id,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def reset_stale_sync_jobs(self, timeout_minutes: int = 30) -> int:
        """Reset jobs stuck in 'running' for longer than timeout to 'queued'."""
        from datetime import timedelta
        cutoff = (datetime.utcnow() - timedelta(minutes=timeout_minutes)).isoformat() + "Z"
        now = datetime.utcnow().isoformat() + "Z"

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE sync_jobs
               SET status = 'queued', updated_at = ?
               WHERE status = 'running' AND updated_at < ?""",
            (now, cutoff),
        )
        count = cursor.rowcount
        conn.commit()
        conn.close()
        return count
