#!/usr/bin/env python3
"""
Store extracted entities and facts to the graph database.

This script takes extraction results (from Auggie) and stores them
in the graph database with cryptographic proofs.

Usage:
    python3 scripts/store_extraction.py \\
        --project "my-project" \\
        --extraction-file extraction_results.json

JSON Format:
    {
        "extractions": [
            {
                "interaction_uuid": "uuid-123",
                "entities": [
                    {"name": "React", "type": "Technology", "summary": "..."}
                ],
                "facts": [
                    {
                        "source_entity": "LadybugDB",
                        "target_entity": "Python",
                        "relationship_type": "BUILT_WITH",
                        "fact": "LadybugDB is built with Python"
                    }
                ]
            }
        ]
    }
"""

import sys
import os
import argparse
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tools.sql_db import SQLDatabase
from tools.graph_db import GraphDatabase
from tools.config import load_config
from tools.deduplication import find_duplicate_candidates_deterministic
from tools.contradiction import get_contradiction_detection_prompt
from tools.console_utils import safe_print, setup_console_encoding
from scripts.validate_extraction import (
    collect_validation_errors,
    load_extraction_data,
    normalize_entity_type,
)
from schema.relationship_types import normalize_fact
import hashlib
from typing import Dict, List, Tuple


def validate_quality_answers(questions_file: str, answers_file: str) -> Tuple[bool, List[str]]:
    """
    Validate that quality answers actually address the questions.

    Returns (is_valid, list_of_errors).
    """
    errors = []

    with open(questions_file, 'r', encoding='utf-8') as f:
        questions = json.load(f)
    with open(answers_file, 'r', encoding='utf-8') as f:
        answers = json.load(f)

    # 1. Correct top-level shape
    if not isinstance(answers.get('duplicates'), list):
        errors.append("Missing or invalid 'duplicates' array")
    if not isinstance(answers.get('contradictions'), list):
        errors.append("Missing or invalid 'contradictions' array")

    if errors:
        return False, errors

    # Get question lists
    q_dups = questions.get('duplicates', [])
    q_contras = questions.get('contradictions', [])

    # Early exit: if no questions exist, no validation needed
    if not q_dups and not q_contras:
        return True, []

    # 2. One answer per duplicate question, keyed by question_index (stable identity)
    q_dup_indices = set(range(len(q_dups)))  # Expected: 0, 1, 2, ... n-1
    a_dup_indices = {a.get('question_index') for a in answers.get('duplicates', [])}

    missing_dup = q_dup_indices - a_dup_indices
    if missing_dup:
        missing_names = [q_dups[i]['new_entity']['name'] for i in missing_dup if i < len(q_dups)]
        errors.append(f"Missing duplicate answers for question_index {missing_dup}: {missing_names}")

    extra_dup = a_dup_indices - q_dup_indices - {None}  # Exclude None from check
    if extra_dup:
        errors.append(f"Extra duplicate answers with invalid question_index: {extra_dup}")

    # 3. No duplicate question_index values in answers
    seen_dup_indices = set()
    for a in answers.get('duplicates', []):
        idx = a.get('question_index')
        if idx is not None and idx in seen_dup_indices:
            errors.append(f"Duplicate answer entry for question_index: {idx}")
        if idx is not None:
            seen_dup_indices.add(idx)

    # 4. Required fields when is_duplicate: true
    for a in answers.get('duplicates', []):
        if not isinstance(a.get('is_duplicate'), bool):
            errors.append(
                f"Missing explicit duplicate decision for question_index: {a.get('question_index')}"
            )
        if not isinstance(a.get('reasoning'), str) or not a.get('reasoning').strip():
            errors.append(
                f"Missing reasoning for duplicate question_index: {a.get('question_index')}"
            )
            errors.append(
                f"    [TIP] If duplicate: \"Same entity - already exists with matching description\""
            )
            errors.append(
                f"    [TIP] If not duplicate: \"Different concept - this describes X, existing describes Y\""
            )
        if a.get('is_duplicate') is True:
            if not a.get('duplicate_uuid') and not a.get('merge_with_uuid'):
                errors.append(
                    f"is_duplicate=true but no duplicate_uuid for question_index: {a.get('question_index')}"
                )

    # 5. One answer per contradiction question, keyed by fact_index (stable identity)
    q_contra_indices = {q['fact_index'] for q in q_contras}
    a_contra_indices = {a.get('fact_index') for a in answers.get('contradictions', [])}

    missing_contra = q_contra_indices - a_contra_indices
    if missing_contra:
        errors.append(f"Missing contradiction answers for fact_index: {missing_contra}")

    extra_contra = a_contra_indices - q_contra_indices - {None}
    if extra_contra:
        errors.append(f"Extra contradiction answers with invalid fact_index: {extra_contra}")

    # 5b. No duplicate fact_index values in contradiction answers
    seen_contra_indices = set()
    for a in answers.get('contradictions', []):
        idx = a.get('fact_index')
        if idx is not None and idx in seen_contra_indices:
            errors.append(f"Duplicate contradiction answer for fact_index: {idx}")
        if idx is not None:
            seen_contra_indices.add(idx)
        if not isinstance(a.get('reasoning'), str) or not a.get('reasoning').strip():
            errors.append(f"Missing reasoning for contradiction fact_index: {idx}")
            errors.append(
                f"    [TIP] If no contradiction: \"No existing facts about this relationship\""
            )
            errors.append(
                f"    [TIP] If contradiction: \"Contradicts fact-uuid-X which states the opposite\""
            )

    # 6. Staleness check - REQUIRE matching hash when questions exist
    q_hash = compute_questions_hash(questions_file)

    a_hash = answers.get('_questions_hash')

    # Hash is REQUIRED, not optional - missing/null hash = unanswered
    if not a_hash:
        errors.append(
            f"Missing _questions_hash in answers file. "
            f"Required value: '{q_hash}' (proves answers match current questions)"
        )
    elif a_hash != q_hash:
        errors.append(
            f"Stale answers: questions hash '{q_hash}' != answers hash '{a_hash}'. "
            f"Re-answer the current questions and set _questions_hash to '{q_hash}'"
        )

    return len(errors) == 0, errors


