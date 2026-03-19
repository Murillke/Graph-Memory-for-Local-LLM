# LLM Wrappers

The memory system supports pluggable LLM wrappers for both **extraction** and **quality checking**. This allows you to use any LLM (local or API-based) for all LLM-powered operations.

---

## Why Wrappers?

**The Problem:** Auggie (the AI agent you're using now) cannot be directly integrated into the memory system because:
- [X] Auggie is an AI agent, not a library (no code to import)
- [X] No hooks or heartbeat mechanism (like OpenClaw) for transparent memory injection
- [X] Cannot edit Auggie's internal code to add memory logic
- [X] Auggie runs as a separate process via CLI

**The Solution:** Wrapper scripts that follow a standard interface, allowing:
- [OK] Any LLM to be used (Auggie, OpenAI, Claude, Ollama, etc.)
- [OK] Users can choose based on cost, speed, privacy needs
- [OK] Easy to add new LLMs (just write a wrapper script)
- [OK] Fallback to manual review if no LLM available

If no extraction wrapper is configured, that means the agent should do the
extraction itself instead of calling `extract_with_wrappers.py`.

If no quality wrapper is configured, that means the agent should either:
- review `tmp/quality-questions.json` itself and create `tmp/quality-answers.json`
- or explicitly use `--skip-quality-check`

---

## Wrapper Types

The system has two types of LLM wrappers:

### 1. **Extraction Wrappers**
Extract entities and facts from conversation text.

**Interface:**
```bash
extraction_wrapper.py <input_file> <output_file> <extraction_type> <prompt_file>
```

**Extraction types:**
- `entities` - Extract entity nodes (Person, Technology, Organization, Concept, Document)
- `facts` - Extract relationships between entities

### 2. **Quality Checking Wrappers**
Review extracted entities/facts for duplicates and contradictions.

**Interface:**
```bash
quality_wrapper.py <questions_file> <answers_file> <prompt_file>
```

---

## Standard Wrapper Interfaces

### Extraction Wrapper Interface

```bash
extraction_wrapper.py <input_file> <output_file> <extraction_type> <prompt_file>
```

**Arguments:**
1. `input_file` - Path to JSON file with conversation data
2. `output_file` - Path where extraction results should be written (JSON)
3. `extraction_type` - Type of extraction: "entities" or "facts"
4. `prompt_file` - Path to markdown file with extraction instructions

**Exit codes:**
- `0` - Success
- `1` - Invalid arguments or configuration error
- `2` - LLM API call failed
- `3` - Invalid response from LLM

### Quality Checking Wrapper Interface

All quality checking wrappers must follow this interface:

```bash
wrapper_script <questions_file> <answers_file> <prompt_file>
```

**Arguments:**
1. `questions_file` - Path to JSON file with quality questions
2. `answers_file` - Path where answers should be written (JSON)
3. `prompt_file` - Path to markdown file with criteria/instructions

**Exit codes:**
- `0` - Success
- `1` - Invalid arguments or configuration error
- `2` - LLM API call failed
- `3` - Invalid response from LLM

---

## Available Wrappers

**Path note:** In subsystem repo mode, examples below use files under `tmp/` such as `tmp/quality-questions.json` and `tmp/quality-answers.json`. In a host workspace where the subsystem lives under `./mem`, the equivalents are typically `mem/tmp/...`.

### 1. Auggie (Default)

**File:** `scripts/llm_wrapper_auggie.py`

**Description:** Uses Auggie CLI for quality checking (Auggie is an AI agent powered by Claude Sonnet 4.5)

**Requirements:**
- Auggie CLI installed and available in PATH
- Augment subscription (Auggie uses Claude Sonnet 4.5 via Anthropic)

**Configuration:**
```json
{
  "quality_check": {
    "llm_wrapper": "./scripts/llm_wrapper_auggie.py"
  }
}
```

**Usage:**
```bash
python scripts/llm_wrapper_auggie.py \\
  tmp/quality-questions.json \\
  tmp/quality-answers.json \\
  prompts/quality-check-contradictions.md
```

**Pros:**
- [OK] Integrated with your existing Augment workflow
- [OK] Same model/agent you're already using
- [OK] No separate API key needed
- [OK] Can leverage Augment's codebase context

**Cons:**
- [*] Costs money (Augment subscription includes Anthropic API costs)
- [!] Requires Auggie CLI
- [!] Cannot edit Auggie's code (it's an AI agent, not a library)
- [!] No hooks/heartbeat for transparent memory injection

