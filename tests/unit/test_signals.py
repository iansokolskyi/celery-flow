"""Tests for Celery signal handlers."""

from typing import Any
from unittest.mock import MagicMock

import pytest

from celery_flow.core.events import TaskState
from celery_flow.library.signals import (
    _on_task_failure,
    _on_task_postrun,
    _on_task_prerun,
    _on_task_retry,
    _on_task_revoked,
    connect_signals,
    disconnect_signals,
)
from celery_flow.library.transports.memory import MemoryTransport


@pytest.fixture(autouse=True)
def clean_transport() -> None:
    """Clean up transport state before each test."""
    MemoryTransport.clear()
    disconnect_signals()


@pytest.fixture
def transport() -> MemoryTransport:
    """Create and connect a MemoryTransport."""
    transport = MemoryTransport()
    connect_signals(transport)
    return transport


@pytest.fixture
def mock_task() -> MagicMock:
    """Create a mock Celery task."""
    task = MagicMock()
    task.name = "tests.sample_task"
    task.request.id = "task-123"
    task.request.parent_id = None
    task.request.root_id = None
    task.request.retries = 0
    return task


@pytest.fixture
def mock_task_with_parent() -> MagicMock:
    """Create a mock Celery task with parent."""
    task = MagicMock()
    task.name = "tests.child_task"
    task.request.id = "task-456"
    task.request.parent_id = "task-123"
    task.request.root_id = "task-001"
    task.request.retries = 0
    return task


class TestConnectDisconnect:
    """Tests for connect/disconnect functions."""

    def test_connect_signals_stores_transport(self) -> None:
        """connect_signals() enables event publishing."""
        transport = MemoryTransport()
        connect_signals(transport)

        # Simulate a signal - should publish event
        task = MagicMock()
        task.name = "tests.task"
        task.request.parent_id = None
        task.request.root_id = None
        task.request.retries = 0

        _on_task_prerun(
            task_id="test-id",
            task=task,
            args=(),
            kwargs={},
        )

        assert len(MemoryTransport.events) == 1

    def test_disconnect_clears_transport(self) -> None:
        """disconnect_signals() stops event publishing."""
        transport = MemoryTransport()
        connect_signals(transport)
        disconnect_signals()

        # Events after disconnect should be dropped
        task = MagicMock()
        task.name = "tests.task"
        task.request.parent_id = None
        task.request.root_id = None
        task.request.retries = 0

        _on_task_prerun(
            task_id="test-id",
            task=task,
            args=(),
            kwargs={},
        )

        # Event not published (logged warning instead)
        assert len(MemoryTransport.events) == 0


class TestTaskPrerun:
    """Tests for task_prerun signal handler."""

    def test_emits_started_event(
        self,
        transport: MemoryTransport,
        mock_task: MagicMock,
    ) -> None:
        """task_prerun emits STARTED event."""
        _on_task_prerun(
            task_id="task-123",
            task=mock_task,
            args=("arg1",),
            kwargs={"key": "value"},
        )

        assert len(MemoryTransport.events) == 1
        event = MemoryTransport.events[0]
        assert event.task_id == "task-123"
        assert event.name == "tests.sample_task"
        assert event.state == TaskState.STARTED
        assert event.parent_id is None
        assert event.root_id is None

    def test_captures_parent_and_root(
        self,
        transport: MemoryTransport,
        mock_task_with_parent: MagicMock,
    ) -> None:
        """task_prerun captures parent_id and root_id."""
        _on_task_prerun(
            task_id="task-456",
            task=mock_task_with_parent,
            args=(),
            kwargs={},
        )

        event = MemoryTransport.events[0]
        assert event.parent_id == "task-123"
        assert event.root_id == "task-001"

    def test_captures_retry_count(
        self,
        transport: MemoryTransport,
        mock_task: MagicMock,
    ) -> None:
        """task_prerun captures current retry count."""
        mock_task.request.retries = 2

        _on_task_prerun(
            task_id="task-123",
            task=mock_task,
            args=(),
            kwargs={},
        )

        event = MemoryTransport.events[0]
        assert event.retries == 2


