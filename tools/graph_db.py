"""
Graph database operations for knowledge storage with extraction proofs.

Using Kuzu (predecessor to LadybugDB) - same API.
"""

import kuzu
import hashlib
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path
from uuid import uuid4

from tools.db_utils import open_kuzu_database


class GraphDatabase:
    """Graph database for storing entities and relationships with crypto proofs."""

    ENTITY_FIELD_NAMES = [
        "uuid",
        "name",
        "group_id",
        "summary",
        "labels",
        "attributes",
        "created_at",
        "source_interactions",
        "source_hashes",
        "source_chain",
        "extraction_timestamp",
        "extraction_timestamp_str",
        "extraction_version",
        "extraction_commit",
        "extraction_proof",
        "timestamp_proof",
        "t_last_accessed",
        "access_count",
        "deleted_at",
        "priority",
        "status",
    ]

    def __init__(self, db_path: str = "./memory/knowledge.graph"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # Create database
        self.db, self.conn = open_kuzu_database(db_path)

        self._ensure_schema_exists()

    @classmethod
    def _entity_return_clause(cls, alias: str = "e") -> str:
        """Return entity fields in a stable explicit order."""
        return ", ".join(f"{alias}.{field}" for field in cls.ENTITY_FIELD_NAMES)

    @staticmethod
    def _json_loads_or_default(value: Any, default: Any) -> Any:
        if not value:
            return default
        # If already parsed (list/dict), return as-is
        if isinstance(value, (list, dict)):
            return value
        # Otherwise parse JSON string
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return default

    @classmethod
    def _entity_from_row(cls, row: Any, start: int = 0) -> Dict[str, Any]:
        """Parse an entity row returned with _entity_return_clause()."""
        data = {}
        for offset, field in enumerate(cls.ENTITY_FIELD_NAMES):
            data[field] = row[start + offset]

        return {
            "uuid": data["uuid"],
            "name": data["name"],
            "group_id": data["group_id"],
            "summary": data["summary"],
            "labels": cls._json_loads_or_default(data["labels"], []),
            "attributes": cls._json_loads_or_default(data["attributes"], {}),
            "created_at": str(data["created_at"]) if data["created_at"] else None,
            "source_interactions": cls._json_loads_or_default(data["source_interactions"], []),
            "source_hashes": cls._json_loads_or_default(data["source_hashes"], []),
            "source_chain": cls._json_loads_or_default(data["source_chain"], []),
            "extraction_timestamp": str(data["extraction_timestamp"]) if data["extraction_timestamp"] else None,
            "extraction_timestamp_str": data["extraction_timestamp_str"],
            "extraction_version": data["extraction_version"],
            "extraction_commit": data["extraction_commit"],
            "extraction_proof": data["extraction_proof"],
            "timestamp_proof": data["timestamp_proof"],
            "t_last_accessed": str(data["t_last_accessed"]) if data["t_last_accessed"] else None,
            "access_count": data["access_count"] or 0,
            "deleted_at": str(data["deleted_at"]) if data["deleted_at"] else None,
            "priority": data["priority"],
            "status": data["status"],
        }

    def close(self):
        """Close the database connection."""
        # Close the underlying Kuzu handles explicitly. Merely dropping Python
        # references leaves file handles and writer state hanging around across
        # long test runs, which can produce order-dependent failures.
        conn = getattr(self, 'conn', None)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
            self.conn = None

        db = getattr(self, 'db', None)
        if db is not None:
            try:
                db.close()
            except Exception:
                pass
            self.db = None

    def _ensure_schema_exists(self):
        """Create node and relationship tables if they don't exist."""

        # Create Project node table
        try:
            self.conn.execute("""
                CREATE NODE TABLE IF NOT EXISTS Project (
                    name STRING PRIMARY KEY,
                    description STRING,
                    created_at TIMESTAMP
                )
            """)
        except:
            pass  # Table already exists

        # Create Entity node table (from Graphiti + our extensions)
        try:
            self.conn.execute("""
                CREATE NODE TABLE IF NOT EXISTS Entity (
                    uuid STRING PRIMARY KEY,
                    name STRING,
                    group_id STRING,
                    summary STRING,
                    labels STRING,
                    attributes STRING,
                    created_at TIMESTAMP,

                    source_interactions STRING,
                    source_hashes STRING,
                    source_chain STRING,
                    extraction_timestamp TIMESTAMP,
                    extraction_timestamp_str STRING,
                    extraction_version STRING,
                    extraction_commit STRING,
                    extraction_proof STRING,
                    timestamp_proof STRING,

                    extraction_batch_uuid STRING,

                    t_last_accessed TIMESTAMP,
                    access_count INT64,

                    deleted_at TIMESTAMP
                )
            """)
        except:
            pass

        # Create Alias node table (for non-destructive deduplication)
        try:
            self.conn.execute("""
                CREATE NODE TABLE IF NOT EXISTS Alias (
                    name STRING,
                    canonical_uuid STRING,
                    created_at TIMESTAMP,
                    created_at_str STRING,
                    source_interaction STRING,
                    source_hash STRING,
                    extraction_version STRING,
                    extraction_commit STRING,
                    alias_proof STRING,
                    timestamp_proof STRING,
                    PRIMARY KEY (name)
                )
            """)
        except:
            pass

        # Add new columns to existing Alias table (if it exists without them)
        try:
            self.conn.execute("ALTER TABLE Alias ADD created_at_str STRING")
        except:
            pass
        try:
            self.conn.execute("ALTER TABLE Alias ADD source_interaction STRING")
        except:
            pass
        try:
            self.conn.execute("ALTER TABLE Alias ADD source_hash STRING")
        except:
            pass
        try:
            self.conn.execute("ALTER TABLE Alias ADD extraction_version STRING")
        except:
            pass
        try:
            self.conn.execute("ALTER TABLE Alias ADD extraction_commit STRING")
        except:
            pass
        try:
            self.conn.execute("ALTER TABLE Alias ADD alias_proof STRING")
        except:
            pass
        try:
            self.conn.execute("ALTER TABLE Alias ADD timestamp_proof STRING")
        except:
            pass

        # Add timestamp_proof to Entity table (if it exists without it)
        try:
            self.conn.execute("ALTER TABLE Entity ADD timestamp_proof STRING")
        except:
            pass

        # Create HAS_ENTITY relationship
        try:
            self.conn.execute("""
                CREATE REL TABLE IF NOT EXISTS HAS_ENTITY (
                    FROM Project TO Entity
                )
            """)
        except:
            pass

        # Create ExtractionBatch node table (provenance hub for extraction runs)
        try:
            self.conn.execute("""
                CREATE NODE TABLE IF NOT EXISTS ExtractionBatch (
                    batch_uuid STRING PRIMARY KEY,
                    batch_hash STRING,
                    timestamp_proof STRING,

                    extracted_by_agent STRING,
                    extracted_by_model STRING,

                    extraction_version STRING,
                    extraction_commit STRING,
                    project_name STRING,

                    source_interaction_uuids STRING,
                    source_interaction_hashes STRING,

                    created_entity_uuids STRING,
                    created_relationship_uuids STRING,

                    previous_batch_hash STRING,
                    batch_index INT64,

                    result STRING,

                    created_at TIMESTAMP
                )
            """)
        except:
            pass

        # Create RELATES_TO relationship (from Graphiti + our extensions)
        try:
            self.conn.execute("""
                CREATE REL TABLE IF NOT EXISTS RELATES_TO (
                    FROM Entity TO Entity,

                    uuid STRING,
                    name STRING,
                    fact STRING,
                    group_id STRING,
                    episodes STRING,

                    created_at TIMESTAMP,
                    expired_at TIMESTAMP,
                    valid_at TIMESTAMP,
                    valid_at_str STRING,
                    invalid_at TIMESTAMP,

                    episode_hashes STRING,
                    derivation_timestamp TIMESTAMP,
                    derivation_timestamp_str STRING,
                    derivation_version STRING,
                    derivation_commit STRING,
                    derivation_proof STRING,
                    timestamp_proof STRING,

                    superseded_by STRING,
                    superseding_proof STRING,

                    extraction_batch_uuid STRING,

                    attributes STRING
                )
            """)
        except:
            pass

        # Add timestamp_proof to RELATES_TO relationship (if it exists without it)
        try:
            self.conn.execute("ALTER TABLE RELATES_TO ADD timestamp_proof STRING")
        except:
            pass

        # Add task-specific fields to Entity table (optional, only used for Task entities)
        try:
            self.conn.execute("ALTER TABLE Entity ADD priority STRING")
        except:
            pass
        try:
            self.conn.execute("ALTER TABLE Entity ADD status STRING")
        except:
            pass

        # Add extraction_batch_uuid to Entity table (migration for existing DBs)
        try:
            self.conn.execute("ALTER TABLE Entity ADD extraction_batch_uuid STRING")
        except:
            pass

        # Add extraction_batch_uuid to RELATES_TO relationship (migration for existing DBs)
        try:
            self.conn.execute("ALTER TABLE RELATES_TO ADD extraction_batch_uuid STRING")
        except:
            pass

        # =====================================================================
        # Phase 2: Execution Telemetry Tables
        # These are SEPARATE from Entity/RELATES_TO (operational, not semantic)
        # =====================================================================

        # Create ProcedureRun node table (execution telemetry)
        try:
            self.conn.execute("""
                CREATE NODE TABLE IF NOT EXISTS ProcedureRun (
                    uuid STRING PRIMARY KEY,
                    procedure_uuid STRING,
                    project_name STRING,

                    created_by_agent STRING,
                    created_by_model STRING,

                    started_at TIMESTAMP,
                    started_at_str STRING,
                    finished_at TIMESTAMP,
                    finished_at_str STRING,

                    status STRING,
                    result_note STRING,

                    created_at TIMESTAMP
                )
            """)
        except:
            pass

        # Create StepRun node table (execution telemetry)
        try:
            self.conn.execute("""
                CREATE NODE TABLE IF NOT EXISTS StepRun (
                    uuid STRING PRIMARY KEY,
                    procedure_run_uuid STRING,
                    procedure_step_uuid STRING,
                    step_number INT64,

                    started_at TIMESTAMP,
                    started_at_str STRING,
                    finished_at TIMESTAMP,
                    finished_at_str STRING,

                    status STRING,
                    result_note STRING,

                    created_at TIMESTAMP
                )
            """)
        except:
            pass

        # Create RUNS relationship (ProcedureRun -> Entity[Procedure])
        # Note: target label constraint enforced in application code
        try:
            self.conn.execute("""
                CREATE REL TABLE IF NOT EXISTS RUNS (
                    FROM ProcedureRun TO Entity,
                    uuid STRING,
                    created_at TIMESTAMP
                )
            """)
        except:
            pass

        # Create HAS_STEP_RUN relationship (ProcedureRun -> StepRun)
        try:
            self.conn.execute("""
                CREATE REL TABLE IF NOT EXISTS HAS_STEP_RUN (
                    FROM ProcedureRun TO StepRun,
                    uuid STRING,
                    created_at TIMESTAMP
                )
            """)
        except:
            pass

        # Create RUNS_STEP relationship (StepRun -> Entity[ProcedureStep])
        # Note: target label constraint enforced in application code
        try:
            self.conn.execute("""
                CREATE REL TABLE IF NOT EXISTS RUNS_STEP (
                    FROM StepRun TO Entity,
                    uuid STRING,
                    created_at TIMESTAMP
                )
            """)
        except:
            pass

        # Create RunBatch node table (execution audit batching)
        try:
            self.conn.execute("""
                CREATE NODE TABLE IF NOT EXISTS RunBatch (
                    batch_uuid STRING PRIMARY KEY,
                    project_name STRING,
                    created_by_agent STRING,
                    created_by_model STRING,

                    run_uuids STRING,
                    run_hashes STRING,

                    batch_hash STRING,
                    previous_batch_hash STRING,
                    batch_index INT64,

                    timestamp_proof STRING,

                    created_at TIMESTAMP,
                    created_at_str STRING
                )
            """)
        except:
            pass

        # Migration: Add new audit fields to ProcedureRun
        for field, ftype in [
            ("invocation_context", "STRING"),
            ("invocation_source", "STRING"),
            ("run_batch_uuid", "STRING"),
            ("run_hash", "STRING"),
        ]:
            try:
                self.conn.execute(f"ALTER TABLE ProcedureRun ADD {field} {ftype}")
            except:
                pass

        # Migration: Add new audit fields to StepRun
        for field, ftype in [
            ("step_hash", "STRING"),
        ]:
            try:
                self.conn.execute(f"ALTER TABLE StepRun ADD {field} {ftype}")
            except:
                pass

    # Valid invocation context values
    VALID_INVOCATION_CONTEXTS = {
        "procedure_md",   # Executed via procedure.md workflow
        "manual",         # Manual execution by user
        "script",         # Executed by a script
        "conversation",   # Triggered from conversation
        "api",            # Triggered via API
    }

    def create_project_node(self, name: str, description: Optional[str] = None) -> bool:
        """Create project node in graph DB."""
        try:
            created_at = datetime.now().isoformat()
            self.conn.execute("""
                CREATE (p:Project {
                    name: $name,
                    description: $description,
                    created_at: timestamp($created_at)
                })
            """, {
                "name": name,
                "description": description or "",
                "created_at": created_at,
            })
            return True
        except:
            return False  # Already exists

    def _calculate_extraction_proof(
        self,
        entity_name: str,
        entity_summary: str,
        entity_labels: List[str],
        entity_attributes: Dict[str, Any],
        source_hashes: List[str],
        extraction_timestamp: str
    ) -> str:
        """Calculate SHA-256 extraction proof."""
        content = "|".join([
            entity_name,
            entity_summary or "",
            json.dumps(sorted(entity_labels)),
            json.dumps(entity_attributes) if entity_attributes else "",
            *sorted(source_hashes),
            extraction_timestamp
        ])
        return hashlib.sha256(content.encode()).hexdigest()

    def _calculate_derivation_proof(
        self,
        fact: str,
        source_uuid: str,
        target_uuid: str,
        relationship_name: str,
        group_id: str,
        episode_hashes: List[str],
        valid_at: str
    ) -> str:
        """Calculate SHA-256 derivation proof."""
        content = "|".join([
            fact,
            source_uuid,
            target_uuid,
            relationship_name,
            group_id,
            *sorted(episode_hashes),
            valid_at
        ])
        return hashlib.sha256(content.encode()).hexdigest()

    def _calculate_batch_hash(
        self,
        extracted_by_agent: str,
        extracted_by_model: Optional[str],
        extraction_version: str,
        extraction_commit: str,
        project_name: str,
        source_interaction_uuids: List[str],
        source_interaction_hashes: List[str],
        created_entity_uuids: List[str],
        created_relationship_uuids: List[str]
    ) -> str:
        """
        Calculate SHA-256 batch hash from canonical payload.

        The canonical payload is a JSON object with keys in alphabetical order,
        arrays sorted alphabetically, compact JSON (no whitespace), UTF-8 encoding.

        This hash is graph-verifiable: all input fields are stored in ExtractionBatch node.
        """
        canonical_payload = {
            "created_entity_uuids": sorted(created_entity_uuids),
            "created_relationship_uuids": sorted(created_relationship_uuids),
            "extracted_by_agent": extracted_by_agent or "",
            "extracted_by_model": extracted_by_model or "",
            "extraction_commit": extraction_commit or "",
            "extraction_version": extraction_version or "",
            "project_name": project_name,
            "source_interaction_hashes": sorted(source_interaction_hashes),
            "source_interaction_uuids": sorted(source_interaction_uuids)
        }
        # Compact JSON with sorted keys
        canonical_json = json.dumps(canonical_payload, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()

    def _calculate_alias_proof(
        self,
        alias_name: str,
        canonical_uuid: str,
        source_hash: str,
        created_at: str
    ) -> str:
        """
        Calculate SHA-256 alias proof.

        Links alias to SQL hash chain via source_hash.
        """
        content = "|".join([
            alias_name,
            canonical_uuid,
            source_hash,
            created_at
        ])
        return hashlib.sha256(content.encode()).hexdigest()

    def create_extraction_batch(
        self,
        project_name: str,
        extracted_by_agent: str,
        extracted_by_model: Optional[str],
        extraction_version: str,
        extraction_commit: str,
        source_interaction_uuids: List[str],
        source_interaction_hashes: List[str],
        created_entity_uuids: List[str],
        created_relationship_uuids: List[str],
        timestamp_proof: Optional[str] = None,
        batch_uuid: Optional[str] = None,
        result: str = "success"
    ) -> str:
        """
        Create an ExtractionBatch node to track provenance of extraction run.

        Args:
            project_name: Project name
            extracted_by_agent: Agent name (e.g., "codex", "auggie")
            extracted_by_model: Model name (e.g., "o3", "claude-opus-4-20250514")
            extraction_version: Extraction version
            extraction_commit: Extraction commit/source
            source_interaction_uuids: UUIDs of source interactions
            source_interaction_hashes: Content hashes from SQL
            created_entity_uuids: UUIDs of entities created in this batch
            created_relationship_uuids: UUIDs of relationships created in this batch
            timestamp_proof: OTS proof of batch_hash (optional, can be added later)
            batch_uuid: Optional UUID (will be generated if not provided)
            result: Batch result type ("success", "heartbeat", "partial")

        Returns:
            UUID of created batch node
        """
        import uuid as uuid_module

        if batch_uuid is None:
            batch_uuid = f"batch-{uuid_module.uuid4().hex[:12]}"

        # Calculate batch hash
        batch_hash = self._calculate_batch_hash(
            extracted_by_agent=extracted_by_agent,
            extracted_by_model=extracted_by_model,
            extraction_version=extraction_version,
            extraction_commit=extraction_commit,
            project_name=project_name,
            source_interaction_uuids=source_interaction_uuids,
            source_interaction_hashes=source_interaction_hashes,
            created_entity_uuids=created_entity_uuids,
            created_relationship_uuids=created_relationship_uuids
        )

        # Get previous batch for chain
        previous_batch_hash = None
        batch_index = 1
        try:
            query_result = self.conn.execute("""
                MATCH (b:ExtractionBatch)
                WHERE b.project_name = $project_name
                RETURN b.batch_hash, b.batch_index
                ORDER BY b.batch_index DESC
                LIMIT 1
            """, {"project_name": project_name})
            if query_result.has_next():
                row = query_result.get_next()
                previous_batch_hash = row[0]
                batch_index = (row[1] or 0) + 1
        except:
            pass

        created_at = datetime.now().isoformat()

        self.conn.execute("""
            CREATE (b:ExtractionBatch {
                batch_uuid: $batch_uuid,
                batch_hash: $batch_hash,
                timestamp_proof: $timestamp_proof,

                extracted_by_agent: $extracted_by_agent,
                extracted_by_model: $extracted_by_model,

                extraction_version: $extraction_version,
                extraction_commit: $extraction_commit,
                project_name: $project_name,

                source_interaction_uuids: $source_interaction_uuids,
                source_interaction_hashes: $source_interaction_hashes,

                created_entity_uuids: $created_entity_uuids,
                created_relationship_uuids: $created_relationship_uuids,

                previous_batch_hash: $previous_batch_hash,
                batch_index: $batch_index,

                result: $result,

                created_at: timestamp($created_at)
            })
        """, {
            "batch_uuid": batch_uuid,
            "batch_hash": batch_hash,
            "timestamp_proof": timestamp_proof,
            "extracted_by_agent": extracted_by_agent,
            "extracted_by_model": extracted_by_model or "",
            "extraction_version": extraction_version,
            "extraction_commit": extraction_commit,
            "project_name": project_name,
            "source_interaction_uuids": json.dumps(sorted(source_interaction_uuids)),
            "source_interaction_hashes": json.dumps(sorted(source_interaction_hashes)),
            "created_entity_uuids": json.dumps(sorted(created_entity_uuids)),
            "created_relationship_uuids": json.dumps(sorted(created_relationship_uuids)),
            "previous_batch_hash": previous_batch_hash,
            "batch_index": batch_index,
            "result": result,
            "created_at": created_at
        })

        return batch_uuid

    def get_latest_valid_batch(self, project_name: str) -> Optional[Dict[str, Any]]:
        """
        Get the most recent ExtractionBatch with result in ('success', 'heartbeat').
        Used by pre-commit sync validator.

        Args:
            project_name: Project to check

        Returns:
            Dict with batch_uuid, created_at, result or None if no valid batch
        """
        try:
            result = self.conn.execute("""
                MATCH (b:ExtractionBatch)
                WHERE b.project_name = $project_name
                  AND b.result IN ['success', 'heartbeat']
                RETURN b.batch_uuid, b.created_at, b.result
                ORDER BY b.created_at DESC
                LIMIT 1
            """, {"project_name": project_name})
            if result.has_next():
                row = result.get_next()
                return {
                    "batch_uuid": row[0],
                    "created_at": row[1],
                    "result": row[2]
                }
        except Exception:
            pass
        return None

    def create_entity(
        self,
        name: str,
        group_id: str,
        source_interactions: List[str],
        source_hashes: List[str],
        extraction_version: str,
        extraction_commit: str,
        summary: Optional[str] = None,
        labels: Optional[List[str]] = None,
        attributes: Optional[Dict[str, Any]] = None,
        uuid: Optional[str] = None,
        event_timestamp: Optional[str] = None,
        timestamp_proof: Optional[str] = None,
        source_chain: Optional[List[Dict[str, str]]] = None,
        priority: Optional[str] = None,
        status: Optional[str] = None,
        extraction_batch_uuid: Optional[str] = None
    ) -> str:
        """
        Create entity with extraction proof.

        Args:
            name: Entity name
            group_id: Project name
            source_interactions: List of interaction UUIDs
            source_hashes: List of content_hash from SQL
            extraction_version: Semantic version (e.g., "v1.0.0")
            extraction_commit: Git commit hash
            summary: Optional description
            labels: Optional list of labels
            attributes: Optional dict of attributes
            uuid: Optional UUID (will be generated if not provided)
            event_timestamp: Optional event time (when entity was observed in conversation).
                           If None, defaults to Unix epoch (1970-01-01T00:00:00Z)
            extraction_batch_uuid: Optional reference to ExtractionBatch node

        Returns:
            UUID of created entity
        """
        import uuid as uuid_module

        if uuid is None:
            uuid = f"entity-{uuid_module.uuid4().hex[:12]}"

        # extraction_timestamp = event time (when it happened in conversation)
        # Default to Unix epoch if not provided
        extraction_timestamp = event_timestamp or "1970-01-01T00:00:00Z"

        # Calculate extraction proof
        extraction_proof = self._calculate_extraction_proof(
            name,
            summary or "",
            labels or [],
            attributes or {},
            source_hashes,
            extraction_timestamp
        )

        # Convert lists/dicts to JSON strings for storage
        labels_json = json.dumps(labels or [])
        attributes_json = json.dumps(attributes or {})
        source_interactions_json = json.dumps(source_interactions)
        source_hashes_json = json.dumps(source_hashes)
        source_chain_json = json.dumps(source_chain or [])

        created_at = datetime.now().isoformat()
        self.conn.execute("""
            CREATE (e:Entity {
                uuid: $uuid,
                name: $name,
                group_id: $group_id,
                summary: $summary,
                labels: $labels,
                attributes: $attributes,
                created_at: timestamp($created_at),
                source_interactions: $source_interactions,
                source_hashes: $source_hashes,
                source_chain: $source_chain,
                extraction_timestamp: timestamp($extraction_timestamp),
                extraction_timestamp_str: $extraction_timestamp_str,
                extraction_version: $extraction_version,
                extraction_commit: $extraction_commit,
                extraction_proof: $extraction_proof,
                timestamp_proof: $timestamp_proof,
                extraction_batch_uuid: $extraction_batch_uuid,
                deleted_at: NULL,
                t_last_accessed: timestamp($created_at),
                access_count: 0,
                priority: $priority,
                status: $status
            })
        """, {
            "uuid": uuid,
            "name": name,
            "group_id": group_id,
            "summary": summary or "",
            "labels": labels_json,
            "attributes": attributes_json,
            "created_at": created_at,
            "source_interactions": source_interactions_json,
            "source_hashes": source_hashes_json,
            "source_chain": source_chain_json,
            "extraction_timestamp": extraction_timestamp,
            "extraction_timestamp_str": extraction_timestamp,
            "extraction_version": extraction_version,
            "extraction_commit": extraction_commit,
            "extraction_proof": extraction_proof,
            "timestamp_proof": timestamp_proof or "",
            "extraction_batch_uuid": extraction_batch_uuid or "",
            "priority": priority,
            "status": status,
        })

        return uuid

    def link_project_to_entity(self, project_name: str, entity_uuid: str) -> bool:
        """Create HAS_ENTITY relationship."""
        try:
            self.conn.execute("""
                MATCH (p:Project {name: $project_name}), (e:Entity {uuid: $entity_uuid})
                CREATE (p)-[:HAS_ENTITY]->(e)
            """, {
                "project_name": project_name,
                "entity_uuid": entity_uuid,
            })
            return True
        except:
            return False

    def create_relationship(
        self,
        source_uuid: str,
        target_uuid: str,
        relationship_name: str,
        fact: str,
        group_id: str,
        episodes: List[str],
        episode_hashes: List[str],
        derivation_version: str,
        derivation_commit: str,
        valid_at: str,
        invalid_at: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
        uuid: Optional[str] = None,
        timestamp_proof: Optional[str] = None,
        extraction_batch_uuid: Optional[str] = None
    ) -> str:
        """
        Create relationship with derivation proof.

        Args:
            source_uuid: Source entity UUID
            target_uuid: Target entity UUID
            relationship_name: Type of relationship (e.g., "LOCATED_AT")
            fact: The actual fact
            group_id: Project name
            episodes: List of interaction UUIDs
            episode_hashes: List of content_hash from SQL
            derivation_version: Semantic version
            derivation_commit: Git commit hash
            valid_at: When fact became true
            invalid_at: When fact stopped being true (optional)
            attributes: Optional dict of attributes
            uuid: Optional UUID
            extraction_batch_uuid: Optional reference to ExtractionBatch node

        Returns:
            UUID of created relationship
        """
        import uuid as uuid_module

        if uuid is None:
            uuid = f"rel-{uuid_module.uuid4().hex[:12]}"

        derivation_timestamp = datetime.now().isoformat()

        # Calculate derivation proof
        derivation_proof = self._calculate_derivation_proof(
            fact,
            source_uuid,
            target_uuid,
            relationship_name,
            group_id,
            episode_hashes,
            valid_at
        )

        # Convert lists/dicts to JSON strings
        episodes_json = json.dumps(episodes)
        episode_hashes_json = json.dumps(episode_hashes)
        attributes_json = json.dumps(attributes or {})

        created_at = datetime.now().isoformat()
        self.conn.execute("""
            MATCH (source:Entity {uuid: $source_uuid}), (target:Entity {uuid: $target_uuid})
            CREATE (source)-[r:RELATES_TO {
                uuid: $uuid,
                name: $relationship_name,
                fact: $fact,
                group_id: $group_id,
                episodes: $episodes,
                created_at: timestamp($created_at),
                expired_at: NULL,
                valid_at: timestamp($valid_at),
                valid_at_str: $valid_at,
                invalid_at: CASE WHEN $invalid_at = '' THEN NULL ELSE timestamp($invalid_at) END,
                episode_hashes: $episode_hashes,
                derivation_timestamp: timestamp($derivation_timestamp),
                derivation_timestamp_str: $derivation_timestamp,
                derivation_version: $derivation_version,
                derivation_commit: $derivation_commit,
                derivation_proof: $derivation_proof,
                timestamp_proof: $timestamp_proof,
                extraction_batch_uuid: $extraction_batch_uuid,
                superseded_by: NULL,
                superseding_proof: NULL,
                attributes: $attributes
            }]->(target)
        """, {
            "source_uuid": source_uuid,
            "target_uuid": target_uuid,
            "uuid": uuid,
            "relationship_name": relationship_name,
            "fact": fact,
            "group_id": group_id,
            "episodes": episodes_json,
            "created_at": created_at,
            "valid_at": valid_at,
            "invalid_at": invalid_at or "",
            "episode_hashes": episode_hashes_json,
            "derivation_timestamp": derivation_timestamp,
            "derivation_version": derivation_version,
            "derivation_commit": derivation_commit,
            "derivation_proof": derivation_proof,
            "timestamp_proof": timestamp_proof or "",
            "extraction_batch_uuid": extraction_batch_uuid or "",
            "attributes": attributes_json,
        })

        return uuid


    def update_entity_access(self, entity_uuid: str) -> None:
        """
        Update entity access tracking (t_last_accessed and access_count).

        Note: Silently skips entities that don't have these properties
        (entities created before the timestamp migration).

        Args:
            entity_uuid: UUID of the entity to update
        """
        try:
            now = datetime.now().isoformat()
            self.conn.execute("""
                MATCH (e:Entity {uuid: $entity_uuid})
                SET e.t_last_accessed = timestamp($now),
                    e.access_count = CASE
                        WHEN e.access_count IS NULL THEN 1
                        ELSE e.access_count + 1
                    END
            """, {
                "entity_uuid": entity_uuid,
                "now": now,
            })
        except Exception as e:
            # Silently skip if property doesn't exist (old entities)
            # Don't print warning - this is expected for pre-migration entities
            pass

    def get_entity_by_uuid(self, entity_uuid: str, track_access: bool = True) -> Optional[Dict[str, Any]]:
        """
        Get entity by UUID.

        Args:
            entity_uuid: UUID of the entity
            track_access: Whether to update access tracking (default: True)
        """
        try:
            result = self.conn.execute(f"""
                MATCH (e:Entity {{uuid: $entity_uuid}})
                RETURN {self._entity_return_clause("e")}
            """, {
                "entity_uuid": entity_uuid,
            })

            rows = []
            while result.has_next():
                rows.append(result.get_next())

            if not rows:
                return None

            entity = self._entity_from_row(rows[0])

            # Track access
            if track_access:
                self.update_entity_access(entity_uuid)

            return entity
        except Exception as e:
            print(f"Error getting entity: {e}")
            return None

    def verify_entity_extraction(self, entity_uuid: str) -> Dict[str, Any]:
        """
        Verify extraction proof for an entity.

        Returns:
            {
                "verified": bool,
                "entity_uuid": str,
                "stored_proof": str,
                "calculated_proof": str,
                "match": bool
            }
        """
        entity = self.get_entity_by_uuid(entity_uuid)
        if not entity:
            return {
                "verified": False,
                "error": "Entity not found"
            }

        # Recalculate extraction proof
        calculated_proof = self._calculate_extraction_proof(
            entity["name"],
            entity["summary"] or "",
            entity["labels"],
            entity["attributes"],
            entity["source_hashes"],
            entity["extraction_timestamp_str"]
        )

        match = calculated_proof == entity["extraction_proof"]

        return {
            "verified": match,
            "entity_uuid": entity_uuid,
            "entity_name": entity["name"],
            "stored_proof": entity["extraction_proof"],
            "calculated_proof": calculated_proof,
            "match": match,
            "source_hashes": entity["source_hashes"],
            "extraction_version": entity["extraction_version"],
            "extraction_commit": entity["extraction_commit"]
        }

    def get_relationship_by_uuid(self, rel_uuid: str) -> Optional[Dict[str, Any]]:
        """Get relationship by UUID."""
        try:
            result = self.conn.execute("""
                MATCH (source:Entity)-[r:RELATES_TO {uuid: $rel_uuid}]->(target:Entity)
                RETURN source.uuid, target.uuid, r.*
            """, {
                "rel_uuid": rel_uuid,
            })

            rows = []
            while result.has_next():
                rows.append(result.get_next())

            if not rows:
                return None

            row = rows[0]
            return {
                "source_uuid": row[0],
                "target_uuid": row[1],
                "uuid": row[2],
                "name": row[3],
                "fact": row[4],
                "group_id": row[5],
                "episodes": json.loads(row[6]) if row[6] else [],
                "created_at": str(row[7]),
                "expired_at": str(row[8]) if row[8] else None,
                "valid_at": str(row[9]),
                "valid_at_str": row[10],
                "invalid_at": str(row[11]) if row[11] else None,
                "episode_hashes": json.loads(row[12]) if row[12] else [],
                "derivation_timestamp": str(row[13]),
                "derivation_timestamp_str": row[14],
                "derivation_version": row[15],
                "derivation_commit": row[16],
                "derivation_proof": row[17],
                "superseded_by": row[18],
                "superseding_proof": row[19],
                "attributes": json.loads(row[20]) if row[20] else {}
            }
        except Exception as e:
            print(f"Error getting relationship: {e}")
            return None

    def verify_relationship_derivation(self, rel_uuid: str) -> Dict[str, Any]:
        """
        Verify derivation proof for a relationship.

        Returns:
            {
                "verified": bool,
                "relationship_uuid": str,
                "stored_proof": str,
                "calculated_proof": str,
                "match": bool
            }
        """
        rel = self.get_relationship_by_uuid(rel_uuid)
        if not rel:
            return {
                "verified": False,
                "error": "Relationship not found"
            }

        # Recalculate derivation proof
        calculated_proof = self._calculate_derivation_proof(
            rel["fact"],
            rel["source_uuid"],
            rel["target_uuid"],
            rel["name"],
            rel["group_id"],
            rel["episode_hashes"],
            rel["valid_at_str"]
        )

        match = calculated_proof == rel["derivation_proof"]

        return {
            "verified": match,
            "relationship_uuid": rel_uuid,
            "fact": rel["fact"],
            "stored_proof": rel["derivation_proof"],
            "calculated_proof": calculated_proof,
            "match": match,
            "episode_hashes": rel["episode_hashes"],
            "derivation_version": rel["derivation_version"],
            "derivation_commit": rel["derivation_commit"]
        }



    def search_entities(
        self,
        project_name: str,
        query: Optional[str] = None,
        labels: Optional[List[str]] = None,
        limit: int = 50,
        track_access: bool = True,
        priority_order: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Search for entities in a project.

        Args:
            project_name: Project to search in
            query: Optional text to search in name/summary
            labels: Optional list of labels to filter by
            limit: Maximum number of results
            track_access: Whether to update access tracking for returned entities (default: True)
            priority_order: Whether to use priority ordering (new first, then recently accessed) (default: True)

        Returns:
            List of entity dictionaries (sorted by priority if priority_order=True)
        """
        try:
            # Step 1: Get base time for priority ordering (if enabled)
            base_time = None
            if priority_order:
                try:
                    max_result = self.conn.execute("""
                        MATCH (e:Entity)
                        WHERE e.group_id = $project_name
                          AND e.deleted_at IS NULL
                        RETURN max(e.extraction_timestamp) as max_time
                    """, {
                        "project_name": project_name,
                    })
                    if max_result.has_next():
                        max_time = max_result.get_next()[0]
                        if max_time:
                            # Calculate base time (24 hours before most recent entity)
                            from datetime import datetime, timedelta
                            if isinstance(max_time, str):
                                max_dt = datetime.fromisoformat(max_time.replace('Z', '+00:00'))
                            else:
                                max_dt = max_time
                            base_dt = max_dt - timedelta(hours=24)
                            base_time = base_dt.isoformat()
                except Exception as e:
                    # If priority ordering fails, continue without it
                    print(f"Warning: Priority ordering failed: {e}")
                    priority_order = False

            # Step 2: Build query
            cypher = """
                MATCH (p:Project {name: $project_name})-[:HAS_ENTITY]->(e:Entity)
                WHERE e.deleted_at IS NULL
            """
            params = {"project_name": project_name}

            # Add text search if provided
            if query:
                # Search in entity names/summaries (alias search done separately below)
                cypher += """
                    AND (lower(e.name) CONTAINS $query
                         OR lower(e.summary) CONTAINS $query)
                """
                params["query"] = query.lower()

            # Add label filter if provided
            if labels:
                # Check if entity has any of the specified labels
                # Use quoted label to avoid partial matches (e.g., "Procedure" vs "ProcedureStep")
                for i, label in enumerate(labels):
                    key = f"label_{i}"
                    cypher += f"""
                        AND e.labels CONTAINS ${key}
                    """
                    # Quote the label to match exact JSON array element
                    params[key] = f'"{label}"'

            cypher += f"""
                RETURN {self._entity_return_clause("e")}
            """

            # Add priority ordering if enabled
            if priority_order and base_time:
                cypher += """
                ORDER BY
                  CASE
                    WHEN e.extraction_timestamp > timestamp($base_time) THEN 1
                    WHEN e.t_last_accessed IS NOT NULL AND e.t_last_accessed > timestamp($base_time) THEN 2
                    ELSE 3
                  END,
                  e.extraction_timestamp DESC,
                  e.t_last_accessed DESC
                """
                params["base_time"] = base_time
            else:
                # Default ordering by creation time
                cypher += """
                ORDER BY e.extraction_timestamp DESC
                """

            cypher += f"""
                LIMIT {limit}
            """

            result = self.conn.execute(cypher, params)

            entities = []
            while result.has_next():
                row = result.get_next()
                entity = self._entity_from_row(row)
                entities.append(entity)

                # Track access for this entity
                if track_access:
                    self.update_entity_access(entity["uuid"])

            # Also search aliases if query provided
            if query:
                alias_result = self.conn.execute("""
                    MATCH (a:Alias)
                    WHERE lower(a.name) CONTAINS $query
                    RETURN DISTINCT a.canonical_uuid
                """, {
                    "query": query.lower(),
                })

                # Get entities for matching aliases
                while alias_result.has_next():
                    canonical_uuid = alias_result.get_next()[0]
                    # Check if we already have this entity
                    if not any(e['uuid'] == canonical_uuid for e in entities):
                        # Get the entity
                        entity_result = self.conn.execute(f"""
                            MATCH (p:Project {{name: $project_name}})-[:HAS_ENTITY]->(e:Entity)
                            WHERE e.uuid = $canonical_uuid AND e.deleted_at IS NULL
                            RETURN {self._entity_return_clause("e")}
                        """, {
                            "project_name": project_name,
                            "canonical_uuid": canonical_uuid,
                        })

                        if entity_result.has_next():
                            entity = self._entity_from_row(entity_result.get_next())
                            entities.append(entity)

                            if track_access:
                                self.update_entity_access(entity["uuid"])

            return entities
        except Exception as e:
            print(f"Error searching entities: {e}")
            return []

    def get_entity_facts(self, entity_uuid: str) -> List[Dict[str, Any]]:
        """
        Get all facts (relationships) about an entity.

        Args:
            entity_uuid: UUID of the entity

        Returns:
            List of facts where entity is source or target
        """
        try:
            # Get outgoing relationships (entity is source)
            result = self.conn.execute("""
                MATCH (e:Entity {uuid: $entity_uuid})-[r:RELATES_TO]->(target:Entity)
                WHERE r.expired_at IS NULL
                RETURN 'outgoing', e.name, r.name, r.fact, target.name, r.uuid,
                       r.valid_at, r.derivation_version, r.episodes
            """, {
                "entity_uuid": entity_uuid,
            })

            facts = []
            while result.has_next():
                row = result.get_next()
                facts.append({
                    "direction": row[0],
                    "source_name": row[1],
                    "relationship_type": row[2],
                    "fact": row[3],
                    "target_name": row[4],
                    "uuid": row[5],
                    "valid_at": str(row[6]),
                    "derivation_version": row[7],
                    "episodes": json.loads(row[8]) if row[8] else []
                })

            # Get incoming relationships (entity is target)
            result = self.conn.execute("""
                MATCH (source:Entity)-[r:RELATES_TO]->(e:Entity {uuid: $entity_uuid})
                WHERE r.expired_at IS NULL
                RETURN 'incoming', source.name, r.name, r.fact, e.name, r.uuid,
                       r.valid_at, r.derivation_version, r.episodes
            """, {
                "entity_uuid": entity_uuid,
            })

            while result.has_next():
                row = result.get_next()
                facts.append({
                    "direction": row[0],
                    "source_name": row[1],
                    "relationship_type": row[2],
                    "fact": row[3],
                    "target_name": row[4],
                    "uuid": row[5],
                    "valid_at": str(row[6]),
                    "derivation_version": row[7],
                    "episodes": json.loads(row[8]) if row[8] else []
                })

            return facts
        except Exception as e:
            print(f"Error getting entity facts: {e}")
            return []

    # =========================================================================
    # Procedural Memory Methods
    # =========================================================================

    # Lifecycle statuses that are excluded from default retrieval
    _EXCLUDED_LIFECYCLE_STATUSES = {"deprecated", "superseded", "invalid"}

    def _filter_by_lifecycle(
        self,
        entities: List[Dict[str, Any]],
        include_all_lifecycle: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Filter entities by lifecycle_status.

        By default, excludes deprecated, superseded, and invalid entities.
        Missing lifecycle_status is treated as "active" for backward compatibility.

        Args:
            entities: List of entity dictionaries
            include_all_lifecycle: If True, return all entities regardless of lifecycle

        Returns:
            Filtered list of entities
        """
        if include_all_lifecycle:
            return entities

        filtered = []
        for entity in entities:
            attrs = entity.get("attributes", {})
            if isinstance(attrs, str):
                try:
                    attrs = json.loads(attrs)
                except:
                    attrs = {}

            # Missing lifecycle_status is treated as "active"
            lifecycle = attrs.get("lifecycle_status", "active")
            if lifecycle not in self._EXCLUDED_LIFECYCLE_STATUSES:
                filtered.append(entity)

        return filtered

    def get_procedures(
        self,
        project_name: str,
        query: Optional[str] = None,
        limit: int = 50,
        include_all_lifecycle: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get all Procedure entities in a project.

        Args:
            project_name: Project to search in
            query: Optional text to search in name, summary, or attributes.search_text
            limit: Maximum number of results
            include_all_lifecycle: If True, include deprecated/superseded/invalid procedures

        Returns:
            List of Procedure entity dictionaries (filtered by lifecycle by default)
        """
        # Get more results than limit to account for lifecycle filtering
        fetch_limit = limit * 3 if not include_all_lifecycle else limit

        results = self.search_entities(
            project_name=project_name,
            query=query,
            labels=["Procedure"],
            limit=fetch_limit,
            track_access=True
        )

        # Apply lifecycle filtering
        filtered = self._filter_by_lifecycle(results, include_all_lifecycle)

        return filtered[:limit]

    def get_procedure_steps(
        self,
        procedure_name: str,
        project_name: str
    ) -> List[Dict[str, Any]]:
        """
        Get all steps for a procedure, ordered by step_number.

        Args:
            procedure_name: Name of the procedure
            project_name: Project name

        Returns:
            List of ProcedureStep entities in order
        """
        try:
            # Get steps that have this procedure_name in attributes
            # and sort by step_number from attributes
            result = self.conn.execute(f"""
                MATCH (p:Project {{name: $project_name}})-[:HAS_ENTITY]->(e:Entity)
                WHERE e.deleted_at IS NULL
                  AND e.labels CONTAINS '"ProcedureStep"'
                  AND e.attributes CONTAINS $procedure_name
                RETURN {self._entity_return_clause("e")}
            """, {
                "project_name": project_name,
                "procedure_name": procedure_name,
            })

            steps = []
            while result.has_next():
                row = result.get_next()
                entity = self._entity_from_row(row)
                steps.append(entity)

            # Sort by step_number from attributes
            def get_step_number(step):
                attrs = step.get("attributes", {})
                if isinstance(attrs, str):
                    try:
                        attrs = json.loads(attrs)
                    except:
                        return 999
                return attrs.get("step_number", 999)

            steps.sort(key=get_step_number)
            return steps

        except Exception as e:
            print(f"Error getting procedure steps: {e}")
            return []

    def search_procedures_by_step(
        self,
        project_name: str,
        step_query: str,
        limit: int = 10,
        include_all_lifecycle: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Find procedures that contain a step matching the query.
        Searches in ProcedureStep attributes (search_text, script_refs, action).

        Args:
            project_name: Project to search in
            step_query: Text to search for in step content
            limit: Maximum number of results
            include_all_lifecycle: If True, include deprecated/superseded/invalid procedures

        Returns:
            List of Procedure entities whose steps match (filtered by lifecycle by default)
        """
        try:
            # First find matching steps
            step_query_lower = step_query.lower()
            result = self.conn.execute(f"""
                MATCH (p:Project {{name: $project_name}})-[:HAS_ENTITY]->(e:Entity)
                WHERE e.deleted_at IS NULL
                  AND e.labels CONTAINS '"ProcedureStep"'
                  AND (lower(e.attributes) CONTAINS $query
                       OR lower(e.summary) CONTAINS $query)
                RETURN DISTINCT e.attributes
                LIMIT 100
            """, {
                "project_name": project_name,
                "query": step_query_lower,
            })

            # Extract procedure names from matching steps
            procedure_names = set()
            while result.has_next():
                attrs_str = result.get_next()[0]
                if attrs_str:
                    try:
                        attrs = json.loads(attrs_str) if isinstance(attrs_str, str) else attrs_str
                        if "procedure_name" in attrs:
                            procedure_names.add(attrs["procedure_name"])
                    except:
                        pass

            # Get the procedures (fetch more to account for lifecycle filtering)
            fetch_limit = limit * 3 if not include_all_lifecycle else limit
            procedures = []
            for proc_name in list(procedure_names)[:fetch_limit]:
                proc_results = self.search_entities(
                    project_name=project_name,
                    query=proc_name,
                    labels=["Procedure"],
                    limit=1,
                    track_access=False
                )
                if proc_results:
                    procedures.append(proc_results[0])

            # Apply lifecycle filtering
            filtered = self._filter_by_lifecycle(procedures, include_all_lifecycle)

            return filtered[:limit]

        except Exception as e:
            print(f"Error searching procedures by step: {e}")
            return []

    # =========================================================================
    # Phase 2: Execution Telemetry Methods
    # These create operational records, NOT semantic/extracted entities
    # =========================================================================

    def create_procedure_run(
        self,
        procedure_uuid: str,
        project_name: str,
        agent: str,
        invocation_context: str,
        model: str = "",
        invocation_source: Optional[str] = None,
        started_at: Optional[str] = None,
        status: str = "in_progress",
        result_note: Optional[str] = None,
    ) -> Optional[str]:
        """
        Create a ProcedureRun record (execution telemetry).

        This is NOT an Entity - it's operational data tracking procedure execution.
        No extraction provenance required.

        Args:
            procedure_uuid: UUID of the Procedure entity being run
            project_name: Project name
            agent: Agent/user who initiated the run
            invocation_context: Required. One of: procedure_md, manual, script, conversation, api
            model: Model name (if applicable)
            invocation_source: Optional. Conversation UUID, script path, etc.
            started_at: ISO timestamp when run started (defaults to now)
            status: Run status (in_progress, success, failure, cancelled)
            result_note: Optional note about the run result

        Returns:
            UUID of the created ProcedureRun, or None on error
        """
        try:
            # Validate invocation_context
            if invocation_context not in self.VALID_INVOCATION_CONTEXTS:
                print(f"Error: Invalid invocation_context '{invocation_context}'. Must be one of: {self.VALID_INVOCATION_CONTEXTS}")
                return None

            # Validate that procedure_uuid points to a Procedure entity AND belongs to the specified project
            result = self.conn.execute("""
                MATCH (e:Entity {uuid: $uuid})
                WHERE e.labels CONTAINS '"Procedure"'
                RETURN e.uuid, e.group_id
            """, {"uuid": procedure_uuid})

            if not result.has_next():
                print(f"Error: {procedure_uuid} is not a valid Procedure entity")
                return None

            row = result.get_next()
            proc_project = row[1]
            if proc_project != project_name:
                print(f"Error: Procedure {procedure_uuid} belongs to project '{proc_project}', not '{project_name}'")
                return None

            run_uuid = f"run-{uuid4().hex[:12]}"
            now = datetime.now()
            started = started_at or now.isoformat()

            self.conn.execute("""
                CREATE (pr:ProcedureRun {
                    uuid: $uuid,
                    procedure_uuid: $procedure_uuid,
                    project_name: $project_name,
                    created_by_agent: $agent,
                    created_by_model: $model,
                    invocation_context: $invocation_context,
                    invocation_source: $invocation_source,
                    run_batch_uuid: NULL,
                    run_hash: NULL,
                    started_at: timestamp($started_at),
                    started_at_str: $started_at_str,
                    finished_at: NULL,
                    finished_at_str: NULL,
                    status: $status,
                    result_note: $result_note,
                    created_at: timestamp($created_at)
                })
            """, {
                "uuid": run_uuid,
                "procedure_uuid": procedure_uuid,
                "project_name": project_name,
                "agent": agent,
                "model": model,
                "invocation_context": invocation_context,
                "invocation_source": invocation_source,
                "started_at": started,
                "started_at_str": started,
                "status": status,
                "result_note": result_note,
                "created_at": now.isoformat(),
            })

            # Create RUNS relationship to the Procedure
            rel_uuid = f"runs-{uuid4().hex[:12]}"
            self.conn.execute("""
                MATCH (pr:ProcedureRun {uuid: $run_uuid}), (e:Entity {uuid: $proc_uuid})
                CREATE (pr)-[:RUNS {uuid: $rel_uuid, created_at: timestamp($created_at)}]->(e)
            """, {
                "run_uuid": run_uuid,
                "proc_uuid": procedure_uuid,
                "rel_uuid": rel_uuid,
                "created_at": now.isoformat(),
            })

            return run_uuid

        except Exception as e:
            print(f"Error creating ProcedureRun: {e}")
            return None

    def create_step_run(
        self,
        procedure_run_uuid: str,
        procedure_step_uuid: str,
        step_number: int,
        started_at: Optional[str] = None,
        status: str = "in_progress",
        result_note: Optional[str] = None,
    ) -> Optional[str]:
        """
        Create a StepRun record (execution telemetry).

        This is NOT an Entity - it's operational data tracking step execution.
        No extraction provenance required.

        Args:
            procedure_run_uuid: UUID of the parent ProcedureRun
            procedure_step_uuid: UUID of the ProcedureStep entity being run
            step_number: Step number within the procedure
            started_at: ISO timestamp when step started (defaults to now)
            status: Step status (in_progress, success, failure, skipped)
            result_note: Optional note about the step result

        Returns:
            UUID of the created StepRun, or None on error
        """
        try:
            # Validate that procedure_run_uuid is a valid ProcedureRun and get its procedure_uuid
            result = self.conn.execute("""
                MATCH (pr:ProcedureRun {uuid: $uuid})
                RETURN pr.uuid, pr.procedure_uuid
            """, {"uuid": procedure_run_uuid})

            if not result.has_next():
                print(f"Error: {procedure_run_uuid} is not a valid ProcedureRun")
                return None

            row = result.get_next()
            run_procedure_uuid = row[1]

            # Validate that procedure_step_uuid is a valid ProcedureStep
            result = self.conn.execute("""
                MATCH (e:Entity {uuid: $uuid})
                WHERE e.labels CONTAINS '"ProcedureStep"'
                RETURN e.uuid
            """, {"uuid": procedure_step_uuid})

            if not result.has_next():
                print(f"Error: {procedure_step_uuid} is not a valid ProcedureStep entity")
                return None

            # Verify step belongs to the same procedure via CONTAINS relationship (strongest check)
            result = self.conn.execute("""
                MATCH (proc:Entity {uuid: $proc_uuid})-[r:RELATES_TO]->(step:Entity {uuid: $step_uuid})
                WHERE r.name = 'CONTAINS'
                RETURN proc.uuid
            """, {
                "proc_uuid": run_procedure_uuid,
                "step_uuid": procedure_step_uuid
            })

            if not result.has_next():
                # Fallback: check procedure_name attribute if CONTAINS relationship doesn't exist yet
                result = self.conn.execute("""
                    MATCH (step:Entity {uuid: $step_uuid}), (proc:Entity {uuid: $proc_uuid})
                    RETURN step.attributes, proc.name
                """, {
                    "step_uuid": procedure_step_uuid,
                    "proc_uuid": run_procedure_uuid
                })

                if result.has_next():
                    row = result.get_next()
                    step_attrs = row[0]
                    proc_name = row[1]

                    if isinstance(step_attrs, str):
                        try:
                            step_attrs = json.loads(step_attrs)
                        except:
                            step_attrs = {}

                    step_procedure_name = step_attrs.get("procedure_name", "")
                    if step_procedure_name and step_procedure_name != proc_name:
                        print(f"Error: ProcedureStep '{procedure_step_uuid}' belongs to procedure '{step_procedure_name}', not '{proc_name}'")
                        return None

            step_run_uuid = f"steprun-{uuid4().hex[:12]}"
            now = datetime.now()
            started = started_at or now.isoformat()

            self.conn.execute("""
                CREATE (sr:StepRun {
                    uuid: $uuid,
                    procedure_run_uuid: $procedure_run_uuid,
                    procedure_step_uuid: $procedure_step_uuid,
                    step_number: $step_number,
                    started_at: timestamp($started_at),
                    started_at_str: $started_at_str,
                    finished_at: NULL,
                    finished_at_str: NULL,
                    status: $status,
                    result_note: $result_note,
                    step_hash: NULL,
                    created_at: timestamp($created_at)
                })
            """, {
                "uuid": step_run_uuid,
                "procedure_run_uuid": procedure_run_uuid,
                "procedure_step_uuid": procedure_step_uuid,
                "step_number": step_number,
                "started_at": started,
                "started_at_str": started,
                "status": status,
                "result_note": result_note,
                "created_at": now.isoformat(),
            })

            # Create HAS_STEP_RUN relationship from ProcedureRun
            rel_uuid1 = f"hassteprun-{uuid4().hex[:12]}"
            self.conn.execute("""
                MATCH (pr:ProcedureRun {uuid: $run_uuid}), (sr:StepRun {uuid: $step_run_uuid})
                CREATE (pr)-[:HAS_STEP_RUN {uuid: $rel_uuid, created_at: timestamp($created_at)}]->(sr)
            """, {
                "run_uuid": procedure_run_uuid,
                "step_run_uuid": step_run_uuid,
                "rel_uuid": rel_uuid1,
                "created_at": now.isoformat(),
            })

            # Create RUNS_STEP relationship to the ProcedureStep
            rel_uuid2 = f"runsstep-{uuid4().hex[:12]}"
            self.conn.execute("""
                MATCH (sr:StepRun {uuid: $step_run_uuid}), (e:Entity {uuid: $step_uuid})
                CREATE (sr)-[:RUNS_STEP {uuid: $rel_uuid, created_at: timestamp($created_at)}]->(e)
            """, {
                "step_run_uuid": step_run_uuid,
                "step_uuid": procedure_step_uuid,
                "rel_uuid": rel_uuid2,
                "created_at": now.isoformat(),
            })

            return step_run_uuid

        except Exception as e:
            print(f"Error creating StepRun: {e}")
            return None

    def _compute_run_hash(self, run_data: Dict[str, Any], step_hashes: List[str]) -> str:
        """Compute canonical SHA-256 hash for a ProcedureRun."""
        payload = {
            "created_by_agent": run_data.get("created_by_agent") or "",
            "created_by_model": run_data.get("created_by_model") or "",
            "finished_at": run_data.get("finished_at") or "",
            "invocation_context": run_data.get("invocation_context") or "",
            "invocation_source": run_data.get("invocation_source") or "",
            "procedure_uuid": run_data.get("procedure_uuid") or "",
            "project_name": run_data.get("project_name") or "",
            "result_note": run_data.get("result_note") or "",
            "started_at": run_data.get("started_at") or "",
            "status": run_data.get("status") or "",
            "step_hashes": step_hashes,  # Already ordered by step_number
            "uuid": run_data.get("uuid") or "",
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical.encode('utf-8')).hexdigest()

    def complete_procedure_run(
        self,
        run_uuid: str,
        status: str = "success",
        result_note: Optional[str] = None,
    ) -> bool:
        """
        Finalize a ProcedureRun (terminalization operation).

        This is NOT a casual status update. It:
        - Verifies all StepRuns are finalized
        - Sets final status and finished_at
        - Computes run_hash (includes step_hashes) for audit integrity
        - After this, the run is considered sealed

        Args:
            run_uuid: UUID of the ProcedureRun
            status: Final status (success, failure, cancelled)
            result_note: Optional note about the result

        Returns:
            True if finalized, False on error
        """
        try:
            # Get the ProcedureRun with all fields needed for hash
            result = self.conn.execute("""
                MATCH (pr:ProcedureRun {uuid: $uuid})
                RETURN pr.uuid, pr.procedure_uuid, pr.project_name,
                       pr.created_by_agent, pr.created_by_model,
                       pr.invocation_context, pr.invocation_source,
                       pr.started_at_str, pr.run_hash
            """, {"uuid": run_uuid})

            if not result.has_next():
                print(f"Error: ProcedureRun {run_uuid} does not exist")
                return False

            row = result.get_next()
            existing_hash = row[8]

            # Reject if already finalized
            if existing_hash:
                print(f"Error: ProcedureRun {run_uuid} is already finalized (run_hash exists)")
                return False

            # Get all StepRuns and verify they're all finalized
            steps_result = self.conn.execute("""
                MATCH (sr:StepRun {procedure_run_uuid: $run_uuid})
                RETURN sr.uuid, sr.step_number, sr.status, sr.step_hash
                ORDER BY sr.step_number
            """, {"run_uuid": run_uuid})

            step_hashes = []
            while steps_result.has_next():
                step_row = steps_result.get_next()
                step_status = step_row[2]
                step_hash = step_row[3]

                if step_status == "in_progress" or not step_hash:
                    print(f"Error: Cannot finalize ProcedureRun {run_uuid} - StepRun {step_row[0]} is not finalized")
                    return False

                step_hashes.append(step_hash)

            now = datetime.now()
            finished_at = now.isoformat()

            # Compute run_hash with final state
            run_data = {
                "uuid": row[0],
                "procedure_uuid": row[1],
                "project_name": row[2],
                "created_by_agent": row[3],
                "created_by_model": row[4],
                "invocation_context": row[5],
                "invocation_source": row[6],
                "started_at": row[7],
                "finished_at": finished_at,
                "status": status,
                "result_note": result_note or "",
            }
            run_hash = self._compute_run_hash(run_data, step_hashes)

            self.conn.execute("""
                MATCH (pr:ProcedureRun {uuid: $uuid})
                SET pr.finished_at = timestamp($finished_at),
                    pr.finished_at_str = $finished_at_str,
                    pr.status = $status,
                    pr.result_note = $result_note,
                    pr.run_hash = $run_hash
            """, {
                "uuid": run_uuid,
                "finished_at": finished_at,
                "finished_at_str": finished_at,
                "status": status,
                "result_note": result_note,
                "run_hash": run_hash,
            })
            return True
        except Exception as e:
            print(f"Error finalizing ProcedureRun: {e}")
            return False

    def _compute_step_hash(self, step_data: Dict[str, Any]) -> str:
        """Compute canonical SHA-256 hash for a StepRun."""
        payload = {
            "finished_at": step_data.get("finished_at") or "",
            "procedure_run_uuid": step_data.get("procedure_run_uuid") or "",
            "procedure_step_uuid": step_data.get("procedure_step_uuid") or "",
            "result_note": step_data.get("result_note") or "",
            "started_at": step_data.get("started_at") or "",
            "status": step_data.get("status") or "",
            "step_number": step_data.get("step_number") or 0,
            "uuid": step_data.get("uuid") or "",
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical.encode('utf-8')).hexdigest()

    def complete_step_run(
        self,
        step_run_uuid: str,
        status: str = "success",
        result_note: Optional[str] = None,
    ) -> bool:
        """
        Finalize a StepRun (terminalization operation).

        This is NOT a casual status update. It:
        - Sets final status and finished_at
        - Computes step_hash for audit integrity
        - After this, the step is considered sealed

        Args:
            step_run_uuid: UUID of the StepRun
            status: Final status (success, failure, skipped)
            result_note: Optional note about the result

        Returns:
            True if finalized, False on error
        """
        try:
            # Get the StepRun with all fields needed for hash
            result = self.conn.execute("""
                MATCH (sr:StepRun {uuid: $uuid})
                RETURN sr.uuid, sr.procedure_run_uuid, sr.procedure_step_uuid,
                       sr.step_number, sr.started_at_str, sr.step_hash
            """, {"uuid": step_run_uuid})

            if not result.has_next():
                print(f"Error: StepRun {step_run_uuid} does not exist")
                return False

            row = result.get_next()
            existing_hash = row[5]

            # Reject if already finalized
            if existing_hash:
                print(f"Error: StepRun {step_run_uuid} is already finalized (step_hash exists)")
                return False

            now = datetime.now()
            finished_at = now.isoformat()

            # Compute step_hash with final state
            step_data = {
                "uuid": row[0],
                "procedure_run_uuid": row[1],
                "procedure_step_uuid": row[2],
                "step_number": row[3],
                "started_at": row[4],
                "finished_at": finished_at,
                "status": status,
                "result_note": result_note or "",
            }
            step_hash = self._compute_step_hash(step_data)

            self.conn.execute("""
                MATCH (sr:StepRun {uuid: $uuid})
                SET sr.finished_at = timestamp($finished_at),
                    sr.finished_at_str = $finished_at_str,
                    sr.status = $status,
                    sr.result_note = $result_note,
                    sr.step_hash = $step_hash
            """, {
                "uuid": step_run_uuid,
                "finished_at": finished_at,
                "finished_at_str": finished_at,
                "status": status,
                "result_note": result_note,
                "step_hash": step_hash,
            })
            return True
        except Exception as e:
            print(f"Error finalizing StepRun: {e}")
            return False

    def get_procedure_run(self, run_uuid: str) -> Optional[Dict[str, Any]]:
        """Get a ProcedureRun by UUID."""
        try:
            result = self.conn.execute("""
                MATCH (pr:ProcedureRun {uuid: $uuid})
                RETURN pr.uuid, pr.procedure_uuid, pr.project_name,
                       pr.created_by_agent, pr.created_by_model,
                       pr.invocation_context, pr.invocation_source,
                       pr.run_batch_uuid, pr.run_hash,
                       pr.started_at_str, pr.finished_at_str,
                       pr.status, pr.result_note, pr.created_at
            """, {"uuid": run_uuid})

            if result.has_next():
                row = result.get_next()
                return {
                    "uuid": row[0],
                    "procedure_uuid": row[1],
                    "project_name": row[2],
                    "created_by_agent": row[3],
                    "created_by_model": row[4],
                    "invocation_context": row[5],
                    "invocation_source": row[6],
                    "run_batch_uuid": row[7],
                    "run_hash": row[8],
                    "started_at": row[9],
                    "finished_at": row[10],
                    "status": row[11],
                    "result_note": row[12],
                    "created_at": str(row[13]) if row[13] else None,
                }
            return None
        except Exception as e:
            print(f"Error getting ProcedureRun: {e}")
            return None

    def get_step_run(self, step_run_uuid: str) -> Optional[Dict[str, Any]]:
        """Get a StepRun by UUID."""
        try:
            result = self.conn.execute("""
                MATCH (sr:StepRun {uuid: $uuid})
                RETURN sr.uuid, sr.procedure_run_uuid, sr.procedure_step_uuid,
                       sr.step_number, sr.started_at_str, sr.finished_at_str,
                       sr.status, sr.result_note, sr.step_hash, sr.created_at
            """, {"uuid": step_run_uuid})

            if result.has_next():
                row = result.get_next()
                return {
                    "uuid": row[0],
                    "procedure_run_uuid": row[1],
                    "procedure_step_uuid": row[2],
                    "step_number": row[3],
                    "started_at": row[4],
                    "finished_at": row[5],
                    "status": row[6],
                    "result_note": row[7],
                    "step_hash": row[8],
                    "created_at": str(row[9]) if row[9] else None,
                }
            return None
        except Exception as e:
            print(f"Error getting StepRun: {e}")
            return None

    # =========================================================================
    # RunBatch Methods - Execution Audit Batching
    # =========================================================================

    def _compute_batch_hash(self, batch_data: Dict[str, Any]) -> str:
        """Compute canonical SHA-256 hash for a RunBatch."""
        payload = {
            "batch_index": batch_data.get("batch_index") or 0,
            "batch_uuid": batch_data.get("batch_uuid") or "",
            "created_by_agent": batch_data.get("created_by_agent") or "",
            "created_by_model": batch_data.get("created_by_model") or "",
            "previous_batch_hash": batch_data.get("previous_batch_hash") or "",
            "project_name": batch_data.get("project_name") or "",
            "run_hashes": batch_data.get("run_hashes") or [],
            "run_uuids": batch_data.get("run_uuids") or [],
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical.encode('utf-8')).hexdigest()

    def create_run_batch(
        self,
        project_name: str,
        run_uuids: List[str],
        agent: str,
        model: str = "",
    ) -> Optional[str]:
        """
        Create a RunBatch to group completed ProcedureRuns for audit.

        This:
        - Validates all runs are finalized (run_hash is not NULL)
        - Validates no run is already batched
        - Computes batch_hash covering all run_hashes
        - Chains to previous batch via previous_batch_hash
        - Sets run_batch_uuid on all included runs

        Args:
            project_name: Project name
            run_uuids: List of ProcedureRun UUIDs to include
            agent: Agent creating the batch
            model: Model name (if applicable)

        Returns:
            batch_uuid if successful, None on error
        """
        try:
            if not run_uuids:
                print("Error: Cannot create empty RunBatch")
                return None

            # Collect run data and validate
            run_pairs = []  # List of (run_uuid, run_hash)
            for run_uuid in run_uuids:
                result = self.conn.execute("""
                    MATCH (pr:ProcedureRun {uuid: $uuid, project_name: $project_name})
                    RETURN pr.uuid, pr.run_hash, pr.run_batch_uuid
                """, {"uuid": run_uuid, "project_name": project_name})

                if not result.has_next():
                    print(f"Error: ProcedureRun {run_uuid} does not exist in project {project_name}")
                    return None

                row = result.get_next()
                run_hash = row[1]
                existing_batch = row[2]

                if not run_hash:
                    print(f"Error: ProcedureRun {run_uuid} is not finalized (run_hash is NULL)")
                    return None

                if existing_batch:
                    print(f"Error: ProcedureRun {run_uuid} is already in batch {existing_batch}")
                    return None

                run_pairs.append((run_uuid, run_hash))

            # Sort pairs by run_uuid for deterministic ordering
            run_pairs.sort(key=lambda x: x[0])
            sorted_run_uuids = [p[0] for p in run_pairs]
            sorted_run_hashes = [p[1] for p in run_pairs]

            # Get previous batch for chaining
            prev_batch = self.get_latest_run_batch(project_name)
            previous_batch_hash = prev_batch["batch_hash"] if prev_batch else ""
            batch_index = (prev_batch["batch_index"] + 1) if prev_batch else 1

            batch_uuid = f"runbatch-{uuid4().hex[:12]}"
            now = datetime.now()

            # Compute batch_hash
            batch_data = {
                "batch_uuid": batch_uuid,
                "project_name": project_name,
                "created_by_agent": agent,
                "created_by_model": model,
                "run_uuids": sorted_run_uuids,
                "run_hashes": sorted_run_hashes,
                "previous_batch_hash": previous_batch_hash,
                "batch_index": batch_index,
            }
            batch_hash = self._compute_batch_hash(batch_data)

            # Create the batch
            self.conn.execute("""
                CREATE (rb:RunBatch {
                    batch_uuid: $batch_uuid,
                    project_name: $project_name,
                    created_by_agent: $agent,
                    created_by_model: $model,
                    run_uuids: $run_uuids,
                    run_hashes: $run_hashes,
                    batch_hash: $batch_hash,
                    previous_batch_hash: $previous_batch_hash,
                    batch_index: $batch_index,
                    timestamp_proof: NULL,
                    created_at: timestamp($created_at),
                    created_at_str: $created_at_str
                })
            """, {
                "batch_uuid": batch_uuid,
                "project_name": project_name,
                "agent": agent,
                "model": model,
                "run_uuids": json.dumps(sorted_run_uuids),
                "run_hashes": json.dumps(sorted_run_hashes),
                "batch_hash": batch_hash,
                "previous_batch_hash": previous_batch_hash,
                "batch_index": batch_index,
                "created_at": now.isoformat(),
                "created_at_str": now.isoformat(),
            })

            # Update all runs with the batch UUID
            for run_uuid in sorted_run_uuids:
                self.conn.execute("""
                    MATCH (pr:ProcedureRun {uuid: $uuid})
                    SET pr.run_batch_uuid = $batch_uuid
                """, {"uuid": run_uuid, "batch_uuid": batch_uuid})

            return batch_uuid

        except Exception as e:
            print(f"Error creating RunBatch: {e}")
            return None

    def get_run_batch(self, batch_uuid: str) -> Optional[Dict[str, Any]]:
        """Get a RunBatch by UUID."""
        try:
            result = self.conn.execute("""
                MATCH (rb:RunBatch {batch_uuid: $batch_uuid})
                RETURN rb.batch_uuid, rb.project_name, rb.created_by_agent,
                       rb.created_by_model, rb.run_uuids, rb.run_hashes,
                       rb.batch_hash, rb.previous_batch_hash, rb.batch_index,
                       rb.timestamp_proof, rb.created_at_str
            """, {"batch_uuid": batch_uuid})

            if result.has_next():
                row = result.get_next()
                return {
                    "batch_uuid": row[0],
                    "project_name": row[1],
                    "created_by_agent": row[2],
                    "created_by_model": row[3],
                    "run_uuids": json.loads(row[4]) if row[4] else [],
                    "run_hashes": json.loads(row[5]) if row[5] else [],
                    "batch_hash": row[6],
                    "previous_batch_hash": row[7],
                    "batch_index": row[8],
                    "timestamp_proof": row[9],
                    "created_at": row[10],
                }
            return None
        except Exception as e:
            print(f"Error getting RunBatch: {e}")
            return None

    def get_latest_run_batch(self, project_name: str) -> Optional[Dict[str, Any]]:
        """Get the most recent RunBatch for a project (for chaining)."""
        try:
            result = self.conn.execute("""
                MATCH (rb:RunBatch {project_name: $project_name})
                RETURN rb.batch_uuid, rb.project_name, rb.created_by_agent,
                       rb.created_by_model, rb.run_uuids, rb.run_hashes,
                       rb.batch_hash, rb.previous_batch_hash, rb.batch_index,
                       rb.timestamp_proof, rb.created_at_str
                ORDER BY rb.batch_index DESC
                LIMIT 1
            """, {"project_name": project_name})

            if result.has_next():
                row = result.get_next()
                return {
                    "batch_uuid": row[0],
                    "project_name": row[1],
                    "created_by_agent": row[2],
                    "created_by_model": row[3],
                    "run_uuids": json.loads(row[4]) if row[4] else [],
                    "run_hashes": json.loads(row[5]) if row[5] else [],
                    "batch_hash": row[6],
                    "previous_batch_hash": row[7],
                    "batch_index": row[8],
                    "timestamp_proof": row[9],
                    "created_at": row[10],
                }
            return None
        except Exception as e:
            print(f"Error getting latest RunBatch: {e}")
            return None

    def search_facts(
        self,
        project_name: str,
        query: Optional[str] = None,
        relationship_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Search for facts (relationships) in a project.

        Args:
            project_name: Project to search in
            query: Optional text to search in fact
            relationship_type: Optional relationship type filter
            limit: Maximum number of results

        Returns:
            List of fact dictionaries
        """
        try:
            cypher = """
                MATCH (p:Project {name: $project_name})-[:HAS_ENTITY]->(source:Entity)
                MATCH (source)-[r:RELATES_TO]->(target:Entity)
                WHERE r.expired_at IS NULL
            """
            params = {"project_name": project_name}

            # Add text search if provided
            if query:
                cypher += """
                    AND lower(r.fact) CONTAINS $query
                """
                params["query"] = query.lower()

            # Add relationship type filter if provided
            if relationship_type:
                cypher += """
                    AND r.name = $relationship_type
                """
                params["relationship_type"] = relationship_type

            cypher += f"""
                RETURN source.name, r.name, r.fact, target.name, r.uuid,
                       r.valid_at, r.derivation_version, r.episodes
                LIMIT {limit}
            """

            result = self.conn.execute(cypher, params)

            facts = []
            while result.has_next():
                row = result.get_next()
                facts.append({
                    "source_name": row[0],
                    "relationship_type": row[1],
                    "fact": row[2],
                    "target_name": row[3],
                    "uuid": row[4],
                    "valid_at": str(row[5]),
                    "derivation_version": row[6],
                    "episodes": json.loads(row[7]) if row[7] else []
                })

            return facts
        except Exception as e:
            print(f"Error searching facts: {e}")
            return []

    def get_entities_by_label(
        self,
        project_name: str,
        label: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get all entities with a specific label.

        Args:
            project_name: Project to search in
            label: Label to filter by
            limit: Maximum number of results

        Returns:
            List of entity dictionaries
        """
        return self.search_entities(project_name, labels=[label], limit=limit)

    def get_all_entities(
        self,
        project_name: str,
        limit: int = 10000,
        track_access: bool = False,
        priority_order: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get all entities in a project.

        Args:
            project_name: Project name
            limit: Maximum number of results (default: 10000)
            track_access: Whether to track access (default: False for bulk operations)
            priority_order: Whether to use priority ordering (default: False for bulk operations)

        Returns:
            List of entity dictionaries
        """
        return self.search_entities(project_name, limit=limit, track_access=track_access, priority_order=priority_order)

    def get_all_facts(
        self,
        project_name: str,
        limit: int = 10000
    ) -> List[Dict[str, Any]]:
        """
        Get all facts/relationships in a project.

        Args:
            project_name: Project name
            limit: Maximum number of results (default: 10000)

        Returns:
            List of fact dictionaries
        """
        try:
            result = self.conn.execute("""
                MATCH (p:Project {name: $project_name})-[:HAS_ENTITY]->(e1:Entity)-[r:RELATES_TO]->(e2:Entity)
                WHERE e1.deleted_at IS NULL AND e2.deleted_at IS NULL
                RETURN e1.name, r.name, e2.name, r.fact, r.uuid, r.created_at
                LIMIT $limit
            """, {
                "project_name": project_name,
                "limit": limit,
            })

            facts = []
            while result.has_next():
                row = result.get_next()
                facts.append({
                    "source_entity": row[0],
                    "relationship_type": row[1],
                    "target_entity": row[2],
                    "fact": row[3],
                    "uuid": row[4],
                    "created_at": row[5]
                })

            return facts

        except Exception as e:
            print(f"Error getting all facts: {e}")
            return []

    def resolve_entity_name(
        self,
        name: str,
        project_name: str = None,
        fail_on_ambiguous: bool = True
    ) -> Optional[str]:
        """
        Resolve entity name to canonical UUID.
        Checks both Entity nodes and Alias nodes.

        Args:
            name: Entity name (could be canonical or alias)
            project_name: If provided, scope lookup to this project only
            fail_on_ambiguous: If True, raise error on multiple matches (default: True)

        Returns:
            UUID of canonical entity, or None if not found

        Raises:
            ValueError: If multiple entities match and fail_on_ambiguous=True
        """
        try:
            # Try direct entity match first
            if project_name:
                # Project-scoped lookup (no LIMIT - need to detect ambiguity)
                result = self.conn.execute("""
                    MATCH (p:Project {name: $project})-[:HAS_ENTITY]->(e:Entity)
                    WHERE e.name = $name AND e.deleted_at IS NULL
                    RETURN e.uuid
                """, {"name": name, "project": project_name})
            else:
                # Global lookup (legacy, no LIMIT to detect ambiguity)
                result = self.conn.execute("""
                    MATCH (e:Entity)
                    WHERE e.name = $name AND e.deleted_at IS NULL
                    RETURN e.uuid
                """, {"name": name})

            uuids = []
            while result.has_next():
                uuids.append(result.get_next()[0])

            if len(uuids) > 1:
                if fail_on_ambiguous:
                    scope = f"project '{project_name}'" if project_name else "global scope"
                    raise ValueError(
                        f"Ambiguous: {len(uuids)} entities named '{name}' in {scope}. "
                        f"Use UUID instead: {uuids}"
                    )
                # If not failing, return first (legacy behavior, but logged)
                print(f"[WARNING] Ambiguous entity name '{name}': {len(uuids)} matches, using first")

            if uuids:
                return uuids[0]

            # Try alias match (also scoped if project provided)
            # ALSO apply ambiguity detection to aliases
            if project_name:
                result = self.conn.execute("""
                    MATCH (a:Alias)
                    WHERE a.name = $name
                    MATCH (p:Project {name: $project})-[:HAS_ENTITY]->(e:Entity {uuid: a.canonical_uuid})
                    RETURN a.canonical_uuid
                """, {"name": name, "project": project_name})
            else:
                result = self.conn.execute("""
                    MATCH (a:Alias)
                    WHERE a.name = $name
                    RETURN a.canonical_uuid
                """, {"name": name})

            alias_uuids = []
            while result.has_next():
                alias_uuids.append(result.get_next()[0])

            # Apply same ambiguity check to alias matches
            if len(alias_uuids) > 1:
                if fail_on_ambiguous:
                    scope = f"project '{project_name}'" if project_name else "global scope"
                    raise ValueError(
                        f"Ambiguous: {len(alias_uuids)} aliases named '{name}' in {scope}. "
                        f"Use UUID instead: {alias_uuids}"
                    )
                print(f"[WARNING] Ambiguous alias '{name}': {len(alias_uuids)} matches, using first")

            return alias_uuids[0] if alias_uuids else None

        except ValueError:
            raise  # Re-raise ambiguity errors
        except Exception as e:
            print(f"Error resolving entity name: {e}")
            return None

    def create_alias(
        self,
        name: str,
        canonical_uuid: str,
        source_interaction: str = None,
        source_hash: str = None,
        extraction_version: str = None,
        extraction_commit: str = None,
        timestamp_proof: str = None
    ) -> bool:
        """
        Create an alias that points to a canonical entity.

        With cryptographic proof linking to SQL hash chain.

        Args:
            name: Alias name
            canonical_uuid: UUID of canonical entity
            source_interaction: UUID of interaction where alias was detected
            source_hash: Hash of source interaction (links to SQL chain)
            extraction_version: Version of extraction that created alias
            extraction_commit: Commit hash of extraction rules

        Returns:
            True if successful, False otherwise
        """
        try:
            created_at = datetime.now().isoformat()

            # Calculate alias proof if we have source_hash
            alias_proof = None
            if source_hash:
                alias_proof = self._calculate_alias_proof(
                    name,
                    canonical_uuid,
                    source_hash,
                    created_at
                )

            self.conn.execute("""
                CREATE (a:Alias {
                    name: $name,
                    canonical_uuid: $canonical_uuid,
                    created_at: timestamp($created_at),
                    created_at_str: $created_at_str,
                    source_interaction: $source_interaction,
                    source_hash: $source_hash,
                    extraction_version: $extraction_version,
                    extraction_commit: $extraction_commit,
                    alias_proof: $alias_proof,
                    timestamp_proof: $timestamp_proof
                })
            """, {
                "name": name,
                "canonical_uuid": canonical_uuid,
                "created_at": created_at,
                "created_at_str": created_at,
                "source_interaction": source_interaction,
                "source_hash": source_hash,
                "extraction_version": extraction_version,
                "extraction_commit": extraction_commit,
                "alias_proof": alias_proof,
                "timestamp_proof": timestamp_proof,
            })
            return True

        except Exception as e:
            print(f"Error creating alias: {e}")
            return False

    def verify_alias_proof(self, alias_name: str) -> bool:
        """
        Verify the cryptographic proof of an alias.

        Args:
            alias_name: Name of the alias to verify

        Returns:
            True if proof is valid, False otherwise
        """
        try:
            # Get alias data
            result = self.conn.execute("""
                MATCH (a:Alias {name: $alias_name})
                RETURN a.canonical_uuid, a.source_hash, a.created_at_str, a.alias_proof
            """, {
                "alias_name": alias_name,
            })

            if not result.has_next():
                print(f"Alias not found: {alias_name}")
                return False

            row = result.get_next()
            canonical_uuid = row[0]
            source_hash = row[1]
            created_at = row[2]  # Use created_at_str (already a string)
            stored_proof = row[3]

            # If no proof stored, can't verify
            if not stored_proof:
                print(f"No proof stored for alias: {alias_name}")
                return False

            # Recalculate proof
            calculated_proof = self._calculate_alias_proof(
                alias_name,
                canonical_uuid,
                source_hash,
                created_at
            )

            # Compare
            if calculated_proof == stored_proof:
                return True
            else:
                print(f"Proof mismatch for alias: {alias_name}")
                print(f"  Stored:     {stored_proof}")
                print(f"  Calculated: {calculated_proof}")
                return False

        except Exception as e:
            print(f"Error verifying alias proof: {e}")
            return False

    def get_entity_aliases(self, canonical_uuid: str) -> List[str]:
        """
        Get all aliases for a canonical entity.

        Args:
            canonical_uuid: UUID of canonical entity

        Returns:
            List of alias names
        """
        try:
            result = self.conn.execute("""
                MATCH (a:Alias)
                WHERE a.canonical_uuid = $canonical_uuid
                RETURN a.name
            """, {
                "canonical_uuid": canonical_uuid,
            })

            aliases = []
            while result.has_next():
                aliases.append(result.get_next()[0])

            return aliases

        except Exception as e:
            print(f"Error getting aliases: {e}")
            return []

    def get_entity_by_name(
        self,
        project_name: str,
        name: str,
        fail_on_ambiguous: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Get entity by exact name match.
        Now supports alias resolution and ambiguity detection!

        Args:
            project_name: Project name
            name: Entity name (canonical or alias)
            fail_on_ambiguous: If True, raise error on multiple matches (default: True)

        Returns:
            Entity dictionary or None

        Raises:
            ValueError: If multiple entities match and fail_on_ambiguous=True
        """
        try:
            # First resolve name to UUID (handles aliases, now project-scoped)
            uuid = self.resolve_entity_name(
                name,
                project_name=project_name,
                fail_on_ambiguous=fail_on_ambiguous
            )
            if not uuid:
                return None

            # Then get entity by UUID
            result = self.conn.execute(f"""
                MATCH (p:Project {{name: $project_name}})-[:HAS_ENTITY]->(e:Entity)
                WHERE e.uuid = $entity_uuid AND e.deleted_at IS NULL
                RETURN {self._entity_return_clause("e")}
                LIMIT 1
            """, {
                "project_name": project_name,
                "entity_uuid": uuid,
            })

            rows = []
            while result.has_next():
                rows.append(result.get_next())

            if not rows:
                return None

            return self._entity_from_row(rows[0])
        except ValueError:
            raise  # Re-raise ambiguity errors
        except Exception as e:
            print(f"Error getting entity by name: {e}")
            return None


    def get_related_entities(
        self,
        entity_uuid: str,
        direction: str = "both",
        relationship_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get all entities connected to a given entity via relationships.

        This returns the FULL ENTITY OBJECTS (not just facts) for all entities
        that are connected to the specified entity through relationships.

        Args:
            entity_uuid: UUID of the entity to find connections for
            direction: Which relationships to follow:
                - "outgoing": Only entities this entity points TO
                - "incoming": Only entities that point TO this entity
                - "both": All connected entities (default)
            relationship_type: Optional filter by relationship type (e.g., "LOCATED_AT")
            limit: Maximum number of entities to return

        Returns:
            List of entity dictionaries with additional relationship info:
            [
                {
                    "uuid": "entity-abc123",
                    "name": "Entity Name",
                    "summary": "...",
                    "labels": [...],
                    "direction": "outgoing",  # How this entity is connected
                    "relationship_type": "LOCATED_AT",
                    "relationship_uuid": "rel-xyz789",
                    "fact": "The actual fact text"
                },
                ...
            ]

        Example:
            # Get all entities that LadybugDB points to
            entities = graph_db.get_related_entities(
                ladybug_uuid,
                direction="outgoing"
            )
            # Returns: [{"name": "./memory/knowledge.ladybug", ...}]

            # Get all entities connected to LadybugDB in any direction
            entities = graph_db.get_related_entities(ladybug_uuid)

            # Get only entities connected via "LOCATED_AT" relationships
            entities = graph_db.get_related_entities(
                ladybug_uuid,
                relationship_type="LOCATED_AT"
            )
        """
        entities = []

        try:
            # Get outgoing relationships (this entity -> target)
            if direction in ["outgoing", "both"]:
                cypher = """
                    MATCH (e:Entity {uuid: $entity_uuid})-[r:RELATES_TO]->(target:Entity)
                    WHERE r.expired_at IS NULL AND target.deleted_at IS NULL
                """
                params = {"entity_uuid": entity_uuid}

                if relationship_type:
                    cypher += " AND r.name = $relationship_type"
                    params["relationship_type"] = relationship_type

                cypher += f"""
                    RETURN {self._entity_return_clause("target")}, 'outgoing', r.name, r.uuid, r.fact
                    LIMIT {limit}
                """

                result = self.conn.execute(cypher, params)

                while result.has_next():
                    row = result.get_next()
                    entity = self._entity_from_row(row)
                    entity.update({
                        "direction": row[len(self.ENTITY_FIELD_NAMES)],
                        "relationship_type": row[len(self.ENTITY_FIELD_NAMES) + 1],
                        "relationship_uuid": row[len(self.ENTITY_FIELD_NAMES) + 2],
                        "fact": row[len(self.ENTITY_FIELD_NAMES) + 3],
                    })
                    entities.append(entity)

            # Get incoming relationships (source -> this entity)
            if direction in ["incoming", "both"]:
                cypher = """
                    MATCH (source:Entity)-[r:RELATES_TO]->(e:Entity {uuid: $entity_uuid})
                    WHERE r.expired_at IS NULL AND source.deleted_at IS NULL
                """
                params = {"entity_uuid": entity_uuid}

                if relationship_type:
                    cypher += " AND r.name = $relationship_type"
                    params["relationship_type"] = relationship_type

                cypher += f"""
                    RETURN {self._entity_return_clause("source")}, 'incoming', r.name, r.uuid, r.fact
                    LIMIT {limit}
                """

                result = self.conn.execute(cypher, params)

                while result.has_next():
                    row = result.get_next()
                    entity = self._entity_from_row(row)
                    entity.update({
                        "direction": row[len(self.ENTITY_FIELD_NAMES)],
                        "relationship_type": row[len(self.ENTITY_FIELD_NAMES) + 1],
                        "relationship_uuid": row[len(self.ENTITY_FIELD_NAMES) + 2],
                        "fact": row[len(self.ENTITY_FIELD_NAMES) + 3],
                    })
                    entities.append(entity)

            return entities
        except Exception as e:
            print(f"Error getting related entities: {e}")
            return []

    def get_relationship_entities(self, relationship_uuid: str) -> Optional[Dict[str, Any]]:
        """
        Get the source and target entities for a specific relationship.

        This is useful when you have a relationship/fact UUID and want to know
        which entities are involved in that relationship.

        Args:
            relationship_uuid: UUID of the relationship

        Returns:
            Dictionary with source and target entities, plus relationship info:
            {
                "relationship_uuid": "rel-xyz789",
                "relationship_type": "LOCATED_AT",
                "fact": "LadybugDB is located at ./memory/knowledge.ladybug",
                "valid_at": "2026-03-01T10:00:00",
                "source": {
                    "uuid": "entity-abc123",
                    "name": "LadybugDB",
                    "summary": "...",
                    "labels": [...]
                },
                "target": {
                    "uuid": "entity-def456",
                    "name": "./memory/knowledge.ladybug",
                    "summary": "...",
                    "labels": [...]
                }
            }

            Returns None if relationship not found.

        Example:
            # Get entities involved in a specific fact
            rel_info = graph_db.get_relationship_entities("rel-xyz789")
            print(f"{rel_info['source']['name']} -> {rel_info['target']['name']}")
            print(f"Fact: {rel_info['fact']}")
        """
        try:
            result = self.conn.execute(f"""
                MATCH (source:Entity)-[r:RELATES_TO {{uuid: $relationship_uuid}}]->(target:Entity)
                RETURN {self._entity_return_clause("source")},
                       {self._entity_return_clause("target")},
                       r.name, r.fact, r.valid_at, r.derivation_version
            """, {
                "relationship_uuid": relationship_uuid,
            })

            rows = []
            while result.has_next():
                rows.append(result.get_next())

            if not rows:
                return None

            row = rows[0]
            entity_field_count = len(self.ENTITY_FIELD_NAMES)
            source = self._entity_from_row(row, start=0)
            target = self._entity_from_row(row, start=entity_field_count)

            return {
                "relationship_uuid": relationship_uuid,
                "relationship_type": row[entity_field_count * 2],
                "fact": row[entity_field_count * 2 + 1],
                "valid_at": str(row[entity_field_count * 2 + 2]),
                "derivation_version": row[entity_field_count * 2 + 3],
                "source": source,
                "target": target
            }
        except Exception as e:
            print(f"Error getting relationship entities: {e}")
            return None



    def get_entity_neighborhood(
        self,
        entity_uuid: str,
        max_hops: int = 1,
        direction: str = "both"
    ) -> Dict[str, Any]:
        """
        NOTE: This function is currently not fully implemented due to Kuzu limitations.
        Use get_related_entities() instead for getting direct neighbors.
        """
        # TODO: Implement when Kuzu supports variable-length paths or directed MATCH
        return {
            "error": "get_entity_neighborhood not yet implemented - use get_related_entities() instead",
            "center": self.get_entity_by_uuid(entity_uuid),
            "entities_by_hop": {},
            "total_entities": 0,
            "max_hops": max_hops
        }

    def get_entity_neighborhood_DISABLED(
        self,
        entity_uuid: str,
        max_hops: int = 1,
        direction: str = "both"
    ) -> Dict[str, Any]:
        """
        Get all entities within N hops of a given entity (graph traversal).

        This performs a breadth-first traversal of the graph starting from the
        specified entity, returning all entities reachable within max_hops steps.

        Args:
            entity_uuid: UUID of the starting entity
            max_hops: Maximum number of relationship hops to traverse (default: 1)
                - 1: Direct neighbors only
                - 2: Neighbors + neighbors of neighbors
                - 3+: Further traversal
            direction: Which relationships to follow:
                - "outgoing": Only follow outgoing relationships
                - "incoming": Only follow incoming relationships
                - "both": Follow all relationships (default)

        Returns:
            Dictionary with entities organized by hop distance:
            {
                "center": {
                    "uuid": "entity-abc123",
                    "name": "LadybugDB",
                    ...
                },
                "entities_by_hop": {
                    1: [  # Entities 1 hop away
                        {
                            "uuid": "entity-def456",
                            "name": "./memory/knowledge.ladybug",
                            "path_length": 1,
                            "relationship_path": ["LOCATED_AT"]
                        },
                        ...
                    ],
                    2: [  # Entities 2 hops away
                        {...},
                        ...
                    ]
                },
                "total_entities": 5,
                "max_hops": 2
            }

        Example:
            # Get direct neighbors of LadybugDB
            neighborhood = graph_db.get_entity_neighborhood(ladybug_uuid, max_hops=1)
            print(f"Found {neighborhood['total_entities']} neighbors")

            # Get entities within 2 hops
            neighborhood = graph_db.get_entity_neighborhood(ladybug_uuid, max_hops=2)
            for hop, entities in neighborhood['entities_by_hop'].items():
                print(f"Hop {hop}: {len(entities)} entities")

            # Only follow outgoing relationships
            neighborhood = graph_db.get_entity_neighborhood(
                ladybug_uuid,
                max_hops=2,
                direction="outgoing"
            )

        Note:
            - This can be expensive for large graphs with high max_hops
            - Entities are deduplicated (each entity appears only once)
            - The shortest path to each entity is recorded
        """
        try:
            # Get the center entity
            center = self.get_entity_by_uuid(entity_uuid)
            if not center:
                return {
                    "error": "Entity not found",
                    "center": None,
                    "entities_by_hop": {},
                    "total_entities": 0,
                    "max_hops": max_hops
                }

            # NOTE: Current implementation only supports max_hops=1 (direct neighbors)
            # Variable-length path queries (*1..N) are not yet supported in Kuzu
            # TODO: Implement multi-hop traversal using recursive queries when Kuzu supports it

            if max_hops > 1:
                print(f"Warning: max_hops > 1 not yet supported, using max_hops=1")
                max_hops = 1

            # Build Cypher query for direct neighbors (1 hop)
            if direction == "outgoing":
                cypher = f"""
                    MATCH (start:Entity {{uuid: '{entity_uuid}'}})-[r:RELATES_TO]->(end:Entity)
                    WHERE end.deleted_at IS NULL AND r.expired_at IS NULL
                    RETURN DISTINCT {self._entity_return_clause("end")}, 1 as hop_distance, [r.name] as rel_path
                """
            elif direction == "incoming":
                cypher = f"""
                    MATCH (start:Entity {{uuid: '{entity_uuid}'}})<-[r:RELATES_TO]-(end:Entity)
                    WHERE end.deleted_at IS NULL AND r.expired_at IS NULL
                    RETURN DISTINCT {self._entity_return_clause("end")}, 1 as hop_distance, [r.name] as rel_path
                """
            else:  # both
                cypher = f"""
                    MATCH (start:Entity {{uuid: '{entity_uuid}'}})-[r:RELATES_TO]->(end:Entity)
                    WHERE end.deleted_at IS NULL AND r.expired_at IS NULL
                    RETURN DISTINCT {self._entity_return_clause("end")}, 1 as hop_distance, [r.name] as rel_path
                """

            result = self.conn.execute(cypher)

            entities_by_hop = {}
            seen_uuids = set()

            while result.has_next():
                row = result.get_next()

                entity_uuid_result = row[0]

                # Skip if we've already seen this entity (take shortest path)
                if entity_uuid_result in seen_uuids:
                    continue

                seen_uuids.add(entity_uuid_result)

                hop_distance = row[len(self.ENTITY_FIELD_NAMES)]
                rel_path = row[len(self.ENTITY_FIELD_NAMES) + 1]

                entity = self._entity_from_row(row)
                entity.update({
                    "path_length": hop_distance,
                    "relationship_path": rel_path,
                })

                if hop_distance not in entities_by_hop:
                    entities_by_hop[hop_distance] = []

                entities_by_hop[hop_distance].append(entity)

            return {
                "center": center,
                "entities_by_hop": entities_by_hop,
                "total_entities": len(seen_uuids),
                "max_hops": max_hops,
                "direction": direction
            }
        except Exception as e:
            print(f"Error getting entity neighborhood: {e}")
            return {
                "error": str(e),
                "center": None,
                "entities_by_hop": {},
                "total_entities": 0,
                "max_hops": max_hops
            }
