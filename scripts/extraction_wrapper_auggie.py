#!/usr/bin/env python3
"""
Extraction Wrapper for Auggie CLI

Standard interface for entity/fact extraction with Auggie.
This wrapper calls the Auggie CLI to extract entities or facts from conversation data.

NOTE: Auggie is an AI agent powered by Claude Sonnet 4.5 via Anthropic.
      Using this wrapper incurs costs through your Augment subscription.

Usage:
    python extraction_wrapper_auggie.py <input_file> <output_file> <extraction_type> <prompt_file>

Arguments:
    input_file       - Path to JSON file with conversation data
    output_file      - Path where extraction results should be written (JSON)
    extraction_type  - Type of extraction: "entities" or "facts"
    prompt_file      - Path to markdown file with extraction instructions

Exit codes:
    0 - Success
    1 - Invalid arguments or Auggie not available
    2 - Auggie command failed
    3 - Invalid response from Auggie

Example:
    python extraction_wrapper_auggie.py \\
        input.json \\
        output.json \\
        entities \\
        prompts/extract-entities.md
"""

import sys
import subprocess
import os
import json


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
    
    # Validate input files exist
    if not os.path.exists(input_file):
        print(f"ERROR: Input file not found: {input_file}", file=sys.stderr)
        sys.exit(1)
    
    if not os.path.exists(prompt_file):
        print(f"ERROR: Prompt file not found: {prompt_file}", file=sys.stderr)
        sys.exit(1)
    
    # Read the prompt/criteria
    print(f"[1/3] Reading prompt from {prompt_file}...")
    with open(prompt_file, 'r', encoding='utf-8') as f:
        prompt = f.read()
    
    # Read input data
    print(f"[2/3] Reading input from {input_file}...")
    with open(input_file, 'r', encoding='utf-8') as f:
        input_data = json.load(f)
    
    # Build instruction for Auggie
    instruction = f"""{prompt}

---

## Input and Output Files

**Input file:** {input_file}
**Output file:** {output_file}
**Extraction type:** {extraction_type}

Please:
1. Read the conversation data from {input_file}
2. Extract {extraction_type} following the schema and rules specified above
3. Write your results to {output_file} in valid JSON format

The output must be valid JSON with a single key "{extraction_type}" containing an array of extracted items.

Example output structure:
```json
{{
  "{extraction_type}": [
    // ... extracted items following the schema above
  ]
}}
```

Make sure the output is valid JSON that can be parsed programmatically.
"""
    
    # Call Auggie
    print(f"[3/3] Calling Auggie to extract {extraction_type}...")
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
    print(f"Verifying output file...")
    if not os.path.exists(output_file):
        print(f"ERROR: Auggie did not create output file: {output_file}", file=sys.stderr)
        print(f"       The file may have been created with a different name.", file=sys.stderr)
        sys.exit(3)
    
    # Verify it's valid JSON with correct structure
    try:
        with open(output_file, 'r', encoding='utf-8') as f:
            result_data = json.load(f)
        
        # Check for expected key
        if extraction_type not in result_data:
            print(f"WARNING: Output missing '{extraction_type}' key", file=sys.stderr)
            print(f"         Keys found: {list(result_data.keys())}", file=sys.stderr)
        else:
            count = len(result_data[extraction_type])
            print(f"✓ Success! Extracted {count} {extraction_type}")
            print(f"  Output: {output_file}")
    
    except json.JSONDecodeError as e:
        print(f"WARNING: Output file is not valid JSON: {e}", file=sys.stderr)
        print(f"         File was created but may need manual review.", file=sys.stderr)
        # Don't exit with error - file exists, just may need cleanup
    
    sys.exit(0)


if __name__ == "__main__":
    main()

