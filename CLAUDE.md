# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Aperçu du projet

QuantLab est un monorepo Python pour la collecte de données quantitatives, l'analyse et la recherche en mode collaboratif. PostgreSQL est le magasin de données partagé faisant autorité ; GitHub fait autorité pour le code/la doc. Le composant le plus mature est le pipeline des halts Nasdaq (collecteur → PostgreSQL → analytics → GUI PySide6) ; un second composant (warrants/structure du capital) est encore au stade d'ébauche mais suit le même patron.

La référence d'architecture détaillée se trouve dans `docs/architecture.md` (anglais) et `docs/database.md` (français — conserver le français en éditant ce fichier). La documentation propre à chaque composant se trouve sous `collectors/nasdaq_halts/docs/` et `collectors/warrants/docs/`.

## Commandes

Nécessite Python >=3.14, une installation éditable (`pip install -e .`), un venv dans `.venv` (gitignored). Aucun linter/formatter n'est configuré (pas de config ruff/black/mypy malgré le `.gitignore` qui anticipe leurs dossiers de cache) et il n'y a pas de configuration CI.

- Initialiser un environnement de dev : `powershell -ExecutionPolicy Bypass -File .\scripts\setup_quantlab.ps1` (crée le venv, installe les dépendances épinglées de `requirements.txt`, installe le package en mode éditable, exécute toute la suite de tests comme condition de succès, persiste les variables `QUANTLAB_DB_*` non sensibles dans le profil utilisateur Windows).
- Lancer tous les tests : `python -m pytest -q`
- Lancer un seul fichier de test : `pytest tests/analytics/test_metric_1.py`
- Lancer un seul test : `pytest tests/analytics/test_metric_1.py::test_name`
- Remarque : `tests/integration/test_nasdaq_postgresql_live_update.py` communique avec une vraie instance PostgreSQL (dans une transaction annulée/rollback) et nécessite que les variables `QUANTLAB_DB_*` soient définies.
- Lancer la GUI : `powershell -File .\scripts\run_nasdaq_halts.ps1` (ou directement : `python -m ui.nasdaq_halts.app`) — demande le mot de passe DB de façon sécurisée et l'efface de l'environnement à la sortie.
- Lancer le collecteur historique Nasdaq : `python -m collectors.nasdaq_halts.src.nasdaq_historical_collector --start-date YYYY-MM-DD --end-date YYYY-MM-DD` (optionnel `--feed halts|resumptions`, `--delay-seconds`, `--max-retries`, `--retry-delay-seconds`)
- Lancer la collecte Nasdaq en direct : `python -m collectors.nasdaq_halts.src.nasdaq_halt_collector`
- Lancer le pipeline de métriques historiques (XML brut → PostgreSQL + CSV de diagnostic) : `python -m collectors.nasdaq_halts.src.calculate_halt_metrics`
- Toutes les commandes s'exécutent depuis la racine du dépôt, venv activé.

## Architecture

