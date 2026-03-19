# Multi-CLI Integration Summary

**Status:** Research Complete - Unified Strategy Recommended

## Overview

This document consolidates integration strategies for connecting the memory system with multiple AI coding CLIs. After reviewing individual designs, we recommend a **unified MCP-first approach** that works across all CLIs.

**Network baseline:** MCP supports both local and private-network deployments from the beginning, but remains deny-by-default. Only explicitly allowlisted private subnets or VPN paths are allowed. Public internet exposure is out of scope. See [MCP Network Posture](./MCP-NETWORK-POSTURE.md).

For home/private use, the intended baseline is:

- VPN membership is the primary network access boundary
- TLS protects traffic in transit
- app-level client auth is optional future hardening, not a day-one requirement

## Supported CLIs

| CLI | MCP Support | Hooks | Slash Commands | AGENTS.md/Rules |
|-----|-------------|-------|----------------|-----------------|
| **Augment CLI** | ✅ Native | ✅ SessionStart/End | ✅ Custom commands | ✅ Via workspace |
| **Claude Code** | ✅ Native | ✅ Full lifecycle | ✅ ~/.claude/commands | ✅ CLAUDE.md |
| **Copilot CLI** | ✅ Native | ✅ Pre/Post hooks | ✅ Custom agents | ✅ Custom instructions |
| **Codex CLI** | ✅ Native | ✅ via Skills | ✅ Skills | ✅ AGENTS.md |
| **Gemini CLI** | ✅ Native | ✅ Hooks | ✅ Commands | ✅ Context |

## Unified Architecture

All integrations share a common backend:

```
┌──────────────────────────────────────────────────────────────────┐
│  Augment    Claude Code    Copilot CLI    Codex CLI    Gemini   │
│    CLI                                                           │
└────┬─────────────┬──────────────┬─────────────┬─────────────┬────┘
     │             │              │             │             │
     ▼             ▼              ▼             ▼             ▼
┌──────────────────────────────────────────────────────────────────┐
│                    MCP Server (Python)                            │
│  - Uses existing scripts (query_memory.py, import_conversation)  │
│  - Reads mem.config.json (config-first)                          │
│  - Provides: remember, recall, get_context tools                 │
└──────────────────────────────────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Memory System                                  │
│  SQLite + Graph Database + OpenTimestamps                        │
└──────────────────────────────────────────────────────────────────┘
```

## Deployment Modes

### Localhost

- MCP server runs on the same machine as the CLI
- memory files stay on that machine
- no inbound network listener is required beyond local process transport

### Private Network / VPN

- MCP server may run on a private Linux host
- clients connect only from approved private subnets or VPN
- the server host owns the SQLite and graph database files
- this is a first-class deployment mode, not a future add-on

### Public Internet

- not supported by this baseline
- not recommended without additional authn/authz and service hardening

## What's Required (Common Across All)

### 1. Universal MCP Server (`mcp-server/memory_mcp.py`)

```python
#!/usr/bin/env python3
"""Illustrative MCP server sketch for the memory system.

This snippet is architectural pseudocode, not drop-in runnable code.
Real implementation must use the repo's actual config and query APIs.
"""
import json
import sys
import os
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.config import load_config
from tools.graph_db import GraphDatabase

def get_project():
    """Get project from config (config-first pattern)."""
    config_path = os.environ.get("MEMORY_CONFIG", "mem.config.json")
    if os.path.exists(config_path):
        with open(config_path) as f:
            return json.load(f).get("project_name")
    return "default"

# Network posture:
# - stdio/local process remains supported
# - private-network hosting is supported from day one
# - only explicitly allowlisted private subnets may be enabled
# - public internet exposure is not supported by baseline policy
# - TLS is required in private-network mode
# - app-level client auth is optional future hardening for small home-use deployments

# Tool handlers using existing scripts
async def handle_recall(query: str, limit: int = 5):
    """Search memories using the repo's real query helpers/scripts."""
    # Pseudocode only:
    # 1. resolve project/config
    # 2. validate tool input
    # 3. call existing query script or importable helper
    # 4. return structured tool output
    return {"status": "not_implemented"}

async def handle_remember(content: str, category: str = "note"):
    """Store memory using existing store_interaction.py logic."""
    # Uses existing storage pipeline
    pass

# MCP protocol handling via stdio
def main():
    """Run MCP server on stdio."""
    # Standard MCP protocol implementation
    pass

if __name__ == "__main__":
    main()
```

