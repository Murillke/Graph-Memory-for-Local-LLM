# Augment CLI Integration Design

**Goal:** Integrate the LLM Memory System with Augment CLI via MCP, Hooks, and Custom Commands.

**Status:** ✅ FINAL - Ready for Implementation (Updated with MCP Support)

---

## Executive Summary

Augment CLI provides **three** extension mechanisms that can transform our memory system into a **drop-in addon**:

1. **MCP Server** (PRIMARY) - Register memory tools via Model Context Protocol
2. **Hooks** - Intercept lifecycle events (session start/end, tool use)
3. **Custom Commands** - Slash commands for agent interaction (`/mem-sync`, `/mem-recall`)

**MCP is the recommended primary integration** as it provides the richest interaction model.

This document maps WHERE each mechanism fits and identifies WHAT'S MISSING for full operation.

---

## MCP Integration (PRIMARY - Recommended)

Augment fully supports MCP servers. This is the **preferred integration method** as it:
- Provides tools the agent can use autonomously
- Works identically to Claude Code, Codex, and other MCP-compatible CLIs
- Requires minimal configuration

**Network posture:** deployment may be local or on a private Linux/VPN host from the beginning, but it must remain deny-by-default. Only approved private subnets or VPN-only access are allowed. No open internet exposure. See [MCP Network Posture](./MCP-NETWORK-POSTURE.md).

### Configuration

Add to Augment settings (via Settings Panel or JSON import):

```json
{
  "mcpServers": {
    "memory": {
      "command": "{PYTHON_PATH}",
      "args": ["{PROJECT}/mcp-server/memory_mcp.py"],
      "cwd": "{PROJECT}",
      "env": {
        "MEM_CONFIG": "{PROJECT}/mem.config.json"
      }
    }
  }
}
```

`cwd` matters when `mem.config.json` uses relative database paths such as
`./memory/conversations.db` and `./memory/{project_name}.graph`. Without it, the
server may resolve those paths from the caller's workspace and appear empty.

This configuration assumes a local process launch. If an Augment setup connects to a private MCP host, that host should still follow the same baseline:

- deny all non-local access by default
- allow only explicitly configured private subnets
- no public IP exposure
- use VPN when crossing untrusted networks
- treat private-network hosting as a supported deployment mode, not an exception
- require TLS in private-network mode
- allow app-level client auth as optional hardening for larger or less-trusted private setups

The important constraint is not "same machine" versus "remote machine"; it is "private trusted network only" versus "public internet". 

### MCP Tools Provided

| Tool | Description |
|------|-------------|
| `memory_recall` | Query memories by topic/keywords |
| `memory_search` | Search entities, facts, relationships |
| `memory_remember` | Store new information |
| `memory_context` | Get project context and recent memories |
| `memory_tasks` | View/manage pending tasks |

### Benefits Over Hooks/Commands

- Agent can decide WHEN to use memory tools
- No manual slash commands needed
- Consistent behavior across all MCP-compatible CLIs
- Richer tool interaction (structured input/output)

---

## Hooks Integration (Supplementary)

Even with MCP, hooks provide value for **automatic** behavior:

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Augment CLI                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  SessionStart Hook ────► memory:load-context.sh              │
│       │                   └── Inject relevant memories       │
│       │                                                      │
│  Agent Conversation                                          │
│       │                                                      │
│  /mem-recall ──────────► .augment/commands/mem-recall.md     │
│  /mem-search ──────────► .augment/commands/mem-search.md     │
│  /mem-tasks  ──────────► .augment/commands/mem-tasks.md      │
│       │                                                      │
│  SessionEnd Hook ──────► memory:sync-conversation.sh         │
│                           └── Auto-extract and store         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## WHERE Hooks Fit (Supplementary)

Hooks complement MCP by providing automatic behavior:

### 1. SessionStart Hook - **AUTO-LOAD CONTEXT**

**Purpose:** Inject relevant memories when a conversation begins.

**Implementation:**
```json
{
  "hooks": {
    "SessionStart": [{
      "hooks": [{
        "type": "command",
        "command": "/path/to/memory/hooks/session-start.sh",
        "timeout": 5000
      }],
      "metadata": {
        "includeUserContext": true
      }
    }]
  }
}
```

