# Entity Duplication Detection

You are reviewing extracted entities to identify duplicates before adding them to the knowledge graph.

---

## Task

Review the questions in the input JSON file and determine if each new entity is a duplicate of an existing entity.

---

## Criteria

### 1. **Exact Duplicates**
- Same name (case-insensitive)
- Same entity type/labels
- **Action:** Mark as duplicate

### 2. **Semantic Duplicates**
- Different names but same meaning
- Examples:
  - "React.js" vs "React"
  - "PostgreSQL" vs "Postgres"
  - "JavaScript" vs "JS"
- **Action:** Mark as duplicate, prefer the more formal/complete name

### 3. **Partial Duplicates**
- Overlapping but not identical
- Examples:
  - "Python" vs "Python 3.11"
  - "React" vs "React Hooks"
- **Action:** NOT duplicates - these are different entities

### 4. **Homonyms**
- Same name but different meaning
- Examples:
  - "Java" (programming language) vs "Java" (island)
  - "Mercury" (planet) vs "Mercury" (element)
- **Action:** NOT duplicates - check attributes/context

---

## Decision Process

For each question:

1. **Compare names** - Are they identical or very similar?
2. **Check attributes** - Do they have the same properties?
3. **Consider context** - What are they used for?
4. **Check labels** - Are they the same type of entity?
5. **Assess confidence** - How sure are you? (0.0 to 1.0)

**Be conservative:** Only mark as duplicate if >90% confident.

---

## Output Format

Return a JSON file with this exact structure:

```json
{
  "duplicates": [
    {
      "new_entity_name": "React.js",
      "is_duplicate": true,
      "duplicate_name": "React",
      "duplicate_uuid": "abc-123-def-456",
      "confidence": 0.95,
      "reason": "Both refer to the React JavaScript library. 'React.js' is just an alternative name for 'React'."
    },
    {
      "new_entity_name": "Python 3.11",
      "is_duplicate": false,
      "confidence": 0.99,
      "reason": "While both are about Python, 'Python 3.11' is a specific version, not the same as the general 'Python' entity."
    }
  ]
}
```

### Field Descriptions:

- `new_entity_name` - Name of the new entity being reviewed
- `is_duplicate` - Boolean: true if duplicate, false if not
- `duplicate_name` - Canonical existing entity name (only if is_duplicate=true)
- `duplicate_uuid` - UUID of the existing entity (only if is_duplicate=true)
- `confidence` - Float 0.0-1.0: How confident you are in this decision
- `reason` - String: Clear explanation of your decision

---

## Important Notes

- **Answer ALL questions** - One answer per question in the input file
- **Maintain order** - Answers should be in the same order as questions
- **Be thorough** - Provide clear reasoning for each decision
- **Be conservative** - When in doubt, mark as NOT duplicate (false negatives are better than false positives)

---

## Example

**Input question:**
```json
{
  "question_index": 0,
  "new_entity": {
    "name": "React.js",
    "labels": ["technology", "library"],
    "summary": "A JavaScript library for building user interfaces"
  },
  "existing_entities": [
    {
      "uuid": "abc-123",
      "name": "React",
      "labels": ["technology", "library"],
      "summary": "JavaScript library for building UIs"
    }
  ]
}
```

**Output answer:**
```json
{
  "new_entity_name": "React.js",
  "is_duplicate": true,
  "duplicate_name": "React",
  "duplicate_uuid": "abc-123",
  "confidence": 0.98,
  "reason": "Both refer to the same React library. 'React.js' is an alternative name for 'React'. Same labels, same purpose, same technology."
}
```
