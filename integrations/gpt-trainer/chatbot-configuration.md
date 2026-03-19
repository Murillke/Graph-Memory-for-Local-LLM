# GPT-Trainer Chatbot Configuration Guide

This guide explains how to configure GPT-trainer chatbots for use with the LLM Memory system.

## Overview

You need to create **2 separate chatbots** in GPT-trainer:

1. **Extraction Chatbot** - For entity and fact extraction
2. **Quality Check Chatbot** - For reviewing contradictions and duplicates

## Why Separate Chatbots?

- Different system prompts and behaviors
- Different backing models (if desired)
- Easier to debug and monitor
- Better cost tracking

---

## Chatbot 1: Extraction Chatbot

### Purpose
Extract entities and facts from conversation exchanges.

### Recommended Settings

**Name:** `LLM Memory - Entity & Fact Extraction`

**Backing Model:** Claude 3.5 Sonnet (or GPT-4o)
- Claude is better at following structured output requirements
- GPT-4o is faster and cheaper

**Temperature:** 0.1
- Low temperature for consistent, structured output
- Reduces hallucinations

**Max Tokens:** 4000
- Enough for complex extractions
- Adjust based on conversation length

### System Prompt

Copy the content from `prompts/entity-extraction-system.md` into the chatbot's system prompt field.

**Key Instructions:**
- Focus on WHY things happen, not WHO said them
- Extract conceptual entities (bugs, features, findings)
- Avoid person names and conversational entities
- Return ONLY valid JSON, no markdown, no explanations

### Data Sources

**IMPORTANT:** Do NOT add any data sources!
- Empty chatbot = no RAG interference
- All context comes from the query
- Prevents hallucinations from unrelated data

### Testing

Test with this query:
```
SYSTEM INSTRUCTIONS:
Extract entities from this conversation exchange.

USER REQUEST:
User: The database connection keeps timing out after 30 seconds
Assistant: I found the issue - the connection pool size is too small. Increasing it to 50 fixed the timeout problem.

Return JSON with entities array.
```

Expected response:
```json
{
  "entities": [
    {
      "name": "Database connection timeout issue",
      "type": "Bug",
      "summary": "Database connections timing out after 30 seconds due to small connection pool size"
    },
    {
      "name": "Connection pool size increase fix",
      "type": "Fix",
      "summary": "Increasing connection pool size to 50 resolved timeout issues"
    }
  ]
}
```

---

## Chatbot 2: Quality Check Chatbot

### Purpose
Review entity/fact pairs for contradictions and duplicates.

### Recommended Settings

**Name:** `LLM Memory - Quality Check`

**Backing Model:** Claude 3.5 Sonnet (or GPT-4o)
- Needs strong reasoning for contradiction detection
- Claude excels at nuanced comparisons

**Temperature:** 0.2
- Slightly higher for better reasoning
- Still low enough for consistency

**Max Tokens:** 2000
- Shorter responses (just decisions)
- Adjust if reviewing many pairs

### System Prompt

Copy the content from `prompts/quality-check-system.md` into the chatbot's system prompt field.

**Key Instructions:**
- Review for contradictions and duplicates
- Be conservative (when in doubt, keep both)
- Return decisions array with reasoning
- Return ONLY valid JSON

### Data Sources

**IMPORTANT:** Do NOT add any data sources!
- Same reason as extraction chatbot
- All context in the query

### Testing

Test with this query:
```
SYSTEM INSTRUCTIONS:
Review these entity pairs for contradictions or duplicates.

USER REQUEST:
{
  "questions": [
    {
      "type": "duplicate",
      "entity1": {"name": "Bug fix for login", "summary": "Fixed login timeout"},
      "entity2": {"name": "Login timeout fix", "summary": "Resolved login timing out"}
    }
  ]
}

Return JSON with decisions array.
```

Expected response:
```json
{
  "decisions": [
    {
      "question_index": 0,
      "decision": "duplicate",
      "keep": "entity1",
      "reasoning": "Both describe the same fix for login timeout issue"
    }
  ]
}
```

---

## Getting API Credentials

### 1. Get API Key

1. Log into GPT-trainer.com
2. Go to Settings → API Keys
3. Create new API key
4. Copy and save securely

### 2. Get Chatbot UUIDs

1. Go to Chatbots
2. Click on chatbot
3. Copy UUID from URL: `https://app.gpt-trainer.com/chatbot/{UUID}`

### 3. Set Environment Variables

```powershell
# Extraction chatbot
$env:GPT_TRAINER_EXTRACTION_API_KEY = "your-api-key"
$env:GPT_TRAINER_EXTRACTION_CHATBOT_UUID = "extraction-chatbot-uuid"

# Quality check chatbot  
$env:GPT_TRAINER_QUALITY_API_KEY = "your-api-key"
$env:GPT_TRAINER_QUALITY_CHATBOT_UUID = "quality-chatbot-uuid"
```

---

## Troubleshooting

### Chatbot returns conversational text instead of JSON

**Problem:** "Sure! Here's the JSON: ```json {...} ```"

**Solution:**
- Emphasize in system prompt: "Return ONLY JSON, no explanations"
- Lower temperature to 0.1
- The wrapper handles Markdown code blocks automatically

### Chatbot adds extra fields

**Problem:** JSON has unexpected fields like `"note": "..."`

**Solution:**
- Specify exact JSON structure in system prompt
- Show example output
- The wrapper validates required fields

### Timeout errors

**Problem:** Requests timing out after 120 seconds

**Solution:**
- Reduce max tokens
- Simplify system prompt
- Check GPT-trainer service status

### Invalid JSON errors after retries

**Problem:** All 3 retries fail with JSON errors

**Solution:**
- Test chatbot directly in GPT-trainer UI
- Check system prompt formatting
- Try different backing model
- Check for special characters in data

---

## Cost Optimization

### Use Cheaper Models for Simple Tasks

- **Entities:** Claude 3.5 Sonnet (best quality)
- **Facts:** GPT-4o (faster, cheaper, good enough)
- **Quality:** Claude 3.5 Sonnet (needs reasoning)

### Monitor Usage

- Check GPT-trainer dashboard for token usage
- Set up usage alerts
- Review costs monthly

### Batch Processing

- Process multiple conversations in one session
- Reduces API overhead
- Better token efficiency

---

## Next Steps

1. Create both chatbots in GPT-trainer
2. Configure system prompts from `prompts/` folder
3. Test with example queries
4. Set environment variables
5. Update `mem.config.json`
6. Run test extraction

See `README.md` for integration instructions.

