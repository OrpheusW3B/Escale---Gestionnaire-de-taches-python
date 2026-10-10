"""Primitives visuelles peintes à la main, adaptées aux thèmes clair et sombre."""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QFrame, QLabel, QWidget
from qfluentwidgets import isDarkTheme

from ..utils import initials, readable_on


def is_dark() -> bool:
    return isDarkTheme()


def secondary_color() -> QColor:
    return QColor(190, 190, 190) if is_dark() else QColor(96, 94, 92)


def text_color() -> QColor:
    return QColor(255, 255, 255) if is_dark() else QColor(27, 27, 27)


def danger_color() -> QColor:
    return QColor("#FF99A4") if is_dark() else QColor("#C42B1C")


def tone(color: str) -> str:
    """Version lisible d'une couleur d'accent sur le thème courant."""
    c = QColor(color)
    return c.lighter(135).name() if is_dark() else c.name()


def alpha(color: str, value: int) -> str:
    c = QColor(color)
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {value})"


class Surface(QFrame):
    """Panneau translucide peint à la main : laisse passer le Mica et suit le thème."""

    def __init__(self, parent: QWidget | None = None, variant: str = "card", radius: int = 8):
        super().__init__(parent)
        self.variant = variant
        self.radius = radius
        self.accent_left: QColor | None = None
        self.accent_top: QColor | None = None
        self.highlight: QColor | None = None
        self._hovered = False

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def _colors(self) -> tuple[QColor, QColor]:
        dark = is_dark()
        hover = self._hovered and self.variant in ("task", "row")
        if self.variant == "column":
            return (QColor(255, 255, 255, 12) if dark else QColor(0, 0, 0, 9)), QColor(0, 0, 0, 0)
        if self.variant == "task":
            if dark:
                return QColor(255, 255, 255, 36 if hover else 24), QColor(255, 255, 255, 30)
            return QColor(255, 255, 255, 255 if hover else 242), QColor(0, 0, 0, 30)
        if self.variant == "row":
            if dark:
                return QColor(255, 255, 255, 26 if hover else 14), QColor(255, 255, 255, 22)
            return QColor(255, 255, 255, 235 if hover else 200), QColor(0, 0, 0, 22)
        if dark:
            return QColor(255, 255, 255, 14), QColor(255, 255, 255, 22)
        return QColor(255, 255, 255, 190), QColor(0, 0, 0, 20)

    def paintEvent(self, event):
        fill, border = self._colors()
        if self.highlight is not None:
            border = QColor(self.highlight)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, self.radius, self.radius)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillPath(path, fill)
        if self.accent_left is not None or self.accent_top is not None:
            painter.save()
            painter.setClipPath(path)
            if self.accent_left is not None:
                painter.fillRect(QRectF(rect.left(), rect.top(), 3, rect.height()), self.accent_left)
            if self.accent_top is not None:
                painter.fillRect(QRectF(rect.left(), rect.top(), rect.width(), 3), self.accent_top)
            painter.restore()
        if border.alpha() > 0:
            painter.setPen(QPen(QBrush(border), 2 if self.highlight is not None else 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)
        painter.end()


class Pill(QLabel):
    """Étiquette colorée discrète (statut, priorité)."""

    def __init__(self, text: str, color: str, parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            f"QLabel {{ color: {tone(color)}; background-color: {alpha(color, 44 if is_dark() else 30)};"
            " border-radius: 9px; padding: 2px 9px; font-size: 12px; font-weight: 600; }"
        )


def _paint_avatar(painter: QPainter, rect: QRectF, name: str, color: str,
                  ring: QColor | None = None) -> None:
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QBrush(ring), 2) if ring is not None else Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color))
    painter.drawEllipse(rect)
    font = QFont(painter.font())
    font.setPixelSize(max(9, int(rect.height() * 0.42)))
    font.setWeight(QFont.Weight.DemiBold)
    painter.setFont(font)
    painter.setPen(readable_on(color))
    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, initials(name))
    painter.restore()


class Avatar(QWidget):
    """Pastille de membre avec initiales."""

    def __init__(self, name: str, color: str, size: int = 24, parent: QWidget | None = None):
        super().__init__(parent)
        self.name = name
        self.color = color
        self.setFixedSize(size, size)
        self.setToolTip(name)

    def paintEvent(self, event):
        painter = QPainter(self)
        _paint_avatar(painter, QRectF(0.5, 0.5, self.width() - 1, self.height() - 1), self.name, self.color)
        painter.end()


