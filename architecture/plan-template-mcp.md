# Action Plan v4: Template Pattern Standardization (MCP-Compatible)

## Changelog

| Version | Changes |
|---------|---------|
| v4 | Fixed query schema: `facts`/`search_procedures` are TEXT not bool, `direction` includes `both`. Fixed enum validation to allow empty optional fields. Removed duplicate common/advanced schema split. |
| v4.1 | Changed test strategy to module-level testing (matching existing repo pattern). Removed dependency on nonexistent CLI flags. Added explicit "project" handling in schema model. Added type coercion to validator. |
| v4.2 | Fixed import path (`tools.graph_db` not `tools.graph_database`). Fixed `strip_help_fields()` to actually strip before validation. Removed "E2E"/"MCP paths" language - now consistently says "module-level contract tests". |
| v3 | Added MCP compatibility architecture, shared schemas, project authority decision |
| v2 | Fixed parser flow, added `_help_*` prefix convention |
| v1 | Initial proposal |

## Overview

This plan standardizes CLI input patterns while ensuring **full MCP compatibility**.

**Design Principle:** Every fix here benefits BOTH template-based CLI use AND future MCP server implementation.

**Network assumption:** MCP must support both localhost and private-network/VPN deployment from the beginning while remaining deny-by-default. Private-network mode is first-class, but only explicitly allowlisted private subnets are permitted. Public internet exposure is out of scope for this plan. See [docs/MCP-NETWORK-POSTURE.md](/Users/davidastua/Documents/llm-mem/docs/MCP-NETWORK-POSTURE.md).

---

## MCP Compatibility Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        INPUT SOURCES                                │
├──────────────────┬──────────────────┬──────────────────────────────┤
│  Human CLI       │  Template File   │  MCP Tool Call               │
│  --user "..."    │  --file tmp/x    │  {"user": "...", ...}        │
├──────────────────┴──────────────────┴──────────────────────────────┤
│                     SHARED SCHEMA LAYER                             │
│           (Same JSON schema for templates AND MCP tools)            │
├─────────────────────────────────────────────────────────────────────┤
│                     SCRIPT CORE LOGIC                               │
│              (Importable functions, not just CLI)                   │
└─────────────────────────────────────────────────────────────────────┘
```

**MCP Server will:**
1. Receive structured tool call
2. Validate against SHARED SCHEMA
3. Call script via import OR subprocess with --file
4. Return result

**Transport note:**
- primary mode: local process / stdio
- also supported from day one: private-network listener with default deny and private-subnet allowlists only
- excluded: open internet listener
- private-network mode must require TLS and must not rely on public DNS or port-forwarding
- app-level authentication can remain optional for small home-use VPN deployments, but should be available as a hardening path

**Implication:** the same schema and script core must work whether the caller is local or reaches a private MCP host over VPN/LAN.

---

## Codex Findings: Fixes

### 🔴 FIX 1: Parser Conflict (CRITICAL)

**Problem:** `store_interaction.py --file tmp/x.json` fails because `--project` is required.

**Decision:** `--project` REQUIRED with `--file`. MCP server will always provide both.

**Rationale:**
- Keeps config-mismatch safety guard intact
- MCP server controls CLI args anyway
- No "two sources of truth" problem

```python
# store_interaction.py - FIXED DESIGN
group = parser.add_mutually_exclusive_group(required=True)
group.add_argument('--project', help='Project name')
group.add_argument('--path', help='File path')

parser.add_argument('--file', help='JSON file with interaction data')
parser.add_argument('--user', help='User message (required if not using --file)')
parser.add_argument('--assistant', help='Assistant message (required if not using --file)')

# After parse:
if args.file:
    data = load_template(args.file, required_fields=['user', 'assistant'])
    args.user = data['user']
    args.assistant = data['assistant']
    # NOTE: data['project'] is IGNORED - CLI --project is authoritative
    # This preserves config.py mismatch guards
elif not args.user or not args.assistant:
    parser.error("--user and --assistant required when not using --file")
