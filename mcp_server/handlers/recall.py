"""Recall tool implementation."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from tools.graph_db import GraphDatabase
from tools.schemas import load_and_validate
from tools.sql_db import SQLDatabase

from .common import Response, fail, load_runtime_state, ok, parse_json_field, require_project


def normalize_recall_time(value: str, *, is_end: bool) -> str:
    """Return an inclusive ISO timestamp for recall queries."""
    return value if "T" in value else f"{value}T23:59:59" if is_end else f"{value}T00:00:00"


def memory_recall(
    start: str,
    end: str,
    entity: Optional[str] = None,
    limit: int = 50,
    hide_time: bool = False,
    hide_task_activity: bool = False,
) -> Response:
    """Query memories from a specific time period."""
    data, errors = load_and_validate(
        {
            "start": start,
            "end": end,
            "entity": entity,
            "limit": limit,
            "hide_time": hide_time,
            "hide_task_activity": hide_task_activity,
        },
        "recall",
    )
    if errors:
        return fail("validation", "Invalid recall parameters", errors=errors)

    graph_db = None
    try:
        state = load_runtime_state()
        project_name = require_project(state)
        graph_db = GraphDatabase(state.graph_db_path)
        sql_db = SQLDatabase(state.sql_db_path)

        start_time = normalize_recall_time(data["start"], is_end=False)
        end_time = normalize_recall_time(data["end"], is_end=True)

        count_result = graph_db.conn.execute(
            """
            MATCH (p:Project {name: $project_name})-[:HAS_ENTITY]->(e:Entity)
            WHERE e.extraction_timestamp_str >= $start_time
              AND e.extraction_timestamp_str <= $end_time
            RETURN count(e)
            """,
            {
                "project_name": project_name,
                "start_time": start_time,
                "end_time": end_time,
            },
        )
        total_entities = count_result.get_next()[0] if count_result.has_next() else 0

        result = graph_db.conn.execute(
            """
            MATCH (p:Project {name: $project_name})-[:HAS_ENTITY]->(e:Entity)
            WHERE e.extraction_timestamp_str >= $start_time
              AND e.extraction_timestamp_str <= $end_time
            RETURN e.name, e.extraction_timestamp_str, e.summary, e.labels
            ORDER BY e.extraction_timestamp_str DESC
            LIMIT $limit
            """,
            {
                "project_name": project_name,
                "start_time": start_time,
                "end_time": end_time,
                "limit": data["limit"],
            },
        )

        entities: List[Dict[str, Any]] = []
        while result.has_next():
            row = result.get_next()
            entities.append(
                {
                    "name": row[0],
                    "extraction_timestamp": row[1] if not data["hide_time"] else None,
                    "summary": row[2],
                    "labels": parse_json_field(row[3], []),
                }
            )

        relationships: Optional[Dict[str, List[Dict[str, Any]]]] = None
        if data.get("entity"):
            outgoing: List[Dict[str, Any]] = []
            incoming: List[Dict[str, Any]] = []

            out_result = graph_db.conn.execute(
                """
                MATCH (e:Entity {name: $entity_name})-[r:RELATES_TO]->(target:Entity)
                RETURN r.name, target.name, r.fact
                LIMIT 10
                """,
                {"entity_name": data["entity"]},
            )
            while out_result.has_next():
                row = out_result.get_next()
                outgoing.append(
                    {
                        "relationship": row[0],
                        "target": row[1],
                        "fact": row[2] if len(row) > 2 else "",
                    }
                )

            in_result = graph_db.conn.execute(
                """
                MATCH (source:Entity)-[r:RELATES_TO]->(e:Entity {name: $entity_name})
                RETURN r.name, source.name, r.fact
                LIMIT 10
                """,
                {"entity_name": data["entity"]},
            )
            while in_result.has_next():
                row = in_result.get_next()
                incoming.append(
                    {
                        "relationship": row[0],
                        "source": row[1],
                        "fact": row[2] if len(row) > 2 else "",
                    }
                )

            relationships = {
                "outgoing": outgoing,
                "incoming": incoming,
            }

        task_activity = []
        if not data["hide_task_activity"]:
            task_activity = sql_db.get_task_operations(
                project_name=project_name,
                start=start_time,
                end=end_time,
            )

        return ok(
            {
                "project_name": project_name,
                "entities": entities,
                "truncated": total_entities > data["limit"],
                "returned_count": len(entities),
                "total_count": total_entities,
                "limit": data["limit"],
                "relationships": relationships,
                "task_activity": task_activity,
                "period": {
                    "start": start_time,
                    "end": end_time,
                },
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
