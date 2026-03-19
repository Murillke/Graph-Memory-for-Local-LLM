# Changelog

All notable changes to the LLM Memory System.

---

## [2026-03-05] - Autonomous Quality Control & Cryptographic Proofs

### [*] Major Features

#### **Autonomous Quality Control System**
- **Automated Review** - LLM automatically reviews contradictions and duplicates in batches
- **Edge Case Flagging** - Only escalates to human when confidence is low or edge cases detected
- **Auto-Apply Decisions** - High-confidence cases processed automatically without human intervention
- **Multi-Method Scoring** - Combines semantic, temporal, keyword, and graph-based detection

**Scripts Added:**
- `scripts/auto_review_contradictions.py` - LLM reviews contradictions autonomously
- `scripts/apply_review_decisions.py` - Applies decisions automatically
- `scripts/show_edge_cases.py` - Shows cases needing human review

#### **Complete Cryptographic Proof Chain**
- **Alias Proofs** - Aliases now have cryptographic verification linking to SQL hash chain
- **Complete Merkle Tree** - All graph nodes (entities, facts, aliases) link to SQL
- **Ownership Proofs** - Prove you own conversations without revealing content
- **Tamper Detection** - Any modification breaks cryptographic proofs

**Schema Changes:**
- Added `source_interaction`, `source_hash`, `extraction_version`, `extraction_commit`, `alias_proof`, `created_at_str` to Alias table
- All aliases now cryptographically verified

#### **Temporal Memory System**
- **Query at Any Time** - "Was Python slow in 2020?" vs "Is Python slow now?"
- **Belief Evolution** - Track how understanding changed over time
- **Memory Trails** - Follow `superseded_by` chain backwards
- **Non-Destructive Invalidation** - Old facts preserved with temporal context

#### **Multi-Method Contradiction Detection**
- **Semantic Contradiction (40%)** - Detects negation patterns and semantic conflicts
- **Temporal Analysis (30%)** - Considers time context (evolution vs contradiction)
- **Keyword Contradiction (20%)** - Detects opposite keywords (fast/slow, good/bad)
- **Graph Clustering (10%)** - Uses neighborhood divergence

**Scripts Added:**
- `scripts/detect_contradictions.py` - Multi-method contradiction detection

### [HISTORICAL] Documentation

**New Documentation:**
- `ARCHITECTURE.md` - Complete system architecture with diagrams
- `LLM-INTEGRATION.md` - Guide for autonomous LLM usage
- `docs/workflows.md` - Common usage patterns and examples
- `DIAGRAMS.md` - Visual architecture diagrams
- `QUICK-REFERENCE.md` - Command cheat sheet
- `CONTRIBUTING.md` - Contribution guide for autonomous LLMs

**Updated Documentation:**
- `README.md` - Added autonomous LLM section, new features, documentation links

### [*] Improvements

**Quality Control:**
- Duplicate detection now uses weighted scoring (clustering 30%, semantic 40%, Levenshtein 25%, Jaccard 20%, fuzzy 15%)
- Contradiction detection uses weighted scoring (semantic 40%, temporal 30%, keyword 20%, graph 10%)
- Relationship type classification (DUPLICATE_OF, ABBREVIATION_OF, SUBSET_OF, SIMILAR_TO, RELATED_TO)

**Database:**
- Alias table now supports cryptographic proofs
- All proofs link to SQL hash chain
- Temporal validity tracking with `valid_at`, `invalid_at`, `superseded_by`

**Autonomous Operation:**
- LLM can run quality checks without human intervention
- Auto-process routine cases
- Only escalate edge cases
- Designed for autonomous commits

### [*] Key Principles

1. **Non-Destructive** - Never delete, always preserve history
2. **Cryptographically Verified** - Every node has proof linking to source
3. **Autonomous** - LLMs can manage quality without human intervention
4. **Human-Like** - Temporal memory, contradictions, evolution of beliefs
5. **Collaborative** - Designed for autonomous LLM commits and contributions

---

## [Previous Versions]

### Initial Implementation
- SQL database for episodic memory (conversations)
- Graph database for semantic memory (entities, facts)
- Hash chain for tamper detection
- Duplicate detection during extraction
- Contradiction detection during extraction
- Basic query system

---

## [*] Future Roadmap

### Planned Features
- [ ] Retroactive duplicate detection script (like detect_contradictions.py but for entities)
- [ ] Enhanced LLM-based semantic analysis (better than current heuristics)
- [ ] Embedding-based similarity search (vector search for entities/facts)
- [ ] Performance optimizations (faster queries, indexing)
- [ ] API server for remote access (REST/GraphQL API)

### Under Consideration
- [ ] Git integration (version control for knowledge graph)
- [ ] Export/import to other formats (RDF, Neo4j, etc.)
- [ ] Distributed storage (sync across multiple machines)

### Recently Added (2026-03-05)
- [OK] **Graph visualization** - Interactive D3.js visualization
  - Export graph to JSON with `scripts/export_graph.py`
  - View in browser with `visualize_graph.html`
  - Interactive force-directed layout
  - Drag nodes, hover for details, color-coded by type
  - See `visualize.md` workflow

### Already Implemented (Not Widely Known)
- [OK] **Real-time collaboration** - Multiple LLMs can share same database with different projects
  - Use `search-external.md` to search across all projects
  - Use `remember-external.md` to query specific project's knowledge
  - Each LLM has own project, can access others' knowledge
  - No need for documentation handoffs - real-time knowledge sharing!

---

**See [ARCHITECTURE.md](ARCHITECTURE.md) for system design ->**  
**See [LLM-INTEGRATION.md](LLM-INTEGRATION.md) for autonomous usage ->**
