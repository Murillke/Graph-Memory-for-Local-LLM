"""
Database utilities for graph DB connection handling.
"""

import time
from typing import Callable, TypeVar, Tuple

import kuzu

from tools.console_utils import safe_print


T = TypeVar("T")


def is_kuzu_lock_error(error: Exception) -> bool:
    """Return True if the exception looks like a Kuzu file-lock error."""
    message = str(error)
    return "Could not set lock" in message or "lock on file" in message


def with_kuzu_retry(
    operation_name: str = "graph DB operation",
    max_retries: int = 5,
    initial_delay: float = 0.1,
    backoff_multiplier: float = 2.0,
):
    """
    Retry Kuzu operations on lock contention using exponential backoff.
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args, **kwargs) -> T:
            delay = initial_delay
            last_error = None

            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    last_error = exc
                    if not is_kuzu_lock_error(exc) or attempt == max_retries:
                        raise

                    safe_print(
                        f"[RETRY] {operation_name} locked, retrying in {delay:.1f}s "
                        f"(attempt {attempt}/{max_retries})"
                    )
                    time.sleep(delay)
                    delay *= backoff_multiplier

            raise last_error

        return wrapper

    return decorator


@with_kuzu_retry(operation_name="opening graph database")
def open_kuzu_database(db_path: str) -> Tuple[kuzu.Database, kuzu.Connection]:
    """Open a Kuzu database and connection with retry-on-lock behavior."""
    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    return db, conn
