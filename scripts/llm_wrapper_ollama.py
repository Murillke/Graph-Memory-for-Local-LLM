#!/usr/bin/env python3
"""
LLM Wrapper for Ollama (Local LLM)

Standard interface for quality checking with Ollama's local models.
Requires Ollama to be installed and running locally.

Installation:
    1. Install Ollama: https://ollama.ai/download
    2. Pull a model: ollama pull llama3.1
    3. Start Ollama service (usually auto-starts)

Usage:
    python llm_wrapper_ollama.py <questions_file> <answers_file> <prompt_file>

Arguments:
    questions_file - Path to JSON file with quality questions
    answers_file   - Path where answers should be written (JSON)
    prompt_file    - Path to markdown file with criteria/instructions

Environment:
    OLLAMA_MODEL - Model to use (default: llama3.1)
    OLLAMA_HOST  - Ollama server URL (default: http://localhost:11434)

Exit codes:
    0 - Success
    1 - Invalid arguments or Ollama not available
    2 - Ollama API call failed
    3 - Invalid response from Ollama

Example:
    # Using default model (llama3.1)
    python llm_wrapper_ollama.py \\
        quality-questions.json \\
        quality-answers.json \\
        prompts/quality-check-contradictions.md
    
    # Using specific model
    export OLLAMA_MODEL="mistral"
    python llm_wrapper_ollama.py \\
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
    
    # Validate input files exist
    if not os.path.exists(questions_file):
        print(f"ERROR: Questions file not found: {questions_file}", file=sys.stderr)
        sys.exit(1)
    
    if not os.path.exists(prompt_file):
        print(f"ERROR: Prompt file not found: {prompt_file}", file=sys.stderr)
        sys.exit(1)
    
    # Import requests (for Ollama API)
    try:
        import requests
    except ImportError:
        print("ERROR: requests package not installed", file=sys.stderr)
        print("       Install with: pip install requests", file=sys.stderr)
        sys.exit(1)
    
    # Get configuration from environment
    model = os.getenv('OLLAMA_MODEL', 'llama3.1')
    host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
    
    # Check if Ollama is running
    print(f"[1/4] Checking Ollama service at {host}...")
    try:
        response = requests.get(f"{host}/api/tags", timeout=5)
        if response.status_code != 200:
            print(f"ERROR: Ollama service not responding properly", file=sys.stderr)
            print(f"       Make sure Ollama is running: ollama serve", file=sys.stderr)
            sys.exit(1)
        
        # Check if model is available
        models = response.json().get('models', [])
        model_names = [m['name'] for m in models]
        if not any(model in name for name in model_names):
            print(f"ERROR: Model '{model}' not found", file=sys.stderr)
            print(f"       Available models: {', '.join(model_names)}", file=sys.stderr)
            print(f"       Pull model with: ollama pull {model}", file=sys.stderr)
            sys.exit(1)
        
        print(f"      ✓ Ollama is running")
        print(f"      ✓ Model '{model}' is available")
    
    except requests.exceptions.ConnectionError:
        print(f"ERROR: Cannot connect to Ollama at {host}", file=sys.stderr)
        print(f"       Make sure Ollama is running: ollama serve", file=sys.stderr)
        print(f"       Or set OLLAMA_HOST environment variable", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to check Ollama: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Read prompt and questions
    print(f"[2/4] Reading prompt from {prompt_file}...")
    with open(prompt_file, 'r', encoding='utf-8') as f:
        prompt = f.read()
    
    print(f"[3/4] Reading questions from {questions_file}...")
    with open(questions_file, 'r', encoding='utf-8') as f:
        questions = json.load(f)
    
    # Build the full prompt
    full_prompt = f"""{prompt}

---

Here are the questions to review:

{json.dumps(questions, indent=2)}

Please provide your answers in valid JSON format following the structure specified above.
"""
    
    # Call Ollama API
    print(f"[4/4] Calling Ollama API (model: {model})...")
    print(f"      (This may take a few minutes for large question sets...)")
    
    try:
        response = requests.post(
            f"{host}/api/generate",
            json={
                "model": model,
                "prompt": full_prompt,
                "stream": False,
                "format": "json",  # Request JSON output
                "options": {
                    "temperature": 0.1,  # Low temperature for consistent responses
                    "num_predict": 4096  # Allow longer responses
                }
            },
            timeout=300  # 5 minute timeout for large requests
        )
        
        if response.status_code != 200:
            print(f"ERROR: Ollama API returned status {response.status_code}", file=sys.stderr)
            print(f"       Response: {response.text}", file=sys.stderr)
            sys.exit(2)
        
        # Extract response
        result = response.json()
        answer_text = result.get('response', '')
        
        if not answer_text:
            print(f"ERROR: Ollama returned empty response", file=sys.stderr)
            sys.exit(2)
        
        # Parse and validate JSON
        try:
            answers = json.loads(answer_text)
        except json.JSONDecodeError as e:
            print(f"ERROR: Ollama returned invalid JSON: {e}", file=sys.stderr)
            print(f"       Response: {answer_text[:500]}...", file=sys.stderr)
            sys.exit(3)
        
        # Write answers to file
        with open(answers_file, 'w', encoding='utf-8') as f:
            json.dump(answers, f, indent=2)
        
        print(f"✓ Success! Answers written to {answers_file}")
        print(f"  Model: {model}")
        print(f"  Tokens: {result.get('eval_count', 'N/A')}")
        print(f"  Time: {result.get('total_duration', 0) / 1e9:.1f}s")
        
    except requests.exceptions.Timeout:
        print(f"ERROR: Ollama request timed out", file=sys.stderr)
        print(f"       Try a smaller question set or increase timeout", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"ERROR: Ollama API call failed: {e}", file=sys.stderr)
        sys.exit(2)
    
    sys.exit(0)


if __name__ == "__main__":
    main()

