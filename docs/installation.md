# QuantLab — Installation and Deployment Procedure

## 1. Purpose

This document defines the reproducible installation procedure for a QuantLab development workstation.

The objective is to allow an authorized collaborator to configure a new workstation and obtain a consistent QuantLab development environment.

## 2. Current Reference Environment

Initial reference workstation:

- Operating system: Windows
- Project root: `C:\QuantLab\QuantLab`
- Source control: Git
- Remote repository: private GitHub repository `QuantLab`
- Development environment: Visual Studio Code
- Python: installed separately
- Authentication: individual GitHub account with 2FA enabled

Secrets, passwords, recovery codes, tokens, and database credentials must never be recorded in this document.

## 3. GitHub Account

Each collaborator must use an individual GitHub account.

Requirements:

- verified email address;
- Two-Factor Authentication (2FA) enabled;
- no shared account credentials.

The initial QuantLab repository is configured as private.

## 4. Git Installation

Git for Windows is installed on the workstation.

Reference installation verified with:

    git --version

Initial workstation result:

    git version 2.55.0.windows.5

## 5. Git Identity

Git identity is configured globally:

    git config --global user.name "<USER NAME>"
    git config --global user.email "<GITHUB NOREPLY EMAIL>"

The GitHub noreply address is recommended to avoid exposing the collaborator's personal email address in commit metadata.

Configuration can be verified with:

    git config --global --list

## 6. Local Repository

The QuantLab repository is cloned under:

    C:\QuantLab\QuantLab

The repository status is verified with:

    git status

Initial expected state before the first commit:

    On branch main
    No commits yet

## 7. Initial Repository Structure

The initial monorepo contains:

    collectors/
    analytics/
    database/
    shared/
    orchestration/
    tests/
    docs/

The existing Nasdaq Halt Collector is preserved separately during migration at:

    C:\QuantLab\nasdaq_halts

It must not be deleted until migration to the QuantLab monorepo has been completed and validated.

## 8. Installation Status and Remaining Stages

Completed stages:

1. Configure `.gitignore`.
2. Create initial repository documentation.
3. Perform first Git commit and push.
4. Configure GitHub Projects.
5. Migrate Nasdaq Halt Collector.
6. Establish Python environment management.
7. Deploy managed PostgreSQL.
8. Create the initial PostgreSQL database and schema migration.

Remaining stages:

1. Add second collaborator.
2. Configure database security and application users.
3. Integrate collectors with PostgreSQL.
4. Load and validate the five-year Nasdaq halt history.
5. Configure automated execution.
6. Configure on-demand execution.
7. Configure backup and restore procedures.
8. Configure Microsoft collaboration environment.
9. Build the database query interface.

## 9. GitHub Projects Configuration

A GitHub Project named `QuantLab` has been created and configured.

Workflow statuses:

- Backlog
- Ready
- In Progress
- Review / Test
- Done

Custom fields:

- Priority
- Component
- Environment
- Target date
- Owner

Initial deployment and platform tasks have been added to the project backlog.

Completed milestone:

- Configure GitHub repository

Current milestone:

- Configure GitHub Projects

## 10. Migration du collecteur Nasdaq Halts

Le projet historique local :

`C:\QuantLab\nasdaq_halts`

a été conservé intact comme copie de référence pendant la migration.

Le collecteur a été copié vers :

`C:\QuantLab\QuantLab\collectors\nasdaq_halts`

Les éléments suivants ont été migrés :

- code source Python;
- configuration non sensible;
- architecture spécifique du collecteur;
- spécification des métriques.

Les éléments suivants n'ont pas été ajoutés à Git :

- environnement virtuel `.venv`;
- données RAW;
- données processed;
- logs.

Les règles `.gitignore` ont été étendues afin d'exclure les données et logs de tous les composants QuantLab.

Après migration, le moteur V0.6 a été exécuté depuis son nouvel emplacement en utilisant temporairement l'environnement Python historique.

Résultat de validation :

- QVCG : PASS
- BCARU : PASS
- résultats métriques identiques à la baseline V0.6.

La migration du collecteur Nasdaq Halts vers le monorepo est validée.

