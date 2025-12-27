"""Task graph models.

This module provides the in-memory representation of task execution flows.
A TaskGraph is a directed acyclic graph (DAG) where nodes are tasks and
edges represent parent-child relationships (task spawning subtasks).

The graph is built incrementally by feeding TaskEvents as they arrive.

Example:
    >>> from datetime import datetime, UTC
    >>> from celery_flow.core.events import TaskEvent, TaskState
    >>> graph = TaskGraph()
    >>> graph.add_event(TaskEvent(
    ...     task_id="task-1",
    ...     name="myapp.tasks.process",
    ...     state=TaskState.STARTED,
    ...     timestamp=datetime.now(UTC),
    ... ))
    >>> graph.get_node("task-1")
    TaskNode(task_id='task-1', ...)
"""

from pydantic import BaseModel, ConfigDict, Field

from celery_flow.core.events import TaskEvent, TaskState


class TaskNode(BaseModel):
    """A mutable node in the task execution graph.

    Each node represents a single Celery task and tracks its complete
    event history and relationships to other tasks.

    Unlike TaskEvent (frozen), TaskNode is mutable to allow state updates
    as new events arrive for the same task.

    Attributes:
        task_id: Unique Celery task identifier.
        name: Fully qualified task name.
        state: Most recent task state.
        events: Chronologically ordered list of events for this task.
        children: Task IDs of subtasks spawned by this task.
        parent_id: Task ID of the parent task, if any.

    Example:
        >>> node = TaskNode(
        ...     task_id="task-1",
        ...     name="myapp.tasks.process",
        ...     state=TaskState.STARTED,
        ... )
        >>> node.children.append("child-1")
        >>> node.state = TaskState.SUCCESS  # Mutable update
    """

    model_config = ConfigDict(validate_assignment=True)

    task_id: str
    name: str
    state: TaskState
    events: list[TaskEvent] = Field(default_factory=list)
    children: list[str] = Field(default_factory=list)
    parent_id: str | None = None


class TaskGraph(BaseModel):
    """A directed acyclic graph of task executions.

    The graph maintains a mapping of task IDs to nodes and tracks which
    tasks are roots (have no parent). It is built incrementally by
    processing TaskEvents via the add_event() method.

    Note:
        Parent-child linking only occurs when the parent node exists
        at the time the child event is processed. If events arrive
        out of order (child before parent), the child will reference
        its parent_id but won't appear in the parent's children list.

    Attributes:
        nodes: Mapping of task_id to TaskNode.
        root_ids: IDs of root tasks (tasks with no parent).

    Example:
        >>> graph = TaskGraph()
        >>> graph.add_event(parent_event)
        >>> graph.add_event(child_event)
        >>> graph.root_ids
        ['parent-task-id']
        >>> graph.get_node("parent-task-id").children
        ['child-task-id']
    """

    model_config = ConfigDict(validate_assignment=True)

    nodes: dict[str, TaskNode] = Field(default_factory=dict)
    root_ids: list[str] = Field(default_factory=list)

    def add_event(self, event: TaskEvent) -> None:
        """Add an event to the graph, creating or updating nodes.

        If the task doesn't exist, a new node is created. If it exists,
        the event is appended and the node's state is updated.

        Parent-child linking occurs when:
        - The event has a parent_id
        - The parent node already exists in the graph

        Args:
            event: The task event to process.
        """
        if event.task_id not in self.nodes:
            self.nodes[event.task_id] = TaskNode(
                task_id=event.task_id,
                name=event.name,
                state=event.state,
                parent_id=event.parent_id,
            )
            if event.parent_id is None:
                self.root_ids.append(event.task_id)
            elif event.parent_id in self.nodes:
                self.nodes[event.parent_id].children.append(event.task_id)

        node = self.nodes[event.task_id]
        node.events.append(event)
        node.state = event.state

    def get_node(self, task_id: str) -> TaskNode | None:
        """Get a node by task ID.

        Args:
            task_id: The unique task identifier.

        Returns:
            The TaskNode if found, None otherwise.
        """
        return self.nodes.get(task_id)
