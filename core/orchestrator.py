from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Any

from .planner import Task
from .state import TaskState, TaskStatus, TERMINAL


@dataclass
class TaskResult:
    success: bool
    artifacts: list[str]
    message: str = ""
    metadata: dict[str, Any] | None = None
    requires_review: bool = True


class TaskExecutor(Protocol):
    def execute(self, task: Task, context: dict[str, Any]) -> TaskResult: ...


class Orchestrator:
    """Small DAG/state kernel. Provider-specific AI execution is injected."""

    def __init__(self, tasks: list[Task], states: dict[str, TaskState] | None = None):
        self.tasks = {t.id: t for t in tasks}
        self.states = states or {t.id: TaskState(task_id=t.id) for t in tasks}
        missing = set(self.tasks) - set(self.states)
        for task_id in missing:
            self.states[task_id] = TaskState(task_id=task_id)
        self.refresh_ready()

    def dependencies_satisfied(self, task: Task) -> bool:
        return all(self.states[dep].status in TERMINAL for dep in task.requires)

    def refresh_ready(self) -> None:
        for task_id, task in self.tasks.items():
            state = self.states[task_id]
            if state.status in {TaskStatus.PENDING, TaskStatus.FAILED} and self.dependencies_satisfied(task):
                if state.status == TaskStatus.FAILED:
                    continue
                state.transition(TaskStatus.READY)

    def ready_tasks(self) -> list[Task]:
        self.refresh_ready()
        return [self.tasks[tid] for tid, st in self.states.items() if st.status == TaskStatus.READY]

    def run_one(self, task_id: str, executor: TaskExecutor, context: dict[str, Any] | None = None) -> TaskResult:
        task = self.tasks[task_id]
        state = self.states[task_id]
        self.refresh_ready()
        if state.status != TaskStatus.READY:
            raise ValueError(f"task {task_id} is not ready: {state.status.value}")
        state.transition(TaskStatus.RUNNING)
        result = executor.execute(task, context or {})
        if not result.success:
            state.transition(TaskStatus.FAILED, result.message)
            return result
        state.artifacts = list(result.artifacts)
        if result.metadata:
            state.metadata.update(result.metadata)
        state.transition(TaskStatus.REVIEW, result.message)
        if not result.requires_review:
            state.transition(TaskStatus.LOCKED)
            state.transition(TaskStatus.PASSED)
        self.refresh_ready()
        return result

    def approve(self, task_id: str, message: str = "") -> None:
        state = self.states[task_id]
        if state.status != TaskStatus.REVIEW:
            raise ValueError(f"task {task_id} is not in review")
        state.transition(TaskStatus.LOCKED, message)
        state.transition(TaskStatus.PASSED)
        self.refresh_ready()

    def fail_review(self, task_id: str, message: str) -> None:
        state = self.states[task_id]
        if state.status != TaskStatus.REVIEW:
            raise ValueError(f"task {task_id} is not in review")
        state.transition(TaskStatus.FAILED, message)

    def retry(self, task_id: str) -> None:
        state = self.states[task_id]
        if state.status != TaskStatus.FAILED:
            raise ValueError(f"task {task_id} is not failed")
        if not self.dependencies_satisfied(self.tasks[task_id]):
            raise ValueError(f"dependencies are no longer satisfied for {task_id}")
        state.transition(TaskStatus.READY)

    def complete_external(self, task_id: str, artifacts: list[str] | None = None, message: str = "") -> None:
        """Record a task completed by an external AI/tool runner after its artifacts were checked."""
        self.refresh_ready()
        state = self.states[task_id]
        if state.status != TaskStatus.READY:
            raise ValueError(f"task {task_id} is not ready: {state.status.value}")
        state.transition(TaskStatus.RUNNING)
        state.artifacts = list(artifacts or [])
        state.transition(TaskStatus.REVIEW, message)
        state.transition(TaskStatus.LOCKED)
        state.transition(TaskStatus.PASSED)
        self.refresh_ready()

    def mark_failed_external(self, task_id: str, message: str) -> None:
        self.refresh_ready()
        state = self.states[task_id]
        if state.status == TaskStatus.READY:
            state.transition(TaskStatus.RUNNING)
        if state.status == TaskStatus.RUNNING:
            state.transition(TaskStatus.FAILED, message)
        elif state.status == TaskStatus.REVIEW:
            state.transition(TaskStatus.FAILED, message)
        else:
            raise ValueError(f"task {task_id} cannot fail from {state.status.value}")

    def is_complete(self) -> bool:
        return bool(self.states) and all(s.status in TERMINAL for s in self.states.values())

    def snapshot(self) -> dict[str, Any]:
        return {
            "tasks": {task_id: state.to_dict() for task_id, state in sorted(self.states.items())},
            "complete": self.is_complete(),
        }