**Hook Script (`session-start.sh`):**
```bash
#!/bin/bash
# SessionStart Hook - Load memory context at conversation start
set -euo pipefail

EVENT_DATA=$(cat)
WORKSPACE=$(echo "$EVENT_DATA" | jq -r '.workspace_roots[0] // empty')

# Validate workspace
if [ -z "$WORKSPACE" ] || [ ! -d "$WORKSPACE" ]; then
  echo "Memory: No workspace found" >&2
  exit 0  # Graceful exit - don't block session
fi

cd "$WORKSPACE"

# Check for memory system
if [ ! -f "mem.config.json" ]; then
  exit 0  # Not a memory-enabled project
fi

# Load config via Python (config-first pattern)
PROJECT=$(python3 -c "import json; print(json.load(open('mem.config.json'))['project_name'])" 2>/dev/null || echo "")
PYTHON_PATH=$(python3 -c "import json; print(json.load(open('mem.config.json')).get('python_path', 'python3'))" 2>/dev/null || echo "python3")

if [ -z "$PROJECT" ]; then
  exit 0  # Config incomplete
fi

# Query recent memories using query_memory.py (supports --last N)
# Note: recall.py requires date range, query_memory.py simpler for "recent"
# Output text is injected as context for agent
$PYTHON_PATH scripts/query_memory.py --project "$PROJECT" --last 10 --limit 5 2>/dev/null || exit 0
```

**What this enables:**
- Agent starts with awareness of recent work
- No manual `/recall` needed
- Continuous memory across sessions

---

### 2. SessionEnd Hook - **AUTO-SYNC CONVERSATIONS**

**Purpose:** Automatically sync the conversation to memory when session ends.

**Implementation:**
```json
{
  "hooks": {
    "SessionEnd": [{
      "hooks": [{
        "type": "command",
        "command": "/path/to/memory/hooks/session-end.sh",
        "timeout": 30000
      }],
      "metadata": {
        "includeConversationData": true
      }
    }]
  }
}
```

**Hook Script (`session-end.sh`):**
```bash
#!/bin/bash
# SessionEnd Hook - Auto-sync conversation to memory
set -euo pipefail

EVENT_DATA=$(cat)
WORKSPACE=$(echo "$EVENT_DATA" | jq -r '.workspace_roots[0] // empty')
CONV_ID=$(echo "$EVENT_DATA" | jq -r '.conversation_id')

# Validate workspace
if [ -z "$WORKSPACE" ] || [ ! -d "$WORKSPACE" ]; then
  exit 0  # Graceful exit
fi

cd "$WORKSPACE"

# Check for memory system
if [ ! -f "mem.config.json" ]; then
  exit 0
fi

# Load config
PROJECT=$(python3 -c "import json; print(json.load(open('mem.config.json'))['project_name'])" 2>/dev/null || echo "")
PYTHON_PATH=$(python3 -c "import json; print(json.load(open('mem.config.json')).get('python_path', 'python3'))" 2>/dev/null || echo "python3")

if [ -z "$PROJECT" ]; then
  exit 0
fi

# Save conversation to temp file (use TMPDIR for portability)
TMPDIR="${TMPDIR:-/tmp}"
CONV_FILE="$TMPDIR/augment-conv-$CONV_ID.json"
echo "$EVENT_DATA" | jq '.conversation' > "$CONV_FILE"

# Convert Augment format to memory system format and sync
# NOTE: This requires scripts/convert_augment_conversation.py (to be created)
$PYTHON_PATH scripts/convert_augment_conversation.py --input "$CONV_FILE" --output "$CONV_FILE.converted.json" 2>/dev/null || exit 0

# Import the converted conversation
$PYTHON_PATH scripts/import_conversation.py --project "$PROJECT" --file "$CONV_FILE.converted.json" --agent "augment-cli" 2>/dev/null || exit 0

# Cleanup temp files
rm -f "$CONV_FILE" "$CONV_FILE.converted.json" 2>/dev/null || true
```

**What this enables:**
- Zero-effort memory capture
- Every conversation automatically indexed
- No more forgetting to sync

---

### 3. Stop Hook - **REQUIRE SYNC BEFORE COMPLETE**

**Purpose:** Remind agent to sync important work before finishing.

```json
{
  "hooks": {
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": "/path/to/memory/hooks/stop-check.sh"
      }],
      "metadata": {
        "includeConversationData": true
      }
    }]
  }
}
```

