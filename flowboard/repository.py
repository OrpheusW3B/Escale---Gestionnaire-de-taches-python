"""Persistance SQLite. Chaque écriture émet `changed` pour rafraîchir les pages."""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from .models import Member, Priority, Project, ProjectStatus, Subtask, Task, TaskStatus

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    color       TEXT NOT NULL DEFAULT '#0F6CBD',
    status      TEXT NOT NULL DEFAULT 'active',
    start_date  TEXT,
    due_date    TEXT,
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS members (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name  TEXT NOT NULL,
    role  TEXT NOT NULL DEFAULT '',
    color TEXT NOT NULL DEFAULT '#0F6CBD'
);
CREATE TABLE IF NOT EXISTS tasks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id   INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title        TEXT NOT NULL,
    description  TEXT NOT NULL DEFAULT '',
    status       TEXT NOT NULL DEFAULT 'todo',
    priority     INTEGER NOT NULL DEFAULT 1,
    assignee_id  INTEGER REFERENCES members(id) ON DELETE SET NULL,
    due_date     TEXT,
    tags         TEXT NOT NULL DEFAULT '',
    position     INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    completed_at TEXT
);
CREATE TABLE IF NOT EXISTS subtasks (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id  INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    title    TEXT NOT NULL,
    done     INTEGER NOT NULL DEFAULT 0,
    position INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def _iso_date(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _iso_dt(value: datetime | None) -> str | None:
    return value.isoformat(timespec="seconds") if value else None


def _parse_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def _parse_dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


class Repository(QObject):
    """Accès aux données. Émet `changed` après chaque écriture."""

    changed = Signal()

    def __init__(self, db_path: Path, parent: QObject | None = None):
        super().__init__(parent)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(SCHEMA)
        if self._get_meta("seeded") is None:
            self._seed_demo()

    # ----- méta -------------------------------------------------------------
    def _get_meta(self, key: str) -> str | None:
        row = self._conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def _set_meta(self, key: str, value: str) -> None:
        with self._conn:
            self._conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, value))

    # ----- projets ----------------------------------------------------------
    def list_projects(self) -> list[Project]:
        rows = self._conn.execute("SELECT * FROM projects ORDER BY id").fetchall()
        return [self._project(r) for r in rows]

    def get_project(self, project_id: int) -> Project | None:
        row = self._conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return self._project(row) if row else None

    def save_project(self, project: Project) -> Project:
        values = (project.name, project.description, project.color, project.status.value,
                  _iso_date(project.start_date), _iso_date(project.due_date))
        with self._conn:
            if project.id is None:
                project.created_at = datetime.now()
                cur = self._conn.execute(
                    "INSERT INTO projects (name, description, color, status, start_date, due_date, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)", (*values, _iso_dt(project.created_at)))
                project.id = cur.lastrowid
            else:
                self._conn.execute(
                    "UPDATE projects SET name=?, description=?, color=?, status=?, start_date=?, due_date=? "
                    "WHERE id=?", (*values, project.id))
        self.changed.emit()
        return project

    def delete_project(self, project_id: int) -> None:
        with self._conn:
            self._conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        self.changed.emit()

    # ----- membres ----------------------------------------------------------
    def list_members(self) -> list[Member]:
        rows = self._conn.execute("SELECT * FROM members ORDER BY id").fetchall()
        return [Member(id=r["id"], name=r["name"], role=r["role"], color=r["color"]) for r in rows]

    def save_member(self, member: Member) -> Member:
        with self._conn:
            if member.id is None:
                cur = self._conn.execute("INSERT INTO members (name, role, color) VALUES (?, ?, ?)",
                                         (member.name, member.role, member.color))
                member.id = cur.lastrowid
            else:
                self._conn.execute("UPDATE members SET name=?, role=?, color=? WHERE id=?",
                                   (member.name, member.role, member.color, member.id))
        self.changed.emit()
        return member

    def delete_member(self, member_id: int) -> None:
        with self._conn:
            self._conn.execute("DELETE FROM members WHERE id = ?", (member_id,))
        self.changed.emit()

    # ----- tâches -----------------------------------------------------------
    def list_tasks(self, project_id: int | None = None) -> list[Task]:
        if project_id is None:
            rows = self._conn.execute("SELECT * FROM tasks ORDER BY position, id").fetchall()
        else:
            rows = self._conn.execute("SELECT * FROM tasks WHERE project_id = ? ORDER BY position, id",
                                      (project_id,)).fetchall()
        tasks = [self._task(r) for r in rows]
        subs = self._subtasks_by_task([t.id for t in tasks])
        for task in tasks:
            task.subtasks = subs.get(task.id, [])
        return tasks

    def get_task(self, task_id: int) -> Task | None:
        row = self._conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            return None
        task = self._task(row)
        task.subtasks = self._subtasks_by_task([task_id]).get(task_id, [])
        return task

    def save_task(self, task: Task) -> Task:
        now = datetime.now()
        task.updated_at = now
        task.completed_at = (task.completed_at or now) if task.status is TaskStatus.DONE else None
        base = (task.project_id, task.title, task.description, task.status.value, int(task.priority),
                task.assignee_id, _iso_date(task.due_date), ",".join(task.tags), task.position)
        with self._conn:
            if task.id is None:
                task.created_at = now
                task.position = self._next_position(task.project_id, task.status)
                base = (*base[:-1], task.position)
                cur = self._conn.execute(
                    "INSERT INTO tasks (project_id, title, description, status, priority, assignee_id, due_date, "
                    "tags, position, created_at, updated_at, completed_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (*base, _iso_dt(task.created_at), _iso_dt(now), _iso_dt(task.completed_at)))
                task.id = cur.lastrowid
            else:
                previous = self._conn.execute("SELECT status FROM tasks WHERE id = ?", (task.id,)).fetchone()
                if previous is None or previous["status"] != task.status.value:
                    task.position = self._next_position(task.project_id, task.status)
                    base = (*base[:-1], task.position)
                self._conn.execute(
                    "UPDATE tasks SET project_id=?, title=?, description=?, status=?, priority=?, assignee_id=?, "
                    "due_date=?, tags=?, position=?, updated_at=?, completed_at=? WHERE id=?",
                    (*base, _iso_dt(now), _iso_dt(task.completed_at), task.id))
            self._conn.execute("DELETE FROM subtasks WHERE task_id = ?", (task.id,))
            for index, sub in enumerate(task.subtasks):
                cur = self._conn.execute(
                    "INSERT INTO subtasks (task_id, title, done, position) VALUES (?,?,?,?)",
                    (task.id, sub.title, int(sub.done), index))
                sub.id, sub.task_id, sub.position = cur.lastrowid, task.id, index
        self.changed.emit()
        return task

    def move_task(self, task_id: int, status: TaskStatus, ordered_ids: list[int]) -> None:
        """Change le statut d'une tâche et enregistre l'ordre des cartes de la colonne cible."""
        now = datetime.now()
        with self._conn:
            row = self._conn.execute("SELECT status, completed_at FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row is None:
                return
            if status is TaskStatus.DONE:
                completed = row["completed_at"] if row["status"] == TaskStatus.DONE.value else _iso_dt(now)
            else:
                completed = None
            self._conn.execute("UPDATE tasks SET status = ?, completed_at = ?, updated_at = ? WHERE id = ?",
                               (status.value, completed, _iso_dt(now), task_id))
            for position, tid in enumerate(ordered_ids):
                self._conn.execute("UPDATE tasks SET position = ? WHERE id = ?", (position, tid))
        self.changed.emit()

    def set_subtask_done(self, subtask_id: int, done: bool) -> None:
        """Coche ou décoche une sous-tâche sans toucher au reste de la tâche."""
        with self._conn:
            self._conn.execute("UPDATE subtasks SET done = ? WHERE id = ?",
                               (int(done), subtask_id))
        self.changed.emit()

    def delete_task(self, task_id: int) -> None:
        with self._conn:
            self._conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        self.changed.emit()

    def reset_demo_data(self) -> None:
        with self._conn:
            for table in ("subtasks", "tasks", "members", "projects"):
                self._conn.execute(f"DELETE FROM {table}")
        self._seed_demo()
        self.changed.emit()

    def clear_all_data(self) -> None:
        """Supprime tous les projets, tâches et membres, laissant l'application vierge."""
        with self._conn:
            for table in ("subtasks", "tasks", "members", "projects"):
                self._conn.execute(f"DELETE FROM {table}")
        self.changed.emit()

    # ----- utilitaires internes --------------------------------------------
    def _next_position(self, project_id: int, status: TaskStatus) -> int:
        row = self._conn.execute(
            "SELECT COALESCE(MAX(position), -1) + 1 AS nxt FROM tasks WHERE project_id = ? AND status = ?",
            (project_id, status.value)).fetchone()
        return int(row["nxt"])

    def _subtasks_by_task(self, task_ids: list[int]) -> dict[int, list[Subtask]]:
        if not task_ids:
            return {}
        marks = ",".join("?" * len(task_ids))
        rows = self._conn.execute(
            f"SELECT * FROM subtasks WHERE task_id IN ({marks}) ORDER BY position, id", task_ids).fetchall()
        result: dict[int, list[Subtask]] = {}
        for r in rows:
            result.setdefault(r["task_id"], []).append(
                Subtask(id=r["id"], task_id=r["task_id"], title=r["title"],
                        done=bool(r["done"]), position=r["position"]))
        return result

    @staticmethod
    def _project(r: sqlite3.Row) -> Project:
        return Project(id=r["id"], name=r["name"], description=r["description"], color=r["color"],
                       status=ProjectStatus(r["status"]), start_date=_parse_date(r["start_date"]),
                       due_date=_parse_date(r["due_date"]),
                       created_at=_parse_dt(r["created_at"]) or datetime.now())

    @staticmethod
    def _task(r: sqlite3.Row) -> Task:
        return Task(id=r["id"], project_id=r["project_id"], title=r["title"], description=r["description"],
                    status=TaskStatus(r["status"]), priority=Priority(r["priority"]),
                    assignee_id=r["assignee_id"], due_date=_parse_date(r["due_date"]),
                    tags=[t for t in r["tags"].split(",") if t], position=r["position"],
                    created_at=_parse_dt(r["created_at"]) or datetime.now(),
                    updated_at=_parse_dt(r["updated_at"]) or datetime.now(),
                    completed_at=_parse_dt(r["completed_at"]))

    # ----- données de démonstration ----------------------------------------
    def _seed_demo(self) -> None:
        today = date.today()

        def d(offset: int) -> date:
            return today + timedelta(days=offset)

        camille = self.save_member(Member(name="Camille Durand", role="Cheffe de projet", color="#0F6CBD"))
        lucas = self.save_member(Member(name="Lucas Martin", role="Développeur front-end", color="#038387"))
        ines = self.save_member(Member(name="Inès Bernard", role="Designer UI/UX", color="#8764B8"))
        thomas = self.save_member(Member(name="Thomas Petit", role="Développeur back-end", color="#CA5010"))

        site = self.save_project(Project(
            name="Refonte du site vitrine", description="Nouvelle identité web et accessibilité WCAG AA",
            color="#0F6CBD", start_date=d(-30), due_date=d(21)))
        mobile = self.save_project(Project(
            name="Application mobile v2", description="Synchronisation hors ligne et connexion unique",
            color="#038387", start_date=d(-10), due_date=d(45)))
        campaign = self.save_project(Project(
            name="Campagne d'automne", description="Contenus réseaux sociaux et bannières publicitaires",
            color="#CA5010", status=ProjectStatus.ON_HOLD, start_date=d(-45), due_date=d(60)))

        def add(project, title, status, priority, who, due, tags="", subs=()):
            self.save_task(Task(
                project_id=project.id, title=title, status=status, priority=priority,
                assignee_id=who.id if who else None, due_date=due,
                tags=[t.strip() for t in tags.split(",") if t.strip()],
                subtasks=[Subtask(title=s, done=done) for s, done in subs]))

        add(site, "Valider l'arborescence du site", TaskStatus.DONE, Priority.HIGH, camille, d(-5),
            "contenu", [("Plan du site", True), ("Validation client", True)])
        add(site, "Maquettes de la page d'accueil", TaskStatus.IN_PROGRESS, Priority.HIGH, ines, d(3),
            "design", [("Version bureau", True), ("Version mobile", False), ("Mode sombre", False)])
        add(site, "Intégrer le menu de navigation", TaskStatus.IN_PROGRESS, Priority.NORMAL, lucas, d(6),
            "front, navigation")
        add(site, "Rédiger les textes de la page Services", TaskStatus.TODO, Priority.LOW, camille, d(10),
            "contenu")
        add(site, "Optimiser le temps de chargement", TaskStatus.TODO, Priority.URGENT, thomas, d(-1),
            "performance", [("Compresser les images", False), ("Activer le cache", False)])
        add(site, "Relecture accessibilité (WCAG)", TaskStatus.REVIEW, Priority.NORMAL, ines, d(1),
            "accessibilité")
        add(site, "Mise en ligne en préproduction", TaskStatus.TODO, Priority.NORMAL, thomas, d(14))

        add(mobile, "Écran de connexion avec SSO", TaskStatus.REVIEW, Priority.HIGH, lucas, d(2), "auth")
        add(mobile, "Synchronisation hors ligne", TaskStatus.IN_PROGRESS, Priority.URGENT, thomas, d(8), "sync",
            [("File d'attente locale", True), ("Résolution des conflits", False),
             ("Tests en réseau instable", False), ("Documentation", False)])
        add(mobile, "Tests utilisateurs (5 personnes)", TaskStatus.TODO, Priority.NORMAL, ines, d(20), "UX")
        add(mobile, "Notifications push", TaskStatus.TODO, Priority.NORMAL, lucas, d(25), "notifications")
        add(mobile, "Mise à jour de l'icône et du thème", TaskStatus.DONE, Priority.LOW, ines, d(-2), "design")

        add(campaign, "Brief créatif", TaskStatus.DONE, Priority.HIGH, camille, d(-20))
        add(campaign, "Planifier les publications", TaskStatus.TODO, Priority.NORMAL, camille, d(30), "social")
        add(campaign, "Préparer les bannières", TaskStatus.TODO, Priority.NORMAL, ines, d(12), "visuels")

        self._set_meta("seeded", "1")
