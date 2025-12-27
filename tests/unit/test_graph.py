"""Tests for task graph models."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from celery_flow.core.events import TaskEvent, TaskState
from celery_flow.core.graph import TaskGraph, TaskNode


class TestTaskNode:
    """Tests for TaskNode model."""

    def test_creation_with_required_fields(self) -> None:
        """TaskNode can be created with required fields."""
        node = TaskNode(
            task_id="task-1",
            name="myapp.tasks.process",
            state=TaskState.STARTED,
        )

        assert node.task_id == "task-1"
        assert node.name == "myapp.tasks.process"
        assert node.state == TaskState.STARTED
        assert node.events == []
        assert node.children == []
        assert node.parent_id is None

    def test_mutable_state(self) -> None:
        """TaskNode state can be mutated (not frozen)."""
        node = TaskNode(
            task_id="task-1",
            name="test",
            state=TaskState.STARTED,
        )

        node.state = TaskState.SUCCESS
        assert node.state == TaskState.SUCCESS

    def test_mutable_children(self) -> None:
        """TaskNode children list can be appended to."""
        node = TaskNode(
            task_id="task-1",
            name="test",
            state=TaskState.STARTED,
        )

        node.children.append("child-1")
        node.children.append("child-2")
        assert node.children == ["child-1", "child-2"]

    def test_mutable_events(self) -> None:
        """TaskNode events list can be appended to."""
        node = TaskNode(
            task_id="task-1",
            name="test",
            state=TaskState.STARTED,
        )

        event = TaskEvent(
            task_id="task-1",
            name="test",
            state=TaskState.STARTED,
            timestamp=datetime.now(UTC),
        )
        node.events.append(event)
        assert len(node.events) == 1

    def test_validates_state(self) -> None:
        """TaskNode validates state type."""
        with pytest.raises(ValidationError):
            TaskNode(
                task_id="task-1",
                name="test",
                state="INVALID",  # type: ignore[arg-type]
            )


class TestTaskGraphBasics:
    """Basic TaskGraph operations."""

    def test_empty_graph(self) -> None:
        """Empty graph has no nodes or roots."""
        graph = TaskGraph()
        assert graph.nodes == {}
        assert graph.root_ids == []

    def test_add_event_creates_node(self) -> None:
        """Adding event creates a node."""
        graph = TaskGraph()
        event = TaskEvent(
            task_id="task-1",
            name="myapp.tasks.process",
            state=TaskState.STARTED,
            timestamp=datetime.now(UTC),
        )

        graph.add_event(event)

        assert "task-1" in graph.nodes
        assert "task-1" in graph.root_ids
        assert graph.nodes["task-1"].name == "myapp.tasks.process"

    def test_add_event_appends_to_existing_node(self) -> None:
        """Adding event to existing node appends to events list."""
        graph = TaskGraph()

        # First event
        graph.add_event(
            TaskEvent(
                task_id="task-1",
                name="myapp.tasks.process",
                state=TaskState.STARTED,
                timestamp=datetime.now(UTC),
            )
        )

        # Second event for same task
        graph.add_event(
            TaskEvent(
                task_id="task-1",
                name="myapp.tasks.process",
                state=TaskState.SUCCESS,
                timestamp=datetime.now(UTC),
            )
        )

        assert len(graph.nodes) == 1
        assert len(graph.nodes["task-1"].events) == 2
        assert graph.nodes["task-1"].state == TaskState.SUCCESS

    def test_get_node_returns_none_for_missing(self) -> None:
        """get_node returns None for non-existent task."""
        graph = TaskGraph()
        assert graph.get_node("nonexistent") is None

    def test_get_node_returns_node(self) -> None:
        """get_node returns the node when it exists."""
        graph = TaskGraph()
        graph.add_event(
            TaskEvent(
                task_id="task-1",
                name="myapp.tasks.process",
                state=TaskState.STARTED,
                timestamp=datetime.now(UTC),
            )
        )

        node = graph.get_node("task-1")
        assert node is not None
        assert node.task_id == "task-1"


class TestTaskGraphParentChild:
    """Tests for parent-child relationships in TaskGraph."""

    def test_parent_then_child(self) -> None:
        """Child is linked when parent exists first."""
        graph = TaskGraph()

        # Add parent first
        graph.add_event(
            TaskEvent(
                task_id="parent-1",
                name="myapp.tasks.main",
                state=TaskState.STARTED,
                timestamp=datetime.now(UTC),
            )
        )

        # Add child
        graph.add_event(
            TaskEvent(
                task_id="child-1",
                name="myapp.tasks.subtask",
                state=TaskState.STARTED,
                timestamp=datetime.now(UTC),
                parent_id="parent-1",
            )
        )

        assert "parent-1" in graph.root_ids
        assert "child-1" not in graph.root_ids
        assert "child-1" in graph.nodes["parent-1"].children

    def test_child_before_parent_orphaned(self) -> None:
        """Child added before parent is not linked (orphan scenario)."""
        graph = TaskGraph()

        # Add child first (parent doesn't exist yet)
        graph.add_event(
            TaskEvent(
                task_id="child-1",
                name="myapp.tasks.subtask",
                state=TaskState.STARTED,
                timestamp=datetime.now(UTC),
                parent_id="parent-1",
            )
        )

        # Child is NOT a root (has parent_id), but parent doesn't exist
        assert "child-1" not in graph.root_ids
        assert "child-1" in graph.nodes
        assert graph.nodes["child-1"].parent_id == "parent-1"

        # Parent doesn't exist, so no children link yet
        assert "parent-1" not in graph.nodes

    def test_child_before_parent_late_linking(self) -> None:
        """When parent arrives after child, child is NOT auto-linked."""
        graph = TaskGraph()

        # Add child first
        graph.add_event(
            TaskEvent(
                task_id="child-1",
                name="myapp.tasks.subtask",
                state=TaskState.STARTED,
                timestamp=datetime.now(UTC),
                parent_id="parent-1",
            )
        )

        # Add parent later
        graph.add_event(
            TaskEvent(
                task_id="parent-1",
                name="myapp.tasks.main",
                state=TaskState.STARTED,
                timestamp=datetime.now(UTC),
            )
        )

        # Current implementation doesn't back-link
        # Child knows its parent, but parent doesn't know child
        assert graph.nodes["child-1"].parent_id == "parent-1"
        assert "child-1" not in graph.nodes["parent-1"].children

    def test_multiple_children(self) -> None:
        """Parent can have multiple children."""
        graph = TaskGraph()

        # Add parent
        graph.add_event(
            TaskEvent(
                task_id="parent-1",
                name="myapp.tasks.main",
                state=TaskState.STARTED,
                timestamp=datetime.now(UTC),
            )
        )

        # Add multiple children
        for i in range(3):
            graph.add_event(
                TaskEvent(
                    task_id=f"child-{i}",
                    name="myapp.tasks.subtask",
                    state=TaskState.STARTED,
                    timestamp=datetime.now(UTC),
                    parent_id="parent-1",
                )
            )

        assert len(graph.nodes["parent-1"].children) == 3
        assert "child-0" in graph.nodes["parent-1"].children
        assert "child-1" in graph.nodes["parent-1"].children
        assert "child-2" in graph.nodes["parent-1"].children


class TestTaskGraphNesting:
    """Tests for deeply nested task graphs."""

    def test_three_level_nesting(self) -> None:
        """Graph supports 3+ levels of nesting."""
        graph = TaskGraph()

        # Root -> Parent -> Child
        graph.add_event(
            TaskEvent(
                task_id="root",
                name="myapp.tasks.root",
                state=TaskState.STARTED,
                timestamp=datetime.now(UTC),
            )
        )
        graph.add_event(
            TaskEvent(
                task_id="parent",
                name="myapp.tasks.parent",
                state=TaskState.STARTED,
                timestamp=datetime.now(UTC),
                parent_id="root",
            )
        )
        graph.add_event(
            TaskEvent(
                task_id="child",
                name="myapp.tasks.child",
                state=TaskState.STARTED,
                timestamp=datetime.now(UTC),
                parent_id="parent",
            )
        )

        assert graph.root_ids == ["root"]
        assert "parent" in graph.nodes["root"].children
        assert "child" in graph.nodes["parent"].children

    def test_multiple_roots(self) -> None:
        """Graph can have multiple root tasks."""
        graph = TaskGraph()

        for i in range(3):
            graph.add_event(
                TaskEvent(
                    task_id=f"root-{i}",
                    name="myapp.tasks.root",
                    state=TaskState.STARTED,
                    timestamp=datetime.now(UTC),
                )
            )

        assert len(graph.root_ids) == 3


class TestTaskNodeStateTransitions:
    """Tests for state transitions on nodes."""

    def test_full_lifecycle(self) -> None:
        """Node tracks full task lifecycle."""
        graph = TaskGraph()
        task_id = "task-1"

        states = [
            TaskState.PENDING,
            TaskState.RECEIVED,
            TaskState.STARTED,
            TaskState.SUCCESS,
        ]

        for state in states:
            graph.add_event(
                TaskEvent(
                    task_id=task_id,
                    name="myapp.tasks.process",
                    state=state,
                    timestamp=datetime.now(UTC),
                )
            )

        node = graph.nodes[task_id]
        assert node.state == TaskState.SUCCESS
        assert len(node.events) == 4

    def test_retry_lifecycle(self) -> None:
        """Node tracks retry attempts."""
        graph = TaskGraph()
        task_id = "task-1"

        # Start -> Retry -> Start -> Success
        graph.add_event(
            TaskEvent(
                task_id=task_id,
                name="myapp.tasks.flaky",
                state=TaskState.STARTED,
                timestamp=datetime.now(UTC),
                retries=0,
            )
        )
        graph.add_event(
            TaskEvent(
                task_id=task_id,
                name="myapp.tasks.flaky",
                state=TaskState.RETRY,
                timestamp=datetime.now(UTC),
                retries=1,
            )
        )
        graph.add_event(
            TaskEvent(
                task_id=task_id,
                name="myapp.tasks.flaky",
                state=TaskState.STARTED,
                timestamp=datetime.now(UTC),
                retries=1,
            )
        )
        graph.add_event(
            TaskEvent(
                task_id=task_id,
                name="myapp.tasks.flaky",
                state=TaskState.SUCCESS,
                timestamp=datetime.now(UTC),
                retries=1,
            )
        )

        node = graph.nodes[task_id]
        assert node.state == TaskState.SUCCESS
        assert len(node.events) == 4
        assert node.events[-1].retries == 1


class TestTaskGraphSerialization:
    """Tests for TaskGraph serialization."""

    def test_to_dict(self) -> None:
        """TaskGraph can be serialized to dict."""
        graph = TaskGraph()
        graph.add_event(
            TaskEvent(
                task_id="task-1",
                name="myapp.tasks.process",
                state=TaskState.STARTED,
                timestamp=datetime.now(UTC),
            )
        )

        data = graph.model_dump()
        assert "nodes" in data
        assert "root_ids" in data
        assert "task-1" in data["nodes"]

    def test_roundtrip(self) -> None:
        """TaskGraph survives serialization roundtrip."""
        graph = TaskGraph()
        graph.add_event(
            TaskEvent(
                task_id="parent",
                name="myapp.tasks.main",
                state=TaskState.STARTED,
                timestamp=datetime(2024, 1, 1, tzinfo=UTC),
            )
        )
        graph.add_event(
            TaskEvent(
                task_id="child",
                name="myapp.tasks.sub",
                state=TaskState.SUCCESS,
                timestamp=datetime(2024, 1, 1, tzinfo=UTC),
                parent_id="parent",
            )
        )

        data = graph.model_dump(mode="json")
        restored = TaskGraph.model_validate(data)

        assert restored.root_ids == graph.root_ids
        assert "parent" in restored.nodes
        assert "child" in restored.nodes
        assert restored.nodes["parent"].children == ["child"]
