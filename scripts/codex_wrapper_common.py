#!/usr/bin/env python3
"""Shared helpers for Codex-based wrapper scripts."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
WRAPPER_TMP_ROOT = REPO_ROOT / "tmp" / "codex_wrapper_tmp"


class CodexWrapperError(RuntimeError):
    """Raised when the Codex CLI wrapper cannot complete successfully."""


def read_text(path_str: str) -> str:
    with open(path_str, "r", encoding="utf-8") as f:
        return f.read()


def read_json(path_str: str) -> Any:
    with open(path_str, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path_str: str, payload: Any) -> None:
    with open(path_str, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def extract_json_payload(raw_text: str) -> Any:
    text = raw_text.strip()
    if not text:
        raise CodexWrapperError("Codex returned an empty response")

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fenced_match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if fenced_match:
        try:
            return json.loads(fenced_match.group(1))
        except json.JSONDecodeError as exc:
            raise CodexWrapperError(f"Codex returned invalid fenced JSON: {exc}") from exc

    raise CodexWrapperError("Codex did not return valid JSON")


def normalize_entities(result: dict[str, Any]) -> dict[str, Any]:
    entities = result.get("entities")
    if not isinstance(entities, list):
        raise CodexWrapperError("Entity extraction output must contain an 'entities' list")

    normalized = []
    for entity in entities:
        if not isinstance(entity, dict):
            raise CodexWrapperError("Each extracted entity must be an object")

        entity_type = entity.get("type") or entity.get("entity_type")
        normalized_entity = {
            "name": entity.get("name"),
            "type": entity_type,
            "summary": entity.get("summary", ""),
        }

        if "priority" in entity:
            normalized_entity["priority"] = entity["priority"]
        if "status" in entity:
            normalized_entity["status"] = entity["status"]

        normalized.append(normalized_entity)

    return {"entities": normalized}


def normalize_facts(result: dict[str, Any]) -> dict[str, Any]:
    facts = result.get("facts")
    if not isinstance(facts, list):
        raise CodexWrapperError("Fact extraction output must contain a 'facts' list")

    normalized = []
    for fact in facts:
        if not isinstance(fact, dict):
            raise CodexWrapperError("Each extracted fact must be an object")

        normalized.append(
            {
                "source_entity": fact.get("source_entity"),
                "target_entity": fact.get("target_entity"),
                "relationship_type": fact.get("relationship_type"),
                "fact": fact.get("fact"),
                "valid_at": fact.get("valid_at"),
                "invalid_at": fact.get("invalid_at"),
            }
        )

    return {"facts": normalized}


def normalize_quality_answers(result: dict[str, Any], questions: dict[str, Any]) -> dict[str, Any]:
    duplicate_questions = questions.get("duplicates", [])
    contradiction_questions = questions.get("contradictions", [])

    duplicate_answers = result.get("duplicates", [])
    contradiction_answers = result.get("contradictions", [])

    if not isinstance(duplicate_answers, list) or not isinstance(contradiction_answers, list):
        raise CodexWrapperError("Quality output must contain 'duplicates' and 'contradictions' lists")

    duplicate_uuid_to_name = {}
    for question in duplicate_questions:
        for candidate in question.get("candidates", []):
            uuid = candidate.get("uuid")
            name = candidate.get("name")
            if uuid and name:
                duplicate_uuid_to_name[uuid] = name

    normalized_duplicates = []
    for item in duplicate_answers:
        if not isinstance(item, dict):
            raise CodexWrapperError("Each duplicate answer must be an object")

        question_index = item.get("question_index")
        question = (
            duplicate_questions[question_index]
            if isinstance(question_index, int) and 0 <= question_index < len(duplicate_questions)
            else {}
        )
        duplicate_uuid = item.get("duplicate_uuid") or item.get("duplicate_of_uuid")
        duplicate_name = item.get("duplicate_name") or duplicate_uuid_to_name.get(duplicate_uuid)

        normalized_duplicates.append(
            {
                "new_entity_name": item.get("new_entity_name")
                or question.get("new_entity", {}).get("name"),
                "is_duplicate": bool(item.get("is_duplicate")),
                "duplicate_name": duplicate_name,
                "duplicate_uuid": duplicate_uuid,
                "confidence": item.get("confidence"),
                "reason": item.get("reason") or item.get("reasoning", ""),
            }
        )

    normalized_contradictions = []
    for item in contradiction_answers:
        if not isinstance(item, dict):
            raise CodexWrapperError("Each contradiction answer must be an object")

        contradicted_fact_uuids = item.get("contradicted_fact_uuids")
        if contradicted_fact_uuids is None:
            single_uuid = item.get("contradicting_fact_uuid")
            contradicted_fact_uuids = [single_uuid] if single_uuid else []
        elif not isinstance(contradicted_fact_uuids, list):
            contradicted_fact_uuids = [contradicted_fact_uuids]

        normalized_contradictions.append(
            {
                "fact_index": item.get("fact_index"),
                "contradicted_fact_uuids": [uuid for uuid in contradicted_fact_uuids if uuid],
                "confidence": item.get("confidence"),
                "reason": item.get("reason") or item.get("reasoning", ""),
                "resolution": item.get("resolution"),
                "resolution_details": item.get("resolution_details"),
            }
        )

    return {
        "duplicates": normalized_duplicates,
        "contradictions": normalized_contradictions,
    }


def run_codex(prompt_text: str, schema: dict[str, Any]) -> Any:
    mock_response_file = os.getenv("CODEX_WRAPPER_MOCK_RESPONSE_FILE")
    if mock_response_file:
        return read_json(mock_response_file)

    codex_bin = os.getenv("CODEX_BIN", "codex")
    resolved_codex_bin = shutil.which(codex_bin)
    if resolved_codex_bin is None:
        raise CodexWrapperError(
            f"Codex CLI not found: {codex_bin}. Set CODEX_BIN if the executable has a different name."
        )

    timeout_seconds = int(os.getenv("CODEX_TIMEOUT_SECONDS", "600"))
    model = os.getenv("CODEX_MODEL")
    profile = os.getenv("CODEX_PROFILE")

    WRAPPER_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    temp_dir = WRAPPER_TMP_ROOT / f"codex-wrapper-{uuid.uuid4().hex[:12]}"
    temp_dir.mkdir(parents=True, exist_ok=False)
    try:
        temp_path = Path(temp_dir)
        schema_path = temp_path / "schema.json"
        response_path = temp_path / "response.json"
        schema_path.write_text(json.dumps(schema, indent=2), encoding="utf-8")

        cmd = [
            resolved_codex_bin,
            "exec",
            "--sandbox",
            "read-only",
            "--skip-git-repo-check",
            "--color",
            "never",
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(response_path),
            "-C",
            str(REPO_ROOT),
            "-",
        ]

        if model:
            cmd[2:2] = ["-m", model]
        if profile:
            cmd[2:2] = ["-p", profile]

        result = subprocess.run(
            cmd,
            input=prompt_text,
            text=True,
            capture_output=True,
            cwd=REPO_ROOT,
            timeout=timeout_seconds,
        )

        if result.returncode != 0:
            details = "\n".join(
                part for part in [result.stdout.strip(), result.stderr.strip()] if part
            )
            raise CodexWrapperError(
                f"Codex exec failed with exit code {result.returncode}"
                + (f"\n{details[-4000:]}" if details else "")
            )

        if not response_path.exists():
            raise CodexWrapperError("Codex exec completed but did not produce an output message")

        return extract_json_payload(response_path.read_text(encoding="utf-8"))
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
