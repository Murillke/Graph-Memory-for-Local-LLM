# Fact Contradiction Detection

You are reviewing extracted facts to identify contradictions with existing knowledge before adding them to the knowledge graph.

---

## Task

Review the questions in the input JSON file and determine if each new fact contradicts any existing facts.

---

## Types of Contradictions

### 1. **Direct Contradiction**
- New fact directly opposes existing fact
- Examples:
  - Existing: "React uses class components"
  - New: "React does not use class components"
- **Resolution:** Usually supersede (new fact replaces old)

### 2. **Temporal Contradiction**
- Facts with conflicting time ranges
- Examples:
  - Existing: "John worked at Google (2020-2023)"
  - New: "John worked at Microsoft (2022-2024)"
- **Resolution:** Coexist with adjusted time ranges, or one is wrong

### 3. **Logical Contradiction**
- Facts that cannot both be true
- Examples:
  - Existing: "Python is statically typed"
  - New: "Python is dynamically typed"
- **Resolution:** One is wrong, determine which

### 4. **Attribute Contradiction**
- Same relationship but different attributes
- Examples:
  - Existing: "React version is 17.0"
  - New: "React version is 18.0"
- **Resolution:** Supersede (version changed) or coexist (different contexts)

---

## Decision Process

For each question:

1. **Read the new fact carefully**
2. **Review all existing facts** about the same entities
3. **Identify conflicts** - Do any facts oppose each other?
4. **Determine type** - What kind of contradiction is it?
5. **Propose resolution** - How should this be resolved?
6. **Assess confidence** - How sure are you? (0.0 to 1.0)

**Be conservative:** Only mark as contradiction if >80% confident.

---

## Resolution Options

- `supersede` - New fact replaces old fact (old fact becomes invalid)
- `coexist` - Both facts can be true (adjust temporal ranges or context)
- `reject` - New fact is wrong, keep old fact
- `merge` - Combine both facts into a more complete fact

---

## Output Format

Return a JSON file with this exact structure:

```json
{
  "contradictions": [
    {
      "fact_index": 0,
      "contradicted_fact_uuids": ["xyz-789-abc-123"],
      "confidence": 0.92,
      "reason": "New fact states React uses hooks exclusively, but existing fact says React uses class components. Hooks were introduced later and are now preferred.",
      "resolution": "supersede",
      "resolution_details": "Mark old fact as invalid_at=2019-02-06 (when hooks were introduced). New fact becomes the current truth."
    },
    {
      "fact_index": 1,
      "contradicted_fact_uuids": [],
      "confidence": 0.95,
      "reason": "No contradiction. The new fact about Python's dynamic typing does not conflict with any existing facts.",
      "resolution": null,
      "resolution_details": null
    }
  ]
}
```

### Field Descriptions:

- `fact_index` - Index of the question being answered (from input file)
- `contradicted_fact_uuids` - Array of conflicting fact UUIDs (empty if none)
- `confidence` - Float 0.0-1.0: How confident you are in this decision
- `reason` - String: Clear explanation of your decision
- `resolution` - String: "supersede", "coexist", "reject", or "merge" (or `null` if no contradiction)
- `resolution_details` - String: Specific instructions for resolving (or `null` if no contradiction)

---

## Important Notes

- **Answer ALL questions** - One answer per question in the input file
- **Maintain order** - Answers should be in the same order as questions
- **Be thorough** - Provide clear reasoning for each decision
- **Consider context** - Facts may seem contradictory but be true in different contexts
- **Check temporal validity** - Facts can change over time (versions, employment, etc.)
- **Be conservative** - When in doubt, mark as NOT contradicting (false negatives are better than false positives)

---

## Example

**Input question:**
```json
{
  "fact_index": 0,
  "new_fact": {
    "source_entity": "React",
    "target_entity": "Hooks",
    "relationship_type": "USES",
    "fact": "React uses Hooks for state management instead of class components"
  },
  "existing_facts": [
    {
      "uuid": "old-fact-123",
      "source_entity": "React",
      "target_entity": "Class Components",
      "relationship_type": "USES",
      "fact": "React uses class components for state management",
      "valid_at": "2013-05-29T00:00:00Z"
    }
  ]
}
```

**Output answer:**
```json
{
  "fact_index": 0,
  "contradicted_fact_uuids": ["old-fact-123"],
  "confidence": 0.95,
  "reason": "The new fact states React uses Hooks instead of class components, which directly contradicts the existing fact. However, this is a temporal evolution - class components were used first, then Hooks were introduced in React 16.8 (Feb 2019) as the preferred approach.",
  "resolution": "coexist",
  "resolution_details": "Set invalid_at='2019-02-06T00:00:00Z' on the old fact (when Hooks were introduced). Both facts are historically true but at different times. The new fact represents current best practice."
}
```
