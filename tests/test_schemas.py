"""
Unit tests for tools/schemas.py

Tests schema validation, type coercion, template generation,
and MCP parameter conversion.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tools.schemas import (
    SCHEMAS,
    get_schema,
    list_schemas,
    generate_template,
    strip_help_fields,
    validate_against_schema,
    coerce_types,
    load_and_validate,
    schema_to_mcp_parameters,
)


class TestSchemaBasics:
    """Test basic schema operations."""

    def test_list_schemas_returns_all(self):
        """All expected schemas are available."""
        schemas = list_schemas()
        assert "interaction" in schemas
        assert "task" in schemas
        assert "query" in schemas
        assert "recall" in schemas
        assert "extraction" in schemas

    def test_get_schema_exists(self):
        """get_schema returns valid schema dict."""
        schema = get_schema("task")
        assert "fields" in schema
        assert "cli_command" in schema
        assert "name" in schema["fields"]

    def test_get_schema_not_found(self):
        """get_schema raises KeyError for unknown schema."""
        with pytest.raises(KeyError):
            get_schema("nonexistent")


class TestTemplateGeneration:
    """Test template generation."""

    def test_generate_template_with_help(self):
        """Template includes _help fields when requested."""
        template = generate_template("task", include_help=True)
        assert "_help" in template
        assert "_help_name" in template
        assert "name" in template

    def test_generate_template_without_help(self):
        """Template excludes _help fields when not requested."""
        template = generate_template("task", include_help=False)
        assert "_help" not in template
        assert "_help_name" not in template
        assert "name" in template

    def test_generate_template_defaults(self):
        """Template has correct default values."""
        template = generate_template("task", include_help=False)
        assert template["priority"] == "medium"  # default from schema
        assert template["name"] == ""  # required str, no default

    def test_generate_template_all_schemas(self):
        """All schemas can generate templates without error."""
        for schema_name in list_schemas():
            template = generate_template(schema_name, include_help=True)
            assert isinstance(template, dict)


class TestStripHelpFields:
    """Test _help field stripping."""

    def test_strip_help_removes_prefixed(self):
        """Removes all _help* keys."""
        data = {
            "_help": "Some help",
            "_help_name": "Name help",
            "name": "Test",
            "summary": "A summary",
        }
        result = strip_help_fields(data)
        assert "_help" not in result
        assert "_help_name" not in result
        assert result["name"] == "Test"
        assert result["summary"] == "A summary"

    def test_strip_help_empty_dict(self):
        """Empty dict returns empty dict."""
        assert strip_help_fields({}) == {}


class TestValidation:
    """Test schema validation."""

    def test_validate_task_valid(self):
        """Valid task data passes validation."""
        data = {"name": "Test Task", "summary": "A test", "priority": "high"}
        errors = validate_against_schema(data, "task")
        assert errors == []

    def test_validate_task_missing_required(self):
        """Missing required field fails validation."""
        data = {"summary": "A test"}
        errors = validate_against_schema(data, "task")
        assert any("name" in e for e in errors)

    def test_validate_task_invalid_enum(self):
        """Invalid enum value fails validation."""
        data = {"name": "Test", "summary": "A test", "priority": "urgent"}
        errors = validate_against_schema(data, "task")
        assert any("priority" in e for e in errors)

    def test_validate_task_empty_string_required(self):
        """Empty string for required field fails validation."""
        data = {"name": "", "summary": "A test"}
        errors = validate_against_schema(data, "task")
        assert any("name" in e for e in errors)

    def test_validate_query_all_optional(self):
        """Query with only optional fields passes."""
        data = {"search": "test query"}
        errors = validate_against_schema(data, "query")
        assert errors == []

    def test_validate_query_direction_enum(self):
        """Query direction validates enum values."""
        for valid in ["incoming", "outgoing", "both"]:
            data = {"direction": valid}
            errors = validate_against_schema(data, "query")
            assert errors == [], f"Failed for direction={valid}"

        data = {"direction": "sideways"}
        errors = validate_against_schema(data, "query")
        assert any("direction" in e for e in errors)

    def test_validate_int_type(self):
        """Integer fields accept int or numeric string."""
        # Actual int
        data = {"search": "test", "limit": 25}
        errors = validate_against_schema(data, "query")
        assert errors == []

        # Numeric string (allowed, will be coerced)
        data = {"search": "test", "limit": "25"}
        errors = validate_against_schema(data, "query")
        assert errors == []

        # Non-numeric string
        data = {"search": "test", "limit": "many"}
        errors = validate_against_schema(data, "query")
        assert any("limit" in e for e in errors)


class TestTypeCoercion:
    """Test type coercion."""

    def test_coerce_int_from_string(self):
        """String integers are coerced to int."""
        data = {"search": "test", "limit": "25"}
        result = coerce_types(data, "query")
        assert result["limit"] == 25
        assert isinstance(result["limit"], int)

    def test_coerce_bool_from_string(self):
        """String booleans are coerced to bool."""
        data = {"start": "2026-03-01", "end": "2026-03-15", "hide_time": "true"}
        result = coerce_types(data, "recall")
        assert result["hide_time"] is True

    def test_coerce_applies_defaults(self):
        """Missing optional fields get defaults."""
        data = {"search": "test"}
        result = coerce_types(data, "query")
        assert result["limit"] == 50  # default
        assert result["direction"] == "both"  # default

    def test_coerce_empty_to_none(self):
        """Empty strings become None."""
        data = {"search": "", "entity": ""}
        result = coerce_types(data, "query")
        assert result["search"] is None
        assert result["entity"] is None


class TestLoadAndValidate:
    """Test combined load_and_validate function."""

    def test_load_and_validate_strips_help(self):
        """_help fields are stripped before validation."""
        data = {
            "_help": "Help text",
            "_help_name": "Name help",
            "name": "Test",
            "summary": "A test",
        }
        result, errors = load_and_validate(data, "task")
        assert errors == []
        assert "_help" not in result
        assert result["name"] == "Test"

    def test_load_and_validate_valid(self):
        """Valid data returns coerced data with no errors."""
        data = {"name": "Test", "summary": "A test", "priority": "low"}
        result, errors = load_and_validate(data, "task")
        assert errors == []
        assert result["name"] == "Test"
        assert result["priority"] == "low"

    def test_load_and_validate_invalid(self):
        """Invalid data returns errors."""
        data = {"summary": "Missing name"}
        result, errors = load_and_validate(data, "task")
        assert len(errors) > 0
        assert any("name" in e for e in errors)

    def test_load_and_validate_coerces(self):
        """Valid data is coerced."""
        data = {"search": "test", "limit": "100"}
        result, errors = load_and_validate(data, "query")
        assert errors == []
        assert result["limit"] == 100
        assert isinstance(result["limit"], int)


class TestMCPParameters:
    """Test MCP parameter schema generation."""

    def test_mcp_params_structure(self):
        """Generated params have correct MCP structure."""
        params = schema_to_mcp_parameters("task")
        assert params["type"] == "object"
        assert "properties" in params
        assert "required" in params

    def test_mcp_params_required_fields(self):
        """Required fields are listed in required array."""
        params = schema_to_mcp_parameters("task")
        assert "name" in params["required"]
        assert "summary" in params["required"]
        assert "priority" not in params["required"]  # has default

    def test_mcp_params_types(self):
        """Field types are mapped correctly."""
        params = schema_to_mcp_parameters("query")
        assert params["properties"]["search"]["type"] == "string"
        assert params["properties"]["limit"]["type"] == "integer"

    def test_mcp_params_enums(self):
        """Enum fields include enum values."""
        params = schema_to_mcp_parameters("task")
        assert "enum" in params["properties"]["priority"]
        assert "high" in params["properties"]["priority"]["enum"]

    def test_mcp_params_defaults(self):
        """Default values are included."""
        params = schema_to_mcp_parameters("task")
        assert params["properties"]["priority"]["default"] == "medium"

    def test_mcp_params_descriptions(self):
        """Help text becomes description."""
        params = schema_to_mcp_parameters("task")
        assert "description" in params["properties"]["name"]

    def test_mcp_params_all_schemas(self):
        """All schemas can generate MCP params."""
        for schema_name in list_schemas():
            params = schema_to_mcp_parameters(schema_name)
            assert params["type"] == "object"
            assert isinstance(params["properties"], dict)

