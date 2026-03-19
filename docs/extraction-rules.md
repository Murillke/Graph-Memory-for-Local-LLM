# Extraction Rules for Memory System

**For: Auggie (AI Assistant)**
**Purpose: Define what to extract from conversations and how to structure it**

---

## [!!!] CRITICAL WARNING [!!!]

**MOST COMMON MISTAKE: Creating facts that reference entities you didn't extract!**

**[!] ALWAYS RUN VALIDATION BEFORE STORING:**
```bash
python scripts/validate_extraction.py --file tmp/extraction.json
```
**This catches missing entities automatically!**

**Example of FAILURE:**
```json
{
  "entities": [
    {"name": "Documentation Fixes", "type": "Solution", "summary": "..."}
  ],
  "facts": [
    {"source_entity": "Documentation Fixes", "target_entity": "docs/README.md", ...}
  ]
}
```
**Result:** `[WARNING] Skipping fact: entities not found (Documentation Fixes -> docs/README.md)`

**Why it failed:** You referenced "docs/README.md" in a fact but didn't extract it as an entity!

**How to fix:** ALWAYS extract ALL entities referenced in facts:
```json
{
  "entities": [
    {"name": "Documentation Fixes", "type": "Solution", "summary": "..."},
    {"name": "docs/README.md", "type": "File", "summary": "Main project documentation"}
  ],
  "facts": [
    {"source_entity": "Documentation Fixes", "target_entity": "docs/README.md", ...}
  ]
}
```

**MANDATORY: Use the validation checklist in Step 4 before storing!**

---

## Core Principle: Extract from EVERY Interaction

Like Graphiti, we extract knowledge from **every single interaction** automatically.

**No filtering, no "is this important?" decisions - just extract!**

---

## What to Extract (Graphiti's Model)

### 1. Entities (Nodes)

**Always extract:**
- **People** (user, team members, mentioned individuals)
- **Projects** (codebases, repositories, systems)
- **Technologies** (libraries, frameworks, tools, databases)
- **Concepts** (patterns, approaches, methodologies)
- **Files/Paths** (important files, directories, repos)
- **Services** (APIs, servers, external services)

**Entity structure:**
```cypher
(entity:Entity {
  uuid: "generated-uuid",
  name: "LadybugDB DB",
  summary: "Embedded graph database, successor to Kùzu",
  type: "technology",
  created_at: "2026-03-01T10:00:00Z",
  project_path: "/Users/davidastua/Documents/gml-llm"
})
```

**Guidelines (from Graphiti):**
- [OK] Extract the speaker/actor as the first entity
- [OK] Extract other significant entities, concepts, or actors
- [OK] Provide concise but informative summaries
- [OK] Be as explicit as possible in entity names
- [ERROR] Do NOT create entities for relationships or actions
- [ERROR] Do NOT create entities for temporal information
- [ERROR] Do NOT create entities for attributes (those go on edges)

---

### 2. Relationships (Edges)

**Facts are stored as edge properties, not separate nodes!**

**Common relationship types:**
- `LOCATED_AT` - Where something is
- `USES` - What technology/tool is used
- `DEPENDS_ON` - Dependencies
- `IMPLEMENTS` - Implementation relationships
- `SUPERSEDES` - When information is updated/corrected
- `SIMILAR_TO` - Pattern similarities
- `CAUSED_BY` - Error/problem causes
- `SOLVED_BY` - Solutions to problems
- `DECIDED` - Decisions made
- `PREFERS` - Preferences (approach A over B)

**Relationship structure:**
```cypher
(entity1)-[:LOCATED_AT {
  value: "./memory/knowledge.ladybug",
  confidence: 1.0,
  valid_from: "2026-03-01T10:00:00Z",
  valid_until: null,
  is_current: true,
  source_interaction: "interaction-uuid-847",
  extracted_at: "2026-03-01T10:05:00Z"
}]->(entity2)
```

**Edge properties (always include):**
- `value` - The actual fact/information
- `confidence` - How confident (0.0-1.0)
- `valid_from` - When this became true
- `valid_until` - When superseded (null if current)
- `is_current` - Boolean flag
- `source_interaction` - Which interaction this came from
- `extracted_at` - When we extracted it

---

### 3. Temporal Information

