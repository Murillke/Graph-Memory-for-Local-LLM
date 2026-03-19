# Tasks "In Progress" Status - Implementation Plan

**Status:** Approved for implementation
**Reviewed by:** Codex (read-only), Auggie
**Date:** 2026-03-13

---

## Summary

Add `in_progress` status to tasks.py with proper state machine, global numbering, and filter behavior.

**Key rule:** Default output = actionable list (in_progress + pending). All number-based operations resolve from this single list.

---

## Core Abstractions

### 1. `get_actionable_tasks_ordered(project_name, db=None)`

```python
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
```

### 2. `transition_task_status(project_name, task_uuid, new_status, db=None)`

```python
"""Loads current status from DB, validates transition, applies side effects.

Returns: {
    'task_name': str,
    'old_status': str,
    'new_status': str,
    'ok': bool,
    'error': str | None
}

Side effects:
  - pending -> in_progress: sets attributes.started_at
  - in_progress -> pending: clears attributes.started_at

On malformed attributes: treat as {}, warn to stderr, continue.
"""
```

---

## Valid State Transitions

```
pending -> in_progress  (--start)     OK, sets started_at
pending -> complete     (--done)      OK
pending -> invalid      (--skip)      OK
pending -> pending      (--pause)     WARN "not in progress", no-op

in_progress -> in_progress (--start)  WARN "already in progress", no-op
in_progress -> complete (--done)      OK
in_progress -> invalid  (--skip)      OK
in_progress -> pending  (--pause)     OK, clears started_at

complete -> complete                  WARN "already complete", no-op
complete -> *                         WARN "already complete", no-op

invalid -> invalid                    WARN "already invalid", no-op
invalid -> *                          WARN "already invalid", no-op
```

---

## CLI Flags

| Flag | Action | Transition |
|------|--------|------------|
| `--start N[,M,X-Y]` | Start working on task | pending -> in_progress |
| `--pause N[,M,X-Y]` | Pause task | in_progress -> pending |
| `--done N[,M,X-Y]` | Complete task | pending or in_progress -> complete |
| `--skip N[,M,X-Y]` | Invalidate task | pending or in_progress -> invalid |
| `--in-progress` | Filter: show only in_progress | (display only) |
| `--pending` | Filter: show only pending | (display only) |

---

## Display Format

```
================================================================================
TASKS - llm_memory
================================================================================

IN PROGRESS (1)
  1. [HIGH] Semantic Code Graph (started 2h ago)

PENDING (3)
  2. [HIGH] Commit preparation (2 days ago)
  3. [MEDIUM] Phase 4 Extensions (8h ago)
  4. [MEDIUM] Docs classification (2 days ago)

================================================================================
```

### Filtered View Example (--pending)

```
PENDING (3)
  2. [HIGH] Commit preparation (2 days ago)
  3. [MEDIUM] Phase 4 Extensions (8h ago)
  4. [MEDIUM] Docs classification (2 days ago)
```

Note: Numbers preserved from global list. Gaps are intentional.

---

## Contracts

| Contract | Rule |
|----------|------|
| **Filter numbering** | Filtered views preserve global actionable numbering. Gaps expected. |
| **`--details N`** | Resolves from global actionable numbering, including when N is seen in a filtered view. |
| **Exit codes** | `0` when at least 1 transition succeeds. Example: if 3 succeed and 2 fail, return 0. Non-zero only if all failed or input invalid. |
| **`attributes.started_at`** | Only used for display when `status == 'in_progress'`. Ignored on pending tasks (even if present from old bad data). |
| **`status IS NULL`** | Treated as `pending`. Backward-compatibility. |
| **`--set-priority`** | Resolves from actionable list only. Complete/invalid tasks are not addressable by number. |
| **Malformed `attributes`** | Treat as `{}`, warn to stderr, continue. |
| **Warnings** | Use stderr (not stdout). See implementation checklist for `print_warning()` helper. |

---

## Age Display Rules

| Status | Condition | Display |
|--------|-----------|---------|
| `in_progress` | `started_at` exists | "started 2h ago" |
| `in_progress` | `started_at` missing | "in progress" |
| `pending` | any | "2 days ago" (from created_at) |

---

## All Status Update Paths (Must Use Transition Helper)

| Path | Change Required |
|------|-----------------|
| `--done N` | Use `transition_task_status()` |
| `--skip N` | Use `transition_task_status()` |
| `--start N` | Use `transition_task_status()` |
| `--pause N` | Use `transition_task_status()` |
| `--complete-file` | Use `transition_task_status()` |
| `--invalid-file` | Use `transition_task_status()` |
| `--batch-complete-file` | Use `transition_task_status()` |
| `--batch-invalid-file` | Use `transition_task_status()` |

---

## Implementation Checklist

- [x] **1. Add `print_warning()` helper**
  - Print to sys.stderr instead of stdout
  - Current code uses safe_print() to stdout; add stderr variant

- [x] **2. Add `get_actionable_tasks_ordered()`**
  - Query `status IN ('in_progress', 'pending') OR status IS NULL`
  - Sort: in_progress first, then pending; within each: high->medium->low, newest first
  - Return list with display_number, uuid, name, status, priority, created_at, attributes
  - Parse attributes JSON; use {} on error and warn

- [x] **3. Add `transition_task_status()`**
  - Load current status from DB
  - Validate against transition matrix
  - Handle malformed attributes (warn to stderr, use {})
  - Apply side effects (started_at)
  - Return result dict

- [x] **4. Refactor all status update paths**
  - All 8 paths must use `transition_task_status()`

- [x] **5. Update `show_tasks()`**
  - Add IN PROGRESS section
  - Use `get_actionable_tasks_ordered()` for numbering
  - Filters preserve global numbers (show gaps)
  - Show appropriate age format per status

- [x] **6. Add CLI flags**
  - `--start`, `--pause`, `--in-progress`
  - All use `parse_number_ranges()`

- [x] **7. Update `--set-priority`**
  - Use `get_actionable_tasks_ordered()`

- [x] **8. Update `--details`**
  - Use `get_actionable_tasks_ordered()`
  - Error message if N not in actionable list

- [x] **9. Add tests (10 cases)**
  - test_global_numbering_preserved_in_filters
  - test_start_transition
  - test_pause_transition
  - test_done_from_pending
  - test_done_from_in_progress
  - test_invalid_transition_warning
  - test_in_progress_filter
  - test_started_age_display
  - test_null_status_as_pending
  - test_malformed_attributes_handling

- [x] **10. Update tasks.md**
  - Document new flags
  - Document filter behavior (global numbers preserved)
  - Add state transition diagram
  - Document backward-compatibility (NULL = pending)

---

## Documentation Note for tasks.md

> **Filtered views and numbering:** When using filters like `--pending` or `--in-progress`, task numbers are preserved from the global actionable list. This means you may see gaps (e.g., tasks numbered 2, 3, 4 when task 1 is in-progress). This is intentional - the number you see is always the number you use for actions like `--done` or `--start`.

---

## State Diagram (ASCII)

```
                     +-------------+
                     |   pending   |
                     +------+------+
                            |
           +----------------+----------------+
           |                |                |
       --start           --done           --skip
           |                |                |
           v                v                v
    +--------------+   +-----------+   +-----------+
    | in_progress  |   | complete  |   |  invalid  |
    +------+-------+   +-----------+   +-----------+
           |                                 ^
           +--- --done ---> complete         |
           |                                 |
           +--- --skip ----------------------+
           |
       --pause
           |
           v
      (back to pending)
```