Patron à trois couches partagé par chaque collecteur : **RAW → CORE → analytics**, adossé aux schémas PostgreSQL `raw`, `core` et `analytics` (le schéma `analytics` lui-même n'est pas encore peuplé ; le calcul analytique se fait côté Python).

- `collectors/<name>/` — acquisition. Possède son propre `data/{raw,processed}/` et `logs/` (tous deux gitignored, par composant — il n'y a pas de répertoire de données partagé à la racine). `collectors/nasdaq_halts/` est l'implémentation de référence : téléchargement XML → parsing (`nasdaq_xml.py`) → déduplication (`nasdaq_deduplication.py`) → construction des épisodes (`nasdaq_episodes.py`) → persistance (`nasdaq_postgresql.py`), qui écrit dans `raw.nasdaq_trade_halt`, `raw.nasdaq_resumption`, `core.nasdaq_halt_episode`, `core.nasdaq_halt_episode_event` au sein d'une seule transaction. `collectors/warrants/` n'est qu'une ébauche (`dilutiontracker_collector.py` lève `NotImplementedError`) et est conçu pour réutiliser le même patron avec de nouvelles tables (`core.security`, `core.warrant`, `core.warrant_term_history`, `raw.dilutiontracker_response`, `raw.sec_filing`), avec à terme des jointures avec `core.nasdaq_halt_episode` par ticker/horodatage.
- `analytics/<name>/` — lecture seule sur la base, sans dépendance sur le code du collecteur. `analytics/nasdaq_halts/` : `core_source.py` (`NasdaqHaltCoreSource`) lit `core.nasdaq_halt_episode` via `shared/database` ; `analysis_service.py` (`AnalysisService`) orchestre récupération → `historical_dataset.build_historical_dataset` → `metric_calculator.calculate_metrics` → un `AnalysisResult`. C'est la frontière dont dépend la GUI.
- `ui/nasdaq_halts/` — GUI de bureau PySide6, point d'entrée humain. `MainWindow` (`main_window.py`) instancie `AnalysisService(core_source=NasdaqHaltCoreSource())` pour le Mode Manuel (un seul ticker) et le Mode Fichier/Batch (XLSX/CSV via `file_validation.py`). La GUI ne parle qu'au package analytics (et transitivement à PostgreSQL) — jamais au collecteur ni au XML brut directement. Remarque : PySide6 est épinglé dans `requirements.txt` mais absent des dépendances de `pyproject.toml`.
- `shared/` — le code transversal réellement utilisé aujourd'hui se limite à `shared/database/connection.py` (`get_connection()` — l'unique fabrique de connexion psycopg3, lit les variables `QUANTLAB_DB_*`, exige TLS) et `shared/calendar/trading_calendar.py` (calendrier des jours fériés NYSE/Nasdaq). `shared/config/`, `shared/logging/`, `shared/utilities/` sont des packages vides — ne pas supposer qu'une fonctionnalité y existe déjà.
- `database/migrations/*.sql` — versionnées, numérotées, appliquées manuellement via `psql ... -f database/migrations/<file>.sql` avec un compte admin. Deux fichiers partagent volontairement le préfixe `002` (`002_core_episode_event.sql`, `002_fix_nasdaq_halt_close_status.sql`) — c'est documenté comme historique et ne doit pas être renommé. Les migrations ne sont jamais modifiées rétroactivement une fois appliquées ; une nouvelle migration prend toujours un numéro inutilisé.
- `orchestration/jobs/` — vide ; l'ordonnancement centralisé n'est pas encore implémenté. Tout s'exécute actuellement à la demande via les scripts/invocations de modules ci-dessus.
- `scripts/` — `setup_quantlab.ps1` (initialisation de l'environnement) et `run_nasdaq_halts.ps1` (lanceur de la GUI) sont les points d'entrée destinés aux collaborateurs ; `scripts/historical/` contient des scripts ponctuels de backfill/diagnostic (`load_raw_month.py`, `load_core_history.py`, `diagnose_core_*.py`, etc.), qui ne font pas partie du chemin d'exécution normal.

### Conventions transversales

- **Configuration DB via variables d'environnement uniquement**, jamais de fichier `.env` : `QUANTLAB_DB_HOST/PORT/NAME/USER/PASSWORD`. Les valeurs non sensibles sont persistées comme variables d'environnement utilisateur Windows par `setup_quantlab.ps1` ; le mot de passe est toujours demandé de façon interactive et effacé après usage (voir `run_nasdaq_halts.ps1`). Tout nouveau code ayant besoin de PostgreSQL doit passer par `shared/database/connection.get_connection()` plutôt que d'ouvrir sa propre connexion.
- **RAW immuable / CORE mutable** : les fichiers source (XML, JSON d'API) ne sont jamais modifiés en place ; l'enrichissement se fait de façon additive au niveau CORE. Les écrivains ne doivent jamais laisser une valeur NULL entrante écraser une valeur connue existante.
- **Concurrence** : les écrivains Nasdaq se sérialisent via `pg_advisory_xact_lock(716203, 1)`. Un nouvel écrivain touchant les mêmes tables doit respecter cette convention de verrouillage ou l'étendre délibérément, plutôt que d'en inventer une autre.
- **Le CSV est uniquement à but diagnostique** — ne jamais le traiter comme un chemin de production entre un collecteur et PostgreSQL ; il sert uniquement aux exports/vérifications de non-régression.
- **Patron de résolution de chemins** : vérifier d'abord une variable d'environnement de surcharge (ex. `QUANTLAB_NASDAQ_RAW_DIRECTORY`), puis retomber sur la config JSON du composant (voir `collectors/nasdaq_halts/src/nasdaq_paths.py`) — suivre ce patron pour tout nouveau chemin propre à une machine.
- **Les fichiers de config ne contiennent aucun secret** : les configs JSON (ex. `collectors/nasdaq_halts/config/config.json`, `collectors/warrants/config.example.json`) référencent les secrets uniquement par nom de variable d'environnement.
- **Piège BOM Windows/PowerShell 5.1** : `Set-Content -Encoding utf8` sous PowerShell 5.1 écrit un BOM, ce qui casse l'exécution de fichiers `.sql` par `psql`. Lors de la génération d'un fichier (notamment les migrations SQL) via PowerShell sur cette machine, l'écrire sans BOM (ex. via `New-Object System.Text.UTF8Encoding($false)`).
- **`docs/database.md` est rédigé en français** — conserver le français en l'éditant ; les autres docs (`architecture.md`, `installation.md`, `collaborator_installation.md`, les README) sont en anglais.
- **Périmètre du système de fichiers** : ne jamais lire, écrire ou exécuter de commande en dehors de `C:\QuantLab\QuantLab` sans permission explicite de l'utilisateur au préalable.
