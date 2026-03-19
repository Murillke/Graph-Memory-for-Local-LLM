# Fact Extraction from Conversation

Extract factual relationships between entities from conversational messages.

---

## Task

Extract all factual relationships between entities based on the conversation, with relevant temporal information (when they became true and when they stopped being true).

---

## Extraction Rules

### 1. Entity Name Validation
- `source_entity` and `target_entity` must use EXACT names from the ENTITIES list provided
- Using names not in the list will cause the fact to be rejected

### 2. Distinct Entities
- Each fact must involve two **distinct** entities
- Cannot create a fact from an entity to itself

### 3. No Duplicates
- Do not emit duplicate or semantically redundant facts

### 4. Paraphrase, Don't Quote
- The fact should closely paraphrase the original sentence(s)
- Do not quote verbatim from the conversation

### 5. Temporal Resolution
- Use REFERENCE_TIME to resolve vague or relative temporal expressions (e.g., "last week", "recently")
- Do NOT hallucinate or infer temporal bounds from unrelated events

---

## Relationship Type Rules

**You MUST use one of the 29 canonical relationship types below.**
Unknown relationship types will be rejected during validation.

### Canonical Relationship Types (29 total)

| Category | Types |
|----------|-------|
| **Dependency/Usage** | `USES`, `DEPENDS_ON`, `BUILT_WITH`, `WRITTEN_IN`, `SUPPORTS`, `NOT_SUPPORTS` |
| **Structure** | `IMPLEMENTS`, `CONTAINS`, `PART_OF`, `LOCATED_AT` |
| **Lifecycle** | `CREATES`, `SUPERSEDES` |
| **Documentation** | `DOCUMENTS`, `REFERENCES` |
| **Causation/Resolution** | `CAUSES`, `RESOLVES` |
| **Security** | `VULNERABLE_TO`, `NOT_VULNERABLE_TO`, `MITIGATES`, `COMPROMISES` |
| **Preferences/Decisions** | `PREFERS`, `DECIDED` |
| **Procedural** | `PRECEDES`, `RUNS`, `EXECUTES`, `HAS_STEP_RUN`, `EXTRACTED_FROM` |
| **Generic** | `RELATED_TO`, `SIMILAR_TO` |

### Relationships for Procedural Entities

Use these when extracting Procedure and ProcedureStep entities:

| Type | Category | Usage | Example |
|------|----------|-------|---------|
| `CONTAINS` | Structure | Procedure contains step | Procedure -[CONTAINS]-> ProcedureStep |
| `PRECEDES` | Procedural | Step ordering | Step1 -[PRECEDES]-> Step2 |
| `RUNS` | Procedural | Execution record | ProcedureRun -[RUNS]-> Procedure |
| `EXECUTES` | Procedural | Agent execution | Agent -[EXECUTES]-> Procedure |
| `HAS_STEP_RUN` | Procedural | Step execution | ProcedureRun -[HAS_STEP_RUN]-> StepRun |
| `EXTRACTED_FROM` | Procedural | Provenance | Procedure -[EXTRACTED_FROM]-> Document |

Note: `CONTAINS` is in the Structure category but commonly used with procedures.

### Common Synonyms (automatically normalized)

These are accepted but will be normalized to canonical types:
- `REQUIRES`, `NEEDS` → `DEPENDS_ON`
- `UTILIZES`, `EMPLOYS`, `LEVERAGES` → `USES`
- `FIXES`, `ADDRESSES`, `SOLVES` → `RESOLVES`
- `REPLACES` → `SUPERSEDES`
- `COMES_BEFORE`, `FOLLOWED_BY` → `PRECEDES`
- `INVOKES`, `CALLS` → `EXECUTES`
- `DERIVED_FROM`, `SOURCED_FROM` → `EXTRACTED_FROM`
- `INCLUDES`, `HAS`, `OWNS` → `CONTAINS`
- `BELONGS_TO`, `MEMBER_OF` → `PART_OF`
- `EXTENDS`, `INHERITS` → `IMPLEMENTS`
- `DESCRIBES` → `DOCUMENTS`
- `LINKS_TO` → `REFERENCES`
- `TRIGGERS`, `LEADS_TO`, `RESULTS_IN` → `CAUSES`
- `GENERATES`, `PRODUCES`, `BUILDS` → `CREATES`
- `COMPATIBLE_WITH`, `WORKS_WITH` → `SUPPORTS`
- `INCOMPATIBLE_WITH` → `NOT_SUPPORTS`
- `ASSOCIATED_WITH`, `CONNECTED_TO` → `RELATED_TO`
- `RESEMBLES`, `LIKE` → `SIMILAR_TO`

