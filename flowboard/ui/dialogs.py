"""Formulaires modaux : tâche (avec sous-tâches), projet et membre d'équipe."""
from __future__ import annotations

from PySide6.QtWidgets import QAbstractSpinBox, QGridLayout, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (CaptionLabel, CheckBox, ComboBox, DateEdit, FluentIcon as FIF, InfoBarPosition,
                            InfoBar, LineEdit, MessageBoxBase, SubtitleLabel, TextEdit, TransparentToolButton)

from ..models import ACCENT_PALETTE, Member, Priority, Project, ProjectStatus, Subtask, Task, TaskStatus
from ..utils import date_to_qdate, parse_tags, qdate_to_date
from .common import ColorPicker


def _labeled(caption: str, widget: QWidget, parent: QWidget) -> QWidget:
    box = QWidget(parent)
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    layout.addWidget(CaptionLabel(caption, box))
    layout.addWidget(widget)
    return box


def _new_date_edit(parent: QWidget) -> DateEdit:
    """Sélecteur de date Fluent avec calendrier, affiché selon la locale (français)."""
    edit = DateEdit(parent)
    edit.setCalendarPopup(True)
    edit.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
    edit.setDisplayFormat("d MMMM yyyy")
    edit.setMinimumWidth(230)
    return edit


def _date_row(check: CheckBox, picker: DateEdit, parent: QWidget) -> QWidget:
    """Case « définir une date » + sélecteur ; le sélecteur n'est actif que si la case est cochée."""
    row = QWidget(parent)
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(12)
    layout.addWidget(check)
    layout.addWidget(picker)
    layout.addStretch(1)
    picker.setEnabled(check.isChecked())
    check.toggled.connect(picker.setEnabled)
    return row


