#!/usr/bin/env python3
"""Thin wrapper so MCP clients can launch the server from mcp-server/."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mcp_server.memory_mcp import main


if __name__ == "__main__":
    raise SystemExit(main())

