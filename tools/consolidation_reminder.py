#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Consolidation Reminder System

Checks if consolidation should be recommended and displays helpful reminders.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path


def check_consolidation_reminder(config_path='mem.config.json'):
    """
    Check if consolidation should be recommended.
    
    Returns:
        tuple: (should_recommend: bool, days_since_last: int, message: str)
    """
    # Load config
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
    except Exception:
        return False, 0, ""
    
    consolidation_config = config.get('consolidation', {})
    
    # Check if recommendations are enabled
    recommend_after_days = consolidation_config.get('recommend_after_days', 30)
    if recommend_after_days == 0:
        return False, 0, ""  # Recommendations disabled
    
    # Get last run timestamp
    last_run = consolidation_config.get('last_run_timestamp', '0')
    
    # Initialize if never run
    if last_run == '0':
        # First time - initialize to now
        update_last_run_timestamp(config_path)
        return False, 0, ""  # Don't recommend on first run
    
    # Calculate days since last run
    try:
        last_run_dt = datetime.fromisoformat(last_run)
        now = datetime.now()
        days_since = (now - last_run_dt).days
    except Exception:
        # Invalid timestamp, reset it
        update_last_run_timestamp(config_path)
        return False, 0, ""
    
    # Check if recommendation should be shown
    if days_since >= recommend_after_days:
        message = generate_recommendation_message(days_since, recommend_after_days)
        return True, days_since, message
    
    return False, days_since, ""


def generate_recommendation_message(days_since, recommend_after):
    """Generate a helpful recommendation message."""
    
    message = f"""
{'='*80}
💡 CONSOLIDATION RECOMMENDATION
{'='*80}

It's been {days_since} days since you last ran consolidation analysis.

Running consolidation helps you:
  • Discover hub entities (central concepts in your knowledge)
  • Find clusters (groups of related topics)
  • Identify relationship patterns (how things connect)
  • Track knowledge evolution over time

Recommended command:
  python scripts/consolidate_knowledge.py --project llm_memory --store

This will:
  ✓ Analyze your current knowledge graph
  ✓ Store insights with cryptographic proofs
  ✓ Update the last-run timestamp
  ✓ Help you understand your knowledge structure

To disable these reminders, set "recommend_after_days": 0 in mem.config.json

{'='*80}
"""
    return message


def update_last_run_timestamp(config_path='mem.config.json'):
    """Update the last run timestamp to now."""
    try:
        # Load config
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # Update timestamp
        if 'consolidation' not in config:
            config['consolidation'] = {}
        
        config['consolidation']['last_run_timestamp'] = datetime.now().isoformat()
        
        # Save config
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        return True
    except Exception as e:
        print(f"[WARN] Failed to update consolidation timestamp: {e}")
        return False


def show_recommendation_if_needed(config_path='mem.config.json'):
    """
    Check and show consolidation recommendation if needed.
    Call this at the end of store_extraction.py or other scripts.
    """
    should_recommend, days_since, message = check_consolidation_reminder(config_path)
    
    if should_recommend:
        print(message)
    
    return should_recommend