## 11. Environnement Python du monorepo

Un environnement virtuel Python commun au monorepo QuantLab a été créé sous :

`C:\QuantLab\QuantLab\.venv`

Version Python de référence actuelle :

`Python 3.14.7`

L'environnement est activé sous Windows PowerShell avec :

    .\.venv\Scripts\Activate.ps1

Lorsque l'environnement est actif, la commande :

    where.exe python

doit retourner en premier :

    C:\QuantLab\QuantLab\.venv\Scripts\python.exe

Le répertoire `.venv` est exclu de Git et doit être recréé indépendamment sur chaque poste de développement.

Le collecteur Nasdaq Halts V0.6 utilise actuellement uniquement des modules de la bibliothèque standard Python et ne nécessite aucune dépendance Python externe.

Après création du nouvel environnement virtuel, le moteur V0.6 a été exécuté depuis :

    collectors\nasdaq_halts\src\calculate_halt_metrics.py

Résultat de validation :

- Événements bruts : 744
- Événements uniques : 744
- HALT Episodes : 744
- Tickers différents : 235
- Lignes quotidiennes : 322
- Jours de marché : 10
- Durées calculables : 742
- QVCG TEST : PASS
- BCARU TEST : PASS

Le monorepo QuantLab est donc autonome par rapport à l'ancien environnement virtuel situé sous `C:\QuantLab\nasdaq_halts`.

## 12. PostgreSQL DEV Environment

The initial QuantLab managed database is hosted using Azure Database for PostgreSQL Flexible Server.

Reference DEV configuration:

- Azure region: Canada Central
- PostgreSQL version: 17
- compute tier: Burstable
- compute size: B1ms
- storage: 32 GiB
- high availability: disabled
- backup retention: 7 days
- authentication: PostgreSQL authentication
- network access: public access restricted by Azure firewall rules
- transport security: TLS

Server endpoint:

    quantlab-postgres-dev.postgres.database.azure.com

Port:

    5432

Primary QuantLab database:

    quantlab

The database contains the following initial schemas:

    raw
    core
    analytics

The initial migration is located at:

    database\migrations\001_create_nasdaq_halts_schema.sql

It creates:

    raw.nasdaq_trade_halt
    core.nasdaq_halt_episode

### PostgreSQL Client Installation on Windows

PostgreSQL 17 client tools were installed using Windows Package Manager:

    winget install --id PostgreSQL.PostgreSQL.17 --exact

The client version can be verified with:

    psql --version

Reference validated version:

    psql (PostgreSQL) 17.11

If the PostgreSQL binary directory is not yet available in the current PowerShell `PATH`, it can be added temporarily with:

    $pgBin = "C:\Program Files\PostgreSQL\17\bin"
    $env:Path = "$pgBin;$env:Path"

### Connecting to Azure PostgreSQL

Example connection from PowerShell:

    psql "host=quantlab-postgres-dev.postgres.database.azure.com port=5432 dbname=quantlab user=quantlab_admin sslmode=require"

The password is entered interactively.

Passwords and database credentials must never be stored in:

- Git;
- GitHub;
- Markdown documentation;
- committed configuration files;
- source code.

A successful connection must report an SSL connection.

### Creating the QuantLab Database

During initial provisioning, the administrative connection is made to the default `postgres` database.

The QuantLab database is created with:

    CREATE DATABASE quantlab;

The session can then switch to the new database using:

    \c quantlab

### Applying Database Migrations

From a `psql` session connected to `quantlab`, the initial migration is executed with:

    \i 'C:/QuantLab/QuantLab/database/migrations/001_create_nasdaq_halts_schema.sql'

The migration was successfully validated against Azure PostgreSQL 17.

Validation confirmed:

- schema `raw`;
- schema `core`;
- schema `analytics`;
- table `raw.nasdaq_trade_halt`;
- table `core.nasdaq_halt_episode`;
- primary keys;
- natural-key uniqueness;
- foreign-key relationship;
- 1:1 uniqueness on `trade_halt_id`;
- data-integrity check constraints;
- expected indexes.

Future migrations must be reviewed, committed to Git, and tested in DEV before promotion to other environments.
