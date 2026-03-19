# LLM Memory System

**Persistent, cryptographically-verified memory for AI assistants across long conversations.**

Store conversations, extract knowledge, and query facts with full cryptographic proof of provenance.

---

## LLMs: Start Here

**READ THIS FIRST:** [LLM-INSTRUCTIONS.md](LLM-INSTRUCTIONS.md)

This file contains everything you need to operate this memory system autonomously.

---

## Quick Start

```bash
git clone <repo> && cd llm_memory
pip install -r requirements.txt
# Done! No API keys, no config. Just works.
```

**Workflow files (your public API):**
- **[sync.md](sync.md)** - Store conversations and knowledge
- **[remember.md](remember.md)** - Query knowledge
- **[history.md](history.md)** - View conversation history

**Full instructions:** [LLM-INSTRUCTIONS.md](LLM-INSTRUCTIONS.md)

---

## Mental Model

| Layer | Purpose | Storage |
|-------|---------|---------|
| **SQL** | Audit log of raw conversations | `memory/conversations.db` |
| **Graph** | Extracted knowledge (entities + facts) | `memory/{project}.graph/` |

| Workflow | When to Use |
|----------|-------------|
| `dump.md` | Save conversation fast (no extraction) |
| `sync.md` | Save + extract knowledge (full pipeline) |
| `remember.md` | Query knowledge graph |
| `recall.md` | Time-based recall ("what did I know on March 5?") |
| `verify.md` | Verify cryptographic integrity |

**Precedence rule:** When docs conflict, `LLM-INSTRUCTIONS.md` and `docs/EXTRACTION-FORMAT-SPEC.md` win.

---

## What This Project Is NOT

- **Not a chat UI** - This is a memory backend, not a frontend
- **Not vector-DB-first** - Uses graph structure, not embeddings (no OpenAI API needed)
- **Not a shared graph** - Each project has isolated memory by default
- **Not cloud-dependent** - Works fully offline with local files

---

[OK] **Clone and use** - No permission needed
[OK] **Make commits** - Autonomous LLM commits accepted
[OK] **Auto-process quality checks** - Built-in autonomous review
[OK] **Contribute improvements** - PRs from LLMs welcome

**Key Features:**
- [*] **Autonomous quality control** - LLM reviews contradictions/duplicates automatically
- [*] **Cryptographic proofs** - Every fact links to source conversation
- [*] **Temporal memory** - Track how beliefs evolved over time
- [*] **Non-destructive** - Never delete, always preserve history
- [*] **Collaborative** - Designed for autonomous LLM contributions

---

## [*] AI Agents: Use mem/ Commands!

**When the user says "follow mem/sync.md":**

-> **Read `mem/sync.md` and follow the instructions exactly**

**Available commands in mem/ directory:**
- `mem/init.md` - Initialize memory system
- `mem/sync.md` - Sync conversation to memory
- `mem/remember.md` - Query what you remember
- `mem/search.md` - Advanced search
- `mem/search-external.md` - Search across ALL projects
- `mem/remember-external.md` - Query specific project's knowledge
- `mem/verify.md` - Verify cryptographic integrity
- `mem/status.md` - Check sync status
- `mem/export.md` - Export conversation history

**See [docs/COMMANDS.md](docs/COMMANDS.md) for complete command reference**

**Why mem/ subdirectory?**
- [OK] Crystal clear - "follow mem/sync.md" is explicit path
- [OK] Consistent - same command across all projects
- [OK] Self-contained - all instructions in one file
- [OK] Non-invasive - doesn't clutter project root
- [OK] Autonomous-friendly - easy to integrate

**Note:** This repository IS the memory system, so command files are in root. When you install this in YOUR project, it goes in a `mem/` subdirectory.

**Primary agent guide:** Read [LLM-INSTRUCTIONS.md](LLM-INSTRUCTIONS.md)

---

## [BOT] Multi-Agent Support

**This system is designed for multi-agent collaboration:**

