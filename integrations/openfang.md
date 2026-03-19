# Integrating llm_memory with OpenFang

## 🦷 Overview

OpenFang's **"Hands"** system is perfect for autonomous llm_memory management!

**The Pattern:**
- **Main agents** handle conversations → dump to SQL (fast, ~10 seconds)
- **Memory Manager Hand** extracts to graph (autonomous, every 30 min)
- **User** never thinks about it!

---

## 🎯 Benefits

✅ **Fully autonomous** - Hand works 24/7 without prompts  
✅ **Fast agent response** - dump takes <1 second  
✅ **Automatic extraction** - Hand runs every 30 min  
✅ **No manual work** - activate once, forget forever  
✅ **Cryptographic integrity** - OpenTimestamps on every dump  
✅ **Knowledge graph** - always up-to-date (within 30 min)  
✅ **Works with your LLM** - OpenAI, Claude, Anthropic, OpenRouter, etc.

---

## 📦 Installation

### 1. Install llm_memory

```bash
cd ~/.openfang
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

Add to your shell profile (`~/.bashrc`, `~/.zshrc`, etc.):

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

## 🤖 Create Memory Manager Hand

### 1. Create Hand Directory

```bash
mkdir -p ~/.openfang/hands/memory_manager
```

### 2. Create HAND.toml

Create `~/.openfang/hands/memory_manager/HAND.toml`:

```toml
[hand]
name = "memory_manager"
description = "Autonomous llm_memory knowledge graph manager"
version = "1.0.0"
author = "Your Name"

[schedule]
type = "continuous"
check_interval = 1800  # 30 minutes in seconds

[tools]
required = ["shell"]

[settings]
project_name = "openfang"
max_extractions_per_run = 50
llm_memory_path = "~/.openfang/llm_memory"

[guardrails]
require_approval = false
max_retries = 3
```

### 3. Create SKILL.md

Create `~/.openfang/hands/memory_manager/SKILL.md`:

```markdown
# Memory Manager Hand - Skill Definition

You are the **Memory Manager Hand** for llm_memory integration.

## Your Purpose

You autonomously manage the knowledge graph extraction for all OpenFang conversations.

## Your Schedule

Every 30 minutes, you wake up and:

1. **Check for pending extractions**
2. **Extract up to 50 conversations** using the configured LLM
3. **Store entities and facts** in the graph database
4. **Go back to sleep**

## Your Commands

### Check for Pending Extractions

```bash
cd ~/.openfang/llm_memory
python scripts/extract_pending.py --project openfang
```

This shows how many conversations are waiting to be extracted.

### Extract Conversations

```bash
cd ~/.openfang/llm_memory
python scripts/extract_with_wrappers.py --project openfang --limit 50
```

This:
- Finds up to 50 pending conversations
- Uses the configured LLM wrapper (OpenAI, Claude, Ollama, etc.)
- Extracts entities and facts
- Creates `tmp/extraction.json`

### Store to Graph

```bash
cd ~/.openfang/llm_memory
python scripts/store_extraction.py --project openfang --extraction-file tmp/extraction.json
```

This:
- Validates the extraction
- Stores entities in graph database
- Creates relationships between entities
- Links to original conversations

## Your Decision Logic

**If pending count > 0:**
- Extract immediately (up to 50)
- Store to graph
- Report success

**If pending count = 0:**
- Nothing to do
- Go back to sleep

**If extraction fails:**
- Log error
- Retry up to 3 times
- If still failing, alert user

## Your Success Metrics

Track and report:
- Total conversations extracted
- Total entities created
- Total facts stored
- Extraction success rate
- Average extraction time

## Your Constraints

