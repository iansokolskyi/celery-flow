"""Task event definitions.

This module defines the core event model for Celery task lifecycle tracking.
Events are immutable records of task state transitions, captured via Celery signals.

Example:
    >>> from datetime import datetime, UTC
    >>> event = TaskEvent(
    ...     task_id="abc-123",
    ...     name="myapp.tasks.send_email",
    ...     state=TaskState.STARTED,
    ...     timestamp=datetime.now(UTC),
    ... )
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict


class TaskState(str, Enum):
    """Celery task execution states.

    Inherits from str for easy comparison with string values.
    Covers all standard Celery task states.

    Terminal states: SUCCESS, FAILURE, REVOKED, REJECTED
    Non-terminal states: PENDING, RECEIVED, STARTED, RETRY

    Example:
        >>> TaskState.SUCCESS == "SUCCESS"
        True
        >>> TaskState.FAILURE in {"SUCCESS", "FAILURE"}
        True
    """

    PENDING = "PENDING"
    """Task is waiting for execution (default initial state)."""

    RECEIVED = "RECEIVED"
    """Task was received by a worker."""

    STARTED = "STARTED"
    """Task execution has begun."""

    SUCCESS = "SUCCESS"
    """Task completed successfully (terminal)."""

    FAILURE = "FAILURE"
    """Task raised an exception (terminal)."""

    REVOKED = "REVOKED"
    """Task was revoked/cancelled (terminal)."""

    REJECTED = "REJECTED"
    """Task was rejected by worker (terminal)."""

    RETRY = "RETRY"
    """Task is being retried after failure."""


class TaskEvent(BaseModel):
    """Immutable task lifecycle event.

    Represents a single state transition in a Celery task's lifecycle.
    Events are frozen (immutable) and can be safely hashed and compared.

    Attributes:
        task_id: Unique Celery task identifier (UUID).
        name: Fully qualified task name (e.g., "myapp.tasks.send_email").
        state: Current task state at the time of this event.
        timestamp: UTC timestamp when the event occurred.
        parent_id: Parent task ID if spawned by another task.
        root_id: Root task ID in a chain/group/chord.
        trace_id: Optional correlation ID for distributed tracing.
        retries: Current retry attempt number (0 = first attempt).

    Example:
        >>> from datetime import datetime, UTC
        >>> event = TaskEvent(
        ...     task_id="abc-123",
        ...     name="myapp.tasks.send_email",
        ...     state=TaskState.STARTED,
        ...     timestamp=datetime.now(UTC),
        ...     parent_id="parent-456",
        ...     retries=1,
        ... )
        >>> event.model_dump_json()  # Serialize to JSON
    """

    model_config = ConfigDict(frozen=True)

    task_id: str
    name: str
    state: TaskState
    timestamp: datetime
    parent_id: str | None = None
    root_id: str | None = None
    trace_id: str | None = None
    retries: int = 0
