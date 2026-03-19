# AI Search Helper

**Workflow helper for AI agents to search with helper-file inputs.**

---

## The Problem

When AI agents use the `launch-process` tool, inline query arguments can be split on spaces:

```bash
# Fragile inline pattern:
--search <multi-word query>

# What can get executed instead:
--search <word1> <word2> <word3>  (split into multiple args)

# Result:
Error: unrecognized arguments: of Custody
```

---

## The Solution

**Use the search helper script with a helper file.**

### Step 1: Write search term to file

```python
# In AI code, write the helper file with a UTF-8-safe file tool:
write_text_file("tmp/search_term.txt", "Chain of Custody")
```

### Step 2: Run search helper

```bash
python scripts/search_helper.py --project llm_memory
```

**Result:** [OK] Works perfectly!

---

## Usage

### Basic Search

**1. Write search term:**
```python
write_text_file("tmp/search_term.txt", "Execute Merge Functionality")
```

**2. Search:**
```bash
python scripts/search_helper.py --project llm_memory
```

**Output:**
```
[SEARCH] Found 1 entities:

[PACKAGE] Execute Merge Functionality
   UUID: entity-28ef30cd64af
   Summary: Implementation that reads quality-answers.json...
```

---

### Search by Entity Name

**1. Write entity name:**
```python
write_text_file("tmp/search_term.txt", "Chain of Custody")
```

**2. Search with --entity flag:**
```bash
python scripts/search_helper.py --project llm_memory --entity
```

---

### Get Related Entities

**1. Write entity name:**
```python
write_text_file("tmp/search_term.txt", "Chain of Custody")
```

**2. Search with --entity --related:**
```bash
python scripts/search_helper.py --project llm_memory --entity --related
```

**Output:**
```
[PACKAGE] Chain of Custody
   UUID: entity-70126686ddd8
   Summary: Maintaining verifiable record of data provenance...

   Facts (1):
      [outgoing] Chain of Custody is implemented by Attestation mechanism
```

---

## Options

```
--project PROJECT       Project name (required)
--search-file FILE      File containing search term (default: tmp/search_term.txt)
--entity                Search by entity name instead of text search
--related               Get related entities (requires --entity)
--json                  Output as JSON
--verbose, -v           Verbose output
```

---

## Examples

### Example 1: Search for multi-word concept

```python
# Step 1: Write search term
write_text_file("tmp/search_term.txt", "AI Review Workflow")

# Step 2: Search
launch_process("python scripts/search_helper.py --project llm_memory")
```

### Example 2: Get facts about entity

```python
# Step 1: Write entity name
write_text_file("tmp/search_term.txt", "Attestation")

# Step 2: Get related
launch_process("python scripts/search_helper.py --project llm_memory --entity --related")
```

### Example 3: JSON output

```python
# Step 1: Write search term
write_text_file("tmp/search_term.txt", "Merkle Tree")

# Step 2: Search with JSON output
launch_process("python scripts/search_helper.py --project llm_memory --json")
```

---

## How It Works

**The helper script:**
1. Reads search term from `tmp/search_term.txt`
2. Passes the file path through `--search-file` or `--entity-file`
3. No quote stripping, no argument splitting
4. Stays aligned with the repo-wide file-input workflow standard

**Code:**
```python
# Build command with helper-file input
cmd = [
    sys.executable,
    'scripts/query_memory.py',
    '--project', args.project,
    '--search-file', 'tmp/search_term.txt'
]

# Run command
subprocess.run(cmd)
```

---

## Why This Works

**Problem:** Shell/tool splits on spaces
**Solution:** The workflow passes a file path, not an inline query string

**Comparison:**

**Old inline-argument pattern (deprecated for workflow use):**
```bash
python query_memory.py --search <multi-word query>
# Fragile across shells and wrappers
```

**Helper-file workflow (standard):**
```python
subprocess.run(['python', 'query_memory.py', '--search-file', 'tmp/search_term.txt'])
```

---

## Credit

**User suggestion:** "What about dumping the words and piping the output? You can write the words with spaces into a file and feed them to a command right?"

**Absolutely correct!** This workaround enables 100% accurate multi-word searches for AI agents.

---

## See Also

- [docs/COMMANDS.md](COMMANDS.md) - Command reference
- [remember.md](../remember.md) - Query memory
- [search.md](../search.md) - Advanced search

