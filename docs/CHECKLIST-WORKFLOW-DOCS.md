# CHECKLIST-WORKFLOW-DOCS

> ⚠️ **DO NOT DELETE** - This is a reusable validation tool for ALL workflow documentation.
> Use this checklist when creating NEW workflow docs or re-validating EXISTING ones.

**Purpose:** Validate that workflow documentation (.md files in root) follows standardized patterns for reliable agent execution.

**What this checks:** The DOCUMENTATION, not the code.

---

## Overview

This checklist validates that workflow documentation files follow standardized patterns to prevent agent execution failures caused by:
- Hardcoded paths and project names
- Ambiguous phrasing about configuration
- Platform-specific assumptions
- Inconsistent placeholder usage
- Stale command contracts after workflow hardening

---

## Scope

**Files to audit:**
- Root command docs: `backup.md`, `consolidate.md`, `dump.md`, `export.md`, `extract.md`, `history.md`, `import-documents.md`, `import.md`, `init.md`, `recall.md`, `remember-external.md`, `remember.md`, `search-external.md`, `search.md`, `stats.md`, `status.md`, `sync.md`, `tasks.md`, `verify.md`, `visualize.md`
- Procedural docs: `procedure.md`, `recall_procedure.md`

**Files excluded:**
- `init.md` - Special case (sets config values, doesn't read them)
- `README.md`, `LLM-INSTRUCTIONS.md` - Not workflow docs
- Files in `docs/`, `examples/`, `archive/` - Not primary workflows

---

## Classification Buckets

After audit, classify each file into one of three buckets:

1. **✅ Already config-first** - No changes needed
2. **⚠️ Needs wording fix only** - Has config-first section but minor issues
3. **❌ Needs example replacement** - Hardcoded values in examples

---

## Checklist Items

### 1. Config-First Section (REQUIRED)

**Location:** After title, before main content
**Format:**
```markdown
## [BOT] Config First

**Read `mem.config.json` before running any command:**
- Use `python_path` value for `{PYTHON_PATH}`
- Use `project_name` value for `{PROJECT}`
- Do not guess or substitute different values
```

**Verification:**
- [ ] Section exists with exact `[BOT] Config First` header
- [ ] Positioned after title/description, before LLM Instructions or main content
- [ ] Uses exact standardized wording (no variations)
- [ ] Mentions both `python_path` and `project_name`

**Common issues:**
- ❌ Missing section entirely
- ❌ Buried in middle of document
- ❌ Different wording ("Read config first" instead of exact format)
- ❌ Only mentions one config value

---

### 2. No Hardcoded Python Paths (CRITICAL)

**Search patterns:**
```bash
grep -n "python313\|python3\|python\|\.exe" filename.md
```

**Violations:**
- ❌ `python3` in examples
- ❌ `python` in examples
- ❌ `.\python313\python.exe` in examples
- ❌ `/usr/bin/python3` in examples
- ❌ Platform-specific paths

**Allowed:**
- ✅ `{PYTHON_PATH}` placeholder
- ✅ Mentions in prose ("uses Python")
- ✅ In config-first section as example

**Verification:**
- [ ] No hardcoded `python3` in command examples
- [ ] No hardcoded `python` in command examples
- [ ] No hardcoded `.exe` paths in command examples
- [ ] All examples use `{PYTHON_PATH}` placeholder

---

### 3. No Hardcoded Project Names (CRITICAL)

**Search patterns:**
```bash
grep -n "my-project\|llm_memory\|myproject" filename.md
```

**Violations:**
- ❌ `my-project` in examples
- ❌ `llm_memory` in examples
- ❌ `demo` in examples (unless explicitly labeled as demo)
- ❌ Any specific project name in command examples

**Allowed:**
- ✅ `{PROJECT}` placeholder
- ✅ Repo-specific examples explicitly labeled
- ✅ In config-first section as example

**Verification:**
- [ ] No hardcoded `my-project` in command examples
- [ ] No hardcoded `llm_memory` in command examples
- [ ] All examples use `{PROJECT}` placeholder
- [ ] Repo-specific examples are clearly labeled

---

### 4. No Ambiguous Phrasing (IMPORTANT)

**Search patterns:**
```bash
grep -i "replace with your project\|use python3 on\|on Linux\|on Windows" filename.md
```

**Violations:**
- ❌ "replace with your project name"
- ❌ "use python3 on Linux/Mac"
- ❌ "use python on Windows"
- ❌ Platform-specific command variations without config reference

**Allowed:**
- ✅ "Use values from mem.config.json"
- ✅ "Replace {PYTHON_PATH} and {PROJECT} with values from mem.config.json"
- ✅ Platform notes that reference config

**Verification:**
- [ ] No "replace with your project" phrases
- [ ] No "use python3 on Linux/Mac" phrases
- [ ] No platform-specific variations without config reference
- [ ] Clear guidance to read from config

---
### 5. Consistent Placeholder Usage (IMPORTANT)

**Required placeholders:**
- `{PYTHON_PATH}` - For Python interpreter path
- `{PROJECT}` - For project name
- `{CONVERSATION_FILE}` - For dynamic conversation file paths
- `{EXTRACTION_FILE}` - For dynamic extraction file paths
- `{AGENT}` - For agent name parameter

**Verification:**
- [ ] All command examples use placeholders consistently
- [ ] No mixing of placeholders and hardcoded values
- [ ] Placeholders match config-first section
- [ ] Dynamic file paths use appropriate placeholders

**Common issues:**
- ❌ Some examples use `{PROJECT}`, others use `my-project`
- ❌ Some examples use `{PYTHON_PATH}`, others use `python3`
- ❌ Inconsistent capitalization of placeholders

---

### 6. Platform-Agnostic Examples (REQUIRED)

**Violations:**
- ❌ Separate "Windows:" and "Linux/Mac:" sections
- ❌ Different commands for different platforms
- ❌ PowerShell-specific syntax (backticks `` ` `` for line continuation)
- ❌ Windows path separators (`tmp\`, `scripts\`)
- ❌ Code fences using ````bash` instead of ````sh`
- ❌ Shell-specific commands (`echo`, `start`, etc.)

**Allowed:**
- ✅ Single unified examples with placeholders
- ✅ Platform notes that reference config
- ✅ POSIX-compliant `sh` syntax
- ✅ Forward slashes for all paths (`tmp/`, `scripts/`)
- ✅ Backslash `\` for line continuation (POSIX standard)

**Verification:**
- [ ] No separate platform-specific command sections
- [ ] Examples work across platforms with config values
- [ ] Code fences use ````sh` not ````bash` or ````powershell`
- [ ] All paths use forward slashes (`/`)
- [ ] Line continuations use `\` not `` ` ``
- [ ] No shell-specific commands (use file creation tools instead)

**Portability Standards (Updated 2026-03-14):**
- **Code fences:** Use ````sh` (POSIX-compliant, works everywhere)
- **Paths:** Always use `/` (works on Windows, macOS, Linux)
- **Line continuation:** Use `\` (POSIX standard)
- **Python version:** Code must work on Python 3.8+ (use `Optional[T]` not `T | None`)

---

### 7. File-Based / Helper-File Input Guidance (REQUIRED for agent-facing hot paths)

**For agent-facing workflow inputs:**
- ✅ Use `--*-file` / helper-file flags where the workflow standard requires them
- ✅ Warn that deprecated direct query/name flags are not part of the approved workflow
- ✅ Reference `prepare_sync_files.py --project {PROJECT} --json` for helper-file creation

**Verification:**
- [ ] Multi-word examples use file-based flags
- [ ] Agent-facing docs do not present deprecated direct query/name flags as the primary path
- [ ] Guidance on avoiding quote escaping issues
- [ ] Reference to file creation tools

---

### 8. Quality Review / Constrained-Environment Guidance (REQUIRED where applicable)

**For sync/import/storage workflows:**
- ✅ `--constrained-environment` guidance is explicit when outbound network access is unavailable, restricted, or unknown
- ✅ AI agents are told they must not use human-only skip flags
- ✅ Quality-review steps explain the rerun pattern with `tmp/quality-answers.json`

**Verification:**
- [ ] Network-sensitive import examples mention `--constrained-environment`
- [ ] Quality-review instructions match current script contracts
- [ ] Human-only skip flags are explicitly forbidden for AI agents

---

## Testing Procedures

### Automated Checks

Run these commands to find violations:

```bash
# Check for hardcoded Python paths
grep -n "python313\|python3 scripts\|python scripts" *.md

# Check for hardcoded project names
grep -n "my-project\|llm_memory" *.md

# Check for ambiguous phrasing
grep -i "replace with your\|use python3 on" *.md

# Check for config-first section
grep -n "\[BOT\] Config First" *.md
```

### Manual Verification

1. **Read config-first section** - Verify exact wording
2. **Scan all code blocks** - Check for placeholders
3. **Test commands** - Replace placeholders with actual config values and run
4. **Check consistency** - Ensure all examples follow same pattern

### Functional Testing

For each workflow doc:

1. Read `mem.config.json` to get `python_path` and `project_name`
2. Replace `{PYTHON_PATH}` and `{PROJECT}` in examples
3. Run at least one command from the doc
4. Verify it executes without errors

**Example:**
```bash
# From mem.config.json:
# python_path: "python3"
# project_name: "llm_memory"

# Test command from remember.md:
python3 scripts/query_memory.py --project llm_memory --last 5
```

---

## Remediation Guidelines

### For "Needs Wording Fix Only"

**Steps:**
1. Add or fix config-first section
2. Update ambiguous phrasing
3. Add placeholder reminders
4. Verify no hardcoded values

**Example fix:**
```markdown
# Before
Use python3 on Linux or python on Windows

# After
Use `{PYTHON_PATH}` from mem.config.json
```

### For "Needs Example Replacement"

**Steps:**
1. Add config-first section if missing
2. Replace all hardcoded `python3` with `{PYTHON_PATH}`
3. Replace all hardcoded `my-project` with `{PROJECT}`
4. Add reminder note about placeholder replacement
5. Remove platform-specific sections
6. Test updated examples

**Example fix:**
```markdown
# Before
```bash
python3 scripts/query_memory.py --project my-project --all
```

# After
```bash
{PYTHON_PATH} scripts/query_memory.py --project {PROJECT} --all
```

Replace `{PYTHON_PATH}` and `{PROJECT}` with values from mem.config.json
```

---

## Audit Results Template

Use this template to document audit results:

```markdown
## Quality Control Audit Report for [filename]

### Classification: [✅ Already config-first | ⚠️ Needs wording fix | ❌ Needs example replacement]

### Issues Found:

#### 1. Config-First Section: [✅ | ❌]
- Status: [description]

#### 2. Hardcoded Python Paths: [✅ | ❌]
- Count: [N instances]
- Lines: [line numbers]

#### 3. Hardcoded Project Names: [✅ | ❌]
- Count: [N instances]
- Lines: [line numbers]

#### 4. Ambiguous Phrasing: [✅ | ❌]
- Issues: [description]

#### 5. Placeholder Consistency: [✅ | ❌]
- Issues: [description]

### Recommended Fixes:
[List specific changes needed]

### Testing:
[Commands tested and results]
```

---

## Success Criteria

A workflow doc passes quality control when:

- [x] Has standardized [BOT] Config First section
- [x] Zero hardcoded Python paths in examples
- [x] Zero hardcoded project names in examples
- [x] No ambiguous phrasing about configuration
- [x] Consistent placeholder usage throughout
- [x] At least one command tested successfully
- [x] Platform-agnostic examples (or clearly labeled)

---

## Regression Prevention

### Pre-Commit Checks

Add to `.git/hooks/pre-commit`:
```bash
#!/bin/bash
# Check for config-first violations in workflow docs

echo "Checking workflow docs for config-first compliance..."

# Check for hardcoded python3
if grep -n "python3 scripts" *.md 2>/dev/null | grep -v "CONFIG-FIRST-QUALITY-CHECKLIST"; then
    echo "ERROR: Found hardcoded 'python3' in workflow docs"
    echo "Use {PYTHON_PATH} placeholder instead"
    exit 1
fi

# Check for hardcoded my-project
if grep -n "my-project" *.md 2>/dev/null | grep -v "CONFIG-FIRST-QUALITY-CHECKLIST"; then
    echo "ERROR: Found hardcoded 'my-project' in workflow docs"
    echo "Use {PROJECT} placeholder instead"
    exit 1
fi

echo "Config-first checks passed!"
```

### Documentation Review Checklist

When adding or updating workflow docs:

1. [ ] Added [BOT] Config First section
2. [ ] Used {PYTHON_PATH} for all Python commands
3. [ ] Used {PROJECT} for all project references
4. [ ] Tested at least one command
5. [ ] No platform-specific variations
6. [ ] Ran automated checks
7. [ ] Updated this checklist if needed

---

## Maintenance

**Review frequency:** After any workflow doc changes
**Owner:** Documentation maintainers
**Last updated:** 2026-03-14

**Change log:**
- 2026-03-14: Initial version created during config-first audit

---

## References

- **Original Plan:** Quality control plan in conversation
- **Example Compliant Docs:** sync.md, dump.md, extract.md, remember.md, recall.md
- **Example Fixed Docs:** procedure.md, recall_procedure.md, backup.md
- **Example Non-Compliant:** search.md (needs fixes)

---

**END OF CHECKLIST**