class TestTaskPostrun:
    """Tests for task_postrun signal handler."""

    def test_emits_success_event_on_success(
        self,
        transport: MemoryTransport,
        mock_task: MagicMock,
    ) -> None:
        """task_postrun emits SUCCESS for successful tasks."""
        _on_task_postrun(
            task_id="task-123",
            task=mock_task,
            args=(),
            kwargs={},
            retval={"result": "data"},
            state="SUCCESS",
        )

        assert len(MemoryTransport.events) == 1
        event = MemoryTransport.events[0]
        assert event.state == TaskState.SUCCESS

    def test_ignores_failure_state(
        self,
        transport: MemoryTransport,
        mock_task: MagicMock,
    ) -> None:
        """task_postrun doesn't emit for FAILURE (handled by task_failure)."""
        _on_task_postrun(
            task_id="task-123",
            task=mock_task,
            args=(),
            kwargs={},
            retval=None,
            state="FAILURE",
        )

        assert len(MemoryTransport.events) == 0

    def test_ignores_retry_state(
        self,
        transport: MemoryTransport,
        mock_task: MagicMock,
    ) -> None:
        """task_postrun doesn't emit for RETRY (handled by task_retry)."""
        _on_task_postrun(
            task_id="task-123",
            task=mock_task,
            args=(),
            kwargs={},
            retval=None,
            state="RETRY",
        )

        assert len(MemoryTransport.events) == 0


class TestTaskFailure:
    """Tests for task_failure signal handler."""

    def test_emits_failure_event(
        self,
        transport: MemoryTransport,
        mock_task: MagicMock,
    ) -> None:
        """task_failure emits FAILURE event."""
        exception = ValueError("Something went wrong")

        _on_task_failure(
            task_id="task-123",
            exception=exception,
            args=(),
            kwargs={},
            traceback=None,
            einfo=None,
            sender=mock_task,
        )

        assert len(MemoryTransport.events) == 1
        event = MemoryTransport.events[0]
        assert event.task_id == "task-123"
        assert event.state == TaskState.FAILURE


class TestTaskRetry:
    """Tests for task_retry signal handler."""

    def test_emits_retry_event(
        self,
        transport: MemoryTransport,
        mock_task: MagicMock,
    ) -> None:
        """task_retry emits RETRY event."""
        request = MagicMock()
        request.id = "task-123"
        request.parent_id = None
        request.root_id = None
        request.retries = 1

        _on_task_retry(
            sender=mock_task,
            request=request,
            reason="Connection timeout",
            einfo=None,
        )

        assert len(MemoryTransport.events) == 1
        event = MemoryTransport.events[0]
        assert event.state == TaskState.RETRY
        assert event.retries == 2  # Incremented for new retry


class TestTaskRevoked:
    """Tests for task_revoked signal handler."""

    def test_emits_revoked_event(
        self,
        transport: MemoryTransport,
        mock_task: MagicMock,
    ) -> None:
        """task_revoked emits REVOKED event."""
        request = MagicMock()
        request.id = "task-123"
        request.parent_id = None
        request.root_id = None
        request.retries = 0

        _on_task_revoked(
            request=request,
            terminated=True,
            signum=15,
            expired=False,
            sender=mock_task,
        )

        assert len(MemoryTransport.events) == 1
        event = MemoryTransport.events[0]
        assert event.state == TaskState.REVOKED


class TestFireAndForget:
    """Tests for fire-and-forget behavior."""

    def test_publish_error_is_logged_not_raised(
        self,
        mock_task: MagicMock,
        caplog: Any,
    ) -> None:
        """Transport errors are logged, not raised."""
        # Create a transport that raises on publish
        broken_transport = MagicMock()
        broken_transport.publish.side_effect = RuntimeError("Connection failed")
        connect_signals(broken_transport)

        # This should not raise
        _on_task_prerun(
            task_id="task-123",
            task=mock_task,
            args=(),
            kwargs={},
        )

        # Error should be logged
        assert "Failed to publish event" in caplog.text
