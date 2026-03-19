"""Focused tests for MCP handler logic."""

from __future__ import annotations

import sys

# Python 3.10+ required for mcp package
if sys.version_info < (3, 10):
    sys.exit(
        "ERROR: MCP tests require Python 3.10+.\n"
        "Current: Python {}.{}\n"
        "Fix: Update mem.config.json python_path to python3.11".format(
            sys.version_info.major, sys.version_info.minor
        )
    )

import json
import os
import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from mcp_server.handlers.context import memory_context
from mcp_server.handlers.recall import memory_recall
from mcp_server.handlers.search import memory_search
from mcp_server.handlers.store import memory_store
from mcp_server.handlers.tasks import memory_tasks
from scripts.tasks import record_task_operation_event
from tools.graph_db import GraphDatabase
from tools.sql_db import SQLDatabase


REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def mcp_test_env(monkeypatch, tmp_path):
    project_name = "mcp-test"
    graph_path = tmp_path / "memory" / f"{project_name}.graph"
    sql_path = tmp_path / "memory" / "conversations.db"
    config_path = tmp_path / "mem.config.json"

    config_path.write_text(
        json.dumps(
            {
                "project_name": project_name,
                "database": {
                    "graph_path": str(graph_path),
                    "sql_path": str(sql_path),
                },
                "mcp": {
                    "network_mode": "localhost",
                    "bind_host": "127.0.0.1",
                    "bind_port": 8765,
                    "tls_enabled": False,
                    "tls_cert_path": None,
                    "tls_key_path": None,
                    "tls_verify_client": False,
                    "allowed_subnets": [],
                    "deny_public_ips": True,
                },
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("MEM_CONFIG", str(config_path))

    sql_db = SQLDatabase(str(sql_path))
    sql_db.create_project(project_name, "MCP Test Project")

    graph_db = GraphDatabase(str(graph_path))
    graph_db.create_project_node(project_name, "MCP Test Project")

    uuid1 = sql_db.store_interaction(
        {
            "project_name": project_name,
            "user_message": "LadybugDB stores the graph",
            "assistant_message": "Noted.",
        }
    )
    interaction1 = sql_db.get_interaction_by_uuid(uuid1)

    uuid2 = sql_db.store_interaction(
        {
            "project_name": project_name,
            "user_message": "The graph lives in memory/knowledge.graph",
            "assistant_message": "Stored.",
        }
    )
    interaction2 = sql_db.get_interaction_by_uuid(uuid2)

    graph_uuid = graph_db.create_entity(
        name="LadybugDB",
        group_id=project_name,
        source_interactions=[uuid1],
        source_hashes=[interaction1["content_hash"]],
        extraction_version="v1.0.0",
        extraction_commit="test",
        summary="Graph database",
        labels=["Technology"],
    )
    file_uuid = graph_db.create_entity(
        name="memory/knowledge.graph",
        group_id=project_name,
        source_interactions=[uuid2],
        source_hashes=[interaction2["content_hash"]],
        extraction_version="v1.0.0",
        extraction_commit="test",
        summary="Graph file path",
        labels=["File"],
    )
    task_uuid = graph_db.create_entity(
        name="Implement MCP server",
        group_id=project_name,
        source_interactions=[uuid1],
        source_hashes=[interaction1["content_hash"]],
        extraction_version="manual",
        extraction_commit="manual",
        summary="Create the MCP adapter",
        labels=["Task"],
        priority="high",
        status="pending",
    )

    graph_db.link_project_to_entity(project_name, graph_uuid)
    graph_db.link_project_to_entity(project_name, file_uuid)
    graph_db.link_project_to_entity(project_name, task_uuid)

    graph_db.create_relationship(
        source_uuid=graph_uuid,
        target_uuid=file_uuid,
        relationship_name="LOCATED_AT",
        fact="LadybugDB is located at memory/knowledge.graph",
        group_id=project_name,
        episodes=[uuid2],
        episode_hashes=[interaction2["content_hash"]],
        derivation_version="v1.0.0",
        derivation_commit="test",
        valid_at=interaction2["timestamp"],
    )
    graph_db.create_relationship(
        source_uuid=file_uuid,
        target_uuid=graph_uuid,
        relationship_name="USED_BY",
        fact="memory/knowledge.graph is used by LadybugDB",
        group_id=project_name,
        episodes=[uuid2],
        episode_hashes=[interaction2["content_hash"]],
        derivation_version="v1.0.0",
        derivation_commit="test",
        valid_at=interaction2["timestamp"],
    )

    record_task_operation_event(
        project_name,
        "start",
        "Implement MCP server",
        task_uuid=task_uuid,
        status_before="pending",
        status_after="in_progress",
    )

    yield {
        "project_name": project_name,
        "graph_db": graph_db,
        "sql_db": sql_db,
        "task_uuid": task_uuid,
    }

    graph_db.close()
    shutil.rmtree(tmp_path, ignore_errors=True)


def test_memory_recall_returns_incoming_and_outgoing_relationships(mcp_test_env):
    response = memory_recall("2026-01-01", "2026-12-31", entity="LadybugDB")

    assert response["status"] == "ok"
    relationships = response["data"]["relationships"]
    assert relationships is not None
    assert relationships["outgoing"]
    assert relationships["incoming"]
    assert response["data"]["task_activity"]


def test_memory_recall_limit_prefers_most_recent_entities(mcp_test_env):
    graph_db = mcp_test_env["graph_db"]
    project_name = mcp_test_env["project_name"]
    old_uuid = graph_db.create_entity(
        name="Older Entity",
        group_id=project_name,
        source_interactions=["test-old"],
        source_hashes=["hash-old"],
        extraction_version="v1.0.0",
        extraction_commit="test",
        summary="Older recall entity",
        labels=["Concept"],
    )
    new_uuid = graph_db.create_entity(
        name="Newer Entity",
        group_id=project_name,
        source_interactions=["test-new"],
        source_hashes=["hash-new"],
        extraction_version="v1.0.0",
        extraction_commit="test",
        summary="Newer recall entity",
        labels=["Concept"],
    )
    graph_db.link_project_to_entity(project_name, old_uuid)
    graph_db.link_project_to_entity(project_name, new_uuid)
    graph_db.conn.execute(
        """
        MATCH (e:Entity {uuid: $uuid})
        SET e.extraction_timestamp_str = $timestamp
        """,
        {"uuid": old_uuid, "timestamp": "2026-03-10T01:00:00"},
    )
    graph_db.conn.execute(
        """
        MATCH (e:Entity {uuid: $uuid})
        SET e.extraction_timestamp_str = $timestamp
        """,
        {"uuid": new_uuid, "timestamp": "2026-03-10T23:00:00"},
    )

    response = memory_recall("2026-03-10", "2026-03-10", limit=1, hide_task_activity=True)

    assert response["status"] == "ok"
    assert [entity["name"] for entity in response["data"]["entities"]] == ["Newer Entity"]
    assert response["data"]["truncated"] is True
    assert response["data"]["returned_count"] == 1
    assert response["data"]["total_count"] >= 2
    assert response["data"]["limit"] == 1


def test_memory_search_returns_entity_and_fact_results(mcp_test_env):
    response = memory_search(search="ladybug", entity="LadybugDB", type="LOCATED_AT", facts="located")

    assert response["status"] == "ok"
    assert response["data"]["entities"]
    assert response["data"]["entity_result"]["entity"]["name"] == "LadybugDB"
    assert response["data"]["entity_result"]["facts"][0]["relationship_type"] == "LOCATED_AT"
    assert response["data"]["facts"][0]["relationship_type"] == "LOCATED_AT"


def test_memory_context_returns_recent_entities_and_tasks(mcp_test_env):
    response = memory_context(last=5)

    assert response["status"] == "ok"
    assert response["data"]["project"]["name"] == mcp_test_env["project_name"]
    assert response["data"]["recent_entities"]
    assert response["data"]["actionable_tasks"]
    assert "verification result" in response["data"]["note"]


def test_memory_store_persists_interaction(mcp_test_env):
    response = memory_store("Store this", "Stored", fidelity="summary")

    assert response["status"] == "ok"
    assert response["data"]["project_name"] == mcp_test_env["project_name"]
    assert response["data"]["fidelity"] == "summary"


def test_memory_tasks_supports_list_add_and_transition(mcp_test_env):
    listed = memory_tasks("list")
    assert listed["status"] == "ok"
    existing_count = listed["data"]["count"]

    # Create a fresh task for this test to avoid state pollution
    fresh_task = memory_tasks("add", name="TransitionTestTask", summary="Task for transition test", priority="high")
    assert fresh_task["status"] == "ok"
    # Get the hash by listing and finding our task
    relisted = memory_tasks("list")
    existing_hash = next(t["short_hash"] for t in relisted["data"]["tasks"] if t["name"] == "TransitionTestTask")

    added = memory_tasks("add", name="Wire inspector", summary="Add MCP inspector docs", priority="medium")
    assert added["status"] == "ok"

    reprioritized = memory_tasks("set_priority", task_hash=existing_hash, priority="low")
    assert reprioritized["status"] == "ok"
    assert reprioritized["data"]["priority"] == "low"

    started = memory_tasks("start", task_hash=existing_hash)
    assert started["status"] == "ok"
    assert started["data"]["status_after"] == "in_progress"

    relisted = memory_tasks("list")
    assert relisted["status"] == "ok"
    assert relisted["data"]["count"] == existing_count + 2  # We added 2 tasks


def test_memory_tasks_supports_edit_and_blockers(mcp_test_env):
    # Create a fresh task for this test to avoid state pollution
    fresh_task = memory_tasks("add", name="EditTestTask", summary="Task for edit test", priority="high")
    assert fresh_task["status"] == "ok"

    added_blocker = memory_tasks("add", name="Write docs blocker", summary="Document the MCP flow", priority="medium")
    assert added_blocker["status"] == "ok"

    # Get hashes by listing
    listed = memory_tasks("list")
    tasks_by_name = {t["name"]: t for t in listed["data"]["tasks"]}
    existing_hash = tasks_by_name["EditTestTask"]["short_hash"]
    blocker_hash = tasks_by_name["Write docs blocker"]["short_hash"]

    edited = memory_tasks(
        "edit",
        task_hash=existing_hash,
        name="Implement MCP server v2",
        summary="Updated MCP adapter summary",
        details="Track blocker and parent coverage",
        blocked_by=[blocker_hash],
    )
    assert edited["status"] == "ok"
    assert set(edited["data"]["fields_changed"]) == {"name", "summary", "details", "blocked_by"}
    assert edited["data"]["task"]["name"] == "Implement MCP server v2"
    assert edited["data"]["task"]["is_blocked"] is True
    assert edited["data"]["task"]["blocked_count"] == 1

    cleared = memory_tasks("clear_blocked_by", task_hash=existing_hash)
    assert cleared["status"] == "ok"
    assert cleared["data"]["task"]["is_blocked"] is False
    assert "blocked_by" not in cleared["data"]["task"]["attributes"]


def test_memory_tasks_supports_parent_and_clear_parent(mcp_test_env):
    # Create fresh tasks for this test to avoid state pollution
    fresh_task = memory_tasks("add", name="ChildTestTask", summary="Task for parent test", priority="medium")
    assert fresh_task["status"] == "ok"

    added_parent = memory_tasks("add", name="ParentTestTask", summary="Own the MCP rollout", priority="high")
    assert added_parent["status"] == "ok"

    # Get hashes by listing
    listed = memory_tasks("list")
    tasks_by_name = {t["name"]: t for t in listed["data"]["tasks"]}
    child_hash = tasks_by_name["ChildTestTask"]["short_hash"]
    parent_hash = tasks_by_name["ParentTestTask"]["short_hash"]

    set_parent = memory_tasks("set_parent", task_hash=child_hash, parent_hash=parent_hash)
    assert set_parent["status"] == "ok"
    assert set_parent["data"]["fields_changed"] == ["parent_task_uuid"]
    assert set_parent["data"]["task"]["parent_short_hash"] == parent_hash

    cleared = memory_tasks("clear_parent", task_hash=child_hash)
    assert cleared["status"] == "ok"
    assert cleared["data"]["fields_changed"] == ["parent_task_uuid"]
    assert cleared["data"]["task"].get("parent_task_uuid") is None


def test_memory_tasks_rejects_invalid_dependency_edits(mcp_test_env):
    # Create a fresh task for this test to avoid state pollution from other tests
    add_result = memory_tasks(
        "add",
        name="DependencyTestTask",
        priority="medium",
        summary="Task for testing invalid dependency edits",
    )
    assert add_result["status"] == "ok"

    # Get hash by listing
    listed = memory_tasks("list")
    task_hash = next(t["short_hash"] for t in listed["data"]["tasks"] if t["name"] == "DependencyTestTask")

    self_block = memory_tasks("edit", task_hash=task_hash, blocked_by=[task_hash])
    assert self_block["status"] == "error"
    assert self_block["type"] == "validation"
    assert "block itself" in self_block["message"]

    self_parent = memory_tasks("set_parent", task_hash=task_hash, parent_hash=task_hash)
    assert self_parent["status"] == "error"
    assert self_parent["type"] == "validation"
    assert "own parent" in self_parent["message"]