---

### 2. OpenAI API

**File:** `scripts/llm_wrapper_openai.py`

**Description:** Uses OpenAI's GPT models via API

**Requirements:**
- `pip install openai`
- OpenAI API key

**Configuration:**
```json
{
  "quality_check": {
    "llm_wrapper": "./scripts/llm_wrapper_openai.py"
  }
}
```

**Environment Variables:**
```bash
export OPENAI_API_KEY="sk-..."
export OPENAI_MODEL="gpt-4o"  # Optional, default: gpt-4o
```

**Usage:**
```bash
export OPENAI_API_KEY="sk-..."
python scripts/llm_wrapper_openai.py \\
  tmp/quality-questions.json \\
  tmp/quality-answers.json \\
  prompts/quality-check-contradictions.md
```

**Pros:**
- [OK] High quality responses
- [OK] Fast API
- [OK] JSON mode support

**Cons:**
- [*] Costs money (~$0.01-0.05 per quality check)
- [*] Requires internet connection

---

### 3. Codex CLI

**File:** `scripts/llm_wrapper_codex.py`

**Description:** Uses `codex exec` non-interactively for quality checking. This is the native wrapper for Codex-style agents working in this repo.

**Requirements:**
- Codex CLI installed and available in PATH
- Authenticated Codex environment

**Configuration:**
```json
{
  "quality_check": {
    "llm_wrapper": "./scripts/llm_wrapper_codex.py"
  }
}
```

**Environment Variables:**
```bash
export CODEX_MODEL="gpt-5-codex"   # Optional
export CODEX_PROFILE="default"     # Optional
export CODEX_BIN="codex"           # Optional
```

**Usage:**
```bash
python scripts/llm_wrapper_codex.py \
  tmp/quality-questions.json \
  tmp/quality-answers.json \
  prompts/quality-check-contradictions.md
```

**Pros:**
- Works with the Codex CLI already used in this workspace
- No separate wrapper protocol to invent
- Normalizes output to the schema consumed by `store_extraction.py`

**Cons:**
- Requires Codex CLI auth/setup
- Depends on the local Codex runtime

---

### 4. Claude API (Anthropic)

**File:** `scripts/llm_wrapper_claude.py`

**Description:** Uses Anthropic's Claude models via API

**Requirements:**
- `pip install anthropic`
- Anthropic API key

**Configuration:**
```json
{
  "quality_check": {
    "llm_wrapper": "./scripts/llm_wrapper_claude.py"
  }
}
```

**Environment Variables:**
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export CLAUDE_MODEL="claude-sonnet-4-20250514"  # Optional
```

**Usage:**
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
python scripts/llm_wrapper_claude.py \\
  tmp/quality-questions.json \\
  tmp/quality-answers.json \\
  prompts/quality-check-contradictions.md
```

**Pros:**
- [OK] Excellent reasoning capabilities
- [OK] Large context window
- [OK] Good at following instructions

**Cons:**
- [*] Costs money (~$0.02-0.10 per quality check)
- [*] Requires internet connection

---

### 5. Ollama (Local LLM)

**File:** `scripts/llm_wrapper_ollama.py`

**Description:** Uses locally-running Ollama models

**Requirements:**
- Ollama installed: https://ollama.ai/download
- `pip install requests`
- Model pulled: `ollama pull llama3.1`

**Configuration:**
```json
{
  "quality_check": {
    "llm_wrapper": "./scripts/llm_wrapper_ollama.py"
  }
}
```

**Environment Variables:**
```bash
export OLLAMA_MODEL="llama3.1"  # Optional, default: llama3.1
export OLLAMA_HOST="http://localhost:11434"  # Optional
```

**Usage:**
```bash
# Start Ollama (if not auto-started)
ollama serve

# Pull a model
ollama pull llama3.1

# Run wrapper
python scripts/llm_wrapper_ollama.py \\
  tmp/quality-questions.json \\
  tmp/quality-answers.json \\
  prompts/quality-check-contradictions.md
```

**Pros:**
- [OK] Free (no API costs)
- [OK] Works offline
- [OK] Privacy (data stays local)
- [OK] Multiple models available

**Cons:**
- [!] Requires local installation
- [!] Slower than API-based models
- [!] Quality depends on model size

---

### 6. Manual Review

**File:** `scripts/llm_wrapper_manual.py`

**Description:** Prompts user to manually review questions (fallback when no LLM available)

**Requirements:**
- None

