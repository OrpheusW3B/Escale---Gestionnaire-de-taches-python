"""Point d'entrée d'Escale : `python main.py`."""
from __future__ import annotations

import ctypes
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QLocale
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication
from qfluentwidgets import FluentTranslator, Theme, qconfig, setTheme, setThemeColor

from flowboard import APP_NAME, __version__
from flowboard.repository import Repository
from flowboard.settings import cfg
from flowboard.ui.main_window import MainWindow
from flowboard.utils import app_data_dir

DEFAULT_ACCENT = "#0F6CBD"
LEGACY_APP_NAME = "FlowBoard"
DB_NAME = "escale.db"


def _migrate_legacy_data(data_dir: Path) -> None:
    """Reprend les données de FlowBoard au premier lancement sous le nouveau nom."""
    legacy_dir = data_dir.parent / LEGACY_APP_NAME
    if legacy_dir == data_dir or not legacy_dir.is_dir():
        return
    if not (data_dir / DB_NAME).exists() and (legacy_dir / "flowboard.db").exists():
        shutil.copy2(legacy_dir / "flowboard.db", data_dir / DB_NAME)
    if not (data_dir / "settings.json").exists() and (legacy_dir / "settings.json").exists():
        shutil.copy2(legacy_dir / "settings.json", data_dir / "settings.json")


def main() -> int:
    if sys.platform == "win32":
        # Regroupement et icône corrects dans la barre des tâches
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"{APP_NAME}.{__version__}")

    # Locale française par défaut : noms de mois et sélecteurs de date en français
    QLocale.setDefault(QLocale(QLocale.Language.French, QLocale.Country.France))
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.installTranslator(FluentTranslator(QLocale(QLocale.Language.French)))

    data_dir = app_data_dir()
    _migrate_legacy_data(data_dir)
    settings_file = data_dir / "settings.json"
    first_run = not settings_file.exists()
    qconfig.load(str(settings_file), cfg)
    if first_run:
        # Premier lancement : suivre le thème de Windows et utiliser le bleu Fluent par défaut
        setThemeColor(QColor(DEFAULT_ACCENT), save=True)
        setTheme(Theme.AUTO, save=True)

    repo = Repository(data_dir / DB_NAME)
    window = MainWindow(repo)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
