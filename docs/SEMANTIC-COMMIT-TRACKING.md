# Semantic Commit Tracking

> **STATUS: EXPERIMENTAL** - Git hook and code graph DB work. LLM semantic correlation untested.
> See [docs/STATUS.md](STATUS.md) for current feature maturity.

Semantic Commit Tracking is a **commit-scoped knowledge graph** that links code changes to conversation context. It captures commits, files, and functions, enabling powerful code evolution analysis.

## Concept

**Same Database, Different Tables:**
- **Conversation Tables** - Entity, Interaction, RELATES_TO, EXTRACTED
- **Code Tables** - Commit, File, Function, MODIFIED, ADDED_FUNCTION, etc.
- **All in** `{project}.kuzu` - Single database file!

**No Physical Links!** The graphs are linked **semantically via LLM** on-demand.

## Schema

**Nodes:**
- `Commit` - Git commits (hash, message, author, timestamp, branch)
- `File` - Files in repository (path, language, extension)
- `Function` - Functions/methods/classes (name, signature, location)

**Relationships:**
- `MODIFIED` - Commit modified file
- `ADDED_FUNCTION` - Commit added function
- `REMOVED_FUNCTION` - Commit removed function
- `MODIFIED_FUNCTION` - Commit modified function
- `CONTAINS` - File contains function

## Setup

### 1. Install Git Hook

```powershell
{PYTHON_PATH} scripts\install_git_hook.py
```

**Replace `{PYTHON_PATH}` with the value from `mem.config.json`.**

This creates `.git/hooks/post-commit` that automatically captures code changes after each commit.

### 2. Make a Commit

```bash
git add .
git commit -m "Add new feature"
```

The hook runs automatically and stores commit data in the semantic commit graph!

## Usage

### Link Commit to Conversations

Find conversations related to a commit:

```powershell
{PYTHON_PATH} scripts\conversations_for_commit.py --commit abc123 --project {PROJECT}
```

**Output:**
```
85% - OpenTimestamps integration (Feature)
  UUID: uuid-xxx
  Created: 2026-03-10 00:15
  Summary: Integrated official Python client...
  Reasoning: Temporal: 0.2h before commit (100%) | Semantic: 80% | Entity name in commit message
  Interaction: uuid-yyy
  User message: Can you integrate OpenTimestamps...
```

### Show Code Changes During Conversation

See what code changed during a conversation:

```powershell
{PYTHON_PATH} scripts\code_during_conversation.py --interaction uuid-xxx --project {PROJECT}
```

**Output:**
```
Commits in time window (3):

abc123 - 0.5h after
  Add OpenTimestamps integration
  by David at 2026-03-10 00:20
  Files (5):
    added    tools/timestamp_proof_official.py
    modified tools/timestamp_proof.py
    ... and 3 more
```

### Analyze Specific Commit

Get detailed correlation analysis:

```powershell
{PYTHON_PATH} scripts\link_code_to_memory.py --commit abc123 --min-confidence 40 --project {PROJECT}
```

## Confidence Scoring

The system calculates confidence scores (0-100%) based on:

**Temporal Proximity (60% weight):**
- Within 30 minutes: 100%
- Within 2 hours: 80%
- Within 6 hours: 60%
- Within 12 hours: 40%
- Beyond 12 hours: 20%

**Semantic Matching (40% weight):**
- Entity name in commit message: +50%
- Multiple matching keywords: +30%
- Keywords in file paths: +10%

**Example:**
```
Confidence: 85%
- Temporal: 0.2h before commit (100%)
- Semantic: 80%
  - Entity name 'OpenTimestamps' in commit message
  - 5 matching keywords
  - Keyword 'timestamp' in file path
```

## When to Use

**Good for:**
- "What conversations led to this commit?"
- "What code changed when we discussed X?"
- "Show me the evolution of feature Y"
- "Which commits implemented this entity?"

**Not good for:**
- Real-time code analysis (use IDE)
- Detailed function-level tracking (coming later)
- Cross-repository analysis (single repo only)

## Tips

### 1. Run sync.md Regularly

The semantic commit graph links to conversations. If you don't run `sync.md`, there's nothing to link to!

**Best practice:**
- Sync before committing major features
- Sync after long coding sessions
- Sync at end of day

### 2. Write Descriptive Commit Messages

Better commit messages = better semantic matching:

**Good:**
```
Add OpenTimestamps integration with nonce and Merkle tree
```

**Bad:**
```
Fix stuff
```

### 3. Adjust Confidence Threshold

Default is 50%. Adjust based on your needs:

```powershell
# Strict (only high confidence)
--min-confidence 70

# Permissive (show all possibilities)
--min-confidence 30
```

### 4. Check Time Windows

If no entities found, check the time window:

```powershell
# Wider window (24 hours)
--window-hours 24

# Narrower window (6 hours)
--window-hours 6
```

## Limitations

**Current:**
- File-level tracking only (no function detection yet)
- Single repository only
- No cross-branch analysis
- No merge commit handling

**Future:**
- Function-level change detection (AST parsing)
- Multi-repository support
- Branch comparison
- Refactoring detection

## Troubleshooting

**"Commit not found"**
- Make sure the git hook is installed
- Check if commit was made after hook installation
- Verify database exists: `memory/{PROJECT}.graph`

**"No entities found in time window"**
- Run `sync.md` to capture recent conversations
- Increase `--window-hours`
- Check if conversation graph has data

**"Low confidence scores"**
- Normal if no sync.md was run before commit
- Improve commit messages to include entity names
- Run sync.md more frequently

## Advanced

### Query Semantic Commit Graph Directly

```python
import kuzu

# Same database as conversation graph!
db = kuzu.Database('memory/{PROJECT}.graph', read_only=True)  # Replace {PROJECT}
conn = kuzu.Connection(db)

# Get recent commits
result = conn.execute("""
    MATCH (c:Commit)
    RETURN c.hash, c.message, c.timestamp
    ORDER BY c.timestamp DESC
    LIMIT 10
""")

# Query both graphs together!
result = conn.execute("""
    MATCH (c:Commit), (e:Entity)
    WHERE c.timestamp >= e.created_at - INTERVAL 2 HOURS
      AND c.timestamp <= e.created_at + INTERVAL 2 HOURS
    RETURN c.hash, c.message, e.name
""")
```

### Disable Hook

Delete or rename the hook:

```bash
rm .git/hooks/post-commit
# or
mv .git/hooks/post-commit .git/hooks/post-commit.disabled
```

---

## Pre-Commit Sync Gate

The pre-commit hook ensures you sync conversations before committing code.

### Install

```powershell
{PYTHON_PATH} scripts/install_precommit_hook.py
```

### How It Works

The hook validates two conditions:

1. **Token file exists:** `tmp/_____COMMIT_BLOCKED_UNTIL_SYNC_COMPLETES_____.tmp`
2. **Recent sync:** Last ExtractionBatch within 2.5 minutes

If either fails, commit is blocked with instructions.

### Workflow

```
Work on code + conversations
    |
    v
Run sync.md (creates ExtractionBatch + token)
    |
    v
Run: {PYTHON_PATH} scripts/sync.py --project {PROJECT} --complete --agent {AGENT}
    |
    v
Commit immediately (within 2.5 minutes)
    |
    v
Hook validates, allows, deletes token
```

### Heartbeat Batches

If sync finds nothing to extract (`unprocessed == 0`), it creates a **heartbeat** ExtractionBatch as a semantic sync checkpoint. This proves "I ran sync, nothing was pending."

---

**Semantic Commit Tracking enables powerful code evolution analysis without polluting the conversation graph!** [*]

