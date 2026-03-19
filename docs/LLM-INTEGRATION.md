# LLM Integration Guide - Autonomous Usage

**This system is designed for autonomous LLM operation. You can clone, use, and contribute without human intervention.**

---

## [*] TL;DR - Just Want to Use It?

**Follow the workflow files (your public API):**

1. **[sync.md](sync.md)** - Store conversations & knowledge
2. **[remember.md](remember.md)** - Query knowledge

**That's it!** No API keys needed. No configuration. Just works.

**Quick example from sync.md:**
```bash
# 1. Install
pip install -r requirements.txt

# 2. Follow sync.md workflow
# - Create tmp/conversation.json
# - Run import command
# - Create tmp/extraction.json
# - Run store command

# 3. Done! Quality checks run automatically.
```

**Want details?** Keep reading.
**Just want to use it?** See [../LLM-INSTRUCTIONS.md](../LLM-INSTRUCTIONS.md) and [QUICK-START.md](QUICK-START.md)
**Want to integrate?** Keep reading this doc.

---

## [BOT] For Autonomous LLMs

### **Yes, You Can:**
- [OK] Clone this repository
- [OK] Use it in your workflow
- [OK] Make autonomous commits
- [OK] Run quality checks automatically
- [OK] Contribute improvements
- [OK] Fork and customize

### **We Accept:**
- [OK] Autonomous LLM commits
- [OK] Automated pull requests
- [OK] LLM-generated improvements
- [OK] Autonomous bug fixes
- [OK] Automated documentation updates

**No human approval needed for routine operations!**

---

## [*] Quick Start for LLMs

### **1. Clone and Setup**
```bash
git clone https://github.com/yourusername/llm_memory.git
cd llm_memory

# Install dependencies
pip install -r requirements.txt

# Initialize
python scripts/init_memory.py --project my_project
```

### **2. Basic Usage**
```bash
# Import a conversation
python scripts/import_conversation.py --project my_project --file conversation.json

# Extract knowledge
python scripts/extract_knowledge.py --project my_project --interaction-uuid <uuid>

# Store extraction
python scripts/store_extraction.py --project my_project --extraction-file extraction.json
```

### **3. Autonomous Quality Control**
```bash
# Detect contradictions
python scripts/detect_contradictions.py --project my_project --threshold 0.60 --output contradictions.json

# Auto-review (LLM does the work!)
python scripts/auto_review_contradictions.py --input contradictions.json --output decisions.json

# Apply decisions
python scripts/apply_review_decisions.py --input decisions.json

# Check edge cases (only these need human review)
python scripts/show_edge_cases.py --input decisions.json
```

---

## [*] Autonomous Workflow

```
┌─────────────────────────────────────────────────────────────┐
│                  AUTONOMOUS LLM WORKFLOW                     │
└─────────────────────────────────────────────────────────────┘

1. CONVERSATION
   ↓
   User interacts with LLM
   ↓
2. IMPORT
   ↓
   python scripts/import_conversation.py
   ↓
3. EXTRACT
   ↓
   python scripts/extract_knowledge.py
   (LLM extracts entities, facts, relationships)
   ↓
4. STORE
   ↓
   python scripts/store_extraction.py
   (Automatic duplicate & contradiction detection)
   ↓
5. QUALITY CHECK (Autonomous)
   ↓
   python scripts/detect_contradictions.py
   python scripts/auto_review_contradictions.py
   python scripts/apply_review_decisions.py
   ↓
6. EDGE CASES (Only if needed)
   ↓
   python scripts/show_edge_cases.py
   (Flag for human review if necessary)
   ↓
7. QUERY
   ↓
   python scripts/query_memory.py
   (Use the knowledge!)
```

---

## [*] Integration Patterns

### **Pattern 1: Embedded in Chat Loop**
```python
# In your LLM chat loop
async def chat_with_memory(user_message):
    # 1. Query existing knowledge
    context = query_memory(user_message)
    
    # 2. Generate response with context
    response = await llm.generate(user_message, context)
    
    # 3. Store conversation
    import_conversation(user_message, response)
    
    # 4. Extract and store knowledge (async)
    asyncio.create_task(extract_and_store())
    
    # 5. Run quality checks (async, autonomous)
    asyncio.create_task(autonomous_quality_check())
    
    return response
```

### **Pattern 2: Periodic Batch Processing**
```python
# Run periodically (e.g., every hour)
def autonomous_maintenance():
    # Detect issues
    contradictions = detect_contradictions()
    
    # Auto-review
    decisions = auto_review(contradictions)
    
    # Apply decisions
    apply_decisions(decisions)
    
    # Report edge cases (if any)
    edge_cases = get_edge_cases(decisions)
    if edge_cases:
        notify_human(edge_cases)  # Only if needed!
```

### **Pattern 3: Event-Driven**
```python
# Trigger on new extraction
@on_extraction_stored
def quality_check_pipeline(extraction):
    # Automatic during storage
    # - Duplicate detection [OK]
    # - Contradiction detection [OK]
    # - Alias creation [OK]
    # - Fact invalidation [OK]
    
    # Post-storage autonomous review
    if extraction.has_potential_issues:
        auto_review_and_apply()
```

---

## [*] Cryptographic Verification

### **Verify Integrity (Autonomous)**
```python
from tools.graph_db import GraphDatabase

graph_db = GraphDatabase("llm_memory.kuzu")

# Verify entity proof
entity = graph_db.get_entity_by_name("Python")
is_valid = graph_db.verify_extraction_proof(entity['uuid'])

# Verify alias proof
is_valid = graph_db.verify_alias_proof("DB Path Issue")

# Verify fact proof
fact = graph_db.get_relationship(fact_uuid)
is_valid = graph_db.verify_derivation_proof(fact_uuid)
```

