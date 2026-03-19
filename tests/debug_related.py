"""
Debug related entities query.
"""

import sys
sys.path.insert(0, '.')

from tools.graph_db import GraphDatabase

graph_db = GraphDatabase("./memory/test_traversal.kuzu")

# Get the ladybug entity
result = graph_db.conn.execute("""
    MATCH (e:Entity)
    WHERE e.name = 'LadybugDB'
    RETURN e.uuid
""")

rows = []
while result.has_next():
    rows.append(result.get_next())

ladybug_uuid = rows[0][0]
print(f"LadybugDB UUID: {ladybug_uuid}")

# Test the query
result = graph_db.conn.execute(f"""
    MATCH (e:Entity {{uuid: '{ladybug_uuid}'}})-[r:RELATES_TO]->(target:Entity)
    WHERE r.expired_at IS NULL AND target.deleted_at IS NULL
    RETURN target.*, 'outgoing', r.name, r.uuid, r.fact
""")

print(f"\nQuery results:")
while result.has_next():
    row = result.get_next()
    print(f"\nRow length: {len(row)}")
    for i, val in enumerate(row):
        print(f"  [{i}] = {val}")

