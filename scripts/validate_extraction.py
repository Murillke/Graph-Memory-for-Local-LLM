#!/usr/bin/env python3
"""
Validate extraction.json before storing.

This script checks:
- Required top-level and per-extraction fields
- Fact entity references are valid
- Supported source types
- Valid JSON structure
- Relationship types are valid (canonical, synonym, or inverse)

Usage:
    python scripts/validate_extraction.py --file tmp/extraction.json
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add parent directory to path for schema imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from schema.relationship_types import is_valid_relationship_type, get_canonical_type


def safe_print(*args, **kwargs):
    """Print with fallback for encoding issues on Windows."""
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        # Fallback: replace problematic characters
        text = " ".join(str(a) for a in args)
        print(text.encode('ascii', 'replace').decode('ascii'), **kwargs)


VALIDATE_EXAMPLES = """
Examples:
  # Validate extraction file
  python scripts/validate_extraction.py --file tmp/extraction_2026-03-13_15-00-00.json

  # Validate with project name check
  python scripts/validate_extraction.py --file tmp/extraction.json --project llm_memory

Note: Run this BEFORE store_extraction.py to catch schema errors early.
"""


class ValidateArgumentParser(argparse.ArgumentParser):
    """Custom parser that prints examples on error."""
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: error: {message}\n{VALIDATE_EXAMPLES}")


def load_extraction_data(extraction_file: Path) -> Dict[str, Any]:
    """Load extraction JSON from disk."""
    with open(extraction_file, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_source_id_field(source_type: str) -> str:
    return "source_uuid" if source_type == "external_document" else "interaction_uuid"


# Entity types available for extraction (match prompts/extract-entities.md)
EXTRACTION_ENTITY_TYPES = [
    "Person",
    "Organization",
    "Project",
    "Technology",
    "Platform",
    "Service",
    "API",
    "Tool",
    "Database",
    "File",
    "Document",
    "Config",
    "Schema",
    "Template",
    "Test",
    "Concept",
    "Pattern",
    "Antipattern",
    "Principle",
    "Task",
    "Feature",
    "Bug",
    "Issue",
    "Fix",
    "Event",
    "Procedure",
    "ProcedureStep",
    "SyncBatch",
]

# System-only types (not for user extraction, created programmatically)
SYSTEM_ENTITY_TYPES = [
    "SecurityViolation",
    "AuthorshipClaim",
]

# All valid entity types
CANONICAL_ENTITY_TYPES = EXTRACTION_ENTITY_TYPES + SYSTEM_ENTITY_TYPES

ENTITY_TYPE_SYNONYMS = {
    "doc": "Document",
    "spec": "Document",
    "plan": "Document",
    "guide": "Document",
    "rfc": "Document",
    "documentation": "Document",
    "configuration": "Config",
    "problem": "Issue",
    "error": "Bug",
    "defect": "Bug",
    "enhancement": "Feature",
    "improvement": "Feature",
    "todo": "Task",
    "action": "Task",
    "finding": "Issue",
    "solution": "Fix",
    "bug fix": "Fix",
    "library": "Technology",
    "framework": "Technology",
    "language": "Technology",
    "package": "Technology",
    "endpoint": "API",
    "script": "File",
    "module": "File",
    "architecture": "Pattern",
    "technique": "Pattern",
    "decision": "Event",
    "testclass": "Test",
    "workflow": "Procedure",
    "process": "Procedure",
    "pipeline": "Procedure",
}

_CANONICAL_ENTITY_TYPES_BY_KEY = {
    entity_type.lower(): entity_type for entity_type in CANONICAL_ENTITY_TYPES
}

COMMON_ENTITY_TYPE_SUGGESTIONS = (
    "Person, Organization, Project, Technology, Tool, Database, File, Document, "
    "Config, Concept, Pattern, Task, Bug, Issue, Fix, Procedure"
)


def get_canonical_entity_type(type_name: str) -> Optional[str]:
    """Return canonical entity type for a canonical or synonym input."""
    if not isinstance(type_name, str):
        return None

    normalized_key = type_name.strip().lower()
    if not normalized_key:
        return None

    canonical = _CANONICAL_ENTITY_TYPES_BY_KEY.get(normalized_key)
    if canonical:
        return canonical

    synonym_target = ENTITY_TYPE_SYNONYMS.get(normalized_key)
    if synonym_target:
        return synonym_target

    return None


def is_valid_entity_type(type_name: str) -> bool:
    """Return True for canonical or recognized synonym entity types."""
    return get_canonical_entity_type(type_name) is not None


def normalize_entity_type(type_name: str, strict: bool = False) -> str:
    """Normalize entity type to canonical casing."""
    canonical = get_canonical_entity_type(type_name)
    if canonical:
        return canonical
    if strict:
        raise ValueError(f"Unknown entity type: {type_name}")
    return type_name


def collect_validation_errors(
    data: Dict[str, Any],
    expected_project_name: Optional[str] = None
) -> Tuple[List[str], List[str]]:
    """Return (fatal_errors, type_warnings) without printing."""
    errors: List[str] = []
    type_warnings: List[str] = []

    required_fields = ["project_name", "extraction_version", "extraction_commit", "extractions"]
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing top-level field: {field}")

    if errors:
        return errors, type_warnings

    if expected_project_name and data.get("project_name") != expected_project_name:
        errors.append(
            f"Extraction project_name '{data.get('project_name')}' does not match "
            f"requested project '{expected_project_name}'"
        )

    source_type = data.get("source_type", "conversation")
    if source_type not in ("conversation", "external_document"):
        errors.append(f"Unsupported source_type '{source_type}'")
        return errors, type_warnings

    extractions = data.get("extractions")
    if not isinstance(extractions, list):
        errors.append("Top-level field 'extractions' must be a list")
        return errors, type_warnings

    source_id_field = _get_source_id_field(source_type)

    for i, extraction in enumerate(extractions, 1):
        prefix = f"Extraction {i}"

        if not isinstance(extraction, dict):
            errors.append(f"{prefix}: must be an object")
            continue

        if source_id_field not in extraction:
            errors.append(f"{prefix}: missing {source_id_field}")

        entities = extraction.get("entities")
        facts = extraction.get("facts")

        if entities is None:
            errors.append(f"{prefix}: missing entities list")
            continue
        if facts is None:
            errors.append(f"{prefix}: missing facts list")
            continue
        if not isinstance(entities, list):
            errors.append(f"{prefix}: entities must be a list")
            continue
        if not isinstance(facts, list):
            errors.append(f"{prefix}: facts must be a list")
            continue

        entity_names = set()
        for j, entity in enumerate(entities, 1):
            entity_prefix = f"{prefix} entity {j}"
            if not isinstance(entity, dict):
                errors.append(f"{entity_prefix}: must be an object")
                continue
            if "name" not in entity:
                errors.append(f"{entity_prefix}: missing name")
                continue
            if "type" not in entity:
                errors.append(f"{entity_prefix}: missing type")
            else:
                entity_type = entity.get("type")
                canonical_type = get_canonical_entity_type(entity_type)
                if canonical_type is None:
                    type_warnings.append(
                        f"{entity_prefix}: unknown entity type '{entity_type}'. "
                        f"Use one of the canonical types in scripts/validate_extraction.py."
                    )
                elif canonical_type != entity_type:
                    type_warnings.append(
                        f"{entity_prefix}: non-canonical entity type '{entity_type}' "
                        f"will normalize to '{canonical_type}' on storage."
                    )
            entity_names.add(entity["name"])

        for j, fact in enumerate(facts, 1):
            fact_prefix = f"{prefix} fact {j}"
            if not isinstance(fact, dict):
                errors.append(f"{fact_prefix}: must be an object")
                continue

            for field in ("source_entity", "target_entity", "relationship_type", "fact"):
                if field not in fact:
                    errors.append(f"{fact_prefix}: missing {field}")

            source = fact.get("source_entity")
            target = fact.get("target_entity")
            # Common entity types - see docs/PENDING-CRITICAL-ENTITY-TYPE-STANDARDIZATION-SPEC.md
            # Note: Process -> Procedure, Configuration -> Config after standardization lands
            if source and source not in entity_names:
                errors.append(
                    f"{fact_prefix}: source_entity '{source}' not found in entities list"
                )
                errors.append(
                    f"    [TIP] FIX: Add to entities: {{\"name\": \"{source}\", \"type\": \"<TYPE>\", \"summary\": \"...\"}}"
                )
                errors.append(
                    f"    [TIP] Canonical types: {COMMON_ENTITY_TYPE_SUGGESTIONS}"
                )
            if target and target not in entity_names:
                errors.append(
                    f"{fact_prefix}: target_entity '{target}' not found in entities list"
                )
                errors.append(
                    f"    [TIP] FIX: Add to entities: {{\"name\": \"{target}\", \"type\": \"<TYPE>\", \"summary\": \"...\"}}"
                )
                errors.append(
                    f"    [TIP] Canonical types: {COMMON_ENTITY_TYPE_SUGGESTIONS}"
                )

            # Validate relationship type
            rel_type = fact.get("relationship_type")
            if rel_type and not is_valid_relationship_type(rel_type):
                canonical = get_canonical_type(rel_type)
                if canonical:
                    # This shouldn't happen if is_valid works correctly, but just in case
                    pass
                else:
                    from schema.relationship_types import RELATIONSHIP_CATEGORIES
                    valid_types = []
                    for category, types in RELATIONSHIP_CATEGORIES.items():
                        valid_types.extend(types)
                    errors.append(
                        f"{fact_prefix}: unknown relationship type '{rel_type}'."
                    )
                    errors.append(
                        f"    [TIP] Valid types: {', '.join(sorted(valid_types))}"
                    )

    return errors, type_warnings


def validate_extraction(
    extraction_file: Path,
    expected_project_name: Optional[str] = None
) -> bool:
    """Validate extraction file and print results."""
    safe_print("=" * 80)
    safe_print("EXTRACTION VALIDATION")
    safe_print("=" * 80)
    safe_print(f"\nFile: {extraction_file}")

    try:
        data = load_extraction_data(extraction_file)
    except json.JSONDecodeError as e:
        safe_print(f"\nINVALID JSON: {e}")
        return False
    except Exception as e:
        safe_print(f"\nERROR reading file: {e}")
        return False

    errors, type_warnings = collect_validation_errors(
        data,
        expected_project_name=expected_project_name,
    )

    if errors:
        safe_print("\nVALIDATION FAILED")
        for error in errors:
            safe_print(f"  - {error}")
        safe_print(f"\n{'=' * 80}")
        safe_print("Fix errors above before storing")
        safe_print("=" * 80)
        return False

    if type_warnings:
        safe_print("\nTYPE WARNINGS")
        for warning in type_warnings:
            safe_print(f"  - {warning}")
        safe_print("  - Storage owns enforcement. Unknown types may be rejected there in strict mode.")

    safe_print("\nValid JSON structure")
    safe_print(f"   Project: {data['project_name']}")
    safe_print(f"   Version: {data['extraction_version']}")
    safe_print(f"   Source type: {data.get('source_type', 'conversation')}")
    safe_print(f"   Extractions: {len(data['extractions'])}")
    safe_print(f"\n{'=' * 80}")
    safe_print("VALIDATION PASSED - Extraction is valid")
    safe_print("=" * 80)
    return True


def main():
    parser = ValidateArgumentParser(
        description="Validate extraction.json before storing",
        epilog=VALIDATE_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--file", required=True, help="Path to extraction.json")
    parser.add_argument("--project", help="Expected project name")

    args = parser.parse_args()

    extraction_file = Path(args.file)
    if not extraction_file.exists():
        safe_print(f"File not found: {args.file}")
        sys.exit(1)

    is_valid = validate_extraction(extraction_file, expected_project_name=args.project)
    sys.exit(0 if is_valid else 1)


if __name__ == "__main__":
    main()