### Inverse Types (source/target will be swapped)

These are accepted but will have source/target swapped during storage:
- `USED_BY` → `USES` (swapped)
- `CAUSED_BY` → `CAUSES` (swapped)
- `CREATED_BY` → `CREATES` (swapped)
- `RESOLVED_BY`, `SOLVED_BY` → `RESOLVES` (swapped)
- `CONTAINED_IN` → `CONTAINS` (swapped)
- `IMPLEMENTED_BY` → `IMPLEMENTS` (swapped)
- `SUPERSEDED_BY`, `REPLACED_BY` → `SUPERSEDES` (swapped)

**⚠️ Do NOT invent new relationship types** - use one from the list above or `RELATED_TO` as a fallback

---

## DateTime Rules

- Use ISO 8601 format with "Z" suffix (UTC)
  - Example: `2025-04-30T00:00:00Z`
- If the fact is ongoing (present tense), set `valid_at` to REFERENCE_TIME
- If a change/termination is expressed, set `invalid_at` to the relevant timestamp
- Leave both fields empty (`null`) if no explicit or resolvable time is stated
- If only a date is mentioned (no time), assume `00:00:00`
- If only a year is mentioned, use January 1st at `00:00:00`

---

## Output Format

Return a JSON object with this exact structure:

```json
{
  "facts": [
    {
      "source_entity": "React",
      "target_entity": "Hooks",
      "relationship_type": "USES",
      "fact": "React uses Hooks for state management in functional components",
      "valid_at": "2019-02-06T00:00:00Z",
      "invalid_at": null
    },
    {
      "source_entity": "Meta",
      "target_entity": "React",
      "relationship_type": "CREATES",
      "fact": "Meta created and develops the React library",
      "valid_at": null,
      "invalid_at": null
    }
  ]
}
```

### Field Descriptions:

- `source_entity` - **String (required)** - Name of the source entity (must be from ENTITIES list)
- `target_entity` - **String (required)** - Name of the target entity (must be from ENTITIES list)
- `relationship_type` - **String (required)** - Relationship in SCREAMING_SNAKE_CASE
- `fact` - **String (required)** - Paraphrased description of the relationship
- `valid_at` - **String (ISO 8601) or null** - When the fact became true
- `invalid_at` - **String (ISO 8601) or null** - When the fact stopped being true

---

## Examples

### Example 1: Technology Usage

**ENTITIES:**
- React
- TypeScript
- Next.js

**CURRENT MESSAGE:**
```
User: I'm building my app with Next.js, which uses React and TypeScript.
```

**REFERENCE_TIME:** `2025-03-06T00:00:00Z`

**Output:**
```json
{
  "facts": [
    {
      "source_entity": "Next.js",
      "target_entity": "React",
      "relationship_type": "USES",
      "fact": "Next.js uses React as its underlying UI library",
      "valid_at": "2025-03-06T00:00:00Z",
      "invalid_at": null
    },
    {
      "source_entity": "Next.js",
      "target_entity": "TypeScript",
      "relationship_type": "SUPPORTS",
      "fact": "Next.js supports TypeScript for type-safe development",
      "valid_at": "2025-03-06T00:00:00Z",
      "invalid_at": null
    }
  ]
}
```

### Example 2: Dependency with Temporal Information

