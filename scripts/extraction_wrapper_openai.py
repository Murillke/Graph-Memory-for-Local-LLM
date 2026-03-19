#!/usr/bin/env python3
"""
Extraction Wrapper for OpenAI API

Standard interface for entity/fact extraction with OpenAI's GPT models.
Requires OPENAI_API_KEY environment variable.

Usage:
    python extraction_wrapper_openai.py <input_file> <output_file> <extraction_type> <prompt_file>

Arguments:
    input_file       - Path to JSON file with conversation data
    output_file      - Path where extraction results should be written (JSON)
    extraction_type  - Type of extraction: "entities" or "facts"
    prompt_file      - Path to markdown file with extraction instructions

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
    python extraction_wrapper_openai.py \\
        input.json \\
        output.json \\
        entities \\
        prompts/extract-entities.md
"""

import sys
import json
import os


def main():
    # Validate arguments
    if len(sys.argv) != 5:
        print("ERROR: Invalid arguments", file=sys.stderr)
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    extraction_type = sys.argv[3]
    prompt_file = sys.argv[4]
    
    # Validate extraction type
    if extraction_type not in ['entities', 'facts']:
        print(f"ERROR: Invalid extraction_type: {extraction_type}", file=sys.stderr)
        print(f"       Must be 'entities' or 'facts'", file=sys.stderr)
        sys.exit(1)
    
    # Check for API key
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("ERROR: OPENAI_API_KEY environment variable not set", file=sys.stderr)
        print("       Get your API key from https://platform.openai.com/api-keys", file=sys.stderr)
        sys.exit(1)
    
    # Validate input files exist
    if not os.path.exists(input_file):
        print(f"ERROR: Input file not found: {input_file}", file=sys.stderr)
        sys.exit(1)
    
    if not os.path.exists(prompt_file):
        print(f"ERROR: Prompt file not found: {prompt_file}", file=sys.stderr)
        sys.exit(1)
    
    # Import OpenAI
    try:
        from openai import OpenAI
    except ImportError:
        print("ERROR: openai package not installed", file=sys.stderr)
        print("       Install with: pip install openai", file=sys.stderr)
        sys.exit(1)
    
    # Read prompt and input data
    print(f"[1/3] Reading prompt from {prompt_file}...")
    with open(prompt_file, 'r', encoding='utf-8') as f:
        prompt = f.read()
    
    print(f"[2/3] Reading input from {input_file}...")
    with open(input_file, 'r', encoding='utf-8') as f:
        input_data = json.load(f)
    
    # Get model from environment or use default
    model = os.getenv('OPENAI_MODEL', 'gpt-4o')
    
    # Call OpenAI API
    print(f"[3/3] Calling OpenAI API (model: {model}, type: {extraction_type})...")
    
    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(input_data, indent=2)}
            ],
            temperature=0.1,  # Low temperature for consistent extraction
            response_format={"type": "json_object"}  # Request JSON response
        )
        
        # Extract response
        result_text = response.choices[0].message.content
        
        # Parse and validate JSON
        try:
            result = json.loads(result_text)
        except json.JSONDecodeError as e:
            print(f"ERROR: OpenAI returned invalid JSON: {e}", file=sys.stderr)
            print(f"       Response: {result_text[:200]}...", file=sys.stderr)
            sys.exit(3)
        
        # Validate structure
        expected_key = extraction_type  # "entities" or "facts"
        if expected_key not in result:
            print(f"ERROR: Response missing '{expected_key}' key", file=sys.stderr)
            print(f"       Response keys: {list(result.keys())}", file=sys.stderr)
            sys.exit(3)
        
        # Write results to file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2)
        
        count = len(result[expected_key])
        print(f"✓ Success! Extracted {count} {extraction_type}")
        print(f"  Output: {output_file}")
        print(f"  Tokens: {response.usage.total_tokens}")
        print(f"  Cost: ${response.usage.total_tokens * 0.00001:.4f}")
        
    except Exception as e:
        print(f"ERROR: OpenAI API call failed: {e}", file=sys.stderr)
        sys.exit(2)
    
    sys.exit(0)


if __name__ == "__main__":
    main()

