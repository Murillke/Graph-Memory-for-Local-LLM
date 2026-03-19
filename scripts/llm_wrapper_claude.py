#!/usr/bin/env python3
"""
LLM Wrapper for Claude API (Anthropic)

Standard interface for quality checking with Anthropic's Claude models.
Requires ANTHROPIC_API_KEY environment variable.

Installation:
    pip install anthropic

Usage:
    python llm_wrapper_claude.py <questions_file> <answers_file> <prompt_file>

Arguments:
    questions_file - Path to JSON file with quality questions
    answers_file   - Path where answers should be written (JSON)
    prompt_file    - Path to markdown file with criteria/instructions

Environment:
    ANTHROPIC_API_KEY - Your Anthropic API key (required)
    CLAUDE_MODEL      - Model to use (default: claude-sonnet-4-20250514)

Exit codes:
    0 - Success
    1 - Invalid arguments or missing API key
    2 - Claude API call failed
    3 - Invalid response from API

Example:
    export ANTHROPIC_API_KEY="sk-ant-..."
    python llm_wrapper_claude.py \\
        quality-questions.json \\
        quality-answers.json \\
        prompts/quality-check-contradictions.md
    
    # Using a different model
    export CLAUDE_MODEL="claude-opus-4-20250514"
    python llm_wrapper_claude.py \\
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
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set", file=sys.stderr)
        print("       Get your API key from https://console.anthropic.com/", file=sys.stderr)
        sys.exit(1)
    
    # Validate input files exist
    if not os.path.exists(questions_file):
        print(f"ERROR: Questions file not found: {questions_file}", file=sys.stderr)
        sys.exit(1)
    
    if not os.path.exists(prompt_file):
        print(f"ERROR: Prompt file not found: {prompt_file}", file=sys.stderr)
        sys.exit(1)
    
    # Import Anthropic (lazy import to avoid dependency if not using this wrapper)
    try:
        import anthropic
    except ImportError:
        print("ERROR: anthropic package not installed", file=sys.stderr)
        print("       Install with: pip install anthropic", file=sys.stderr)
        sys.exit(1)
    
    # Read prompt and questions
    print(f"[1/3] Reading prompt from {prompt_file}...")
    with open(prompt_file, 'r', encoding='utf-8') as f:
        prompt = f.read()
    
    print(f"[2/3] Reading questions from {questions_file}...")
    with open(questions_file, 'r', encoding='utf-8') as f:
        questions = json.load(f)
    
    # Get model from environment or use default
    model = os.getenv('CLAUDE_MODEL', 'claude-sonnet-4-20250514')
    
    # Call Claude API
    print(f"[3/3] Calling Claude API (model: {model})...")
    print(f"      (This may take a minute...)")
    
    try:
        client = anthropic.Anthropic(api_key=api_key)
        
        # Build the user message
        user_message = f"""Here are the questions to review:

{json.dumps(questions, indent=2)}

Please provide your answers in valid JSON format following the structure specified in the system prompt.
"""
        
        response = client.messages.create(
            model=model,
            max_tokens=8192,
            temperature=0.1,  # Low temperature for consistent, factual responses
            system=prompt,  # System prompt with criteria
            messages=[
                {"role": "user", "content": user_message}
            ]
        )
        
        # Extract response
        answer_text = response.content[0].text
        
        # Parse and validate JSON
        try:
            answers = json.loads(answer_text)
        except json.JSONDecodeError as e:
            # Sometimes Claude wraps JSON in markdown code blocks
            # Try to extract JSON from markdown
            if '```json' in answer_text:
                import re
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', answer_text, re.DOTALL)
                if json_match:
                    try:
                        answers = json.loads(json_match.group(1))
                    except json.JSONDecodeError:
                        print(f"ERROR: Claude returned invalid JSON: {e}", file=sys.stderr)
                        print(f"       Response: {answer_text[:500]}...", file=sys.stderr)
                        sys.exit(3)
                else:
                    print(f"ERROR: Claude returned invalid JSON: {e}", file=sys.stderr)
                    print(f"       Response: {answer_text[:500]}...", file=sys.stderr)
                    sys.exit(3)
            else:
                print(f"ERROR: Claude returned invalid JSON: {e}", file=sys.stderr)
                print(f"       Response: {answer_text[:500]}...", file=sys.stderr)
                sys.exit(3)
        
        # Write answers to file
        with open(answers_file, 'w', encoding='utf-8') as f:
            json.dump(answers, f, indent=2)
        
        print(f"✓ Success! Answers written to {answers_file}")
        print(f"  Model: {model}")
        print(f"  Input tokens: {response.usage.input_tokens}")
        print(f"  Output tokens: {response.usage.output_tokens}")
        
        # Calculate cost (approximate, based on current pricing)
        # Sonnet 4: $3/MTok input, $15/MTok output
        input_cost = response.usage.input_tokens * 3 / 1_000_000
        output_cost = response.usage.output_tokens * 15 / 1_000_000
        total_cost = input_cost + output_cost
        print(f"  Estimated cost: ${total_cost:.4f}")
        
    except anthropic.APIError as e:
        print(f"ERROR: Claude API error: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"ERROR: Claude API call failed: {e}", file=sys.stderr)
        sys.exit(2)
    
    sys.exit(0)


if __name__ == "__main__":
    main()

