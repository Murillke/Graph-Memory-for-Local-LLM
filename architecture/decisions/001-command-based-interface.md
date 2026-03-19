# ADR 001: Command-Based Interface

**Date:** 2026-03-04

**Status:** Accepted

---

## Context

AI agents need to interact with the memory system, but vague instructions like "sync your memory" get lost in conversation. We need a clear, unambiguous way for users to instruct AI agents to use the memory system.

**Problem:**
- User says: "Sync your memory after a few interchanges"
- AI agent: Doesn't understand when or how to sync
- Result: Memory system not used

**Requirements:**
1. Clear, unambiguous instructions
2. Impossible for AI agents to miss
3. Self-contained (all info in one place)
4. Easy for autonomous agents to integrate
5. Platform-specific (Windows/Linux/Mac)

---

## Decision

We will use **explicit command files** in the root directory as the primary interface for AI agents.

**Structure:**
- Root directory IS `/mem/`
- Command files: `init.md`, `sync.md`, `remember.md`, etc.
- Each file contains complete step-by-step instructions
- Platform-specific commands (Windows PowerShell and Linux/Mac bash)

**Usage:**
```
User: "follow mem/sync.md"
AI: *reads my-project/mem/sync.md*
AI: *executes step-by-step instructions*
AI: *reports results*
```

---

## Alternatives Considered

### Alternative 1: Natural Language Instructions

**Approach:** User says "sync your memory" and AI figures it out

**Pros:**
- Natural for users
- Flexible

**Cons:**
- ❌ Ambiguous - AI doesn't know when/how
- ❌ Gets lost in conversation
- ❌ Inconsistent execution
- ❌ Hard for autonomous agents

**Rejected:** Too ambiguous

### Alternative 2: CLI Tool

**Approach:** Create a CLI tool like `mem sync`

**Pros:**
- Clear commands
- Standard CLI patterns

**Cons:**
- ❌ Requires installation
- ❌ AI agents can't easily discover commands
- ❌ No self-contained instructions
- ❌ Platform-specific issues

**Rejected:** Not AI-agent friendly

### Alternative 3: API Endpoints

**Approach:** REST API for memory operations

**Pros:**
- Standard HTTP interface
- Language-agnostic

**Cons:**
- ❌ Requires server running
- ❌ Network dependency
- ❌ Overkill for local usage
- ❌ AI agents need API documentation

**Rejected:** Too complex for local use

### Alternative 4: Python Functions

**Approach:** Import Python module and call functions

**Pros:**
- Programmatic
- Type-safe

**Cons:**
- ❌ Requires Python knowledge
- ❌ AI agents can't easily execute
- ❌ Not self-documenting
- ❌ Platform-specific setup

**Rejected:** Not accessible to AI agents

---

## Rationale

**Why command files work:**

**1. Crystal Clear**
- "follow mem/sync.md" is explicit and unambiguous
- Clear path: `my-project/mem/sync.md`
- No confusion about what to do

**2. Impossible to Miss**
- Explicit file reference with path
- Can't be lost in conversation
- `mem/` prefix makes it obvious

**3. Self-Contained**
- All instructions in one file
- No need to search multiple docs
- Complete workflow in each command

**4. Discoverable**
- `ls mem/*.md` shows all commands
- `mem/index.md` lists everything
- Easy to explore

**5. Autonomous-Friendly**
- Easy to parse: "follow mem/X.md"
- Easy to execute: read `mem/X.md`, follow steps
- Easy to verify: expected output shown

**6. Platform-Specific**
- Windows PowerShell commands
- Linux/Mac bash commands
- No platform confusion

**7. Human-Readable**
- Markdown format
- Clear structure
- Examples and troubleshooting

**8. Non-Invasive**
- Lives in `mem/` subdirectory
- Doesn't clutter project root
- Easy to add/remove

---

## Implementation

**When installed in user's project:**
```
my-project/              # User's project root
├── src/                 # User's code
├── package.json         # User's config
└── mem/                 # Memory system (installed here)
    ├── init.md          # Initialize system
    ├── sync.md          # Sync conversation
    ├── remember.md      # Query your memory
    ├── remember-external.md  # Query other projects
    ├── search.md        # Advanced search
    ├── search-external.md    # Cross-project search
    ├── verify.md        # Verify integrity
    ├── export.md        # Export history
    ├── status.md        # Check status
    ├── index.md         # Command list
    ├── scripts/         # Python scripts
    ├── tools/           # Library code
    └── memory/          # Databases
```

**This repository (llm_memory):**
```
llm_memory/              # Development repository
├── init.md              # Command files (in root for dev)
├── sync.md
├── remember.md
├── scripts/             # Python scripts
├── tools/               # Library code
└── architecture/        # Architecture docs
```

**File structure:**
```markdown
# command.md - Title

**One-line description**

## What This Does
...

## Prerequisites
...

## Instructions

### Step 1: ...

**Windows:**
```powershell
command
```

**Linux/Mac:**
```bash
command
```

**Expected output:**
```
output
```

## Troubleshooting
...
```

---

## Consequences

**Positive:**
- ✅ Clear, unambiguous instructions
- ✅ AI agents can't miss commands
- ✅ Self-contained documentation
- ✅ Easy to maintain
- ✅ Platform-specific support
- ✅ Autonomous-agent friendly
- ✅ Non-invasive to project structure
- ✅ Easy to install/uninstall

**Negative:**
- ⚠️ Adds `mem/` subdirectory to project
- ⚠️ Duplication between command files and docs (acceptable trade-off)
- ⚠️ Requires Python installation

**Neutral:**
- Command files are markdown (not executable scripts)
- Lives in `mem/` subdirectory (not root)
- User must say "mem/sync.md" not just "sync.md"

---

## Related Decisions

- ADR 002: mem/ Subdirectory Structure (why mem/ not root)
- ADR 003: Multi-Project Architecture (why shared database)
- ADR 004: Command File Format (why markdown not scripts)

---

## References

- User feedback: "You can't understand stuff like sync your memory after a few interchanges"
- User suggestion: "What about creating a kind of 'command-like' setup so I can tell you follow mem/sync.md"

