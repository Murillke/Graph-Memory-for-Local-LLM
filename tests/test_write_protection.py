#!/usr/bin/env python3
"""
Test write protection mechanisms.

Tests:
1. Read-only connection blocks writes
2. Triggers prevent unauthorized updates
3. Triggers prevent hard deletes
4. Soft delete still works
"""

import sys
import os
import sqlite3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tools.sql_db import SQLDatabase
from tools.sql_db_readonly import SQLDatabaseReadOnly

# Ensure test directory exists
os.makedirs("./tests/tmp", exist_ok=True)


def test_readonly_connection():
    """Test that read-only connection blocks all writes."""
    print("\n" + "="*60)
    print("TEST 1: Read-Only Connection Blocks Writes")
    print("="*60)
    
    # Create database with some data
    db = SQLDatabase("./tests/tmp/test-writeprotect.db")
    db.create_project("test-project", "Test project")
    
    interaction = {
        "project_name": "test-project",
        "user_message": "Hello",
        "assistant_message": "Hi there!"
    }
    uuid = db.store_interaction(interaction)
    print(f"[OK] Created interaction: {uuid}")
    
    # Try to use read-only connection
    readonly_db = SQLDatabaseReadOnly("./tests/tmp/test-writeprotect.db")
    
    # Read operations should work
    project = readonly_db.get_project_by_name("test-project")
    assert project is not None
    print(f"[OK] Read operation works: {project['name']}")
    
    # Write operations should fail
    try:
        readonly_db.create_project("new-project", "Should fail")
        assert False, "Write operation should have been blocked!"
    except PermissionError as e:
        print(f"[OK] Write blocked: {e}")

    try:
        readonly_db.store_interaction(interaction)
        assert False, "Write operation should have been blocked!"
    except PermissionError as e:
        print(f"[OK] Write blocked: {e}")


def test_trigger_prevents_hash_update():
    """Test that triggers prevent hash chain modification."""
    print("\n" + "="*60)
    print("TEST 2: Triggers Prevent Hash Chain Modification")
    print("="*60)
    
    db = SQLDatabase("./tests/tmp/test-writeprotect.db")
    
    # Get an interaction
    interactions = db.get_all_interactions("test-project")
    interaction = interactions[0]
    
    print(f"Original hash: {interaction['content_hash'][:16]}...")
    
    # Try to modify hash chain fields directly
    conn = sqlite3.connect("./tests/tmp/test-writeprotect.db")
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE interactions
            SET content_hash = 'tampered-hash'
            WHERE uuid = ?
        """, (interaction['uuid'],))
        conn.commit()
        assert False, "Hash modification should have been blocked!"
    except sqlite3.IntegrityError as e:
        print(f"[OK] Hash modification blocked: {e}")

    try:
        cursor.execute("""
            UPDATE interactions
            SET chain_index = 999
            WHERE uuid = ?
        """, (interaction['uuid'],))
        conn.commit()
        assert False, "Chain index modification should have been blocked!"
    except sqlite3.IntegrityError as e:
        print(f"[OK] Chain index modification blocked: {e}")

    conn.close()


def test_trigger_prevents_content_update():
    """Test that triggers prevent content modification."""
    print("\n" + "="*60)
    print("TEST 3: Triggers Prevent Content Modification")
    print("="*60)
    
    db = SQLDatabase("./tests/tmp/test-writeprotect.db")
    
    # Get an interaction
    interactions = db.get_all_interactions("test-project")
    interaction = interactions[0]
    
    print(f"Original message: {interaction['user_message'][:20]}...")
    
    # Try to modify content directly
    conn = sqlite3.connect("./tests/tmp/test-writeprotect.db")
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE interactions
            SET user_message = 'Tampered message'
            WHERE uuid = ?
        """, (interaction['uuid'],))
        conn.commit()
        assert False, "Content modification should have been blocked!"
    except sqlite3.IntegrityError as e:
        print(f"[OK] Content modification blocked: {e}")

    try:
        cursor.execute("""
            UPDATE interactions
            SET assistant_message = 'Tampered response'
            WHERE uuid = ?
        """, (interaction['uuid'],))
        conn.commit()
        assert False, "Content modification should have been blocked!"
    except sqlite3.IntegrityError as e:
        print(f"[OK] Content modification blocked: {e}")

    conn.close()


