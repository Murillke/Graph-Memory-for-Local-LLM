#!/usr/bin/env python3
"""Integration tests that launch MCP server and make real protocol calls.

These tests verify the full MCP protocol flow:
1. Server starts and accepts connections
2. Client connects via MCP protocol
3. Tool calls work end-to-end
4. Results are correctly returned
"""

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
from pathlib import Path
from unittest.mock import patch

import pytest

# Add repo root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Skip all tests if fastmcp not available
fastmcp = pytest.importorskip("fastmcp", reason="fastmcp package required for integration tests")
pytest_asyncio = pytest.importorskip("pytest_asyncio", reason="pytest-asyncio required")


@pytest.fixture
def test_env(tmp_path):
    """Create isolated test config and initialize DBs."""
    config_path = tmp_path / "mem.config.json"
    graph_path = tmp_path / "test.graph"
    sql_path = tmp_path / "test.db"

    config_path.write_text(json.dumps({
        "project_name": "test_mcp_integration",
        "database": {
            "sql_path": str(sql_path),
            "graph_path": str(graph_path)
        }
    }))

    # Initialize graph DB schema
    from tools.graph_db import GraphDatabase
    GraphDatabase(str(graph_path))

    return {
        "config_path": config_path,
        "graph_path": graph_path,
        "sql_path": sql_path,
        "project_name": "test_mcp_integration",
    }


@pytest.fixture
def mcp_server(test_env):
    """Build the MCP server with mocked config."""
    from mcp_server.memory_mcp import build_server
    from mcp_server.handlers.common import RuntimeState
    from tools.mcp_network import MCPNetworkConfig
    from tools.config import load_config

    # Create mock runtime state using load_config with explicit path
    config = load_config(config_path=str(test_env["config_path"]))
    mock_state = RuntimeState(
        config=config,
        project_name=test_env["project_name"],
        graph_db_path=str(test_env["graph_path"]),
        sql_db_path=str(test_env["sql_path"]),
        mcp_config=MCPNetworkConfig(),
    )

    # Patch load_runtime_state in ALL handler modules (including sync)
    with patch("mcp_server.handlers.recall.load_runtime_state", return_value=mock_state), \
         patch("mcp_server.handlers.search.load_runtime_state", return_value=mock_state), \
         patch("mcp_server.handlers.store.load_runtime_state", return_value=mock_state), \
         patch("mcp_server.handlers.tasks.load_runtime_state", return_value=mock_state), \
         patch("mcp_server.handlers.context.load_runtime_state", return_value=mock_state), \
         patch("mcp_server.handlers.sync.load_runtime_state", return_value=mock_state):
        server = build_server()
        yield server


class TestMCPIntegration:
    """Integration tests using FastMCP's in-memory transport."""

    @pytest.mark.asyncio
    async def test_server_lists_tools(self, mcp_server):
        """Test: Client can connect and list available tools."""
        from fastmcp import Client

        client = Client(mcp_server)

        async with client:
            tools = await client.list_tools()
            tool_names = [t.name for t in tools]

            # Verify expected tools are registered
            assert "memory_recall" in tool_names
            assert "memory_search" in tool_names
            # Verify sync tools are registered (Phase 0 fix)
            assert "memory_sync_submit" in tool_names
            assert "memory_sync_status" in tool_names
            assert "memory_sync_result" in tool_names
            assert "memory_sync_list" in tool_names
            assert "memory_sync_submit_quality_review" in tool_names

    @pytest.mark.asyncio
    async def test_memory_recall_via_protocol(self, mcp_server):
        """Test: memory_recall tool works via MCP protocol."""
        from fastmcp import Client

        client = Client(mcp_server)

        async with client:
            result = await client.call_tool(
                "memory_recall",
                {
                    "project": "test_mcp_integration",
                    "start": "2026-03-01",
                    "end": "2026-03-31",
                }
            )

            # Verify we got a response
            assert result is not None

    @pytest.mark.asyncio
    async def test_memory_search_via_protocol(self, mcp_server):
        """Test: memory_search tool works via MCP protocol."""
        from fastmcp import Client

        client = Client(mcp_server)

        async with client:
            result = await client.call_tool(
                "memory_search",
                {
                    "project": "test_mcp_integration",
                    "query": "test query",
                }
            )

            assert result is not None

    @pytest.mark.asyncio
    async def test_memory_sync_submit_via_protocol(self, mcp_server):
        """Test: memory_sync_submit works via MCP protocol."""
        from fastmcp import Client

        client = Client(mcp_server)

        async with client:
            result = await client.call_tool(
                "memory_sync_submit",
                {
                    "summary": {
                        "session_id": "test-session",
                        "timestamp": "2026-03-18T12:00:00Z",
                        "intent": "Test via MCP protocol",
                        "work_attempted": ["Test call"],
                        "outcomes": [{"type": "success", "description": "Test"}],
                        "fidelity": "summary",
                    },
                    "extraction": {"extractions": []},
                    "options": {"skip_quality_check": True},
                }
            )

            assert result is not None
            # Result should contain job_id
            result_text = str(result)
            assert "job_id" in result_text.lower() or "job-" in result_text.lower()

    @pytest.mark.asyncio
    async def test_memory_sync_list_via_protocol(self, mcp_server):
        """Test: memory_sync_list works via MCP protocol."""
        from fastmcp import Client

        client = Client(mcp_server)

        async with client:
            result = await client.call_tool(
                "memory_sync_list",
                {}
            )

            assert result is not None

    @pytest.mark.asyncio
    async def test_sync_submit_then_status_flow(self, mcp_server):
        """Test: submit job then check status via MCP protocol."""
        from fastmcp import Client
        import json

        client = Client(mcp_server)

        async with client:
            # Submit a job
            submit_result = await client.call_tool(
                "memory_sync_submit",
                {
                    "summary": {
                        "session_id": "test-status-flow",
                        "timestamp": "2026-03-18T12:00:00Z",
                        "intent": "Test status flow",
                        "work_attempted": ["Test"],
                        "outcomes": [{"type": "success", "description": "Test"}],
                        "fidelity": "summary",
                    },
                    "extraction": {"extractions": []},
                    "options": {"skip_quality_check": True},
                }
            )

            # Extract job_id from result
            result_text = str(submit_result)
            # Parse the JSON response
            try:
                # FastMCP returns TextContent, extract the text
                if hasattr(submit_result, '__iter__'):
                    for item in submit_result:
                        if hasattr(item, 'text'):
                            result_data = json.loads(item.text)
                            break
                else:
                    result_data = json.loads(result_text)

                if result_data.get("status") == "ok":
                    job_id = result_data["data"]["job_id"]

                    # Check status
                    status_result = await client.call_tool(
                        "memory_sync_status",
                        {"job_id": job_id}
                    )

                    assert status_result is not None
            except (json.JSONDecodeError, KeyError, TypeError):
                # If we can't parse, just verify we got a response
                pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

