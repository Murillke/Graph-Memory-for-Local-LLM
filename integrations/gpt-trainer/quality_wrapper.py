"""
GPT-trainer.com quality check wrapper for contradiction and duplicate detection.

This wrapper uses GPT-trainer.com API to review quality check questions.
The chatbot can use any backing model (Claude, GPT-4o, etc.) configured in GPT-trainer.

Environment variables required:
    GPT_TRAINER_QUALITY_API_KEY: Your GPT-trainer API key
    GPT_TRAINER_QUALITY_CHATBOT_UUID: UUID of the chatbot to use

Exit codes:
    0: Success
    1: Invalid arguments or environment setup
    2: API call failed (Network/Auth)
    3: Invalid response (Bad JSON after all retries)

Usage:
    python integrations/gpt-trainer/quality_wrapper.py QUESTIONS_FILE ANSWERS_FILE
"""

import sys
import os
import json
import re
import requests
import time

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from tools.quality.prompts import get_quality_check_prompt

MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

def call_gpt_trainer_api(api_key, chatbot_uuid, query):
    """Call GPT-trainer API."""
    url = f"https://app.gpt-trainer.com/api/v1/chatbot/{chatbot_uuid}/query"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "query": query,
        "stream": False
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=120)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        print(f"[ERROR] API request timed out after 120 seconds", file=sys.stderr)
        return None
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] API request failed: {e}", file=sys.stderr)
        return None

def sanitize_json(response_text):
    """Extract and clean JSON from response text."""
    # Try to find JSON in Markdown code blocks
    json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
    if json_match:
        return json_match.group(1)
    
    # Try to find JSON object directly
    json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
    if json_match:
        return json_match.group(0)
    
    # Return as-is if no pattern found
    return response_text

def main():
    # Validate arguments
    if len(sys.argv) != 3:
        print("[ERROR] Usage: quality_wrapper.py QUESTIONS_FILE ANSWERS_FILE", file=sys.stderr)
        sys.exit(1)
    
    questions_file = sys.argv[1]
    answers_file = sys.argv[2]
    
    # Validate environment variables
    api_key = os.environ.get('GPT_TRAINER_QUALITY_API_KEY')
    chatbot_uuid = os.environ.get('GPT_TRAINER_QUALITY_CHATBOT_UUID')
    
    if not api_key:
        print("[ERROR] GPT_TRAINER_QUALITY_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)
    
    if not chatbot_uuid:
        print("[ERROR] GPT_TRAINER_QUALITY_CHATBOT_UUID environment variable not set", file=sys.stderr)
        sys.exit(1)
    
    # Read questions
    try:
        with open(questions_file, 'r', encoding='utf-8') as f:
            questions = json.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to read questions file: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Build prompt using the CORRECT prompts from tools/quality/prompts.py
    messages = get_quality_check_prompt(questions)
    
    # Convert messages to single query
    query_parts = []
    for msg in messages:
        if msg['role'] == 'system':
            query_parts.append(f"SYSTEM INSTRUCTIONS:\n{msg['content']}")
        elif msg['role'] == 'user':
            query_parts.append(f"USER REQUEST:\n{msg['content']}")
    
    query = "\n\n".join(query_parts)
    
    # Try quality check with retries
    for attempt in range(MAX_RETRIES):
        print(f"[INFO] Calling GPT-trainer API (attempt {attempt + 1}/{MAX_RETRIES})...")
        
        response_data = call_gpt_trainer_api(api_key, chatbot_uuid, query)
        
        if not response_data:
            sys.exit(2)
        
        response_text = response_data.get('data', '')
        
        if not response_text:
            print("[ERROR] Empty response from API", file=sys.stderr)
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
                continue
            sys.exit(3)
        
        # Sanitize and parse JSON
        clean_json = sanitize_json(response_text)
        
        try:
            result = json.loads(clean_json)
            
            # Validate structure - should have 'decisions' key
            if 'decisions' not in result:
                raise ValueError("Response missing 'decisions' key")
            
            # Success!
            with open(answers_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2)
            print(f"[SUCCESS] Quality check complete: {answers_file}")
            sys.exit(0)
            
        except (json.JSONDecodeError, ValueError) as e:
            print(f"[WARN] Attempt {attempt + 1} failed: {e}", file=sys.stderr)
            
            if attempt < MAX_RETRIES - 1:
                # Retry with correction prompt
                query = f"{query}\n\nYour previous response had invalid JSON. Please provide ONLY valid JSON with no markdown, no explanations, just the JSON object with a 'decisions' array."
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                print(f"[ERROR] All {MAX_RETRIES} attempts failed", file=sys.stderr)
                print(f"[DEBUG] Last response: {response_text[:500]}", file=sys.stderr)
                sys.exit(3)

if __name__ == '__main__':
    main()

