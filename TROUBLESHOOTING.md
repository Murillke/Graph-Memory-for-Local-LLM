# Troubleshooting Guide

Common issues and solutions for the LLM Memory System.

---

## EOFError When Running store_extraction.py

### Symptom
```
[PAUSE]  Please create the answers file manually for now.
Press Enter when quality-answers.json is ready...
EOFError: EOF when reading a line
```

### Cause
The script pauses and waits for user input (Enter key), but when run non-interactively (by AI agents or in automated scripts), there's no input available.

### Solution for AI Agents

**Option 1: Use keep_stdin_open and write-process**

```python
# Launch with stdin open
terminal_id = launch_process(
    command="python scripts/store_extraction.py --project X --extraction-file Y",
    wait=false,
    keep_stdin_open=true
)

# Wait for pause message
output = read_process(terminal_id, wait=true)

# Create quality-answers.json
# (analyze quality-questions.json and create your answers)

# Send Enter to continue
write_process(terminal_id, "\n")

# Wait for completion
final_output = read_process(terminal_id, wait=true)
```

**Option 2: Create quality-answers.json first**

If `quality-answers.json` already exists, the script will use it without pausing:

```sh
# 1. Run once to generate quality-questions.json (will fail with EOFError)
# 2. Analyze quality-questions.json
# 3. Create quality-answers.json
# 4. Run again - script will detect existing file and skip pause
python scripts/store_extraction.py --project X --extraction-file Y
```

**Option 3: Pipe empty input (PowerShell/Bash)**

**PowerShell:**
```powershell
# Create quality-answers.json first, then:
"" | python scripts/store_extraction.py --project X --extraction-file Y
```

**Bash/Linux:**
```sh
# Create quality-answers.json first, then:
echo "" | python scripts/store_extraction.py --project X --extraction-file Y
```

**Note:** This only works if `quality-answers.json` already exists. The empty input just satisfies the Enter prompt.

**Option 4: Use --skip-quality-check (NOT RECOMMENDED)**

```sh
# WARNING: This skips deduplication and contradiction detection!
# Only use for testing or if you're absolutely sure there are no duplicates
python scripts/store_extraction.py --project X --extraction-file Y --skip-quality-check
```

### Solution for Human Users

Just press Enter when prompted after creating `quality-answers.json`.

### Common Mistakes

**DON'T use `echo` in PowerShell:**
```powershell
# WRONG - PowerShell echo requires InputObject parameter
echo "" | python scripts/store_extraction.py ...

# Error: Cannot process command because of one or more missing mandatory parameters: InputObject
```

**DO use empty string in PowerShell:**
```powershell
# CORRECT - Use empty string directly
"" | python scripts/store_extraction.py ...
```

**In Bash/Linux, `echo` works fine:**
```sh
# CORRECT - echo works in bash
echo "" | python scripts/store_extraction.py ...
```

---

## Query Returns 0 Results

### Symptom
```
$ python scripts/query_memory.py --project my-project --all
Found 0 entities:
```

### Cause
Query tool is looking in the wrong database file.

### Solution

**Step 1: Check which database file has your data**
```sh
ls -lh memory/*.graph
```

Look for files with size > 50KB (those have data).

**Step 2: Use verbose mode to see which file is being used**
```sh
python scripts/query_memory.py --project my-project --all --verbose
```

**Step 3: If wrong file, specify correct one**
```sh
python scripts/query_memory.py --project my-project --db ./memory/my-project.graph --all
```

**Step 4: Fix the issue permanently**

Run health check to see all database files:
```sh
python scripts/health_check.py
```

Delete the empty/smaller duplicate files.

---

## Database Appears Empty

### Symptom
```
[WARNING] Database appears empty or new: ./memory/my-project.graph (20,480 bytes)
```

### Cause
1. You haven't stored any data yet, OR
2. You have multiple database files and query is using the empty one

### Solution

**Check if data was actually stored:**
```sh
# List all database files with sizes
ls -lh memory/

# Files > 50KB have data
# Files < 50KB are empty
```

**If you have data in a different file:**
```sh
# Use the correct file
python scripts/query_memory.py --project my-project --db ./memory/my-project.graph --all
```

**If you haven't stored data yet:**
```sh
# Store some data first
python scripts/store_extraction.py --project my-project --extraction-file examples/current-extraction.json
```

---

## Multiple Database Files for Same Project

### Symptom
```
[WARNING] Multiple databases for project 'my-project':
   my-project.graph (21,356,544 bytes) <- LARGEST
   my-project.kuzu (20,480 bytes)
```