### 2. Conversation Format Adapters

Each CLI has a different conversation format. We need adapters:

| CLI | Input Format | Adapter Script |
|-----|--------------|----------------|
| Augment | `{conversation: {userPrompt, agentTextResponse}}` | `convert_augment_conversation.py` |
| Claude Code | `{messages: [{role, content}]}` | `convert_claude_conversation.py` |
| Copilot CLI | TBD (needs research) | `convert_copilot_conversation.py` |
| Codex CLI | TBD (needs research) | `convert_codex_conversation.py` |

### 3. CLI-Specific Installers

Each CLI needs its own installer that:
1. Detects the CLI installation
2. Copies appropriate hooks/commands
3. Configures MCP server (if supported)
4. Updates CLI settings

## Implementation Priority

### Phase 1: Foundation (Week 1)
- [ ] Create universal MCP server (`mcp-server/memory_mcp.py`)
- [ ] Test with Claude Code (best MCP support)
- [ ] Document MCP server API

### Phase 2: Augment Integration (Week 2)
- [ ] Complete hooks (SessionStart, SessionEnd)
- [ ] Create conversation adapter
- [ ] Build installer

### Phase 3: Multi-CLI Expansion (Week 3-4)
- [ ] Claude Code: Commands, MCP, hooks
- [ ] Copilot CLI: Verify capabilities, implement
- [ ] Codex CLI: Skills/MCP integration

### Phase 4: Polish (Week 5)
- [ ] Universal installer that detects all CLIs
- [ ] Documentation
- [ ] Testing across platforms

## Critical Findings from Reviews

### Issues Discovered

1. **All designs violated config-first pattern** - Fixed by using shared MCP server
2. **Non-existent classes referenced** - Must use existing `GraphDatabase`, not fictional `MemoryStore`
3. **Conversation formats undocumented** - Need to research each CLI's actual format
4. **Copilot CLI capabilities unverified** - Need to confirm MCP/hooks support
5. **No error handling** - All designs lacked proper error handling
6. **Network posture was underspecified** - default-deny and private-subnet-only policy must be documented up front

### Recommended Approach

**Start with AGENTS.md/CLAUDE.md injection** for quick wins:
- Works without MCP server
- Uses existing scripts
- Follows config-first pattern
- No conversation format issues

Then add MCP server for richer integration.

For network access, support both of these from the start:

1. local stdio MCP
2. private LAN/VPN allowlist mode

Do not add any public-network mode.

## Related Documents

- [Augment Integration Design](./AUGMENT-INTEGRATION-DESIGN.md) - Detailed Augment-specific design
- [Claude Code Integration Design](./CLAUDE-CODE-INTEGRATION-DESIGN.md) - Claude Code options
- [Copilot CLI Integration Design](./COPILOT-CLI-INTEGRATION-DESIGN.md) - Copilot CLI options
- [Codex CLI Integration Design](./CODEX-CLI-INTEGRATION-DESIGN.md) - Codex CLI options
- [MCP Network Posture](./MCP-NETWORK-POSTURE.md) - deny-by-default private deployment policy

## Success Criteria

- [ ] One MCP server works across 3+ CLIs
- [ ] Context injection at session start for all CLIs
- [ ] Conversation sync at session end for 2+ CLIs
- [ ] One-command installer for each CLI
- [ ] Works on macOS and Linux
