"""Modèles métier d'Escale : énumérations, dataclasses et palette."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum, IntEnum

ACCENT_PALETTE = [
    "#0F6CBD", "#038387", "#107C10", "#8764B8", "#C239B3", "#CA5010",
    "#C42B1C", "#986F0B", "#4F6BED", "#567C73", "#5D5A58", "#E3008C",
]


class TaskStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    DONE = "done"

    @property
    def label(self) -> str:
        return _STATUS_LABELS[self]

    @property
    def color(self) -> str:
        return _STATUS_COLORS[self]


_STATUS_LABELS = {
    TaskStatus.TODO: "À faire",
    TaskStatus.IN_PROGRESS: "En cours",
    TaskStatus.REVIEW: "En revue",
    TaskStatus.DONE: "Terminé",
}
_STATUS_COLORS = {
    TaskStatus.TODO: "#8A8886",
    TaskStatus.IN_PROGRESS: "#0F6CBD",
    TaskStatus.REVIEW: "#8764B8",
    TaskStatus.DONE: "#107C10",
}


class Priority(IntEnum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3

    @property
    def label(self) -> str:
        return _PRIORITY_LABELS[self]

    @property
    def color(self) -> str:
        return _PRIORITY_COLORS[self]


_PRIORITY_LABELS = {
    Priority.LOW: "Basse",
    Priority.NORMAL: "Normale",
    Priority.HIGH: "Haute",
    Priority.URGENT: "Urgente",
}
_PRIORITY_COLORS = {
    Priority.LOW: "#8A8886",
    Priority.NORMAL: "#0F6CBD",
    Priority.HIGH: "#CA5010",
    Priority.URGENT: "#C42B1C",
}


class ProjectStatus(str, Enum):
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"

    @property
    def label(self) -> str:
        return _PROJECT_STATUS_LABELS[self]

    @property
    def color(self) -> str:
        return _PROJECT_STATUS_COLORS[self]


_PROJECT_STATUS_LABELS = {
    ProjectStatus.ACTIVE: "Actif",
    ProjectStatus.ON_HOLD: "En pause",
    ProjectStatus.COMPLETED: "Terminé",
}
_PROJECT_STATUS_COLORS = {
    ProjectStatus.ACTIVE: "#107C10",
    ProjectStatus.ON_HOLD: "#9D5D00",
    ProjectStatus.COMPLETED: "#5D5A58",
}


@dataclass
class Project:
    id: int | None = None
    name: str = ""
    description: str = ""
    color: str = ACCENT_PALETTE[0]
    status: ProjectStatus = ProjectStatus.ACTIVE
    start_date: date | None = None
    due_date: date | None = None
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class Member:
    id: int | None = None
    name: str = ""
    role: str = ""
    color: str = ACCENT_PALETTE[0]


@dataclass
class Subtask:
    id: int | None = None
    task_id: int | None = None
    title: str = ""
    done: bool = False
    position: int = 0


@dataclass
class Task:
    id: int | None = None
    project_id: int = 0
    title: str = ""
    description: str = ""
    status: TaskStatus = TaskStatus.TODO
    priority: Priority = Priority.NORMAL
    assignee_id: int | None = None
    due_date: date | None = None
    tags: list[str] = field(default_factory=list)
    position: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    subtasks: list[Subtask] = field(default_factory=list)

    @property
    def is_done(self) -> bool:
        return self.status is TaskStatus.DONE

    def is_overdue(self, today: date | None = None) -> bool:
        today = today or date.today()
        return self.due_date is not None and not self.is_done and self.due_date < today

    @property
    def progress(self) -> float:
        if self.subtasks:
            return sum(1 for s in self.subtasks if s.done) / len(self.subtasks)
        return 1.0 if self.is_done else 0.0