---

## WHERE Custom Commands Fit

### Recommended Commands

| Command | File | Purpose |
|---------|------|---------|
| `/mem-recall` | `mem-recall.md` | Query memories by topic |
| `/mem-search` | `mem-search.md` | Search entities/facts |
| `/mem-tasks` | `mem-tasks.md` | View/manage TODO items |
| `/mem-sync` | `mem-sync.md` | Manually sync conversation |
| `/mem-status` | `mem-status.md` | Check memory system health |

### Example: `/mem-recall` Command

**File:** `.augment/commands/mem-recall.md`
```markdown
---
description: Recall memories related to a topic
argument-hint: [topic or question]
---

Query the memory system for information related to: $ARGUMENTS

Follow the workflow in `recall.md`:
1. Read mem.config.json for python_path and project_name
2. Write `$ARGUMENTS` to `tmp/search.txt`
3. Run: {PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --search-file tmp/search.txt
4. Present findings in a clear summary
```

---

## Review Findings (v1 → v2)

### Critical Issues Resolved:

| Issue | Resolution |
|-------|------------|
| ❌ Inline `jq` config reading | ✅ Now uses Python config loader |
| ❌ Non-existent `--format context` flag | ✅ Changed to `query_memory.py --last 10` |
| ❌ Non-existent `sync_memory.py` | ✅ Uses `import_conversation.py` pipeline |
| ❌ Missing workspace validation | ✅ Added validation with graceful exit |
| ❌ Hardcoded `/tmp` path | ✅ Uses `$TMPDIR` for portability |

### Known Limitations (Accepted):

1. **SessionEnd only captures last exchange** - Augment's `includeConversationData` doesn't provide full history. We accept partial sync.
2. **Windows not supported** - Hooks require bash/jq. Windows users must use manual sync.
3. **Code changes not stored** - `agentCodeResponse` is captured but not indexed into memory (future enhancement).

---

## WHAT'S MISSING for Full Operation

### Critical Gaps

| Gap | Description | Priority |
|-----|-------------|----------|
| **Universal MCP Server** | Create `mcp-server/memory_mcp.py` that works with Augment and all other MCP CLIs | **CRITICAL** |
| **Conversation export format** | Augment provides `conversation.agentCodeResponse` and `conversation.userPrompt` but we need to map this to our sync format | HIGH |
| **Installer script** | No automated setup for MCP/hooks/commands | HIGH |
| **Settings.json generator** | Need to generate Augment settings with correct paths and MCP config | MEDIUM |
| **Context injection format** | SessionStart output needs specific format for agent ingestion | MEDIUM |
| **Error handling** | Hook failures should degrade gracefully | LOW |

### 1. Conversation Format Mapping

**Augment provides:**
```json
{
  "conversation": {
    "userPrompt": "Add error handling...",
    "agentTextResponse": "I'll add comprehensive...",
    "agentCodeResponse": [{"path": "...", "changeType": "edit", "content": "..."}]
  }
}
```

**We need:**
```json
{
  "messages": [
    {"role": "user", "content": "Add error handling..."},
    {"role": "assistant", "content": "I'll add comprehensive..."}
  ],
  "file_changes": [...]
}
```

**Solution:** Create `scripts/convert_augment_conversation.py` adapter.

---

### 2. Installer Script

**Proposed:** `install-augment-integration.sh`

```bash
#!/usr/bin/env bash
# Memory System - Augment Integration Installer

MEMORY_ROOT="$(pwd)"
AUGMENT_USER_DIR="$HOME/.augment"
AUGMENT_COMMANDS="$AUGMENT_USER_DIR/commands"
AUGMENT_HOOKS="$AUGMENT_USER_DIR/hooks"
AUGMENT_SETTINGS="$AUGMENT_USER_DIR/settings.json"

# Create directories
mkdir -p "$AUGMENT_COMMANDS" "$AUGMENT_HOOKS"

# Copy hook scripts
cp "$MEMORY_ROOT/augment/hooks/"*.sh "$AUGMENT_HOOKS/"
chmod +x "$AUGMENT_HOOKS/"*.sh

# Copy command definitions
cp "$MEMORY_ROOT/augment/commands/"*.md "$AUGMENT_COMMANDS/"

# Generate settings.json (merge with existing if present)
python3 "$MEMORY_ROOT/scripts/generate_augment_settings.py" \
  --hooks-dir "$AUGMENT_HOOKS" \
  --output "$AUGMENT_SETTINGS"

echo "✅ Memory system integrated with Augment CLI"
echo "   Hooks: $AUGMENT_HOOKS"
echo "   Commands: $AUGMENT_COMMANDS"
echo "   Settings: $AUGMENT_SETTINGS"
```

