"""celery-flow: A lightweight Celery task flow visualizer.

Usage:
    from celery_flow import init
    init(app)
"""

from typing import TYPE_CHECKING

from celery_flow.core.events import TaskEvent, TaskState
from celery_flow.core.exceptions import ConfigurationError
from celery_flow.core.graph import TaskGraph, TaskNode
from celery_flow.library.config import CeleryFlowConfig, set_config
from celery_flow.library.signals import connect_signals
from celery_flow.library.transports import get_transport

if TYPE_CHECKING:
    from celery import Celery

__version__ = "0.1.0"
__all__ = [
    "ConfigurationError",
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

    Connects to Celery's task signals and publishes lifecycle events
    to the configured transport (Redis, RabbitMQ, etc.).

    Args:
        app: The Celery application instance.
        transport_url: Broker URL for events. If None, uses Celery's broker_url.
        prefix: Key/queue prefix for events.
        ttl: Event TTL in seconds (default: 24 hours).
        redact_args: Whether to hash sensitive arguments.

    Raises:
        ConfigurationError: If no broker URL can be determined.

    Example:
        >>> from celery import Celery
        >>> from celery_flow import init
        >>> app = Celery("myapp", broker="redis://localhost:6379/0")
        >>> init(app)

        # With explicit transport URL:
        >>> init(app, transport_url="redis://events-redis:6379/1")
    """
    url = transport_url or app.conf.broker_url
    if not url:
        raise ConfigurationError(
            "No broker URL available. Either pass transport_url or configure "
            "Celery's broker_url."
        )

    config = CeleryFlowConfig(
        transport_url=url,
        prefix=prefix,
        ttl=ttl,
        redact_args=redact_args,
    )
    set_config(config)

    transport = get_transport(url, prefix=prefix, ttl=ttl)
    connect_signals(transport)
