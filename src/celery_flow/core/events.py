"""Task event definitions."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict


class TaskState(str, Enum):
    """Celery task states. Inherits from str for easy comparison."""

    PENDING = "PENDING"
    RECEIVED = "RECEIVED"
    STARTED = "STARTED"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    REVOKED = "REVOKED"
    REJECTED = "REJECTED"
    RETRY = "RETRY"


class TaskEvent(BaseModel):
    """Immutable task lifecycle event.

    Frozen model that can be hashed and compared. Captures a single
    state transition in a Celery task's lifecycle.
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
