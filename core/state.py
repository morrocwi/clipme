from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


class TaskStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    REVIEW = "review"
    LOCKED = "locked"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


TERMINAL = {TaskStatus.PASSED, TaskStatus.SKIPPED}

_ALLOWED = {
    TaskStatus.PENDING: {TaskStatus.READY, TaskStatus.SKIPPED},
    TaskStatus.READY: {TaskStatus.RUNNING, TaskStatus.SKIPPED},
    TaskStatus.RUNNING: {TaskStatus.REVIEW, TaskStatus.FAILED},
    TaskStatus.REVIEW: {TaskStatus.LOCKED, TaskStatus.FAILED, TaskStatus.RUNNING},
    TaskStatus.LOCKED: {TaskStatus.PASSED, TaskStatus.FAILED},
    TaskStatus.FAILED: {TaskStatus.READY, TaskStatus.SKIPPED},
    TaskStatus.PASSED: set(),
    TaskStatus.SKIPPED: set(),
}


@dataclass
class TaskState:
    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    attempts: int = 0
    artifacts: list[str] = field(default_factory=list)
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def transition(self, target: TaskStatus, message: str = "") -> None:
        if target not in _ALLOWED[self.status]:
            raise ValueError(f"invalid task transition {self.status.value} -> {target.value} for {self.task_id}")
        if target == TaskStatus.RUNNING:
            self.attempts += 1
        self.status = target
        if message:
            self.message = message

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskState":
        payload = dict(data)
        payload["status"] = TaskStatus(payload.get("status", "pending"))
        return cls(**payload)