**Track when things happened and when they changed:**

- `valid_from` - Event time (when it actually happened)
- `valid_until` - When it was superseded/invalidated
- `extracted_at` - Ingestion time (when we learned about it)

**Example:**
```
Interaction 847: "auth repo is at ../auth-service"
-> valid_from: 2026-03-01T10:00:00Z
-> valid_until: null (current)

Interaction 849: "Actually, auth repo moved to ~/projects/auth"
-> Old fact: valid_until = 2026-03-01T15:45:00Z
-> New fact: valid_from = 2026-03-01T15:45:00Z
```

---

### 4. Project Association

**Every entity and relationship MUST be associated with a project:**

```cypher
(project:Project {path: $current_path})-[:HAS_ENTITY]->(entity)
```

**Use current working directory to determine project!**

---

## What NOT to Extract

[ERROR] **Casual conversation** - "How are you?", "Thanks!", "Okay"
[ERROR] **Relationships as nodes** - Store as edges, not nodes
[ERROR] **Actions as nodes** - Actions are relationships
[ERROR] **Temporal info as nodes** - Dates/times go on edges
[ERROR] **Duplicate information** - Check for existing entities first

---

## Extraction Process (Step-by-Step)

### Step 1: Identify Entities

**Rule: Extract all nouns that represent concepts, tools, files, people, problems, or solutions**

**How to identify entities:**
1. Read the interaction
2. Find all nouns and noun phrases
3. For each noun, ask: "Is this a thing, concept, tool, file, person, problem, or solution?"
4. If YES -> Extract as entity
5. If NO -> Skip

**Entity types:**
- `Concept` - Abstract ideas, patterns, approaches, workflows
- `Tool` - Software, libraries, frameworks, scripts
- `File` - Specific files, directories, documentation
- `Person` - People, teams, organizations
- `Problem` - Issues, bugs, errors, confusion
- `Solution` - Fixes, workarounds, resolutions
- `Task` - Work items, todos, goals
- `Design Decision` - Choices made about architecture or implementation
- `Procedure` - Step-by-step workflows or "how to do X" processes
- `ProcedureStep` - Individual step within a procedure

**Example:**
```
Input: "File-based workflow resolves subprocess command confusion"

Nouns found:
- "File-based workflow" -> Concept [OK]
- "subprocess command confusion" -> Problem [OK]

Entities to extract:
1. {"name": "File-based workflow", "type": "Concept"}
2. {"name": "Subprocess command confusion", "type": "Problem"}
```

---

### Step 2: Write Entity Summaries

**Rule: One sentence describing what the entity is**

**Format:** `[Entity] is [description]`

**Examples:**
- "File-based workflow" -> "Workflow using file I/O for communication between processes"
- "Subprocess command confusion" -> "Confusion about whether Python script could automatically call Auggie with subprocess"
- "docs/MEMORY-SYSTEM-INSTRUCTIONS.md" -> "Complete sync workflow instructions for Auggie to follow"

**Bad summaries (too vague):**
- [ERROR] "A workflow"
- [ERROR] "Some confusion"
- [ERROR] "A file"

**Good summaries (specific):**
- [OK] "Workflow using file I/O for communication"
- [OK] "Confusion about subprocess command invocation"
- [OK] "Documentation file containing sync workflow instructions"

---

### Step 3: Identify Relationships (Facts)

**Rule: Find all statements of the form "X does Y to Z" or "X is related to Z"**

**How to identify facts:**
1. Read the interaction
2. Find all verbs connecting entities
3. For each verb, ask: "Does this describe a relationship between two entities?"
4. If YES -> Extract as fact
5. If NO -> Skip

**Common relationship patterns:**
- X **uses** Y
- X **solves** Y
- X **creates** Y
- X **references** Y
- X **implements** Y
- X **tests** Y
- X **documents** Y
- X **supersedes** Y
- X **depends on** Y
- X **is part of** Y

**Example:**
```
Input: "File-based workflow resolves subprocess command confusion"

Verb found: "resolves"
Subject: "File-based workflow"
Object: "subprocess command confusion"

Fact to extract:
{
  "source_entity": "File-based workflow",
  "target_entity": "Subprocess command confusion",
  "relationship_type": "RESOLVES",
  "fact": "File-based workflow resolves subprocess command confusion by using simple pause and file I/O"
}
```