- **Never** extract more than 50 conversations per run (to avoid long-running tasks)
- **Never** modify existing entities (only create new ones)
- **Always** validate extraction before storing
- **Always** clean up temp files after processing
```

### 4. Activate the Hand

```bash
openfang hand activate memory_manager
```

The Hand will now work autonomously!

---

## 🔄 Integrate with Your Agent Workflow

### When Your Agents End a Conversation:

Instead of manually creating extraction JSON, just dump to SQL:

**Quick dump (recommended):**
```bash
cd ~/.openfang/llm_memory
python scripts/import_conversation.py --project openfang --file tmp/conversation_2026-03-08_14-30-45.json
```

This:
- ✅ Stores conversation in SQL
- ✅ Creates OpenTimestamps proof
- ✅ Takes ~1 second
- ✅ Agent can exit immediately

**The Memory Manager Hand will handle extraction automatically!**

---

## 🧪 Testing the Integration

### 1. Test Manual Extraction

```bash
cd ~/.openfang/llm_memory

# Extract one conversation
python scripts/extract_with_wrappers.py --project openfang --limit 1

# Store it
python scripts/store_extraction.py --project openfang --extraction-file tmp/extraction.json
```

### 2. Verify It Worked

```bash
# Query the graph
python scripts/query_memory.py --project openfang --query "What entities do we have?"

# Export graph visualization
python scripts/export_graph.py --project openfang --output tmp/graph.json
```

Open `visualize_graph.html` in your browser and load `tmp/graph.json`.

### 3. Test the Hand

```bash
# Check Hand status
openfang hand status memory_manager

# View Hand logs
openfang hand logs memory_manager

# Manually trigger (for testing)
openfang hand run memory_manager
```

---

## 📊 Monitoring

### Check Hand Status

```bash
# Is the Hand running?
openfang hand status memory_manager

# View recent activity
openfang hand logs memory_manager --tail 50
```

### Check Extraction Status

```bash
# How many conversations are pending extraction?
cd ~/.openfang/llm_memory
python scripts/extract_pending.py --project openfang
```

### View Recent Entities

```bash
# Query recent entities
python scripts/query_memory.py --project openfang --query "Show me recent entities"
```

### Export Graph

```bash
# Export last 7 days
python scripts/export_graph.py --project openfang --output tmp/graph.json --last-days 7
```

---

## 🔧 Troubleshooting

### Hand Not Running

**Check Hand status:**
```bash
openfang hand status memory_manager
```

**Check Hand logs:**
```bash
openfang hand logs memory_manager
```

**Restart Hand:**
```bash
openfang hand restart memory_manager
```

### Extraction Failing

**Test wrapper manually:**
```bash
cd ~/.openfang/llm_memory
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
ls -la ~/.openfang/llm_memory/tmp/extraction*.json
```

**Check if storage ran:**
```bash
cd ~/.openfang/llm_memory
python scripts/query_memory.py --project openfang --all
```

---

## 🎯 Advanced Configuration

### Custom Extraction Frequency

Edit `HAND.toml`:

```toml
[schedule]
check_interval = 3600  # Every hour instead of 30 min
```

Then restart the Hand:
```bash
openfang hand restart memory_manager
```

### Batch Size

Edit `HAND.toml`:

```toml
[settings]
max_extractions_per_run = 100  # Process 100 at a time
```

### Multiple Projects

Create separate Hands for different projects:

```bash
# Work Hand
mkdir -p ~/.openfang/hands/memory_manager_work
# Copy HAND.toml and SKILL.md, change project_name to "work"

# Personal Hand
mkdir -p ~/.openfang/hands/memory_manager_personal
# Copy HAND.toml and SKILL.md, change project_name to "personal"

# Activate both
openfang hand activate memory_manager_work
openfang hand activate memory_manager_personal
```

---

## 📚 Next Steps

- Read `docs/extraction-rules.md` for entity extraction guidelines
- Check `COMMANDS.md` for all available workflows
- Explore `visualize_graph.html` for graph visualization
- See `quality-check.md` for contradiction detection

---

**Integration complete! Your OpenFang agents now have persistent memory.** 🧠

