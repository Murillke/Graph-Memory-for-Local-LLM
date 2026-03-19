# Integrating llm_memory with OpenClaw

## 🦞 Overview

OpenClaw's **heartbeat system** is perfect for running llm_memory extraction in the background!

**The Pattern:**
- **Main agent** (OpenClaw) handles conversations → dumps to SQL (fast, ~10 seconds)
- **Heartbeat** (background) extracts to graph (slow, ~2 minutes per batch)
- **User** never waits for extraction!

---

## 🎯 Benefits

✅ **Fast agent response** - dump takes <1 second  
✅ **Automatic extraction** - heartbeat runs every 30 min  
✅ **No manual work** - set it and forget it  
✅ **Cryptographic integrity** - OpenTimestamps on every dump  
✅ **Knowledge graph** - always up-to-date (within 30 min)  
✅ **Works with your LLM** - OpenAI, Claude, Anthropic, OpenRouter, etc.

---

## 📦 Installation

### 1. Install llm_memory

```bash
cd ~/.openclaw
git clone https://github.com/yourusername/llm_memory.git
cd llm_memory
pip install -r requirements.txt
```

### 2. Initialize llm_memory

```bash
# Follow the initialization wizard
python scripts/init.py
```

This creates:
- `mem.config.json` - Configuration file
- `memory/` - Database directory
- `tmp/` - Temporary files directory

### 3. Configure LLM Wrapper

Edit `mem.config.json` to use your LLM provider:

**For OpenAI:**
```json
{
  "extraction": {
    "llm_wrapper_entities": "./scripts/extraction_wrapper_openai.py",
    "llm_wrapper_facts": "./scripts/extraction_wrapper_openai.py"
  }
}
```

**For Claude:**
```json
{
  "extraction": {
    "llm_wrapper_entities": "./scripts/extraction_wrapper_claude.py",
    "llm_wrapper_facts": "./scripts/extraction_wrapper_claude.py"
  }
}
```

**For Ollama (local):**
```json
{
  "extraction": {
    "llm_wrapper_entities": "./scripts/extraction_wrapper_ollama.py",
    "llm_wrapper_facts": "./scripts/extraction_wrapper_ollama.py"
  }
}
```

### 4. Set Environment Variables

**For OpenAI:**
```bash
export OPENAI_API_KEY="sk-..."
export OPENAI_MODEL="gpt-4"  # Optional, defaults to gpt-4
```

**For Claude:**
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export ANTHROPIC_MODEL="claude-3-5-sonnet-20241022"  # Optional
```

**For OpenRouter (any model):**
```bash
export OPENAI_API_KEY="sk-or-..."
export OPENAI_BASE_URL="https://openrouter.ai/api/v1"
export OPENAI_MODEL="anthropic/claude-3.5-sonnet"
```

**For Ollama (local):**
```bash
export OLLAMA_MODEL="llama3.1:8b"  # Or any local model
export OLLAMA_BASE_URL="http://localhost:11434"  # Optional
```

---

## ⚙️ Configure OpenClaw Heartbeat

### Option 1: Using openclaw.json

Edit `~/.openclaw/openclaw.json`:

```json
{
  "heartbeat": {
    "enabled": true,
    "interval": 1800,
    "tasks": ["llm_memory_extract"]
  },
  "custom_commands": {
    "llm_memory_extract": {
      "command": "cd ~/.openclaw/llm_memory && python scripts/extract_with_wrappers.py --project openclaw --limit 50 && python scripts/store_extraction.py --project openclaw --extraction-file tmp/extraction.json",
      "description": "Extract pending conversations to knowledge graph"
    }
  }
}
```

### Option 2: Using HEARTBEAT.md

Create or edit `~/.openclaw/workspace/HEARTBEAT.md`:

```markdown
# OpenClaw Heartbeat Tasks

## Knowledge Graph Extraction

Every 30 minutes, extract pending conversations to the knowledge graph.

**Steps:**
1. Check for pending conversations
2. Extract up to 50 conversations using configured LLM
3. Store entities and facts in graph database

**Commands:**
```bash
cd ~/.openclaw/llm_memory
python scripts/extract_with_wrappers.py --project openclaw --limit 50
python scripts/store_extraction.py --project openclaw --extraction-file tmp/extraction.json
```

