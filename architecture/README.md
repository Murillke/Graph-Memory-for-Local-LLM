# Architecture Documentation

**Complete architecture documentation for the LLM Memory System.**

---

## Overview

The LLM Memory System is a cryptographically-verified knowledge graph for AI agents to store and query conversational knowledge across multiple projects.

**Key Features:**
- Cryptographic hash chain for tamper-proof audit log
- Graph database for entity-relationship knowledge
- Multi-project support with cross-project queries
- Command-based interface for AI agents
- Real-time knowledge sharing across teams

---

## Documentation Structure

### Core Architecture

- **[system-overview.md](system-overview.md)** - High-level system architecture
- **[data-model.md](data-model.md)** - Database schemas and data structures
- **[cryptographic-proofs.md](cryptographic-proofs.md)** - Hash chain and proof system
- **[multi-project.md](multi-project.md)** - Multi-project architecture

### Workflows

- **[workflow-sync.md](workflow-sync.md)** - Sync conversation workflow
- **[workflow-query.md](workflow-query.md)** - Query memory workflow
- **[workflow-cross-project.md](workflow-cross-project.md)** - Cross-project query workflow
- **[workflow-verification.md](workflow-verification.md)** - Integrity verification workflow

### Diagrams

- **[diagrams/](diagrams/)** - Visual architecture diagrams
  - System architecture
  - Data flow diagrams
  - Sequence diagrams
  - Entity-relationship diagrams

### Design Decisions

- **[decisions/](decisions/)** - Architecture Decision Records (ADRs)
  - Why graph database?
  - Why hash chain?
  - Why command-based interface?
  - Why multi-project in one database?

---

## Quick Links

**For Developers:**
- Start with [system-overview.md](system-overview.md)
- Understand data model: [data-model.md](data-model.md)
- See workflows: [workflow-sync.md](workflow-sync.md)

**For Users:**
- See command files in root directory
- Read [../README.md](../README.md)

**For Architects:**
- Review [decisions/](decisions/)
- Study [diagrams/](diagrams/)

---

## Principles

**1. Cryptographic Integrity**
- Every interaction has SHA-256 hash
- Hash chain links all interactions
- Entities have extraction proofs
- Facts have derivation proofs

**2. Graph-First Design**
- Graph database is THE MEMORY
- SQL database is audit log
- Entities and relationships are first-class

**3. Multi-Project Support**
- One database, multiple projects
- Project isolation via filtering
- Cross-project queries enabled
- Real-time knowledge sharing

**4. Command-Based Interface**
- Explicit command files (init.md, sync.md, etc.)
- Self-contained instructions
- Platform-specific commands
- AI-agent friendly

**5. Human-Readable**
- Clear documentation
- Visual diagrams
- Step-by-step workflows
- Troubleshooting guides

---

## Technology Stack

**Databases:**
- SQLite - Audit log with hash chain
- Kuzu - Graph database for knowledge

**Language:**
- Python 3.9-3.13

**Key Libraries:**
- kuzu - Graph database
- sqlite3 - SQL database
- hashlib - Cryptographic hashing
- json - Data serialization

---

## Directory Structure

```
/mem/ (project root)
├── architecture/           # THIS DIRECTORY
│   ├── README.md          # This file
│   ├── system-overview.md
│   ├── data-model.md
│   ├── cryptographic-proofs.md
│   ├── multi-project.md
│   ├── workflow-*.md
│   ├── diagrams/
│   └── decisions/
├── scripts/               # Python scripts
├── tools/                 # Library code
├── docs/                  # Detailed documentation
├── examples/              # Example files
├── tests/                 # Test files
├── config/                # Configuration
└── *.md                   # Command files
```

---

## Contributing

When adding new features:
1. Update relevant architecture docs
2. Create/update diagrams
3. Document workflows
4. Add ADR if architectural decision
5. Update this README

---

**Start with [system-overview.md](system-overview.md) for the big picture!**

