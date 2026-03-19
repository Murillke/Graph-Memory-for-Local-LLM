#!/usr/bin/env python3
"""
Task Management - Query and manage tasks from the knowledge graph.

Usage:
    # Show actionable tasks (in_progress + pending, with stable short-hash IDs)
    python scripts/tasks.py --project llm_memory

    # Filter by status
    python scripts/tasks.py --project llm_memory --in-progress
    python scripts/tasks.py --project llm_memory --pending

    # Start working on task (use hash ID from task list)
    python scripts/tasks.py --project llm_memory --start 1fab266

    # Pause task (in_progress -> pending)
    python scripts/tasks.py --project llm_memory --pause 1fab266

    # Mark task complete
    python scripts/tasks.py --project llm_memory --done c7dec3e

    # Mark task invalid
    python scripts/tasks.py --project llm_memory --skip abc1234

    # Change priority
    python scripts/tasks.py --project llm_memory --set-priority 1fab266 --to high

    # Edit task name / summary / details
    python scripts/tasks.py --project llm_memory --edit 1fab266 --name-file tmp/task.txt
    python scripts/tasks.py --project llm_memory --edit 1fab266 --summary-file tmp/summary.txt
    python scripts/tasks.py --project llm_memory --edit 1fab266 --details-file tmp/details.txt

    # Set or clear blockers / parent task
    python scripts/tasks.py --project llm_memory --edit 1fab266 --blocked-by c7dec3e,abc1234
    python scripts/tasks.py --project llm_memory --edit 1fab266 --clear-blocked-by
    python scripts/tasks.py --project llm_memory --edit 1fab266 --parent c7dec3e
    python scripts/tasks.py --project llm_memory --edit 1fab266 --clear-parent

    # Add new task (use JSON file for complex names)
    python scripts/tasks.py --project llm_memory --add-file tmp/task.json

IMPORTANT: Operations (--done, --skip, --start, --pause, --set-priority, --edit) require
hash identifiers, NOT numbers. Numbers are display-only for human readability.
Hash IDs are stable and don't shift when task lists change.
"""

import sys
import json
import argparse
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Any
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.graph_db import GraphDatabase
from tools.config import load_config
from tools.sql_db import SQLDatabase, get_task_event_display_label, get_task_short_hash


UNSET = object()


def get_workflow_session_id(cli_value: Optional[str] = None) -> Optional[str]:
    """Resolve optional workflow session ID from CLI or environment."""
    return cli_value or os.environ.get("WORKFLOW_SESSION_ID")


def record_task_operation_event(
    project_name: str,
    operation: str,
    task_name: str,
    *,
    task_uuid: Optional[str] = None,
    status_before: Optional[str] = None,
    status_after: Optional[str] = None,
    priority_before: Optional[str] = None,
    priority_after: Optional[str] = None,
    workflow_session_id: Optional[str] = None,
    command_context: Optional[str] = None,
    payload: Optional[dict] = None,
) -> None:
    """Record a successful task mutation to SQL for sync/store reuse."""
    config = load_config(project_name=project_name)
    sql_db = SQLDatabase(config.get_sql_db_path())
    sql_db.record_task_operation(
        project_name=project_name,
        operation=operation,
        success=True,
        task_name=task_name,
        task_uuid=task_uuid,
        status_before=status_before,
        status_after=status_after,
        priority_before=priority_before,
        priority_after=priority_after,
        workflow_session_id=get_workflow_session_id(workflow_session_id),
        command_context=command_context,
        payload=payload,
    )


def parse_datetime(dt_str) -> datetime:
    """Parse various datetime string formats."""
    if not dt_str:
        return None
    if isinstance(dt_str, datetime):
        return dt_str
    try:
        return datetime.fromisoformat(str(dt_str).replace('Z', '+00:00').split('.')[0])
    except:
        return None


def format_age(created_at_str: str) -> str:
    """Format task age as human-readable string."""
    if not created_at_str:
        return ""

    try:
        created = parse_datetime(created_at_str)
        if not created:
            return ""
        now = datetime.now()
        delta = now - created

        days = delta.days
        if days == 0:
            hours = delta.seconds // 3600
            if hours == 0:
                minutes = delta.seconds // 60
                return f"{minutes}m ago"
            return f"{hours}h ago"
        elif days == 1:
            return "1 day ago"
        elif days < 7:
            return f"{days} days ago"
        elif days < 30:
            weeks = days // 7
            return f"{weeks}w ago"
        elif days < 365:
            months = days // 30
            return f"{months}mo ago"
        else:
            years = days // 365
            return f"{years}y ago"
    except:
        return ""


