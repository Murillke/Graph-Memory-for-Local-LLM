import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.validate_extraction import (
    CANONICAL_ENTITY_TYPES,
    COMMON_ENTITY_TYPE_SUGGESTIONS,
    ENTITY_TYPE_SYNONYMS,
    collect_validation_errors,
    is_valid_entity_type,
    normalize_entity_type,
)


REPO_ROOT = Path(__file__).resolve().parent.parent


def _extract_prompt_entity_types(prompt_text: str):
    lines = prompt_text.splitlines()
    collected = []
    capture = False

    for line in lines:
        if line.strip() == "## Entity Types":
            capture = True
            continue
        if capture and line.startswith("## "):
            break
        if capture and line.startswith("- **"):
            collected.append(line.split("**")[1])

    return collected


class EntityTypeStandardizationTests(unittest.TestCase):
    def test_canonical_types_accepted(self):
        for type_name in CANONICAL_ENTITY_TYPES:
            self.assertTrue(is_valid_entity_type(type_name))
            self.assertEqual(normalize_entity_type(type_name), type_name)

    def test_synonym_normalization(self):
        self.assertEqual(normalize_entity_type("Script"), "File")
        self.assertEqual(normalize_entity_type("Documentation"), "Document")
        self.assertEqual(normalize_entity_type("Bug Fix"), "Fix")
        self.assertEqual(normalize_entity_type("Workflow"), "Procedure")

    def test_case_insensitive_matching(self):
        self.assertEqual(normalize_entity_type("document"), "Document")
        self.assertEqual(normalize_entity_type("TECHNOLOGY"), "Technology")
        self.assertEqual(normalize_entity_type("bug fix"), "Fix")

    def test_unknown_type_rejected(self):
        self.assertFalse(is_valid_entity_type("RandomGarbage"))
        self.assertFalse(is_valid_entity_type("FooBar"))
        with self.assertRaises(ValueError):
            normalize_entity_type("Unknown", strict=True)

    def test_collect_validation_errors_separates_type_warnings(self):
        extraction = {
            "project_name": "test-project",
            "extraction_version": "test",
            "extraction_commit": "test",
            "extractions": [
                {
                    "interaction_uuid": "uuid-123",
                    "entities": [
                        {"name": "X", "type": "RandomType", "summary": "Y"},
                        {"name": "Workflow Alpha", "type": "Workflow", "summary": "Y"},
                    ],
                    "facts": [],
                }
            ],
        }

        fatal_errors, type_warnings = collect_validation_errors(extraction)
        self.assertEqual(fatal_errors, [])
        self.assertEqual(len(type_warnings), 2)
        self.assertTrue(any("unknown entity type 'RandomType'" in warning for warning in type_warnings))
        self.assertTrue(any("will normalize to 'Procedure'" in warning for warning in type_warnings))

    def test_prompt_types_match_canonical(self):
        from scripts.validate_extraction import EXTRACTION_ENTITY_TYPES
        prompt_text = (REPO_ROOT / "prompts" / "extract-entities.md").read_text(encoding="utf-8")
        prompt_types = _extract_prompt_entity_types(prompt_text)
        self.assertEqual(prompt_types, EXTRACTION_ENTITY_TYPES)

    def test_validate_tips_use_canonical_types(self):
        deprecated = {"Process", "Configuration", "Documentation", "Script", "Bug Fix", "Solution"}
        for bad_type in deprecated:
            self.assertNotIn(bad_type, COMMON_ENTITY_TYPE_SUGGESTIONS)

        for good_type in ("Project", "Technology", "Database", "Config", "Issue", "Fix", "Procedure"):
            self.assertIn(good_type, COMMON_ENTITY_TYPE_SUGGESTIONS)

    def test_no_deprecated_entity_types_in_workflow_docs(self):
        extract_doc = (REPO_ROOT / "extract.md").read_text(encoding="utf-8")
        self.assertIn("`Procedure`", extract_doc)
        self.assertIn("`Config`", extract_doc)
        self.assertIn("`Issue`", extract_doc)
        self.assertNotIn("Common entity types: `Feature`, `Bug`, `Task`, `File`, `Tool`, `Process`, `Event`, `Pattern`, `Concept`, `Configuration`", extract_doc)

        spec_doc = (REPO_ROOT / "docs" / "EXTRACTION-FORMAT-SPEC.md").read_text(encoding="utf-8")
        self.assertIn("Canonical source of truth", spec_doc)
        self.assertNotIn("You can use custom types", spec_doc)

    def test_synonym_table_covers_rollout_examples(self):
        expected = {
            "workflow": "Procedure",
            "process": "Procedure",
            "pipeline": "Procedure",
            "script": "File",
            "documentation": "Document",
            "configuration": "Config",
            "bug fix": "Fix",
            "technique": "Pattern",  # Pattern for approaches; Procedure is for executable steps
            "decision": "Event",  # Not ideal but captures "something that happened"
        }
        for synonym, canonical in expected.items():
            self.assertEqual(ENTITY_TYPE_SYNONYMS[synonym], canonical)


if __name__ == "__main__":
    unittest.main()
