"""
Debug proof calculation.
"""

import sys
sys.path.insert(0, '.')

from tools.graph_db import GraphDatabase
import json

graph_db = GraphDatabase("./memory/test_verify.kuzu")

# Get entity
entity = graph_db.get_entity_by_uuid("entity-8e839a6abe72")

print("Entity data:")
print(f"  name: {entity['name']}")
print(f"  summary: {entity['summary']}")
print(f"  labels: {entity['labels']}")
print(f"  attributes: {entity['attributes']}")
print(f"  source_hashes: {entity['source_hashes']}")
print(f"  extraction_timestamp: {entity['extraction_timestamp']}")
print(f"  extraction_timestamp type: {type(entity['extraction_timestamp'])}")

# Manual calculation
import hashlib

content = "|".join([
    entity['name'],
    entity['summary'] or "",
    json.dumps(sorted(entity['labels'])),
    json.dumps(entity['attributes']) if entity['attributes'] else "",
    *sorted(entity['source_hashes']),
    entity['extraction_timestamp']
])

print(f"\nContent to hash:")
print(f"  {repr(content)}")

manual_hash = hashlib.sha256(content.encode()).hexdigest()

print(f"\nManual hash: {manual_hash}")
print(f"Stored hash: {entity['extraction_proof']}")
print(f"Match: {manual_hash == entity['extraction_proof']}")

