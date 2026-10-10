"""Page équipe : membres, charge de travail et gestion des membres."""
from __future__ import annotations

from PySide6.QtCore import QSize, QTimer, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidgetItem, QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon as FIF, MessageBox, PrimaryPushButton, RoundMenu, TableWidget

from ...models import ACCENT_PALETTE, Member
from ...repository import Repository
from ...utils import plural
from ..common import PageHeader, make_action
from ..dialogs import MemberDialog
from ..widgets import avatar_icon

COLUMNS = ["Membre", "Rôle", "Tâches ouvertes", "Tâches terminées", "En retard"]


def _fallback_color(index: int) -> str:
    """Couleur générée quand la palette est épuisée (B12)."""
    return QColor.fromHsl((index * 67) % 360, 120, 140).name()


class TeamPage(QWidget):
    def __init__(self, repo: Repository, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("teamPage")
        self.repo = repo
        self._members: list[Member] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 28, 36, 24)
        root.setSpacing(16)

        self.header = PageHeader("Équipe")
        add_button = PrimaryPushButton("Ajouter un membre", self, FIF.ADD)
        add_button.clicked.connect(lambda _checked=False: self.new_member())
        self.header.add_action(add_button)
        root.addWidget(self.header)

        self.table = TableWidget(self)
        self.table.setColumnCount(len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.verticalHeader().hide()
        self.table.setIconSize(QSize(28, 28))
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for column in range(2, len(COLUMNS)):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_menu)
        self.table.cellDoubleClicked.connect(lambda row, _column: self._edit_row(row))
        root.addWidget(self.table, 1)

        self.repo.changed.connect(self._schedule_refresh)
        self.refresh()

    def refresh(self) -> None:
        self._members = self.repo.list_members()
        tasks = self.repo.list_tasks()
        self.header.set_subtitle(plural(len(self._members), "membre dans l'équipe", "membres dans l'équipe") + ".")
        self.table.setRowCount(len(self._members))
        for row, member in enumerate(self._members):
            mine = [t for t in tasks if t.assignee_id == member.id]
            open_tasks = [t for t in mine if not t.is_done]
            values = [
                member.name,
                member.role or "—",
                str(len(open_tasks)),
                str(len(mine) - len(open_tasks)),
                str(sum(1 for t in open_tasks if t.is_overdue())),
            ]
            for column, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, member.id)
                if column == 0:
                    item.setIcon(avatar_icon(member.name, member.color, 28))
                self.table.setItem(row, column, item)
        self.table.resizeRowsToContents()

    def _schedule_refresh(self, *_args) -> None:
        QTimer.singleShot(0, self.refresh)

    # ----- actions ---------------------------------------------------------
    def new_member(self) -> None:
        used = {m.color for m in self._members}
        free = [c for c in ACCENT_PALETTE if c not in used]
        # B12 : couleur générée si la palette est épuisée (évite le doublon)
        default = free[0] if free else _fallback_color(len(self._members))
        dialog = MemberDialog(self.window(), default_color=default)
        if dialog.exec() and dialog.validate():
            self.repo.save_member(dialog.build_member())

    def _edit_row(self, row: int) -> None:
        if not (0 <= row < len(self._members)):
            return
        member = self._members[row]
        dialog = MemberDialog(self.window(), member=member)
        if dialog.exec() and dialog.validate():
            self.repo.save_member(dialog.build_member())

    def _delete(self, member_id: int) -> None:
        member = next((m for m in self._members if m.id == member_id), None)
        if member is None:
            return
        box = MessageBox("Supprimer ce membre ?",
                         f"{member.name} ne sera plus assigné à ses tâches. Les tâches sont conservées.",
                         self.window())
        box.yesButton.setText("Supprimer")
        box.cancelButton.setText("Annuler")
        if box.exec():
            self.repo.delete_member(member_id)

    def _show_menu(self, pos) -> None:
        row = self.table.rowAt(pos.y())
        if not (0 <= row < len(self._members)):
            return
        mid = self._members[row].id
        menu = RoundMenu(parent=self)
        menu.addAction(make_action("Modifier", lambda: self._edit_row(row), FIF.EDIT, menu))
        menu.addSeparator()
        menu.addAction(make_action("Supprimer", lambda: self._delete(mid), FIF.DELETE, menu))
        menu.exec(self.table.viewport().mapToGlobal(pos))
