#!/usr/bin/env python3
"""
LLM Wrapper for Auggie CLI

Standard interface for quality checking with Auggie.
This wrapper calls the Auggie CLI to review quality questions and generate answers.

NOTE: Auggie is an AI agent powered by Claude Sonnet 4.5 via Anthropic.
      Using this wrapper incurs costs through your Augment subscription.

Usage:
    python llm_wrapper_auggie.py <questions_file> <answers_file> <prompt_file>

Arguments:
    questions_file - Path to JSON file with quality questions
    answers_file   - Path where answers should be written (JSON)
    prompt_file    - Path to markdown file with criteria/instructions

Exit codes:
    0 - Success
    1 - Invalid arguments
    2 - Auggie command failed
    3 - Output file not created

Example:
    python llm_wrapper_auggie.py \\
        quality-questions.json \\
        quality-answers.json \\
        prompts/quality-check-contradictions.md
"""

import sys
import subprocess
import os


def main():
    # Validate arguments
    if len(sys.argv) != 4:
        print("ERROR: Invalid arguments", file=sys.stderr)
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    
    questions_file = sys.argv[1]
    answers_file = sys.argv[2]
    prompt_file = sys.argv[3]
    
    # Validate input files exist
    if not os.path.exists(questions_file):
        print(f"ERROR: Questions file not found: {questions_file}", file=sys.stderr)
        sys.exit(1)
    
    if not os.path.exists(prompt_file):
        print(f"ERROR: Prompt file not found: {prompt_file}", file=sys.stderr)
        sys.exit(1)
    
    # Read the prompt/criteria
    print(f"[1/3] Reading prompt from {prompt_file}...")
    with open(prompt_file, 'r', encoding='utf-8') as f:
        prompt = f.read()
    
    # Build instruction for Auggie
    instruction = f"""{prompt}

---

## Input and Output Files

**Input file:** {questions_file}
**Output file:** {answers_file}

Please:
1. Read the questions from {questions_file}
2. Follow the criteria and output format specified above
3. Write your answers to {answers_file} in valid JSON format

Make sure the output is valid JSON that can be parsed programmatically.
"""
    
    # Call Auggie
    print(f"[2/3] Calling Auggie to review {questions_file}...")
    print(f"      (This may take a minute...)")
    
    result = subprocess.run(
        [
            "auggie",
            "--print",
            "--quiet",
            "--instruction", instruction
        ],
        capture_output=False,  # Let Auggie output show through
        text=True
    )
    
    if result.returncode != 0:
        print(f"ERROR: Auggie command failed with exit code {result.returncode}", file=sys.stderr)
        sys.exit(2)
    
    # Verify output file was created
    print(f"[3/3] Verifying output file...")
    if not os.path.exists(answers_file):
        print(f"ERROR: Auggie did not create output file: {answers_file}", file=sys.stderr)
        print(f"       The file may have been created with a different name.", file=sys.stderr)
        sys.exit(3)
    
    # Verify it's valid JSON
    try:
        import json
        with open(answers_file, 'r', encoding='utf-8') as f:
            json.load(f)
        print(f"✓ Success! Answers written to {answers_file}")
    except json.JSONDecodeError as e:
        print(f"WARNING: Output file is not valid JSON: {e}", file=sys.stderr)
        print(f"         File was created but may need manual review.", file=sys.stderr)
        # Don't exit with error - file exists, just may need cleanup
    
    sys.exit(0)


if __name__ == "__main__":
    main()

