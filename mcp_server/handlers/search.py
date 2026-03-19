"""Search tool implementation."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from tools.graph_db import GraphDatabase
from tools.schemas import load_and_validate

from .common import Response, fail, load_runtime_state, ok, require_project


def memory_search(
    search: Optional[str] = None,
    entity: Optional[str] = None,
    type: Optional[str] = None,
    limit: int = 50,
    facts: Optional[str] = None,
) -> Response:
    """Search entities, facts, and relationships in the configured project."""
    data, errors = load_and_validate(
        {
            "search": search,
            "entity": entity,
            "type": type,
            "limit": limit,
            "facts": facts,
        },
        "query",
    )
    if errors:
        return fail("validation", "Invalid search parameters", errors=errors)

    if not any([data.get("search"), data.get("entity"), data.get("facts"), data.get("type")]):
        return fail(
            "validation",
            "At least one of search, entity, facts, or type is required",
        )

    graph_db = None
    try:
        state = load_runtime_state()
        project_name = require_project(state)
        graph_db = GraphDatabase(state.graph_db_path)

        results: Dict[str, Any] = {
            "project_name": project_name,
            "filters": {
                "search": data.get("search"),
                "entity": data.get("entity"),
                "type": data.get("type"),
                "facts": data.get("facts"),
                "limit": data["limit"],
            },
            "entities": [],
            "facts": [],
            "entity_result": None,
            "related_entities": [],
        }

        if data.get("search"):
            results["entities"] = graph_db.search_entities(
                project_name,
                query=data["search"],
                limit=data["limit"],
            )

        if data.get("facts") or (data.get("type") and not data.get("entity")):
            results["facts"] = graph_db.search_facts(
                project_name,
                query=data.get("facts"),
                relationship_type=data.get("type"),
                limit=data["limit"],
            )

        if data.get("entity"):
            try:
                entity_result = graph_db.get_entity_by_name(project_name, data["entity"])
            except ValueError as exc:
                return fail("validation", str(exc))

            if entity_result is None:
                return fail("not_found", "Entity not found")

            entity_facts = graph_db.get_entity_facts(entity_result["uuid"])
            if data.get("type"):
                entity_facts = [
                    row for row in entity_facts if row.get("relationship_type") == data["type"]
                ]

            related_entities = graph_db.get_related_entities(
                entity_result["uuid"],
                direction="both",
                relationship_type=data.get("type"),
                limit=data["limit"],
            )

            results["entity_result"] = {
                "entity": entity_result,
                "facts": entity_facts,
            }
            results["related_entities"] = related_entities

        return ok(results)
    except LookupError as exc:
        return fail("config", str(exc))
    except FileNotFoundError as exc:
        return fail("not_found", str(exc))
    except Exception as exc:
        return fail("internal", str(exc))
    finally:
        if graph_db is not None:
            graph_db.close()

