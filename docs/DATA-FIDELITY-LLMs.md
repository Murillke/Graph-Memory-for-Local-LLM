# Data Fidelity Tracking

**Track the quality and source of conversation data in the memory system.**

---

## [TARGET] Purpose

**Problem:** When importing conversations, some are exact transcripts while others are reconstructed from summaries.

**Solution:** Track data fidelity so we always know:
- [OK] Which conversations are word-for-word accurate
- [WARNING] Which are paraphrased/reconstructed
- [DATA] Where the data came from

**Principle:** **Always prefer full data over paraphrased data.**

---

## [DATA] Fidelity Levels

### 1. `full` - Exact Text [OK]

**Definition:** Word-for-word, verbatim conversation text

**Examples:**
- Direct export from Auggie's recent conversation history
- Copy-pasted from chat logs
- API-captured conversations

**Quality:** Highest - can be used for exact replay, analysis, training

**Source Note Examples:**
- "Exact text from recent conversation exchanges"
- "Direct export from Auggie conversation on 2026-03-01"
- "Copy-pasted from chat transcript"

---

### 2. `paraphrased` - Key Points Accurate [WARNING]

**Definition:** Reconstructed conversation capturing key points but not exact words

**Examples:**
- Recreated from conversation summary
- Human-written summary of what was discussed
- Condensed version of longer exchange

**Quality:** Medium - good for knowledge extraction, not for exact replay

**Source Note Examples:**
- "Reconstructed from conversation summary - key points accurate but not verbatim"
- "Paraphrased from meeting notes"
- "Summary of 2-hour conversation"

---

### 3. `reconstructed` - Recreated from Memory [NOTE]

**Definition:** Conversation recreated from partial information or memory

**Examples:**
- Auggie reconstructing from compressed summary
- User recalling conversation from memory
- Pieced together from multiple sources

**Quality:** Lower - facts may be accurate but details/phrasing uncertain

**Source Note Examples:**
- "Reconstructed from Auggie's conversation summary"
- "User's recollection of conversation from last week"
- "Pieced together from notes and memory"

---

### 4. `summary` - High-Level Overview [LIST]

**Definition:** High-level summary, not a conversation transcript

**Examples:**
- Executive summary of discussion
- Meeting minutes
- Project status update

**Quality:** Lowest for conversation replay - good for context only

**Source Note Examples:**
- "Executive summary of project kickoff meeting"
- "Weekly status update - not verbatim"
- "High-level overview of discussion topics"

---

### 5. `llm-state` - Session Synthesis [BOT]

**Definition:** Compact high-signal synthesis of the model's current understanding of the whole working session

**Examples:**
- End-of-session engineering state capture
- One concise summary of goals, completed work, blockers, and scope decisions
- Sync-time summary for long coding sessions where raw turns are too tactical

**Quality:** High for continuity and recall, but not a transcript substitute

**Source Note Examples:**
- "Session-level synthesis captured during sync"
- "LLM state summary of completed work, blockers, and open questions"
- "Compact working-session snapshot for future recall"

---

##  Database Schema

### SQL Database

```sql
CREATE TABLE interactions (
    ...
    -- Data fidelity tracking
    fidelity TEXT DEFAULT 'full' 
        CHECK(fidelity IN ('full', 'paraphrased', 'reconstructed', 'summary', 'llm-state')),
    source_note TEXT,
    ...
);
```

**Fields:**
- `fidelity`: One of the 5 levels above
- `source_note`: Free-text description of data source/quality

---

## [NOTE] Usage Examples

### Example 1: Importing Full Conversation

```json
{
  "exchanges": [
    {
      "user": "What's missing?",
      "assistant": "Perfect! Now let me create a gap analysis...",
      "fidelity": "full",
      "source_note": "Exact text from Auggie conversation on 2026-03-01"
    }
  ]
}
```

### Example 2: Importing Paraphrased Conversation

