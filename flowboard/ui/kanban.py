"""Tableau Kanban : colonnes par statut, cartes glissables et menus contextuels."""
from __future__ import annotations

from PySide6.QtCore import QMimeData, QPoint, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QDrag, QPainter
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (CaptionLabel, CheckBox, FluentIcon as FIF, ProgressBar, RoundMenu,
                            ScrollArea, SingleDirectionScrollArea, StrongBodyLabel,
                            TransparentToolButton, themeColor)

from ..models import Member, Priority, Task, TaskStatus
from ..utils import format_date, relative_due
from .common import make_action, transparent_scroll
from .widgets import Avatar, Pill, Surface, danger_color

TASK_MIME = "application/x-flowboard-task"

HINTS = {
    TaskStatus.TODO: "Aucune tâche à démarrer. Créez-en une avec le bouton +.",
    TaskStatus.IN_PROGRESS: "Rien n'est en cours. Glissez une tâche ici pour la démarrer.",
    TaskStatus.REVIEW: "Aucune tâche en attente de relecture.",
    TaskStatus.DONE: "Les tâches terminées apparaissent ici.",
}


def _dragged_task_id(event) -> int | None:
    """Identifiant de la tâche glissée, lu depuis les données MIME."""
    raw = event.mimeData().data(TASK_MIME)
    text = raw.data().decode("utf-8", errors="ignore") if not raw.isEmpty() else ""
    return int(text) if text.isdigit() else None


class TaskCard(Surface):
    """Carte de tâche : glisser pour déplacer, double-clic pour modifier, clic droit pour le menu."""

    editRequested = Signal(int)
    deleteRequested = Signal(int)
    moveRequested = Signal(int, object)
    subtaskToggled = Signal(int, bool)
    toggleDoneRequested = Signal(int)

    def __init__(self, task: Task, member: Member | None, parent: QWidget | None = None):
        super().__init__(parent, variant="task", radius=6)
        self.task = task
        self._press_pos: QPoint | None = None
        self._subtask_checks: list[CheckBox] = []
        if task.priority >= Priority.HIGH:
            self.accent_left = QColor(task.priority.color)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 12, 10)
        root.setSpacing(7)

        title = StrongBodyLabel(task.title, self)
        title.setWordWrap(True)
        root.addWidget(title)

        if task.tags:
            root.addWidget(CaptionLabel("   ".join(f"#{tag}" for tag in task.tags[:3]), self))

        if task.subtasks:
            done = sum(1 for s in task.subtasks if s.done)
            row = QHBoxLayout()
            row.setSpacing(8)
            bar = ProgressBar(self)
            bar.setFixedHeight(4)
            bar.setValue(round(task.progress * 100))
            row.addWidget(bar, 1)
            row.addWidget(CaptionLabel(f"{done}/{len(task.subtasks)}", self))
            root.addLayout(row)
            for sub in task.subtasks:
                check = CheckBox(sub.title, self)
                check.setChecked(sub.done)
                check.setFixedHeight(24)
                self._subtask_checks.append(check)
                check.toggled.connect(
                    lambda _checked, sid=sub.id: self._on_subtask_toggled(sid, _checked))
                root.addWidget(check)

        footer = QHBoxLayout()
        footer.setSpacing(8)
        if task.priority >= Priority.HIGH:
            footer.addWidget(Pill(task.priority.label, task.priority.color, self))
        if task.due_date:
            text = format_date(task.due_date) if task.is_done else relative_due(task.due_date)
            due = CaptionLabel(text, self)
            if task.is_overdue():
                due.setTextColor(danger_color(), danger_color())
            footer.addWidget(due)
        footer.addStretch(1)
        if member is not None:
            footer.addWidget(Avatar(member.name, member.color, 22, self))
        root.addLayout(footer)

        # Les enfants laissent passer les clics vers la carte (glisser-déposer fiable),
        # sauf les cases à cocher de sous-tâches qui restent interactives
        interactive = {id(c) for c in self._subtask_checks}
        for check in self._subtask_checks:
            interactive.update(id(d) for d in check.findChildren(QWidget))
        for child in self.findChildren(QWidget):
            if id(child) not in interactive:
                child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def _on_subtask_toggled(self, subtask_id: int | None, done: bool) -> None:
        if subtask_id is not None:
            self.subtaskToggled.emit(subtask_id, done)

    # ----- interactions ----------------------------------------------------
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.position().toPoint()
        event.accept()

    def mouseReleaseEvent(self, event):
        self._press_pos = None
        event.accept()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.editRequested.emit(self.task.id)
        event.accept()

    def mouseMoveEvent(self, event):
        if self._press_pos is None or not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        if (event.position().toPoint() - self._press_pos).manhattanLength() < QApplication.startDragDistance():
            return
        self._start_drag()

    def _start_drag(self) -> None:
        hot_spot = self._press_pos if self._press_pos is not None else QPoint(20, 20)
        self._press_pos = None
        mime = QMimeData()
        mime.setData(TASK_MIME, str(self.task.id).encode("utf-8"))
        pixmap = self.grab()
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.setPixmap(pixmap)
        drag.setHotSpot(hot_spot)
        drag.exec(Qt.DropAction.MoveAction)

    def contextMenuEvent(self, event):
        tid = self.task.id
        menu = RoundMenu(parent=self)
        menu.addAction(make_action("Modifier", lambda: self.editRequested.emit(tid), FIF.EDIT, menu))
        done_label = ("Rouvrir la tâche" if self.task.status is TaskStatus.DONE
                      else "Marquer comme terminée")
        menu.addAction(make_action(done_label,
                                   lambda: self.toggleDoneRequested.emit(tid), FIF.ACCEPT, menu))
        move = RoundMenu("Déplacer vers", menu)
        for status in TaskStatus:
            if status is not self.task.status:
                move.addAction(make_action(
                    status.label, lambda s=status: self.moveRequested.emit(tid, s), None, move))
        menu.addMenu(move)
        menu.addSeparator()
        menu.addAction(make_action("Supprimer", lambda: self.deleteRequested.emit(tid), FIF.DELETE, menu))
        menu.exec(event.globalPos())


