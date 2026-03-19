# Windows Setup Guide

This guide will help you get the LLM Memory System running on Windows.

---

## [AI AGENTS] Quick Reference - Portable Python URLs

**If you're an AI agent and need to download portable Python, use these EXACT URLs:**

**DO NOT hallucinate or modify these URLs - they are permanent links from python.org**

```
Python 3.13.1 (RECOMMENDED):
https://www.python.org/ftp/python/3.13.1/python-3.13.1-embed-amd64.zip

Python 3.12.8:
https://www.python.org/ftp/python/3.12.8/python-3.12.8-embed-amd64.zip

Python 3.11.11:
https://www.python.org/ftp/python/3.11.11/python-3.11.11-embed-amd64.zip

Python 3.10.16:
https://www.python.org/ftp/python/3.10.16/python-3.10.16-embed-amd64.zip

Python 3.9.21:
https://www.python.org/ftp/python/3.9.21/python-3.9.21-embed-amd64.zip

get-pip.py (PERMANENT):
https://bootstrap.pypa.io/get-pip.py
```

**DO NOT use Python 3.14+ - not supported by kuzu library!**

**After downloading, extract to `python313/` and use `.\python313\python.exe` for all commands.**

---

## Prerequisites

### 1. Python 3.9-3.13 (IMPORTANT!)

**[WARNING] Python 3.14 is NOT supported yet!** The `kuzu` graph database library only supports Python 3.8-3.13.

**Step 1: Check if Python is installed:**
```powershell
python --version
```

**Possible outcomes:**

**A) Python 3.9-3.13 installed** -> Great! Skip to step 2.

**B) Python 3.14 installed** -> Need to install Python 3.13 or use portable Python (see below).

**C) No Python installed** -> Use portable Python (see below).

**D) "python: command not found"** -> Use portable Python (see below).

---

### Option 1: Install Python (Recommended for permanent use)

