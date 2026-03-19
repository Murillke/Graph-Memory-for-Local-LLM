"""
Shared schemas for templates, CLI validation, and MCP tools.

This module provides:
- Schema definitions for all structured inputs (interactions, tasks, queries, etc.)
- Template generation for agent workflows
- Validation with type coercion
- Shared between CLI scripts and future MCP server

DESIGN NOTES:
- Project is NOT included in template "fields" because CLI --project is authoritative.
- Templates are "payload only" - project is passed via CLI --project flag.
- MCP tools receive project as a separate parameter, not in the payload.
- This avoids dual-authority conflicts with config.py mismatch guards.
"""

from typing import Dict, Any, List, Tuple, Optional


SCHEMAS: Dict[str, Dict[str, Any]] = {
    "interaction": {
        "description": "Store a conversation exchange",
        "project_source": "cli",  # --project flag, NOT in payload
        "fields": {
            "user": {"type": "str", "required": True, "help": "User's message"},
            "assistant": {"type": "str", "required": True, "help": "Assistant's response"},
            "fidelity": {
                "type": "str",
                "required": False,
                "default": "summary",
                "enum": ["summary", "paraphrased", "reconstructed", "llm-state"],
                "help": "How accurately the exchange was captured",
            },
        },
        "cli_command": "store_interaction.py --project {project} --file {file}",
    },
    "task": {
        "description": "Create a new task",
        "project_source": "cli",
        "fields": {
            "name": {"type": "str", "required": True, "help": "Short task name"},
            "summary": {"type": "str", "required": True, "help": "Detailed description"},
            "priority": {
                "type": "str",
                "required": False,
                "default": "medium",
                "enum": ["high", "medium", "low"],
                "help": "Task priority",
            },
        },
        "cli_command": "tasks.py --project {project} --add-file {file}",
    },
    "query": {
        "description": "Query the memory graph",
        "project_source": "cli",
        "fields": {
            "search": {"type": "str", "required": False, "help": "Semantic search term"},
            "entity": {"type": "str", "required": False, "help": "Entity name to look up"},
            "type": {"type": "str", "required": False, "help": "Relationship type filter"},
            "limit": {"type": "int", "required": False, "default": 50, "help": "Max results"},
            "label": {"type": "str", "required": False, "help": "Entity label filter"},
            "entity_uuid": {"type": "str", "required": False, "help": "Entity UUID"},
            "facts": {"type": "str", "required": False, "help": "Search facts by text"},
            "procedure": {"type": "str", "required": False, "help": "Procedure name"},
            "search_procedures": {"type": "str", "required": False, "help": "Search procedures by text"},
            "direction": {
                "type": "str",
                "required": False,
                "enum": ["incoming", "outgoing", "both"],
                "default": "both",
                "help": "Relationship direction",
            },
            "last": {"type": "int", "required": False, "help": "Get last N entities"},
        },
        "cli_command": "query_memory.py --project {project} --input-file {file}",
    },
    "recall": {
        "description": "Time-based memory recall",
        "project_source": "cli",
        "fields": {
            "start": {"type": "str", "required": True, "help": "Start date/time (ISO format)"},
            "end": {"type": "str", "required": True, "help": "End date/time (ISO format)"},
            "entity": {"type": "str", "required": False, "help": "Focus on specific entity"},
            "limit": {"type": "int", "required": False, "default": 50, "help": "Max entities per day"},
            "hide_time": {"type": "bool", "required": False, "default": False, "help": "Hide timestamps"},
            "hide_task_activity": {"type": "bool", "required": False, "default": False},
        },
        "cli_command": "recall.py --project {project} --start {start} --end {end}",
    },
    "extraction": {
        "description": "Knowledge extraction payload",
        "project_source": "cli",
        "fields": {
            "interaction_uuid": {"type": "str", "required": True, "help": "Source interaction UUID"},
            "entities": {"type": "list", "required": True, "help": "List of entity objects"},
            "facts": {"type": "list", "required": False, "default": [], "help": "List of fact objects"},
        },
        "cli_command": "store_extraction.py --project {project} --extraction-file {file}",
    },
}


def get_schema(name: str) -> Dict[str, Any]:
    """Get schema by name. Raises KeyError if not found."""
    return SCHEMAS[name]


def list_schemas() -> List[str]:
    """List all available schema names."""
    return list(SCHEMAS.keys())


