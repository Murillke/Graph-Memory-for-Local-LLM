# init.md - Initialize Memory System

---

## [BOT] Special Case: Config Setup

**This is the ONLY doc where you SET config values.**

During initialization, you set `project_name` and `python_path` in `mem.config.json`.
After that, ALL other workflow docs instruct you to READ those values - never invent new ones.

---

## LLM Instructions

**If you have been instructed to "follow init.md", "execute init.md", "run init.md" or "initialize memory", you are expected to:**

1. **Verify Python is available** (check system python3 or local install)
2. **Verify dependencies are installed** (check requirements.txt packages)
3. **Create necessary directories** (memory/, tmp/ if they don't exist)
4. **Copy example config** to mem.config.json and edit project_name/python_path
5. **Inform the user** if any prerequisites are missing

**[!] CONSTRAINED ENVIRONMENTS (Codex, sandboxed agents):**
If you CANNOT make outbound network requests, when running sync.md later you MUST use `--constrained-environment` flag on import_conversation.py. The example config has empty wrappers (manual extraction) which is correct for constrained environments.

**You are capable of:**
- Running Python version checks via launch-process
- Checking if directories exist
- Creating directories if needed
- Verifying package installations
- Copying and editing config files

**Follow the instructions below to initialize the memory system.**

---

## What This Does

- Creates necessary directories (memory/, tmp/)
- Verifies Python and dependencies are installed
- Sets up the project for first use

---

## Prerequisites

- Python 3.9-3.13 installed (or portable Python in python313/, if not check Troubleshooting section )
- requirements.txt dependencies installed

---

## Instructions

### Step 1: Check Python

```sh
python3 --version       # Linux/Mac
# or on Windows: .\python313\python.exe --version
```

**Expected output:** `Python 3.X.X` (where X is 9-13)

**If Python not found:** See [WINDOWS-SETUP.md](../WINDOWS-SETUP.md) for portable Python setup.

---

### Step 2: Install Dependencies

```sh
pip install -r requirements.txt
# or on Windows: .\python313\python.exe -m pip install -r requirements.txt
```

**Expected output:** `Successfully installed kuzu-X.X.X ...`

---

### Step 3: Create Directories

```sh
mkdir -p memory tmp
# Windows: New-Item -ItemType Directory -Force -Path memory, tmp
```

**Expected output:** Directories created (or already exist)

---

### Step 4: Setup Config (REQUIRED)

**COPY the example config - do NOT create your own:**

```sh
cp examples/mem.config.json mem.config.json
# Windows: Copy-Item examples\mem.config.json -Destination mem.config.json
```

**Then edit mem.config.json:**
1. Change `project_name` to your project name
2. Change `python_path` to your Python path (e.g., `python3` or full path)

**DO NOT change database paths** - they are correct as-is:
- `./memory/conversations.db` - SQL database
- `./memory/{project_name}.graph` - Graph database

**Empty wrappers = manual extraction** (default, recommended):
```json
"llm_wrapper_entities": "",
"llm_wrapper_facts": "",
"llm_wrapper": ""
```
This means YOU create extraction JSON manually. No external LLM calls.

---

---

### Step 5: Verify Installation

```sh
{PYTHON_PATH} scripts/sync.py --help
```

**Expected output:** Help text shows (means kuzu imported successfully)

---

### Step 6: Check Status

```sh
{PYTHON_PATH} scripts/sync.py --project {PROJECT} --status
```

Use the `project_name` you just set in `mem.config.json`.

**Expected output:**
```
Project: {PROJECT}
Total interactions: 0
Processed: 0
Unprocessed: 0
```

---

## Success Criteria

[OK] Python version 3.9-3.13 installed
[OK] Dependencies installed (kuzu)
[OK] Directories created (memory/, tmp/)
[OK] Verification command works
[OK] Status command works

---

## Troubleshooting

**"Python not found"**
- See [WINDOWS-SETUP.md](../WINDOWS-SETUP.md) for portable Python setup

**"No module named 'kuzu'"**
- Run: `pip install -r requirements.txt`

**"Project not found"**
- Normal for new projects - will be created on first sync

---

## Next Steps

After initialization:
- **Follow [mem/sync.md](sync.md)** to sync your first conversation
- **Follow [mem/remember.md](remember.md)** to query memory

---

**Initialization complete! Ready to use the memory system.**