---

### Step 4: Validate Extraction [!!!] MANDATORY - DO NOT SKIP! [!!!]

**CRITICAL: Before storing, check that all entities referenced in facts exist!**

**This is the #1 cause of "[WARNING] Skipping fact: entities not found" errors!**

**VALIDATION CHECKLIST - RUN THIS BEFORE STEP 6:**

```
STEP 4a: Validate Facts (MOST IMPORTANT!)
==========================================
For EACH fact in your extraction:
  1. [ ] Does source_entity exist in entities list?
  2. [ ] Does target_entity exist in entities list?
  3. [ ] If NO to either -> STOP! Add missing entity to entities list NOW!

Common missing entities:
  - Files (docs/README.md, scripts/sync.py, etc.)
  - Existing entities from database (scripts/health_check.py, etc.)
  - Concepts mentioned in facts but not extracted

STEP 4b: Validate Entities
===========================
For EACH entity:
  1. [ ] Does it have a name?
  2. [ ] Does it have a type?
  3. [ ] Does it have a summary?
  4. [ ] If NO to any -> Fix the entity NOW!

STEP 4c: Validate JSON
======================
  1. [ ] Is it valid JSON? (run: python -m json.tool < file.json)
  2. [ ] Does it match the format in EXTRACTION-FORMAT-SPEC.md?

IF YOU SKIP THIS STEP, YOUR FACTS WILL BE LOST!
```

**Example validation:**

```json
{
  "entities": [
    {"name": "Subprocess command confusion", "type": "Problem", "summary": "..."}
  ],
  "facts": [
    {"source_entity": "File-based workflow", "target_entity": "Subprocess command confusion", ...}
  ]
}
```

**Validation result:**
- [ERROR] Fact references "File-based workflow" but it's NOT in entities list
- [OK] Fix: Add "File-based workflow" to entities list

**Fixed extraction:**
```json
{
  "entities": [
    {"name": "File-based workflow", "type": "Concept", "summary": "Workflow using file I/O"},
    {"name": "Subprocess command confusion", "type": "Problem", "summary": "..."}
  ],
  "facts": [
    {"source_entity": "File-based workflow", "target_entity": "Subprocess command confusion", ...}
  ]
}
```

---

### Step 5: Deduplicate Entities (Automated)

**This step is handled by the quality check system - you don't need to do it manually!**

The storage script will:
1. Find potential duplicates using fuzzy matching
2. Ask you to confirm if entities are duplicates
3. Merge duplicates automatically

---

### Step 6: Detect Contradictions (Automated)

**This step is also handled by the quality check system!**

The storage script will:
1. Find facts that might contradict existing facts
2. Ask you to confirm contradictions
3. Invalidate old facts and store new ones

---

## Procedural Extraction

### When to Extract Procedures

Extract a `Procedure` entity when you encounter:
- "Here's how to do X..."
- "The workflow for Y is..."
- "Before doing Z, you need to..."
- "Follow these steps to..."
- "The process involves..."

Extract `ProcedureStep` entities for each discrete step in the procedure.

### Procedure Entity Structure

```json
{
  "name": "Memory Sync Workflow",
  "type": "Procedure",
  "summary": "Workflow for syncing conversation memory to knowledge graph",
  "attributes": {
    "goal": "Store conversation and extract knowledge to graph database",
    "trigger_phrases": ["follow sync.md", "run memory sync", "before commit"],
    "prerequisites": ["mem.config.json exists", "conversation has content"],
    "agent_scope": "all"
  }
}
```

### ProcedureStep Entity Structure

```json
{
  "name": "Memory Sync Workflow / Step 1",
  "type": "ProcedureStep",
  "summary": "Import conversation to SQL database",
  "attributes": {
    "procedure_name": "Memory Sync Workflow",
    "step_number": 1,
    "action": "Run import_conversation.py with conversation JSON",
    "expected_output": "Interactions stored in SQL database",
    "script_refs": ["scripts/import_conversation.py"]
  }
}
```

### Required Relationships for Procedures

When extracting procedures, you MUST also extract these relationships:

