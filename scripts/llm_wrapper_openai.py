#!/usr/bin/env python3
"""
LLM Wrapper for OpenAI API

Standard interface for quality checking with OpenAI's GPT models.
Requires OPENAI_API_KEY environment variable.

Usage:
    python llm_wrapper_openai.py <questions_file> <answers_file> <prompt_file>

Arguments:
    questions_file - Path to JSON file with quality questions
    answers_file   - Path where answers should be written (JSON)
    prompt_file    - Path to markdown file with criteria/instructions

Environment:
    OPENAI_API_KEY - Your OpenAI API key (required)
    OPENAI_MODEL   - Model to use (default: gpt-4o)

Exit codes:
    0 - Success
    1 - Invalid arguments or missing API key
    2 - OpenAI API call failed
    3 - Invalid response from API

Example:
    export OPENAI_API_KEY="sk-..."
    python llm_wrapper_openai.py \\
        quality-questions.json \\
        quality-answers.json \\
        prompts/quality-check-contradictions.md
"""

import sys
import json
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
    
    # Check for API key
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("ERROR: OPENAI_API_KEY environment variable not set", file=sys.stderr)
        print("       Get your API key from https://platform.openai.com/api-keys", file=sys.stderr)
        sys.exit(1)
    
    # Validate input files exist
    if not os.path.exists(questions_file):
        print(f"ERROR: Questions file not found: {questions_file}", file=sys.stderr)
        sys.exit(1)
    
    if not os.path.exists(prompt_file):
        print(f"ERROR: Prompt file not found: {prompt_file}", file=sys.stderr)
        sys.exit(1)
    
    # Import OpenAI (lazy import to avoid dependency if not using this wrapper)
    try:
        from openai import OpenAI
    except ImportError:
        print("ERROR: openai package not installed", file=sys.stderr)
        print("       Install with: pip install openai", file=sys.stderr)
        sys.exit(1)
    
    # Read prompt and questions
    print(f"[1/3] Reading prompt from {prompt_file}...")
    with open(prompt_file, 'r', encoding='utf-8') as f:
        prompt = f.read()
    
    print(f"[2/3] Reading questions from {questions_file}...")
    with open(questions_file, 'r', encoding='utf-8') as f:
        questions = json.load(f)
    
    # Get model from environment or use default
    model = os.getenv('OPENAI_MODEL', 'gpt-4o')
    
    # Call OpenAI API
    print(f"[3/3] Calling OpenAI API (model: {model})...")
    print(f"      (This may take a minute...)")
    
    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(questions, indent=2)}
            ],
            temperature=0.1,  # Low temperature for consistent, factual responses
            response_format={"type": "json_object"}  # Request JSON response
        )
        
        # Extract response
        answer_text = response.choices[0].message.content
        
        # Parse and validate JSON
        try:
            answers = json.loads(answer_text)
        except json.JSONDecodeError as e:
            print(f"ERROR: OpenAI returned invalid JSON: {e}", file=sys.stderr)
            print(f"       Response: {answer_text[:200]}...", file=sys.stderr)
            sys.exit(3)
        
        # Write answers to file
        with open(answers_file, 'w', encoding='utf-8') as f:
            json.dump(answers, f, indent=2)
        
        print(f"✓ Success! Answers written to {answers_file}")
        print(f"  Tokens used: {response.usage.total_tokens}")
        print(f"  Estimated cost: ${response.usage.total_tokens * 0.00001:.4f}")
        
    except Exception as e:
        print(f"ERROR: OpenAI API call failed: {e}", file=sys.stderr)
        sys.exit(2)
    
    sys.exit(0)


if __name__ == "__main__":
    main()

