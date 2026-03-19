#!/usr/bin/env python3
"""
Extract knowledge from interactions using configurable LLM wrappers.

This script uses the extraction wrapper interface to extract entities and facts
using ANY configured LLM (Auggie, OpenAI, Claude, Ollama, etc.).

Usage:
    python scripts/extract_with_wrappers.py --project llm_memory --limit 5
    python scripts/extract_with_wrappers.py --project llm_memory --limit 5 --output tmp/extraction.json
"""

import sys
import os
import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tools.sql_db import SQLDatabase
from tools.config import load_config
from tools.console_utils import safe_print, setup_console_encoding

# Setup console encoding for Windows
setup_console_encoding()

def call_extraction_wrapper(wrapper_script, input_file, output_file, extraction_type, prompt_file):
    """Call an extraction wrapper script."""
    safe_print(f"  Calling {os.path.basename(wrapper_script)} for {extraction_type}...")

    try:
        result = subprocess.run(
            [sys.executable, wrapper_script, input_file, output_file, extraction_type, prompt_file],
            capture_output=False,
            text=True
        )

        if result.returncode != 0:
            safe_print(f"[ERROR] Wrapper failed with exit code {result.returncode}")
            return False

        if not os.path.exists(output_file):
            safe_print(f"[ERROR] Wrapper did not create output file: {output_file}")
            return False

        return True

    except Exception as e:
        safe_print(f"[ERROR] Failed to call wrapper: {e}")
        return False


def fail_preflight(message: str):
    safe_print(f"[ERROR] {message}")
    sys.exit(1)


def ensure_directory_exists(path_str: str, label: str):
    directory = Path(path_str)
    if not directory.exists():
        fail_preflight(f"{label} does not exist: {directory}")


def ensure_parent_directory_exists(path_str: str, label: str):
    parent = Path(path_str).parent
    if not parent.exists():
        fail_preflight(f"{label} directory does not exist: {parent}")


def has_configured_wrapper(path_str):
    return isinstance(path_str, str) and path_str.strip() not in {"", "null", "None"}