1. **CONTAINS** - Link procedure to each step:
   ```json
   {
     "source_entity": "Memory Sync Workflow",
     "target_entity": "Memory Sync Workflow / Step 1",
     "relationship_type": "CONTAINS",
     "fact": "Memory Sync Workflow contains step 1"
   }
   ```

2. **PRECEDES** - Link steps in order:
   ```json
   {
     "source_entity": "Memory Sync Workflow / Step 1",
     "target_entity": "Memory Sync Workflow / Step 2",
     "relationship_type": "PRECEDES",
     "fact": "Step 1 precedes Step 2"
   }
   ```

3. **EXTRACTED_FROM** (if applicable) - Link to source document:
   ```json
   {
     "source_entity": "Memory Sync Workflow",
     "target_entity": "sync.md",
     "relationship_type": "EXTRACTED_FROM",
     "fact": "Workflow extracted from sync.md documentation"
   }
   ```

### Naming Conventions

- **Procedures**: Use descriptive workflow names (e.g., "Memory Sync Workflow", "Pre-Commit Validation")
- **Steps**: Use pattern `{Procedure Name} / Step {N}` (e.g., "Memory Sync Workflow / Step 1")

### Extraction Window

Unlike regular entities which extract from the current message only, procedures often span multiple turns. For procedural extraction:
- Look at the **last 3-5 turns** to capture complete workflows
- Don't extract partial procedures - wait until you have the full workflow

---

## Superseding Triggers

**Auto-supersede when user says:**
- "Actually..."
- "No, it's..."
- "Correction:"
- "I meant..."
- "moved to"
- "changed to"
- "now it's"
- "updated to"

**Example:**
```
User: "Actually, we're using LadybugDB not Neo4j"

Action:
1. Find: (project)-[:USES]->(Neo4j)
2. Supersede: valid_until = now, is_current = false
3. Create: (project)-[:USES]->(LadybugDB) with valid_from = now
4. Link: (new_fact)-[:SUPERSEDES {reason: "user correction"}]->(old_fact)
```

---

## Complete Worked Example

### Input Interaction:

```
User: "No I'm more worried about you forgetting how to sync and having to explain it again. Which would be a much better prompt?"

Assistant: "I created docs/MEMORY-SYSTEM-INSTRUCTIONS.md with complete sync workflow instructions. I proposed several prompt options and recommended 'Sync (check instructions)' as the best balance of brevity and clarity."
```

### Step 1: Identify Entities

**Nouns found:**
- "you" -> Skip (pronoun, not a concept)
- "sync" -> Skip (verb/action, not a thing)
- "prompt" -> Skip (too generic)
- "docs/MEMORY-SYSTEM-INSTRUCTIONS.md" -> File [OK]
- "sync workflow instructions" -> Skip (covered by the file)
- "Sync (check instructions)" -> Skip (this is a prompt text, not an entity)
- "Sync prompt design" -> Concept [OK] (the design/choice of the prompt)

**Entities to extract:**
1. `docs/MEMORY-SYSTEM-INSTRUCTIONS.md` - File
2. `Sync prompt design` - Design Decision

### Step 2: Write Summaries

1. **docs/MEMORY-SYSTEM-INSTRUCTIONS.md**
   - Summary: "Complete sync workflow instructions for Auggie to follow"

2. **Sync prompt design**
   - Summary: "Design of optimal prompt for user to trigger sync workflow"

### Step 3: Identify Relationships

**Relationships found:**
- "I created docs/MEMORY-SYSTEM-INSTRUCTIONS.md" -> Auggie CREATED the file
- "docs/MEMORY-SYSTEM-INSTRUCTIONS.md contains sync workflow instructions" -> File DOCUMENTS workflow
- "Sync prompt design references docs/MEMORY-SYSTEM-INSTRUCTIONS.md" -> Design REFERENCES file

**Wait! "Auggie" and "Sync workflow" are not in our entities list!**

**Add missing entities:**
3. `Auggie` - Person (already exists in database, but good to reference)
4. `Sync workflow` - Concept

### Step 4: Validate

**Check facts against entities:**

Fact 1: `Auggie -> docs/MEMORY-SYSTEM-INSTRUCTIONS.md`
- Source: "Auggie" [OK] (in entities list)
- Target: "docs/MEMORY-SYSTEM-INSTRUCTIONS.md" [OK] (in entities list)

