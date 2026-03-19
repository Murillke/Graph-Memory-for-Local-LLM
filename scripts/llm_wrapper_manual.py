#!/usr/bin/env python3
"""
LLM Wrapper for Manual Review

Standard interface for manual quality checking (fallback when no LLM available).
This wrapper prompts the user to manually review questions and create answers.

Usage:
    python llm_wrapper_manual.py <questions_file> <answers_file> <prompt_file>

Arguments:
    questions_file - Path to JSON file with quality questions
    answers_file   - Path where answers should be written (JSON)
    prompt_file    - Path to markdown file with criteria/instructions

Exit codes:
    0 - Success (user created answers file)
    1 - Invalid arguments
    2 - User cancelled or answers file not created

Example:
    python llm_wrapper_manual.py \\
        quality-questions.json \\
        quality-answers.json \\
        prompts/quality-check-contradictions.md
"""

import sys
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
    
    # Display instructions to user
    print("\n" + "="*80)
    print("MANUAL QUALITY CHECK REQUIRED")
    print("="*80)
    print("\nNo automated LLM is configured. Please review the questions manually.")
    print("\nSteps:")
    print(f"\n  1. Read the criteria and instructions:")
    print(f"     {os.path.abspath(prompt_file)}")
    print(f"\n  2. Review the questions:")
    print(f"     {os.path.abspath(questions_file)}")
    print(f"\n  3. Create the answers file following the format in the prompt:")
    print(f"     {os.path.abspath(answers_file)}")
    print("\nTips:")
    print("  - Open the files in your favorite editor")
    print("  - Follow the JSON format exactly as specified in the prompt")
    print("  - Answer ALL questions in the same order")
    print("  - Validate your JSON before saving (use jsonlint.com or similar)")
    print("\n" + "="*80)
    print("\nPress Enter when you've created the answers file...")
    print("(or Ctrl+C to cancel)")
    print("="*80 + "\n")
    
    try:
        input()
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
        sys.exit(2)
    
    # Verify answers file was created
    if not os.path.exists(answers_file):
        print(f"\nERROR: Answers file not found: {answers_file}", file=sys.stderr)
        print(f"       Please create the file and run again.", file=sys.stderr)
        sys.exit(2)
    
    # Verify it's valid JSON
    try:
        import json
        with open(answers_file, 'r', encoding='utf-8') as f:
            json.load(f)
        print(f"\n✓ Success! Found valid answers file: {answers_file}\n")
    except json.JSONDecodeError as e:
        print(f"\nERROR: Answers file is not valid JSON: {e}", file=sys.stderr)
        print(f"       Please fix the JSON syntax and run again.", file=sys.stderr)
        sys.exit(2)
    
    sys.exit(0)


if __name__ == "__main__":
    main()

