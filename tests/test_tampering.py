"""
Test that tampering is detected.
"""

import sys
sys.path.insert(0, '.')

from tools.sql_db import SQLDatabase
import sqlite3
import os
import shutil

# Use tests/tmp/ for test databases, not memory/
os.makedirs("./tests/tmp", exist_ok=True)
db_path = "./tests/tmp/test_tampering.db"

if os.path.exists(db_path):
    os.remove(db_path)

db = SQLDatabase(db_path)
db.create_project("test-project", "Tamper detection test project")
for i in range(3):
    db.store_interaction({
        "project_name": "test-project",
        "user_message": f"Original message {i}",
        "assistant_message": f"Original response {i}",
    })

print("Testing Tamper Detection:")
print("="*60)

# First verify chain is valid
result = db.verify_interaction_chain("test-project")
print(f"\n1. Initial verification: {'[OK] VALID' if result['verified'] else '[ERROR] INVALID'}")

# Now tamper with the database directly
print(f"\n2. Tampering with interaction 2...")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

tamper_blocked = False
try:
    cursor.execute("""
        UPDATE interactions 
        SET user_message = 'TAMPERED MESSAGE' 
        WHERE chain_index = 2
    """)
    conn.commit()
    print(f"   [ERROR] Direct tampering unexpectedly succeeded")
except sqlite3.IntegrityError as e:
    tamper_blocked = True
    print(f"   [OK] Direct tampering blocked by trigger: {e}")
finally:
    conn.close()

# Verify again - should remain valid because tampering was blocked
result = db.verify_interaction_chain("test-project")
print(f"\n3. Verification after tampering: {'[OK] VALID' if result['verified'] else '[ERROR] INVALID'}")

if tamper_blocked and result['verified']:
    print(f"\n   [OK] TAMPERING PREVENTED!")
    print(f"   Immutable write protection blocked the unauthorized update.")
    print("\n" + "="*60)
else:
    print(f"\n   [ERROR] FAILED TAMPER PREVENTION TEST!")
    print("\n" + "="*60)
    print("\nNOTE: This test expects unauthorized SQL updates to be blocked.")
    print("If they are not blocked, or the chain becomes inconsistent afterward,")
    print("write protection has been bypassed. This is a REAL failure.")
    sys.exit(1)