class _SubtaskRow(QWidget):
    def __init__(self, title: str, done: bool, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.check = CheckBox(title, self)
        self.check.setChecked(done)
        self.remove = TransparentToolButton(FIF.CLOSE, self)
        self.remove.setToolTip("Supprimer la sous-tâche")
        layout.addWidget(self.check, 1)
        layout.addWidget(self.remove)

    def subtask(self) -> Subtask:
        return Subtask(title=self.check.text().strip(), done=self.check.isChecked())


class TaskDialog(MessageBoxBase):
    """Création ou modification d'une tâche."""

    def __init__(self, projects: list[Project], members: list[Member], parent: QWidget | None = None,
                 task: Task | None = None, project_id: int | None = None,
                 status: TaskStatus = TaskStatus.TODO):
        super().__init__(parent)
        self._projects = projects
        self._members = members
        self._task = task
        self._subtask_rows: list[_SubtaskRow] = []
        self.widget.setMinimumWidth(640)
        self.viewLayout.addWidget(SubtitleLabel("Modifier la tâche" if task else "Nouvelle tâche", self))

        self.titleEdit = LineEdit(self)
        self.titleEdit.setPlaceholderText("Par exemple : valider la maquette de l'accueil")
        self.titleEdit.setClearButtonEnabled(True)

        self.projectBox = ComboBox(self)
        for project in projects:
            self.projectBox.addItem(project.name)

        self.statusBox = ComboBox(self)
        for item in TaskStatus:
            self.statusBox.addItem(item.label)

        self.priorityBox = ComboBox(self)
        for item in Priority:
            self.priorityBox.addItem(item.label)

        self.assigneeBox = ComboBox(self)
        self.assigneeBox.addItem("Non assigné")
        for member in members:
            self.assigneeBox.addItem(member.name)

        self.dueCheck = CheckBox("Définir une échéance", self)
        self.datePicker = _new_date_edit(self)
        due_row = _date_row(self.dueCheck, self.datePicker, self)

        self.tagsEdit = LineEdit(self)
        self.tagsEdit.setPlaceholderText("design, accessibilité")

        self.descriptionEdit = TextEdit(self)
        self.descriptionEdit.setPlaceholderText("Contexte, critères d'acceptation, liens utiles…")
        self.descriptionEdit.setFixedHeight(92)

        self.subtaskInput = LineEdit(self)
        self.subtaskInput.setPlaceholderText("Ajouter une sous-tâche, puis Entrée")
        self.subtaskInput.returnPressed.connect(self._add_subtask_from_input)
        add_subtask = TransparentToolButton(FIF.ADD, self)
        add_subtask.clicked.connect(lambda _checked=False: self._add_subtask_from_input())
        input_row = QHBoxLayout()
        input_row.addWidget(self.subtaskInput, 1)
        input_row.addWidget(add_subtask)
        self.subtaskBox = QVBoxLayout()
        self.subtaskBox.setSpacing(4)
        subtasks = QWidget(self)
        subtasks_layout = QVBoxLayout(subtasks)
        subtasks_layout.setContentsMargins(0, 0, 0, 0)
        subtasks_layout.setSpacing(6)
        subtasks_layout.addLayout(self.subtaskBox)
        subtasks_layout.addLayout(input_row)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(14)
        grid.addWidget(_labeled("Nom", self.titleEdit, self), 0, 0, 1, 2)
        grid.addWidget(_labeled("Projet", self.projectBox, self), 1, 0)
        grid.addWidget(_labeled("Statut", self.statusBox, self), 1, 1)
        grid.addWidget(_labeled("Priorité", self.priorityBox, self), 2, 0)
        grid.addWidget(_labeled("Responsable", self.assigneeBox, self), 2, 1)
        grid.addWidget(_labeled("Échéance", due_row, self), 3, 0)
        grid.addWidget(_labeled("Étiquettes", self.tagsEdit, self), 3, 1)
        grid.addWidget(_labeled("Description", self.descriptionEdit, self), 4, 0, 1, 2)
        grid.addWidget(_labeled("Sous-tâches", subtasks, self), 5, 0, 1, 2)
        self.viewLayout.addLayout(grid)

        self.yesButton.setText("Enregistrer")
        self.cancelButton.setText("Annuler")
        self._fill(project_id, status)

    def _fill(self, project_id: int | None, status: TaskStatus) -> None:
        task = self._task
        if task is not None:
            project_id, status = task.project_id, task.status
            self.titleEdit.setText(task.title)
            self.descriptionEdit.setPlainText(task.description)
            self.tagsEdit.setText(", ".join(task.tags))
            self.priorityBox.setCurrentIndex(list(Priority).index(task.priority))
            for sub in task.subtasks:
                self._add_subtask_row(sub.title, sub.done)
        else:
            self.priorityBox.setCurrentIndex(list(Priority).index(Priority.NORMAL))

        project_ids = [p.id for p in self._projects]
        if project_id in project_ids:
            self.projectBox.setCurrentIndex(project_ids.index(project_id))
        self.statusBox.setCurrentIndex(list(TaskStatus).index(status))
        member_ids = [m.id for m in self._members]
        if task is not None and task.assignee_id in member_ids:
            self.assigneeBox.setCurrentIndex(member_ids.index(task.assignee_id) + 1)

        due = task.due_date if task is not None else None
        self.dueCheck.setChecked(due is not None)
        self.datePicker.setDate(date_to_qdate(due))
        self.datePicker.setEnabled(due is not None)

    # ----- sous-tâches -----------------------------------------------------
    def _add_subtask_row(self, title: str, done: bool = False) -> None:
        row = _SubtaskRow(title, done, self)
        row.remove.clicked.connect(lambda _checked=False, r=row: self._remove_subtask_row(r))
        self._subtask_rows.append(row)
        self.subtaskBox.addWidget(row)

    def _remove_subtask_row(self, row: _SubtaskRow) -> None:
        if row in self._subtask_rows:
            self._subtask_rows.remove(row)
        self.subtaskBox.removeWidget(row)
        row.deleteLater()

    def _add_subtask_from_input(self) -> None:
        text = self.subtaskInput.text().strip()
        if text:
            self._add_subtask_row(text)
            self.subtaskInput.clear()

    # ----- validation et résultat -----------------------------------------
    def validate(self) -> bool:
        if not self.titleEdit.text().strip():
            InfoBar.warning("Nom manquant", "Donnez un nom à la tâche avant d'enregistrer.",
                            parent=self, position=InfoBarPosition.TOP, duration=2500)
            self.titleEdit.setFocus()
            return False
        if not self._projects:
            InfoBar.warning("Aucun projet", "Créez d'abord un projet pour y ajouter des tâches.",
                            parent=self, position=InfoBarPosition.TOP, duration=2500)
            return False
        return True

    def build_task(self) -> Task:
        task = self._task if self._task is not None else Task()
        task.title = self.titleEdit.text().strip()
        task.project_id = self._projects[self.projectBox.currentIndex()].id
        task.status = list(TaskStatus)[self.statusBox.currentIndex()]
        task.priority = list(Priority)[self.priorityBox.currentIndex()]
        index = self.assigneeBox.currentIndex()
        task.assignee_id = self._members[index - 1].id if index > 0 else None
        task.due_date = qdate_to_date(self.datePicker.date()) if self.dueCheck.isChecked() else None
        task.description = self.descriptionEdit.toPlainText().strip()
        task.tags = parse_tags(self.tagsEdit.text())
        task.subtasks = [row.subtask() for row in self._subtask_rows if row.check.text().strip()]
        return task


class ProjectDialog(MessageBoxBase):
    """Création ou modification d'un projet."""

    def __init__(self, parent: QWidget | None = None, project: Project | None = None):
        super().__init__(parent)
        self._project = project
        self.widget.setMinimumWidth(560)
        self.viewLayout.addWidget(SubtitleLabel("Modifier le projet" if project else "Nouveau projet", self))

        self.nameEdit = LineEdit(self)
        self.nameEdit.setPlaceholderText("Par exemple : refonte du site vitrine")
        self.nameEdit.setClearButtonEnabled(True)
        self.descriptionEdit = TextEdit(self)
        self.descriptionEdit.setPlaceholderText("Objectif du projet en une ou deux phrases")
        self.descriptionEdit.setFixedHeight(80)
        self.colorPicker = ColorPicker(ACCENT_PALETTE, project.color if project else ACCENT_PALETTE[0], self)
        self.statusBox = ComboBox(self)
        for item in ProjectStatus:
            self.statusBox.addItem(item.label)

        self.startCheck = CheckBox("Définir une date de début", self)
        self.startPicker = _new_date_edit(self)
        self.dueCheck = CheckBox("Définir une échéance", self)
        self.duePicker = _new_date_edit(self)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(14)
        grid.addWidget(_labeled("Nom", self.nameEdit, self), 0, 0, 1, 2)
        grid.addWidget(_labeled("Description", self.descriptionEdit, self), 1, 0, 1, 2)
        grid.addWidget(_labeled("Couleur", self.colorPicker, self), 2, 0)
        grid.addWidget(_labeled("Statut", self.statusBox, self), 2, 1)
        grid.addWidget(_labeled("Début", _date_row(self.startCheck, self.startPicker, self), self), 3, 0, 1, 2)
        grid.addWidget(_labeled("Échéance", _date_row(self.dueCheck, self.duePicker, self), self), 4, 0, 1, 2)
        self.viewLayout.addLayout(grid)

        if project is not None:
            self.nameEdit.setText(project.name)
            self.descriptionEdit.setPlainText(project.description)
        self.statusBox.setCurrentIndex(list(ProjectStatus).index(project.status if project else ProjectStatus.ACTIVE))
        start = project.start_date if project else None
        self.startCheck.setChecked(start is not None)
        self.startPicker.setDate(date_to_qdate(start))
        due = project.due_date if project else None
        self.dueCheck.setChecked(due is not None)
        self.duePicker.setDate(date_to_qdate(due))

        self.yesButton.setText("Enregistrer")
        self.cancelButton.setText("Annuler")

    def validate(self) -> bool:
        if not self.nameEdit.text().strip():
            InfoBar.warning("Nom manquant", "Donnez un nom au projet avant d'enregistrer.",
                            parent=self, position=InfoBarPosition.TOP, duration=2500)
            self.nameEdit.setFocus()
            return False
        if self.startCheck.isChecked() and self.dueCheck.isChecked():
            start = self.startPicker.date()
            due = self.duePicker.date()
            if due < start:
                InfoBar.warning("Dates incohérentes", "La date de fin doit suivre la date de début.",
                                parent=self, position=InfoBarPosition.TOP, duration=3000)
                return False
        return True

    def build_project(self) -> Project:
        project = self._project if self._project is not None else Project()
        project.name = self.nameEdit.text().strip()
        project.description = self.descriptionEdit.toPlainText().strip()
        project.color = self.colorPicker.color()
        project.status = list(ProjectStatus)[self.statusBox.currentIndex()]
        project.start_date = qdate_to_date(self.startPicker.date()) if self.startCheck.isChecked() else None
        project.due_date = qdate_to_date(self.duePicker.date()) if self.dueCheck.isChecked() else None
        return project


class MemberDialog(MessageBoxBase):
    """Création ou modification d'un membre de l'équipe."""

    def __init__(self, parent: QWidget | None = None, member: Member | None = None,
                 default_color: str = ACCENT_PALETTE[0]):
        super().__init__(parent)
        self._member = member
        self.widget.setMinimumWidth(480)
        self.viewLayout.addWidget(SubtitleLabel("Modifier le membre" if member else "Nouveau membre", self))

        self.nameEdit = LineEdit(self)
        self.nameEdit.setPlaceholderText("Prénom et nom")
        self.nameEdit.setClearButtonEnabled(True)
        self.roleEdit = LineEdit(self)
        self.roleEdit.setPlaceholderText("Par exemple : développeuse back-end")
        current = member.color if member else default_color
        self.colorPicker = ColorPicker(ACCENT_PALETTE, current, self)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(14)
        grid.addWidget(_labeled("Nom", self.nameEdit, self), 0, 0, 1, 2)
        grid.addWidget(_labeled("Rôle", self.roleEdit, self), 1, 0, 1, 2)
        grid.addWidget(_labeled("Couleur de l'avatar", self.colorPicker, self), 2, 0, 1, 2)
        self.viewLayout.addLayout(grid)

        if member is not None:
            self.nameEdit.setText(member.name)
            self.roleEdit.setText(member.role)
        self.yesButton.setText("Enregistrer")
        self.cancelButton.setText("Annuler")

    def validate(self) -> bool:
        if not self.nameEdit.text().strip():
            InfoBar.warning("Nom manquant", "Indiquez le nom du membre avant d'enregistrer.",
                            parent=self, position=InfoBarPosition.TOP, duration=2500)
            self.nameEdit.setFocus()
            return False
        return True

    def build_member(self) -> Member:
        member = self._member if self._member is not None else Member()
        member.name = self.nameEdit.text().strip()
        member.role = self.roleEdit.text().strip()
        member.color = self.colorPicker.color()
        return member