def avatar_icon(name: str, color: str, size: int = 26) -> QIcon:
    """Avatar sous forme d'icône, pour les cellules de tableau."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    _paint_avatar(painter, QRectF(0, 0, size, size), name, color)
    painter.end()
    return QIcon(pixmap)


class AvatarStack(QWidget):
    """Avatars superposés, pour les membres d'un projet."""

    def __init__(self, people: list[tuple[str, str]], size: int = 24, parent: QWidget | None = None):
        super().__init__(parent)
        self._people = people[:4]
        self._extra = len(people) - len(self._people)
        self._size = size
        self._step = size + 4  # sans chevauchement : initiales toujours lisibles
        width = size + max(0, len(self._people) - 1) * self._step if self._people else 0
        if self._extra:
            width += self._step  # B10 : badge « +N »
        self.setFixedSize(max(width, 1), size)

    def paintEvent(self, event):
        painter = QPainter(self)
        ring = QColor(32, 32, 32) if is_dark() else QColor(255, 255, 255)
        for index, (name, color) in enumerate(self._people):
            rect = QRectF(index * self._step, 0, self._size, self._size).adjusted(1, 1, -1, -1)
            _paint_avatar(painter, rect, name, color, ring)
        if self._extra:
            # B10 : badge « +N » à la suite des avatars
            rect = QRectF(len(self._people) * self._step, 0, self._size, self._size).adjusted(1, 1, -1, -1)
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(120, 120, 120, 200))
            painter.drawEllipse(rect)
            font = QFont(painter.font())
            font.setPixelSize(max(8, int(self._size * 0.38)))
            font.setWeight(QFont.Weight.DemiBold)
            painter.setFont(font)
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"+{self._extra}")
            painter.restore()
        painter.end()


class ColorDot(QWidget):
    """Point coloré (priorité, statut, projet)."""

    def __init__(self, color: str, size: int = 10, parent: QWidget | None = None):
        super().__init__(parent)
        self._color = QColor(color)
        self.setFixedSize(size, size)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._color)
        painter.drawEllipse(QRectF(0, 0, self.width(), self.height()))
        painter.end()


class Divider(QWidget):
    """Filet fin horizontal ou vertical."""

    def __init__(self, horizontal: bool = True, parent: QWidget | None = None):
        super().__init__(parent)
        if horizontal:
            self.setFixedHeight(1)
        else:
            self.setFixedWidth(1)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(255, 255, 255, 30) if is_dark() else QColor(0, 0, 0, 20))
        painter.end()


class DonutChart(QWidget):
    """Graphique en anneau avec valeur centrale."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._segments: list[tuple[QColor, int]] = []
        self._center = ("", "")
        self.setMinimumSize(150, 150)

    def set_data(self, segments: list[tuple[str, int]], center_value: str, center_label: str) -> None:
        self._segments = [(QColor(color), value) for color, value in segments if value > 0]
        self._center = (center_value, center_label)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        side = min(self.width(), self.height())
        thick = max(10.0, side * 0.12)
        x = (self.width() - side) / 2 + thick / 2
        y = (self.height() - side) / 2 + thick / 2
        rect = QRectF(x, y, side - thick, side - thick)
        track = QColor(255, 255, 255, 26) if is_dark() else QColor(0, 0, 0, 18)
        painter.setPen(QPen(QBrush(track), thick))
        painter.drawEllipse(rect)
        total = sum(value for _, value in self._segments)
        start = 90 * 16
        for color, value in self._segments:
            span = int(360 * 16 * value / total)
            painter.setPen(QPen(QBrush(color), thick))
            painter.drawArc(rect, start, -span)
            start -= span
        center_value, center_label = self._center
        font = QFont(painter.font())
        font.setPixelSize(max(12, int(side * 0.2)))
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(text_color())
        painter.drawText(QRectF(0, self.height() / 2 - side * 0.27, self.width(), side * 0.3),
                         Qt.AlignmentFlag.AlignCenter, center_value)
        font.setPixelSize(max(10, int(side * 0.08)))
        font.setWeight(QFont.Weight.Normal)
        painter.setFont(font)
        painter.setPen(secondary_color())
        painter.drawText(QRectF(0, self.height() / 2 + side * 0.06, self.width(), side * 0.14),
                         Qt.AlignmentFlag.AlignCenter, center_label)
        painter.end()
