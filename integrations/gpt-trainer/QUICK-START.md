# GPT-Trainer Quick Start

Get up and running with GPT-trainer integration in 5 minutes.

## Step 1: Create Chatbots (5 min)

1. Go to [GPT-trainer.com](https://gpt-trainer.com)
2. Create 2 chatbots:
   - **Extraction Chatbot** - For entity/fact extraction
   - **Quality Chatbot** - For quality checking

### Extraction Chatbot Settings

- **Name:** LLM Memory - Extraction
- **Model:** Claude 3.5 Sonnet
- **Temperature:** 0.1
- **Max Tokens:** 4000
- **System Prompt:** Copy from `prompts/entity-extraction-system.md`
- **Data Sources:** NONE (leave empty!)

### Quality Chatbot Settings

- **Name:** LLM Memory - Quality Check
- **Model:** Claude 3.5 Sonnet
- **Temperature:** 0.2
- **Max Tokens:** 2000
- **System Prompt:** Copy from `prompts/quality-check-system.md`
- **Data Sources:** NONE (leave empty!)

## Step 2: Get Credentials (2 min)

1. Go to Settings → API Keys
2. Create API key, copy it
3. Go to each chatbot, copy UUID from URL

## Step 3: Set Environment Variables (1 min)

```powershell
# Extraction
$env:GPT_TRAINER_EXTRACTION_API_KEY = "your-api-key"
$env:GPT_TRAINER_EXTRACTION_CHATBOT_UUID = "extraction-uuid"

# Quality
$env:GPT_TRAINER_QUALITY_API_KEY = "your-api-key"
$env:GPT_TRAINER_QUALITY_CHATBOT_UUID = "quality-uuid"
```

## Step 4: Update Config (1 min)

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

## Step 5: Test (1 min)

```powershell
# Test extraction
.\python313\python.exe scripts\extract_knowledge_llm.py --project llm_memory --limit 1

# Check output
cat tmp\extraction-*.json
```

## Done! 🎉

Your LLM Memory system now uses GPT-trainer!

## Troubleshooting

**"Environment variable not set"**
- Run Step 3 again in current PowerShell session

**"Invalid JSON in response"**
- Check chatbot system prompt matches exactly
- Test chatbot directly in GPT-trainer UI
- Make sure Data Sources is empty

**"API request failed"**
- Check API key is correct
- Check chatbot UUID is correct
- Verify internet connection

## Next Steps

- Read `README.md` for full documentation
- Read `chatbot-configuration.md` for detailed setup
- Monitor usage in GPT-trainer dashboard
- Adjust temperature/tokens based on results

## Cost Estimate

Typical conversation (500 tokens):
- Extraction: ~$0.002 per conversation
- Quality check: ~$0.001 per check
- Total: ~$0.003 per conversation

For 1000 conversations/month: ~$3/month

*Actual costs depend on backing model and GPT-trainer pricing*

