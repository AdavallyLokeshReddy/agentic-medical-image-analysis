from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List


class TaskStatus(str, Enum):
    PROPOSED = "proposed"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TaskNode:
    """
    One bounded task in the agent task graph.

    A task describes what the agent is allowed to coordinate.
    It does not execute the task itself.
    """

    task_id: str
    task_type: str
    description: str

    status: TaskStatus = TaskStatus.PROPOSED

    dependencies: List[str] = field(
        default_factory=list
    )

    permitted_tools: List[str] = field(
        default_factory=list
    )

    preconditions: List[str] = field(
        default_factory=list
    )

    verification_required: bool = False

    stopping_conditions: List[str] = field(
        default_factory=list
    )

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "description": self.description,
            "status": self.status.value,
            "dependencies": list(self.dependencies),
            "permitted_tools": list(
                self.permitted_tools
            ),
            "preconditions": list(
                self.preconditions
            ),
            "verification_required":
                self.verification_required,
            "stopping_conditions": list(
                self.stopping_conditions
            ),
            "metadata": dict(self.metadata),
        }


class TaskGraph:
    """
    Lightweight directed acyclic task graph.

    The graph stores bounded dependencies between tasks.

    It does NOT execute medical AI tools.
    """

    def __init__(self):
        self._tasks: Dict[str, TaskNode] = {}

    def add_task(self, task: TaskNode) -> None:
        if not isinstance(task, TaskNode):
            raise TypeError(
                "task must be a TaskNode instance."
            )

        if task.task_id in self._tasks:
            raise ValueError(
                f"Task already exists: {task.task_id}"
            )

        for dependency in task.dependencies:
            if dependency == task.task_id:
                raise ValueError(
                    "A task cannot depend on itself."
                )

            if dependency not in self._tasks:
                raise ValueError(
                    f"Dependency does not exist: "
                    f"{dependency}"
                )

        self._tasks[task.task_id] = task

    def get_task(self, task_id: str) -> TaskNode:
        if task_id not in self._tasks:
            raise KeyError(
                f"Task not found: {task_id}"
            )

        return self._tasks[task_id]

    def list_tasks(self) -> List[Dict[str, Any]]:
        return [
            task.to_dict()
            for task in self._tasks.values()
        ]

    def get_ready_tasks(self) -> List[TaskNode]:
        """
        Return tasks whose dependencies have completed.
        """

        ready_tasks = []

        for task in self._tasks.values():

            if task.status != TaskStatus.PROPOSED:
                continue

            dependencies_complete = all(
                self._tasks[
                    dependency
                ].status == TaskStatus.COMPLETED
                for dependency in task.dependencies
            )

            if dependencies_complete:
                ready_tasks.append(task)

        return ready_tasks

    def mark_completed(
        self,
        task_id: str,
    ) -> None:
        task = self.get_task(task_id)

        task.status = TaskStatus.COMPLETED

    def mark_blocked(
        self,
        task_id: str,
    ) -> None:
        task = self.get_task(task_id)

        task.status = TaskStatus.BLOCKED

    def mark_failed(
        self,
        task_id: str,
    ) -> None:
        task = self.get_task(task_id)

        task.status = TaskStatus.FAILED

    def has_task(
        self,
        task_id: str,
    ) -> bool:
        return task_id in self._tasks

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tasks": self.list_tasks()
        }

    def summary(self) -> Dict[str, Any]:
        return {
            "task_count": len(self._tasks),
            "tasks": [
                {
                    "task_id": task.task_id,
                    "task_type": task.task_type,
                    "status": task.status.value,
                    "dependencies": list(
                        task.dependencies
                    ),
                }
                for task in self._tasks.values()
            ],
        }