"""Context tool implementation."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from scripts.tasks import get_actionable_tasks_ordered
from tools.graph_db import GraphDatabase
from tools.schemas import load_and_validate
from tools.sql_db import SQLDatabase

from .common import Response, fail, load_runtime_state, ok, require_project


def _get_scalar(graph_db: GraphDatabase, query: str, params: Dict[str, Any]) -> Any:
    result = graph_db.conn.execute(query, params)
    if result.has_next():
        return result.get_next()[0]
    return None


def memory_context(last: int = 10) -> Response:
    """Get project context and recent memories for session start."""
    data, errors = load_and_validate({"last": last}, "query")
    if errors:
        return fail("validation", "Invalid context parameters", errors=errors)

    graph_db = None
    try:
        state = load_runtime_state()
        project_name = require_project(state)
        graph_db = GraphDatabase(state.graph_db_path)
        sql_db = SQLDatabase(state.sql_db_path)

        recent_query = """
            MATCH (p:Project {name: $project_name})-[:HAS_ENTITY]->(e:Entity)
            WHERE e.deleted_at IS NULL
            RETURN e.uuid, e.name, e.summary, e.labels, e.created_at
            ORDER BY e.created_at DESC
            LIMIT $limit
        """
        result = graph_db.conn.execute(
            recent_query,
            {
                "project_name": project_name,
                "limit": data["last"] or 10,
            },
        )

        recent_entities: List[Dict[str, Any]] = []
        while result.has_next():
            row = result.get_next()
            labels = []
            if row[3]:
                try:
                    labels = json.loads(row[3]) if isinstance(row[3], str) else row[3]
                except json.JSONDecodeError:
                    labels = [row[3]]
            recent_entities.append(
                {
                    "uuid": row[0],
                    "name": row[1],
                    "summary": row[2],
                    "labels": labels,
                    "created_at": str(row[4]) if row[4] else None,
                }
            )

        task_preview = get_actionable_tasks_ordered(project_name, graph_db)[:10]
        interaction_counts = sql_db.get_interaction_counts(project_name)

        project_info = sql_db.get_project_by_name(project_name) or {"name": project_name}
        entity_count = _get_scalar(
            graph_db,
            """
            MATCH (p:Project {name: $project_name})-[:HAS_ENTITY]->(e:Entity)
            WHERE e.deleted_at IS NULL
            RETURN count(e)
            """,
            {"project_name": project_name},
        ) or 0
        fact_count = _get_scalar(
            graph_db,
            """
            MATCH (p:Project {name: $project_name})-[:HAS_ENTITY]->(:Entity)-[r:RELATES_TO]->(:Entity)
            WHERE r.expired_at IS NULL
            RETURN count(r)
            """,
            {"project_name": project_name},
        ) or 0

        return ok(
            {
                "project": project_info,
                "counts": {
                    "entities": int(entity_count),
                    "facts": int(fact_count),
                    "interactions": interaction_counts,
                    "actionable_tasks": len(task_preview),
                },
                "recent_entities": recent_entities,
                "actionable_tasks": task_preview,
                "note": "This is a current project snapshot from the configured databases, not a verification result.",
            }
        )
    except LookupError as exc:
        return fail("config", str(exc))
    except FileNotFoundError as exc:
        return fail("not_found", str(exc))
    except Exception as exc:
        return fail("internal", str(exc))
    finally:
        if graph_db is not None:
            graph_db.close()

