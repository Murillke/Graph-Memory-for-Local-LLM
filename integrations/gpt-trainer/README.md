# GPT-Trainer Integration

Integration with [GPT-trainer.com](https://gpt-trainer.com) for LLM-based entity and fact extraction.

## Overview

GPT-trainer allows you to create custom chatbots with any backing model (Claude, GPT-4o, etc.) and use them via API. This integration provides wrappers that use GPT-trainer chatbots for:

1. **Entity Extraction** - Extract entities from conversations
2. **Fact Extraction** - Extract relationships between entities  
3. **Quality Checking** - Review for contradictions and duplicates

## Benefits

- ✅ **Model Flexibility** - Choose backing model (Claude, GPT-4o, Gemini, etc.)
- ✅ **Single API** - One wrapper for multiple LLM backends
- ✅ **Custom Configuration** - Configure chatbot personality and system prompt
- ✅ **Cost Control** - Potentially more cost-effective than direct API calls
- ✅ **Dedicated Chatbots** - Create separate chatbots for different tasks

## Files

```
integrations/gpt-trainer/
├── README.md                           # This file
├── chatbot-configuration.md            # How to configure GPT-trainer chatbots
├── extraction_wrapper.py               # Entity/fact extraction wrapper
├── quality_wrapper.py                  # Quality check wrapper
└── prompts/
    ├── entity-extraction-system.md     # System prompt for entity extraction
    ├── fact-extraction-system.md       # System prompt for fact extraction
    └── quality-check-system.md         # System prompt for quality checking
```

## Quick Start

### 1. Create GPT-Trainer Chatbots

Follow `chatbot-configuration.md` to create 2 chatbots:
- **Entity/Fact Extraction Chatbot** - For extracting knowledge
- **Quality Check Chatbot** - For reviewing quality

### 2. Set Environment Variables

```powershell
# For extraction
$env:GPT_TRAINER_EXTRACTION_API_KEY = "your-api-key"
$env:GPT_TRAINER_EXTRACTION_CHATBOT_UUID = "extraction-chatbot-uuid"

# For quality checking
$env:GPT_TRAINER_QUALITY_API_KEY = "your-api-key"
$env:GPT_TRAINER_QUALITY_CHATBOT_UUID = "quality-chatbot-uuid"
```

### 3. Update Configuration

Edit `mem.config.json`:

```json
{
  "extraction": {
    "llm_wrapper_entities": "./integrations/gpt-trainer/extraction_wrapper.py",
    "llm_wrapper_facts": "./integrations/gpt-trainer/extraction_wrapper.py"
  },
  "quality_check": {
    "llm_wrapper": "./integrations/gpt-trainer/quality_wrapper.py"
  }
}
```

### 4. Test

```powershell
# Test entity extraction
.\python313\python.exe integrations\gpt-trainer\extraction_wrapper.py examples\current-conversation.json tmp\test-extraction.json entities

# Test quality check
.\python313\python.exe integrations\gpt-trainer\quality_wrapper.py tmp\questions.json tmp\answers.json
```

## Features

### Retry Logic

Both wrappers include automatic retry with JSON correction:
- 3 retry attempts on JSON parsing failure
- Sends "fix your JSON" prompt on retry
- Exponential backoff between retries

### JSON Sanitization

Automatically handles:
- Markdown code blocks (```json ... ```)
- Conversational filler text
- Malformed JSON structures

### Error Handling

Standard exit codes:
- `0` - Success
- `1` - Invalid arguments/environment
- `2` - API call failed (network/auth)
- `3` - Invalid response (after all retries)

## Troubleshooting

See `chatbot-configuration.md` for:
- Common configuration issues
- How to test chatbot responses
- Debugging tips

## Cost Comparison

| Provider | Model | Cost per 1M tokens |
|----------|-------|-------------------|
| OpenAI Direct | GPT-4o | $2.50 input / $10 output |
| Claude Direct | Claude 3.5 Sonnet | $3 input / $15 output |
| GPT-Trainer | Any model | Variable (check pricing) |

*Note: GPT-trainer pricing may include markup over direct API costs*

## Limitations

- 120-second timeout per request
- Requires internet connection
- Dependent on GPT-trainer service availability
- May have rate limits (check GPT-trainer docs)

## Support

For issues with:
- **This integration**: Open issue in this repo
- **GPT-trainer service**: Contact GPT-trainer support
- **Backing models**: Check model provider docs

