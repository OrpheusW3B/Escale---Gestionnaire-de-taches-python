"""Outils transversaux : chemins, dates en français, export CSV et couleurs."""
from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from typing import Iterable

from PySide6.QtCore import QDate, QStandardPaths
from PySide6.QtGui import QColor

from . import APP_NAME
from .models import Task

_MONTHS_SHORT = ["janv.", "févr.", "mars", "avr.", "mai", "juin",
                 "juil.", "août", "sept.", "oct.", "nov.", "déc."]
_MONTHS_LONG = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
                "août", "septembre", "octobre", "novembre", "décembre"]
_WEEKDAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


def app_data_dir() -> Path:
    """Dossier utilisateur de l'application (base SQLite, préférences)."""
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    path = Path(base) if base else Path.home() / f".{APP_NAME.lower()}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def qdate_to_date(value: QDate) -> date | None:
    return value.toPython() if value.isValid() else None


def date_to_qdate(value: date | None) -> QDate:
    if value is None:
        return QDate.currentDate()
    return QDate(value.year, value.month, value.day)


def format_date(value: date, with_year: bool = True) -> str:
    text = f"{value.day} {_MONTHS_SHORT[value.month - 1]}"
    return f"{text} {value.year}" if with_year else text


def format_long_date(value: date) -> str:
    weekday = _WEEKDAYS[value.weekday()].capitalize()
    return f"{weekday} {value.day} {_MONTHS_LONG[value.month - 1]} {value.year}"


def relative_due(value: date, today: date | None = None) -> str:
    """Libellé court d'une échéance : « Aujourd'hui », « Demain », « En retard de 2 j »…"""
    today = today or date.today()
    delta = (value - today).days
    if delta == 0:
        return "Aujourd'hui"
    if delta == 1:
        return "Demain"
    if delta < 0:
        return f"En retard de {-delta} j"
    return format_date(value, with_year=value.year != today.year)


def plural(count: int, singular: str, plural_form: str) -> str:
    return f"{count} {singular if count == 1 else plural_form}"


def initials(name: str) -> str:
    parts = [p for p in name.split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def parse_tags(text: str) -> list[str]:
    tags: list[str] = []
    for raw in text.replace(";", ",").split(","):
        tag = raw.strip().lstrip("#").strip()
        if tag and tag.lower() not in (t.lower() for t in tags):
            tags.append(tag)
    return tags


def readable_on(color: str) -> QColor:
    """Texte noir ou blanc, selon la luminosité de la couleur de fond."""
    c = QColor(color)
    luma = 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()
    return QColor("#1B1B1B") if luma > 150 else QColor("#FFFFFF")


def export_tasks_csv(path: str | Path, tasks: Iterable[Task],
                     project_names: dict[int, str], member_names: dict[int, str]) -> None:
    """Exporte les tâches en CSV (séparateur « ; », compatible Excel en français)."""
    headers = ["Tâche", "Projet", "Statut", "Priorité", "Responsable", "Échéance",
               "Étiquettes", "Sous-tâches terminées", "Créée le", "Terminée le"]
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(headers)
        for t in tasks:
            subs = t.subtasks
            writer.writerow([
                t.title,
                project_names.get(t.project_id, ""),
                t.status.label,
                t.priority.label,
                member_names.get(t.assignee_id, "") if t.assignee_id is not None else "",
                t.due_date.isoformat() if t.due_date else "",
                ", ".join(t.tags),
                f"{sum(1 for s in subs if s.done)}/{len(subs)}" if subs else "",
                t.created_at.strftime("%Y-%m-%d %H:%M") if t.created_at else "",
                t.completed_at.strftime("%Y-%m-%d %H:%M") if t.completed_at else "",
            ])
