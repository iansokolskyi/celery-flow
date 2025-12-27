"""Tests for core event models."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from celery_flow.core.events import TaskEvent, TaskState


class TestTaskState:
    """Tests for TaskState enum."""

    def test_has_expected_values(self) -> None:
        """TaskState enum has expected values."""
        assert TaskState.PENDING.value == "PENDING"
        assert TaskState.SUCCESS.value == "SUCCESS"
        assert TaskState.FAILURE.value == "FAILURE"

    def test_all_celery_states_defined(self) -> None:
        """All standard Celery task states are defined."""
        expected_states = {
            "PENDING",
            "RECEIVED",
            "STARTED",
            "SUCCESS",
            "FAILURE",
            "REVOKED",
            "REJECTED",
            "RETRY",
        }
        actual_states = {s.value for s in TaskState}
        assert actual_states == expected_states

    def test_string_comparison(self) -> None:
        """TaskState can be compared to strings (str inheritance)."""
        assert TaskState.SUCCESS == "SUCCESS"
        assert TaskState.FAILURE == "FAILURE"
        assert TaskState.PENDING != "STARTED"

    def test_string_in_collections(self) -> None:
        """TaskState works in string collections."""
        terminal_states = {"SUCCESS", "FAILURE", "REVOKED", "REJECTED"}
        assert TaskState.SUCCESS in terminal_states
        assert TaskState.STARTED not in terminal_states


class TestTaskEventCreation:
    """Tests for TaskEvent creation and validation."""

    def test_with_required_fields(self) -> None:
        """TaskEvent can be created with required fields only."""
        event = TaskEvent(
            task_id="abc-123",
            name="myapp.tasks.send_email",
            state=TaskState.STARTED,
            timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        )

        assert event.task_id == "abc-123"
        assert event.name == "myapp.tasks.send_email"
        assert event.state == TaskState.STARTED
        assert event.parent_id is None
        assert event.root_id is None
        assert event.trace_id is None
        assert event.retries == 0

    def test_with_all_fields(self) -> None:
        """TaskEvent can be created with all fields populated."""
        event = TaskEvent(
            task_id="child-456",
            name="myapp.tasks.subtask",
            state=TaskState.RETRY,
            timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
            parent_id="parent-123",
            root_id="root-001",
            trace_id="trace-abc-xyz",
            retries=3,
        )

        assert event.task_id == "child-456"
        assert event.parent_id == "parent-123"
        assert event.root_id == "root-001"
        assert event.trace_id == "trace-abc-xyz"
        assert event.retries == 3

    def test_validates_field_types(self) -> None:
        """TaskEvent validates field types."""
        with pytest.raises(ValidationError):
            TaskEvent(
                task_id=123,  # type: ignore[arg-type]  # Should be str
                name="test",
                state=TaskState.PENDING,
                timestamp=datetime.now(UTC),
            )

    def test_validates_retries_type(self) -> None:
        """TaskEvent validates retries is an integer."""
        with pytest.raises(ValidationError):
            TaskEvent(
                task_id="abc-123",
                name="test",
                state=TaskState.PENDING,
                timestamp=datetime.now(UTC),
                retries="five",  # type: ignore[arg-type]
            )

    def test_state_from_string(self) -> None:
        """TaskEvent accepts state as string (enum coercion)."""
        event = TaskEvent(
            task_id="abc-123",
            name="test",
            state="SUCCESS",  # type: ignore[arg-type]
            timestamp=datetime.now(UTC),
        )
        assert event.state == TaskState.SUCCESS

    def test_invalid_state_raises(self) -> None:
        """TaskEvent rejects invalid state strings."""
        with pytest.raises(ValidationError):
            TaskEvent(
                task_id="abc-123",
                name="test",
                state="INVALID_STATE",  # type: ignore[arg-type]
                timestamp=datetime.now(UTC),
            )


class TestTaskEventImmutability:
    """Tests for TaskEvent frozen model behavior."""

    def test_cannot_modify_task_id(self) -> None:
        """TaskEvent task_id cannot be modified after creation."""
        event = TaskEvent(
            task_id="abc-123",
            name="myapp.tasks.send_email",
            state=TaskState.STARTED,
            timestamp=datetime.now(UTC),
        )

        with pytest.raises(ValidationError):
            event.task_id = "changed"  # type: ignore[misc]

    def test_cannot_modify_state(self) -> None:
        """TaskEvent state cannot be modified after creation."""
        event = TaskEvent(
            task_id="abc-123",
            name="test",
            state=TaskState.STARTED,
            timestamp=datetime.now(UTC),
        )

        with pytest.raises(ValidationError):
            event.state = TaskState.SUCCESS  # type: ignore[misc]


class TestTaskEventEquality:
    """Tests for TaskEvent equality comparison."""

    def test_equal_events(self) -> None:
        """Events with same values are equal."""
        ts = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        event1 = TaskEvent(
            task_id="abc-123",
            name="test",
            state=TaskState.STARTED,
            timestamp=ts,
        )
        event2 = TaskEvent(
            task_id="abc-123",
            name="test",
            state=TaskState.STARTED,
            timestamp=ts,
        )
        assert event1 == event2

    def test_different_task_id_not_equal(self) -> None:
        """Events with different task_id are not equal."""
        ts = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        event1 = TaskEvent(
            task_id="abc-123",
            name="test",
            state=TaskState.STARTED,
            timestamp=ts,
        )
        event2 = TaskEvent(
            task_id="xyz-789",
            name="test",
            state=TaskState.STARTED,
            timestamp=ts,
        )
        assert event1 != event2

    def test_hashable_for_sets(self) -> None:
        """Frozen events can be used in sets."""
        ts = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        event1 = TaskEvent(
            task_id="abc-123",
            name="test",
            state=TaskState.STARTED,
            timestamp=ts,
        )
        event2 = TaskEvent(
            task_id="abc-123",
            name="test",
            state=TaskState.STARTED,
            timestamp=ts,
        )
        event3 = TaskEvent(
            task_id="xyz-789",
            name="test",
            state=TaskState.STARTED,
            timestamp=ts,
        )

        event_set = {event1, event2, event3}
        assert len(event_set) == 2


class TestTaskEventSerialization:
    """Tests for TaskEvent serialization and deserialization."""

    def test_to_dict(self) -> None:
        """TaskEvent can be serialized to dict."""
        event = TaskEvent(
            task_id="abc-123",
            name="myapp.tasks.send_email",
            state=TaskState.STARTED,
            timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        )

        data = event.model_dump()
        assert data["task_id"] == "abc-123"
        assert data["state"] == TaskState.STARTED
        assert data["parent_id"] is None

    def test_to_json(self) -> None:
        """TaskEvent can be serialized to JSON string."""
        event = TaskEvent(
            task_id="abc-123",
            name="myapp.tasks.send_email",
            state=TaskState.STARTED,
            timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        )

        json_str = event.model_dump_json()
        assert "abc-123" in json_str
        assert "STARTED" in json_str

    def test_from_dict(self) -> None:
        """TaskEvent can be deserialized from dict."""
        data = {
            "task_id": "abc-123",
            "name": "myapp.tasks.send_email",
            "state": "SUCCESS",
            "timestamp": "2024-01-01T12:00:00Z",
            "parent_id": "parent-001",
            "retries": 2,
        }

        event = TaskEvent.model_validate(data)
        assert event.task_id == "abc-123"
        assert event.state == TaskState.SUCCESS
        assert event.parent_id == "parent-001"
        assert event.retries == 2

    def test_roundtrip(self) -> None:
        """TaskEvent survives serialization roundtrip."""
        original = TaskEvent(
            task_id="abc-123",
            name="myapp.tasks.send_email",
            state=TaskState.STARTED,
            timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
            parent_id="parent-001",
            root_id="root-001",
            trace_id="trace-xyz",
            retries=1,
        )

        data = original.model_dump(mode="json")
        restored = TaskEvent.model_validate(data)

        assert restored == original