def safe_print(text):
    """Print with encoding fallback for Windows."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode('ascii', 'replace').decode('ascii'))


def print_warning(text):
    """Print warning to stderr."""
    try:
        print(text, file=sys.stderr)
    except UnicodeEncodeError:
        print(text.encode('ascii', 'replace').decode('ascii'), file=sys.stderr)


def read_text_file(path: str) -> str:
    """Read UTF-8 text from a helper file and strip trailing whitespace."""
    with open(path, 'r', encoding='utf-8') as f:
        return f.read().strip()


def parse_attributes(raw_value: Any, *, task_name: str = "(unknown)") -> dict:
    """Parse task attributes JSON, treating malformed values as empty."""
    if not raw_value:
        return {}
    try:
        return json.loads(raw_value) if isinstance(raw_value, str) else raw_value
    except json.JSONDecodeError:
        print_warning(f"Warning: Malformed attributes for '{task_name}', treating as {{}}")
        return {}


def get_task_entity(project_name: str, task_uuid: str, db=None) -> Optional[dict]:
    """Load a task entity with parsed attributes."""
    should_close = False
    if db is None:
        db_path = load_config(project_name=project_name).get_graph_db_path(project_name)
        db = GraphDatabase(db_path)
        should_close = True

    try:
        result = db.conn.execute("""
            MATCH (p:Project {name: $project_name})-[:HAS_ENTITY]->(e:Entity)
            WHERE e.uuid = $uuid AND e.labels CONTAINS 'Task' AND e.deleted_at IS NULL
            RETURN e.uuid, e.name, e.summary, e.priority, e.status, e.created_at, e.attributes
            LIMIT 1
        """, {
            "project_name": project_name,
            "uuid": task_uuid,
        })
        if not result.has_next():
            return None
        row = result.get_next()
        return {
            "uuid": row[0],
            "name": row[1],
            "summary": row[2] or "",
            "priority": row[3] or "medium",
            "status": row[4] or "pending",
            "created_at": str(row[5]) if row[5] else "",
            "attributes": parse_attributes(row[6], task_name=row[1]),
        }
    finally:
        if should_close:
            db.close()


def get_project_task_map(project_name: str, db) -> dict:
    """Return UUID -> task metadata for all non-deleted tasks in a project."""
    result = db.conn.execute("""
        MATCH (p:Project {name: $project_name})-[:HAS_ENTITY]->(e:Entity)
        WHERE e.labels CONTAINS 'Task' AND e.deleted_at IS NULL
        RETURN e.uuid, e.name, e.status, e.priority, e.attributes
    """, {"project_name": project_name})

    task_map = {}
    while result.has_next():
        row = result.get_next()
        task_map[row[0]] = {
            "uuid": row[0],
            "name": row[1],
            "status": row[2] or "pending",
            "priority": row[3] or "medium",
            "attributes": parse_attributes(row[4], task_name=row[1]),
        }
    return task_map


def get_child_tasks(project_name: str, parent_uuid: str, db=None) -> list:
    """Return child tasks whose attributes.parent_task_uuid matches parent_uuid."""
    should_close = False
    if db is None:
        db_path = load_config(project_name=project_name).get_graph_db_path(project_name)
        db = GraphDatabase(db_path)
        should_close = True

    try:
        children = []
        for task in get_project_task_map(project_name, db).values():
            if task["attributes"].get("parent_task_uuid") == parent_uuid:
                uuid = task["uuid"] or ""
                unique_part = uuid[7:] if uuid.startswith("entity-") else uuid
                children.append({
                    "uuid": uuid,
                    "short_hash": unique_part[:7] if unique_part else "",
                    "name": task["name"],
                    "status": task["status"],
                    "priority": task["priority"],
                })
        children.sort(key=lambda item: (item["status"], item["name"].lower()))
        return children
    finally:
        if should_close:
            db.close()


def task_blocker_info(task: dict, task_map: dict) -> tuple[list, bool]:
    """Return active blocker rows and whether the task is currently blocked."""
    blockers = []
    for blocker_uuid in task.get("attributes", {}).get("blocked_by", []):
        blocker = task_map.get(blocker_uuid)
        if blocker is None:
            blockers.append({
                "uuid": blocker_uuid,
                "short_hash": blocker_uuid[7:14] if blocker_uuid.startswith("entity-") else blocker_uuid[:7],
                "name": blocker_uuid,
                "status": "missing",
            })
            continue
        blocker_copy = blocker.copy()
        uuid = blocker_copy["uuid"] or ""
        unique_part = uuid[7:] if uuid.startswith("entity-") else uuid
        blocker_copy["short_hash"] = unique_part[:7] if unique_part else ""
        blockers.append(blocker_copy)

    active_statuses = {"pending", "in_progress"}
    is_blocked = any(blocker["status"] in active_statuses for blocker in blockers)
    return blockers, is_blocked


def update_task_entity(
    project_name: str,
    task_uuid: str,
    *,
    name: Any = UNSET,
    summary: Any = UNSET,
    details: Any = UNSET,
    blocked_by: Any = UNSET,
    parent_task_uuid: Any = UNSET,
    db=None,
    emit_event: bool = False,
    workflow_session_id: Optional[str] = None,
    command_context: Optional[str] = None,
):
    """Update task fields and record a structured task operation event when requested."""
    should_close = False
    if db is None:
        db_path = load_config(project_name=project_name).get_graph_db_path(project_name)
        db = GraphDatabase(db_path)
        should_close = True

    try:
        current = get_task_entity(project_name, task_uuid, db)
        if current is None:
            return {"ok": False, "error": f"Task not found: {task_uuid}"}

        current_attrs = dict(current["attributes"])
        new_name = current["name"] if name is UNSET else name
        new_summary = current["summary"] if summary is UNSET else summary
        new_attrs = dict(current_attrs)

        if details is not UNSET:
            if details:
                new_attrs["details"] = details
            else:
                new_attrs.pop("details", None)

        if blocked_by is not UNSET:
            if blocked_by:
                new_attrs["blocked_by"] = blocked_by
            else:
                new_attrs.pop("blocked_by", None)

        if parent_task_uuid is not UNSET:
            if parent_task_uuid:
                new_attrs["parent_task_uuid"] = parent_task_uuid
            else:
                new_attrs.pop("parent_task_uuid", None)

        fields_changed = []
        before = {}
        after = {}

        def track_change(field_name: str, old_value: Any, new_value: Any):
            if old_value != new_value:
                fields_changed.append(field_name)
                before[field_name] = old_value
                after[field_name] = new_value

        track_change("name", current["name"], new_name)
        track_change("summary", current["summary"], new_summary)
        track_change("details", current_attrs.get("details"), new_attrs.get("details"))
        track_change("blocked_by", current_attrs.get("blocked_by"), new_attrs.get("blocked_by"))
        track_change("parent_task_uuid", current_attrs.get("parent_task_uuid"), new_attrs.get("parent_task_uuid"))

        if not fields_changed:
            return {"ok": False, "error": "No changes requested"}

        db.conn.execute("""
            MATCH (e:Entity {uuid: $uuid})
            SET e.name = $name,
                e.summary = $summary,
                e.attributes = $attributes
        """, {
            "uuid": task_uuid,
            "name": new_name,
            "summary": new_summary,
            "attributes": json.dumps(new_attrs, sort_keys=True),
        })

        if emit_event:
            operations = set(fields_changed)
            if operations == {"blocked_by"}:
                operation = "set_blocked_by"
            elif operations == {"parent_task_uuid"}:
                operation = "set_parent_task"
            else:
                operation = "edit"
            record_task_operation_event(
                project_name,
                operation,
                new_name,
                task_uuid=task_uuid,
                status_before=current["status"],
                status_after=current["status"],
                priority_before=current["priority"],
                priority_after=current["priority"],
                workflow_session_id=workflow_session_id,
                command_context=command_context,
                payload={
                    "fields_changed": fields_changed,
                    "before": before,
                    "after": after,
                },
            )

        return {
            "ok": True,
            "task_uuid": task_uuid,
            "task_name": new_name,
            "fields_changed": fields_changed,
            "before": before,
            "after": after,
        }
    finally:
        if should_close:
            db.close()


def get_actionable_tasks_ordered(project_name: str, db=None):
    """Returns in_progress + pending tasks in global numbered order.

    Order:
      1. in_progress tasks (high -> medium -> low, newest first within priority)
      2. pending tasks (high -> medium -> low, newest first within priority)

    This is THE source of truth for all number-based operations.
    Note: status IS NULL is treated as 'pending' (backward-compatibility).

    Returns: list of dicts with keys:
      - display_number: int (1-based, for CLI operations)
      - uuid: str
      - name: str
      - status: str ('in_progress' or 'pending')
      - priority: str
      - created_at: str
      - attributes: dict (parsed JSON, or {} if malformed)
    """
    should_close = False
    if db is None:
        db_path = load_config(project_name=project_name).get_graph_db_path(project_name)
        db = GraphDatabase(db_path)
        should_close = True

    try:
        result = db.conn.execute("""
            MATCH (p:Project {name: $project_name})-[:HAS_ENTITY]->(e:Entity)
            WHERE e.labels CONTAINS 'Task' AND e.deleted_at IS NULL
              AND (e.status IN ['in_progress', 'pending'] OR e.status IS NULL)
            RETURN e.uuid, e.name, e.status, e.priority, e.created_at, e.attributes, e.summary
            ORDER BY e.created_at DESC
        """, {"project_name": project_name})

        in_progress = []
        pending = []
        task_map = {}
        seen_task_uuids = set()

        while result.has_next():
            row = result.get_next()
            task_uuid = row[0]
            if task_uuid in seen_task_uuids:
                continue
            seen_task_uuids.add(task_uuid)

            status = row[2] or 'pending'

            # Parse attributes safely
            attrs = {}
            if row[5]:
                try:
                    attrs = json.loads(row[5]) if isinstance(row[5], str) else row[5]
                except json.JSONDecodeError:
                    print_warning(f"Warning: Malformed attributes for task '{row[1]}', treating as {{}}")

            task = {
                'uuid': task_uuid,
                'name': row[1],
                'status': status,
                'priority': row[3] or 'medium',
                'created_at': str(row[4]) if row[4] else '',
                'attributes': attrs,
                'summary': row[6] or ''
            }
            task_map[task['uuid']] = task

            if status == 'in_progress':
                in_progress.append(task)
            else:
                pending.append(task)

        # Sort each group by priority (high -> medium -> low), newest first within priority
        def sort_by_priority(tasks):
            def group_for(priority):
                group = [t for t in tasks if t['priority'] == priority]
                for task in group:
                    blockers, is_blocked = task_blocker_info(task, task_map)
                    task['blockers'] = blockers
                    task['is_blocked'] = is_blocked
                    task['blocked_count'] = sum(1 for blocker in blockers if blocker['status'] in {'pending', 'in_progress'})
                    parent_uuid = task['attributes'].get('parent_task_uuid')
                    task['parent_task_uuid'] = parent_uuid
                    task['parent_short_hash'] = ""
                    if parent_uuid:
                        parent = task_map.get(parent_uuid)
                        if parent_uuid.startswith('entity-'):
                            task['parent_short_hash'] = parent_uuid[7:14]
                        if parent:
                            task['parent_name'] = parent['name']
                    else:
                        task['parent_name'] = None
                # Preserve existing created_at-desc order within each priority bucket,
                # only demoting blocked tasks behind unblocked tasks.
                return sorted(group, key=lambda t: 1 if t.get('is_blocked') else 0)

            high = group_for('high')
            medium = group_for('medium')
            low = group_for('low')
            return high + medium + low

        in_progress = sort_by_priority(in_progress)
        pending = sort_by_priority(pending)

        # Combine: in_progress first, then pending
        all_tasks = in_progress + pending

        # Add display_number and short_hash
        for i, task in enumerate(all_tasks, start=1):
            task['display_number'] = i
            # Short hash: first 7 chars of unique part of UUID (like git commits)
            # UUIDs are formatted as "entity-<hex>", so skip the "entity-" prefix
            uuid = task['uuid'] or ''
            unique_part = uuid[7:] if uuid.startswith('entity-') else uuid
            task['short_hash'] = unique_part[:7] if unique_part else ''

        return all_tasks
    finally:
        if should_close:
            db.close()


def resolve_task_identifier(identifier: str, actionable: list) -> tuple:
    """Resolve a task identifier (UUID or short-hash) to a task.

    IMPORTANT: Numbers are NOT accepted. This forces agents to use stable
    hash identifiers that don't shift when task lists change.

    Args:
        identifier: Short-hash prefix (e.g., "1fab266") or full UUID
        actionable: List of actionable tasks from get_actionable_tasks_ordered()

    Returns:
        (task, error_msg) - task dict if found, or (None, error message)
    """
    identifier = identifier.strip()

    # Reject numeric identifiers - force use of stable hashes
    if identifier.isdigit():
        return (None, f"Numbers not accepted. Use hash identifier (e.g., --done 1fab266). Run tasks.py to see hash IDs.")

    # Try as short-hash prefix (matches against short_hash or full uuid)
    matches = []
    seen_match_uuids = set()
    for task in actionable:
        if not (task['short_hash'].startswith(identifier) or task['uuid'].startswith(identifier)):
            continue
        if task['uuid'] in seen_match_uuids:
            continue
        matches.append(task)
        seen_match_uuids.add(task['uuid'])
    if len(matches) == 1:
        return (matches[0], None)
    elif len(matches) > 1:
        match_info = ", ".join([f"#{t['display_number']} {t['short_hash']}" for t in matches[:3]])
        return (None, f"Ambiguous hash prefix '{identifier}' matches {len(matches)} tasks: {match_info}...")

    return (None, f"No task found matching hash '{identifier}'")


def parse_task_identifiers(identifiers_str: str) -> list:
    """Parse comma-separated task hash identifiers.

    Numbers and numeric ranges are NOT supported - use hash identifiers only.
    This prevents agents from using unstable numeric references.

    Examples:
        "1fab266,c7dec3e" -> ["1fab266", "c7dec3e"]
        "entity-abc123" -> ["entity-abc123"]
    """
    result = []
    for part in identifiers_str.split(','):
        part = part.strip()
        if not part:
            continue
        result.append(part)
    return result


# Valid state transitions
VALID_TRANSITIONS = {
    ('pending', 'in_progress'),      # --start
    ('pending', 'complete'),         # --done
    ('pending', 'invalid'),          # --skip
    ('in_progress', 'complete'),     # --done
    ('in_progress', 'invalid'),      # --skip
    ('in_progress', 'pending'),      # --pause
}


def transition_task_status(project_name: str, task_uuid: str, new_status: str, db=None):
    """Loads current status from DB, validates transition, applies side effects.

    Returns: {
        'task_name': str,
        'old_status': str,
        'new_status': str,
        'ok': bool,
        'error': Optional[str]
    }

    Side effects:
      - pending -> in_progress: sets attributes.started_at
      - in_progress -> pending: clears attributes.started_at

    On malformed attributes: treat as {}, warn, continue.
    """
    should_close = False
    if db is None:
        db_path = load_config(project_name=project_name).get_graph_db_path(project_name)
        db = GraphDatabase(db_path)
        should_close = True

    try:
        # Load current state
        result = db.conn.execute("""
            MATCH (e:Entity {uuid: $uuid})
            RETURN e.name, e.status, e.attributes
        """, {"uuid": task_uuid})

        if not result.has_next():
            return {
                'task_name': '(unknown)',
                'old_status': None,
                'new_status': new_status,
                'ok': False,
                'error': f"Task not found: {task_uuid}"
            }

        row = result.get_next()
        task_name = row[0]
        old_status = row[1] or 'pending'

        # Parse attributes
        attrs = {}
        if row[2]:
            try:
                attrs = json.loads(row[2]) if isinstance(row[2], str) else row[2]
            except json.JSONDecodeError:
                print_warning(f"Warning: Malformed attributes for '{task_name}', treating as {{}}")

        # Check same-state no-op
        if old_status == new_status:
            return {
                'task_name': task_name,
                'old_status': old_status,
                'new_status': new_status,
                'ok': False,
                'error': f"already {old_status}"
            }

        # Validate transition
        if (old_status, new_status) not in VALID_TRANSITIONS:
            return {
                'task_name': task_name,
                'old_status': old_status,
                'new_status': new_status,
                'ok': False,
                'error': f"cannot transition from {old_status} to {new_status}"
            }

        # Apply side effects
        if old_status == 'pending' and new_status == 'in_progress':
            # Set started_at
            attrs['started_at'] = datetime.now().isoformat()
        elif old_status == 'in_progress' and new_status == 'pending':
            # Clear started_at
            attrs.pop('started_at', None)

        # Update database
        db.conn.execute("""
            MATCH (e:Entity {uuid: $uuid})
            SET e.status = $new_status, e.attributes = $attributes
        """, {
            "uuid": task_uuid,
            "new_status": new_status,
            "attributes": json.dumps(attrs)
        })

        return {
            'task_uuid': task_uuid,
            'task_name': task_name,
            'old_status': old_status,
            'new_status': new_status,
            'ok': True,
            'error': None
        }
    finally:
        if should_close:
            db.close()


def show_task_details(project_name: str, task_number: int):
    """Show detailed context for a specific task (Level 3 display)."""

    db_path = load_config(project_name=project_name).get_graph_db_path(project_name)
    db = GraphDatabase(db_path)

    try:
        # Use global actionable list for numbering
        ordered = get_actionable_tasks_ordered(project_name, db)

        if task_number < 1 or task_number > len(ordered):
            safe_print(f"Error: Task #{task_number} not in actionable list (1-{len(ordered)})")
            return

        task = ordered[task_number - 1]
        task_uuid = task['uuid']

        # Get full task entity data by UUID (not name, to avoid duplicates)
        result = db.conn.execute("""
            MATCH (e:Entity {uuid: $uuid})
            RETURN e.uuid, e.name, e.summary, e.priority, e.status, e.created_at,
                   e.source_interactions, e.attributes, e.extraction_version
        """, {"uuid": task_uuid})

        if not result.has_next():
            safe_print(f"Error: Task UUID '{task_uuid}' not found")
            return

        row = result.get_next()
        # task_uuid already set from ordered list
        name = row[1]
        summary = row[2] or ''
        priority = (row[3] or 'medium').upper()
        status = row[4] or 'pending'
        created_at = row[5]
        source_interactions_raw = row[6]
        attributes_raw = row[7]
        extraction_version = row[8] or 'manual'

        # Parse JSON fields
        source_interactions = []
        if source_interactions_raw:
            try:
                source_interactions = json.loads(source_interactions_raw) if isinstance(source_interactions_raw, str) else source_interactions_raw
            except:
                pass

        attributes = {}
        if attributes_raw:
            try:
                attributes = json.loads(attributes_raw) if isinstance(attributes_raw, str) else attributes_raw
            except:
                pass

        # Age display: in_progress shows started_at, pending shows created_at
        if status == 'in_progress' and attributes.get('started_at'):
            age = "started " + format_age(attributes['started_at'])
        elif status == 'in_progress':
            age = "in progress"
        else:
            age = format_age(str(created_at)) if created_at else ''

        is_extracted = extraction_version != 'manual' and source_interactions

        # Print header
        safe_print("")
        safe_print(f"TASK #{task_number}: {name}")
        safe_print("=" * 60)
        safe_print(f"Priority: {priority} | Age: {age} | Status: {status}")
        safe_print("")

        # Summary
        safe_print("Summary:")
        safe_print(f"  {summary}")
        safe_print("")

        # Details (from attributes if present)
        details = attributes.get('details', '')
        if details:
            safe_print("Details:")
            safe_print(f"  {details}")
            safe_print("")

        task_map = get_project_task_map(project_name, db)
        blockers, _is_blocked = task_blocker_info({
            "attributes": attributes,
        }, task_map)
        parent_uuid = attributes.get('parent_task_uuid')
        children = get_child_tasks(project_name, task_uuid, db)

        # Related Facts
        safe_print("Related Facts:")
        facts_result = db.conn.execute("""
            MATCH (e1:Entity)-[r:RELATES_TO]->(e2:Entity)
            WHERE e1.uuid = $uuid OR e2.uuid = $uuid
            RETURN e1.name, r.name, e2.name, r.fact
            LIMIT 10
        """, {"uuid": task_uuid})

        facts_count = 0
        while facts_result.has_next():
            frow = facts_result.get_next()
            safe_print(f"  * {frow[0]} --[{frow[1]}]--> {frow[2]}")
            if frow[3]:
                safe_print(f"    {frow[3][:80]}...")
            facts_count += 1
        if facts_count == 0:
            safe_print("  (none found)")
        safe_print("")

        safe_print("Blocked By:")
        if blockers:
            for blocker in blockers:
                hash_str = f"[{blocker.get('short_hash', '')}] " if blocker.get('short_hash') else ""
                safe_print(f"  * {hash_str}{blocker.get('name', '(unknown)')} ({blocker.get('status', 'unknown')})")
        else:
            safe_print("  (none)")
        safe_print("")

        safe_print("Parent Task:")
        if parent_uuid:
            parent = task_map.get(parent_uuid)
            parent_hash = parent_uuid[7:14] if parent_uuid.startswith('entity-') else parent_uuid[:7]
            if parent:
                safe_print(f"  * [{parent_hash}] {parent['name']} ({parent['status']})")
            else:
                safe_print(f"  * [{parent_hash}] {parent_uuid} (missing)")
        else:
            safe_print("  (none)")
        safe_print("")

        safe_print("Subtasks:")
        if children:
            for child in children:
                safe_print(f"  * [{child['short_hash']}] {child['name']} ({child['status']})")
        else:
            safe_print("  (none)")
        safe_print("")

        # Source Interactions
        safe_print("Source Interactions:")
        if is_extracted and source_interactions:
            for src_uuid in source_interactions[:5]:
                safe_print(f"  * {src_uuid}")
        else:
            safe_print("  (none captured - task was added via tasks.py --add)")
        safe_print("")

        # Related Entities (time correlation + keyword search)
        safe_print("Related Entities:")

        # Get task creation time for time correlation
        task_created = parse_datetime(created_at)

        # Extract keywords from task name and summary
        stop_words = {'the', 'a', 'an', 'to', 'for', 'of', 'in', 'on', 'with', 'and', 'or', 'is', 'are', 'was', 'be'}
        words = (name + ' ' + summary).lower().split()
        keywords = [w.strip('.,()[]{}') for w in words if len(w) > 3 and w not in stop_words]
        keywords = list(set(keywords))[:10]  # Dedupe and limit

        related_entities = []

        # Query entities by keyword match, ordered by time proximity
        for kw in keywords:
            kw_result = db.conn.execute("""
                MATCH (e:Entity)
                WHERE (e.name CONTAINS $kw OR e.summary CONTAINS $kw)
                  AND e.deleted_at IS NULL
                  AND NOT e.labels CONTAINS 'Task'
                  AND e.uuid <> $task_uuid
                RETURN DISTINCT e.name, e.summary, e.created_at
                LIMIT 3
            """, {"kw": kw, "task_uuid": task_uuid})

            while kw_result.has_next():
                erow = kw_result.get_next()
                ename = erow[0]
                esummary = (erow[1] or '')[:60]
                ecreated = parse_datetime(erow[2])

                # Calculate time distance if possible
                time_distance = None
                if task_created and ecreated:
                    time_distance = abs((task_created - ecreated).total_seconds())

                # Avoid duplicates
                if not any(e['name'] == ename for e in related_entities):
                    related_entities.append({
                        'name': ename,
                        'summary': esummary,
                        'time_distance': time_distance,
                        'keyword': kw
                    })

        # Sort by time proximity (closest first), then by keyword relevance
        related_entities.sort(key=lambda x: (x['time_distance'] if x['time_distance'] is not None else float('inf')))

        # Display top 10
        for ent in related_entities[:10]:
            safe_print(f"  * {ent['name']}")
            if ent['summary']:
                safe_print(f"    {ent['summary']}...")

        if not related_entities:
            safe_print("  (none found)")

        safe_print("")

    finally:
        db.close()


def show_tasks(project_name: str, pending_only: bool = False, in_progress_only: bool = False,
               priority_filter: str = None, verbose: bool = False,
               include_closed: bool = False, db=None):
    """Show tasks grouped by status and priority.

    Default output = active/actionable list only (in_progress + pending).
    Closed tasks (complete + invalid) require explicit opt-in.
    Filtered views preserve global numbering (gaps expected).
    """

    should_close = False
    if db is None:
        db_path = load_config(project_name=project_name).get_graph_db_path(project_name)
        db = GraphDatabase(db_path)
        should_close = True

    try:
        # Get actionable tasks with global numbering
        actionable = get_actionable_tasks_ordered(project_name, db)

        # Determine if any filter is active
        any_filter_active = pending_only or in_progress_only or priority_filter

        # Closed tasks are opt-in because the regular hot path is the actionable list.
        complete = []
        invalid = []
        if include_closed and not any_filter_active:
            result = db.conn.execute("""
                MATCH (p:Project {name: $project_name})-[:HAS_ENTITY]->(e:Entity)
                WHERE e.labels CONTAINS 'Task' AND e.deleted_at IS NULL
                  AND e.status IN ['complete', 'invalid']
                RETURN e.name, e.summary, e.status
                ORDER BY e.created_at DESC
            """, {"project_name": project_name})

            while result.has_next():
                row = result.get_next()
                task = {'name': row[0], 'summary': row[1] or '', 'status': row[2]}
                if row[2] == 'complete':
                    complete.append(task)
                else:
                    invalid.append(task)

        # Separate actionable into in_progress and pending
        in_progress = [t for t in actionable if t['status'] == 'in_progress']
        pending = [t for t in actionable if t['status'] == 'pending']

        # Apply filters (preserve global numbers)
        if in_progress_only:
            pending = []
        elif pending_only:
            in_progress = []

        # Apply priority filter
        if priority_filter:
            in_progress = [t for t in in_progress if t['priority'] == priority_filter]
            pending = [t for t in pending if t['priority'] == priority_filter]

        # Check for empty results AFTER filters applied
        has_visible_tasks = in_progress or pending or complete or invalid
        if not has_visible_tasks:
            if any_filter_active:
                safe_print("\nNo tasks found matching filter.")
            else:
                safe_print("\nNo tasks found.")
            return

        safe_print("="*80)
        title = f"TASKS - {project_name}"
        if include_closed and not any_filter_active:
            title += " (INCLUDING CLOSED)"
        safe_print(title)
        safe_print("="*80)

        def get_task_age(task):
            """Get age string for a task based on status."""
            if task['status'] == 'in_progress' and task['attributes'].get('started_at'):
                return "started " + format_age(task['attributes']['started_at'])
            elif task['status'] == 'in_progress':
                return "in progress"
            else:
                return format_age(task['created_at']) if task['created_at'] else ''

        def print_task_with_verbose(task, include_priority_badge=True):
            """Print a single task, optionally with summary in verbose mode."""
            age = get_task_age(task)
            age_str = f" ({age})" if age else ""
            short_hash = task.get('short_hash', '')
            hash_str = f" [{short_hash}]" if short_hash else ""
            suffix_parts = []
            if task.get('is_blocked'):
                suffix_parts.append(f"blocked by {task.get('blocked_count', 0)}")
            if task.get('parent_short_hash'):
                suffix_parts.append(f"SUBTASK of {task['parent_short_hash']}")
            suffix = f" [{' | '.join(suffix_parts)}]" if suffix_parts else ""
            if include_priority_badge:
                safe_print(f"  {task['display_number']}.{hash_str} [{task['priority'].upper()}] {task['name']}{age_str}{suffix}")
            else:
                safe_print(f"  {task['display_number']}.{hash_str} {task['name']}{age_str}{suffix}")
            if verbose and task.get('summary'):
                safe_print(f"     {task['summary']}")

        # Show in_progress tasks
        if in_progress:
            safe_print(f"\nIN PROGRESS ({len(in_progress)})")
            for task in in_progress:
                print_task_with_verbose(task, include_priority_badge=True)
            safe_print("")

        # Show pending tasks grouped by priority
        if pending:
            safe_print(f"PENDING ({len(pending)})")

            high = [t for t in pending if t['priority'] == 'high']
            medium = [t for t in pending if t['priority'] == 'medium']
            low = [t for t in pending if t['priority'] == 'low']

            for priority_tasks, label in [(high, "HIGH"), (medium, "MEDIUM"), (low, "LOW")]:
                if priority_tasks:
                    safe_print(f"[{label}] Priority:")
                    for task in priority_tasks:
                        print_task_with_verbose(task, include_priority_badge=False)
                    safe_print("")

        # Show completed tasks only in explicit closed-history view.
        if complete and include_closed and not pending_only and not in_progress_only:
            safe_print(f"COMPLETED TASKS ({len(complete)})")
            for task in complete[:5]:
                safe_print(f"  [OK] {task['name']}")
            if len(complete) > 5:
                safe_print(f"  ... and {len(complete) - 5} more")
            safe_print("")

        # Show invalid tasks only in explicit closed-history view.
        if invalid and include_closed and not pending_only and not in_progress_only:
            safe_print(f"INVALID TASKS ({len(invalid)})")
            for task in invalid[:5]:
                safe_print(f"  [X] {task['name']}")
            if len(invalid) > 5:
                safe_print(f"  ... and {len(invalid) - 5} more")
            safe_print("")

        safe_print("="*80)

    finally:
        if should_close:
            db.close()



def update_task_status(
    project_name: str,
    task_name: str,
    new_status: str,
    db=None,
    emit_event: bool = False,
    workflow_session_id: Optional[str] = None,
    command_context: Optional[str] = None,
):
    """Update task status by name. Uses transition_task_status for state machine."""

    should_close = False
    if db is None:
        db_path = load_config(project_name=project_name).get_graph_db_path(project_name)
        db = GraphDatabase(db_path)
        should_close = True

    try:
        # Find task UUID by name - check for duplicates
        result = db.conn.execute("""
            MATCH (p:Project {name: $project_name})-[:HAS_ENTITY]->(e:Entity)
            WHERE e.name = $task_name AND e.labels CONTAINS 'Task'
            RETURN e.uuid
        """, {
            "project_name": project_name,
            "task_name": task_name,
        })

        if not result.has_next():
            safe_print(f"\nERROR: Task not found: {task_name}")
            return False

        uuid = result.get_next()[0]

        # Check for duplicate names
        if result.has_next():
            print_warning(f"\nWARNING: Multiple tasks named '{task_name}' exist. Use number-based operations (--done N) instead.")
            return False

        # Use transition helper
        result = transition_task_status(project_name, uuid, new_status, db)

        if result['ok']:
            if emit_event:
                record_task_operation_event(
                    project_name,
                    new_status,
                    task_name,
                    task_uuid=uuid,
                    status_before=result['old_status'],
                    status_after=result['new_status'],
                    workflow_session_id=workflow_session_id,
                    command_context=command_context,
                )
            safe_print(f"\nOK Updated task: {task_name}")
            safe_print(f"   Status: {result['old_status']} -> {result['new_status']}")
            return True
        else:
            print_warning(f"\nWARNING: {task_name}: {result['error']}")
            return False

    finally:
        if should_close:
            db.close()


def batch_update_tasks(
    project_name: str,
    task_names: list,
    new_status: str,
    db=None,
    emit_event: bool = False,
    workflow_session_id: Optional[str] = None,
    command_context: Optional[str] = None,
):
    """Update multiple tasks' status in a single call. Uses transition_task_status."""

    should_close = False
    if db is None:
        db_path = load_config(project_name=project_name).get_graph_db_path(project_name)
        db = GraphDatabase(db_path)
        should_close = True

    try:
        updated = []
        not_found = []
        warnings = []

        for task_name in task_names:
            # Find task UUID - check for duplicates
            result = db.conn.execute("""
                MATCH (p:Project {name: $project_name})-[:HAS_ENTITY]->(e:Entity)
                WHERE e.name = $task_name AND e.labels CONTAINS 'Task'
                RETURN e.uuid
            """, {
                "project_name": project_name,
                "task_name": task_name,
            })

            if not result.has_next():
                not_found.append(task_name)
                continue

            uuid = result.get_next()[0]

            # Check for duplicate names
            if result.has_next():
                warnings.append({"name": task_name, "error": "Multiple tasks with same name. Use --done N instead."})
                continue

            # Use transition helper
            trans_result = transition_task_status(project_name, uuid, new_status, db)

            if trans_result['ok']:
                if emit_event:
                    record_task_operation_event(
                        project_name,
                        new_status,
                        task_name,
                        task_uuid=uuid,
                        status_before=trans_result['old_status'],
                        status_after=trans_result['new_status'],
                        workflow_session_id=workflow_session_id,
                        command_context=command_context,
                    )
                updated.append({
                    "name": task_name,
                    "old_status": trans_result['old_status'],
                    "new_status": trans_result['new_status']
                })
            else:
                warnings.append({"name": task_name, "error": trans_result['error']})

        # Report results
        if updated:
            safe_print(f"\nBatch {new_status.upper()}: {len(updated)} tasks updated")
            for task in updated:
                safe_print(f"  OK {task['name']} ({task['old_status']} -> {task['new_status']})")

        if warnings:
            for warn in warnings:
                print_warning(f"  WARNING: {warn['name']}: {warn['error']}")

        if not_found:
            safe_print(f"\nNOT FOUND: {len(not_found)} tasks")
            for name in not_found:
                safe_print(f"  ? {name}")

        # Return success if at least one updated
        return len(updated) > 0

    finally:
        if should_close:
            db.close()