**Configuration:**
```json
{
  "quality_check": {
    "llm_wrapper": "./scripts/llm_wrapper_manual.py"
  }
}
```

**Usage:**
```bash
python scripts/llm_wrapper_manual.py \\
  tmp/quality-questions.json \\
  tmp/quality-answers.json \\
  prompts/quality-check-contradictions.md

# Review tmp/quality-questions.json and create tmp/quality-answers.json
```

**Pros:**
- [OK] Always works
- [OK] No dependencies
- [OK] Human judgment

**Cons:**
- [*] Time-consuming
- [*] Requires manual work

---

## Writing Your Own Wrapper

You can write a custom wrapper for any LLM! Just follow the standard interface.

### Template:

```python
#!/usr/bin/env python3
"""Custom LLM Wrapper"""

import sys
import json
import os

def main():
    # 1. Validate arguments
    if len(sys.argv) != 4:
        print("Usage: wrapper.py <questions> <answers> <prompt>")
        sys.exit(1)
    
    questions_file = sys.argv[1]
    answers_file = sys.argv[2]
    prompt_file = sys.argv[3]
    
    # 2. Read inputs
    with open(prompt_file, 'r') as f:
        prompt = f.read()
    
    with open(questions_file, 'r') as f:
        questions = json.load(f)
    
    # 3. Call your LLM
    # ... your custom LLM logic here ...
    answers = call_my_llm(prompt, questions)
    
    # 4. Write outputs
    with open(answers_file, 'w') as f:
        json.dump(answers, f, indent=2)
    
    sys.exit(0)

if __name__ == "__main__":
    main()
```

### Examples:

**For a REST API:**
```python
import requests
response = requests.post(
    "https://api.example.com/v1/chat",
    json={"prompt": prompt, "input": questions}
)
answers = response.json()
```

**For a Python library:**
```python
from my_llm import LLM
llm = LLM(model="my-model")
answers = llm.generate(prompt, questions)
```

**For a CLI tool:**
```python
import subprocess
result = subprocess.run(
    ["my-llm-cli", "--prompt", prompt_file, "--input", questions_file],
    capture_output=True
)
answers = json.loads(result.stdout)
```

---

## Comparison Table

| Wrapper | Cost | Speed | Quality | Offline | Setup |
|---------|------|-------|---------|---------|-------|
| **Auggie** | Subscription* | Fast | Excellent | No | Easy |
| **OpenAI** | ~$0.03/check | Very Fast | Excellent | No | Easy |
| **Codex** | Existing Codex usage | Fast | Excellent | No | Easy |
| **Claude** | ~$0.06/check | Fast | Excellent | No | Easy |
| **Ollama** | Free | Slow | Good | Yes | Medium |
| **Manual** | Free (your time) | Very Slow | Excellent | Yes | None |

*Auggie requires Augment subscription which includes Anthropic API costs

---

## Extraction Wrappers

Extraction wrappers work the same way as quality checking wrappers, but for entity/fact extraction.

**Available extraction wrappers:**
- `extraction_wrapper_auggie.py` - Auggie CLI
- `extraction_wrapper_codex.py` - Codex CLI
- `extraction_wrapper_openai.py` - OpenAI API
- `extraction_wrapper_claude.py` - Claude API
- `extraction_wrapper_ollama.py` - Ollama

**Configuration:**
```json
{
  "extraction": {
    "llm_wrapper_entities": "./scripts/extraction_wrapper_auggie.py",
    "llm_wrapper_facts": "./scripts/extraction_wrapper_auggie.py",
    "prompts": {
      "entities": "./prompts/extract-entities.md",
      "facts": "./prompts/extract-facts.md"
    }
  }
}
```

**Manual mode:**
```json
{
  "extraction": {
    "llm_wrapper_entities": null,
    "llm_wrapper_facts": null
  }
}
```

When both wrapper values are `null`, do the extraction yourself, write
`tmp/extraction.json`, validate it, and store it manually.

**See extraction prompt files for detailed schemas and examples:**
- `prompts/extract-entities.md` - Entity extraction schema
- `prompts/extract-facts.md` - Fact extraction schema

---

## See Also

- `prompts/extract-entities.md` - Entity extraction schema and examples
- `prompts/extract-facts.md` - Fact extraction schema and examples
- `prompts/quality-check-duplicates.md` - Duplication detection criteria
- `prompts/quality-check-contradictions.md` - Contradiction detection criteria
- `mem.config.json` - Configuration file
- `scripts/extraction_wrapper_*.py` - Extraction wrapper implementations
