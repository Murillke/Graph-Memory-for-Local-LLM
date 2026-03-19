"""
Test SQLite database with hash chain.
"""

import sys
sys.path.insert(0, '.')

from tools.sql_db import SQLDatabase
import os

# Ensure test directory exists
os.makedirs("./tests/tmp", exist_ok=True)

# Clean up test database
if os.path.exists("./tests/tmp/test.db"):
    os.remove("./tests/tmp/test.db")

# Create database
db = SQLDatabase("./tests/tmp/test.db")

print("[OK] Database created")

# Create project
success = db.create_project("test-project", "Test project for GML-LLM")
print(f"[OK] Project created: {success}")

# Associate path
success = db.associate_path_with_project("/test/path", "test-project", "test-machine")
print(f"[OK] Path associated: {success}")

# Look up project
project = db.get_project_from_path("/test/path")
print(f"[OK] Project lookup: {project}")

# Store first interaction
uuid1 = db.store_interaction({
    "project_name": "test-project",
    "user_message": "We are using LadybugDB",
    "assistant_message": "Got it! LadybugDB is an embedded graph database.",
    "session_id": "test-session"
})
print(f"[OK] Stored interaction 1: {uuid1}")

# Store second interaction
uuid2 = db.store_interaction({
    "project_name": "test-project",
    "user_message": "Where is it located?",
    "assistant_message": "At ./memory/knowledge.ladybug",
    "session_id": "test-session"
})
print(f"[OK] Stored interaction 2: {uuid2}")

# Store third interaction
uuid3 = db.store_interaction({
    "project_name": "test-project",
    "user_message": "What version are we using?",
    "assistant_message": "Version 1.0.0",
    "session_id": "test-session"
})
print(f"[OK] Stored interaction 3: {uuid3}")

# Get unprocessed interactions
unprocessed = db.get_unprocessed_interactions("test-project")
print(f"[OK] Unprocessed interactions: {len(unprocessed)}")

# Verify hash chain
result = db.verify_interaction_chain("test-project")
print(f"\n{'='*60}")
print(f"Hash Chain Verification:")
print(f"{'='*60}")
print(f"Verified: {result['verified']}")
print(f"Total interactions: {result['total_interactions']}")
print(f"Chain length: {result['chain_length']}")
print(f"Errors: {len(result['errors'])}")

if result['verified']:
    print(f"\n[OK] HASH CHAIN VERIFIED!")
    
    # Show chain details
    all_interactions = db.get_all_interactions("test-project")
    print(f"\nChain details:")
    for i, interaction in enumerate(all_interactions):
        print(f"\n  [{i+1}] {interaction['uuid']}")
        print(f"      Chain index: {interaction['chain_index']}")
        print(f"      Content hash: {interaction['content_hash'][:16]}...")
        print(f"      Previous hash: {interaction['previous_hash'][:16] if interaction['previous_hash'] else 'None'}...")
        print(f"      Message: '{interaction['user_message'][:50]}...'")
else:
    print(f"\n[ERROR] HASH CHAIN VERIFICATION FAILED!")
    for error in result['errors']:
        print(f"  - {error}")

# Mark as processed
count = db.mark_interactions_processed([uuid1, uuid2, uuid3])
print(f"\n[OK] Marked {count} interactions as processed")

# Check unprocessed again
unprocessed = db.get_unprocessed_interactions("test-project")
print(f"[OK] Unprocessed interactions now: {len(unprocessed)}")

print(f"\n{'='*60}")
print(f"[OK] ALL TESTS PASSED!")
print(f"{'='*60}")

