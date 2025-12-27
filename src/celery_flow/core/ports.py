"""Protocol definitions (ports) for dependency inversion.

This module defines the abstract interfaces (ports) that decouple the core
domain from infrastructure concerns. Implementations of these protocols
live in the library/ and server/ packages.

Following hexagonal architecture, the core domain defines what it needs
via protocols, and adapters (implementations) are plugged in at runtime.

Example:
    >>> class RedisTransport:
    ...     def publish(self, event: TaskEvent) -> None: ...
    ...     def consume(self) -> Iterator[TaskEvent]: ...
    ...     @classmethod
    ...     def from_url(cls, url: str) -> "RedisTransport": ...
    ...
    >>> # RedisTransport satisfies EventTransport protocol
"""

from collections.abc import Iterator
from typing import TYPE_CHECKING, Protocol

from typing_extensions import Self

if TYPE_CHECKING:
    from celery_flow.core.events import TaskEvent


class EventTransport(Protocol):
    """Broker-agnostic event transport interface.

    Defines the contract for publishing task events from the library
    (Celery side) and consuming them in the server (visualization side).

    Implementations:
        - RedisTransport: Uses Redis Streams
        - RabbitMQTransport: Uses RabbitMQ queues
        - MemoryTransport: In-process for testing

    Important:
        publish() must be fire-and-forget and never raise exceptions.
        Transport failures should be logged but not propagate to the
        Celery task, as this would affect task execution.
    """

    def publish(self, event: "TaskEvent") -> None:
        """Publish an event to the transport.

        This method must be fire-and-forget: it should never raise
        exceptions or block the calling task. Any errors should be
        logged and swallowed.

        Args:
            event: The task event to publish.
        """
        ...

    def consume(self) -> Iterator["TaskEvent"]:
        """Consume events from the transport.

        Yields events as they become available. The iterator may block
        waiting for new events (long-polling behavior).

        Yields:
            TaskEvent instances as they arrive.
        """
        ...

    @classmethod
    def from_url(cls, url: str) -> Self:
        """Create a transport instance from a broker URL.

        Args:
            url: Broker connection URL (e.g., "redis://localhost:6379").

        Returns:
            Configured transport instance.

        Raises:
            UnsupportedBrokerError: If the URL scheme is not supported.
        """
        ...


class TaskRepository(Protocol):
    """Abstract interface for task data access.

    Defines the contract for querying task data from the server side.
    Used by API endpoints to retrieve task information.

    Implementations may be backed by in-memory storage, Redis, or a database.
    """

    def get(self, task_id: str) -> "TaskEvent | None":
        """Get the latest event for a task.

        Args:
            task_id: The unique task identifier.

        Returns:
            The most recent TaskEvent for this task, or None if not found.
        """
        ...

    def list_recent(self, limit: int = 100) -> list["TaskEvent"]:
        """List recent task events.

        Args:
            limit: Maximum number of events to return. Defaults to 100.

        Returns:
            List of recent events, most recent first.
        """
        ...

    def get_children(self, parent_id: str) -> list["TaskEvent"]:
        """Get child task events for a parent task.

        Args:
            parent_id: The parent task's unique identifier.

        Returns:
            List of events for tasks spawned by the parent.
        """
        ...