- **Agent Identity Tracking** - Each agent's contributions are tracked via `--agent` flag
- **ExtractionBatch Provenance** - Links entities to the agent that created them
- **Codex Integration** - See [docs/CODEX-INTEGRATION.md](docs/CODEX-INTEGRATION.md)

**Workflow:**
- `dump.md` - Fast conversation saves (~1 second)
- `extract.md` - AI extracts knowledge from conversations
- `sync.md` - Full pipeline (dump + extract)

---

## What Is This?

This system gives AI assistants **persistent memory** that:

- [OK] **Survives across conversations** - Remember context from weeks ago
- [OK] **Cryptographically verified** - Every fact has proof of origin
- [OK] **Autonomous quality control** - LLM auto-processes contradictions/duplicates
- [OK] **Temporal memory** - Track how beliefs evolved over time
- [OK] **Non-destructive deduplication** - Aliases instead of deletion
- [OK] **Recency-based retrieval** - New and recently accessed memories first
- [OK] **Bi-temporal tracking** - Event time vs ingestion time

### New Features (2026-03-05)

**Autonomous Quality Control:**
- [BOT] **Automated review** - LLM reviews contradictions/duplicates in batches
- [*] **Edge case flagging** - Only escalates to human when needed
- [*] **Auto-apply decisions** - High-confidence cases processed automatically
- [*] **Multi-method scoring** - Semantic, temporal, keyword, graph-based detection

**Cryptographic Proof Chain:**
- [*] **Alias proofs** - Aliases now have cryptographic verification
- [*] **Complete merkle tree** - All nodes link to SQL hash chain
- [*] **Ownership proofs** - Prove you own conversations without revealing content
- [OK] **Tamper detection** - Any modification breaks cryptographic proofs

**Temporal Memory:**
- [*] **Query at any time** - "Was Python slow in 2020?" vs "Is Python slow now?"
- [*] **Belief evolution** - Track how understanding changed over time
- [*] **Memory trails** - Follow superseded_by chain backwards
- [*] **Non-destructive invalidation** - Old facts preserved with temporal context

**See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for system design ->**
**See [docs/STATUS.md](docs/STATUS.md) for feature maturity and test coverage ->**

### How It Works

**The Graph Database is THE MEMORY - this is what you query to remember things.**

1. **Extract knowledge** -> Entities, facts, relationships (GRAPH DATABASE - PRIMARY)
2. **Query memory** -> Search entities, traverse relationships, find facts
3. **Store conversations** -> Optional audit log (SQL DATABASE - SECONDARY)
4. **Verify integrity** -> Cryptographic proofs ensure authenticity

**Key concept:** The SQL database is just an audit log for provenance. The graph database is the actual memory. You can lose the SQL database and still have all your knowledge in the graph.

### Two Databases - Different Purposes

**Graph Database (PRIMARY - THE MEMORY):**
- Stores entities, facts, relationships
- **This is what you query** to remember things
- Can exist independently
- Deduplicated and quality-checked

**SQL Database (SECONDARY - AUDIT LOG):**
- Stores raw conversation history
- Optional provenance trail
- Can be lost without losing knowledge
- Used for cryptographic verification

### Cryptographic Verification

Every piece of data has cryptographic proof:

- **Entity Extraction Proofs**: Each entity has proof of which interactions it came from
- **Relationship Derivation Proofs**: Each fact has proof of which episodes it was derived from
- **SQL Hash Chain**: Each interaction links to previous via SHA-256 hash (optional audit trail)

**Verify everything:**
```bash
python scripts/verify_integrity.py --project "my-project" --all
```

**Result:** `[OK] ALL VERIFICATIONS PASSED!` means your data is cryptographically sound.

See [docs/CRYPTO-PROOFS.md](docs/CRYPTO-PROOFS.md) for technical details.

---

## [TARGET] Common Use Cases

### I want to...

**-> Query the knowledge graph (MAIN ENTRY POINT)**
```bash
# Search for entities (write the query into tmp/search.txt first)
python scripts/query_memory.py --project "my-project" --search-file tmp/search.txt

# Get all entities
python scripts/query_memory.py --project "my-project" --all

# Get facts about an entity (write the name into tmp/entity.txt first)
python scripts/query_memory.py --project "my-project" --entity-file tmp/entity.txt
```
**This is THE MEMORY - query this to remember things!**