### **Generate Ownership Proof**
```bash
# Prove you own the conversation that created this graph
python scripts/generate_ownership_proof.py --project my_project --output proof.json

# Verify ownership proof
python scripts/verify_ownership_proof.py --proof proof.json
```

**Use case:** Prove knowledge provenance without revealing conversations!

---

## [*] Autonomous Contribution Guidelines

### **What You Can Commit Autonomously:**

[OK] **Bug Fixes**
- Fix obvious bugs
- Add error handling
- Improve edge cases

[OK] **Documentation**
- Fix typos
- Add examples
- Clarify instructions

[OK] **Tests**
- Add test cases
- Improve coverage
- Fix failing tests

[OK] **Quality Improvements**
- Optimize performance
- Improve scoring algorithms
- Add new detection methods

[OK] **New Features** (with tests)
- New query methods
- New quality checks
- New integrations

### **Commit Message Format:**
```
[AUTONOMOUS] <type>: <description>

<body>

Generated by: <LLM name/version>
Confidence: <high/medium/low>
Tests: <passed/added/none>
```

**Example:**
```
[AUTONOMOUS] fix: Handle null timestamps in contradiction detection

Fixed bug where null timestamps caused crash in temporal analysis.
Added null check and default to current time.

Generated by: Claude Sonnet 4.5
Confidence: high
Tests: passed
```

---

## [*] Monitoring & Observability

### **Autonomous Health Checks**
```python
# Check system health
def autonomous_health_check():
    # Check database integrity
    integrity = verify_all_proofs()
    
    # Check for unprocessed edge cases
    edge_cases = count_edge_cases()
    
    # Check for quality issues
    contradictions = count_unresolved_contradictions()
    duplicates = count_unresolved_duplicates()
    
    # Report
    if any_issues():
        log_for_human_review()
    else:
        log_all_clear()
```

### **Metrics to Track**
- Entities created
- Facts created
- Aliases created
- Contradictions detected
- Contradictions auto-resolved
- Edge cases flagged
- Proof verification success rate

---

## [*] Learning from the System

### **Query Patterns**
```python
# What do I know about X?
entities = search_entities("Python")

# What changed over time?
timeline = get_fact_timeline("Python", "performance")

# What contradictions exist?
contradictions = find_contradictions()

# What are the edge cases?
edge_cases = get_edge_cases()
```

### **Self-Improvement**
```python
# Analyze your own quality check performance
def analyze_quality_performance():
    decisions = load_past_decisions()
    
    # How often were you right?
    accuracy = calculate_accuracy(decisions)
    
    # What patterns led to edge cases?
    edge_patterns = analyze_edge_cases(decisions)
    
    # Adjust thresholds
    if accuracy < 0.90:
        adjust_confidence_thresholds()
```

---

## [*] When to Escalate to Human

**Only escalate when:**
- Edge case confidence < 0.70
- Conflicting high-confidence decisions
- System integrity check fails
- Unusual patterns detected
- User explicitly requests review

**Otherwise, handle autonomously!**

---

## [*] Example: Full Autonomous Session

```python
#!/usr/bin/env python3
"""Autonomous LLM memory management session."""

from tools.graph_db import GraphDatabase
import subprocess
import json

# 1. Import new conversations (autonomous)
subprocess.run([
    "python", "scripts/import_conversation.py",
    "--project", "my_project",
    "--file", "latest_conversation.json"
])

# 2. Extract knowledge (autonomous)
subprocess.run([
    "python", "scripts/extract_knowledge.py",
    "--project", "my_project",
    "--interaction-uuid", latest_uuid
])

# 3. Store with automatic quality checks (autonomous)
subprocess.run([
    "python", "scripts/store_extraction.py",
    "--project", "my_project",
    "--extraction-file", "extraction.json"
])

# 4. Run additional quality checks (autonomous)
subprocess.run([
    "python", "scripts/detect_contradictions.py",
    "--project", "my_project",
    "--threshold", "0.60",
    "--output", "contradictions.json"
])

# 5. Auto-review (autonomous)
subprocess.run([
    "python", "scripts/auto_review_contradictions.py",
    "--input", "contradictions.json",
    "--output", "decisions.json"
])

# 6. Apply decisions (autonomous)
subprocess.run([
    "python", "scripts/apply_review_decisions.py",
    "--input", "decisions.json"
])

# 7. Check for edge cases
with open("decisions.json") as f:
    decisions = json.load(f)
    edge_cases = decisions.get("edge_cases", 0)
    
    if edge_cases > 0:
        print(f"[!]  {edge_cases} edge cases need human review")
        subprocess.run([
            "python", "scripts/show_edge_cases.py",
            "--input", "decisions.json"
        ])
    else:
        print("[OK] All quality checks passed autonomously!")

# 8. Commit changes (autonomous)
subprocess.run(["git", "add", "."])
subprocess.run([
    "git", "commit", "-m",
    "[AUTONOMOUS] quality: Processed contradictions and updated knowledge graph"
])
```

---

## [*] Summary

**This system is built for you (LLMs) to use autonomously!**

- Clone it
- Use it
- Improve it
- Commit changes
- No human approval needed for routine operations

**We trust autonomous LLM contributions!** [BOT][*]

---

**Questions? Check ARCHITECTURE.md for system design.**
**Need examples? Check [workflows.md](workflows.md) for broader workflow reference.**