**Why this works:**
- `extract_with_wrappers.py` uses your configured LLM wrapper
- Processes up to 50 conversations per run
- Creates extraction JSON automatically
- `store_extraction.py` saves to graph database
```

---

## 🔄 Integrate with Your Agent Workflow

### When Your Agent Ends a Conversation:

Instead of manually creating extraction JSON, just dump to SQL:

**Quick dump (recommended):**
```bash
cd ~/.openclaw/llm_memory
python scripts/import_conversation.py --project openclaw --file tmp/conversation_2026-03-08_14-30-45.json
```

This:
- ✅ Stores conversation in SQL
- ✅ Creates OpenTimestamps proof
- ✅ Takes ~1 second
- ✅ Agent can exit immediately

**The heartbeat will handle extraction automatically!**

---

## 🧪 Testing the Integration

### 1. Test Manual Extraction

```bash
cd ~/.openclaw/llm_memory

# Extract one conversation
python scripts/extract_with_wrappers.py --project openclaw --limit 1

# Store it
python scripts/store_extraction.py --project openclaw --extraction-file tmp/extraction.json
```

### 2. Verify It Worked

```bash
# Query the graph
python scripts/query_memory.py --project openclaw --query "What entities do we have?"

# Export graph visualization
python scripts/export_graph.py --project openclaw --output tmp/graph.json
```

Open `visualize_graph.html` in your browser and load `tmp/graph.json`.

### 3. Test Heartbeat

Wait 30 minutes (or trigger manually) and check:

```bash
# Check for pending extractions
python scripts/extract_pending.py --project openclaw
```

If the heartbeat is working, this should show 0 pending (all extracted).

---

## 📊 Monitoring

### Check Extraction Status

```bash
# How many conversations are pending extraction?
python scripts/extract_pending.py --project openclaw
```

### View Recent Entities

```bash
# Query recent entities
python scripts/query_memory.py --project openclaw --query "Show me recent entities"
```

### Export Graph

```bash
# Export last 7 days
python scripts/export_graph.py --project openclaw --output tmp/graph.json --last-days 7
```

---

## 🔧 Troubleshooting

### Heartbeat Not Running

**Check OpenClaw logs:**
```bash
openclaw logs
```

Look for `llm_memory_extract` task execution.

### Extraction Failing

**Test wrapper manually:**
```bash
cd ~/.openclaw/llm_memory
python scripts/extraction_wrapper_openai.py tmp/test_input.json tmp/test_output.json entities prompts/extract-entities.md
```

**Check environment variables:**
```bash
echo $OPENAI_API_KEY
echo $OPENAI_MODEL
```

### No Entities in Graph

**Check if extraction ran:**
```bash
ls -la tmp/extraction*.json
```

**Check if storage ran:**
```bash
python scripts/query_memory.py --project openclaw --all
```

---

## 🎯 Advanced Configuration

### Custom Extraction Frequency

Change heartbeat interval in `openclaw.json`:

```json
{
  "heartbeat": {
    "interval": 3600  // Every hour instead of 30 min
  }
}
```

### Batch Size

Change `--limit` in heartbeat command:

```json
{
  "custom_commands": {
    "llm_memory_extract": {
      "command": "... --limit 100 ..."  // Process 100 at a time
    }
  }
}
```

### Multiple Projects

Create separate heartbeat tasks:

```json
{
  "heartbeat": {
    "tasks": ["llm_memory_work", "llm_memory_personal"]
  },
  "custom_commands": {
    "llm_memory_work": {
      "command": "cd ~/.openclaw/llm_memory && python scripts/extract_with_wrappers.py --project work --limit 50 && ..."
    },
    "llm_memory_personal": {
      "command": "cd ~/.openclaw/llm_memory && python scripts/extract_with_wrappers.py --project personal --limit 50 && ..."
    }
  }
}
```

---

## 📚 Next Steps

- Read `docs/extraction-rules.md` for entity extraction guidelines
- Check `COMMANDS.md` for all available workflows
- Explore `visualize_graph.html` for graph visualization
- See `quality-check.md` for contradiction detection

---

**Integration complete! Your OpenClaw agent now has persistent memory.** 🧠