```

**Command (template flow):**
```bash
python scripts/store_interaction.py --project llm_memory --file tmp/interaction.json
```

**Command (MCP server internal):**
```python
# MCP server calls the same way
subprocess.run([
    'python', 'scripts/store_interaction.py',
    '--project', project_name,
    '--file', temp_file_path
])
```

---

### 🟡 FIX 2: Project Authority (HIGH)

**Problem:** Plan said to override `args.project` from template, but `config.py:55,71` has mismatch guards.

**Decision:** CLI is authoritative. Template `project` field is for **documentation only**.

| Source | Authority | Use |
|--------|-----------|-----|
| `--project` CLI arg | ✅ AUTHORITATIVE | Used by script |
| Template `project` field | ❌ IGNORED | Documentation for humans |
| MCP tool `project` param | ✅ AUTHORITATIVE | MCP server passes as `--project` |

**Template with documentation-only project:**
```json
{
  "_help": "Store interaction. Run: python scripts/store_interaction.py --project YOUR_PROJECT --file tmp/interaction.json",
  "_help_project": "Replace YOUR_PROJECT in the command above. This field is NOT used by the script.",
  "project": "YOUR_PROJECT_NAME",
  "user": "",
  "assistant": ""
}
```

**MCP Benefit:** MCP server doesn't need to reconcile conflicting project sources.

---

### 🟡 FIX 3: Query Template Completeness (MEDIUM)

**Problem:** Template exposes subset of API. Missing: `label`, `entity_uuid`, `facts`, `procedure`, `search_procedures`, `direction`, `last`.

**Decision:** Full schema with `_help_advanced` section.

```python
# NOTE: Single schema definition in tools/schemas.py (see "Shared Schema Design" section below)
# Removed duplicate common/advanced split - use flat "fields" structure only
```

**Template includes ALL fields (with correct types matching CLI):**
```json
{
  "_help": "Query memory. Run: python scripts/query_memory.py --project YOUR_PROJECT --input-file tmp/query.json",
  "search": "",
  "entity": "",
  "type": "",
  "limit": 50,
  "_help_advanced": "Advanced options below - leave empty/null if not needed",
  "label": "",
  "entity_uuid": "",
  "_help_facts": "TEXT search query for facts (not boolean)",
  "facts": "",
  "procedure": "",
  "_help_search_procedures": "TEXT search query for procedures (not boolean)",
  "search_procedures": "",
  "_help_direction": "One of: incoming, outgoing, both",
  "direction": "",
  "last": null
}
```

**MCP Benefit:** Schema definitions reused for MCP tool parameter validation.

---

### 🟡 FIX 4: Contract Tests (MEDIUM)

**Problem:** No tests verifying template → script contracts.

**Decision:** Module-level contract tests (matching existing repo test pattern).

**What tests validate:**
- Schema/template output can be consumed by script core logic correctly
- Type coercion and validation work as expected

**What tests do NOT validate:**
- Full CLI subprocess paths (would require adding new CLI flags)
- MCP server integration (separate future work)

```python
"""Test that schema templates work with script core logic.

Module-level tests matching existing repo pattern (see tests/test_tasks.py).
"""

import unittest
import shutil
from pathlib import Path
from uuid import uuid4

# Import core logic directly, not via CLI
from tools.schemas import SCHEMAS, generate_template, validate_against_schema, load_and_validate
from tools.graph_db import GraphDatabase

REPO_ROOT = Path(__file__).parent.parent


class TestSchemaTemplateContracts(unittest.TestCase):
    """Test that generated templates are valid for their target functions."""

    def test_task_template_validates(self):
        """Task template with filled fields passes validation."""
        template = generate_template("task", include_help=True)

        # Fill required fields
        template["name"] = "Test Task"
        template["summary"] = "Test Summary"
        template["priority"] = "high"

        errors = validate_against_schema(template, "task")
        self.assertEqual(errors, [])

    def test_task_template_empty_fails(self):
        """Task template with empty required fields fails validation."""
        template = generate_template("task", include_help=True)
        # Leave fields empty

        errors = validate_against_schema(template, "task")
        self.assertIn("name", str(errors))
        self.assertIn("summary", str(errors))

    def test_query_template_optional_fields(self):
        """Query template with only optional fields passes validation."""
        template = generate_template("query", include_help=True)
        template["search"] = "test query"
        # Leave other fields empty/None

        errors = validate_against_schema(template, "query")
        self.assertEqual(errors, [])

    def test_query_direction_enum(self):
        """Query direction field validates enum values including 'both'."""
        template = generate_template("query", include_help=True)

        for valid in ["incoming", "outgoing", "both"]:
            template["direction"] = valid
            errors = validate_against_schema(template, "query")
            self.assertEqual(errors, [], f"Failed for direction={valid}")

        template["direction"] = "invalid"
        errors = validate_against_schema(template, "query")
        self.assertIn("direction", str(errors))

    def test_type_coercion_int_fields(self):
        """Integer fields are coerced from strings."""
        template = generate_template("query", include_help=True)
        template["limit"] = "25"  # String instead of int

        data, errors = load_and_validate(template, "query")
        self.assertEqual(errors, [])
        self.assertEqual(data["limit"], 25)  # Coerced to int
        self.assertIsInstance(data["limit"], int)


