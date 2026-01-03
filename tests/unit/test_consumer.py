"""Tests for EventConsumer and AsyncEventConsumer."""

import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from stemtrace.core.events import TaskEvent, TaskState, WorkerEvent, WorkerEventType
from stemtrace.server.api.schemas import WorkerStatus
from stemtrace.server.consumer import AsyncEventConsumer, EventConsumer
from stemtrace.server.store import GraphStore, WorkerRegistry


class FakeTransport:
    """Fake transport for testing."""

    def __init__(self, events: list[TaskEvent | WorkerEvent] | None = None) -> None:
        self._events: list[TaskEvent | WorkerEvent] = events or []
        self._publish_count = 0
        self._consume_started = False
        self._stop = False

    def publish(self, event: TaskEvent | WorkerEvent) -> None:
        self._events.append(event)
        self._publish_count += 1

    def consume(self) -> Iterator[TaskEvent | WorkerEvent]:
        self._consume_started = True
        for event in self._events:
            if self._stop:
                break
            yield event
        # Block until stopped
        while not self._stop:
            time.sleep(0.01)

    def stop(self) -> None:
        self._stop = True


@pytest.fixture
def store() -> GraphStore:
    """Create a fresh GraphStore for each test."""
    return GraphStore()


@pytest.fixture
def sample_events() -> list[TaskEvent]:
    """Create sample events for testing."""
    base_time = datetime(2024, 1, 1, tzinfo=UTC)
    return [
        TaskEvent(
            task_id=f"task-{i}",
            name="tests.sample",
            state=TaskState.STARTED,
            timestamp=base_time,
        )
        for i in range(5)
    ]


class TestEventConsumer:
    def test_initial_state(self, store: GraphStore) -> None:
        consumer = EventConsumer("memory://", store)
        assert not consumer.is_running

    def test_start_stops_gracefully(self, store: GraphStore) -> None:
        fake = FakeTransport()

        with patch("stemtrace.server.consumer.get_transport", return_value=fake):
            consumer = EventConsumer("memory://", store)
            consumer.start()

            assert consumer.is_running
            time.sleep(0.05)  # Let thread start

            # Stop should work
            fake.stop()
            consumer.stop(timeout=1.0)
            assert not consumer.is_running

    def test_start_idempotent(self, store: GraphStore) -> None:
        fake = FakeTransport()

        with patch("stemtrace.server.consumer.get_transport", return_value=fake):
            consumer = EventConsumer("memory://", store)
            consumer.start()
            consumer.start()  # Second start should be no-op

            assert consumer.is_running

            fake.stop()
            consumer.stop(timeout=1.0)

    def test_stop_when_not_running(self, store: GraphStore) -> None:
        consumer = EventConsumer("memory://", store)
        # Should not raise
        consumer.stop()

    def test_consumes_events_into_store(
        self, store: GraphStore, sample_events: list[TaskEvent]
    ) -> None:
        fake = FakeTransport(sample_events.copy())

        with patch("stemtrace.server.consumer.get_transport", return_value=fake):
            consumer = EventConsumer("memory://", store)
            consumer.start()

            # Wait for events to be consumed
            time.sleep(0.1)

            fake.stop()
            consumer.stop(timeout=1.0)

            assert store.node_count == 5

    def test_config_passed_to_transport(self, store: GraphStore) -> None:
        mock_get_transport = MagicMock(return_value=FakeTransport())

        with patch("stemtrace.server.consumer.get_transport", mock_get_transport):
            consumer = EventConsumer(
                "redis://localhost:6379",
                store,
                prefix="custom_prefix",
                ttl=3600,
            )
            consumer.start()
            time.sleep(0.05)

            mock_get_transport.assert_called_once_with(
                "redis://localhost:6379",
                prefix="custom_prefix",
                ttl=3600,
            )

            mock_get_transport.return_value.stop()
            consumer.stop(timeout=1.0)


class TestAsyncEventConsumer:
    def test_initial_state(self, store: GraphStore) -> None:
        consumer = AsyncEventConsumer("memory://", store)
        assert not consumer.is_running

    @pytest.mark.asyncio
    async def test_async_context_manager(self, store: GraphStore) -> None:
        fake = FakeTransport()

        with patch("stemtrace.server.consumer.get_transport", return_value=fake):
            async with AsyncEventConsumer("memory://", store) as consumer:
                assert consumer.is_running
                fake.stop()

            assert not consumer.is_running

    def test_manual_start_stop(self, store: GraphStore) -> None:
        fake = FakeTransport()

        with patch("stemtrace.server.consumer.get_transport", return_value=fake):
            consumer = AsyncEventConsumer("memory://", store)
            consumer.start()
            assert consumer.is_running

            fake.stop()
            consumer.stop(timeout=1.0)
            assert not consumer.is_running


