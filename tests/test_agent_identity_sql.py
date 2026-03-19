#!/usr/bin/env python3
"""Test agent identity tracking in SQL layer."""

import sys
import os
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.sql_db import SQLDatabase


def test_agent_identity_stored():
    """Test that agent identity is stored and retrieved correctly."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    try:
        db = SQLDatabase(db_path)
        
        # Test storing with agent identity
        interaction = {
            'project_name': 'test',
            'user_message': 'Hello',
            'assistant_message': 'Hi there',
            'imported_by_agent': 'codex',
            'imported_by_model': 'o3'
        }
        
        uuid = db.store_interaction(interaction)
        stored = db.get_interaction_by_uuid(uuid)
        
        assert stored['imported_by_agent'] == 'codex', f"Expected codex, got {stored['imported_by_agent']}"
        assert stored['imported_by_model'] == 'o3', f"Expected o3, got {stored['imported_by_model']}"
        print("[PASS] Agent identity stored and retrieved correctly")
        
    finally:
        os.unlink(db_path)


def test_agent_identity_in_hash():
    """Test that agent identity is included in content hash."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    try:
        db = SQLDatabase(db_path)
        
        # Create two interactions with same content but different agents
        base = {
            'project_name': 'test',
            'user_message': 'Hello',
            'assistant_message': 'Hi there',
            'timestamp': '2026-03-11T00:00:00'
        }
        
        # First interaction - no agent
        int1 = {**base}
        uuid1 = db.store_interaction(int1)
        stored1 = db.get_interaction_by_uuid(uuid1)
        
        # Create new db for second test (to reset chain)
        os.unlink(db_path)
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        db2 = SQLDatabase(db_path)
        
        # Second interaction - with agent
        int2 = {**base, 'imported_by_agent': 'codex', 'imported_by_model': 'o3'}
        uuid2 = db2.store_interaction(int2)
        stored2 = db2.get_interaction_by_uuid(uuid2)
        
        # Hashes should be different because agent identity is included
        assert stored1['content_hash'] != stored2['content_hash'], \
            "Hashes should differ when agent identity is included"
        print("[PASS] Agent identity affects content hash")
        
    finally:
        os.unlink(db_path)


def test_legacy_null_agent():
    """Test that legacy data with NULL agent fields still works."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    try:
        db = SQLDatabase(db_path)
        
        # Store without agent (simulates legacy data)
        interaction = {
            'project_name': 'test',
            'user_message': 'Hello',
            'assistant_message': 'Hi there'
        }
        
        uuid = db.store_interaction(interaction)
        stored = db.get_interaction_by_uuid(uuid)
        
        assert stored['imported_by_agent'] is None
        assert stored['imported_by_model'] is None
        assert stored['content_hash'] is not None
        print("[PASS] Legacy NULL agent fields work correctly")
        
    finally:
        os.unlink(db_path)


def main():
    print("=" * 60)
    print("Testing Agent Identity SQL Layer")
    print("=" * 60)
    print()
    
    test_agent_identity_stored()
    test_agent_identity_in_hash()
    test_legacy_null_agent()
    
    print()
    print("=" * 60)
    print("All tests passed!")
    print("=" * 60)


if __name__ == '__main__':
    main()