class TestTaskSchemaToFunction(unittest.TestCase):
    """Test that validated task data works with actual task functions."""

    def setUp(self):
        base_tmp = REPO_ROOT / "tests" / "tmp"
        base_tmp.mkdir(parents=True, exist_ok=True)
        self.test_dir = base_tmp / f"schema_contract_{uuid4().hex[:8]}"
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.graph_path = self.test_dir / "test.graph"
        self.project_name = "schema-test"
        self.graph_db = GraphDatabase(str(self.graph_path))
        self.graph_db.create_project_node(self.project_name)

    def tearDown(self):
        self.graph_db.close()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_validated_task_creates_entity(self):
        """Task data that passes schema validation can create graph entity."""
        template = generate_template("task", include_help=True)
        template["name"] = "Schema Test Task"
        template["summary"] = "Created from validated template"
        template["priority"] = "high"

        data, errors = load_and_validate(template, "task")
        self.assertEqual(errors, [])

        # Use validated data to create entity (matching tasks.py logic)
        uuid = self.graph_db.create_entity(
            name=data["name"],
            group_id=self.project_name,
            source_interactions=["test-1"],
            source_hashes=["hash-1"],
            extraction_version="v1.0.0",
            extraction_commit="test",
            summary=data["summary"],
            labels=["Task"],
            attributes={"priority": data["priority"], "status": "pending"}
        )

        self.assertIsNotNone(uuid)
        # Verify entity exists
        entity = self.graph_db.get_entity_by_uuid(uuid)
        self.assertEqual(entity["name"], "Schema Test Task")
```

**CLI Smoke Tests (existing interfaces only):**

```python
class TestExistingCLIInterfaces(unittest.TestCase):
    """Smoke tests for CLI paths that already exist."""

    def test_query_memory_input_file(self):
        """query_memory.py --input-file works (interface exists)."""
        import subprocess
        import json
        import tempfile

        # Create minimal query file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"search": "test", "limit": 5}, f)
            query_file = f.name

        try:
            result = subprocess.run([
                'python', 'scripts/query_memory.py',
                '--project', 'llm_memory',
                '--input-file', query_file
            ], capture_output=True, text=True, timeout=30)

            # Should not error on parse (may return empty results)
            self.assertNotIn("error", result.stderr.lower())
        finally:
            Path(query_file).unlink(missing_ok=True)
```

---

## Shared Schema Design (MCP-Ready)

Create `tools/schemas.py` - used by templates AND future MCP server:

```python
"""Shared schemas for templates and MCP tools.

DESIGN NOTE ON PROJECT HANDLING:
- Project is NOT included in template "fields" because CLI is authoritative for project.
- Templates are "payload only" - project is passed via CLI --project flag.
- MCP tools receive project as a separate parameter, not in the payload.
- This avoids dual-authority conflicts with config.py mismatch guards.
- The "project_source" key documents how each script receives project.
"""

