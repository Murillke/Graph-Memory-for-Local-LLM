#!/usr/bin/env python3
"""
Temp file cleanup reminder system.

Checks if temp file cleanup should be recommended based on config settings.
"""

import json
from datetime import datetime, timedelta


def check_cleanup_reminder(config_path='mem.config.json'):
    """
    Check if temp file cleanup should be recommended.
    
    Returns:
        tuple: (should_recommend: bool, days_since_last: int, message: str)
    """
    # Load config
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
    except Exception:
        return False, 0, ""
    
    cleanup_config = config.get('temp_file_cleanup', {})
    
    # Check if recommendations are enabled
    if not cleanup_config.get('enabled', True):
        return False, 0, ""
    
    recommend_after_days = cleanup_config.get('recommend_after_days', 30)
    if recommend_after_days == 0:
        return False, 0, ""  # Recommendations disabled
    
    # Get last cleanup timestamp
    last_cleanup = cleanup_config.get('last_cleanup_timestamp')
    
    if not last_cleanup:
        # Never cleaned up - recommend
        return True, 999, generate_recommendation_message(999, recommend_after_days, first_time=True)
    
    # Parse timestamp
    try:
        last_cleanup_dt = datetime.fromisoformat(last_cleanup)
    except Exception:
        return False, 0, ""
    
    # Calculate days since last cleanup
    days_since = (datetime.now() - last_cleanup_dt).days
    
    # Check if we should recommend
    if days_since >= recommend_after_days:
        message = generate_recommendation_message(days_since, recommend_after_days)
        return True, days_since, message
    
    return False, days_since, ""


def generate_recommendation_message(days_since, recommend_after, first_time=False):
    """Generate a helpful recommendation message."""
    
    if first_time:
        message = f"""
{'='*80}
TEMP FILE CLEANUP RECOMMENDATION
{'='*80}

You have never run temp file cleanup!

Temp files (conversation_*.json, extraction_*.json) accumulate over time.
These files are kept for hash source validation but can be cleaned up safely.

Recommended command:
  python scripts/cleanup_temp_files.py

This will:
  - Remove temp files older than 30 days (configurable)
  - Keep recent files for validation
  - Update the last-cleanup timestamp
  - Free up disk space

To see what would be deleted without deleting:
  python scripts/cleanup_temp_files.py --dry-run

To disable these reminders:
  Set "recommend_after_days": 0 in mem.config.json

{'='*80}
"""
    else:
        message = f"""
{'='*80}
TEMP FILE CLEANUP RECOMMENDATION
{'='*80}

It's been {days_since} days since you last cleaned up temp files.

Temp files (conversation_*.json, extraction_*.json) may have accumulated.

Recommended command:
  python scripts/cleanup_temp_files.py

This will:
  - Remove temp files older than 30 days (configurable)
  - Keep recent files for validation
  - Update the last-cleanup timestamp
  - Free up disk space

To see what would be deleted without deleting:
  python scripts/cleanup_temp_files.py --dry-run

To change cleanup frequency:
  Edit "recommend_after_days" in mem.config.json

To disable these reminders:
  Set "recommend_after_days": 0 in mem.config.json

{'='*80}
"""
    
    return message


def show_recommendation_if_needed(config_path='mem.config.json'):
    """
    Check and show cleanup recommendation if needed.
    Call this at the end of store_extraction.py or other scripts.
    """
    should_recommend, days_since, message = check_cleanup_reminder(config_path)
    
    if should_recommend:
        print(message)
    
    return should_recommend


if __name__ == "__main__":
    # Test the reminder
    show_recommendation_if_needed()