Fact 2: `docs/MEMORY-SYSTEM-INSTRUCTIONS.md -> Sync workflow`
- Source: "docs/MEMORY-SYSTEM-INSTRUCTIONS.md" [OK]
- Target: "Sync workflow" [OK] (in entities list)

Fact 3: `Sync prompt design -> docs/MEMORY-SYSTEM-INSTRUCTIONS.md`
- Source: "Sync prompt design" [OK]
- Target: "docs/MEMORY-SYSTEM-INSTRUCTIONS.md" [OK]

**All facts validated! [OK]**

### Step 5: Final Extraction JSON

```json
{
  "extractions": [
    {
      "interaction_uuid": "uuid-73d09f3cab75",
      "entities": [
        {
          "name": "docs/MEMORY-SYSTEM-INSTRUCTIONS.md",
          "type": "File",
          "summary": "Complete sync workflow instructions for Auggie to follow"
        },
        {
          "name": "Sync prompt design",
          "type": "Design Decision",
          "summary": "Design of optimal prompt for user to trigger sync workflow"
        },
        {
          "name": "Sync workflow",
          "type": "Concept",
          "summary": "Workflow for syncing conversations into memory system"
        }
      ],
      "facts": [
        {
          "source_entity": "docs/MEMORY-SYSTEM-INSTRUCTIONS.md",
          "target_entity": "Sync workflow",
          "relationship_type": "DOCUMENTS",
          "fact": "docs/MEMORY-SYSTEM-INSTRUCTIONS.md documents the complete sync workflow"
        },
        {
          "source_entity": "Sync prompt design",
          "target_entity": "docs/MEMORY-SYSTEM-INSTRUCTIONS.md",
          "relationship_type": "REFERENCES",
          "fact": "Sync prompt design references docs/MEMORY-SYSTEM-INSTRUCTIONS.md to avoid Auggie forgetting workflow"
        }
      ]
    }
  ]
}
```

**Note:** I didn't include the "Auggie CREATED file" fact because it's less important than the documentation and reference relationships.

---

## Error Recovery Guide

### Error: "[WARNING] Skipping fact: entities not found"

**Cause:** Fact references an entity that doesn't exist

**Fix:**
1. Look at the error message to see which entity is missing
2. Add that entity to the entities list in your extraction JSON
3. Re-run the storage command

**Example:**
```
[WARNING] Skipping fact: entities not found (File-based workflow -> Subprocess command confusion)
```

**Fix:** Add "File-based workflow" to entities list

---

### Error: "RuntimeError: Parser exception"

**Cause:** Single quotes (apostrophes) in entity names or facts

**Fix:**
1. Find the entity or fact with apostrophes
2. Remove or replace apostrophes
3. Re-run the storage command

**Example:**
```
"fact": "Sync prompt uses 'Sync (see docs/FILE.md)' format"
```

**Fix:** Change to:
```
"fact": "Sync prompt uses recommended format with exact filename"
```

---

### Error: "JSON decode error"

**Cause:** Invalid JSON syntax

**Fix:**
1. Run: `python3 -m json.tool < your-extraction.json`
2. Fix the syntax error shown
3. Re-run the storage command

**Common issues:**
- Missing comma between items
- Trailing comma after last item
- Unescaped quotes in strings
- Missing closing bracket/brace

---

## Quick Reference Card

### Entity Extraction
```
1. Find nouns -> 2. Check if concept/tool/file/person/problem/solution -> 3. Extract
```

### Fact Extraction
```
1. Find verbs -> 2. Check if connects two entities -> 3. Extract
```

### Validation
```
1. All entities in facts exist in entities list? -> 2. All entities have name/type/summary? -> 3. JSON valid?
```

### Common Mistakes
```
[ERROR] Extracting actions as entities (use relationships instead)
[ERROR] Forgetting to add entities referenced in facts
[ERROR] Using apostrophes in entity names or facts
[ERROR] Vague summaries ("A file" instead of "Documentation file containing X")
```

---

## Next Steps

**See `docs/MEMORY-SYSTEM-INSTRUCTIONS.md` for:**
- How to use these rules in the sync workflow
- Step-by-step sync process
- Quality check workflow
- Rebuilding the graph from scratch


