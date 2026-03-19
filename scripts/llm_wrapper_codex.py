#!/usr/bin/env python3
"""
LLM Wrapper for Codex CLI

Standard interface for quality checking with Codex.
This wrapper uses `codex exec` non-interactively and writes normalized JSON
that `store_extraction.py` can consume directly.

Usage:
    python llm_wrapper_codex.py <questions_file> <answers_file> <prompt_file>

Arguments:
    questions_file - Path to JSON file with quality questions
    answers_file   - Path where answers should be written (JSON)
    prompt_file    - Path to markdown file with criteria/instructions

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
    normalize_quality_answers,
    read_json,
    read_text,
    run_codex,
    write_json,
)


QUALITY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["duplicates", "contradictions"],
    "properties": {
        "duplicates": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": True,
                "required": ["question_index", "is_duplicate", "reasoning"],
                "properties": {
                    "question_index": {"type": "integer", "minimum": 0},
                    "is_duplicate": {"type": "boolean"},
                    "duplicate_of_uuid": {"type": ["string", "null"]},
                    "duplicate_uuid": {"type": ["string", "null"]},
                    "duplicate_name": {"type": ["string", "null"]},
                    "confidence": {"type": ["number", "null"]},
                    "reasoning": {"type": "string"},
                    "reason": {"type": ["string", "null"]},
                },
            },
        },
        "contradictions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": True,
                "required": ["fact_index", "reasoning"],
                "properties": {
                    "fact_index": {"type": "integer", "minimum": 0},
                    "contradicted_fact_uuids": {
                        "type": ["array", "null"],
                        "items": {"type": "string"},
                    },
                    "contradicting_fact_uuid": {"type": ["string", "null"]},
                    "confidence": {"type": ["number", "null"]},
                    "reasoning": {"type": "string"},
                    "reason": {"type": ["string", "null"]},
                    "resolution": {"type": ["string", "null"]},
                    "resolution_details": {"type": ["string", "null"]},
                },
            },
        },
    },
}


def build_prompt(criteria: str, questions: dict) -> str:
    return f"""You are producing machine-readable quality review output for Portable LLM Memory.

Do not run shell commands.
Do not edit files.
Return only JSON matching the required schema.

You are given the repository's quality-check prompt and the full question set.
Answer the full question set in one JSON object with both arrays:
- "duplicates"
- "contradictions"

Normalize to the runtime schema expected by the repo:
- For duplicates, include question_index, is_duplicate, duplicate_uuid or duplicate_of_uuid when applicable, confidence, and reasoning.
- For contradictions, include fact_index, contradicted_fact_uuids when applicable, confidence, and reasoning.
- If a prompt section is irrelevant to a question type, still keep the other top-level array present.
- When there is no contradiction, use an empty contradicted_fact_uuids array.

Quality-check criteria:
{criteria}

Question JSON:
{questions}
"""


def main() -> None:
    if len(sys.argv) != 4:
        print("ERROR: Invalid arguments", file=sys.stderr)
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    questions_file, answers_file, prompt_file = sys.argv[1:4]

    if not os.path.exists(questions_file):
        print(f"ERROR: Questions file not found: {questions_file}", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(prompt_file):
        print(f"ERROR: Prompt file not found: {prompt_file}", file=sys.stderr)
        sys.exit(1)

    print(f"[1/3] Reading prompt from {prompt_file}...")
    criteria = read_text(prompt_file)

    print(f"[2/3] Reading questions from {questions_file}...")
    questions = read_json(questions_file)

    print("[3/3] Calling Codex CLI for quality review...")
    try:
        raw_result = run_codex(build_prompt(criteria, questions), QUALITY_SCHEMA)
        normalized = normalize_quality_answers(raw_result, questions)
        write_json(answers_file, normalized)
    except CodexWrapperError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
    except Exception as exc:
        print(f"ERROR: Failed to normalize Codex response: {exc}", file=sys.stderr)
        sys.exit(3)

    print(f"Success! Answers written to {answers_file}")
    sys.exit(0)


if __name__ == "__main__":
    main()