# NOTE: get_pending_tasks_ordered() was removed.
# Use get_actionable_tasks_ordered() instead - it returns the global actionable
# list (in_progress + pending) with display_number for all number-based operations.


def parse_number_ranges(range_str: str) -> list:
    """Parse number ranges like '1,3,5-8,10' into list of integers.

    Raises ValueError with helpful message if input is not numeric.
    """
    numbers = []
    try:
        for part in range_str.replace(' ', '').split(','):
            if '-' in part:
                start, end = part.split('-', 1)
                numbers.extend(range(int(start), int(end) + 1))
            else:
                numbers.append(int(part))
    except ValueError:
        raise ValueError(
            f"Expected task numbers (e.g., '1,3,5-8'), got: '{range_str}'\n"
            f"  Hint: Use --done N, --skip N, --start N, --pause N with task numbers from the list.\n"
            f"  For name-based operations, use --complete-file or --batch-done-file with JSON."
        )
    return numbers


def update_task_priority_by_uuid(
    project_name: str,
    task_uuids: list,
    new_priority: str,
    emit_event: bool = False,
    workflow_session_id: Optional[str] = None,
    command_context: Optional[str] = None,
):
    """Update priority for multiple tasks by UUID."""
    db_path = load_config(project_name=project_name).get_graph_db_path(project_name)
    db = GraphDatabase(db_path)

    try:
        updated = []
        not_found = []

        for task_uuid in task_uuids:
            result = db.conn.execute("""
                MATCH (e:Entity {uuid: $uuid})
                RETURN e.name, e.priority
            """, {"uuid": task_uuid})

            if not result.has_next():
                not_found.append(task_uuid)
                continue

            row = result.get_next()
            task_name = row[0]
            old_priority = row[1] or 'medium'

            db.conn.execute("""
                MATCH (e:Entity {uuid: $uuid})
                SET e.priority = $new_priority
            """, {"uuid": task_uuid, "new_priority": new_priority})

            if emit_event:
                record_task_operation_event(
                    project_name,
                    "set_priority",
                    task_name,
                    task_uuid=task_uuid,
                    priority_before=old_priority,
                    priority_after=new_priority,
                    workflow_session_id=workflow_session_id,
                    command_context=command_context,
                )

            updated.append({"name": task_name, "old": old_priority})

        safe_print(f"\nPRIORITY UPDATED: {len(updated)} tasks -> {new_priority.upper()}")
        for task in updated:
            safe_print(f"  OK {task['name']} ({task['old']} -> {new_priority})")

        if not_found:
            safe_print(f"\nNOT FOUND: {len(not_found)}")
            for uuid in not_found:
                safe_print(f"  ? {uuid}")
    finally:
        db.close()


