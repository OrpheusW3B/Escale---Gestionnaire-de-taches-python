"""Page paramètres : apparence (thème, accent, Mica), données et à propos."""
from __future__ import annotations

import sys

import PySide6
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QWidget
from qfluentwidgets import (FluentIcon as FIF, HyperlinkCard, MessageBox, OptionsSettingCard, PushSettingCard,
                            SettingCard, SettingCardGroup, SwitchSettingCard, ColorSettingCard, qconfig)

from ... import __version__
from ...repository import Repository
from ...settings import cfg
from ...utils import app_data_dir
from ..common import PageBase, PageHeader, notify


class SettingsPage(PageBase):
    def __init__(self, repo: Repository, parent: QWidget | None = None):
        super().__init__("settingsPage", parent)
        self.repo = repo
        self.vbox.addWidget(PageHeader("Paramètres", "Personnalisez l'apparence et gérez vos données."))

        appearance = SettingCardGroup("Apparence", self.content)
        appearance.addSettingCard(OptionsSettingCard(
            qconfig.themeMode, FIF.BRUSH, "Thème de l'application",
            "Mode clair, mode sombre, ou selon le réglage de Windows",
            texts=["Clair", "Sombre", "Selon Windows"], parent=appearance))
        appearance.addSettingCard(ColorSettingCard(
            qconfig.themeColor, FIF.PALETTE, "Couleur d'accent",
            "Couleur des boutons, des sélections et des indicateurs", appearance))
        appearance.addSettingCard(SwitchSettingCard(
            FIF.TRANSPARENT, "Effet Mica",
            "Fond translucide de la fenêtre. Disponible sous Windows 11.", cfg.micaEnabled, appearance))
        self.vbox.addWidget(appearance)

        data = SettingCardGroup("Données", self.content)
        folder = app_data_dir()
        open_card = PushSettingCard("Ouvrir le dossier", FIF.FOLDER, "Dossier des données",
                                    str(folder), data)
        open_card.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder))))
        data.addSettingCard(open_card)
        demo_card = PushSettingCard("Réinitialiser", FIF.HISTORY, "Données de démonstration",
                                    "Remplace toutes les données par l'exemple fourni. Action irréversible.", data)
        demo_card.clicked.connect(self._reset_demo)
        data.addSettingCard(demo_card)
        wipe_card = PushSettingCard("Tout vider", FIF.DELETE, "Effacer toutes les données",
                                    "Supprime tous les projets, tâches et membres. Action irréversible.", data)
        wipe_card.clicked.connect(self._clear_all)
        data.addSettingCard(wipe_card)
        self.vbox.addWidget(data)

        about = SettingCardGroup("À propos", self.content)
        about.addSettingCard(SettingCard(
            FIF.INFO, f"Escale {__version__}",
            f"Propulsé par PySide6 {PySide6.__version__} et Python {sys.version.split()[0]}.", about))
        about.addSettingCard(HyperlinkCard(
            "https://github.com/zhiyiYo/PyQt-Fluent-Widgets", "Voir le dépôt", FIF.GITHUB,
            "PyQt-Fluent-Widgets",
            "Composants Fluent utilisés par Escale. Licence GPL-3.0, licence commerciale disponible.", about))
        self.vbox.addWidget(about)
        self.vbox.addStretch(1)

    def _reset_demo(self) -> None:
        box = MessageBox("Réinitialiser les données ?",
                         "Toutes les tâches, projets et membres seront remplacés par les données de démonstration.",
                         self.window())
        box.yesButton.setText("Réinitialiser")
        box.cancelButton.setText("Annuler")
        if box.exec():
            self.repo.reset_demo_data()
            notify(self.window(), "Données réinitialisées", "Les exemples ont été rechargés.")

    def _clear_all(self) -> None:
        box = MessageBox("Vider toute l'application ?",
                         "Tous les projets, tâches et membres seront supprimés définitivement. Cette action est irréversible.",
                         self.window())
        box.yesButton.setText("Tout vider")
        box.cancelButton.setText("Annuler")
        if box.exec():
            self.repo.clear_all_data()
            notify(self.window(), "Données supprimées", "Tous les projets, tâches et membres ont été supprimés.")
