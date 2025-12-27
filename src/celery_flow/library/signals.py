"""Celery signal handlers for task lifecycle events."""

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from celery.signals import (
    task_failure,
    task_postrun,
    task_prerun,
    task_retry,
    task_revoked,
)

from celery_flow.core.events import TaskEvent, TaskState
from celery_flow.core.ports import EventTransport

if TYPE_CHECKING:
    from celery import Task

logger = logging.getLogger(__name__)

_transport: EventTransport | None = None


def _publish_event(event: TaskEvent) -> None:
    """Publish event via transport. Fire-and-forget: logs errors, never raises."""
    if _transport is None:
        logger.warning("celery-flow not initialized, event dropped: %s", event.task_id)
        return

    try:
        _transport.publish(event)
    except Exception:
        logger.warning(
            "Failed to publish event for task %s", event.task_id, exc_info=True
        )


def _on_task_prerun(
    task_id: str,
    task: "Task",
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    **_: Any,
) -> None:
    del args, kwargs
    _publish_event(
        TaskEvent(
            task_id=task_id,
            name=task.name,
            state=TaskState.STARTED,
            timestamp=datetime.now(timezone.utc),
            parent_id=getattr(task.request, "parent_id", None),
            root_id=getattr(task.request, "root_id", None),
            retries=task.request.retries or 0,
        )
    )


def _on_task_postrun(
    task_id: str,
    task: "Task",
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    retval: Any,
    state: str,
    **_: Any,
) -> None:
    del args, kwargs, retval
    if state != "SUCCESS":
        return

    _publish_event(
        TaskEvent(
            task_id=task_id,
            name=task.name,
            state=TaskState.SUCCESS,
            timestamp=datetime.now(timezone.utc),
            parent_id=getattr(task.request, "parent_id", None),
            root_id=getattr(task.request, "root_id", None),
            retries=task.request.retries or 0,
        )
    )


def _on_task_failure(
    task_id: str,
    exception: BaseException,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    traceback: Any,
    einfo: Any,
    sender: "Task",
    **_: Any,
) -> None:
    del args, kwargs, traceback, einfo, exception
    _publish_event(
        TaskEvent(
            task_id=task_id,
            name=sender.name,
            state=TaskState.FAILURE,
            timestamp=datetime.now(timezone.utc),
            parent_id=getattr(sender.request, "parent_id", None),
            root_id=getattr(sender.request, "root_id", None),
            retries=sender.request.retries or 0,
        )
    )


def _on_task_retry(
    sender: "Task",
    request: Any,
    reason: Any,
    einfo: Any,
    **_: Any,
) -> None:
    del reason, einfo
    _publish_event(
        TaskEvent(
            task_id=request.id,
            name=sender.name,
            state=TaskState.RETRY,
            timestamp=datetime.now(timezone.utc),
            parent_id=getattr(request, "parent_id", None),
            root_id=getattr(request, "root_id", None),
            retries=(request.retries or 0) + 1,
        )
    )


def _on_task_revoked(
    request: Any,
    terminated: bool,
    signum: int | None,
    expired: bool,
    sender: "Task",
    **_: Any,
) -> None:
    del terminated, signum, expired
    _publish_event(
        TaskEvent(
            task_id=request.id,
            name=sender.name,
            state=TaskState.REVOKED,
            timestamp=datetime.now(timezone.utc),
            parent_id=getattr(request, "parent_id", None),
            root_id=getattr(request, "root_id", None),
            retries=getattr(request, "retries", 0) or 0,
        )
    )


def connect_signals(transport: EventTransport) -> None:
    """Register signal handlers with the given transport."""
    global _transport
    _transport = transport

    task_prerun.connect(_on_task_prerun)
    task_postrun.connect(_on_task_postrun)
    task_failure.connect(_on_task_failure)
    task_retry.connect(_on_task_retry)
    task_revoked.connect(_on_task_revoked)

    logger.info("celery-flow signal handlers connected")


def disconnect_signals() -> None:
    """Disconnect all signal handlers."""
    global _transport
    _transport = None

    task_prerun.disconnect(_on_task_prerun)
    task_postrun.disconnect(_on_task_postrun)
    task_failure.disconnect(_on_task_failure)
    task_retry.disconnect(_on_task_retry)
    task_revoked.disconnect(_on_task_revoked)

    logger.info("celery-flow signal handlers disconnected")
