"""Préférences persistées dans settings.json (gérées par qfluentwidgets)."""
from qfluentwidgets import BoolValidator, ConfigItem, QConfig


class EscaleConfig(QConfig):
    # L'effet Mica n'est appliqué que sous Windows 11 (ignoré ailleurs)
    micaEnabled = ConfigItem("Window", "MicaEnabled", True, BoolValidator())
    # Dernier projet affiché dans le Kanban (0 = aucun)
    lastProjectId = ConfigItem("Board", "LastProjectId", 0)


cfg = EscaleConfig()
