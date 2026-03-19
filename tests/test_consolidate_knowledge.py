import json
import os
import shutil
import sys
import unittest
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tools.graph_db import GraphDatabase
from scripts.consolidate_knowledge import (
    cleanup_old_hub_detections,
    find_hubs,
    get_last_hub_detection,
    find_neighborhoods,
    find_relationship_patterns,
    find_transitive_relationships,
    store_hub_detections,
)


REPO_ROOT = Path(__file__).resolve().parent.parent


class ConsolidateKnowledgeTests(unittest.TestCase):
    def setUp(self):
        base_tmp = REPO_ROOT / "tests" / "tmp"
        base_tmp.mkdir(parents=True, exist_ok=True)
        self.test_dir = base_tmp / f"consolidate_{uuid4().hex[:8]}"
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.graph_path = self.test_dir / "test.graph"
        self.original_cwd = Path.cwd()
        os.chdir(self.test_dir)

        self.graph_db = GraphDatabase(str(self.graph_path))
        self.project_a = "project-a"
        self.project_b = "project-b"
        self.graph_db.create_project_node(self.project_a)
        self.graph_db.create_project_node(self.project_b)

    def tearDown(self):
        self.graph_db.close()
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_entity(self, project_name, name, summary="test entity", labels=None):
        entity_uuid = self.graph_db.create_entity(
            name=name,
            group_id=project_name,
            source_interactions=[],
            source_hashes=[],
            extraction_version="test",
            extraction_commit="test",
            summary=summary,
            labels=labels or ["Concept"],
            attributes={},
        )
        self.graph_db.link_project_to_entity(project_name, entity_uuid)
        return entity_uuid

    def _create_relationship(
        self,
        source_uuid,
        target_uuid,
        project_name,
        relationship_name="RELATED_TO",
        fact="test fact",
        valid_at="2026-03-14T00:00:00",
        invalid_at=None,
        attributes=None,
    ):
        self.graph_db.create_relationship(
            source_uuid=source_uuid,
            target_uuid=target_uuid,
            relationship_name=relationship_name,
            fact=fact,
            episodes=[],
            episode_hashes=[],
            group_id=project_name,
            valid_at=valid_at,
            invalid_at=invalid_at,
            attributes=attributes or {},
            derivation_version="test",
            derivation_commit="test",
        )

    def _get_hub_relationship_attributes(self, source_uuid):
        result = self.graph_db.conn.execute(
            """
            MATCH (e:Entity {uuid: $source_uuid})-[r:RELATES_TO]->(c:Entity {name: 'Consolidation System'})
            WHERE r.name = 'HUB_ENTITY' AND r.invalid_at IS NULL
            RETURN r.attributes
            """,
            {"source_uuid": source_uuid},
        )
        self.assertTrue(result.has_next(), "Expected active HUB_ENTITY relationship")
        row = result.get_next()
        return row[0] if isinstance(row[0], dict) else json.loads(row[0])

    def _count_hub_relationships(self, project_name):
        result = self.graph_db.conn.execute(
            """
            MATCH (p:Project {name: $project_name})-[:HAS_ENTITY]->(e:Entity)-[r:RELATES_TO]->(c:Entity {name: 'Consolidation System'})
            WHERE r.name = 'HUB_ENTITY'
            RETURN count(r)
            """,
            {"project_name": project_name},
        )
        return result.get_next()[0] if result.has_next() else 0

    def _get_min_hub_chain_index(self, project_name):
        """Get the minimum hub_chain_index for a project (should be 0 for first run)."""
        result = self.graph_db.conn.execute(
            """
            MATCH (p:Project {name: $project_name})-[:HAS_ENTITY]->(e:Entity)-[r:RELATES_TO]->(c:Entity {name: 'Consolidation System'})
            WHERE r.name = 'HUB_ENTITY'
            RETURN r.attributes
            """,
            {"project_name": project_name},
        )
        min_index = None
        while result.has_next():
            row = result.get_next()
            attrs = row[0] if isinstance(row[0], dict) else json.loads(row[0])
            idx = attrs.get("hub_chain_index", 0)
            if min_index is None or idx < min_index:
                min_index = idx
        return min_index

    def _get_max_hub_chain_index(self, project_name):
        """Get the maximum hub_chain_index for a project."""
        result = self.graph_db.conn.execute(
            """
            MATCH (p:Project {name: $project_name})-[:HAS_ENTITY]->(e:Entity)-[r:RELATES_TO]->(c:Entity {name: 'Consolidation System'})
            WHERE r.name = 'HUB_ENTITY'
            RETURN r.attributes
            """,
            {"project_name": project_name},
        )
        max_index = 0
        while result.has_next():
            row = result.get_next()
            attrs = row[0] if isinstance(row[0], dict) else json.loads(row[0])
            idx = attrs.get("hub_chain_index", 0)
            if idx > max_index:
                max_index = idx
        return max_index

    def _count_active_hub_relationships(self, project_name, entity_uuid=None):
        query = """
            MATCH (p:Project {name: $project_name})-[:HAS_ENTITY]->(e:Entity)-[r:RELATES_TO]->(c:Entity {name: 'Consolidation System'})
            WHERE r.name = 'HUB_ENTITY' AND r.invalid_at IS NULL
        """
        params = {"project_name": project_name}
        if entity_uuid:
            query += " AND e.uuid = $entity_uuid"
            params["entity_uuid"] = entity_uuid
        query += " RETURN count(r)"
        result = self.graph_db.conn.execute(query, params)
        return result.get_next()[0] if result.has_next() else 0

    def _count_total_hub_relationships(self, project_name, entity_uuid=None):
        query = """
            MATCH (p:Project {name: $project_name})-[:HAS_ENTITY]->(e:Entity)-[r:RELATES_TO]->(c:Entity {name: 'Consolidation System'})
            WHERE r.name = 'HUB_ENTITY'
        """
        params = {"project_name": project_name}
        if entity_uuid:
            query += " AND e.uuid = $entity_uuid"
            params["entity_uuid"] = entity_uuid
        query += " RETURN count(r)"
        result = self.graph_db.conn.execute(query, params)
        return result.get_next()[0] if result.has_next() else 0

    def test_get_last_hub_detection_is_project_scoped(self):
        entity_a = self._create_entity(self.project_a, "Entity A")
        entity_b = self._create_entity(self.project_b, "Entity B")
        consolidation_a = self._create_entity(self.project_a, "Consolidation System", labels=["System"])
        consolidation_b = self._create_entity(self.project_b, "Consolidation System", labels=["System"])

        self._create_relationship(
            entity_a,
            consolidation_a,
            self.project_a,
            relationship_name="HUB_ENTITY",
            fact="A is a hub",
            valid_at="2026-03-14T00:00:00",
            attributes={"hub_chain_index": 0, "current_hub_hash": "hash-a"},
        )
        self._create_relationship(
            entity_b,
            consolidation_b,
            self.project_b,
            relationship_name="HUB_ENTITY",
            fact="B is a hub",
            valid_at="2026-03-14T01:00:00",
            attributes={"hub_chain_index": 0, "current_hub_hash": "hash-b"},
        )

        last_a = get_last_hub_detection(self.graph_db, self.project_a)
        self.assertEqual(last_a["hash"], "hash-a")
        self.assertEqual(last_a["chain_index"], 0)

    def test_store_hub_detections_starts_separate_chain_per_project(self):
        entity_a = self._create_entity(self.project_a, "Hub A")
        target_a = self._create_entity(self.project_a, "Target A")
        self._create_relationship(
            entity_a,
            target_a,
            self.project_a,
            relationship_name="USES",
            fact="Hub A uses Target A",
        )

        entity_b = self._create_entity(self.project_b, "Hub B")
        target_b = self._create_entity(self.project_b, "Target B")
        self._create_relationship(
            entity_b,
            target_b,
            self.project_b,
            relationship_name="USES",
            fact="Hub B uses Target B",
        )

        hubs_a = find_hubs(self.graph_db, self.project_a, min_size=1)
        store_hub_detections(None, self.graph_db, self.project_a, hubs_a)

        hubs_b = find_hubs(self.graph_db, self.project_b, min_size=1)
        store_hub_detections(None, self.graph_db, self.project_b, hubs_b)

        # Get minimum chain index for each project - should start at 0
        min_index_a = self._get_min_hub_chain_index(self.project_a)
        min_index_b = self._get_min_hub_chain_index(self.project_b)

        self.assertEqual(min_index_a, 0, "Project A chain should start at 0")
        self.assertEqual(min_index_b, 0, "Project B chain should start at 0 (separate chain)")

    def test_cleanup_old_hub_detections_only_removes_requested_project(self):
        entity_a = self._create_entity(self.project_a, "Entity A")
        consolidation_a = self._create_entity(self.project_a, "Consolidation System", labels=["System"])
        entity_b = self._create_entity(self.project_b, "Entity B")
        consolidation_b = self._create_entity(self.project_b, "Consolidation System", labels=["System"])

        old_invalid_at = "2000-01-01T00:00:00"
        self._create_relationship(
            entity_a,
            consolidation_a,
            self.project_a,
            relationship_name="HUB_ENTITY",
            fact="old hub A",
            valid_at="1999-01-01T00:00:00",
            invalid_at=old_invalid_at,
            attributes={"hub_chain_index": 0, "current_hub_hash": "old-a"},
        )
        self._create_relationship(
            entity_b,
            consolidation_b,
            self.project_b,
            relationship_name="HUB_ENTITY",
            fact="old hub B",
            valid_at="1999-01-01T00:00:00",
            invalid_at=old_invalid_at,
            attributes={"hub_chain_index": 0, "current_hub_hash": "old-b"},
        )

        cleanup_old_hub_detections(self.graph_db, self.project_a, keep_days=0)

        archive_file = self.test_dir / f"hub_archive_{self.project_a}.jsonl"
        self.assertTrue(archive_file.exists(), "Expected cleanup archive file for requested project")
        archive_lines = [json.loads(line) for line in archive_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        archived_names = {line["entity_name"] for line in archive_lines}

        self.assertEqual(archived_names, {"Entity A"})
        self.assertEqual(self._count_hub_relationships(self.project_a), 0)
        self.assertEqual(self._count_hub_relationships(self.project_b), 1)

    def test_find_hubs_ignores_cross_project_edges(self):
        local_hub = self._create_entity(self.project_a, "Local Hub")
        local_target = self._create_entity(self.project_a, "Local Target")
        foreign_1 = self._create_entity(self.project_b, "Foreign 1")
        foreign_2 = self._create_entity(self.project_b, "Foreign 2")
        foreign_3 = self._create_entity(self.project_b, "Foreign 3")

        self._create_relationship(local_hub, local_target, self.project_a, relationship_name="USES", fact="local link")
        self._create_relationship(local_hub, foreign_1, self.project_a, relationship_name="USES", fact="cross link 1")
        self._create_relationship(foreign_2, local_hub, self.project_b, relationship_name="USES", fact="cross link 2")
        self._create_relationship(foreign_3, local_hub, self.project_b, relationship_name="USES", fact="cross link 3")

        hubs = find_hubs(self.graph_db, self.project_a, min_size=2)

        self.assertEqual(hubs, [], "Cross-project edges should not make a project-local hub exceed threshold")

    def test_find_hubs_counts_incoming_and_outgoing_project_local_edges(self):
        center = self._create_entity(self.project_a, "Center")
        out_1 = self._create_entity(self.project_a, "Out 1")
        out_2 = self._create_entity(self.project_a, "Out 2")
        in_1 = self._create_entity(self.project_a, "In 1")
        in_2 = self._create_entity(self.project_a, "In 2")

        self._create_relationship(center, out_1, self.project_a, relationship_name="USES", fact="out 1")
        self._create_relationship(center, out_2, self.project_a, relationship_name="USES", fact="out 2")
        self._create_relationship(in_1, center, self.project_a, relationship_name="USES", fact="in 1")
        self._create_relationship(in_2, center, self.project_a, relationship_name="USES", fact="in 2")

        hubs = find_hubs(self.graph_db, self.project_a, min_size=4)

        self.assertEqual(len(hubs), 1)
        self.assertEqual(hubs[0]["name"], "Center")
        self.assertEqual(hubs[0]["count"], 4)

    def test_find_neighborhoods_ignores_cross_project_neighbors(self):
        center = self._create_entity(self.project_a, "Center")
        local_1 = self._create_entity(self.project_a, "Local 1")
        local_2 = self._create_entity(self.project_a, "Local 2")
        foreign_1 = self._create_entity(self.project_b, "Foreign 1")
        foreign_2 = self._create_entity(self.project_b, "Foreign 2")

        self._create_relationship(center, local_1, self.project_a, relationship_name="RELATED_TO", fact="local 1")
        self._create_relationship(center, local_2, self.project_a, relationship_name="RELATED_TO", fact="local 2")
        self._create_relationship(center, foreign_1, self.project_a, relationship_name="RELATED_TO", fact="cross 1")
        self._create_relationship(foreign_2, center, self.project_b, relationship_name="RELATED_TO", fact="cross 2")

        clusters = find_neighborhoods(self.graph_db, self.project_a, min_size=3)

        self.assertEqual(clusters, [], "Cross-project neighbors should not inflate neighborhood size")

    def test_find_relationship_patterns_ignore_cross_project_targets(self):
        source_a = self._create_entity(self.project_a, "Source A")
        local_target = self._create_entity(self.project_a, "Local Target")
        foreign_1 = self._create_entity(self.project_b, "Foreign 1")
        foreign_2 = self._create_entity(self.project_b, "Foreign 2")

        self._create_relationship(source_a, local_target, self.project_a, relationship_name="USES", fact="local use")
        self._create_relationship(source_a, foreign_1, self.project_a, relationship_name="USES", fact="cross use 1")
        self._create_relationship(source_a, foreign_2, self.project_a, relationship_name="USES", fact="cross use 2")

        patterns = find_relationship_patterns(self.graph_db, self.project_a)

        self.assertEqual(patterns, [], "Cross-project targets should not count toward project-local relationship patterns")

    def test_find_transitive_relationships_ignores_cross_project_middle_and_target(self):
        a = self._create_entity(self.project_a, "A")
        foreign_b = self._create_entity(self.project_b, "Foreign B")
        foreign_c = self._create_entity(self.project_b, "Foreign C")

        self._create_relationship(a, foreign_b, self.project_a, relationship_name="ENABLES", fact="A enables B")
        self._create_relationship(foreign_b, foreign_c, self.project_b, relationship_name="ENABLES", fact="B enables C")

        transitive = find_transitive_relationships(self.graph_db, self.project_a, rel_type="ENABLES")

        self.assertEqual(transitive, [], "Transitive chains should not traverse entities outside the requested project")

    def test_repeated_store_supersedes_previous_hub_detection(self):
        """Test that storing hubs twice supersedes old detections.

        Chain semantics: The chain is per-project, not per-entity.
        Each store batch advances the project-wide chain index.
        """
        hub = self._create_entity(self.project_a, "Repeat Hub")
        target = self._create_entity(self.project_a, "Target")
        self._create_relationship(hub, target, self.project_a, relationship_name="USES", fact="initial relation")

        hubs = find_hubs(self.graph_db, self.project_a, min_size=1)
        store_hub_detections(None, self.graph_db, self.project_a, hubs)
        first_min_index = self._get_min_hub_chain_index(self.project_a)
        first_max_index = self._get_max_hub_chain_index(self.project_a)

        extra_target = self._create_entity(self.project_a, "Target 2")
        self._create_relationship(hub, extra_target, self.project_a, relationship_name="USES", fact="second relation")

        hubs = find_hubs(self.graph_db, self.project_a, min_size=1)
        store_hub_detections(None, self.graph_db, self.project_a, hubs)
        second_attrs = self._get_hub_relationship_attributes(hub)

        # Old detection for this entity should be superseded (invalid_at set)
        self.assertEqual(self._count_active_hub_relationships(self.project_a, hub), 1)
        self.assertEqual(self._count_total_hub_relationships(self.project_a, hub), 2)

        # New detection should have higher chain index than first batch
        self.assertGreater(second_attrs["hub_chain_index"], first_max_index)


if __name__ == "__main__":
    unittest.main()
