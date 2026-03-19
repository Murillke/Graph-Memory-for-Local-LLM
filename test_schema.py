import os
import shutil
from pathlib import Path

import kuzu

from tools.graph_db import GraphDatabase


tmp_dir = Path("./tests/tmp")
tmp_dir.mkdir(parents=True, exist_ok=True)
db_path = tmp_dir / "test-schema.kuzu"
if db_path.exists():
    if db_path.is_dir():
        shutil.rmtree(db_path)
    else:
        db_path.unlink()

graph_db = GraphDatabase(str(db_path))
graph_db.create_project_node("schema-test", "Schema test project")

result = graph_db.conn.execute('CALL table_info("Entity") RETURN *;')
props = []
while result.has_next():
    row = result.get_next()
    props.append(row[1])

print(f"Total properties: {len(props)}")
print(f"Has 'priority': {'priority' in props}")
print(f"Has 'status': {'status' in props}")
print(f"\nAll properties: {props}")

assert "priority" in props
assert "status" in props

graph_db.close()
if db_path.exists():
    if db_path.is_dir():
        shutil.rmtree(db_path)
    else:
        db_path.unlink()