def add_task(
    project_name: str,
    task_name: str,
    priority: str = 'medium',
    summary: str = '',
    emit_event: bool = False,
    workflow_session_id: Optional[str] = None,
    command_context: Optional[str] = None,
):
    """Add a new task."""

    db_path = load_config(project_name=project_name).get_graph_db_path(project_name)
    db = GraphDatabase(db_path)

    try:
        db.create_project_node(project_name, f"Project: {project_name}")

        # Create task entity
        entity_uuid = db.create_entity(
            name=task_name,
            summary=summary,
            labels=['Task'],
            attributes={},
            source_interactions=[],
            source_hashes=[],
            source_chain=[],
            group_id=project_name,
            extraction_version='manual',
            extraction_commit='manual',
            priority=priority,
            status='pending'
        )

        # Link to project
        db.link_project_to_entity(project_name, entity_uuid)

        if emit_event:
            record_task_operation_event(
                project_name,
                "add",
                task_name,
                task_uuid=entity_uuid,
                status_after="pending",
                priority_after=priority,
                workflow_session_id=workflow_session_id,
                command_context=command_context,
                payload={"summary": summary},
            )

        safe_print(f"\nOK Added task: {task_name}")
        safe_print(f"   Priority: {priority}")
        safe_print(f"   UUID: {entity_uuid}")
        return entity_uuid

    finally:
        db.close()


