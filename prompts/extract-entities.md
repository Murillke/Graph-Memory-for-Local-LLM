# Entity Extraction from Conversation

Extract entity nodes from conversational messages.

---

## Task

Extract all significant entities mentioned in the conversation and classify them by type.

---

## Entity Types

- **Person** - A human being or named AI assistant
- **Organization** - Company, team, institution, or formal group
- **Project** - Named software project, repository, or initiative
- **Technology** - Framework, library, language, package, or technical system concept
- **Platform** - Operating system, runtime platform, or hosting platform
- **Service** - Hosted service or service-like system endpoint
- **API** - Explicit API or endpoint surface
- **Tool** - Directly used utility, product, or CLI
- **Database** - Database engine or database system
- **File** - Specific path-like repo artifact or concrete file
- **Document** - Spec, guide, plan, RFC, or documentation resource
- **Config** - Configuration file or configuration artifact
- **Schema** - Formal schema, contract, or structured data definition
- **Template** - Reusable template or scaffold
- **Test** - Test suite, test case, or testing artifact
- **Concept** - Abstract idea, methodology, or general technical concept
- **Pattern** - Named design, architecture, or implementation pattern
- **Antipattern** - Named bad practice or harmful pattern
- **Principle** - Guiding rule or design principle
- **Task** - TODO, action item, or work to be done (see Task Extraction Rules below)
- **Feature** - Product capability or implemented user-facing behavior
- **Bug** - Defect or incorrect behavior
- **Issue** - Broader problem, risk, inconsistency, or unresolved concern
- **Fix** - Concrete remediation or correction
- **Event** - Time-bound incident, milestone, or notable occurrence
- **Procedure** - Step-by-step executable workflow (see Procedure Extraction Rules below)
- **ProcedureStep** - Individual step within a procedure
- **SyncBatch** - System-generated provenance batch for network sync submissions; not a normal conversational extraction target

Do not invent new entity types during normal extraction. Use the closest canonical type above.

Important boundaries:
- Use `File` for concrete paths like `scripts/query_memory.py`; use `Document` for conceptual specs/guides.
- Use `Procedure` for workflows, processes, and pipelines; `Workflow`, `Process`, and `Pipeline` are not canonical output types.
- Use `Bug` for defects, `Issue` for broader gaps/risks, and `Fix` for the remediation.
- Use `Technology` for frameworks/languages/libraries, `Tool` for directly used utilities/CLIs, and `Service` for hosted systems.
- `SyncBatch` is reserved for deterministic system provenance writes, not normal LLM extraction from conversation text.

---

## Extraction Rules

### 1. Entity Identification
- Extract all significant entities, concepts, or actors mentioned in the message
- Include technologies, tools, people, organizations, concepts, and documents
- Disambiguate pronouns to actual entity names when possible

### 2. Extract CONCEPTS, not TOOLS

**CRITICAL: Extract WHAT is being done, not HOW it's being done**

❌ **BAD (extracting tools/commands):**
- "ALTER TABLE command"
- "for loop"
- "HTTP POST request"
- "JSON format"

✅ **GOOD (extracting concepts/patterns):**
- "Dynamic task property extension"
- "Batch entity processing"
- "OpenTimestamps submission"
- "Timestamped conversation format"

**Ask yourself:** "What is this ACCOMPLISHING?" not "What command/tool is being used?"

### 3. Entity Classification
- Classify each entity using one of the ENTITY TYPES above
- Choose the most specific type that fits

### 4. Entity Summary - The 4-Part Template

Write RICH summaries that capture:

1. **What it is** - The concept/pattern/feature
2. **What problem it solves** - Why it exists
3. **How it works** - Implementation details (mention tools/commands here)
4. **Where it's used** - Context in the project

**Example:**
```
"Pattern for adding task-specific properties (status, priority) to Entity table
without breaking existing entities. Different entity types need different properties -
Tasks have status/priority while Technologies/Concepts don't. Implemented using
ALTER TABLE in _ensure_schema_exists method on first database connection. Enables
flexible schema in Kuzu graph database."
```

**The tool/command (ALTER TABLE) goes in the summary, NOT the entity name.**

### 5. Exclusions
- Do NOT extract relationships or actions (those will be extracted separately)
- Do NOT extract dates, times, or temporal information
- Do NOT extract pronouns like "you", "me", "he/she/they", "we/us"
- Do NOT extract generic programming constructs as entities (for loops, if statements)
- Do NOT extract standard commands/tools without context (SELECT, INSERT, HTTP GET)

