"""Mise en page partagée : pages défilantes, en-têtes, états vides, sélecteur de couleur."""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QBrush, QColor, QIcon, QPainter, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLayout, QScrollArea, QVBoxLayout, QWidget
from qfluentwidgets import (BodyLabel, FluentIcon as FIF, IconWidget, InfoBar, InfoBarPosition,
                            PrimaryPushButton, ScrollArea, SubtitleLabel, TitleLabel)

from .widgets import Surface, secondary_color, text_color


def transparent_scroll(area: QScrollArea) -> None:
    """Rend une zone de défilement transparente pour laisser voir le Mica."""
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setStyleSheet("QScrollArea { background: transparent; border: none; }")
    area.viewport().setAutoFillBackground(False)
    if area.widget() is not None:
        area.widget().setStyleSheet("QWidget { background: transparent; }")


def make_action(text: str, callback: Callable[[], None], icon: object | None = None,
                parent: QWidget | None = None) -> QAction:
    """Action de menu contextuel avec icône Fluent optionnelle."""
    action = QAction(icon.icon() if icon is not None else QIcon(), text, parent)
    action.triggered.connect(lambda _checked=False: callback())
    return action


def notify(parent: QWidget, title: str, content: str, error: bool = False) -> None:
    """Affiche une notification discrète en haut à droite."""
    show = InfoBar.error if error else InfoBar.success
    show(title=title, content=content, orient=Qt.Orientation.Horizontal, isClosable=True,
         duration=2500, position=InfoBarPosition.TOP_RIGHT, parent=parent)


def clear_layout(layout: QLayout) -> None:
    """Supprime tous les éléments d'un layout (widgets libérés de façon différée)."""
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
        elif item.layout() is not None:
            clear_layout(item.layout())


def make_panel(title: str, parent: QWidget | None = None) -> tuple[Surface, QVBoxLayout]:
    """Panneau avec titre ; retourne la surface et le layout où ajouter le contenu."""
    panel = Surface(parent, variant="card", radius=8)
    outer = QVBoxLayout(panel)
    outer.setContentsMargins(20, 18, 20, 20)
    outer.setSpacing(14)
    outer.addWidget(BodyLabel(title, panel))
    body = QVBoxLayout()
    body.setSpacing(10)
    outer.addLayout(body)
    outer.addStretch(1)
    return panel, body


def muted_label(text: str, parent: QWidget | None = None) -> BodyLabel:
    label = BodyLabel(text, parent)
    label.setWordWrap(True)
    label.setTextColor(secondary_color(), secondary_color())
    return label


class PageHeader(QWidget):
    """Titre de page, sous-titre et actions alignées à droite."""

    def __init__(self, title: str, subtitle: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.row = QHBoxLayout(self)
        self.row.setContentsMargins(0, 0, 0, 0)
        self.row.setSpacing(12)
        texts = QVBoxLayout()
        texts.setSpacing(4)
        texts.addWidget(TitleLabel(title, self))
        self.subtitleLabel = muted_label(subtitle, self)
        texts.addWidget(self.subtitleLabel)
        self.row.addLayout(texts, 1)

    def add_action(self, widget: QWidget) -> None:
        self.row.addWidget(widget, 0, Qt.AlignmentFlag.AlignBottom)

    def set_subtitle(self, text: str) -> None:
        self.subtitleLabel.setText(text)


class EmptyState(QWidget):
    """État vide : explique la situation et invite à agir."""

    def __init__(self, icon: object, title: str, text: str, action_text: str | None = None,
                 parent: QWidget | None = None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.addStretch(1)
        icon_widget = IconWidget(icon, self)
        icon_widget.setFixedSize(40, 40)
        root.addWidget(icon_widget, 0, Qt.AlignmentFlag.AlignHCenter)
        root.addWidget(SubtitleLabel(title, self), 0, Qt.AlignmentFlag.AlignHCenter)
        body = muted_label(text, self)
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.setMaximumWidth(420)
        root.addWidget(body, 0, Qt.AlignmentFlag.AlignHCenter)
        self.button: PrimaryPushButton | None = None
        if action_text:
            root.addSpacing(8)
            self.button = PrimaryPushButton(action_text, self, FIF.ADD)
            root.addWidget(self.button, 0, Qt.AlignmentFlag.AlignHCenter)
        root.addStretch(1)


class PageBase(ScrollArea):
    """Page défilante : contenu centré, largeur maximale, fond transparent."""

    def __init__(self, object_name: str, parent: QWidget | None = None, max_width: int = 1120):
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        outer = QHBoxLayout(body)
        outer.setContentsMargins(36, 28, 36, 36)
        outer.addStretch(1)
        self.content = QWidget(body)
        self.content.setMaximumWidth(max_width)
        self.vbox = QVBoxLayout(self.content)
        self.vbox.setContentsMargins(0, 0, 0, 0)
        self.vbox.setSpacing(20)
        outer.addWidget(self.content, 10)
        outer.addStretch(1)
        self.setWidget(body)
        transparent_scroll(self)

    def refresh(self) -> None:
        """Recharge le contenu de la page (à redéfinir)."""

    def _schedule_refresh(self, *_args) -> None:
        # Différé : évite de détruire des widgets pendant un glisser-déposer ou un événement en cours
        QTimer.singleShot(0, self.refresh)


class ColorPicker(QWidget):
    """Rangée de pastilles de couleur sélectionnables."""

    colorChanged = Signal(str)
    SIZE = 22
    GAP = 10

    def __init__(self, colors: list[str], current: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._colors = list(colors)
        self._current = current if current in self._colors else self._colors[0]
        self.setFixedSize(len(self._colors) * (self.SIZE + self.GAP) - self.GAP + 4, self.SIZE + 4)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def color(self) -> str:
        return self._current

    def _slot_x(self, index: int) -> float:
        return 2 + index * (self.SIZE + self.GAP)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        for index, color in enumerate(self._colors):
            x = self._slot_x(index)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(color))
            painter.drawEllipse(QRectF(x + 4, 6, self.SIZE - 8, self.SIZE - 8))
            if color == self._current:
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(QBrush(text_color()), 2))
                painter.drawEllipse(QRectF(x + 1, 3, self.SIZE - 2, self.SIZE - 2))
        painter.end()

    def mousePressEvent(self, event):
        x = event.position().x()
        for index, color in enumerate(self._colors):
            start = self._slot_x(index)
            if start <= x <= start + self.SIZE:
                if color != self._current:
                    self._current = color
                    self.update()
                    self.colorChanged.emit(color)
                break
        event.accept()
