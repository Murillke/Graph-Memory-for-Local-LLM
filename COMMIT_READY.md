# Initial Commit Checklist

> See `docs/STATUS.md` for authoritative feature maturity.

## What's Included

### [STABLE] Core System
- **Memory System** - Dual-layer architecture (SQL + Graph)
- **Cryptographic Verification** - Hash chains, extraction proofs, OpenTimestamps
- **Entity Extraction** - Concept-based extraction with LLM
- **Temporal Tracking** - See how knowledge evolved over time

### [EXPERIMENTAL] Visualization
- **D3.js Graph Visualization** - Interactive graph viewer
  - Force layout, temporal animation, filtering
  - Works but limited features

### [EXPERIMENTAL] Semantic Commit Tracking
- Commit-scoped knowledge graph from code + conversation context
- Git hook installs and captures commits
- Code graph DB schema and API work
- LLM-powered semantic correlation untested

### [STABLE] OpenTimestamps Integration
- **Bitcoin Attestations** - Blockchain-grade timestamps
- **Official Python Client** - Proper nonce + Merkle tree

### Documentation
- Workflow files (sync.md, remember.md, verify.md, etc.)
- Architecture and schema docs
- See `docs/STATUS.md` for documentation hierarchy

### Scripts
- Import/export conversations
- Extract entities and facts
- Query memory
- Verify integrity
- Recall timeline
- Export graphs

## What's Ignored (.gitignore)

### [*] NOT Committed
- `memory/` - Database files (can be huge!)
- `tmp/` - Temporary files
- `__pycache__/` - Python cache
- `python313/` - Virtual environment
- `*.log` - Log files
- `.env` - Secrets
- `graph_full.json` - Large exports
- `node_modules/` - Node dependencies

## Pre-Commit Cleanup

Before committing, ensure:

1. [ ] `tmp/` contains only `.gitkeep`
2. [ ] `tests/tmp/` is empty or gitignored
3. [ ] `backups/` is empty or gitignored
4. [ ] `llm_memory_dist/` is removed or gitignored
5. [ ] No `*.db` or `*.kuzu` files in root
6. [ ] No secrets or API keys

## Tests

Run tests with pytest:

```sh
python3 -m pytest tests/ -v
```

See `docs/TESTING.md` for details.
