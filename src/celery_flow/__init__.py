"""celery-flow: A lightweight Celery task flow visualizer.

Usage:
    from celery_flow import init
    init(app)
"""

from typing import TYPE_CHECKING

from celery_flow.core.events import TaskEvent, TaskState
from celery_flow.core.graph import TaskGraph, TaskNode

if TYPE_CHECKING:
    from celery import Celery

__version__ = "0.1.0"
__all__ = [
    "TaskEvent",
    "TaskGraph",
    "TaskNode",
    "TaskState",
    "__version__",
    "init",
]


def init(
    app: "Celery",
    *,
    transport_url: str | None = None,
    prefix: str = "celery_flow",
    ttl: int = 86400,
    redact_args: bool = True,
) -> None:
    """Initialize celery-flow event tracking.

    Args:
        app: The Celery application instance.
        transport_url: Broker URL for events. If None, uses Celery's broker_url.
        prefix: Key/queue prefix for events.
        ttl: Event TTL in seconds (default: 24 hours).
        redact_args: Whether to hash sensitive arguments.

    Example:
        >>> from celery import Celery
        >>> from celery_flow import init
        >>> app = Celery("myapp", broker="redis://localhost:6379/0")
        >>> init(app)
    """
    # TODO: Implement signal handler registration
    _ = app, transport_url, prefix, ttl, redact_args