---

## Required New Scripts

Before implementation, these scripts must be created:

### 1. `scripts/convert_augment_conversation.py`

**Purpose:** Convert Augment conversation format to memory system format.

**Input (Augment):**
```json
{
  "userPrompt": "Add error handling...",
  "agentTextResponse": "I'll add comprehensive...",
  "agentCodeResponse": [{"path": "...", "changeType": "edit", "content": "..."}]
}
```

**Output (Memory System):**
```json
{
  "messages": [
    {"role": "user", "content": "Add error handling..."},
    {"role": "assistant", "content": "I'll add comprehensive..."}
  ]
}
```

**Interface:**
```
python3 scripts/convert_augment_conversation.py --input /tmp/conv.json --output /tmp/conv.converted.json
```

### 2. `scripts/generate_augment_settings.py`

**Purpose:** Generate or merge Augment settings.json with memory hooks.

**Interface:**
```
python3 scripts/generate_augment_settings.py --hooks-dir ~/.augment/hooks --output ~/.augment/settings.json
```

---

## Implementation Phases

### Phase 1: Custom Commands (Quick Win)
- Create `.augment/commands/` directory in memory repo
- Add `mem-recall.md`, `mem-search.md`, `mem-tasks.md`
- Test with `auggie command mem-recall "topic"`
- **Effort:** 2-3 hours

### Phase 2: SessionEnd Hook (Auto-Sync)
- Create `hooks/session-end.sh`
- Create `scripts/convert_augment_conversation.py`
- Configure in settings.json
- **Effort:** 4-6 hours

### Phase 3: SessionStart Hook (Context Loading)
- Create `hooks/session-start.sh`
- Define context output format
- Test with real sessions
- **Effort:** 3-4 hours

### Phase 4: Installer & Distribution
- Create `install-augment-integration.sh`
- Create `scripts/generate_augment_settings.py`
- Documentation and testing
- **Effort:** 2-3 hours

---

## File Structure (Proposed)

```
llm-memory/
├── augment/                    # NEW - Augment integration
│   ├── commands/               # Custom slash commands
│   │   ├── mem-recall.md
│   │   ├── mem-search.md
│   │   ├── mem-tasks.md
│   │   ├── mem-sync.md
│   │   └── mem-status.md
│   ├── hooks/                  # Hook scripts
│   │   ├── session-start.sh
│   │   ├── session-end.sh
│   │   └── stop-check.sh
│   └── install.sh              # Installer
├── scripts/
│   ├── convert_augment_conversation.py  # NEW
│   └── generate_augment_settings.py     # NEW
└── docs/
    └── AUGMENT-INTEGRATION-DESIGN.md    # This document
```

---

## Open Questions

1. **Does SessionStart stdout get injected as system context or user message?**
   - Docs say "stdout added as context for agent"
   - Need to test actual behavior

2. **Can we access full conversation history, not just last exchange?**
   - `includeConversationData` only shows last userPrompt/agentResponse
   - May need to accumulate across session

3. **How do workspace commands interact with user commands?**
   - If both exist, workspace takes precedence
   - Should memory commands be workspace or user level?

4. **What's the timeout limit for hooks?**
   - Default 60s, configurable
   - Memory operations may need higher timeout

---

## Success Criteria

- [ ] MCP server registered and tools accessible to agent
- [ ] `/mem-recall topic` works from any conversation
- [ ] Sessions automatically sync to memory on end
- [ ] Agent has context of recent work at session start
- [ ] One-command installation: `./augment/install.sh`
- [ ] Works across macOS/Linux (Windows TBD)

---

## Related

- [Augment MCP Documentation](https://docs.augmentcode.com/setup-augment/mcp)
- [Augment Hooks Documentation](https://docs.augmentcode.com/cli/hooks)
- [Augment Custom Commands](https://docs.augmentcode.com/cli/custom-commands)
- `sync.md` - Memory sync workflow
- `recall.md` - Memory recall workflow
