"""Page Kanban : choix du projet, filtres, progression et actions sur les tâches."""
from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget
from qfluentwidgets import (CaptionLabel, ComboBox, FluentIcon as FIF, MessageBox, PrimaryPushButton,
                            ProgressBar, PushButton, SearchLineEdit, qconfig)

from ...models import Member, Priority, Project, Task, TaskStatus
from ...repository import Repository
from ...settings import cfg
from ...utils import format_date
from ..common import EmptyState, PageHeader, notify
from ..dialogs import ProjectDialog, TaskDialog
from ..kanban import KanbanBoard


class BoardPage(QWidget):
    def __init__(self, repo: Repository, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("boardPage")
        self.repo = repo
        self.current_project_id: int | None = cfg.get(cfg.lastProjectId) or None
        self._projects: list[Project] = []
        self._project_tasks: list[Task] = []
        self._members: dict[int, Member] = {}
        self._priority_choices: list[Priority | None] = [None, *Priority]
        self._assignee_choices: list[int | None] = []
        self._assignee_filter: int | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 28, 36, 24)
        root.setSpacing(16)

        self.header = PageHeader("Kanban")
        self.edit_project_button = PushButton("Modifier le projet", self, FIF.EDIT)
        self.edit_project_button.clicked.connect(lambda _checked=False: self.edit_current_project())
        self.new_task_button = PrimaryPushButton("Nouvelle tâche", self, FIF.ADD)
        self.new_task_button.clicked.connect(lambda _checked=False: self.add_task(TaskStatus.TODO))
        self.header.add_action(self.edit_project_button)
        self.header.add_action(self.new_task_button)
        root.addWidget(self.header)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        self.project_box = ComboBox(self)
        self.project_box.setMinimumWidth(240)
        self.project_box.currentIndexChanged.connect(self._on_project_changed)
        self.search = SearchLineEdit(self)
        self.search.setPlaceholderText("Rechercher une tâche ou une étiquette")
        self.search.setFixedWidth(300)
        self.search.textChanged.connect(lambda *_: self.refresh())
        self.priority_box = ComboBox(self)
        self.priority_box.setFixedWidth(190)
        self.priority_box.addItem("Toutes les priorités")
        for priority in Priority:
            self.priority_box.addItem(priority.label)
        self.priority_box.currentIndexChanged.connect(lambda *_: self.refresh())
        self.assignee_box = ComboBox(self)
        self.assignee_box.setFixedWidth(190)
        self.assignee_box.currentIndexChanged.connect(self._on_assignee_changed)
        toolbar.addWidget(self.project_box)
        toolbar.addWidget(self.search)
        toolbar.addStretch(1)
        toolbar.addWidget(self.priority_box)
        toolbar.addWidget(self.assignee_box)
        root.addLayout(toolbar)

        summary = QHBoxLayout()
        summary.setSpacing(14)
        self.summary_label = CaptionLabel("", self)
        self.summary_bar = ProgressBar(self)
        self.summary_bar.setFixedWidth(220)
        summary.addWidget(self.summary_label)
        summary.addStretch(1)
        summary.addWidget(self.summary_bar)
        root.addLayout(summary)

        self.stack = QStackedWidget(self)
        self.board = KanbanBoard(self)
        self.empty = EmptyState(FIF.LAYOUT, "Aucun projet pour le moment",
                                "Créez un projet pour organiser ses tâches sur un tableau Kanban.",
                                "Nouveau projet", self)
        self.empty.button.clicked.connect(lambda _checked=False: self.create_project())
        self.stack.addWidget(self.board)
        self.stack.addWidget(self.empty)
        root.addWidget(self.stack, 1)

        self.board.addRequested.connect(self.add_task)
        self.board.editRequested.connect(self.edit_task)
        self.board.deleteRequested.connect(self.delete_task)
        self.board.moveRequested.connect(self.move_task)
        self.board.taskDropped.connect(self._on_dropped)
        self.board.subtaskToggled.connect(self._on_subtask_toggled)
        self.board.toggleDoneRequested.connect(self._on_toggle_done)

        self.repo.changed.connect(self._schedule_refresh)
        self.refresh()

    # ----- affichage -------------------------------------------------------
    def set_project(self, project_id: int | None) -> None:
        self.current_project_id = project_id
        qconfig.set(cfg.lastProjectId, project_id or 0)
        self.refresh()

    def refresh(self) -> None:
        self._projects = self.repo.list_projects()
        members = self.repo.list_members()
        self._members = {m.id: m for m in members}
        self._fill_project_box()
        self._fill_assignee_box(members)

        has_project = bool(self._projects)
        self.edit_project_button.setEnabled(has_project)
        self.new_task_button.setEnabled(has_project)
        if not has_project:
            self.stack.setCurrentWidget(self.empty)
            self.header.set_subtitle("Créez un projet pour commencer à planifier vos tâches.")
            self.summary_label.setText("")
            self.summary_bar.setValue(0)
            return

        project = self._current_project()
        self._project_tasks = self.repo.list_tasks(project.id)
        # B6 : totaux par statut (indépendants des filtres)
        totals = {status: 0 for status in TaskStatus}
        for task in self._project_tasks:
            totals[task.status] += 1
        self.board.set_tasks(self._filtered(self._project_tasks), self._members, totals)
        self.stack.setCurrentWidget(self.board)
        self.header.set_subtitle(
            project.description or "Glissez les cartes d'une colonne à l'autre pour changer leur statut.")
        self._update_summary(project)

    def _update_summary(self, project: Project) -> None:
        if not self._project_tasks:
            self.summary_label.setText("Aucune tâche dans ce projet pour le moment.")
            self.summary_bar.setValue(0)
            return
        done = sum(1 for t in self._project_tasks if t.is_done)
        due = f" Échéance le {format_date(project.due_date)}." if project.due_date else ""
        self.summary_label.setText(f"{done} sur {len(self._project_tasks)} tâches terminées.{due}")
        self.summary_bar.setValue(round(100 * done / len(self._project_tasks)))

    def _current_project(self) -> Project:
        for project in self._projects:
            if project.id == self.current_project_id:
                return project
        self.current_project_id = self._projects[0].id
        return self._projects[0]

    def _fill_project_box(self) -> None:
        self.project_box.blockSignals(True)
        self.project_box.clear()
        for project in self._projects:
            self.project_box.addItem(project.name)
        ids = [p.id for p in self._projects]
        if self.current_project_id in ids:
            self.project_box.setCurrentIndex(ids.index(self.current_project_id))
        elif ids:
            self.project_box.setCurrentIndex(0)
        self.project_box.blockSignals(False)

    def _fill_assignee_box(self, members: list[Member]) -> None:
        self.assignee_box.blockSignals(True)
        self.assignee_box.clear()
        self._assignee_choices = [None, -1] + [m.id for m in members]
        self.assignee_box.addItem("Tous les membres")
        self.assignee_box.addItem("Non assigné")
        for member in members:
            self.assignee_box.addItem(member.name)
        if self._assignee_filter in self._assignee_choices:
            index = self._assignee_choices.index(self._assignee_filter)
        else:
            index = 0
            self._assignee_filter = None
        self.assignee_box.setCurrentIndex(index)
        self.assignee_box.blockSignals(False)

    def _filtered(self, tasks: list[Task]) -> list[Task]:
        query = self.search.text().strip().lower()
        priority = self._priority_choices[self.priority_box.currentIndex()]
        result = []
        for task in tasks:
            if query and query not in task.title.lower() and not any(query in t.lower() for t in task.tags):
                continue
            if priority is not None and task.priority != priority:
                continue
            if self._assignee_filter == -1 and task.assignee_id is not None:
                continue
            if self._assignee_filter not in (None, -1) and task.assignee_id != self._assignee_filter:
                continue
            result.append(task)
        return result

    def _schedule_refresh(self, *_args) -> None:
        QTimer.singleShot(0, self.refresh)

    def _on_project_changed(self, index: int) -> None:
        if 0 <= index < len(self._projects):
            self.set_project(self._projects[index].id)

    def _on_assignee_changed(self, index: int) -> None:
        if 0 <= index < len(self._assignee_choices):
            self._assignee_filter = self._assignee_choices[index]
            self.refresh()

    # ----- actions sur les tâches -------------------------------------------
    def _members_list(self) -> list[Member]:
        return list(self._members.values())

    def _save_task(self, task: Task) -> None:
        # B8 : erreur de sauvegarde signalée au lieu d'un crash
        try:
            self.repo.save_task(task)
        except ValueError as error:
            notify(self.window(), "Sauvegarde impossible", str(error), error=True)

    def add_task(self, status: TaskStatus) -> None:
        if not self._projects:
            return
        dialog = TaskDialog(self._projects, self._members_list(), self.window(),
                            project_id=self.current_project_id, status=status)
        if dialog.exec() and dialog.validate():
            self._save_task(dialog.build_task())

    def edit_task(self, task_id: int) -> None:
        task = self.repo.get_task(task_id)
        if task is None:
            return
        dialog = TaskDialog(self._projects, self._members_list(), self.window(), task=task)
        if dialog.exec() and dialog.validate():
            self._save_task(dialog.build_task())

    def delete_task(self, task_id: int) -> None:
        task = self.repo.get_task(task_id)
        if task is None:
            return
        box = MessageBox("Supprimer la tâche ?", f"« {task.title} » sera supprimée définitivement.", self.window())
        box.yesButton.setText("Supprimer")
        box.cancelButton.setText("Annuler")
        if box.exec():
            self.repo.delete_task(task_id)

    def move_task(self, task_id: int, status: TaskStatus) -> None:
        ordered = [t.id for t in self._project_tasks if t.status is status and t.id != task_id]
        ordered.append(task_id)
        self.repo.move_task(task_id, status, ordered)

    def _on_dropped(self, task_id: int, status: TaskStatus, ordered_ids: list[int]) -> None:
        self.repo.move_task(task_id, status, list(ordered_ids))

    def _on_subtask_toggled(self, subtask_id: int, done: bool) -> None:
        self.repo.set_subtask_done(subtask_id, done)

    def _on_toggle_done(self, task_id: int) -> None:
        task = self.repo.get_task(task_id)
        if task is None:
            return
        task.status = TaskStatus.IN_PROGRESS if task.is_done else TaskStatus.DONE
        self._save_task(task)

    def edit_current_project(self) -> None:
        if not self._projects:
            return
        dialog = ProjectDialog(self.window(), self._current_project())
        if dialog.exec() and dialog.validate():
            self.repo.save_project(dialog.build_project())

    def create_project(self) -> None:
        dialog = ProjectDialog(self.window())
        if dialog.exec() and dialog.validate():
            project = self.repo.save_project(dialog.build_project())
            self.set_project(project.id)
