"""Bootstrap tests for the MCP server module."""

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

import importlib.util

import pytest

from mcp_server.memory_mcp import build_server


MCP_AVAILABLE = importlib.util.find_spec("mcp") is not None


@pytest.mark.skipif(not MCP_AVAILABLE, reason="mcp package not installed")
def test_build_server_registers_fastmcp_server():
    server = build_server()
    assert server is not None

