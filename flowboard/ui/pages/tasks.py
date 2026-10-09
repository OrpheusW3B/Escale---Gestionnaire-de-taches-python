"""Page des tâches : tableau filtrable, édition rapide, menu contextuel et export CSV."""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QAbstractItemView, QFileDialog, QHBoxLayout, QHeaderView, QTableWidgetItem, QVBoxLayout, QWidget
from qfluentwidgets import (ComboBox, FluentIcon as FIF, MessageBox, PrimaryPushButton, PushButton,
                            RoundMenu, SearchLineEdit, TableWidget)

from ...models import Priority, Project, Task, TaskStatus
from ...repository import Repository
from ...utils import export_tasks_csv, format_date, relative_due
from ..common import PageHeader, make_action, notify
from ..dialogs import TaskDialog
from ..widgets import danger_color, tone

COLUMNS = ["Tâche", "Projet", "Statut", "Priorité", "Responsable", "Échéance", "Sous-tâches"]


class TasksPage(QWidget):
    def __init__(self, repo: Repository, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("tasksPage")
        self.repo = repo
        self._rows: list[Task] = []
        self._projects: list[Project] = []
        self._project_choices: list[int | None] = [None]
        self._status_choices: list[TaskStatus | None] = [None, *TaskStatus]
        self._priority_choices: list[Priority | None] = [None, *Priority]
        self._sort_column = -1
        self._sort_order = Qt.SortOrder.AscendingOrder

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 28, 36, 24)
        root.setSpacing(16)

        self.header = PageHeader("Tâches")
        export_button = PushButton("Exporter en CSV", self, FIF.DOWNLOAD)
        export_button.clicked.connect(lambda _checked=False: self.export_csv())
        new_button = PrimaryPushButton("Nouvelle tâche", self, FIF.ADD)
        new_button.clicked.connect(lambda _checked=False: self.new_task())
        self.header.add_action(export_button)
        self.header.add_action(new_button)
        root.addWidget(self.header)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        self.search = SearchLineEdit(self)
        self.search.setPlaceholderText("Rechercher une tâche")
        self.search.setFixedWidth(260)
        self.search.textChanged.connect(lambda *_: self.refresh())
        self.project_box = ComboBox(self)
        self.project_box.setFixedWidth(220)
        self.status_box = ComboBox(self)
        self.status_box.setFixedWidth(160)
        self.status_box.addItem("Tous les statuts")
        for status in TaskStatus:
            self.status_box.addItem(status.label)
        self.priority_box = ComboBox(self)
        self.priority_box.setFixedWidth(190)
        self.priority_box.addItem("Toutes les priorités")
        for priority in Priority:
            self.priority_box.addItem(priority.label)
        for box in (self.project_box, self.status_box, self.priority_box):
            box.currentIndexChanged.connect(lambda *_: self.refresh())
        toolbar.addWidget(self.search)
        toolbar.addWidget(self.project_box)
        toolbar.addWidget(self.status_box)
        toolbar.addWidget(self.priority_box)
        toolbar.addStretch(1)
        root.addLayout(toolbar)

        self.table = TableWidget(self)
        self.table.setColumnCount(len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setWordWrap(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, len(COLUMNS)):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSortIndicatorShown(True)
        header.sectionClicked.connect(self._on_header_clicked)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_menu)
        self.table.cellDoubleClicked.connect(lambda row, _column: self._edit_row(row))
        root.addWidget(self.table, 1)

        self.repo.changed.connect(self._schedule_refresh)
        self.refresh()

    # ----- affichage -------------------------------------------------------
    def refresh(self) -> None:
        self._projects = self.repo.list_projects()
        self._fill_project_box()
        names = {p.id: p.name for p in self._projects}
        members = {m.id: m.name for m in self.repo.list_members()}
        tasks = self.repo.list_tasks()
        self._rows = self._sort_tasks(self._filtered(tasks), names, members)
        self.header.set_subtitle(f"{len(self._rows)} tâche{'s' if len(self._rows) != 1 else ''} affichée"
                                 f"{'s' if len(self._rows) != 1 else ''} sur {len(tasks)}.")

        self.table.setRowCount(len(self._rows))
        for row, task in enumerate(self._rows):
            status_text = task.status.label
            cells = [
                task.title,
                names.get(task.project_id, ""),
                status_text,
                task.priority.label,
                members.get(task.assignee_id, "Non assigné") if task.assignee_id is not None else "Non assigné",
                (format_date(task.due_date) if task.is_done else relative_due(task.due_date))
                if task.due_date else "—",
                f"{sum(1 for s in task.subtasks if s.done)}/{len(task.subtasks)}" if task.subtasks else "—",
            ]
            for column, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, task.id)
                if column == 2:
                    item.setForeground(QBrush(QColor(tone(task.status.color))))
                elif column == 3 and task.priority >= Priority.HIGH:
                    item.setForeground(QBrush(QColor(tone(task.priority.color))))
                elif column == 5 and task.is_overdue():
                    item.setForeground(QBrush(danger_color()))
                self.table.setItem(row, column, item)
        if self._sort_column >= 0:
            self.table.horizontalHeader().setSortIndicator(self._sort_column, self._sort_order)
        self.table.resizeRowsToContents()

    def _fill_project_box(self) -> None:
        current = self._project_choices[self.project_box.currentIndex()] if self._project_choices else None
        self.project_box.blockSignals(True)
        self.project_box.clear()
        self._project_choices = [None] + [p.id for p in self._projects]
        self.project_box.addItem("Tous les projets")
        for project in self._projects:
            self.project_box.addItem(project.name)
        index = self._project_choices.index(current) if current in self._project_choices else 0
        self.project_box.setCurrentIndex(index)
        self.project_box.blockSignals(False)

    def _filtered(self, tasks: list[Task]) -> list[Task]:
        query = self.search.text().strip().lower()
        project = self._project_choices[self.project_box.currentIndex()]
        status = self._status_choices[self.status_box.currentIndex()]
        priority = self._priority_choices[self.priority_box.currentIndex()]
        result = []
        for task in tasks:
            if query and query not in task.title.lower() and not any(
                    query in tag.lower() for tag in task.tags):
                continue
            if project is not None and task.project_id != project:
                continue
            if status is not None and task.status is not status:
                continue
            if priority is not None and task.priority != priority:
                continue
            result.append(task)
        return result

    def _schedule_refresh(self, *_args) -> None:
        QTimer.singleShot(0, self.refresh)

    def _on_header_clicked(self, column: int) -> None:
        if column == self._sort_column:
            self._sort_order = (Qt.SortOrder.DescendingOrder
                                if self._sort_order == Qt.SortOrder.AscendingOrder
                                else Qt.SortOrder.AscendingOrder)
        else:
            self._sort_column = column
            self._sort_order = Qt.SortOrder.AscendingOrder
        self.refresh()

    def _sort_key(self, task: Task, names: dict[int, str], members: dict[int, str]):
        column = self._sort_column
        if column == 0:
            return task.title.lower()
        if column == 1:
            return names.get(task.project_id, "").lower()
        if column == 2:
            return task.status.value
        if column == 3:
            return int(task.priority)
        if column == 4:
            if task.assignee_id is None:
                return ""
            return members.get(task.assignee_id, "").lower()
        if column == 5:
            return task.due_date or date.max
        return task.progress

    def _sort_tasks(self, tasks: list[Task], names: dict[int, str],
                    members: dict[int, str]) -> list[Task]:
        if self._sort_column < 0:
            return tasks
        return sorted(tasks, key=lambda t: self._sort_key(t, names, members),
                      reverse=self._sort_order == Qt.SortOrder.DescendingOrder)

    # ----- actions ---------------------------------------------------------
    def _task_at(self, row: int) -> Task | None:
        return self._rows[row] if 0 <= row < len(self._rows) else None

    def _members_list(self):
        return self.repo.list_members()

    def new_task(self) -> None:
        if not self._projects:
            notify(self.window(), "Aucun projet", "Créez d'abord un projet pour y ajouter des tâches.", error=True)
            return
        dialog = TaskDialog(self._projects, self._members_list(), self.window())
        if dialog.exec() and dialog.validate():
            self.repo.save_task(dialog.build_task())

    def _edit_row(self, row: int) -> None:
        task = self._task_at(row)
        if task is None:
            return
        fresh = self.repo.get_task(task.id)
        if fresh is None:
            return
        dialog = TaskDialog(self._projects, self._members_list(), self.window(), task=fresh)
        if dialog.exec() and dialog.validate():
            self.repo.save_task(dialog.build_task())

    def _toggle_done(self, task_id: int) -> None:
        task = self.repo.get_task(task_id)
        if task is None:
            return
        task.status = TaskStatus.IN_PROGRESS if task.is_done else TaskStatus.DONE
        self.repo.save_task(task)

    def _delete(self, task_id: int) -> None:
        task = self.repo.get_task(task_id)
        if task is None:
            return
        box = MessageBox("Supprimer la tâche ?", f"« {task.title} » sera supprimée définitivement.", self.window())
        box.yesButton.setText("Supprimer")
        box.cancelButton.setText("Annuler")
        if box.exec():
            self.repo.delete_task(task_id)

    def _show_menu(self, pos) -> None:
        row = self.table.rowAt(pos.y())
        task = self._task_at(row)
        if task is None:
            return
        tid = task.id
        menu = RoundMenu(parent=self)
        menu.addAction(make_action("Modifier", lambda: self._edit_row(row), FIF.EDIT, menu))
        done_label = "Rouvrir la tâche" if task.is_done else "Marquer comme terminée"
        menu.addAction(make_action(done_label, lambda: self._toggle_done(tid), FIF.ACCEPT, menu))
        menu.addSeparator()
        menu.addAction(make_action("Supprimer", lambda: self._delete(tid), FIF.DELETE, menu))
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def export_csv(self) -> None:
        if not self._rows:
            notify(self.window(), "Rien à exporter", "Aucune tâche ne correspond aux filtres actuels.", error=True)
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exporter les tâches", "escale-taches.csv",
                                              "Fichier CSV (*.csv)")
        if not path:
            return
        names = {p.id: p.name for p in self._projects}
        members = {m.id: m.name for m in self.repo.list_members()}
        export_tasks_csv(path, self._rows, names, members)
        notify(self.window(), "Export terminé", f"{len(self._rows)} tâches enregistrées.")
