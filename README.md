# Escale

Application de bureau de gestion de projets et de tableau Kanban, construite avec **PySide6** et **PyQt-Fluent-Widgets** : style Fluent Design, effet Mica, thèmes clair et sombre.

## Fonctionnalités

- **Tableau de bord** : indicateurs clés, échéances à venir, répartition des tâches, avancement des projets, charge de l'équipe.
- **Projets** : statut, couleur, description, dates, avancement et membres de l'équipe.
- **Kanban** : colonnes À faire, En cours, En revue et Terminé, glisser-déposer avec repère d'insertion, sous-tâches cochables sur la carte, marquer terminé en un clic, double-clic pour modifier, menu contextuel.
- **Tâches** : tableau filtrable (recherche, projet, statut, priorité), tri par colonnes et export CSV compatible Excel.
- **Détails d'une tâche** : priorité, responsable, échéance, étiquettes, description et sous-tâches.
- **Équipe** : membres, rôles et charge de travail.
- **Paramètres** : thème clair, sombre ou selon Windows, couleur d'accent, effet Mica, réinitialisation des données de démonstration.
- **Stockage local** : base SQLite, aucun compte ni connexion requis.

## Installation

```bash
pip install -r requirements.txt
python main.py
```

Python 3.10 ou plus récent est recommandé.

### Windows

Installateur tout-en-un : **`Escale-Setup-0.0.1.exe`**. Il installe Escale dans
`%LOCALAPPDATA%\Programs\Escale` (aucun droit administrateur requis), crée les raccourcis
(menu Démarrer + bureau) et un désinstalleur (visible dans « Ajout/Suppression de programmes »).
Les données utilisateur (`%APPDATA%\Escale\`) sont conservées à la désinstallation.

Pour reconstruire l'installateur :

```bash
python -m PyInstaller --noconfirm --clean --onefile --windowed --name Escale --icon=escale.ico main.py
"C:\Program Files (x86)\NSIS\makensis.exe" Escale.nsi
```

## Données

- Windows : `%APPDATA%\Escale\escale.db` (préférences dans `settings.json`).
- Au premier lancement, l'application charge des données de démonstration.
- Si vous utilisiez FlowBoard, vos données sont reprises automatiquement au premier lancement.

## Notes

- L'effet Mica n'apparaît que sous Windows 11 ; ailleurs, la fenêtre reste opaque.
- PyQt-Fluent-Widgets est distribuée sous licence GPL-3.0 ou sous licence commerciale. Vérifiez les conditions avant de diffuser un produit fermé.

## Structure

```
main.py                      point d'entrée
escale.ico                   icône de l'application
Escale.nsi                   script de l'installateur
flowboard/
  models.py                  énumérations et dataclasses
  repository.py              persistance SQLite et données de démonstration
  settings.py                préférences persistées
  utils.py                   dates en français, export CSV, outils
  ui/
    main_window.py           fenêtre, navigation Fluent, Mica
    widgets.py               surfaces peintes, avatars, anneau de répartition
    common.py                pages, en-têtes, états vides, sélecteur de couleur
    kanban.py                tableau Kanban et glisser-déposer
    dialogs.py               formulaires tâche, projet et membre
    pages/                   tableau de bord, projets, Kanban, tâches, équipe, paramètres
```