def normalize_stats_window(
    period: str,
    *,
    from_value: Optional[str] = None,
    to_value: Optional[str] = None,
    now: Optional[datetime] = None,
):
    """Return inclusive ISO timestamps for a task stats window."""
    now = now or datetime.now()

    if period == "today":
        start_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_dt = now.replace(hour=23, minute=59, second=59, microsecond=0)
    elif period == "week":
        end_dt = now.replace(hour=23, minute=59, second=59, microsecond=0)
        start_dt = (end_dt - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "month":
        end_dt = now.replace(hour=23, minute=59, second=59, microsecond=0)
        start_dt = (end_dt - timedelta(days=29)).replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "custom":
        if not from_value or not to_value:
            raise ValueError("--stats custom requires both --from and --to")
        start_dt = parse_datetime(from_value)
        end_dt = parse_datetime(to_value)
        if start_dt is None or end_dt is None:
            raise ValueError("Custom stats window requires ISO dates/times for --from and --to")
        if "T" not in from_value:
            start_dt = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        if "T" not in to_value:
            end_dt = end_dt.replace(hour=23, minute=59, second=59, microsecond=0)
    else:
        raise ValueError(f"Unsupported stats period: {period}")

    if start_dt > end_dt:
        raise ValueError("--from must be earlier than or equal to --to")

    return start_dt.isoformat(), end_dt.isoformat()


def normalize_explicit_window(from_value: str, to_value: str):
    """Return an inclusive ISO timestamp window from explicit date/time values."""
    start_dt = parse_datetime(from_value)
    end_dt = parse_datetime(to_value)
    if start_dt is None or end_dt is None:
        raise ValueError("Expected ISO dates/times for --from and --to")
    if "T" not in from_value:
        start_dt = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    if "T" not in to_value:
        end_dt = end_dt.replace(hour=23, minute=59, second=59, microsecond=0)
    if start_dt > end_dt:
        raise ValueError("--from must be earlier than or equal to --to")
    return start_dt.isoformat(), end_dt.isoformat()


def render_task_stats(
    project_name: str,
    period: str,
    start_time: str,
    end_time: str,
    *,
    verbose: bool = False,
) -> int:
    """Render task activity stats from SQL task operation history."""
    config = load_config(project_name=project_name)
    sql_db = SQLDatabase(config.get_sql_db_path())
    stats = sql_db.get_task_operation_stats(project_name=project_name, start=start_time, end=end_time)
    operations = sql_db.get_task_operations(project_name=project_name, start=start_time, end=end_time) if verbose else []

    safe_print("=" * 80)
    safe_print(f"TASK STATS - {project_name}")
    safe_print("=" * 80)
    safe_print(f"Period: {period}")
    safe_print(f"Window: {start_time} -> {end_time}")
    safe_print("")
    safe_print(f"Created:          {stats['created']}")
    safe_print(f"Started:          {stats['started']}")
    safe_print(f"Paused:           {stats['paused']}")
    safe_print(f"Completed:        {stats['completed']}")
    safe_print(f"Invalidated:      {stats['invalidated']}")
    safe_print(f"Priority changed: {stats['priority_changed']}")
    safe_print(f"Total events:     {stats['total_events']}")

    if verbose and operations:
        safe_print("")
        safe_print("EVENTS")
        for row in operations:
            label = get_task_event_display_label(row)
            short_hash = get_task_short_hash(row.get("task_uuid"))
            hash_str = f" [{short_hash}]" if short_hash else ""
            status_before = row.get("status_before") or "-"
            status_after = row.get("status_after") or "-"
            safe_print(
                f"  {row.get('created_at', '')}  {label}{hash_str}  "
                f"{row.get('task_name', '(unknown)')}  "
                f"({row.get('operation', '')}: {status_before} -> {status_after})"
            )

    return 0


def show_tasks_created_between(project_name: str, start_time: str, end_time: str) -> int:
    """Show tasks created in the graph during an inclusive time window."""
    db_path = load_config(project_name=project_name).get_graph_db_path(project_name)
    db = GraphDatabase(db_path)

    try:
        result = db.conn.execute("""
            MATCH (p:Project {name: $project_name})-[:HAS_ENTITY]->(e:Entity)
            WHERE e.labels CONTAINS 'Task'
              AND e.deleted_at IS NULL
              AND e.created_at >= $start_time
              AND e.created_at <= $end_time
            RETURN e.uuid, e.name, e.status, e.priority, e.created_at, e.summary
            ORDER BY e.created_at ASC
        """, {
            "project_name": project_name,
            "start_time": start_time,
            "end_time": end_time,
        })

        tasks = []
        while result.has_next():
            row = result.get_next()
            task_uuid = row[0] or ""
            unique_part = task_uuid[7:] if task_uuid.startswith("entity-") else task_uuid
            tasks.append({
                "uuid": task_uuid,
                "short_hash": unique_part[:7] if unique_part else "",
                "name": row[1],
                "status": row[2] or "pending",
                "priority": row[3] or "medium",
                "created_at": str(row[4]) if row[4] else "",
                "summary": row[5] or "",
            })

        safe_print("=" * 80)
        safe_print(f"TASKS CREATED - {project_name}")
        safe_print("=" * 80)
        safe_print(f"Window: {start_time} -> {end_time}")

        if not tasks:
            safe_print("\nNo tasks created in this window.")
            return 0

        for index, task in enumerate(tasks, start=1):
            safe_print(
                f"\n{index}. [{task['short_hash']}] [{task['priority'].upper()}] "
                f"{task['name']} ({task['status']})"
            )
            safe_print(f"   Created: {task['created_at']}")
            if task["summary"]:
                safe_print(f"   {task['summary']}")

        safe_print(f"\nTotal created tasks: {len(tasks)}")
        return 0
    finally:
        db.close()


def show_tasks_completed_between(project_name: str, start_time: str, end_time: str) -> int:
    """Show tasks completed during an inclusive time window (from task_operations)."""
    import sqlite3
    config = load_config(project_name=project_name)
    db_path = config.get_sql_db_path()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Query task_operations for 'complete' operations in the window
        cursor.execute("""
            SELECT task_uuid, task_name, created_at
            FROM task_operations
            WHERE project_name = ?
              AND operation = 'complete'
              AND created_at >= ?
              AND created_at <= ?
            ORDER BY created_at ASC
        """, (project_name, start_time, end_time))

        rows = cursor.fetchall()

        safe_print("=" * 80)
        safe_print(f"TASKS COMPLETED - {project_name}")
        safe_print("=" * 80)
        safe_print(f"Window: {start_time} -> {end_time}")

        if not rows:
            safe_print("\nNo tasks completed in this window.")
            return 0

        for index, row in enumerate(rows, start=1):
            task_uuid, task_name, completed_at = row
            # Extract short hash from uuid
            unique_part = task_uuid[7:] if task_uuid and task_uuid.startswith("entity-") else (task_uuid or "")
            short_hash = unique_part[:7] if unique_part else "???????"

            safe_print(f"\n{index}. [{short_hash}] {task_name}")
            safe_print(f"   Completed: {completed_at}")

        safe_print(f"\nTotal completed: {len(rows)}")
        return 0
    finally:
        conn.close()


TASKS_EXAMPLES = """
Examples:
  # List actionable tasks (shows hash IDs in brackets like [1fab266])
  python scripts/tasks.py --project llm_memory

  # Show task activity statistics
  python scripts/tasks.py --project llm_memory --stats today
  python scripts/tasks.py --project llm_memory --stats custom --from 2026-03-10 --to 2026-03-16

  # Show tasks created in the graph during a time window
  python scripts/tasks.py --project llm_memory --created-between --from 2026-03-10 --to 2026-03-16

  # Show tasks completed during a time window (queries task_operations)
  python scripts/tasks.py --project llm_memory --completed-between --from 2026-03-15 --to 2026-03-15

  # Mark task complete (use hash from task list)
  python scripts/tasks.py --project llm_memory --done 1fab266

  # Mark multiple tasks complete
  python scripts/tasks.py --project llm_memory --done 1fab266,c7dec3e

  # Mark task invalid/skipped
  python scripts/tasks.py --project llm_memory --skip abc1234

  # Start working on task (pending -> in_progress)
  python scripts/tasks.py --project llm_memory --start 1fab266

  # Pause task (in_progress -> pending)
  python scripts/tasks.py --project llm_memory --pause 1fab266

  # Edit task text using helper files
  python scripts/tasks.py --project llm_memory --edit 1fab266 --name-file tmp/task.txt
  python scripts/tasks.py --project llm_memory --edit 1fab266 --summary-file tmp/summary.txt
  python scripts/tasks.py --project llm_memory --edit 1fab266 --details-file tmp/details.txt

  # Set and clear blockers / parent task
  python scripts/tasks.py --project llm_memory --edit 1fab266 --blocked-by c7dec3e,abc1234
  python scripts/tasks.py --project llm_memory --edit 1fab266 --clear-blocked-by
  python scripts/tasks.py --project llm_memory --edit 1fab266 --parent c7dec3e
  python scripts/tasks.py --project llm_memory --edit 1fab266 --clear-parent

  # Add new task (use JSON file for names with spaces)
  python scripts/tasks.py --project llm_memory --add-file tmp/task.json

IMPORTANT: --done, --skip, --start, --pause, --set-priority, --edit require HASH identifiers, not numbers.
           Numbers shift after mutations. Hash IDs are stable.
"""


class TasksArgumentParser(argparse.ArgumentParser):
    """Custom parser that prints examples on error."""
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: error: {message}\n{TASKS_EXAMPLES}")


def build_parser():
    parser = TasksArgumentParser(
        description="Task Management",
        epilog=TASKS_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--project", required=True, help="Project name")
    parser.add_argument("--workflow-session-id", help="Optional workflow/session ID for structured task operation events")
    parser.add_argument("--stats", choices=["today", "week", "month", "custom"], help="Show task activity statistics for a time window")
    parser.add_argument("--created-between", action="store_true", help="Show tasks whose graph created_at falls within --from/--to")
    parser.add_argument("--completed-between", action="store_true", help="Show tasks completed within --from/--to (queries task_operations)")
    parser.add_argument("--from", dest="from_time", help="Start date/time for --stats custom (YYYY-MM-DD or ISO timestamp)")

    # Status filters (mutually exclusive)
    status_filter_group = parser.add_mutually_exclusive_group()
    status_filter_group.add_argument("--pending", action="store_true", help="Show only pending tasks")
    status_filter_group.add_argument("--in-progress", action="store_true", help="Show only in-progress tasks")
    parser.add_argument(
        "--all-statuses",
        action="store_true",
        help="Show closed tasks too (complete + invalid). Discouraged for normal workflow."
    )

    # Single task operations
    parser.add_argument("--complete", metavar="TASK_NAME", nargs='+', help="Mark task as complete")
    parser.add_argument("--complete-file", help="File containing task name to mark complete (RECOMMENDED)")
    parser.add_argument("--invalid", metavar="TASK_NAME", nargs='+', help="Mark task as invalid")
    parser.add_argument("--invalid-file", help="File containing task name to mark invalid (RECOMMENDED)")
    parser.add_argument("--add", metavar="TASK_NAME", nargs='+', help="Add new task")
    parser.add_argument("--add-file", help="File containing task name to add (RECOMMENDED)")
    parser.add_argument("--priority", choices=['high', 'medium', 'low'], default='medium', help="Priority for new task")
    parser.add_argument("--summary", default='', help="Summary for new task, or new summary for --edit")
    parser.add_argument("--summary-file", help="File containing task summary for --add or --edit (RECOMMENDED)")
    parser.add_argument("--edit", help="Edit a task by hash (e.g., --edit 1fab266)")
    parser.add_argument("--name", help="New task name for --edit")
    parser.add_argument("--name-file", help="File containing new task name for --edit (RECOMMENDED)")
    parser.add_argument("--blocked-by", help="Comma-separated blocker task hashes for --edit")
    parser.add_argument("--blocked-by-file", help="File containing comma-separated blocker task hashes for --edit")
    parser.add_argument("--clear-blocked-by", action="store_true", help="Clear blockers for --edit")
    parser.add_argument("--parent", help="Parent task hash for --edit")
    parser.add_argument("--parent-file", help="File containing parent task hash for --edit")
    parser.add_argument("--clear-parent", action="store_true", help="Clear parent task for --edit")
    parser.add_argument("--details-file", help="File containing task details text for --edit (RECOMMENDED)")

    # Batch operations (JSON file with {"tasks": ["name1", "name2", ...]})
    parser.add_argument("--batch-complete-file", help="JSON file with task names to mark complete")
    parser.add_argument("--batch-invalid-file", help="JSON file with task names to mark invalid")

    # Hash-based operations (use hash IDs from task list, e.g., [1fab266])
    parser.add_argument("--done", help="Mark tasks complete by hash (e.g., '1fab266,c7dec3e')")
    parser.add_argument("--skip", help="Mark tasks invalid by hash (e.g., 'abc1234')")
    parser.add_argument("--start", help="Start tasks (pending -> in_progress) by hash (e.g., '1fab266')")
    parser.add_argument("--pause", help="Pause tasks (in_progress -> pending) by hash (e.g., '1fab266')")

    # Priority filter and update
    parser.add_argument("--high", action="store_true", help="Show only HIGH priority tasks")
    parser.add_argument("--medium", action="store_true", help="Show only MEDIUM priority tasks")
    parser.add_argument("--low", action="store_true", help="Show only LOW priority tasks")
    parser.add_argument("--set-priority", help="Change priority of task(s) by hash (e.g., '1fab266,c7dec3e')")
    parser.add_argument("--to", help="New priority for --set-priority, or end date/time for --stats custom")

    # Display levels
    parser.add_argument("-v", "--verbose", action="store_true", help="Level 2: Show task summaries")
    parser.add_argument("--details", metavar="VALUE", help="Without --edit: show full context by hash. With --edit: set task details text.")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    mutation_args = [
        args.complete,
        args.complete_file,
        args.invalid,
        args.invalid_file,
        args.add,
        args.add_file,
        args.batch_complete_file,
        args.batch_invalid_file,
        args.done,
        args.skip,
        args.start,
        args.pause,
        args.set_priority,
        args.edit,
    ]
    if args.name and args.name_file:
        parser.error("--name and --name-file cannot be combined")
    if args.blocked_by and args.blocked_by_file:
        parser.error("--blocked-by and --blocked-by-file cannot be combined")
    if args.parent and args.parent_file:
        parser.error("--parent and --parent-file cannot be combined")
    if args.details and args.details_file:
        parser.error("--details and --details-file cannot be combined")
    if args.name_file and not args.edit:
        parser.error("--name-file requires --edit")
    if args.summary_file and not args.edit and not args.add and not args.add_file:
        parser.error("--summary-file requires --add/--add-file or --edit")
    if args.blocked_by_file and not args.edit:
        parser.error("--blocked-by-file requires --edit")
    if args.parent_file and not args.edit:
        parser.error("--parent-file requires --edit")
    if args.details_file and not args.edit:
        parser.error("--details-file requires --edit")

    edit_name_value = args.name
    edit_summary_value = args.summary if args.summary != '' else None
    edit_blocked_by_value = args.blocked_by
    edit_parent_value = args.parent
    edit_details_value = args.details if args.edit else None
    if args.name_file:
        edit_name_value = read_text_file(args.name_file)
    if args.summary_file and args.edit:
        edit_summary_value = read_text_file(args.summary_file)
    if args.blocked_by_file:
        edit_blocked_by_value = read_text_file(args.blocked_by_file)
    if args.parent_file:
        edit_parent_value = read_text_file(args.parent_file)
    if args.details_file:
        edit_details_value = read_text_file(args.details_file)

    if args.stats and any(value for value in mutation_args):
        parser.error("--stats cannot be combined with task mutation flags")
    if args.created_between and any(value for value in mutation_args):
        parser.error("--created-between cannot be combined with task mutation flags")
    if args.completed_between and any(value for value in mutation_args):
        parser.error("--completed-between cannot be combined with task mutation flags")
    if args.stats and args.details and not args.edit:
        parser.error("--stats cannot be combined with --details")
    if args.created_between and args.details and not args.edit:
        parser.error("--created-between cannot be combined with --details")
    if args.completed_between and args.details and not args.edit:
        parser.error("--completed-between cannot be combined with --details")
    if args.stats and args.created_between:
        parser.error("--stats cannot be combined with --created-between")
    if args.stats and args.completed_between:
        parser.error("--stats cannot be combined with --completed-between")
    if args.created_between and args.completed_between:
        parser.error("--created-between cannot be combined with --completed-between")
    if args.stats and args.stats != "custom" and (args.from_time or (args.to and not args.set_priority)):
        parser.error("--from/--to are only valid with --stats custom")
    if not args.stats and args.from_time:
        if not args.created_between and not args.completed_between:
            parser.error("--from is only valid with --stats custom, --created-between, or --completed-between")
    if not args.stats and args.to and not args.set_priority and not args.created_between and not args.completed_between:
        parser.error("--to is only valid with --set-priority, --stats custom, --created-between, or --completed-between")

    if args.stats:
        try:
            start_time, end_time = normalize_stats_window(
                args.stats,
                from_value=args.from_time,
                to_value=args.to if args.stats == "custom" else None,
            )
        except ValueError as exc:
            parser.error(str(exc))
        return render_task_stats(args.project, args.stats, start_time, end_time, verbose=args.verbose)

    if args.created_between:
        if not args.from_time or not args.to:
            parser.error("--created-between requires both --from and --to")
        try:
            start_time, end_time = normalize_explicit_window(args.from_time, args.to)
        except ValueError as exc:
            parser.error(str(exc))
        return show_tasks_created_between(args.project, start_time, end_time)

    if args.completed_between:
        if not args.from_time or not args.to:
            parser.error("--completed-between requires both --from and --to")
        try:
            start_time, end_time = normalize_explicit_window(args.from_time, args.to)
        except ValueError as exc:
            parser.error(str(exc))
        return show_tasks_completed_between(args.project, start_time, end_time)

    if args.edit:
        edit_fields_present = any([
            edit_name_value is not None,
            edit_summary_value is not None,
            edit_details_value is not None,
            edit_blocked_by_value is not None,
            args.clear_blocked_by,
            edit_parent_value is not None,
            args.clear_parent,
        ])
        if not edit_fields_present:
            parser.error("--edit requires at least one edit field (--name/--name-file, --summary/--summary-file, --details/--details-file, --blocked-by/--blocked-by-file, --clear-blocked-by, --parent/--parent-file, --clear-parent)")
        if edit_parent_value and args.clear_parent:
            parser.error("--parent and --clear-parent cannot be combined")
        if edit_blocked_by_value and args.clear_blocked_by:
            parser.error("--blocked-by and --clear-blocked-by cannot be combined")

        actionable = get_actionable_tasks_ordered(args.project)
        task, error = resolve_task_identifier(args.edit, actionable)
        if error:
            safe_print(f"Error: {error}")
            safe_print("\n" + "="*80)
            safe_print("TASK LIST (use hash IDs shown in brackets for --edit):")
            safe_print("="*80)
            show_tasks(args.project, verbose=False)
            sys.exit(1)

        db_path = load_config(project_name=args.project).get_graph_db_path(args.project)
        db = GraphDatabase(db_path)
        try:
            task_map = get_project_task_map(args.project, db)
            blocked_by_value = UNSET
            if args.clear_blocked_by:
                blocked_by_value = []
            elif edit_blocked_by_value is not None:
                blocked_by_value = []
                seen = set()
                for ident in parse_task_identifiers(edit_blocked_by_value):
                    blocker, blocker_error = resolve_task_identifier(ident, actionable)
                    if blocker_error:
                        parser.error(f"Invalid hash '{ident}' - operation cancelled")
                    if blocker["uuid"] == task["uuid"]:
                        parser.error("Task cannot block itself")
                    if blocker["status"] in {"complete", "invalid"}:
                        parser.error(f"Closed tasks cannot be blockers: {blocker['name']}")
                    if blocker["uuid"] not in seen:
                        blocked_by_value.append(blocker["uuid"])
                        seen.add(blocker["uuid"])

            parent_value = UNSET
            if args.clear_parent:
                parent_value = None
            elif edit_parent_value is not None:
                parent_task, parent_error = resolve_task_identifier(edit_parent_value, actionable)
                if parent_error:
                    parser.error(f"Invalid hash '{edit_parent_value}' - operation cancelled")
                if parent_task["uuid"] == task["uuid"]:
                    parser.error("Task cannot be its own parent")
                if parent_task["status"] in {"complete", "invalid"}:
                    parser.error(f"Closed tasks cannot be parents: {parent_task['name']}")
                parent_entity = task_map.get(parent_task["uuid"])
                if parent_entity and parent_entity["attributes"].get("parent_task_uuid") == task["uuid"]:
                    parser.error("Direct parent cycle detected")
                parent_value = parent_task["uuid"]

            result = update_task_entity(
                args.project,
                task["uuid"],
                name=edit_name_value if edit_name_value is not None else UNSET,
                summary=edit_summary_value if edit_summary_value is not None else UNSET,
                details=edit_details_value if edit_details_value is not None else UNSET,
                blocked_by=blocked_by_value,
                parent_task_uuid=parent_value,
                db=db,
                emit_event=True,
                workflow_session_id=args.workflow_session_id,
                command_context="tasks.py --edit",
            )
        finally:
            db.close()

        if not result["ok"]:
            print_warning(f"ERROR: {result['error']}")
            return 1

        safe_print("\nTASK UPDATED:")
        safe_print(f"  OK #{task['display_number']} [{task['short_hash']}] {result['task_name']}")
        safe_print(f"  Fields changed: {', '.join(result['fields_changed'])}")
        return 0

    # Handle --details first (Level 3 display)
    if args.details:
        actionable = get_actionable_tasks_ordered(args.project)
        task, error = resolve_task_identifier(args.details, actionable)
        if error:
            safe_print(f"Error: {error}")
            safe_print("\n" + "="*80)
            safe_print("TASK LIST (use hash IDs shown in brackets for --details):")
            safe_print("="*80)
            show_tasks(args.project, verbose=False)
            sys.exit(1)
        show_task_details(args.project, task['display_number'])
        return 0

    # Handle task operations (supports hash identifiers only)
    def process_task_identifiers(identifiers_str, new_status, action_msg):
        """Helper to resolve task identifiers and apply transition.

        On error, prints the full task list so LLMs can retry with correct hashes.
        """
        try:
            identifiers = parse_task_identifiers(identifiers_str)
        except ValueError as e:
            parser.error(str(e))

        actionable = get_actionable_tasks_ordered(args.project)

        # First pass: resolve all identifiers and collect errors
        resolved_tasks = []
        errors = []
        for ident in identifiers:
            task, error = resolve_task_identifier(ident, actionable)
            if error:
                errors.append(error)
            else:
                resolved_tasks.append(task)

        # If ALL identifiers failed, show errors + task list, no action message
        if not resolved_tasks:
            for err in errors:
                print_warning(f"ERROR: {err}")
            safe_print("\n" + "="*80)
            safe_print("TASK LIST (use hash IDs shown in brackets for operations):")
            safe_print("="*80)
            show_tasks(args.project, verbose=False)
            return 0

        # Some tasks resolved - proceed with action
        safe_print(action_msg)

        # Print any errors first
        for err in errors:
            print_warning(f"  ERROR: {err}")

        # Process resolved tasks
        success_count = 0
        had_transition_errors = False
        for task in resolved_tasks:
            result = transition_task_status(args.project, task['uuid'], new_status)
            if result['ok']:
                record_task_operation_event(
                    args.project,
                    new_status,
                    task['name'],
                    task_uuid=task['uuid'],
                    status_before=result['old_status'],
                    status_after=result['new_status'],
                    priority_before=task.get('priority'),
                    priority_after=task.get('priority'),
                    workflow_session_id=args.workflow_session_id,
                    command_context=f"tasks.py --{new_status}",
                )
                safe_print(f"  OK #{task['display_number']} [{task['short_hash']}] {task['name']}: {result['old_status']} -> {result['new_status']}")
                success_count += 1
            else:
                print_warning(f"  ERROR: #{task['display_number']} [{task['short_hash']}] {task['name']}: {result['error']}")
                had_transition_errors = True

        # On any error, print the task list so LLM can retry with correct hash
        if errors or had_transition_errors:
            safe_print("\n" + "="*80)
            safe_print("TASK LIST (use hash IDs shown in brackets for operations):")
            safe_print("="*80)
            show_tasks(args.project, verbose=False)

        return success_count

    if args.done:
        count = process_task_identifiers(args.done, 'complete', "\nMarking tasks as complete:")
        return 0 if count > 0 else 1

    if args.skip:
        count = process_task_identifiers(args.skip, 'invalid', "\nMarking tasks as invalid:")
        return 0 if count > 0 else 1

    if args.start:
        count = process_task_identifiers(args.start, 'in_progress', "\nStarting tasks (pending -> in_progress):")
        return 0 if count > 0 else 1

    if args.pause:
        count = process_task_identifiers(args.pause, 'pending', "\nPausing tasks (in_progress -> pending):")
        return 0 if count > 0 else 1

    # Handle priority change
    if args.set_priority:
        if not args.to:
            parser.error("--set-priority requires --to high|medium|low")
        if args.to not in {"high", "medium", "low"}:
            parser.error("--set-priority requires --to high|medium|low")
        try:
            identifiers = parse_task_identifiers(args.set_priority)
        except ValueError as e:
            parser.error(str(e))
        actionable = get_actionable_tasks_ordered(args.project)
        task_uuids = []
        had_errors = False
        for ident in identifiers:
            task, error = resolve_task_identifier(ident, actionable)
            if error:
                print_warning(f"ERROR: {error}")
                had_errors = True
                continue
            task_uuids.append(task['uuid'])

        # On any error, print the task list so LLM can retry with correct hash
        if had_errors:
            safe_print("\n" + "="*80)
            safe_print("TASK LIST (use hash IDs shown in brackets for --set-priority):")
            safe_print("="*80)
            show_tasks(args.project, verbose=False)

        if task_uuids:
            update_task_priority_by_uuid(
                args.project,
                task_uuids,
                args.to,
                emit_event=True,
                workflow_session_id=args.workflow_session_id,
                command_context="tasks.py --set-priority",
            )
        return 0 if task_uuids else 1

    # Handle batch operations
    if args.batch_complete_file:
        with open(args.batch_complete_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            task_names = data.get("tasks", [])
        success = batch_update_tasks(
            args.project,
            task_names,
            'complete',
            emit_event=True,
            workflow_session_id=args.workflow_session_id,
            command_context="tasks.py --batch-complete-file",
        )
        return 0 if success else 1

    if args.batch_invalid_file:
        with open(args.batch_invalid_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            task_names = data.get("tasks", [])
        success = batch_update_tasks(
            args.project,
            task_names,
            'invalid',
            emit_event=True,
            workflow_session_id=args.workflow_session_id,
            command_context="tasks.py --batch-invalid-file",
        )
        return 0 if success else 1

    # Read from files if provided (single task operations)
    complete_name = None
    if args.complete_file:
        with open(args.complete_file, 'r', encoding='utf-8') as f:
            complete_name = f.read().strip()
    elif args.complete:
        complete_name = ' '.join(args.complete)

    invalid_name = None
    if args.invalid_file:
        with open(args.invalid_file, 'r', encoding='utf-8') as f:
            invalid_name = f.read().strip()
    elif args.invalid:
        invalid_name = ' '.join(args.invalid)

    add_name = None
    add_priority = args.priority
    add_summary = args.summary

    if args.add_file:
        with open(args.add_file, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            # Try JSON first, fall back to plain text (just name)
            try:
                data = json.loads(content)
                add_name = data.get('name', '').strip()
                add_summary = data.get('summary', add_summary)
                add_priority = data.get('priority', add_priority)
                if not add_name:
                    print("[ERROR] JSON must contain 'name' field")
                    return 1
            except json.JSONDecodeError:
                # Plain text = just the task name
                add_name = content
    elif args.add:
        add_name = ' '.join(args.add)

    # Override summary from --summary-file if provided
    if args.summary_file and not args.edit:
        add_summary = read_text_file(args.summary_file)

    # Execute commands
    if complete_name:
        success = update_task_status(
            args.project,
            complete_name,
            'complete',
            emit_event=True,
            workflow_session_id=args.workflow_session_id,
            command_context="tasks.py --complete",
        )
        return 0 if success else 1
    elif invalid_name:
        success = update_task_status(
            args.project,
            invalid_name,
            'invalid',
            emit_event=True,
            workflow_session_id=args.workflow_session_id,
            command_context="tasks.py --invalid",
        )
        return 0 if success else 1
    elif add_name:
        add_task(
            args.project,
            add_name,
            add_priority,
            add_summary,
            emit_event=True,
            workflow_session_id=args.workflow_session_id,
            command_context="tasks.py --add",
        )
        return 0
    else:
        # Determine priority filter
        priority_filter = None
        if args.high:
            priority_filter = 'high'
        elif args.medium:
            priority_filter = 'medium'
        elif args.low:
            priority_filter = 'low'

        # Handle --in-progress flag (argparse converts to in_progress)
        in_progress_only = getattr(args, 'in_progress', False)

        show_tasks(
            args.project,
            args.pending,
            in_progress_only,
            priority_filter,
            args.verbose,
            include_closed=args.all_statuses
        )
        return 0


if __name__ == "__main__":
    sys.exit(main())