SCHEMAS = {
    "interaction": {
        "project_source": "cli",  # --project flag, NOT in payload
        "fields": {
            "user": {"type": "str", "required": True, "help": "User's message"},
            "assistant": {"type": "str", "required": True, "help": "Assistant's response"}
        },
        "cli_command": "store_interaction.py --project {project} --file {file}"
    },
    "task": {
        "project_source": "cli",
        "fields": {
            "name": {"type": "str", "required": True, "help": "Short task name"},
            "summary": {"type": "str", "required": True, "help": "Detailed description"},
            "priority": {"type": "str", "required": False, "default": "medium",
                        "enum": ["high", "medium", "low"], "help": "Task priority"}
        },
        "cli_command": "tasks.py --project {project} --add-file {file}"
    },
    "query": {
        "project_source": "cli",
        "fields": {
            "search": {"type": "str", "required": False, "help": "Semantic search term"},
            "entity": {"type": "str", "required": False, "help": "Entity name"},
            "type": {"type": "str", "required": False, "help": "Relationship type filter"},
            "limit": {"type": "int", "required": False, "default": 50},
            "label": {"type": "str", "required": False},
            "entity_uuid": {"type": "str", "required": False, "help": "Entity UUID"},
            "facts": {"type": "str", "required": False, "help": "Search facts by TEXT query (not boolean)"},
            "procedure": {"type": "str", "required": False, "help": "Procedure name"},
            "search_procedures": {"type": "str", "required": False, "help": "Search procedures by TEXT query (not boolean)"},
            "direction": {"type": "str", "required": False, "enum": ["incoming", "outgoing", "both"], "default": "both"},
            "last": {"type": "int", "required": False, "help": "Get last N entities"}
        },
        "cli_command": "query_memory.py --project {project} --input-file {file}"
    }
}

def generate_template(schema_name: str, include_help: bool = True) -> dict:
    """Generate a template dict from schema."""
    schema = SCHEMAS[schema_name]
    template = {}
    
    if include_help:
        template["_help"] = f"Run: python scripts/{schema['cli_command']}"
    
    for field, spec in schema["fields"].items():
        if include_help and "help" in spec:
            template[f"_help_{field}"] = spec["help"]
        
        # Set default or empty value
        if "default" in spec:
            template[field] = spec["default"]
        elif spec["type"] == "bool":
            template[field] = False
        elif spec["type"] == "int":
            template[field] = None
        else:
            template[field] = ""
    
    return template

def validate_against_schema(data: dict, schema_name: str) -> list[str]:
    """Validate data against schema. Returns list of errors (no coercion)."""
    schema = SCHEMAS[schema_name]
    errors = []

    for field, spec in schema["fields"].items():
        value = data.get(field)

        # Normalize empty strings to None for optional fields
        if value == "" and not spec.get("required"):
            value = None

        if spec.get("required") and (value is None or value == ""):
            errors.append(f"Required field '{field}' is missing or empty")

        # Only check enum if value is not None/empty (optional fields can be blank)
        if value is not None and value != "" and "enum" in spec:
            if value not in spec["enum"]:
                errors.append(f"Field '{field}' must be one of {spec['enum']}, got '{value}'")

        # Type validation (without coercion)
        if value is not None and value != "":
            expected_type = spec.get("type")
            if expected_type == "int" and not isinstance(value, int):
                if not (isinstance(value, str) and value.isdigit()):
                    errors.append(f"Field '{field}' must be int, got {type(value).__name__}")
            elif expected_type == "bool" and not isinstance(value, bool):
                errors.append(f"Field '{field}' must be bool, got {type(value).__name__}")

    return errors


def strip_help_fields(data: dict) -> dict:
    """Remove _help_* prefixed keys from data dict."""
    return {k: v for k, v in data.items() if not k.startswith("_help")}


def load_and_validate(data: dict, schema_name: str) -> tuple[dict, list[str]]:
    """Validate and coerce types. Returns (coerced_data, errors).

    This is the main entry point:
    1. Strips _help_* fields from input
    2. Validates against schema
    3. Coerces types (str -> int, str -> bool)
    4. Applies defaults

    Use this instead of validate_against_schema() when you need coerced values.
    """
    # Step 1: Strip _help fields from input BEFORE validation
    clean_data = strip_help_fields(data)

    # Step 2: Validate
    errors = validate_against_schema(clean_data, schema_name)
    if errors:
        return clean_data, errors

    # Step 3: Coerce types and apply defaults
    schema = SCHEMAS[schema_name]
    coerced = {}

    for field, spec in schema["fields"].items():
        value = clean_data.get(field)

        # Normalize empty to None
        if value == "":
            value = None

        # Apply defaults
        if value is None and "default" in spec:
            value = spec["default"]

        # Coerce types
        if value is not None:
            if spec.get("type") == "int" and isinstance(value, str):
                value = int(value)
            elif spec.get("type") == "bool" and isinstance(value, str):
                value = value.lower() in ("true", "1", "yes")

        coerced[field] = value

    return coerced, []
