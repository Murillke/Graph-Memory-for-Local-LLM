#!/usr/bin/env python3
"""
Extraction Wrapper for Claude API (Anthropic)

Standard interface for entity/fact extraction with Anthropic's Claude models.
Requires ANTHROPIC_API_KEY environment variable.

Usage:
    python extraction_wrapper_claude.py <input_file> <output_file> <extraction_type> <prompt_file>

Arguments:
    input_file       - Path to JSON file with conversation data
    output_file      - Path where extraction results should be written (JSON)
    extraction_type  - Type of extraction: "entities" or "facts"
    prompt_file      - Path to markdown file with extraction instructions

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
    python extraction_wrapper_claude.py \\
        input.json \\
        output.json \\
        entities \\
        prompts/extract-entities.md
"""

import sys
import json
import os
import re


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
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set", file=sys.stderr)
        print("       Get your API key from https://console.anthropic.com/", file=sys.stderr)
        sys.exit(1)
    
    # Validate input files exist
    if not os.path.exists(input_file):
        print(f"ERROR: Input file not found: {input_file}", file=sys.stderr)
        sys.exit(1)
    
    if not os.path.exists(prompt_file):
        print(f"ERROR: Prompt file not found: {prompt_file}", file=sys.stderr)
        sys.exit(1)
    
    # Import Anthropic
    try:
        import anthropic
    except ImportError:
        print("ERROR: anthropic package not installed", file=sys.stderr)
        print("       Install with: pip install anthropic", file=sys.stderr)
        sys.exit(1)
    
    # Read prompt and input data
    print(f"[1/3] Reading prompt from {prompt_file}...")
    with open(prompt_file, 'r', encoding='utf-8') as f:
        prompt = f.read()
    
    print(f"[2/3] Reading input from {input_file}...")
    with open(input_file, 'r', encoding='utf-8') as f:
        input_data = json.load(f)
    
    # Get model from environment or use default
    model = os.getenv('CLAUDE_MODEL', 'claude-sonnet-4-20250514')
    
    # Build user message
    user_message = f"""Here is the conversation data to extract {extraction_type} from:

{json.dumps(input_data, indent=2)}

Please extract {extraction_type} following the format specified in the system prompt.
Return ONLY valid JSON, no markdown formatting."""
    
    # Call Claude API
    print(f"[3/3] Calling Claude API (model: {model}, type: {extraction_type})...")
    
    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=8192,
            temperature=0.1,  # Low temperature for consistent extraction
            system=prompt,
            messages=[
                {"role": "user", "content": user_message}
            ]
        )
        
        # Extract response
        result_text = response.content[0].text
        
        # Parse and validate JSON (handle markdown code blocks)
        try:
            result = json.loads(result_text)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code block
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', result_text, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group(1))
                except json.JSONDecodeError as e:
                    print(f"ERROR: Claude returned invalid JSON: {e}", file=sys.stderr)
                    print(f"       Response: {result_text[:200]}...", file=sys.stderr)
                    sys.exit(3)
            else:
                print(f"ERROR: Claude returned invalid JSON", file=sys.stderr)
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
        print(f"  Input tokens: {response.usage.input_tokens}")
        print(f"  Output tokens: {response.usage.output_tokens}")
        
        # Calculate cost (Sonnet 4: $3/MTok input, $15/MTok output)
        input_cost = response.usage.input_tokens * 3 / 1_000_000
        output_cost = response.usage.output_tokens * 15 / 1_000_000
        print(f"  Cost: ${input_cost + output_cost:.4f}")
        
    except anthropic.APIError as e:
        print(f"ERROR: Claude API error: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"ERROR: Claude API call failed: {e}", file=sys.stderr)
        sys.exit(2)
    
    sys.exit(0)


if __name__ == "__main__":
    main()