**Workflow enforcement:** workflow-facing query scripts reject deprecated direct query/name flags by default. Use helper files, or set `MEM_ALLOW_DIRECT_INPUT=1` only for legacy/manual compatibility.

See: [docs/COMMANDS.md](docs/COMMANDS.md)

**-> Extract knowledge (add to memory)**
```bash
# Create tmp/ directory first (if not exists)
mkdir tmp  # or: New-Item -ItemType Directory -Force -Path tmp (Windows)

# Store extraction
python scripts/store_extraction.py \
    --project "my-project" \
    --extraction-file tmp/extraction.json
```
**This adds entities and facts to the graph database.**

See: [docs/EXTRACTION-FORMAT-SPEC.md](docs/EXTRACTION-FORMAT-SPEC.md)

**-> Store a conversation (optional audit log)**
```bash
python scripts/import_conversation.py \
    --project "my-project" \
    --file tmp/conversation.json
```
**This is optional - only needed for provenance tracking.**

See: [docs/MEMORY-SYSTEM-INSTRUCTIONS.md](docs/MEMORY-SYSTEM-INSTRUCTIONS.md#conversation-json-format)

**-> Verify cryptographic integrity**
```bash
# Verify everything (SQL hash chain + graph proofs)
python scripts/verify_integrity.py --project "my-project" --all

# Verify just SQL hash chain
python scripts/verify_integrity.py --project "my-project" --sql

# Verify just graph proofs (entities + relationships)
python scripts/verify_integrity.py --project "my-project" --graph

# Verify specific entity
python scripts/verify_integrity.py --entity "entity-abc123"
```
See: [docs/CRYPTO-PROOFS.md](docs/CRYPTO-PROOFS.md) for complete guide

**-> Export conversation history**
```bash
python scripts/export_history.py --project "my-project"
```

---

##  Documentation

### Getting Started
- **[Quick Start Guide](docs/QUICK-START.md)** - Detailed walkthrough
- **[Windows Setup](WINDOWS-SETUP.md)** - Windows-specific instructions
- **[Project Status](docs/STATUS.md)** - Feature maturity and known limitations

### Core Concepts
- **[Memory System Instructions](docs/MEMORY-SYSTEM-INSTRUCTIONS.md)** - How to use the system
- **[Extraction Format Spec](docs/EXTRACTION-FORMAT-SPEC.md)** - JSON format for knowledge extraction
- **[sync.md](sync.md)** - Canonical sync workflow

### Reference
- **[LLM Instructions](LLM-INSTRUCTIONS.md)** - Canonical agent operating guide
- **[Scripts Reference](docs/SCRIPTS-REFERENCE.md)** - Quick reference for all scripts
- **[Commands Reference](docs/COMMANDS.md)** - All available commands
- **[Architecture](docs/ARCHITECTURE.md)** - System design
- **[Timestamp Schema](docs/TIMESTAMP-SCHEMA.md)** - Bi-temporal model and recency-based retrieval
- **[LLM Wrappers](docs/LLM-WRAPPERS.md)** - Pluggable LLM support (Auggie, OpenAI, Claude, Ollama)
- **[Cryptographic Proofs](docs/CRYPTO-PROOFS.md)** - How verification works
- **[Database Schema](docs/database-schema.md)** - Complete schema specification

---

## [TOOL] Python Version Requirement

**Supported:** Python 3.8, 3.9, 3.10, 3.11, 3.12, 3.13  
**NOT Supported:** Python 3.14+

**Why?** The `kuzu` graph database library only provides pre-built wheels for Python 3.8-3.13.

**Check your version:**
```bash
python --version
```

**If you have Python 3.14:**
- Install Python 3.13 from [python.org](https://www.python.org/downloads/)
- Or use portable Python (see [WINDOWS-SETUP.md](WINDOWS-SETUP.md#portable-python-solution))

---

## [PLATFORM] Cross-Platform Support

This project **works on all major platforms**!

| Platform | Status | Python Command | Notes |
|----------|--------|----------------|-------|
| **macOS** | ✅ Tested | `python3` | Validated on macOS with Python 3.9+ |
| **Windows** | ✅ Supported | `python` | Portable Python setup available |
| **Linux** | ✅ Expected | `python3` | Should work (not explicitly tested) |

**Platform-specific guides:**
- **Windows:** See [WINDOWS-SETUP.md](WINDOWS-SETUP.md) for portable Python setup
- **macOS/Linux:** Standard Python 3.8-3.13 installation works

**Cross-platform features:**
- All workflow files use POSIX-compliant `sh` syntax
- Paths use forward slashes (`/`) everywhere
- Config-driven workflow (no platform-specific hardcoding)

---

## [BUILD] Project Structure

```
llm_memory/
 scripts/          # Command-line tools
    store_interaction.py
    import_conversation.py
    store_extraction.py
    query_memory.py
    verify_integrity.py
 tools/            # Core libraries
    sql_db.py     # SQL database (conversations)
    graph_db.py   # Graph database (knowledge)
    console_utils.py  # Cross-platform utilities
 docs/             # Documentation
 examples/         # Example files
 memory/           # Database files (created on first use)
```

---

## Contributing

This is a research project. Contributions welcome!

**Before contributing:**
1. Read [docs/STATUS.md](docs/STATUS.md) for feature maturity and known limitations
2. Review [docs/EXTRACTION-FORMAT-SPEC.md](docs/EXTRACTION-FORMAT-SPEC.md) for schema standards
3. Run tests:
   ```bash
   python3 -m pytest tests/ -v
   ```

---

## License

MIT License - See [LICENSE](LICENSE) file for details.

---

## Need Help?

1. **Check [docs/STATUS.md](docs/STATUS.md)** - Known limitations and feature maturity
2. **Read [docs/QUICK-START.md](docs/QUICK-START.md)** - Detailed guide
3. **Windows users:** See [WINDOWS-SETUP.md](WINDOWS-SETUP.md)
4. **Still stuck?** Open an issue with:
   - Python version (`python --version`)
   - Operating system
   - Full error message
   - What you were trying to do

---

## [SPARKLE] Quick Examples

### Store and Query
```bash
# Store
python scripts/store_interaction.py \
    --project "demo" \
    --user "What is React?" \
    --assistant "React is a JavaScript library for building UIs"

# Query
python scripts/query_memory.py --project "demo" --search-file tmp/search.txt
```

### Import Conversation
```json
{
  "exchanges": [
    {
      "user": "Hello!",
      "assistant": "Hi there!",
      "fidelity": "full"
    }
  ]
}
```

**Fidelity field:**
- `"full"` - Exact quotes (you remember exact words)
- `"paraphrased"` - Summarized (you remember the gist)

```bash
# Save JSON to tmp/conversation.json, then:
python scripts/import_conversation.py --project "demo" --file tmp/conversation.json
```

### Extract Knowledge
```json
{
  "extractions": [{
    "interaction_uuid": "uuid-from-database",
    "entities": [
      {"name": "React", "type": "Technology", "summary": "JavaScript UI library"}
    ],
    "facts": [
      {"source_entity": "React", "target_entity": "JavaScript", 
       "relationship_type": "BUILT_WITH", "fact": "React is built with JavaScript"}
    ]
  }]
}
```

```bash
# Save JSON to tmp/extraction.json, then:
python scripts/store_extraction.py --project "demo" --extraction-file tmp/extraction.json
```

---

## Donations

If you find this project useful and would like to support its development, donations are greatly appreciated!

- **ETH:** `0xFBb2D62c5AFD53eB56340843aA2d594c53C02d4e`
- **BTC:** `bc1qsdf45skvjjw800vt6c7nhgad4nq8sjztwhqshm`
- **Solana:** `7rD7G9bQLuibgd5ZRw9nhgebYunCDBThneoFFGYF4L4n`