```

**MCP Server will use:**
```python
from tools.schemas import SCHEMAS, validate_against_schema

@mcp_tool("memory_add_task")
def add_task(name: str, summary: str, priority: str = "medium"):
    # Validate using same schema
    errors = validate_against_schema(
        {"name": name, "summary": summary, "priority": priority},
        "task"
    )
    if errors:
        return {"error": errors}
    
    # Call script...
```

---

## PR Breakdown (5 PRs)

| PR | Scope | Files | MCP Prep |
|----|-------|-------|----------|
| **PR1** | Fix `store_interaction.py` parser + `--file` | `store_interaction.py` | ✅ Enables MCP subprocess call |
| **PR2a** | Create `tools/schemas.py` | `tools/schemas.py` | ✅ Shared schema for MCP tools |
| **PR2b** | Create `tools/template_utils.py` | `tools/template_utils.py` | ✅ Reusable validation |
| **PR2c** | Wire `--template` into `prepare_sync_files.py` | `prepare_sync_files.py` | Neutral |
| **PR2d** | Module-level contract tests + docs | `tests/`, `LLM-INSTRUCTIONS.md` | ✅ Validates schema/function contracts |

---

## Testing Strategy (Updated for Module-Level)

**What tests validate:**
- Schema/template output can be consumed by script core logic correctly
- Type coercion and validation work as expected
- Generated templates pass their own validation when filled

**What tests do NOT validate:**
- Full CLI subprocess paths (would require adding new CLI flags)
- MCP server integration (separate future work)

| Test Type | What | Level |
|-----------|------|-------|
| Unit: `strip_help_fields()` | Nested structures, edge cases | Module |
| Unit: `validate_against_schema()` | Required fields, enums, types | Module |
| Unit: `load_and_validate()` | Type coercion | Module |
| Contract: template → function | Validated data works with graph functions | Module |
| Smoke: existing CLI | `query_memory.py --input-file` | CLI (exists) |
| Regression: inline args | `--user/--assistant` still work | CLI (exists) |

---

## Decisions Summary

| Decision | Choice | MCP Impact |
|----------|--------|------------|
| Parser: `--file` with `--project` | Required together | ✅ MCP server provides both |
| Project authority | CLI is king, template is docs | ✅ No conflict for MCP |
| Query template | Full API coverage | ✅ MCP tools get full API |
| Schema location | `tools/schemas.py` (shared) | ✅ Reused by MCP server |
| Tests | Module-level contract tests | ✅ Validates schema/function contracts (not full CLI/MCP) |
| Network posture | Localhost supported; private-subnet/VPN deployment supported from day one; deny public exposure | ✅ Safe baseline for shared private hosting |

---

## File Changes Summary

| File | Action | MCP Ready |
|------|--------|-----------|
| `tools/schemas.py` | CREATE | ✅ Shared with MCP |
| `tools/template_utils.py` | CREATE | ✅ Importable |
| `scripts/store_interaction.py` | MODIFY | ✅ --file works |
| `scripts/prepare_sync_files.py` | MODIFY | Neutral |
| `scripts/tasks.py` | COMMENT ONLY | ✅ Already compliant |
| `tests/test_template_contracts.py` | CREATE | ✅ Module-level contract tests |
| `LLM-INSTRUCTIONS.md` | MODIFY | Neutral |

---

## Success Criteria

- [ ] `store_interaction.py --project X --file tmp/interaction.json` works
- [ ] `tools/schemas.py` defines all input schemas
- [ ] Schema validation catches required field errors
- [ ] Module-level contract tests pass for all template → function paths
- [ ] Existing inline arg workflows unchanged
- [ ] **MCP server can import `tools/schemas.py` and call scripts**
- [ ] Network mode is documented as private/VPN-only from day one and rejects public-IP exposure
