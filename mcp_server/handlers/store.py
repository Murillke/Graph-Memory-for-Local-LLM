"""Store tool implementation."""

from __future__ import annotations

from tools.schemas import load_and_validate
from tools.sql_db import SQLDatabase

from .common import Response, fail, load_runtime_state, ok, require_project


def memory_store(user: str, assistant: str, fidelity: str = "summary") -> Response:
    """Store a conversation exchange in the configured project."""
    data, errors = load_and_validate(
        {
            "user": user,
            "assistant": assistant,
            "fidelity": fidelity,
        },
        "interaction",
    )
    if errors:
        return fail("validation", "Invalid interaction payload", errors=errors)

    try:
        state = load_runtime_state()
        project_name = require_project(state)
        sql_db = SQLDatabase(state.sql_db_path)

        if not sql_db.get_project_by_name(project_name):
            sql_db.create_project(project_name, f"Project: {project_name}")

        interaction_uuid = sql_db.store_interaction(
            {
                "project_name": project_name,
                "user_message": data["user"],
                "assistant_message": data["assistant"],
                "fidelity": data["fidelity"],
            }
        )
        stored = sql_db.get_interaction_by_uuid(interaction_uuid)

        return ok(
            {
                "uuid": interaction_uuid,
                "project_name": project_name,
                "content_hash": stored["content_hash"],
                "chain_index": stored["chain_index"],
                "timestamp": stored["timestamp"],
                "fidelity": stored["fidelity"],
            }
        )
    except LookupError as exc:
        return fail("config", str(exc))
    except Exception as exc:
        return fail("internal", str(exc))
