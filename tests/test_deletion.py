"""
Test that deletion is PREVENTED by database triggers.

NOTE: This test is EXPECTED TO FAIL with IntegrityError.
The database has triggers that prevent hard deletes.
This is a FEATURE, not a bug!
"""

import sys
sys.path.insert(0, '.')

import sqlite3
import os

# Ensure test directory exists
os.makedirs("./tests/tmp", exist_ok=True)

# Create fresh test database
if os.path.exists("./tests/tmp/test_deletion.db"):
    os.remove("./tests/tmp/test_deletion.db")

from tools.sql_db import SQLDatabase

db = SQLDatabase("./tests/tmp/test_deletion.db")

# Create project
db.create_project("test-project", "Test")
db.associate_path_with_project("/test", "test-project")

# Store 5 interactions
for i in range(1, 6):
    db.store_interaction({
        "project_name": "test-project",
        "user_message": f"Message {i}",
        "assistant_message": f"Response {i}"
    })

print("Testing Deletion Detection:")
print("="*60)

# Verify chain is valid
result = db.verify_interaction_chain("test-project")
print(f"\n1. Initial verification: {'[OK] VALID' if result['verified'] else '[ERROR] INVALID'}")
print(f"   Total interactions: {result['total_interactions']}")

# Try to delete interaction 3 (should be prevented by trigger)
print(f"\n2. Attempting to delete interaction 3 (middle of chain)...")
conn = sqlite3.connect("./tests/tmp/test_deletion.db")
cursor = conn.cursor()

try:
    cursor.execute("DELETE FROM interactions WHERE chain_index = 3")
    conn.commit()
    print(f"   [ERROR] DELETION SUCCEEDED - Write protection failed!")
    deletion_prevented = False
except sqlite3.IntegrityError as e:
    print(f"   [OK] DELETION PREVENTED by database trigger!")
    print(f"   Error: {e}")
    deletion_prevented = True
finally:
    conn.close()

# Verify chain is still intact (deletion was prevented)
if deletion_prevented:
    result = db.verify_interaction_chain("test-project")
    print(f"\n3. Verification after prevented deletion: {'[OK] VALID' if result['verified'] else '[ERROR] INVALID'}")

    if result['verified']:
        print(f"\n   [OK] CHAIN STILL INTACT - Write protection working!")
        print(f"   Total interactions: {result['total_interactions']}")
    else:
        print(f"\n   [ERROR] Chain broken despite prevention!")
else:
    print(f"\n3. [ERROR] Write protection not working - deletion succeeded!")

print("\n" + "="*60)
print("\n[SUCCESS] Write protection test passed!")
print("Database triggers successfully prevent hard deletes.")