class _Indicator(QWidget):
    """Repère horizontal qui indique où la carte sera insérée."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setFixedHeight(3)
        self.hide()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(themeColor())
        painter.drawRoundedRect(QRectF(self.rect()), 1.5, 1.5)
        painter.end()


class _DropZone(QWidget):
    """Liste verticale des cartes d'une colonne. Calcule la position d'insertion au dépôt."""

    def __init__(self, column: "KanbanColumn"):
        super().__init__()
        self.column = column
        self.cards: list[TaskCard] = []
        self.setAcceptDrops(True)
        self.vbox = QVBoxLayout(self)
        self.vbox.setContentsMargins(8, 4, 8, 12)
        self.vbox.setSpacing(8)
        self.hint = CaptionLabel("", self)
        self.hint.setWordWrap(True)
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint.setContentsMargins(12, 28, 12, 0)
        self.hint.hide()
        self.vbox.addWidget(self.hint)
        self.vbox.addStretch(1)
        self._indicator = _Indicator(self)

    def clear(self) -> None:
        for card in self.cards:
            self.vbox.removeWidget(card)
            card.deleteLater()
        self.cards = []

    def add_card(self, card: TaskCard) -> None:
        self.cards.append(card)
        self.vbox.insertWidget(self.vbox.count() - 1, card)

    def set_hint(self, text: str) -> None:
        self.hint.setText(text)
        self.hint.setVisible(bool(text))

    # ----- calcul de la position ------------------------------------------
    def _slot_for(self, y: float, dragged_id: int | None) -> tuple[int, list[TaskCard]]:
        others = [c for c in self.cards if c.task.id != dragged_id]
        for index, card in enumerate(others):
            if y < card.geometry().center().y():
                return index, others
        return len(others), others

    def _show_indicator(self, slot: int, others: list[TaskCard]) -> None:
        gap = self.vbox.spacing()
        if not others:
            y = 6
        elif slot < len(others):
            y = others[slot].geometry().top() - gap // 2 - 1
        else:
            y = others[-1].geometry().bottom() + gap // 2 + 1
        self._indicator.setGeometry(10, max(0, y), max(0, self.width() - 20), 3)
        self._indicator.show()
        self._indicator.raise_()

    def _hide_indicator(self) -> None:
        self._indicator.hide()
        self.column.set_highlight(False)

    # ----- événements de glisser-déposer ----------------------------------
    def dragEnterEvent(self, event):
        if _dragged_task_id(event) is None:
            event.ignore()
            return
        event.acceptProposedAction()
        self.column.set_highlight(True)

    def dragMoveEvent(self, event):
        dragged = _dragged_task_id(event)
        if dragged is None:
            event.ignore()
            return
        event.acceptProposedAction()
        slot, others = self._slot_for(event.position().y(), dragged)
        self._show_indicator(slot, others)

    def dragLeaveEvent(self, event):
        self._hide_indicator()

    def dropEvent(self, event):
        dragged = _dragged_task_id(event)
        if dragged is None:
            event.ignore()
            return
        slot, others = self._slot_for(event.position().y(), dragged)
        ordered = [c.task.id for c in others]
        ordered.insert(slot, dragged)
        self._hide_indicator()
        event.acceptProposedAction()
        self.column.board.taskDropped.emit(dragged, self.column.status, ordered)


class KanbanColumn(Surface):
    """Colonne d'un statut : en-tête, compteur, ajout rapide et liste de cartes."""

    def __init__(self, status: TaskStatus, board: "KanbanBoard"):
        super().__init__(None, variant="column", radius=8)
        self.status = status
        self.board = board
        self.accent_top = QColor(status.color)
        self.setMinimumWidth(240)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 10, 10)
        root.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(8)
        self.title = StrongBodyLabel(status.label, self)
        self.count = CaptionLabel("0", self)
        self.add_button = TransparentToolButton(FIF.ADD, self)
        self.add_button.setToolTip(f"Ajouter une tâche « {status.label} »")
        self.add_button.clicked.connect(lambda _checked=False: board.addRequested.emit(status))
        header.addWidget(self.title)
        header.addWidget(self.count)
        header.addStretch(1)
        header.addWidget(self.add_button)
        root.addLayout(header)

        self.scroll = SingleDirectionScrollArea(self, orient=Qt.Orientation.Vertical)
        self.zone = _DropZone(self)
        self.scroll.setWidget(self.zone)
        self.scroll.setWidgetResizable(True)
        transparent_scroll(self.scroll)
        root.addWidget(self.scroll, 1)

    def set_highlight(self, on: bool) -> None:
        self.highlight = QColor(themeColor()) if on else None
        self.update()

    def set_tasks(self, tasks: list[Task], members: dict[int, Member]) -> None:
        self.zone.clear()
        for task in tasks:
            member = members.get(task.assignee_id) if task.assignee_id is not None else None
            card = TaskCard(task, member, self.zone)
            card.editRequested.connect(self.board.editRequested)
            card.deleteRequested.connect(self.board.deleteRequested)
            card.moveRequested.connect(self.board.moveRequested)
            card.subtaskToggled.connect(self.board.subtaskToggled)
            card.toggleDoneRequested.connect(self.board.toggleDoneRequested)
            self.zone.add_card(card)
        self.count.setText(str(len(tasks)))
        self.zone.set_hint("" if tasks else HINTS[self.status])


class KanbanBoard(ScrollArea):
    """Tableau horizontal : une colonne par statut."""

    addRequested = Signal(object)
    editRequested = Signal(int)
    deleteRequested = Signal(int)
    moveRequested = Signal(int, object)
    taskDropped = Signal(int, object, object)
    subtaskToggled = Signal(int, bool)
    toggleDoneRequested = Signal(int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("kanbanBoard")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        container = QWidget()
        self.hbox = QHBoxLayout(container)
        self.hbox.setContentsMargins(0, 0, 0, 0)
        self.hbox.setSpacing(14)
        self.columns: dict[TaskStatus, KanbanColumn] = {}
        for status in TaskStatus:
            column = KanbanColumn(status, self)
            self.columns[status] = column
            self.hbox.addWidget(column, 1)
        self.setWidget(container)
        transparent_scroll(self)

    def set_tasks(self, tasks: list[Task], members: dict[int, Member]) -> None:
        grouped: dict[TaskStatus, list[Task]] = {status: [] for status in TaskStatus}
        for task in tasks:
            grouped[task.status].append(task)
        for status, column in self.columns.items():
            column.set_tasks(grouped[status], members)
