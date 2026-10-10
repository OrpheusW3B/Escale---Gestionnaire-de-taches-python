"""Page des projets : recherche, filtre par statut, avancement et actions rapides."""
from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor, QCursor
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (CaptionLabel, ComboBox, FluentIcon as FIF, MessageBox, PrimaryPushButton,
                            ProgressBar, RoundMenu, SearchLineEdit, StrongBodyLabel, TransparentToolButton)

from ...models import Member, Project, ProjectStatus
from ...repository import Repository
from ...utils import format_date, plural
from ..common import EmptyState, PageBase, PageHeader, clear_layout, make_action, muted_label, notify
from ..dialogs import ProjectDialog
from ..widgets import AvatarStack, Pill, Surface


class ProjectRow(Surface):
    """Ligne de projet : couleur, avancement, statut, équipe et actions."""

    openRequested = Signal(int)
    editRequested = Signal(int)
    deleteRequested = Signal(int)

    def __init__(self, project: Project, total: int, done: int, people: list[Member],
                 parent: QWidget | None = None):
        super().__init__(parent, variant="row", radius=8)
        self.project = project
        self.accent_left = QColor(project.color)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(22, 16, 14, 16)
        layout.setSpacing(24)

        info = QVBoxLayout()
        info.setSpacing(4)
        info.addWidget(StrongBodyLabel(project.name, self))
        description = CaptionLabel(project.description or "Pas encore de description", self)
        description.setWordWrap(True)
        info.addWidget(description)
        layout.addLayout(info, 5)

        progress = QVBoxLayout()
        progress.setSpacing(8)
        bar = ProgressBar(self)
        bar.setValue(round(100 * done / total) if total else 0)
        progress.addWidget(bar)
        summary = f"{done} sur {total} tâches terminées" if total else "Aucune tâche pour l'instant"
        progress.addWidget(CaptionLabel(summary, self))
        layout.addLayout(progress, 4)

        meta = QVBoxLayout()
        meta.setSpacing(6)
        meta.addWidget(Pill(project.status.label, project.status.color, self), 0, Qt.AlignmentFlag.AlignRight)
        due_text = f"Échéance le {format_date(project.due_date)}" if project.due_date else "Sans échéance"
        meta.addWidget(CaptionLabel(due_text, self), 0, Qt.AlignmentFlag.AlignRight)
        layout.addLayout(meta, 2)

        layout.addWidget(AvatarStack([(m.name, m.color) for m in people], 24, self), 0,
                         Qt.AlignmentFlag.AlignVCenter)
        more = TransparentToolButton(FIF.MORE, self)
        more.clicked.connect(lambda _checked=False: self._open_menu(QCursor.pos()))
        layout.addWidget(more, 0, Qt.AlignmentFlag.AlignVCenter)

        for child in self.findChildren(QWidget):
            if child is not more:
                child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.openRequested.emit(self.project.id)
        event.accept()

    def contextMenuEvent(self, event):
        self._open_menu(event.globalPos())

    def _open_menu(self, pos: QPoint) -> None:
        pid = self.project.id
        menu = RoundMenu(parent=self)
        menu.addAction(make_action("Ouvrir le Kanban", lambda: self.openRequested.emit(pid), FIF.LAYOUT, menu))
        menu.addAction(make_action("Modifier", lambda: self.editRequested.emit(pid), FIF.EDIT, menu))
        menu.addSeparator()
        menu.addAction(make_action("Supprimer", lambda: self.deleteRequested.emit(pid), FIF.DELETE, menu))
        menu.exec(pos)


