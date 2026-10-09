"""Tableau de bord : indicateurs clés, échéances, répartition, avancement et charge de l'équipe."""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, CaptionLabel, LargeTitleLabel, ProgressBar

from ...models import Member, Project, ProjectStatus, Task, TaskStatus
from ...repository import Repository
from ...utils import format_long_date, plural, relative_due
from ..common import PageBase, PageHeader, clear_layout, make_panel, muted_label
from ..widgets import Avatar, ColorDot, Divider, DonutChart, Surface, danger_color, text_color


class _Metric(QWidget):
    def __init__(self, caption: str, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 14, 22, 14)
        layout.setSpacing(2)
        self.value = LargeTitleLabel("0", self)
        self.caption = CaptionLabel(caption, self)
        layout.addWidget(self.value)
        layout.addWidget(self.caption)

    def set_value(self, text: str, alert: bool = False) -> None:
        self.value.setText(text)
        if alert:
            self.value.setTextColor(danger_color(), danger_color())
        else:
            self.value.setTextColor(text_color(), text_color())


def _legend_row(color: str, label: str, value: int) -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)
    layout.addWidget(ColorDot(color, 10, row))
    layout.addWidget(BodyLabel(label, row), 1)
    layout.addWidget(BodyLabel(str(value), row))
    return row


def _progress_row(label: str, detail: str, percent: int) -> QWidget:
    row = QWidget()
    layout = QVBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    top = QHBoxLayout()
    top.addWidget(BodyLabel(label, row))
    top.addStretch(1)
    top.addWidget(CaptionLabel(detail, row))
    bar = ProgressBar(row)
    bar.setValue(percent)
    layout.addLayout(top)
    layout.addWidget(bar)
    return row


def _member_row(member: Member, open_count: int, percent: int) -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(12)
    layout.addWidget(Avatar(member.name, member.color, 26, row), 0, Qt.AlignmentFlag.AlignVCenter)
    column = QVBoxLayout()
    column.setSpacing(6)
    top = QHBoxLayout()
    top.addWidget(BodyLabel(member.name, row))
    top.addStretch(1)
    top.addWidget(CaptionLabel(plural(open_count, "tâche ouverte", "tâches ouvertes"), row))
    bar = ProgressBar(row)
    bar.setValue(percent)
    column.addLayout(top)
    column.addWidget(bar)
    layout.addLayout(column, 1)
    return row


def _upcoming_row(task: Task, project_name: str, member_name: str | None, today: date) -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 6, 0, 6)
    layout.setSpacing(12)
    layout.addWidget(ColorDot(task.priority.color, 8, row), 0, Qt.AlignmentFlag.AlignVCenter)
    texts = QVBoxLayout()
    texts.setSpacing(2)
    texts.addWidget(BodyLabel(task.title, row))
    meta = f"{project_name}, {member_name}" if member_name else project_name
    texts.addWidget(CaptionLabel(meta, row))
    layout.addLayout(texts, 1)
    due = BodyLabel(relative_due(task.due_date, today), row)
    if task.is_overdue(today):
        due.setTextColor(danger_color(), danger_color())
    layout.addWidget(due, 0, Qt.AlignmentFlag.AlignVCenter)
    return row