def load_wrapper_output(path_str: str, field_name: str):
    try:
        with open(path_str, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        fail_preflight(f"Wrapper output is invalid JSON ({path_str}): {e}")
    except Exception as e:
        fail_preflight(f"Failed to read wrapper output {path_str}: {e}")

    items = data.get(field_name)
    if not isinstance(items, list):
        fail_preflight(f"Wrapper output {path_str} must contain a '{field_name}' list")
    return items


def main():
    parser = argparse.ArgumentParser(description='Extract knowledge using configurable LLM wrappers')
    parser.add_argument('--project', required=True, help='Project name')
    parser.add_argument('--limit', type=int, help='Limit number of interactions to process')
    parser.add_argument('--output', help='Output file path (default: <tmp_dir>/extraction.json)')
    parser.add_argument('--sql-db', help='Path to SQL database (overrides config)')
    parser.add_argument('--include-processed', action='store_true', help='Include already-processed interactions')

    args = parser.parse_args()

    # Load configuration
    resolved_config = load_config(project_name=args.project, cli_args={"sql_db": args.sql_db})
    config = resolved_config.to_dict()

    # Get database path from config
    sql_path = resolved_config.get_sql_db_path()
    tmp_dir = resolved_config.get_tmp_dir()
    output_path = args.output or str(Path(tmp_dir) / "extraction.json")

    # Get extraction wrapper settings
    entities_wrapper = config['extraction']['llm_wrapper_entities']
    facts_wrapper = config['extraction']['llm_wrapper_facts']
    entities_prompt = config['extraction']['prompts']['entities']
    facts_prompt = config['extraction']['prompts']['facts']

    if not Path(sql_path).exists():
        fail_preflight(f"SQL database file not found: {sql_path}")

    ensure_directory_exists(tmp_dir, "Temporary directory")
    ensure_parent_directory_exists(output_path, "Output file")

    if not has_configured_wrapper(entities_wrapper) or not has_configured_wrapper(facts_wrapper):
        fail_preflight(
            "No extraction wrapper is configured. Do the extraction yourself: read the pending interactions, "
            "write tmp/extraction.json manually, validate it with scripts/validate_extraction.py, and then "
            "store it with scripts/store_extraction.py."
        )

    for label, path_str in (
        ("Entities wrapper", entities_wrapper),
        ("Facts wrapper", facts_wrapper),
        ("Entities prompt", entities_prompt),
        ("Facts prompt", facts_prompt),
    ):
        if not Path(path_str).exists():
            fail_preflight(f"{label} not found: {path_str}")

    safe_print(f"[CONFIG] Extraction wrappers:")
    safe_print(f"  Entities: {entities_wrapper}")
    safe_print(f"  Facts: {facts_wrapper}")
    safe_print(f"  Output: {output_path}\n")

    # Connect to SQL database
    sql_db = SQLDatabase(sql_path)

    # Get interactions
    if args.include_processed:
        interactions = sql_db.get_all_interactions(args.project)
    else:
        interactions = sql_db.get_unprocessed_interactions(args.project)

    if not interactions:
        safe_print(f"[OK] No interactions found for project '{args.project}'")
        return

    # Apply limit if specified
    if args.limit:
        interactions = interactions[-args.limit:]

    safe_print(f"[DATA] Processing {len(interactions)} interactions...\n")

    # Prepare extraction results
    extraction_version = config['extraction']['version']
    extraction_commit = datetime.now().strftime('%Y-%m-%d')

    extractions = []
    failed_interactions = []

    # Process each interaction
    for i, interaction in enumerate(interactions, 1):
        safe_print(f"[{i}/{len(interactions)}] Processing interaction {interaction['uuid']}...")

        # Create temp input file for wrapper
        input_data = {
            "interaction_uuid": interaction['uuid'],
            "user_message": interaction.get('user_message', ''),
            "assistant_message": interaction.get('assistant_message', ''),
            "timestamp": interaction.get('timestamp', ''),
            "previous_messages": []
        }

        temp_input = str(Path(tmp_dir) / f"wrapper_input_{i}.json")
        temp_entities = str(Path(tmp_dir) / f"wrapper_entities_{i}.json")
        temp_facts = str(Path(tmp_dir) / f"wrapper_facts_{i}.json")

        try:
            # Write input file
            with open(temp_input, 'w', encoding='utf-8') as f:
                json.dump(input_data, f, indent=2)

            # Extract entities
            safe_print(f"  Step 1: Extracting entities...")
            if not call_extraction_wrapper(entities_wrapper, temp_input, temp_entities, 'entities', entities_prompt):
                safe_print(f"[ERROR] Failed to extract entities")
                failed_interactions.append(interaction['uuid'])
                continue

            # Read entities
            entities = load_wrapper_output(temp_entities, 'entities')
            safe_print(f"  OK Extracted {len(entities)} entities")

            # Extract facts
            safe_print(f"  Step 2: Extracting facts...")

            # Add entities list to input for fact extraction
            input_data['entities'] = [e['name'] for e in entities]
            with open(temp_input, 'w', encoding='utf-8') as f:
                json.dump(input_data, f, indent=2)

            if not call_extraction_wrapper(facts_wrapper, temp_input, temp_facts, 'facts', facts_prompt):
                safe_print(f"[ERROR] Failed to extract facts")
                failed_interactions.append(interaction['uuid'])
                continue

            # Read facts
            facts = load_wrapper_output(temp_facts, 'facts')

            safe_print(f"  OK Extracted {len(facts)} facts\n")

            # Add to extractions
            extractions.append({
                "interaction_uuid": interaction['uuid'],
                "entities": entities,
                "facts": facts
            })
        finally:
            for temp_file in [temp_input, temp_entities, temp_facts]:
                if os.path.exists(temp_file):
                    os.remove(temp_file)

    if not extractions:
        fail_preflight(
            f"No extractions were produced. Wrapper failures: {len(failed_interactions)} interaction(s)."
        )

    # Create final extraction file
    extraction_data = {
        "project_name": args.project,
        "extraction_version": extraction_version,
        "extraction_commit": extraction_commit,
        "extractions": extractions
    }

    # Write output file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(extraction_data, f, indent=2)

    # Summary
    total_entities = sum(len(e['entities']) for e in extractions)
    total_facts = sum(len(e['facts']) for e in extractions)

    safe_print(f"{'='*60}")
    safe_print(f"[OK] Extraction complete!")
    safe_print(f"  Interactions: {len(extractions)}")
    safe_print(f"  Entities: {total_entities}")
    safe_print(f"  Facts: {total_facts}")
    safe_print(f"  Output: {output_path}")
    safe_print(f"{'='*60}\n")
    safe_print(f"Next step: Store to database with:")
    safe_print(f"  python scripts/store_extraction.py --project {args.project} --extraction-file {output_path}")


if __name__ == "__main__":
    main()
