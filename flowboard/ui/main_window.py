"""Fenêtre principale : navigation Fluent, effet Mica et rafraîchissement au changement de thème."""
from __future__ import annotations

from qfluentwidgets import FluentIcon as FIF, FluentWindow, NavigationItemPosition, qconfig

from .. import APP_NAME
from ..repository import Repository
from ..settings import cfg
from .pages.board import BoardPage
from .pages.dashboard import DashboardPage
from .pages.projects import ProjectsPage
from .pages.settings import SettingsPage
from .pages.tasks import TasksPage
from .pages.team import TeamPage


class MainWindow(FluentWindow):
    def __init__(self, repo: Repository):
        super().__init__()
        self.repo = repo
        self.setWindowTitle(APP_NAME)
        self.resize(1320, 860)
        self.setMinimumSize(1080, 720)

        self.dashboard = DashboardPage(repo, self)
        self.projects = ProjectsPage(repo, self)
        self.board = BoardPage(repo, self)
        self.tasks = TasksPage(repo, self)
        self.team = TeamPage(repo, self)
        self.settings = SettingsPage(repo, self)

        self.addSubInterface(self.dashboard, FIF.HOME, "Tableau de bord")
        self.addSubInterface(self.projects, FIF.FOLDER, "Projets")
        self.addSubInterface(self.board, FIF.LAYOUT, "Kanban")
        self.addSubInterface(self.tasks, FIF.CHECKBOX, "Tâches")
        self.addSubInterface(self.team, FIF.PEOPLE, "Équipe")
        self.addSubInterface(self.settings, FIF.SETTING, "Paramètres", NavigationItemPosition.BOTTOM)

        self.projects.openRequested.connect(self.open_board)
        cfg.micaEnabled.valueChanged.connect(self.setMicaEffectEnabled)
        self.setMicaEffectEnabled(cfg.get(cfg.micaEnabled))
        qconfig.themeChanged.connect(self._on_appearance_changed)
        qconfig.themeColorChanged.connect(self._on_appearance_changed)
        self.switchTo(self.dashboard)

    def open_board(self, project_id: int) -> None:
        self.board.set_project(project_id)
        self.switchTo(self.board)

    def _on_appearance_changed(self, *_args) -> None:
        # Le Mica doit connaître le mode courant ; les pages reconstruisent leurs couleurs peintes
        self.setMicaEffectEnabled(cfg.get(cfg.micaEnabled))
        for page in (self.dashboard, self.projects, self.board, self.tasks, self.team):
            page.refresh()