class TestWorkerEventHandling:
    """Tests for worker event consumption and routing."""

    def test_worker_ready_registers_worker(self, store: GraphStore) -> None:
        """Worker ready event should register worker in registry."""
        worker_registry = WorkerRegistry()
        # Use future time to ensure event is after consumer's _started_at
        future_time = datetime.now(UTC) + timedelta(seconds=1)
        worker_event = WorkerEvent(
            event_type=WorkerEventType.WORKER_READY,
            hostname="worker-1",
            pid=12345,
            timestamp=future_time,
            registered_tasks=["tasks.add", "tasks.multiply"],
        )
        fake = FakeTransport([worker_event])

        with patch("stemtrace.server.consumer.get_transport", return_value=fake):
            consumer = EventConsumer(
                "memory://", store, worker_registry=worker_registry
            )
            consumer.start()
            time.sleep(0.1)  # Wait for event processing

            fake.stop()
            consumer.stop(timeout=1.0)

            # Worker should be registered
            workers = worker_registry.get_all_workers()
            assert len(workers) == 1
            assert workers[0].hostname == "worker-1"
            assert workers[0].pid == 12345
            assert workers[0].registered_tasks == ["tasks.add", "tasks.multiply"]
            assert workers[0].status == WorkerStatus.ONLINE

    def test_worker_shutdown_marks_offline(self, store: GraphStore) -> None:
        """Worker shutdown event should mark worker offline."""
        worker_registry = WorkerRegistry()
        # First register the worker
        worker_registry.register_worker("worker-1", 12345, ["tasks.add"])

        # Use future time to ensure event is after consumer's _started_at
        future_time = datetime.now(UTC) + timedelta(seconds=1)
        shutdown_event = WorkerEvent(
            event_type=WorkerEventType.WORKER_SHUTDOWN,
            hostname="worker-1",
            pid=12345,
            timestamp=future_time,
            shutdown_time=future_time,
        )
        fake = FakeTransport([shutdown_event])

        with patch("stemtrace.server.consumer.get_transport", return_value=fake):
            consumer = EventConsumer(
                "memory://", store, worker_registry=worker_registry
            )
            consumer.start()
            time.sleep(0.1)

            fake.stop()
            consumer.stop(timeout=1.0)

            # Worker should be marked offline
            worker = worker_registry.get_worker("worker-1", 12345)
            assert worker is not None
            assert worker.status == WorkerStatus.OFFLINE

    def test_mixed_events_routed_correctly(self, store: GraphStore) -> None:
        """Task and worker events should be routed to correct handlers."""
        worker_registry = WorkerRegistry()
        # Use future time for worker event so it's after consumer's _started_at
        # Task events can use any time (they're not filtered)
        future_time = datetime.now(UTC) + timedelta(seconds=1)
        past_time = datetime(2024, 1, 1, tzinfo=UTC)

        events: list[TaskEvent | WorkerEvent] = [
            TaskEvent(
                task_id="task-1",
                name="tests.sample",
                state=TaskState.STARTED,
                timestamp=past_time,
            ),
            WorkerEvent(
                event_type=WorkerEventType.WORKER_READY,
                hostname="worker-1",
                pid=12345,
                timestamp=future_time,  # Future time for worker event
                registered_tasks=["tasks.add"],
            ),
            TaskEvent(
                task_id="task-2",
                name="tests.sample",
                state=TaskState.SUCCESS,
                timestamp=past_time,
            ),
        ]
        fake = FakeTransport(events)

        with patch("stemtrace.server.consumer.get_transport", return_value=fake):
            consumer = EventConsumer(
                "memory://", store, worker_registry=worker_registry
            )
            consumer.start()
            time.sleep(0.1)

            fake.stop()
            consumer.stop(timeout=1.0)

            # Both task events should be in store
            assert store.node_count == 2

            # Worker should be registered
            workers = worker_registry.get_all_workers()
            assert len(workers) == 1

    def test_worker_events_skipped_without_registry(self, store: GraphStore) -> None:
        """Worker events should be skipped if no registry provided."""
        future_time = datetime.now(UTC) + timedelta(seconds=1)
        worker_event = WorkerEvent(
            event_type=WorkerEventType.WORKER_READY,
            hostname="worker-1",
            pid=12345,
            timestamp=future_time,
            registered_tasks=["tasks.add"],
        )
        fake = FakeTransport([worker_event])

        with patch("stemtrace.server.consumer.get_transport", return_value=fake):
            # No worker_registry passed
            consumer = EventConsumer("memory://", store)
            consumer.start()
            time.sleep(0.1)

            fake.stop()
            consumer.stop(timeout=1.0)

    def test_historical_worker_events_are_processed(self, store: GraphStore) -> None:
        """Historical worker events should be processed to rebuild registry state.

        When server restarts but workers are still running, the historical
        WORKER_READY events in Redis are still valid and should be processed.
        This enables the registry to show "Registered Only" and "Never Executed"
        tasks even after server restart.

        If a worker has shut down, there will be a WORKER_SHUTDOWN event that
        marks it offline. Processing events in order gives correct state.
        """
        worker_registry = WorkerRegistry()
        # Create an event from 1 minute ago (before consumer starts but recent)
        one_min_ago = datetime.now(UTC) - timedelta(minutes=1)
        old_event = WorkerEvent(
            event_type=WorkerEventType.WORKER_READY,
            hostname="still-running-worker",
            pid=12345,
            timestamp=one_min_ago,
            registered_tasks=["tasks.add", "tasks.multiply"],
        )
        fake = FakeTransport([old_event])

        with patch("stemtrace.server.consumer.get_transport", return_value=fake):
            # Consumer is created NOW, but should still process historical events
            consumer = EventConsumer(
                "memory://", store, worker_registry=worker_registry
            )
            consumer.start()
            time.sleep(0.1)

            fake.stop()
            consumer.stop(timeout=1.0)

        # Historical WORKER_READY should register the worker
        workers = worker_registry.get_all_workers()
        assert len(workers) == 1
        assert workers[0].hostname == "still-running-worker"
        assert workers[0].pid == 12345
        assert workers[0].registered_tasks == ["tasks.add", "tasks.multiply"]

    def test_historical_shutdown_marks_worker_offline(self, store: GraphStore) -> None:
        """Historical WORKER_SHUTDOWN after WORKER_READY marks worker offline.

        When processing events from Redis, a worker that started and then
        shut down (before server restart) should end up marked offline.
        Stream ordering ensures correct final state.
        """
        worker_registry = WorkerRegistry()
        # Worker started at T1, shut down at T2 (both before consumer but recent)
        t1 = datetime.now(UTC) - timedelta(minutes=2)
        t2 = datetime.now(UTC) - timedelta(minutes=1)
        events: list[WorkerEvent] = [
            WorkerEvent(
                event_type=WorkerEventType.WORKER_READY,
                hostname="dead-worker",
                pid=99999,
                timestamp=t1,
                registered_tasks=["tasks.old"],
            ),
            WorkerEvent(
                event_type=WorkerEventType.WORKER_SHUTDOWN,
                hostname="dead-worker",
                pid=99999,
                timestamp=t2,
            ),
        ]
        fake = FakeTransport(events)

        with patch("stemtrace.server.consumer.get_transport", return_value=fake):
            consumer = EventConsumer(
                "memory://", store, worker_registry=worker_registry
            )
            consumer.start()
            time.sleep(0.1)

            fake.stop()
            consumer.stop(timeout=1.0)

        # Worker should be registered but marked offline
        workers = worker_registry.get_all_workers()
        assert len(workers) == 1
        assert workers[0].hostname == "dead-worker"
        assert workers[0].status == WorkerStatus.OFFLINE

    def test_stale_worker_check_runs_periodically(self, store: GraphStore) -> None:
        """Consumer should periodically check for and mark stale workers.

        Workers that haven't been seen recently (no heartbeat/events)
        should be marked offline by the stale check mechanism.
        """
        worker_registry = WorkerRegistry()
        # Pre-register a worker that we'll manually mark as stale
        worker_registry.register_worker("stale-worker", 11111, ["tasks.stale"])

        # Manually set last_seen to 20 minutes ago to trigger stale detection
        with worker_registry._lock:
            worker = worker_registry._workers["stale-worker:11111"]
            worker.last_seen = datetime.now(UTC) - timedelta(minutes=20)

        # Create a task event to trigger processing (stale check happens after events)
        task_event = TaskEvent(
            task_id="trigger-1",
            name="tests.trigger",
            state=TaskState.STARTED,
            timestamp=datetime.now(UTC),
        )
        fake = FakeTransport([task_event])

        with patch("stemtrace.server.consumer.get_transport", return_value=fake):
            # Use stale_check_interval=0 to trigger check immediately
            consumer = EventConsumer(
                "memory://",
                store,
                worker_registry=worker_registry,
                stale_check_interval=0,
            )
            consumer.start()
            time.sleep(0.1)

            fake.stop()
            consumer.stop(timeout=1.0)

        # Task event should be processed
        assert store.node_count == 1

        # Stale worker should now be marked offline
        worker = worker_registry.get_worker("stale-worker", 11111)
        assert worker is not None
        assert worker.status == WorkerStatus.OFFLINE