### 6. Formatting
- Use full, unambiguous names (e.g., "React.js" not just "React" if that's clearer)
- Be consistent with naming across the conversation
- Entity names should be descriptive of PURPOSE, not implementation

### 6. Task Extraction Rules
- Extract TODOs, action items, or work mentioned to be done
- Extract things that are MISSING or NEEDED
- Tasks should be specific and actionable
- Include priority if mentioned (high, medium, low)
- Default status is "pending"
- Examples of tasks:
  - "We need to implement X"
  - "TODO: Add feature Y"
  - "Should create script Z"
  - "Next step is to build W"
  - "We are missing X"
  - "We need X"
  - "Should add X"
  - "Let's implement X"

### 7. Procedure Extraction Rules
- Extract step-by-step workflows, processes, or "how to do X" instructions
- A **Procedure** is the overall workflow with a goal and trigger
- **ProcedureSteps** are individual steps within that procedure
- Include `attributes` with structured procedure data

**Procedure attributes:**
- `goal` - What the procedure accomplishes
- `trigger_phrases` - When to use this procedure (e.g., "sync memory", "before commit")
- `prerequisites` - What must be true before starting
- `agent_scope` - Which agents can use this (e.g., "auggie", "codex", "all")
- `lifecycle_status` - Usually `"active"` for new procedures; use `"deprecated"`, `"superseded"`, or `"invalid"` only if the conversation clearly says so
- `search_text` - Flattened text for retrieval (generated by storage pipeline)

**ProcedureStep attributes:**
- `procedure_name` - Name of parent procedure (for quick filtering)
- `step_number` - Order within procedure
- `action` - What to do in this step
- `expected_output` - What success looks like
- `script_refs` - Scripts/files used in this step
- `search_text` - Flattened text for retrieval

**Examples of procedures:**
- "To sync memory, first run import_conversation.py, then..."
- "Before committing, you need to run sync.md..."
- "The workflow for X is: step 1, step 2, step 3..."
- "Here's how to do Y: first A, then B, then C"

---

## Output Format

Return a JSON object with this exact structure:

```json
{
  "entities": [
    {
      "name": "React",
      "type": "Technology",
      "summary": "A JavaScript library for building user interfaces"
    },
    {
      "name": "Meta",
      "type": "Organization",
      "summary": "Technology company that created and maintains React"
    },
    {
      "name": "Component-Based Architecture",
      "type": "Concept",
      "summary": "Design pattern where UI is built from reusable components"
    },
    {
      "name": "Implement External Document Import",
      "type": "Task",
      "summary": "Add ability to import and extract knowledge from external documents like PDFs and MD files",
      "priority": "high",
      "status": "pending"
    },
    {
      "name": "Memory Sync Workflow",
      "type": "Procedure",
      "summary": "Step-by-step process to sync conversation context to memory graph",
      "attributes": {
        "goal": "Persist conversation context to memory",
        "trigger_phrases": ["sync memory", "save to memory", "before commit"],
        "prerequisites": ["mem.config.json exists", "conversation has content"],
        "agent_scope": "all"
      }
    },
    {
      "name": "Memory Sync Step 1: Import Conversation",
      "type": "ProcedureStep",
      "summary": "Import conversation JSON to SQL database",
      "attributes": {
        "procedure_name": "Memory Sync Workflow",
        "step_number": 1,
        "action": "Run import_conversation.py with conversation JSON",
        "expected_output": "Interactions stored in SQL",
        "script_refs": ["scripts/import_conversation.py"]
      }
    }
  ]
}
```

### Field Descriptions:

- `name` - **String (required)** - Name of the entity (use full, unambiguous names)
- `type` - **String (required)** - One of the canonical entity types listed above
- `summary` - **String (optional)** - Brief 1-sentence description of the entity
- `priority` - **String (optional, Task only)** - One of: high, medium, low (default: medium)
- `status` - **String (optional, Task only)** - One of: pending, complete, invalid (default: pending)
- `attributes` - **Object (optional, Procedure/ProcedureStep)** - Structured metadata (see Procedure Extraction Rules)

---

## Examples

### Example 1: Technology Discussion

**Input:**
```
User: I'm using React with TypeScript for my new project.


Assistant: That's a great combination! TypeScript adds static typing to React.
```

**Output:**
```json
{
  "entities": [
    {
      "name": "React",
      "type": "Technology",
      "summary": "A JavaScript library for building user interfaces"
    },
    {
      "name": "TypeScript",
      "type": "Technology",
      "summary": "A typed superset of JavaScript that compiles to plain JavaScript"
    }
  ]
}
```

### Example 2: Person and Organization

**Input:**
```
User: John works at Google on the Chrome team.
```

**Output:**
```json
{
  "entities": [
    {
      "name": "John",
      "type": "Person",
      "summary": "A person who works at Google on the Chrome team"
    },
    {
      "name": "Google",
      "type": "Organization",
      "summary": "Technology company"
    },
    {
      "name": "Chrome",
      "type": "Technology",
      "summary": "Web browser developed by Google"
    }
  ]
}
```

### Example 3: Concepts

**Input:**
```
User: We're using microservices architecture with event-driven design.
```

**Output:**
```json
{
  "entities": [
    {
      "name": "Microservices Architecture",
      "type": "Concept",
      "summary": "Architectural style that structures an application as a collection of loosely coupled services"
    },
    {
      "name": "Event-Driven Design",
      "type": "Concept",
      "summary": "Design pattern where components communicate through events"
    }
  ]
}
```

### Example 4: Extract CONCEPTS not TOOLS

**Input:**
```
User: We use ALTER TABLE to dynamically add task-specific fields like status and priority to the Entity table.
Assistant: Right, this allows different entity types to have different properties without breaking existing entities.
```

**❌ BAD Output (extracting the tool):**
```json
{
  "entities": [
    {
      "name": "ALTER TABLE command",
      "type": "Concept",
      "summary": "SQL command to add columns to tables"
    }
  ]
}
```

**✅ GOOD Output (extracting the concept):**
```json
{
  "entities": [
    {
      "name": "Dynamic task property extension",
      "type": "Concept",
      "summary": "Pattern for adding task-specific properties (status, priority) to Entity table without breaking existing entities. Different entity types need different properties - Tasks have status/priority while Technologies/Concepts don't. Implemented using ALTER TABLE in _ensure_schema_exists method on first database connection. Enables flexible schema in Kuzu graph database."
    }
  ]
}
```

---

## Important Notes

- **Extraction scope:**
  - For most entities: extract from current message only
  - For **Procedure/ProcedureStep**: extract from recent message window (last 3-5 turns) since workflows often span multiple exchanges
- **Don't hallucinate** - Only extract entities actually mentioned
- **Be specific** - "React" is better than "JavaScript library"
- **Disambiguate** - If "React" could mean React.js or React Native, use context to clarify
- **No duplicates** - Each entity should appear only once
- **Valid JSON** - Ensure the output is valid, parseable JSON

---

## Quality Checklist

Before finalizing your extraction, check each entity:

### ✅ Entity Name Quality
- [ ] Does the name describe WHAT is being done (not HOW)?
- [ ] Is it a concept/pattern/feature (not a tool/command)?
- [ ] Would a human understand what this is from the name alone?

### ✅ Summary Quality
- [ ] Does it explain WHAT it is?
- [ ] Does it explain WHY it exists (what problem it solves)?
- [ ] Does it explain HOW it works (implementation details)?
- [ ] Does it explain WHERE it's used (context)?

### ✅ Common Mistakes to Avoid
- [ ] Not extracting "ALTER TABLE command" (extract "Dynamic schema extension" instead)
- [ ] Not extracting "for loop" (extract "Batch processing pattern" instead)
- [ ] Not extracting "HTTP POST" (extract "API submission pattern" instead)
- [ ] Not extracting "JSON format" (extract "Timestamped conversation format" instead)

**Remember:** The entity name should tell you WHAT, the summary should tell you WHY and HOW.

---

## Helper Functions (Optional)

If your LLM struggles with JSON formatting, you can use this helper script approach:

```python
# entities_builder.py - Helper script to build JSON
entities = []

def add_entity(name, entity_type, summary=""):
    entities.append({
        "name": name,
        "type": entity_type,
        "summary": summary
    })

# Your extraction logic
add_entity("React", "Technology", "A JavaScript library for building user interfaces")
add_entity("TypeScript", "Technology", "A typed superset of JavaScript")

# Output
import json
print(json.dumps({"entities": entities}, indent=2))
```

But **direct JSON output is preferred** if your LLM supports it.

---

## ⚠️ IMPORTANT: Entity Validation

**When creating facts later, you MUST reference entities you extracted here!**

**Common mistake:**
- Extract entity "Python"
- Later create fact: "Python" → "NumPy"
- But forgot to extract "NumPy" entity!
- Result: Fact gets skipped!

**Solution:**
- Extract ALL entities that will be referenced in facts
- Even "well-known" entities like OpenAI, ASCII Art, etc.
- Run validation: `python scripts/validate_extraction.py --file extraction.json`

**Remember:** If an entity appears in a fact, it MUST be in the entities list!