class DashboardPage(PageBase):
    def __init__(self, repo: Repository, parent: QWidget | None = None):
        super().__init__("dashboardPage", parent)
        self.repo = repo
        self.header = PageHeader("Tableau de bord")
        self.vbox.addWidget(self.header)

        # Un seul bandeau d'indicateurs séparés par des filets, au lieu de quatre cartes identiques
        strip = Surface(variant="card", radius=8)
        strip_layout = QHBoxLayout(strip)
        strip_layout.setContentsMargins(0, 8, 0, 8)
        strip_layout.setSpacing(0)
        self.metrics: dict[str, _Metric] = {}
        for key, caption in (("active", "Projets en cours"), ("open", "Tâches ouvertes"),
                             ("late", "Tâches en retard"), ("rate", "Tâches terminées")):
            if strip_layout.count():
                strip_layout.addWidget(Divider(horizontal=False, parent=strip))
            metric = _Metric(caption, strip)
            self.metrics[key] = metric
            strip_layout.addWidget(metric, 1)
        self.vbox.addWidget(strip)

        row = QHBoxLayout()
        row.setSpacing(16)
        self.upcoming_panel, self.upcoming_box = make_panel("Échéances à venir")
        self.distribution_panel, distribution_box = make_panel("Répartition des tâches")
        row.addWidget(self.upcoming_panel, 3)
        row.addWidget(self.distribution_panel, 2)
        self.vbox.addLayout(row)

        self.donut = DonutChart()
        self.donut.setFixedHeight(170)
        distribution_box.addWidget(self.donut, 0, Qt.AlignmentFlag.AlignHCenter)
        self.legend_box = QVBoxLayout()
        self.legend_box.setSpacing(8)
        distribution_box.addLayout(self.legend_box)

        row2 = QHBoxLayout()
        row2.setSpacing(16)
        self.progress_panel, self.progress_box = make_panel("Avancement des projets")
        self.team_panel, self.team_box = make_panel("Charge de l'équipe")
        row2.addWidget(self.progress_panel, 1)
        row2.addWidget(self.team_panel, 1)
        self.vbox.addLayout(row2)
        self.vbox.addStretch(1)

        self.repo.changed.connect(self._schedule_refresh)
        self.refresh()

    def refresh(self) -> None:
        today = date.today()
        projects = self.repo.list_projects()
        members = self.repo.list_members()
        tasks = self.repo.list_tasks()
        names = {p.id: p.name for p in projects}
        member_names = {m.id: m.name for m in members}

        open_tasks = [t for t in tasks if not t.is_done]
        overdue = [t for t in open_tasks if t.is_overdue(today)]
        soon = [t for t in open_tasks if t.due_date and 0 <= (t.due_date - today).days <= 7]
        active = [p for p in projects if p.status is ProjectStatus.ACTIVE]
        rate = round(100 * (len(tasks) - len(open_tasks)) / len(tasks)) if tasks else 0

        self.header.set_subtitle(
            f"{format_long_date(today)}. {plural(len(soon), 'tâche arrive', 'tâches arrivent')} "
            "à échéance dans les sept prochains jours.")
        self.metrics["active"].set_value(str(len(active)))
        self.metrics["open"].set_value(str(len(open_tasks)))
        self.metrics["late"].set_value(str(len(overdue)), alert=bool(overdue))
        self.metrics["rate"].set_value(f"{rate} %")

        clear_layout(self.upcoming_box)
        upcoming = sorted((t for t in open_tasks if t.due_date), key=lambda t: t.due_date)[:6]
        if not upcoming:
            self.upcoming_box.addWidget(muted_label(
                "Aucune échéance à venir. Ajoutez une date à vos tâches pour les suivre ici."))
        for index, task in enumerate(upcoming):
            if index:
                self.upcoming_box.addWidget(Divider(horizontal=True))
            member_name = member_names.get(task.assignee_id) if task.assignee_id is not None else None
            self.upcoming_box.addWidget(_upcoming_row(task, names.get(task.project_id, ""), member_name, today))

        counts = {s: sum(1 for t in tasks if t.status is s) for s in TaskStatus}
        self.donut.set_data([(s.color, counts[s]) for s in TaskStatus], str(len(tasks)),
                            "tâches" if len(tasks) != 1 else "tâche")
        clear_layout(self.legend_box)
        for status in TaskStatus:
            self.legend_box.addWidget(_legend_row(status.color, status.label, counts[status]))

        clear_layout(self.progress_box)
        if not projects:
            self.progress_box.addWidget(muted_label("Aucun projet. Créez-en un pour suivre son avancement."))
        for project in projects:
            mine = [t for t in tasks if t.project_id == project.id]
            finished = sum(1 for t in mine if t.is_done)
            percent = round(100 * finished / len(mine)) if mine else 0
            self.progress_box.addWidget(_progress_row(project.name, f"{percent} %", percent))

        clear_layout(self.team_box)
        load = {m.id: sum(1 for t in open_tasks if t.assignee_id == m.id) for m in members}
        peak = max(load.values(), default=0) or 1
        if not members:
            self.team_box.addWidget(muted_label("Ajoutez des membres pour répartir le travail."))
        for member in members:
            count = load[member.id]
            self.team_box.addWidget(_member_row(member, count, round(100 * count / peak)))