def generate_template(schema_name: str, include_help: bool = True) -> Dict[str, Any]:
    """
    Generate a template dict from schema.
    
    Args:
        schema_name: Name of the schema
        include_help: Whether to include _help fields
        
    Returns:
        Template dict with default/empty values
    """
    schema = SCHEMAS[schema_name]
    template: Dict[str, Any] = {}

    if include_help:
        template["_help"] = f"Run: python scripts/{schema['cli_command']}"

    for field, spec in schema["fields"].items():
        if include_help and "help" in spec:
            template[f"_help_{field}"] = spec["help"]

        # Set default or empty value based on type
        if "default" in spec:
            template[field] = spec["default"]
        elif spec["type"] == "bool":
            template[field] = False
        elif spec["type"] == "int":
            template[field] = None
        elif spec["type"] == "list":
            template[field] = []
        else:
            template[field] = ""

    return template


def strip_help_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    """Remove _help_* prefixed keys from data dict."""
    return {k: v for k, v in data.items() if not k.startswith("_help")}


def validate_against_schema(data: Dict[str, Any], schema_name: str) -> List[str]:
    """
    Validate data against schema. Returns list of errors (no coercion).

    Args:
        data: Input data dict (should have _help fields stripped)
        schema_name: Name of the schema to validate against

    Returns:
        List of error messages, empty if valid
    """
    schema = SCHEMAS[schema_name]
    errors: List[str] = []

    for field, spec in schema["fields"].items():
        value = data.get(field)

        # Normalize empty strings to None for optional fields
        if value == "" and not spec.get("required"):
            value = None

        # Check required fields
        if spec.get("required") and (value is None or value == ""):
            errors.append(f"Required field '{field}' is missing or empty")
            continue

        # Skip further validation if value is None/empty (optional)
        if value is None or value == "":
            continue

        # Enum validation
        if "enum" in spec and value not in spec["enum"]:
            errors.append(f"Field '{field}' must be one of {spec['enum']}, got '{value}'")

        # Type validation (without coercion)
        expected_type = spec.get("type")
        if expected_type == "int":
            if not isinstance(value, int):
                if not (isinstance(value, str) and value.lstrip("-").isdigit()):
                    errors.append(f"Field '{field}' must be int, got {type(value).__name__}")
        elif expected_type == "bool":
            if not isinstance(value, bool):
                if not (isinstance(value, str) and value.lower() in ("true", "false", "1", "0")):
                    errors.append(f"Field '{field}' must be bool, got {type(value).__name__}")
        elif expected_type == "list":
            if not isinstance(value, list):
                errors.append(f"Field '{field}' must be list, got {type(value).__name__}")

    return errors


def coerce_types(data: Dict[str, Any], schema_name: str) -> Dict[str, Any]:
    """
    Coerce data types according to schema and apply defaults.

    Args:
        data: Input data dict (should be validated first)
        schema_name: Name of the schema

    Returns:
        New dict with coerced types and defaults applied
    """
    schema = SCHEMAS[schema_name]
    coerced: Dict[str, Any] = {}

    for field, spec in schema["fields"].items():
        value = data.get(field)

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

    return coerced


def load_and_validate(
    data: Dict[str, Any], schema_name: str
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Validate and coerce types. Main entry point for schema processing.

    Steps:
    1. Strips _help_* fields from input
    2. Validates against schema
    3. Coerces types (str -> int, str -> bool)
    4. Applies defaults

    Args:
        data: Input data dict (may contain _help fields)
        schema_name: Name of the schema

    Returns:
        Tuple of (coerced_data, errors)
        If errors is non-empty, coerced_data may be incomplete
    """
    # Step 1: Strip _help fields
    clean_data = strip_help_fields(data)

    # Step 2: Validate
    errors = validate_against_schema(clean_data, schema_name)
    if errors:
        return clean_data, errors

    # Step 3 & 4: Coerce types and apply defaults
    coerced = coerce_types(clean_data, schema_name)
    return coerced, []


def schema_to_mcp_parameters(schema_name: str) -> Dict[str, Any]:
    """
    Convert schema to MCP tool parameter specification.

    This generates the parameter schema that MCP tools use for
    input validation.

    Args:
        schema_name: Name of the schema

    Returns:
        MCP-compatible parameter specification dict
    """
    schema = SCHEMAS[schema_name]
    properties: Dict[str, Any] = {}
    required: List[str] = []

    for field, spec in schema["fields"].items():
        prop: Dict[str, Any] = {}

        # Map types
        type_map = {
            "str": "string",
            "int": "integer",
            "bool": "boolean",
            "list": "array",
        }
        prop["type"] = type_map.get(spec["type"], "string")

        # Add description
        if "help" in spec:
            prop["description"] = spec["help"]

        # Add enum
        if "enum" in spec:
            prop["enum"] = spec["enum"]

        # Add default
        if "default" in spec:
            prop["default"] = spec["default"]

        properties[field] = prop

        if spec.get("required"):
            required.append(field)

    return {
        "type": "object",
        "properties": properties,
        "required": required,
    }