def compute_questions_hash(questions_file: str) -> str:
    """Compute the short hash used to bind answers to the current questions file."""
    with open(questions_file, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()[:12]


def build_quality_answers_template(questions: dict, questions_hash: str) -> dict:
    """Create a prefilled answers template that matches the current questions schema."""
    return {
        "_questions_hash": questions_hash,
        "_help_duplicates": "is_duplicate: bool, duplicate_uuid: entity-xxx|null, reasoning: string",
        "_help_contradictions": "contradicted_fact_uuids: [fact-xxx], reasoning: string",
        "duplicates": [
            {
                "question_index": index,
                "is_duplicate": False,
                "duplicate_uuid": None,
                "reasoning": "",
            }
            for index, _question in enumerate(questions.get("duplicates", []))
        ],
        "contradictions": [
            {
                "fact_index": question.get("fact_index"),
                "contradicted_fact_uuids": [],
                "reasoning": "",
            }
            for question in questions.get("contradictions", [])
        ],
    }


def ensure_quality_answers_template(questions_file: str, answers_file: str, questions: dict) -> tuple[str, bool]:
    """
    Ensure the answers file exists with the current schema.

    Returns the current questions hash and whether a template file was written.
    """
    questions_hash = compute_questions_hash(questions_file)
    template = build_quality_answers_template(questions, questions_hash)

    should_write_template = True
    if os.path.exists(answers_file):
        try:
            with open(answers_file, 'r', encoding='utf-8') as f:
                existing_answers = json.load(f)
            if existing_answers.get("_questions_hash") == questions_hash:
                should_write_template = False
        except (json.JSONDecodeError, OSError, TypeError):
            should_write_template = True

    if should_write_template:
        with open(answers_file, 'w', encoding='utf-8') as f:
            json.dump(template, f, indent=2)
            f.write("\n")

    return questions_hash, should_write_template


STORE_EXAMPLES = """
Examples:
  # Store extraction with quality review (recommended)
  python scripts/store_extraction.py --project llm_memory --extraction-file tmp/extraction_2026-03-13_15-00-00.json --require-quality-review --quality-answers-file tmp/quality-answers.json

  # Preview without storing
  python scripts/store_extraction.py --project llm_memory --extraction-file tmp/extraction.json --dry-run

  # With agent identity
  python scripts/store_extraction.py --project llm_memory --extraction-file tmp/extraction.json --require-quality-review --quality-answers-file tmp/quality-answers.json --agent auggie

Note: Always run validate_extraction.py FIRST.
      AI agents must NEVER use --i-am-a-human-and-i-want-to-skip-quality-checks.
      Entity type rollout defaults to warning mode; use --entity-type-enforcement strict to reject unknown types.
"""


class StoreArgumentParser(argparse.ArgumentParser):
    """Custom parser that prints examples on error."""
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: error: {message}\n{STORE_EXAMPLES}")


def show_task_summary(project_name: str, graph_db: GraphDatabase):
    """Show summary of tasks after extraction."""

    try:
        # Query all pending tasks
        result = graph_db.conn.execute("""
            MATCH (p:Project {name: $project_name})-[:HAS_ENTITY]->(e:Entity)
            WHERE e.labels CONTAINS 'Task'
              AND (e.status = 'pending' OR e.status IS NULL)
              AND e.deleted_at IS NULL
            RETURN e.name, e.priority, e.created_at
            ORDER BY e.created_at DESC
        """, {
            "project_name": project_name,
        })

        tasks = []
        while result.has_next():
            row = result.get_next()
            tasks.append({
                'name': row[0],
                'priority': row[1] or 'medium',
                'created_at': str(row[2]) if row[2] else ''
            })

        if not tasks:
            return

        # Find new tasks (created in last minute)
        from datetime import datetime, timedelta
        now = datetime.now()
        one_minute_ago = now - timedelta(minutes=1)

        new_tasks = []
        for task in tasks:
            if task['created_at']:
                try:
                    created = datetime.fromisoformat(task['created_at'].replace('Z', '+00:00'))
                    if created > one_minute_ago:
                        new_tasks.append(task)
                except:
                    pass

        if new_tasks:
            safe_print(f"\n{'='*80}")
            safe_print(f"NEW TASKS IDENTIFIED ({len(new_tasks)}):")
            safe_print(f"{'='*80}\n")

            for i, task in enumerate(new_tasks, 1):
                priority_label = f"[{task['priority'].upper()}]"
                safe_print(f"  {i}. {priority_label} {task['name']}")

            safe_print(f"\n{len(tasks)} pending tasks total")
            safe_print(f"\nRun: python scripts/tasks.py --project {project_name}")
            safe_print(f"{'='*80}\n")

    except Exception as e:
        # Silently ignore errors in task summary (non-critical feature)
        pass
from tools.source_chain import build_source_chain_from_interactions

# Setup console encoding for Windows
setup_console_encoding()


def generate_quality_questions(extractions, graph_db, project_name):
    """
    Generate quality check questions for duplicates and contradictions.

    Returns dict with questions for Auggie to analyze.
    """
    questions = {
        "duplicates": [],
        "contradictions": []
    }

    # Get all existing entities for this project
    existing_entities = graph_db.get_all_entities(project_name)

    # Get all existing facts for this project
    existing_facts = graph_db.get_all_facts(project_name)

    # Check each new entity for duplicates
    for extraction in extractions:
        for entity in extraction.get('entities', []):
            # Find duplicate candidates
            candidates = find_duplicate_candidates_deterministic(
                entity,
                existing_entities
            )

            if candidates:
                # Add question for Auggie
                questions["duplicates"].append({
                    "new_entity": {
                        "name": entity['name'],
                        "type": entity['type'],
                        "summary": entity.get('summary', '')
                    },
                    "candidates": [
                        {
                            "name": c[0]['name'],
                            "type": c[0].get('labels', ['Unknown'])[0] if c[0].get('labels') else 'Unknown',
                            "summary": c[0].get('summary', ''),
                            "uuid": c[0]['uuid'],
                            "similarity": c[1]
                        }
                        for c in candidates
                    ]
                })

    # Check each new fact for contradictions
    fact_index = 0
    for extraction in extractions:
        for fact in extraction.get('facts', []):
            # ENTITY FILTERING: Only include facts about the same entities
            # This reduces file size by ~90% and improves LLM accuracy
            source_entity = fact['source_entity']
            target_entity = fact['target_entity']

            relevant_facts = [
                f for f in existing_facts
                if (f.get('source_name', '') == source_entity or
                    f.get('target_name', '') == source_entity or
                    f.get('source_name', '') == target_entity or
                    f.get('target_name', '') == target_entity)
            ]

            # Format relevant facts for contradiction check
            existing_facts_formatted = [
                {
                    "source_entity": f.get('source_name', ''),
                    "target_entity": f.get('target_name', ''),
                    "relationship_type": f.get('relationship_name', ''),
                    "fact": f.get('fact', ''),
                    "valid_at": f.get('valid_at', ''),
                    "invalid_at": f.get('invalid_at', ''),
                    "uuid": f.get('uuid', '')
                }
                for f in relevant_facts
            ]

            # Add question for Auggie
            questions["contradictions"].append({
                "fact_index": fact_index,
                "new_fact": {
                    "source_entity": fact['source_entity'],
                    "target_entity": fact['target_entity'],
                    "relationship_type": fact['relationship_type'],
                    "fact": fact['fact']
                },
                "existing_facts": existing_facts_formatted,
                "stats": {
                    "total_facts_in_db": len(existing_facts),
                    "relevant_facts_checked": len(relevant_facts),
                    "reduction_percent": round((1 - len(relevant_facts) / max(len(existing_facts), 1)) * 100, 1)
                }
            })

            fact_index += 1

    return questions


def call_llm_for_quality_check(questions_file, answers_file, check_type, config):
    """
    Call configured LLM wrapper for quality checking.

    Uses the standard wrapper interface:
        wrapper_script <questions_file> <answers_file> <prompt_file>

    Args:
        questions_file: Path to JSON file with quality questions
        answers_file: Path where answers should be written
        check_type: Type of check ("duplicates" or "contradictions")
        config: Configuration dict with llm_wrapper and prompts

    Returns:
        True if successful, False otherwise
    """
    # Get wrapper script and prompt file from config
    wrapper_script = config['quality_check']['llm_wrapper']
    prompt_file = config['quality_check']['prompts'][check_type]

    if not isinstance(wrapper_script, str) or wrapper_script.strip() in {"", "null", "None"}:
        safe_print("[ERROR] No quality-check wrapper is configured.")
        safe_print("        YOU are the reviewer! Review the quality questions yourself:")
        safe_print("        1. Read the questions file (see path above)")
        safe_print("        2. Write your answers to the answers file")
        safe_print("        3. Rerun with --require-quality-review")
        safe_print("")
        safe_print("        DO NOT skip quality checks - this is your job!")
        return False

    safe_print(f"\n[AI] Calling LLM for {check_type} quality check...")
    safe_print(f"   Wrapper: {wrapper_script}")
    safe_print(f"   Prompt: {prompt_file}")
    safe_print(f"   Questions: {questions_file}")
    safe_print(f"   Answers: {answers_file}")

    # Check if answers file already exists
    if os.path.exists(answers_file):
        safe_print(f"[OK] Answers file already exists, using it.")
        return True

    # Validate wrapper script exists
    if not os.path.exists(wrapper_script):
        safe_print(f"[ERROR] LLM wrapper script not found: {wrapper_script}")
        safe_print(f"        Please check your configuration in mem.config.json")
        return False

    # Validate prompt file exists
    if not os.path.exists(prompt_file):
        safe_print(f"[ERROR] Prompt file not found: {prompt_file}")
        safe_print(f"        Please check your configuration in mem.config.json")
        return False

    # Call the wrapper script
    safe_print(f"\n   Calling wrapper script...")

    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, wrapper_script, questions_file, answers_file, prompt_file],
            capture_output=False,  # Let wrapper output show through
            text=True
        )

        if result.returncode != 0:
            safe_print(f"[ERROR] LLM wrapper failed with exit code {result.returncode}")
            return False

        # Verify answers file was created
        if not os.path.exists(answers_file):
            safe_print(f"[ERROR] LLM wrapper did not create answers file: {answers_file}")
            return False

        safe_print(f"[OK] Quality check complete!")
        return True

    except Exception as e:
        safe_print(f"[ERROR] Failed to call LLM wrapper: {e}")
        return False