class ProjectsPage(PageBase):
    openRequested = Signal(int)

    def __init__(self, repo: Repository, parent: QWidget | None = None):
        super().__init__("projectsPage", parent)
        self.repo = repo
        self._status_choices: list[ProjectStatus | None] = [None, *ProjectStatus]

        self.header = PageHeader("Projets")
        new_button = PrimaryPushButton("Nouveau projet", self, FIF.ADD)
        new_button.clicked.connect(lambda _checked=False: self.new_project())
        self.header.add_action(new_button)
        self.vbox.addWidget(self.header)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        self.search = SearchLineEdit(self)
        self.search.setPlaceholderText("Rechercher un projet")
        self.search.setFixedWidth(280)
        self.search.textChanged.connect(lambda *_: self.refresh())
        self.status_box = ComboBox(self)
        self.status_box.setFixedWidth(180)
        self.status_box.addItem("Tous les statuts")
        for status in ProjectStatus:
            self.status_box.addItem(status.label)
        self.status_box.currentIndexChanged.connect(lambda *_: self.refresh())
        toolbar.addWidget(self.search)
        toolbar.addWidget(self.status_box)
        toolbar.addStretch(1)
        self.vbox.addLayout(toolbar)

        self.list_host = QWidget()
        self.list_layout = QVBoxLayout(self.list_host)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(12)
        self.vbox.addWidget(self.list_host)
        self.vbox.addStretch(1)

        self.repo.changed.connect(self._schedule_refresh)
        self.refresh()

    def refresh(self) -> None:
        projects = self.repo.list_projects()
        tasks = self.repo.list_tasks()
        members = {m.id: m for m in self.repo.list_members()}
        active = sum(1 for p in projects if p.status is ProjectStatus.ACTIVE)
        self.header.set_subtitle(
            f"{plural(active, 'projet en cours', 'projets en cours')}, {plural(len(projects), 'projet au total', 'projets au total')}.")

        status = self._status_choices[self.status_box.currentIndex()]
        query = self.search.text().strip().lower()
        visible = [p for p in projects
                   if (status is None or p.status is status)
                   and (not query or query in p.name.lower() or query in p.description.lower())]

        clear_layout(self.list_layout)
        if not projects:
            empty = EmptyState(FIF.FOLDER, "Aucun projet pour le moment",
                               "Créez un projet pour regrouper vos tâches et suivre son avancement.",
                               "Nouveau projet", parent=self.list_host)
            empty.button.clicked.connect(lambda _checked=False: self.new_project())
            self.list_layout.addWidget(empty)
            return
        if not visible:
            self.list_layout.addWidget(muted_label("Aucun projet ne correspond à votre recherche.", self.list_host))
            return

        for project in visible:
            mine = [t for t in tasks if t.project_id == project.id]
            done = sum(1 for t in mine if t.is_done)
            people: list[Member] = []
            for task in mine:
                member = members.get(task.assignee_id) if task.assignee_id is not None else None
                if member is not None and member not in people:
                    people.append(member)
            row = ProjectRow(project, len(mine), done, people, self.list_host)
            row.openRequested.connect(self.openRequested)
            row.editRequested.connect(self.edit_project)
            row.deleteRequested.connect(self.delete_project)
            self.list_layout.addWidget(row)

    # ----- actions ---------------------------------------------------------
    def new_project(self) -> None:
        dialog = ProjectDialog(self.window())
        if dialog.exec() and dialog.validate():
            project = self.repo.save_project(dialog.build_project())
            notify(self.window(), "Projet créé", f"« {project.name} » est prêt. Ajoutez-y des tâches.")

    def edit_project(self, project_id: int) -> None:
        project = self.repo.get_project(project_id)
        if project is None:
            return
        dialog = ProjectDialog(self.window(), project)
        if dialog.exec() and dialog.validate():
            self.repo.save_project(dialog.build_project())

    def delete_project(self, project_id: int) -> None:
        project = self.repo.get_project(project_id)
        if project is None:
            return
        box = MessageBox("Supprimer le projet ?",
                         f"« {project.name} » et toutes ses tâches seront supprimés définitivement.",
                         self.window())
        box.yesButton.setText("Supprimer")
        box.cancelButton.setText("Annuler")
        if box.exec():
            self.repo.delete_project(project_id)