### Cause
Database files were created with different extensions (legacy `.kuzu` vs current `.graph`).

### Why This Happens
- Old versions used `.kuzu` or `.db` extension
- Current version uses `.graph` extension
- All work, but having multiple causes confusion

### Solution

**Keep the larger file (has data), delete the smaller one:**

```sh
# On Unix/Mac
rm memory/my-project.kuzu

# On Windows
del memory\my-project.kuzu
```

**Or rename to standardize on .graph:**
```sh
# On Unix/Mac
mv memory/my-project.kuzu memory/my-project.graph

# On Windows
move memory\my-project.kuzu memory\my-project.graph
```

---

## Which Database File Should I Use?

### Answer

**Pattern:** `./memory/{project-name}.graph`

Examples:
- Project "llm_memory" -> `./memory/llm_memory.graph`
- Project "my-app" -> `./memory/my-app.graph`
- Project "auth-service" -> `./memory/auth-service.graph`

**Note:** `.kuzu` and `.db` extensions also work (legacy) but `.graph` is preferred.

---

## How to Verify Data Was Stored

### After running store_extraction.py

**Step 1: Check the output**
```
[OK] Storage complete!
Entities stored: 31
Facts stored: 19
```

**Step 2: Verify with query**
```sh
python scripts/query_memory.py --project my-project --all
```

Should show your entities.

**Step 3: Check file size**
```sh
ls -lh memory/my-project.graph
```

Should be > 50KB if data was stored.

---

## Python 3.14 Not Supported

### Symptom
```
[ERROR] FAIL: Python 3.14+ not supported (kuzu limitation)
```

### Cause
The `kuzu` library doesn't have pre-built wheels for Python 3.14 yet.

### Solution

**Install Python 3.13 or earlier:**

**Option 1: Install Python 3.13 from python.org**
- Download from https://www.python.org/downloads/
- Install alongside Python 3.14
- Use `python3.13` command

**Option 2: Use portable Python (Windows)**
See WINDOWS-SETUP.md for details.

**Option 3: Use pyenv (Unix/Mac)**
```sh
pyenv install 3.13.0
pyenv local 3.13.0
```

---

## Cannot Import kuzu

### Symptom
```
ModuleNotFoundError: No module named 'kuzu'
```

### Solution
```sh
pip install kuzu
```

Or if using requirements.txt:
```sh
pip install -r requirements.txt
```

---

## Windows Console Encoding Errors

### Symptom
```
UnicodeEncodeError: 'charmap' codec can't encode character
```

### Cause
Windows console uses CP1252 encoding by default.

### Solution

**This is already fixed!** All scripts use `safe_print()` which handles encoding automatically.

If you still see errors:
1. Make sure you're using the latest version of the scripts
2. Check that `tools/console_utils.py` exists
3. Run health check: `python scripts/health_check.py`

---

## Database File Not Found

### Symptom
```
[ERROR] Database file not found: ./memory/my-project.graph
```

### Cause
You haven't created the database yet.

### Solution

**Store some data first:**
```sh
# Option 1: Store an interaction
python scripts/store_interaction.py \
    --project my-project \
    --user "Hello" \
    --assistant "Hi there"

# Option 2: Import a conversation
python scripts/import_conversation.py \
    --project my-project \
    --file examples/sample-conversation.json

# Option 3: Store extraction
python scripts/store_extraction.py \
    --project my-project \
    --extraction-file examples/current-extraction.json
```

---

## OpenTimestamps Submission Fails

### Symptom
```
[INFO] OpenTimestamps servers unreachable (network constrained); using local timestamp
```
or
```
[WARN] OpenTimestamps submission failed: ...; using local timestamp
```

### Cause
OpenTimestamps requires internet access to pool servers. Common reasons for failure:
- Firewall blocking outbound connections
- Corporate proxy
- Air-gapped environment
- Network timeout

### Solution

**This is NOT an error.** The system gracefully falls back to local timestamps.

Your data is still:
- ✅ Hashed and stored
- ✅ Locally timestamped
- ✅ Part of the hash chain

You just don't get Bitcoin attestation for external proof.

**To explicitly skip OTS (cleaner output):**
```sh
python scripts/import_conversation.py --project X --file Y --constrained-environment
```

**To retry OTS later:**
```sh
python scripts/upgrade_timestamps.py --project X
```

---

## For More Help

- **README.md** - Complete usage guide
- **docs/QUICK-START.md** - Step-by-step tutorial
- **docs/KNOWN_ISSUES.md** - Known issues and technical debt
- **WINDOWS-SETUP.md** - Windows-specific help