def fail_preflight(message: str):
    """Exit with a concise preflight error."""
    safe_print(f"[ERROR] {message}")
    safe_print("        See sync.md for the extraction workflow.")
    sys.exit(1)


def ensure_parent_directory_exists(path_str: str, label: str):
    """Validate the parent directory for a configured path."""
    parent = Path(path_str).parent
    if not parent.exists():
        fail_preflight(f"{label} directory does not exist: {parent}")


def resolve_quality_artifact_path(config: dict, cli_value: Optional[str], config_value: str) -> str:
    """Resolve quality artifact paths without relying on repo-root magic files."""
    if cli_value:
        return cli_value

    configured_path = Path(config_value)
    if configured_path.is_absolute() or configured_path.parent != Path("."):
        return str(configured_path)

    return str(Path(config["paths"]["tmp_dir"]) / configured_path.name)


def classify_conversation_extractions(extractions, sql_db):
    """Split extractions into actionable and already-processed interaction groups."""
    actionable = []
    skipped = []
    errors = []

    for extraction in extractions:
        interaction_uuid = extraction["interaction_uuid"]
        interaction = sql_db.get_interaction_by_uuid(interaction_uuid)
        if not interaction:
            errors.append(f"Interaction not found in SQL database: {interaction_uuid}")
            continue

        if interaction.get("processed"):
            skipped.append(interaction_uuid)
            continue

        actionable.append(extraction)

    return actionable, skipped, errors


def find_task_event_reuse_candidate(
    sql_db: Optional[SQLDatabase],
    graph_db: GraphDatabase,
    project_name: str,
    entity_name: str,
    workflow_session_id: Optional[str],
    reference_timestamp: Optional[str],
) -> tuple[Optional[Dict[str, object]], Optional[str]]:
    """
    Find an authoritative task operation event for exact-name task reuse.

    Returns (event_row, warning_message). Any warning means the caller should
    fall back to normal duplicate-safe handling instead of trusting the event.
    """
    if not sql_db:
        return None, None

    try:
        event = sql_db.find_task_operation_event(
            project_name=project_name,
            task_name=entity_name,
            workflow_session_id=workflow_session_id,
            reference_timestamp=reference_timestamp,
        )
    except ValueError as exc:
        return None, str(exc)
    except Exception as exc:
        return None, f"Task operation event lookup failed for '{entity_name}': {exc}"

    if not event:
        return None, None

    task_uuid = event.get("task_uuid")
    if not task_uuid:
        return None, f"Task operation event for '{entity_name}' is missing task_uuid"

    canonical = graph_db.get_entity_by_uuid(task_uuid)
    if not canonical:
        return None, f"Task operation event for '{entity_name}' points to missing UUID {task_uuid}"

    if canonical.get("name") != entity_name:
        return None, (
            f"Task operation event for '{entity_name}' points to '{canonical.get('name')}', "
            f"not an exact-name match"
        )

    return event, None


