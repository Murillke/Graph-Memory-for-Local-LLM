"""
Manually verify hash chain is correct.
"""

import sys
sys.path.insert(0, '.')

from tools.sql_db import SQLDatabase
import hashlib

db = SQLDatabase("./memory/test.db")

# Get all interactions
interactions = db.get_all_interactions("test-project")

print("Manual Hash Verification:")
print("="*60)

for i, interaction in enumerate(interactions):
    # Manually calculate hash
    content = "|".join([
        str(interaction["uuid"]),
        str(interaction["project_name"]),
        str(interaction["user_message"]),
        str(interaction["assistant_message"]),
        str(interaction["timestamp"]),
        str(interaction["chain_index"]),
        str(interaction.get("previous_hash") or "")
    ])
    
    manual_hash = hashlib.sha256(content.encode()).hexdigest()
    stored_hash = interaction["content_hash"]
    
    print(f"\nInteraction {i+1}:")
    print(f"  UUID: {interaction['uuid']}")
    print(f"  Chain index: {interaction['chain_index']}")
    print(f"  Stored hash:  {stored_hash[:32]}...")
    print(f"  Manual hash:  {manual_hash[:32]}...")
    print(f"  Match: {'[OK] YES' if manual_hash == stored_hash else '[ERROR] NO'}")
    
    # Verify chain link
    if i > 0:
        prev_hash = interactions[i-1]["content_hash"]
        curr_prev = interaction["previous_hash"]
        print(f"  Previous hash: {prev_hash[:32]}...")
        print(f"  Stored prev:   {curr_prev[:32]}...")
        print(f"  Chain link: {'[OK] VALID' if prev_hash == curr_prev else '[ERROR] BROKEN'}")

print("\n" + "="*60)
print("[OK] Manual verification complete!")

