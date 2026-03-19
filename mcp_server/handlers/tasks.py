"""Task tool implementation."""

from __future__ import annotations

from typing import Any, Dict, Optional

from scripts.tasks import (
    get_actionable_tasks_ordered,
    get_project_task_map,
    record_task_operation_event,
    resolve_task_identifier,
    transition_task_status,
    UNSET,
    update_task_entity,
)
from tools.graph_db import GraphDatabase

from .common import Response, fail, load_runtime_state, ok, require_project


VALID_ACTIONS = {
    "list",
    "start",
    "done",
    "skip",
    "pause",
    "add",
    "set_priority",
    "edit",
    "clear_blocked_by",
    "set_parent",
    "clear_parent",
}
PRIORITIES = {"high", "medium", "low"}
STATUS_BY_ACTION = {
    "start": "in_progress",
    "pause": "pending",
    "done": "complete",
    "skip": "invalid",
}


def _resolve_actionable_task(project_name: str, graph_db: GraphDatabase, task_hash: str):
    actionable = get_actionable_tasks_ordered(project_name, graph_db)
    task, error = resolve_task_identifier(task_hash, actionable)
    return actionable, task, error


def memory_tasks(
    action: str = "list",
    task_hash: Optional[str] = None,
    priority: Optional[str] = None,
    name: Optional[str] = None,
    summary: str = "",
    details: Optional[str] = None,
    blocked_by: Optional[list[str]] = None,
    parent_hash: Optional[str] = None,
) -> Response:
    """View and manage tasks for the configured project."""
    if action not in VALID_ACTIONS:
        return fail(
            "validation",
            "Invalid task action",
            errors=[f"action must be one of {sorted(VALID_ACTIONS)}"],
        )

    graph_db = None
    try:
        state = load_runtime_state()
        project_name = require_project(state)
        graph_db = GraphDatabase(state.graph_db_path)

        if action == "list":
            actionable = get_actionable_tasks_ordered(project_name, graph_db)
            return ok(
                {
                    "project_name": project_name,
                    "tasks": actionable,
                    "count": len(actionable),
                }
            )

        if action == "add":
            if not name:
                return fail("validation", "name is required when action='add'")
            resolved_priority = priority or "medium"
            if resolved_priority not in PRIORITIES:
                return fail("validation", "Invalid priority", errors=[f"priority must be one of {sorted(PRIORITIES)}"])

            graph_db.create_project_node(project_name, f"Project: {project_name}")
            task_uuid = graph_db.create_entity(
                name=name,
                summary=summary,
                labels=["Task"],
                attributes={},
                source_interactions=[],
                source_hashes=[],
                source_chain=[],
                group_id=project_name,
                extraction_version="manual",
                extraction_commit="manual",
                priority=resolved_priority,
                status="pending",
            )
            graph_db.link_project_to_entity(project_name, task_uuid)
            record_task_operation_event(
                project_name,
                "add",
                name,
                task_uuid=task_uuid,
                status_after="pending",
                priority_after=resolved_priority,
                payload={"summary": summary},
            )
            return ok(
                {
                    "project_name": project_name,
                    "task_uuid": task_uuid,
                    "name": name,
                    "priority": resolved_priority,
                    "status": "pending",
                }
            )

        if not task_hash:
            return fail("validation", "task_hash is required for task mutations")

        actionable, task, error_message = _resolve_actionable_task(project_name, graph_db, task_hash)
        if task is None:
            return fail("not_found", error_message or "Task not found")

        if action == "set_priority":
            if priority not in PRIORITIES:
                return fail("validation", "Invalid priority", errors=[f"priority must be one of {sorted(PRIORITIES)}"])
            graph_db.conn.execute(
                """
                MATCH (e:Entity {uuid: $uuid})
                SET e.priority = $priority
                """,
                {
                    "uuid": task["uuid"],
                    "priority": priority,
                },
            )
            record_task_operation_event(
                project_name,
                "set_priority",
                task["name"],
                task_uuid=task["uuid"],
                priority_before=task.get("priority"),
                priority_after=priority,
            )
            return ok(
                {
                    "project_name": project_name,
                    "task_uuid": task["uuid"],
                    "name": task["name"],
                    "priority": priority,
                }
            )

        if action in {"edit", "clear_blocked_by", "set_parent", "clear_parent"}:
            task_map = get_project_task_map(project_name, graph_db)

            blocked_by_value = UNSET
            if action == "clear_blocked_by":
                blocked_by_value = []
            elif blocked_by is not None:
                if not isinstance(blocked_by, list):
                    return fail("validation", "blocked_by must be a list of task hashes")
                resolved_blockers = []
                seen = set()
                for blocker_hash in blocked_by:
                    blocker, blocker_error = resolve_task_identifier(blocker_hash, actionable)
                    if blocker_error:
                        return fail("validation", f"Invalid blocker hash '{blocker_hash}'")
                    if blocker["uuid"] == task["uuid"]:
                        return fail("validation", "Task cannot block itself")
                    if blocker["status"] in {"complete", "invalid"}:
                        return fail("validation", f"Closed tasks cannot be blockers: {blocker['name']}")
                    if blocker["uuid"] not in seen:
                        resolved_blockers.append(blocker["uuid"])
                        seen.add(blocker["uuid"])
                blocked_by_value = resolved_blockers

            parent_task_uuid = UNSET
            if action == "clear_parent":
                parent_task_uuid = None
            elif action == "set_parent":
                if not parent_hash:
                    return fail("validation", "parent_hash is required when action='set_parent'")
                parent_task, parent_error = resolve_task_identifier(parent_hash, actionable)
                if parent_error:
                    return fail("validation", f"Invalid parent hash '{parent_hash}'")
                if parent_task["uuid"] == task["uuid"]:
                    return fail("validation", "Task cannot be its own parent")
                if parent_task["status"] in {"complete", "invalid"}:
                    return fail("validation", f"Closed tasks cannot be parents: {parent_task['name']}")
                parent_entity = task_map.get(parent_task["uuid"])
                if parent_entity and parent_entity["attributes"].get("parent_task_uuid") == task["uuid"]:
                    return fail("validation", "Direct parent cycle detected")
                parent_task_uuid = parent_task["uuid"]

            if action == "edit":
                if name is None and summary == "" and details is None and blocked_by is None and parent_hash is None:
                    return fail("validation", "edit requires at least one field")

            result = update_task_entity(
                project_name,
                task["uuid"],
                name=name if name is not None else UNSET,
                summary=summary if summary != "" else UNSET,
                details=details if details is not None else UNSET,
                blocked_by=blocked_by_value,
                parent_task_uuid=parent_task_uuid,
                db=graph_db,
                emit_event=True,
                command_context=f"memory_tasks:{action}",
            )
            if not result.get("ok"):
                return fail("validation", result.get("error", "Task update failed"))

            updated_task = next(
                (item for item in get_actionable_tasks_ordered(project_name, graph_db) if item["uuid"] == task["uuid"]),
                None,
            )
            data = {
                "project_name": project_name,
                "task_uuid": task["uuid"],
                "name": result["task_name"],
                "fields_changed": result["fields_changed"],
                "before": result["before"],
                "after": result["after"],
            }
            if updated_task is not None:
                data["task"] = updated_task
            return ok(data)

        transition = transition_task_status(project_name, task["uuid"], STATUS_BY_ACTION[action], graph_db)
        if not transition.get("ok"):
            return fail("validation", transition.get("error", "Task transition failed"))

        record_task_operation_event(
            project_name,
            action,
            task["name"],
            task_uuid=task["uuid"],
            status_before=transition.get("old_status"),
            status_after=transition.get("new_status"),
        )

        return ok(
            {
                "project_name": project_name,
                "task_uuid": task["uuid"],
                "name": task["name"],
                "status_before": transition.get("old_status"),
                "status_after": transition.get("new_status"),
                "remaining_actionable": len(actionable),
            }
        )
    except LookupError as exc:
        return fail("config", str(exc))
    except Exception as exc:
        return fail("internal", str(exc))
    finally:
        if graph_db is not None:
            graph_db.close()