def main():
    parser = StoreArgumentParser(
        description='Store extraction results to graph database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=STORE_EXAMPLES,
    )
    
    parser.add_argument('--project', required=True, help='Project name')
    parser.add_argument('--config', help='Path to config file (default: ./mem.config.json or MEM_CONFIG)')
    parser.add_argument('--extraction-file', required=True, help='JSON file with extraction results')
    parser.add_argument('--sql-db', help='Path to SQL database (default: from config)')
    parser.add_argument('--graph-db', help='Path to graph database (default: from config)')
    parser.add_argument('--extraction-version', default='1.0.0', help='Extraction version')
    parser.add_argument('--extraction-commit', default='manual', help='Extraction commit/source')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be stored without storing')
    parser.add_argument('--skip-quality-check', action='store_true', help=argparse.SUPPRESS)  # DEPRECATED - hidden from help
    parser.add_argument('--i-am-a-human-and-i-want-to-skip-quality-checks', action='store_true',
                        dest='human_skip_quality',
                        help='HUMAN-ONLY: Skip quality checks. AI agents must NEVER use this flag - do the review yourself!')
    parser.add_argument('--require-quality-review', action='store_true', help='Block until a quality answers file is provided')
    parser.add_argument('--quality-questions-file', help='File to save quality questions (default: from config/tmp dir)')
    parser.add_argument('--quality-answers-file', help='File to read quality answers (default: from config/tmp dir)')
    parser.add_argument(
        '--entity-type-enforcement',
        choices=('warn', 'strict'),
        default='warn',
        help='How to handle unknown entity types after normalization (default: warn)',
    )

    # Agent identity (for provenance tracking)
    parser.add_argument('--agent', dest='extracted_by_agent',
                       help='Agent name doing extraction (e.g., "codex", "auggie"). '
                            'Can also be set via LLM_AGENT_NAME env or extracted_by_agent in JSON.')
    parser.add_argument('--model', dest='extracted_by_model',
                       help='Model name (e.g., "o3", "claude-opus-4-20250514"). '
                            'Can also be set via LLM_AGENT_MODEL env or extracted_by_model in JSON.')

    args = parser.parse_args()

    resolved_config = load_config(
        project_name=args.project,
        cli_args={"sql_db": args.sql_db, "graph_db": args.graph_db, "config": args.config},
        config_path=args.config,
    )
    config = resolved_config.to_dict()
    args.graph_db = resolved_config.get_graph_db_path(args.project)
    args.sql_db = resolved_config.get_sql_db_path()
    args.quality_questions_file = resolve_quality_artifact_path(
        config,
        args.quality_questions_file,
        config["quality_check"]["questions_file"]
    )
    args.quality_answers_file = resolve_quality_artifact_path(
        config,
        args.quality_answers_file,
        config["quality_check"]["answers_file"]
    )

    # Handle deprecated --skip-quality-check flag
    if args.skip_quality_check:
        safe_print("[WARNING] --skip-quality-check is DEPRECATED!")
        safe_print("          If you are an AI agent: DO NOT skip quality checks - do the review yourself!")
        safe_print("          If you are a human and really need to skip: use --i-am-a-human-and-i-want-to-skip-quality-checks")
        safe_print("")
        fail_preflight("Use --i-am-a-human-and-i-want-to-skip-quality-checks if you really need to skip")

    if args.human_skip_quality and args.require_quality_review:
        fail_preflight("Cannot skip quality checks and require quality review at the same time")

    extraction_path = Path(args.extraction_file)
    if not extraction_path.exists():
        fail_preflight(f"Extraction file not found: {args.extraction_file}")

    ensure_parent_directory_exists(args.sql_db, "SQL database")
    ensure_parent_directory_exists(args.graph_db, "Graph database")
    ensure_parent_directory_exists(args.quality_questions_file, "Quality questions file")
    ensure_parent_directory_exists(args.quality_answers_file, "Quality answers file")

    try:
        data = load_extraction_data(extraction_path)
    except json.JSONDecodeError as e:
        fail_preflight(f"Extraction file contains invalid JSON: {e}")
    except Exception as e:
        fail_preflight(f"Failed to read extraction file: {e}")

    validation_errors, type_warnings = collect_validation_errors(
        data,
        expected_project_name=args.project,
    )
    if validation_errors:
        safe_print("[ERROR] Extraction validation failed:")
        for error in validation_errors:
            safe_print(f"        - {error}")
        safe_print("        Run scripts/validate_extraction.py --file <path> --project <project> for details.")
        sys.exit(1)

    if type_warnings:
        label = "[ERROR]" if args.entity_type_enforcement == "strict" else "[WARNING]"
        safe_print(f"{label} Entity type warnings detected:")
        for warning in type_warnings:
            safe_print(f"        - {warning}")
        if args.entity_type_enforcement == "strict":
            safe_print("        Re-run with canonical entity types or use --entity-type-enforcement warn during rollout.")
            sys.exit(1)
        safe_print("        Continuing in warn mode; storage will normalize recognized synonyms to canonical labels.")

    extractions = data.get('extractions', [])
    workflow_session_id = data.get('workflow_session_id')
    if not extractions:
        fail_preflight("No extractions found in file")

    # Resolve agent identity: CLI args > JSON file > environment variables
    args.extracted_by_agent = (
        args.extracted_by_agent or
        data.get('extracted_by_agent') or
        os.environ.get('LLM_AGENT_NAME')
    )
    args.extracted_by_model = (
        args.extracted_by_model or
        data.get('extracted_by_model') or
        os.environ.get('LLM_AGENT_MODEL')
    )

    safe_print(f"\n{'='*60}")
    safe_print(f"[DATA] Storing extraction results for project '{args.project}'")
    safe_print(f"{'='*60}\n")

    if args.extracted_by_agent:
        safe_print(f"[INFO] Extractor: {args.extracted_by_agent} ({args.extracted_by_model or 'unknown model'})\n")

    source_type = data.get('source_type', 'conversation')
    sql_db = None
    skipped_interactions = []

    if source_type == 'conversation':
        if not Path(args.sql_db).exists():
            fail_preflight(f"SQL database file not found: {args.sql_db}")

        sql_db = SQLDatabase(args.sql_db)
        extractions, skipped_interactions, interaction_errors = classify_conversation_extractions(extractions, sql_db)
        if interaction_errors:
            safe_print("[ERROR] Extraction references missing interactions:")
            for error in interaction_errors:
                safe_print(f"        - {error}")
            sys.exit(1)

        if skipped_interactions:
            safe_print(f"[SKIP] Skipping {len(skipped_interactions)} already-processed interactions")

    if not extractions:
        safe_print("[OK] Nothing to store. All interactions in this extraction are already processed.")
        return

    graph_db = GraphDatabase(args.graph_db)

    if source_type == 'external_document':
        missing_sources = []
        for extraction in extractions:
            source_uuid = extraction['source_uuid']
            if not graph_db.get_entity_by_uuid(source_uuid):
                missing_sources.append(source_uuid)

        if missing_sources:
            graph_db.close()
            safe_print("[ERROR] Extraction references missing external sources:")
            for source_uuid in sorted(set(missing_sources)):
                safe_print(f"        - {source_uuid}")
            safe_print("        Import the source documents before storing this extraction.")
            sys.exit(1)

    # Run quality checks (unless human explicitly skipped)
    # Note: We DO process quality answers in dry-run mode to test the logic
    quality_answers = None
    quality_questions = None
    if not args.human_skip_quality:
        safe_print("[SEARCH] Running quality checks for duplicates and contradictions...\n")

        # Generate questions
        questions = generate_quality_questions(extractions, graph_db, args.project)

        # Check if there are any questions
        has_questions = len(questions['duplicates']) > 0 or len(questions['contradictions']) > 0

        if has_questions:
            # Save questions to file
            with open(args.quality_questions_file, 'w', encoding='utf-8') as f:
                json.dump(questions, f, indent=2)

            safe_print(f"[NOTE] Found {len(questions['duplicates'])} potential duplicates")
            safe_print(f"[NOTE] Found {len(questions['contradictions'])} facts to check for contradictions")
            safe_print(f"[NOTE] Questions saved to: {args.quality_questions_file}\n")

            if args.require_quality_review:
                questions_hash, answers_template_written = ensure_quality_answers_template(
                    args.quality_questions_file,
                    args.quality_answers_file,
                    questions,
                )
                if answers_template_written:
                    safe_print(f"[NOTE] Answers template refreshed: {args.quality_answers_file}")
                    safe_print(f"       _questions_hash: {questions_hash}\n")
                # Validate answers actually address the questions
                is_valid, validation_errors = validate_quality_answers(
                    args.quality_questions_file,
                    args.quality_answers_file
                )
                if not is_valid:
                    safe_print(f"\n[ERROR] Quality answers validation failed:")
                    for err in validation_errors:
                        safe_print(f"   - {err}")
                    safe_print(f"\nEdit {args.quality_answers_file} and rerun.")
                    sys.exit(1)

                with open(args.quality_answers_file, 'r', encoding='utf-8') as f:
                    quality_answers = json.load(f)
                # Also load questions for index-based lookup
                with open(args.quality_questions_file, 'r', encoding='utf-8') as f:
                    quality_questions = json.load(f)
            else:
                # Call LLM wrapper to analyze duplicates
                safe_print(f"\n[QUALITY] Checking for duplicates...")
                success_duplicates = call_llm_for_quality_check(
                    args.quality_questions_file,
                    args.quality_answers_file,
                    'duplicates',
                    config
                )

                if not success_duplicates:
                    safe_print(f"[ERROR] Duplicate check failed!")
                    safe_print(f"        AI agents: Review the quality questions yourself and provide answers.")
                    safe_print(f"        Write answers to the quality-answers file, then rerun with --require-quality-review")
                    sys.exit(1)

                # Call LLM wrapper to analyze contradictions
                safe_print(f"\n[QUALITY] Checking for contradictions...")
                success_contradictions = call_llm_for_quality_check(
                    args.quality_questions_file,
                    args.quality_answers_file,
                    'contradictions',
                    config
                )

                if not success_contradictions:
                    safe_print(f"[ERROR] Contradiction check failed!")
                    safe_print(f"        AI agents: Review the quality questions yourself and provide answers.")
                    safe_print(f"        Write answers to the quality-answers file, then rerun with --require-quality-review")
                    sys.exit(1)

                with open(args.quality_answers_file, 'r', encoding='utf-8') as f:
                    quality_answers = json.load(f)
                # Also load questions for index-based lookup
                with open(args.quality_questions_file, 'r', encoding='utf-8') as f:
                    quality_questions = json.load(f)

            safe_print(f"\n[OK] Quality analysis complete!")
            safe_print(f"   Duplicates to merge: {sum(1 for d in quality_answers.get('duplicates', []) if d.get('is_duplicate'))}")
            safe_print(f"   Facts to invalidate: {sum(len(c.get('contradicted_fact_uuids', [])) for c in quality_answers.get('contradictions', []))}\n")
        else:
            safe_print("[OK] No quality issues found - all entities and facts are unique!\n")
    elif args.human_skip_quality:
        safe_print("[SKIP]  Skipping quality checks (human override)\n")

    # Create project node only after preflight and quality gating are complete.
    graph_db.create_project_node(args.project, f"Project: {args.project}")

    total_entities = 0
    total_facts = 0
    total_duplicates_merged = 0
    total_facts_invalidated = 0
    total_facts_expected = 0  # Track expected facts for validation
    total_facts_skipped = 0   # Track skipped facts
    skipped_facts_details = []  # Details of skipped facts for error reporting
    entity_uuid_map = {}  # Map entity names to UUIDs
    global_fact_index = 0  # Track fact index across all extractions

    # Track entity dispositions for verification (Fix #3)
    entity_disposition_map = {}  # input_name -> {canonical_uuid, disposition, canonical_name}

    # Track created UUIDs for ExtractionBatch provenance
    created_entity_uuids = []
    created_relationship_uuids = []
    source_interaction_uuids = []
    source_interaction_hashes = []

    # Pre-populate entity_uuid_map with existing entities from database
    # This allows facts to reference entities created in previous syncs
    safe_print("[LIST] Loading existing entities from database...")
    existing_entities = graph_db.get_all_entities(args.project)
    for entity in existing_entities:
        entity_uuid_map[entity['name']] = entity['uuid']
    safe_print(f"   Loaded {len(existing_entities)} existing entities\n")

    # Process each extraction
    for extraction in extractions:
        interaction_uuid = None
        interaction_session_id = None

        # Support both conversation and external document sources
        if source_type == 'external_document':
            source_ref_uuid = extraction['source_uuid']
            entities = extraction.get('entities', [])
            facts = extraction.get('facts', [])

            safe_print(f"Processing external document {source_ref_uuid}...")

            # Get ExternalSource from graph for metadata
            external_source = graph_db.get_entity_by_uuid(source_ref_uuid)
            if not external_source:
                safe_print(f"  [WARNING]  ExternalSource not found in graph, skipping")
                continue

            # Use file hash as source hash
            source_hash = external_source.get('attributes', {}).get('file_hash', '')
            event_timestamp = external_source.get('created_at', datetime.now().isoformat())
            timestamp_proof = external_source.get('timestamp_proof', '')
            episode_ids = [source_ref_uuid]

        else:
            # Original conversation-based extraction
            interaction_uuid = extraction['interaction_uuid']
            entities = extraction.get('entities', [])
            facts = extraction.get('facts', [])

            safe_print(f"Processing interaction {interaction_uuid}...")

            # Get interaction from SQL for source hash, timestamp, and timestamp proof
            interaction = sql_db.get_interaction_by_uuid(interaction_uuid)
            if not interaction:
                safe_print(f"  [WARNING]  Interaction not found in SQL, skipping")
                continue

            source_ref_uuid = interaction_uuid
            source_hash = interaction['content_hash']
            event_timestamp = interaction.get('timestamp', '1970-01-01T00:00:00Z')
            timestamp_proof = interaction.get('timestamp_proof')
            interaction_session_id = interaction.get('session_id')
            episode_ids = [interaction_uuid]

            # Track source for ExtractionBatch provenance
            source_interaction_uuids.append(interaction_uuid)
            source_interaction_hashes.append(source_hash)

        # Store entities
        for entity in entities:
            entity_name = entity['name']
            entity_type = normalize_entity_type(entity['type'], strict=False)

            # Check if this entity is a duplicate (from quality answers)
            is_duplicate = False
            duplicate_uuid = None
            duplicate_name = None

            if quality_answers and quality_questions:
                # Build lookup: question_index -> answer
                answer_by_index = {
                    a.get('question_index'): a
                    for a in quality_answers.get('duplicates', [])
                }

                # Find if this entity has a duplicate question answered
                for q_idx, q in enumerate(quality_questions.get('duplicates', [])):
                    q_entity_name = q.get('new_entity', {}).get('name')
                    if q_entity_name == entity_name:
                        answer = answer_by_index.get(q_idx)
                        if answer and answer.get('is_duplicate'):
                            is_duplicate = True
                            # Accept both key names for backwards compatibility
                            duplicate_uuid = answer.get('duplicate_uuid') or answer.get('merge_with_uuid')
                            duplicate_name = answer.get('duplicate_name') or answer.get('merge_with_name')

                            # If no name provided, look it up from the question candidates
                            if not duplicate_name and duplicate_uuid:
                                for candidate in q.get('candidates', []):
                                    if candidate.get('uuid') == duplicate_uuid:
                                        duplicate_name = candidate.get('name')
                                        break

                            # Validate we got a UUID
                            if not duplicate_uuid:
                                safe_print(f"")
                                safe_print(f"  [ERROR] Duplicate marked but no UUID provided for '{entity_name}'!")
                                safe_print(f"          Use 'duplicate_uuid' in quality-answers.json")
                                safe_print(f"          Entity will be created as NEW (facts may fail to link)")
                                safe_print(f"")
                                is_duplicate = False
                        break

            if args.dry_run:
                if is_duplicate:
                    if duplicate_name == entity_name:
                        safe_print(f"  [DRY RUN] Would reuse canonical entity: {entity_name} ({duplicate_uuid})")
                    else:
                        safe_print(f"  [DRY RUN] Would create alias: {entity_name} -> {duplicate_name}")
                else:
                    task_event = None
                    task_event_warning = None
                    if entity_type == 'Task':
                        task_event, task_event_warning = find_task_event_reuse_candidate(
                            sql_db,
                            graph_db,
                            args.project,
                            entity_name,
                            workflow_session_id or interaction_session_id,
                            event_timestamp,
                        )
                    if task_event_warning:
                        safe_print(f"  [WARNING] {task_event_warning}")
                    if task_event:
                        safe_print(
                            f"  [DRY RUN] Would reuse task from event log: "
                            f"{entity_name} ({task_event['task_uuid']})"
                        )
                    else:
                        safe_print(f"  [DRY RUN] Would create entity: {entity_name} ({entity_type})")
            else:
                if is_duplicate:
                    # Use canonical UUID for facts
                    entity_uuid_map[entity_name] = duplicate_uuid

                    # Exact-name duplicate means the canonical entity already has the same name.
                    # Reuse it directly instead of trying to create a self-alias that will violate
                    # the Alias primary key constraint.
                    if duplicate_name == entity_name:
                        total_duplicates_merged += 1
                        safe_print(f"  [LINK] Using existing entity: {entity_name} ({duplicate_uuid})")
                        # Track disposition: REUSED
                        entity_disposition_map[entity_name] = {
                            'canonical_uuid': duplicate_uuid,
                            'canonical_name': duplicate_name,
                            'disposition': 'REUSED'
                        }
                    else:
                        alias_created = graph_db.create_alias(
                            name=entity_name,
                            canonical_uuid=duplicate_uuid,
                            source_interaction=source_ref_uuid,
                            source_hash=source_hash,
                            extraction_version=args.extraction_version,
                            extraction_commit=args.extraction_commit
                        )

                        total_duplicates_merged += 1
                        if alias_created:
                            safe_print(f"  [ALIAS] Created alias: {entity_name} -> {duplicate_name} ({duplicate_uuid})")
                            # Track disposition: ALIASED
                            entity_disposition_map[entity_name] = {
                                'canonical_uuid': duplicate_uuid,
                                'canonical_name': duplicate_name,
                                'disposition': 'ALIASED'
                            }
                        else:
                            safe_print(f"  [LINK] Reused canonical entity without creating alias: {entity_name} -> {duplicate_name} ({duplicate_uuid})")
                            # Track disposition: REUSED (alias already existed)
                            entity_disposition_map[entity_name] = {
                                'canonical_uuid': duplicate_uuid,
                                'canonical_name': duplicate_name,
                                'disposition': 'REUSED'
                            }
                else:
                    task_event = None
                    task_event_warning = None
                    if entity_type == 'Task':
                        task_event, task_event_warning = find_task_event_reuse_candidate(
                            sql_db,
                            graph_db,
                            args.project,
                            entity_name,
                            workflow_session_id or interaction_session_id,
                            event_timestamp,
                        )
                    if task_event_warning:
                        safe_print(f"  [WARNING] {task_event_warning}")

                    if task_event:
                        reused_uuid = task_event['task_uuid']
                        entity_uuid_map[entity_name] = reused_uuid
                        total_duplicates_merged += 1
                        safe_print(
                            f"  [LINK] Reused task from event log: {entity_name} "
                            f"({reused_uuid})"
                        )
                        entity_disposition_map[entity_name] = {
                            'canonical_uuid': reused_uuid,
                            'canonical_name': entity_name,
                            'disposition': 'REUSED'
                        }
                        continue

                    # Build source chain
                    if source_type == 'external_document':
                        # For external documents, source chain is just the document itself
                        source_chain = [{
                            'source_uuid': source_ref_uuid,
                            'source_hash': source_hash,
                            'source_type': 'external_document'
                        }]
                    else:
                        # For conversations, build from interactions
                        source_chain = build_source_chain_from_interactions(sql_db, [source_ref_uuid])

                    # Create new entity
                    entity_uuid = graph_db.create_entity(
                        name=entity_name,
                        summary=entity.get('summary', ''),
                        labels=[entity_type],
                        attributes=entity.get('attributes', {}),
                        source_interactions=[source_ref_uuid],
                        source_hashes=[source_hash],
                        source_chain=source_chain,
                        group_id=args.project,
                        extraction_version=args.extraction_version,
                        extraction_commit=args.extraction_commit,
                        event_timestamp=event_timestamp,
                        timestamp_proof=timestamp_proof,
                        priority=entity.get('priority'),
                        status=entity.get('status', 'pending' if entity_type == 'Task' else None)
                    )

                    # Link to project
                    graph_db.link_project_to_entity(args.project, entity_uuid)

                    # Link to source (ExternalSource or Interaction)
                    if source_type == 'external_document':
                        # Create EXTRACTED_FROM relationship to document entity
                        graph_db.create_relationship(
                            source_uuid=entity_uuid,
                            target_uuid=source_ref_uuid,
                            relationship_name='EXTRACTED_FROM',
                            fact=f"Entity {entity_name} was extracted from document",
                            group_id=args.project,
                            episodes=episode_ids,
                            episode_hashes=[source_hash] if source_hash else [],
                            derivation_version=args.extraction_version,
                            derivation_commit=args.extraction_commit,
                            valid_at=event_timestamp
                        )

                    entity_uuid_map[entity_name] = entity_uuid
                    created_entity_uuids.append(entity_uuid)
                    total_entities += 1
                    safe_print(f"  [OK] Created entity: {entity_name} ({entity_uuid})")
                    # Track disposition: CREATED
                    entity_disposition_map[entity_name] = {
                        'canonical_uuid': entity_uuid,
                        'canonical_name': entity_name,
                        'disposition': 'CREATED'
                    }
        
        # Store facts
        for fact in facts:
            total_facts_expected += 1

            # Normalize relationship type (may swap source/target for inverse types)
            normalized_fact, norm_error = normalize_fact(fact)
            if norm_error:
                # This should have been caught by validate_extraction.py, but defense-in-depth
                safe_print(f"  [WARNING]  Skipping fact with invalid relationship type: {norm_error}")
                skipped_facts_details.append({
                    'source': fact.get('source_entity', '?'),
                    'target': fact.get('target_entity', '?'),
                    'relationship': fact.get('relationship_type', '?'),
                    'reason': norm_error
                })
                total_facts_skipped += 1
                global_fact_index += 1
                continue

            # Use normalized values (source/target may be swapped for inverse types like USED_BY)
            source_name = normalized_fact['source_entity']
            target_name = normalized_fact['target_entity']
            relationship_type = normalized_fact['relationship_type']

            # Get entity UUIDs
            source_uuid = entity_uuid_map.get(source_name)
            target_uuid = entity_uuid_map.get(target_name)

            if not source_uuid or not target_uuid:
                missing = []
                if not source_uuid:
                    missing.append(f"source '{source_name}'")
                if not target_uuid:
                    missing.append(f"target '{target_name}'")
                safe_print(f"  [WARNING]  Skipping fact: entities not found ({source_name} -> {target_name})")
                skipped_facts_details.append({
                    'source': source_name,
                    'target': target_name,
                    'relationship': relationship_type,
                    'reason': f"Missing: {', '.join(missing)}"
                })
                total_facts_skipped += 1
                global_fact_index += 1
                continue

            # Check for contradictions (from quality answers)
            contradicted_uuids = []
            if quality_answers:
                for contra in quality_answers.get('contradictions', []):
                    if contra.get('fact_index') == global_fact_index:
                        contradicted_uuids = contra.get('contradicted_fact_uuids', [])
                        break

            if args.dry_run:
                if contradicted_uuids:
                    safe_print(f"  [DRY RUN] Would invalidate {len(contradicted_uuids)} contradicted facts")
                safe_print(f"  [DRY RUN] Would create fact: {source_name} --[{relationship_type}]--> {target_name}")
            else:
                valid_at = event_timestamp

                # Create the new fact first
                rel_uuid = graph_db.create_relationship(
                    source_uuid=source_uuid,
                    target_uuid=target_uuid,
                    relationship_name=relationship_type,
                    fact=normalized_fact['fact'],
                    episodes=episode_ids,
                    episode_hashes=[source_hash],
                    group_id=args.project,
                    valid_at=valid_at,
                    invalid_at=normalized_fact.get('invalid_at'),
                    derivation_version=args.extraction_version,
                    derivation_commit=args.extraction_commit,
                    timestamp_proof=timestamp_proof
                )

                created_relationship_uuids.append(rel_uuid)
                total_facts += 1
                safe_print(f"  [OK] Created fact: {source_name} --[{relationship_type}]--> {target_name}")

                # Invalidate contradicted facts AFTER creating new fact (so we can set superseded_by)
                if contradicted_uuids:
                    from tools.contradiction import invalidate_facts
                    count = invalidate_facts(
                        graph_db,
                        contradicted_uuids,
                        datetime.now().isoformat(),
                        superseded_by=rel_uuid  # Link to new fact that supersedes them
                    )
                    total_facts_invalidated += count
                    safe_print(f"  [WARNING]  Invalidated {count} contradicted facts (superseded by {rel_uuid})")

            global_fact_index += 1
        
        # Mark interaction as processed
        if not args.dry_run and source_type == 'conversation' and interaction_uuid:
            sql_db.mark_interaction_processed(interaction_uuid)
            safe_print(f"  [OK] Marked interaction as processed")
        
        safe_print()
    
    # Summary
    safe_print(f"{'='*60}")
    safe_print("[DATA] Summary")
    safe_print("="*60)
    safe_print(f"Project:               {args.project}")
    safe_print(f"Extractions stored:    {len(extractions)}")
    safe_print(f"Interactions skipped:  {len(skipped_interactions)}")
    safe_print(f"Entities stored:       {total_entities}")
    safe_print(f"Duplicates merged:     {total_duplicates_merged}")
    safe_print(f"Facts expected:        {total_facts_expected}")
    safe_print(f"Facts stored:          {total_facts}")
    safe_print(f"Facts skipped:         {total_facts_skipped}")
    safe_print(f"Facts invalidated:     {total_facts_invalidated}")
    quality_mode = 'Skipped (human override)' if args.human_skip_quality else ('Required' if args.require_quality_review else 'Enabled')
    safe_print(f"Quality checks:        {quality_mode}")
    safe_print(f"Dry run:               {args.dry_run}")

    # Validation: Check if facts were skipped
    if total_facts_skipped > 0:
        safe_print(f"\n{'='*60}")
        safe_print("[ERROR] VALIDATION FAILED - FACTS WERE SKIPPED!")
        safe_print("="*60)
        safe_print(f"\n{total_facts_skipped} of {total_facts_expected} facts were NOT stored due to missing entities.")
        safe_print("\nSkipped facts:")
        for i, skipped in enumerate(skipped_facts_details, 1):
            safe_print(f"  {i}. {skipped['source']} --[{skipped['relationship']}]--> {skipped['target']}")
            safe_print(f"     Reason: {skipped['reason']}")
        safe_print("\nPossible causes:")
        safe_print("  - Entity marked as duplicate but UUID not found (check quality-answers.json)")
        safe_print("  - Entity name mismatch between entities and facts in extraction")
        safe_print("  - Missing 'duplicate_uuid' or 'merge_with_uuid' in quality answers")
        safe_print("\nRecommended action:")
        safe_print("  1. Check quality-answers.json has correct 'duplicate_uuid' for each duplicate")
        safe_print("  2. Re-run store_extraction.py with corrected quality-answers.json")
        safe_print("  3. Or add missing entities to the extraction file")
        safe_print("="*60)
        if not args.dry_run:
            sys.exit(1)  # Exit with error code
    else:
        safe_print("\n[OK] Storage complete - all facts stored successfully!")

    # Create ExtractionBatch for provenance tracking
    if not args.dry_run and (created_entity_uuids or created_relationship_uuids):
        safe_print(f"\n{'='*60}")
        safe_print("[PROVENANCE] Creating ExtractionBatch...")
        safe_print(f"{'='*60}")

        # Create batch (OTS attestation can be added later via upgrade_ots.py)
        batch_uuid = graph_db.create_extraction_batch(
            project_name=args.project,
            extracted_by_agent=args.extracted_by_agent,
            extracted_by_model=args.extracted_by_model,
            extraction_version=args.extraction_version,
            extraction_commit=args.extraction_commit,
            source_interaction_uuids=source_interaction_uuids,
            source_interaction_hashes=source_interaction_hashes,
            created_entity_uuids=created_entity_uuids,
            created_relationship_uuids=created_relationship_uuids,
            timestamp_proof=None,  # OTS proof can be added later
            result="success"  # Mark as successful extraction
        )

        safe_print(f"  Batch UUID: {batch_uuid}")
        safe_print(f"  Agent: {args.extracted_by_agent or '(not specified)'}")
        safe_print(f"  Source interactions: {len(source_interaction_uuids)}")
        safe_print(f"  Created entities: {len(created_entity_uuids)}")
        safe_print(f"  Created relationships: {len(created_relationship_uuids)}")
        safe_print(f"  [OK] ExtractionBatch created")

    # Output entity mapping for verification (Fix #3)
    if entity_disposition_map and not args.dry_run:
        safe_print(f"\n{'='*60}")
        safe_print("[ENTITY MAPPING] Input -> Canonical UUID -> Disposition")
        safe_print(f"{'='*60}")
        for input_name, info in entity_disposition_map.items():
            safe_print(f"  {input_name}")
            safe_print(f"    -> {info['canonical_uuid']}")
            if info['disposition'] == 'ALIASED':
                safe_print(f"    -> {info['disposition']} (alias to \"{info['canonical_name']}\")")
            elif info['disposition'] == 'REUSED':
                safe_print(f"    -> {info['disposition']} (canonical match)")
            else:
                safe_print(f"    -> {info['disposition']} (new canonical entity)")
        safe_print(f"{'='*60}")

        # Write timestamped mapping file
        extraction_path = Path(args.extraction_file)
        timestamp_suffix = extraction_path.stem.replace("extraction_", "")
        mapping_filename = f"entity-mapping_{timestamp_suffix}.json"
        mapping_path = extraction_path.parent / mapping_filename

        mapping_output = {
            "extraction_file": str(args.extraction_file),
            "timestamp": datetime.now().isoformat(),
            "project": args.project,
            "entities": entity_disposition_map
        }
        with open(mapping_path, 'w', encoding='utf-8') as f:
            json.dump(mapping_output, f, indent=2)
        safe_print(f"Mapping saved to: {mapping_path}")

    # Check if consolidation should be recommended
    if not args.dry_run:
        from tools.consolidation_reminder import show_recommendation_if_needed
        show_recommendation_if_needed()

    # Check if temp file cleanup should be recommended
    if not args.dry_run:
        from tools.temp_cleanup_reminder import show_recommendation_if_needed as show_cleanup_reminder
        show_cleanup_reminder()

    # Show task summary
    if not args.dry_run:
        show_task_summary(args.project, graph_db)

    # Close database connection after all graph reads are finished.
    graph_db.close()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        safe_print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        safe_print(f"\n[ERROR] Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

