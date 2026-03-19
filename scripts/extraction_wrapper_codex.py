#!/usr/bin/env python3
"""
Extraction Wrapper for Codex CLI

Standard interface for entity/fact extraction with Codex.
This wrapper uses `codex exec` non-interactively and normalizes the result to
the extraction schema used by `extract_with_wrappers.py` and
`store_extraction.py`.

Usage:
    python extraction_wrapper_codex.py <input_file> <output_file> <extraction_type> <prompt_file>

Arguments:
    input_file       - Path to JSON file with conversation data
    output_file      - Path where extraction results should be written (JSON)
    extraction_type  - Type of extraction: "entities" or "facts"
    prompt_file      - Path to markdown file with extraction instructions

Environment:
    CODEX_BIN                      - Codex executable name/path (default: codex)
    CODEX_MODEL                    - Optional model override for `codex exec`
    CODEX_PROFILE                  - Optional Codex profile for `codex exec`
    CODEX_TIMEOUT_SECONDS          - Optional timeout in seconds (default: 600)
    CODEX_WRAPPER_MOCK_RESPONSE_FILE - Optional JSON file for offline testing

Exit codes:
    0 - Success
    1 - Invalid arguments or configuration error
    2 - Codex command failed
    3 - Invalid response from Codex
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from codex_wrapper_common import (
    CodexWrapperError,
    normalize_entities,
    normalize_facts,
    read_json,
    read_text,
    run_codex,
    write_json,
)


ENTITY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["entities"],
    "properties": {
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": True,
                "required": ["name"],
                "properties": {
                    "name": {"type": "string"},
                    "type": {"type": ["string", "null"]},
                    "entity_type": {"type": ["string", "null"]},
                    "summary": {"type": ["string", "null"]},
                    "priority": {"type": ["string", "null"]},
                    "status": {"type": ["string", "null"]},
                },
            },
        }
    },
}


FACT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["facts"],
    "properties": {
        "facts": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "source_entity",
                    "target_entity",
                    "relationship_type",
                    "fact",
                    "valid_at",
                    "invalid_at",
                ],
                "properties": {
                    "source_entity": {"type": "string"},
                    "target_entity": {"type": "string"},
                    "relationship_type": {"type": "string"},
                    "fact": {"type": "string"},
                    "valid_at": {"type": ["string", "null"]},
                    "invalid_at": {"type": ["string", "null"]},
                },
            },
        }
    },
}


def build_prompt(criteria: str, input_data: dict, extraction_type: str) -> str:
    output_rules = (
        'Return JSON with top-level key "entities". Use field "type" for entity type, not "entity_type".'
        if extraction_type == "entities"
        else 'Return JSON with top-level key "facts". Use exact entity names already present in the input "entities" list.'
    )

    return f"""You are producing machine-readable extraction output for Portable LLM Memory.

Do not run shell commands.
Do not edit files.
Return only JSON matching the required schema.

Follow the repository extraction instructions below, but obey these runtime compatibility rules first:
- {output_rules}
- Omit duplicates.
- Use null for missing temporal fields.
- Stay grounded in the provided JSON input only.

Extraction instructions:
{criteria}

Conversation/input JSON:
{input_data}
"""


def main() -> None:
    if len(sys.argv) != 5:
        print("ERROR: Invalid arguments", file=sys.stderr)
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    input_file, output_file, extraction_type, prompt_file = sys.argv[1:5]

    if extraction_type not in {"entities", "facts"}:
        print(f"ERROR: Invalid extraction_type: {extraction_type}", file=sys.stderr)
        print("       Must be 'entities' or 'facts'", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(input_file):
        print(f"ERROR: Input file not found: {input_file}", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(prompt_file):
        print(f"ERROR: Prompt file not found: {prompt_file}", file=sys.stderr)
        sys.exit(1)

    print(f"[1/3] Reading prompt from {prompt_file}...")
    criteria = read_text(prompt_file)

    print(f"[2/3] Reading input from {input_file}...")
    input_data = read_json(input_file)

    print(f"[3/3] Calling Codex CLI for {extraction_type} extraction...")
    try:
        schema = ENTITY_SCHEMA if extraction_type == "entities" else FACT_SCHEMA
        raw_result = run_codex(build_prompt(criteria, input_data, extraction_type), schema)
        normalized = normalize_entities(raw_result) if extraction_type == "entities" else normalize_facts(raw_result)
        write_json(output_file, normalized)
    except CodexWrapperError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
    except Exception as exc:
        print(f"ERROR: Failed to normalize Codex response: {exc}", file=sys.stderr)
        sys.exit(3)

    count = len(normalized[extraction_type])
    print(f"Success! Extracted {count} {extraction_type}")
    print(f"Output: {output_file}")
    sys.exit(0)


if __name__ == "__main__":
    main()
