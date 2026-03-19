"""True stdio MCP end-to-end tests using the real MCP client/session."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

if sys.version_info < (3, 10):
    sys.exit(
        "ERROR: MCP tests require Python 3.10+.\n"
        "Current: Python {}.{}\n"
        "Fix: Update mem.config.json python_path to python3.11".format(
            sys.version_info.major, sys.version_info.minor
        )
    )

pytest.importorskip("mcp", reason="mcp package required for stdio protocol tests")

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from tools.graph_db import GraphDatabase
from tools.sql_db import SQLDatabase

SERVER_STARTUP_TIMEOUT = 10.0
SESSION_INIT_TIMEOUT = 10.0
TOOL_CALL_TIMEOUT = 10.0


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


@pytest.fixture
def isolated_stdio_env(tmp_path: Path, repo_root: Path) -> dict[str, str]:
    """Create an isolated config + databases for real stdio MCP tests."""
    config_path = tmp_path / "mem.config.json"
    sql_path = tmp_path / "stdio-test.db"
    graph_path = tmp_path / "stdio-test.graph"
    project_name = "test_stdio_protocol"

    config_path.write_text(
        json.dumps(
            {
                "project_name": project_name,
                "python_path": sys.executable,
                "database": {
                    "sql_path": str(sql_path),
                    "graph_path": str(graph_path),
                },
            }
        )
    )

    GraphDatabase(str(graph_path))
    SQLDatabase(str(sql_path)).create_project(project_name, "Real stdio MCP test project")

    return {
        "repo_root": str(repo_root),
        "config_path": str(config_path),
        "sql_path": str(sql_path),
        "graph_path": str(graph_path),
        "project_name": project_name,
        "entrypoint": str(repo_root / "mcp-server" / "memory_mcp.py"),
    }


@pytest.fixture
def stdio_server_params(isolated_stdio_env: dict[str, str]) -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=[isolated_stdio_env["entrypoint"]],
        env={**os.environ, "MEM_CONFIG": isolated_stdio_env["config_path"]},
        cwd=isolated_stdio_env["repo_root"],
    )


@pytest.fixture
def stdio_server_params_other_cwd(isolated_stdio_env: dict[str, str], tmp_path: Path) -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=[isolated_stdio_env["entrypoint"]],
        env={**os.environ, "MEM_CONFIG": isolated_stdio_env["config_path"]},
        cwd=str(tmp_path),
    )


@asynccontextmanager
async def open_stdio_client_session(stdio_server_params: StdioServerParameters):
    async with stdio_client(stdio_server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await asyncio.wait_for(session.initialize(), timeout=SESSION_INIT_TIMEOUT)
            yield session


def _tool_result_json(result) -> dict:
    assert getattr(result, "isError", False) is False
    assert getattr(result, "content", None), "Expected MCP tool content"
    first = result.content[0]
    return json.loads(first.text)


class TestMCPStdioProtocolE2E:
    @pytest.mark.asyncio
    async def test_stdio_server_initializes(self, stdio_server_params: StdioServerParameters):
        async with open_stdio_client_session(stdio_server_params) as session:
            tools = await asyncio.wait_for(session.list_tools(), timeout=TOOL_CALL_TIMEOUT)
            assert tools is not None
            assert hasattr(tools, "tools")

    @pytest.mark.asyncio
    async def test_stdio_lists_expected_tools(self, stdio_server_params: StdioServerParameters):
        async with open_stdio_client_session(stdio_server_params) as session:
            tools = await asyncio.wait_for(session.list_tools(), timeout=TOOL_CALL_TIMEOUT)
            tool_names = {tool.name for tool in tools.tools}

            assert {
                "memory_recall",
                "memory_search",
                "memory_store",
                "memory_tasks",
                "memory_context",
                "memory_sync_submit",
                "memory_sync_status",
                "memory_sync_result",
                "memory_sync_list",
                "memory_sync_submit_quality_review",
            }.issubset(tool_names)

    @pytest.mark.asyncio
    async def test_stdio_memory_context_round_trip(
        self, stdio_server_params: StdioServerParameters, isolated_stdio_env: dict[str, str]
    ):
        async with open_stdio_client_session(stdio_server_params) as session:
            result = await asyncio.wait_for(
                session.call_tool("memory_context", {"last": 2}),
                timeout=TOOL_CALL_TIMEOUT,
            )
            data = _tool_result_json(result)

        assert data["status"] == "ok"
        assert data["data"]["project"]["name"] == isolated_stdio_env["project_name"]
        assert "counts" in data["data"]

    @pytest.mark.asyncio
    async def test_stdio_memory_tasks_list_round_trip(
        self, stdio_server_params: StdioServerParameters, isolated_stdio_env: dict[str, str]
    ):
        async with open_stdio_client_session(stdio_server_params) as session:
            result = await asyncio.wait_for(
                session.call_tool("memory_tasks", {"action": "list"}),
                timeout=TOOL_CALL_TIMEOUT,
            )
            data = _tool_result_json(result)

        assert data["status"] == "ok"
        assert data["data"]["project_name"] == isolated_stdio_env["project_name"]
        assert isinstance(data["data"]["tasks"], list)
        assert data["data"]["count"] == 0

    @pytest.mark.asyncio
    async def test_stdio_respects_mem_config_from_other_cwd(
        self,
        stdio_server_params_other_cwd: StdioServerParameters,
        isolated_stdio_env: dict[str, str],
    ):
        async with stdio_client(stdio_server_params_other_cwd) as (read, write):
            async with ClientSession(read, write) as session:
                await asyncio.wait_for(session.initialize(), timeout=SESSION_INIT_TIMEOUT)
                result = await asyncio.wait_for(
                    session.call_tool("memory_context", {"last": 1}),
                    timeout=TOOL_CALL_TIMEOUT,
                )
                data = _tool_result_json(result)

        assert data["status"] == "ok"
        assert data["data"]["project"]["name"] == isolated_stdio_env["project_name"]

    @pytest.mark.asyncio
    async def test_stdio_sync_submit_then_status_round_trip(self, stdio_server_params: StdioServerParameters):
        async with open_stdio_client_session(stdio_server_params) as session:
            submit_result = await asyncio.wait_for(
                session.call_tool(
                    "memory_sync_submit",
                    {
                        "summary": {
                            "session_id": "test-stdio-roundtrip",
                            "timestamp": "2026-03-18T12:00:00Z",
                            "intent": "Test stdio round trip",
                            "work_attempted": ["Test"],
                            "outcomes": [{"type": "success", "description": "Test"}],
                            "fidelity": "summary",
                        },
                        "extraction": {"extractions": []},
                        "options": {"skip_quality_check": True},
                    },
                ),
                timeout=TOOL_CALL_TIMEOUT,
            )
            submit_data = _tool_result_json(submit_result)

            assert submit_data["status"] == "ok"
            job_id = submit_data["data"]["job_id"]
            assert job_id.startswith("sync-job-")

            status_result = await asyncio.wait_for(
                session.call_tool("memory_sync_status", {"job_id": job_id}),
                timeout=TOOL_CALL_TIMEOUT,
            )
            status_data = _tool_result_json(status_result)

        assert status_data["status"] == "ok"
        assert status_data["data"]["job_id"] == job_id
        assert status_data["data"]["status"] in {"queued", "running"}

    @pytest.mark.asyncio
    async def test_stdio_sync_list_shows_submitted_job(self, stdio_server_params: StdioServerParameters):
        async with open_stdio_client_session(stdio_server_params) as session:
            submit_result = await asyncio.wait_for(
                session.call_tool(
                    "memory_sync_submit",
                    {
                        "summary": {
                            "session_id": "test-stdio-list",
                            "timestamp": "2026-03-18T12:00:00Z",
                            "intent": "Test stdio list",
                            "work_attempted": ["Test"],
                            "outcomes": [{"type": "success", "description": "Test"}],
                            "fidelity": "summary",
                        },
                        "extraction": {"extractions": []},
                        "options": {"skip_quality_check": True},
                    },
                ),
                timeout=TOOL_CALL_TIMEOUT,
            )
            submit_data = _tool_result_json(submit_result)
            job_id = submit_data["data"]["job_id"]

            list_result = await asyncio.wait_for(
                session.call_tool("memory_sync_list", {}),
                timeout=TOOL_CALL_TIMEOUT,
            )
            list_data = _tool_result_json(list_result)

        assert list_data["status"] == "ok"
        assert any(job["job_id"] == job_id for job in list_data["data"]["jobs"])

    @pytest.mark.asyncio
    async def test_stdio_sync_result_rejects_non_terminal_job(self, stdio_server_params: StdioServerParameters):
        async with open_stdio_client_session(stdio_server_params) as session:
            submit_result = await asyncio.wait_for(
                session.call_tool(
                    "memory_sync_submit",
                    {
                        "summary": {
                            "session_id": "test-stdio-result",
                            "timestamp": "2026-03-18T12:00:00Z",
                            "intent": "Test non-terminal result",
                            "work_attempted": ["Test"],
                            "outcomes": [{"type": "success", "description": "Test"}],
                            "fidelity": "summary",
                        },
                        "extraction": {"extractions": []},
                        "options": {"skip_quality_check": True},
                    },
                ),
                timeout=TOOL_CALL_TIMEOUT,
            )
            submit_data = _tool_result_json(submit_result)
            job_id = submit_data["data"]["job_id"]

            result = await asyncio.wait_for(
                session.call_tool("memory_sync_result", {"job_id": job_id}),
                timeout=TOOL_CALL_TIMEOUT,
            )
            data = _tool_result_json(result)

        assert data["status"] == "error"
        assert data["type"] == "validation"
        assert "not complete" in data["message"].lower()