**ENTITIES:**
- React
- Webpack
- Vite

**CURRENT MESSAGE:**
```
User: React used Webpack for bundling from 2018 to 2023, then many projects switched to Vite.
```

**REFERENCE_TIME:** `2025-03-06T00:00:00Z`

**Output:**
```json
{
  "facts": [
    {
      "source_entity": "React",
      "target_entity": "Webpack",
      "relationship_type": "DEPENDS_ON",
      "fact": "React projects depended on Webpack for bundling",
      "valid_at": "2018-01-01T00:00:00Z",
      "invalid_at": "2023-12-31T23:59:59Z"
    },
    {
      "source_entity": "React",
      "target_entity": "Vite",
      "relationship_type": "DEPENDS_ON",
      "fact": "Many React projects now depend on Vite for bundling",
      "valid_at": "2023-01-01T00:00:00Z",
      "invalid_at": null
    }
  ]
}
```

### Example 3: Project Relationships

**ENTITIES:**
- React
- Meta
- Component-Based Architecture

**CURRENT MESSAGE:**
```
User: React was created by Meta and implements component-based architecture.
```

**REFERENCE_TIME:** `2025-03-06T00:00:00Z`

**Output:**
```json
{
  "facts": [
    {
      "source_entity": "Meta",
      "target_entity": "React",
      "relationship_type": "CREATES",
      "fact": "Meta created the React library",
      "valid_at": null,
      "invalid_at": null
    },
    {
      "source_entity": "React",
      "target_entity": "Component-Based Architecture",
      "relationship_type": "IMPLEMENTS",
      "fact": "React implements component-based architecture for building UIs",
      "valid_at": null,
      "invalid_at": null
    }
  ]
}
```

---

## Important Notes

- **Extraction scope:**
  - For most facts: extract from CURRENT MESSAGE only, use PREVIOUS MESSAGES for context/disambiguation
  - For **procedures**: extract from recent message window (last 3-5 turns) since workflows often span multiple exchanges
- **Validate entity names** - Both source and target must be in the ENTITIES list
- **No self-relationships** - source_entity ≠ target_entity
- **Be precise with temporal info** - Don't guess dates if not mentioned
- **Valid JSON** - Ensure the output is valid, parseable JSON
- **Use null, not empty strings** - For missing temporal fields, use `null` not `""`

---

## Helper Functions (Optional)

If your LLM struggles with JSON formatting, you can use this helper script approach:

```python
# facts_builder.py - Helper script to build JSON
facts = []

def add_fact(source, target, rel_type, fact_text, valid_at=None, invalid_at=None):
    facts.append({
        "source_entity": source,
        "target_entity": target,
        "relationship_type": rel_type,
        "fact": fact_text,
        "valid_at": valid_at,
        "invalid_at": invalid_at
    })

# Your extraction logic
add_fact("React", "Hooks", "USES", 
         "React uses Hooks for state management",
         valid_at="2019-02-06T00:00:00Z")

add_fact("Meta", "React", "MAINTAINS",
         "Meta maintains the React library")

# Output
import json
print(json.dumps({"facts": facts}, indent=2))
```

But **direct JSON output is preferred** if your LLM supports it.

---

## ⚠️ CRITICAL: Validate Before Storing

**After creating your extraction.json, ALWAYS validate it:**

```bash
python scripts/validate_extraction.py --file extraction.json
```

**This checks:**
- ✅ All source_entity in facts exist in entities list
- ✅ All target_entity in facts exist in entities list
- ✅ All relationship_type values are valid (canonical, synonym, or inverse)
- ✅ Required fields present

**If validation fails:**
1. Read error messages
2. Fix issues:
   - Add missing entities to entities list
   - Replace unknown relationship types with canonical types (see list above)
3. Run validation again
4. Only store when validation passes!

**Remember:**
- Every entity referenced in facts MUST be in the entities list!
- Every relationship_type MUST be from the canonical list (or a recognized synonym/inverse)!

