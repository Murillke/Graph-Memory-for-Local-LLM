# Project Status

**Version:** Pre-1.0 (First Commit)
**Last Updated:** 2026-03-14

---

## Feature Status

### [IMPLEMENTED] Core Features

| Feature | Status | Notes |
|---------|--------|-------|
| Conversation import | Stable | `import_conversation.py` |
| Knowledge extraction | Stable | Manual via `extract.md` |
| Quality review | Stable | Autonomous LLM review with human escalation |
| Graph storage | Stable | Kuzu-based, 24 relationship types |
| Cryptographic proofs | Stable | SHA-256 hash chains, OpenTimestamps |
| Time-based recall | Stable | `recall.py` with hour-level precision |
| Agent identity tracking | Stable | `--agent` flag, ExtractionBatch provenance |

### [IMPLEMENTED] Workflow Files

| File | Status | Purpose |
|------|--------|---------|
| `sync.md` | Stable | Full pipeline (import + extract) |
| `dump.md` | Stable | Fast conversation save |
| `extract.md` | Stable | Manual extraction workflow |
| `remember.md` | Stable | Query knowledge graph |
| `recall.md` | Stable | Time-based queries |
| `verify.md` | Stable | Integrity verification |
| `backup.md` | Stable | Backup and restore |

### [EXPERIMENTAL] Features

| Feature | Status | Notes |
|---------|--------|-------|
| Document import | Experimental | `import-documents.md` - basic flow works, advanced queries limited |
| Automated extraction | Experimental | Two paths: `extract_with_wrappers.py` (wrapper config) or `--extract` flag (uses `get_default_client()`) |
| Visualization | Experimental | `visualize.md` - D3.js graph viewer |
| Semantic Commit Tracking | Experimental | Git hook + code graph DB works; LLM correlation untested |

### [NOT IMPLEMENTED] Graphiti Concepts

These concepts are from the Graphiti inspiration but are **not implemented**:

| Concept | Status | Notes |
|---------|--------|-------|
| `Episodic` nodes | Not Implemented | Episode data stored in SQL instead |
| `MENTIONS` edges | Not Implemented | No Episodic nodes to link |
| Vector embeddings | Not Implemented | `name_embedding`, `fact_embedding` not used |
| Semantic search | Not Implemented | Uses keyword matching instead |

---

## Documentation Hierarchy

| Type | File | Purpose |
|------|------|---------|
| **[CANONICAL] Operational** | `LLM-INSTRUCTIONS.md` | Primary guide for LLM agents |
| **[CANONICAL] Schema** | `docs/EXTRACTION-FORMAT-SPEC.md` | Authoritative extraction format |
| **[REFERENCE]** | `docs/COMMANDS.md` | Quick command lookup |
| **[REFERENCE]** | `docs/database-schema.md` | Persisted schema definitions |
| **[SUPERSEDED]** | `docs/MEMORY-SYSTEM-INSTRUCTIONS.md` | Use root LLM-INSTRUCTIONS.md |

**Precedence rule:** When docs conflict, `LLM-INSTRUCTIONS.md` and `docs/EXTRACTION-FORMAT-SPEC.md` win.

---

## Known Limitations

1. **No vector search** - Queries use exact/keyword matching, not semantic similarity
2. **Single-agent writes** - Concurrent writes from multiple agents not tested
3. **No web UI** - Command-line and file-based interface only

---

## Maturity Assessment

| Area | Maturity | Confidence |
|------|----------|------------|
| Core conversation flow | Production-ready | High |
| Knowledge extraction | Production-ready | High |
| Quality review | Production-ready | High |
| Cryptographic proofs | Production-ready | High |
| Document import | Alpha | Medium |
| Visualization | Alpha | Low |

---

## Test Coverage

| Test File | Tests | Status |
|-----------|-------|--------|
| `test_workflow_hardening.py` | 68 | Passing |
| `test_relationship_types.py` | 10 | Passing |
| `test_agent_identity_sql.py` | 3 | Passing |
| `test_agent_identity_graph.py` | 3 | Passing |
| `test_consolidate_knowledge.py` | Multiple | Passing |
| `test_tasks.py` | Multiple | Passing |
| (+ 18 more test files) | Multiple | Passing |

**Total: 68+ tests passing**

---

## Platform Support

| Platform | Status | Python Version | Notes |
|----------|--------|----------------|-------|
| **macOS** | ✅ Tested | 3.9.6 | Full compatibility verified (2026-03-14) |
| **Windows** | ✅ Supported | 3.8-3.13 | Portable Python setup available |
| **Linux** | ✅ Expected | 3.8-3.13 | Not explicitly tested but should work |

**Cross-Platform Features:**
- ✅ All paths use forward slashes (`/`)
- ✅ Shell syntax uses POSIX-compliant `sh` (not `bash` or PowerShell)
- ✅ Python code compatible with 3.8+ (uses `Optional[T]` not `T | None`)
- ✅ Config-driven workflow (no hardcoded platform assumptions)

**Portability Fixes (2026-03-14):**
- Fixed Python 3.10+ union syntax (`str | None` → `Optional[str]`)
- Standardized code fences to `sh` instead of `bash`
- Removed Windows-specific path separators from all workflow docs
- Removed shell-specific commands (`echo`, PowerShell backticks)