def test_trigger_prevents_hard_delete():
    """Test that triggers prevent hard deletes."""
    print("\n" + "="*60)
    print("TEST 4: Triggers Prevent Hard Deletes")
    print("="*60)
    
    db = SQLDatabase("./tests/tmp/test-writeprotect.db")
    
    # Get an interaction
    interactions = db.get_all_interactions("test-project")
    interaction = interactions[0]
    
    # Try to hard delete
    conn = sqlite3.connect("./tests/tmp/test-writeprotect.db")
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            DELETE FROM interactions
            WHERE uuid = ?
        """, (interaction['uuid'],))
        conn.commit()
        assert False, "Hard delete should have been blocked!"
    except sqlite3.IntegrityError as e:
        print(f"[OK] Hard delete blocked: {e}")

    conn.close()


def test_soft_delete_still_works():
    """Test that soft delete still works."""
    print("\n" + "="*60)
    print("TEST 5: Soft Delete Still Works")
    print("="*60)

    db = SQLDatabase("./tests/tmp/test-writeprotect.db")

    # Get an interaction
    interactions = db.get_all_interactions("test-project")
    interaction = interactions[0]

    # Soft delete should work (only updating deleted_at)
    conn = sqlite3.connect("./tests/tmp/test-writeprotect.db")
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE interactions
            SET deleted_at = CURRENT_TIMESTAMP
            WHERE uuid = ?
        """, (interaction['uuid'],))
        conn.commit()
        print(f"[OK] Soft delete works (deleted_at can be updated)")
    except sqlite3.IntegrityError as e:
        assert False, f"Soft delete should work! {e}"

    conn.close()


def test_allowed_updates():
    """Test that allowed updates still work."""
    print("\n" + "="*60)
    print("TEST 6: Allowed Updates Still Work")
    print("="*60)

    db = SQLDatabase("./tests/tmp/test-writeprotect.db")

    # Create a new interaction for this test
    interaction_data = {
        "project_name": "test-project",
        "user_message": "Test message",
        "assistant_message": "Test response"
    }
    uuid = db.store_interaction(interaction_data)
    interaction = db.get_interaction_by_uuid(uuid)
    
    # These updates should be allowed
    conn = sqlite3.connect("./tests/tmp/test-writeprotect.db")
    cursor = conn.cursor()
    
    try:
        # Update processed flag (allowed)
        cursor.execute("""
            UPDATE interactions
            SET processed = TRUE, extracted_at = CURRENT_TIMESTAMP
            WHERE uuid = ?
        """, (interaction['uuid'],))
        conn.commit()
        print(f"[OK] Allowed update works (processed flag)")

        # Update metadata (allowed)
        cursor.execute("""
            UPDATE interactions
            SET session_id = 'test-session', token_count = 100
            WHERE uuid = ?
        """, (interaction['uuid'],))
        conn.commit()
        print(f"[OK] Allowed update works (metadata)")

    except sqlite3.IntegrityError as e:
        assert False, f"Allowed updates should work! {e}"

    conn.close()


if __name__ == '__main__':
    # Clean up
    import shutil
    if os.path.exists("./tests/tmp/test-writeprotect.db"):
        os.remove("./tests/tmp/test-writeprotect.db")
    
    print("="*60)
    print("Testing Write Protection Mechanisms")
    print("="*60)
    
    all_passed = True
    
    all_passed &= test_readonly_connection()
    all_passed &= test_trigger_prevents_hash_update()
    all_passed &= test_trigger_prevents_content_update()
    all_passed &= test_trigger_prevents_hard_delete()
    all_passed &= test_soft_delete_still_works()
    all_passed &= test_allowed_updates()
    
    print("\n" + "="*60)
    if all_passed:
        print("[OK] ALL WRITE PROTECTION TESTS PASSED!")
    else:
        print("[ERROR] SOME TESTS FAILED!")
    print("="*60)
    
    # Clean up
    if os.path.exists("./tests/tmp/test-writeprotect.db"):
        os.remove("./tests/tmp/test-writeprotect.db")
    
    sys.exit(0 if all_passed else 1)