Download Python 3.13 from [python.org](https://www.python.org/downloads/)

**Make sure to check "Add Python to PATH" during installation!**

---

### Option 2: Portable Python (No installation required)

**Perfect for:**
- Systems where you can't install software
- Testing without affecting system Python
- AI agents that need Python on-demand

**IMPORTANT: Use these EXACT URLs - they are permanent links from python.org**

**Supported Python Versions (choose ONE):**

**Python 3.13.1 (RECOMMENDED):**
```
https://www.python.org/ftp/python/3.13.1/python-3.13.1-embed-amd64.zip
```

**Python 3.12.8:**
```
https://www.python.org/ftp/python/3.12.8/python-3.12.8-embed-amd64.zip
```

**Python 3.11.11:**
```
https://www.python.org/ftp/python/3.11.11/python-3.11.11-embed-amd64.zip
```

**Python 3.10.16:**
```
https://www.python.org/ftp/python/3.10.16/python-3.10.16-embed-amd64.zip
```

**Python 3.9.21:**
```
https://www.python.org/ftp/python/3.9.21/python-3.9.21-embed-amd64.zip
```

**DO NOT use Python 3.14+ - kuzu library does not support it yet!**

---

**Steps (using Python 3.13.1 as example):**

1. **Download portable Python:**
   ```powershell
   # Download embedded Python 3.13.1
   Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.13.1/python-3.13.1-embed-amd64.zip" -OutFile "python-3.13.1-embed-amd64.zip"
   ```

2. **Extract to python313/ directory:**
   ```powershell
   Expand-Archive -Path "python-3.13.1-embed-amd64.zip" -DestinationPath "python313"
   ```

3. **Download and install pip:**
   ```powershell
   # Download get-pip.py (PERMANENT LINK - always works)
   Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile "get-pip.py"

   # Install pip
   .\python313\python.exe get-pip.py
   ```

   **Note:** The URL `https://bootstrap.pypa.io/get-pip.py` is a permanent link maintained by PyPA (Python Packaging Authority). It always points to the latest pip installer.

4. **Enable pip in embedded Python:**
   ```powershell
   # Edit python313\python313._pth file
   # Uncomment the line: import site
   (Get-Content python313\python313._pth) -replace '#import site', 'import site' | Set-Content python313\python313._pth
   ```

5. **Use portable Python for all commands:**
   ```powershell
   # Instead of: python scripts/...
   # Use: .\python313\python.exe scripts/...

   .\python313\python.exe --version
   # Should show: Python 3.13.1
   ```

**From now on, replace all `python` commands with `.\python313\python.exe`**

---

### 2. Install Dependencies

**If using system Python:**
```powershell
pip install -r requirements.txt
```

**If using portable Python:**
```powershell
.\python313\python.exe -m pip install -r requirements.txt
```

**Expected output:**
```
Successfully installed kuzu-0.11.3 ...
```

**Requirements:**
- Python 3.9-3.13
- kuzu 0.11.3+
- SQLite (built-in with Python)

---

## Quick Start

### 1. Create Memory Directory

```powershell
New-Item -ItemType Directory -Force -Path memory
```

### 2. Store Your First Interaction

```powershell
python scripts/store_interaction.py `
    --project "my-project" `
    --user "Let's build a web app" `
    --assistant "Great! I'll help you build a web app."
```

**Output:**
```
[OK] Interaction stored successfully!

[LIST] Details:
   UUID:         uuid-abc123
   Project:      my-project
   Chain Index:  1
   Content Hash: sha256-def456...
```

### 3. Query Memory

```powershell
python scripts/prepare_sync_files.py --project "my-project" --json
# Edit tmp/search.txt, then:
python scripts/query_memory.py `
    --project "my-project" `
    --search-file tmp/search.txt
```

---

## Using the Auggie Wrapper (PowerShell)

The wrapper script automates the memory sync workflow.

### Run the Wrapper

```powershell
.\auggie-wrapper.ps1
```

Or with a specific project:

```powershell
.\auggie-wrapper.ps1 -Project "my-project"
```

### What It Does

1. **PRE-SYNC**: Checks for unprocessed interactions from last session
2. **INTERACTIVE**: Pauses for your Auggie conversation
3. **POST-SYNC**: Syncs knowledge from this session

---

## Troubleshooting Portable Python

### Download fails with 404 error

**Problem:** URL not found or version doesn't exist

**Solution:** Use ONLY the URLs listed above. They are verified permanent links.

**DO NOT:**
- Guess version numbers (e.g., 3.13.2, 3.12.9)
- Change the URL format
- Use shortened URLs or mirrors

**If you need a different version:**
1. Go to https://www.python.org/downloads/
2. Find the version you need
3. Look for "Windows embeddable package (64-bit)"
4. Copy the EXACT download URL

### "Invoke-WebRequest: The request was aborted"

**Problem:** Network timeout or firewall blocking

**Solution:**
```powershell
# Try with longer timeout
Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.13.1/python-3.13.1-embed-amd64.zip" -OutFile "python.zip" -TimeoutSec 300
```

Or download manually:
1. Open browser
2. Paste URL: `https://www.python.org/ftp/python/3.13.1/python-3.13.1-embed-amd64.zip`
3. Save file
4. Extract manually

### "python313\python.exe: command not found"

**Problem:** Wrong directory or extraction failed

**Solution:**
```powershell
# Check if python.exe exists
Test-Path python313\python.exe

# If False, re-extract
Expand-Archive -Path "python-3.13.1-embed-amd64.zip" -DestinationPath "python313" -Force
```

---

## Running Tests

### Test the Wrapper Scripts

```powershell
.\tests\test_wrappers.ps1
```

This will:
- [OK] Store test interactions
- [OK] Export conversation history
- [OK] Verify SQL hash chain
- [OK] Create entities and relationships
- [OK] Query the knowledge graph
- [OK] Verify cryptographic proofs

---

## Common Commands

### Store Interaction

```powershell
python scripts/store_interaction.py `
    --project "my-project" `
    --user "Your message" `
    --assistant "Assistant response"
```

### Check Sync Status

```powershell
python scripts/sync.py --project "my-project" --status
```

### Show Unprocessed Interactions

```powershell
python scripts/sync.py --project "my-project" --show
```

### Store Extraction Results

```powershell
python scripts/sync.py --project "my-project" --store extraction.json
```

### Query Memory

```powershell
# Search for entities
python scripts/prepare_sync_files.py --project "my-project" --json
# Edit tmp/search.txt / tmp/entity.txt, then:
python scripts/query_memory.py `
    --project "my-project" `
    --search-file tmp/search.txt

# Get facts about an entity
python scripts/query_memory.py `
    --project "my-project" `
    --entity-file tmp/entity.txt

# Search by label
python scripts/query_memory.py `
    --project "my-project" `
    --label "technology"
```

### Store Extraction

```powershell
# Store extraction results (will pause for quality checks)
python scripts/store_extraction.py `
    --project "my-project" `
    --extraction-file extraction.json

# If you need to run non-interactively (after creating quality-answers.json):
"" | python scripts/store_extraction.py `
    --project "my-project" `
    --extraction-file extraction.json
```

**IMPORTANT:** The script pauses for quality checks. See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for details.

**PowerShell Note:** Use `""` not `echo ""` - PowerShell's echo requires InputObject parameter.

### Verify Integrity

```powershell
# Verify SQL hash chain
python scripts/verify_integrity.py `
    --project "my-project" `
    --sql

# Verify graph extraction proofs
python scripts/verify_integrity.py `
    --project "my-project" `
    --graph

# Verify everything
python scripts/verify_integrity.py `
    --project "my-project" `
    --all
```

---

## File Locations

### Memory Storage
```
.\memory\
 knowledge.kuzu\     # Graph DB (PUBLIC SHAREABLE)
 conversations.db    # SQLite (SELECTIVE SHARING)
```

### Scripts
```
.\scripts\
 store_interaction.py   # Store conversations
 sync.py                # Sync workflow
 query_memory.py        # Query knowledge graph
 verify_integrity.py    # Verify proofs
```

### Wrappers
```
.\auggie-wrapper.ps1       # PowerShell wrapper (Windows)
.\auggie-wrapper.sh        # Bash wrapper (Linux/Mac)
```

---

## Troubleshooting

### PowerShell Execution Policy

If you get an error running `.ps1` scripts:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Python Command Not Found

Make sure Python is in your PATH, or use:

```powershell
py scripts/store_interaction.py ...
```

---

## Next Steps

- See [docs/README.md](docs/README.md) for full documentation
- See [docs/QUICK-START.md](docs/QUICK-START.md) for more examples
- See [docs/COMMANDS.md](docs/COMMANDS.md) for command reference