```json
{
  "exchanges": [
    {
      "user": "Let's work on that integration",
      "assistant": "I'll create integration documentation...",
      "fidelity": "paraphrased",
      "source_note": "Reconstructed from conversation summary - key points accurate but not verbatim"
    }
  ]
}
```

### Example 3: Mixed Fidelity

```json
{
  "exchanges": [
    {
      "user": "Earlier discussion about database schema",
      "assistant": "We decided on SQL + Graph dual storage",
      "fidelity": "summary",
      "source_note": "High-level summary of early design discussions"
    },
    {
      "user": "Why worried about deduplication?",
      "assistant": "We should copy Graphiti's proven solutions...",
      "fidelity": "full",
      "source_note": "Exact text from recent conversation"
    }
  ]
}
```

---

## [SEARCH] Querying by Fidelity

### Get Only Full-Fidelity Conversations

```sql
SELECT * FROM interactions
WHERE fidelity = 'full'
ORDER BY timestamp DESC;
```

### Get All Non-Full Data (for review)

```sql
SELECT uuid, fidelity, source_note, 
       substr(user_message, 1, 50) as preview
FROM interactions
WHERE fidelity != 'full'
ORDER BY timestamp DESC;
```

### Count by Fidelity Level

```sql
SELECT fidelity, COUNT(*) as count
FROM interactions
GROUP BY fidelity
ORDER BY 
    CASE fidelity
        WHEN 'full' THEN 1
        WHEN 'paraphrased' THEN 2
        WHEN 'reconstructed' THEN 3
        WHEN 'summary' THEN 4
        WHEN 'llm-state' THEN 5
    END;
```

---

## [OK] Best Practices

### 1. Always Specify Fidelity

**Good:**
```python
interaction = {
    'user_message': '...',
    'assistant_message': '...',
    'fidelity': 'full',
    'source_note': 'Direct export from Auggie'
}
```

**Bad:**
```python
interaction = {
    'user_message': '...',
    'assistant_message': '...'
    # Missing fidelity - defaults to 'full' but may not be accurate!
}
```

---

### 2. Prefer Full Over Paraphrased

**When you have both:**
- [OK] Use the full version
- [ERROR] Don't import paraphrased if full exists

**When importing:**
- Import recent exchanges as `full` (you have exact text)
- Import older exchanges as `paraphrased` (reconstructed from summary)

---

### 3. Be Honest in Source Notes

**Good source notes:**
- "Exact text from Auggie conversation on 2026-03-01"
- "Reconstructed from conversation summary - key points accurate"
- "User's recollection - may have inaccuracies"

**Bad source notes:**
- "Probably accurate" (too vague)
- "" (empty - no information)
- "Full conversation" (when it's actually paraphrased)

---

### 4. Use for Knowledge Extraction Priority

**When extracting entities/facts:**

1. **Priority 1:** Extract from `fidelity='full'` first
2. **Priority 2:** Extract from `fidelity='paraphrased'` 
3. **Priority 3:** Extract from `fidelity='reconstructed'`
4. **Priority 4:** Extract from `fidelity='summary'`

**Why:** Full data is more reliable for extraction.

---

## [START] Future Enhancements

### Potential Additions:

1. **Confidence Score** (0.0 - 1.0)
   - `full`: 1.0
   - `paraphrased`: 0.7-0.9
   - `reconstructed`: 0.5-0.7
   - `summary`: 0.3-0.5

2. **Verification Status**
   - `verified`: User confirmed accuracy
   - `unverified`: Not yet reviewed
   - `disputed`: User flagged as inaccurate

3. **Source Metadata**
   - Original file path
   - Export timestamp
   - Auggie version
   - Conversation ID

---

## [DATA] Summary

**Fidelity tracking lets us:**
- [OK] Know which data is most reliable
- [OK] Prioritize full data over paraphrased
- [OK] Track data provenance
- [OK] Make informed decisions about data quality

**Always prefer full data, but paraphrased is better than nothing!** 

