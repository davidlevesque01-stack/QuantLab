# QuantLab — Installation and Deployment Procedure

## 1. Purpose

This document defines the reproducible installation procedure for a QuantLab development workstation.

The objective is to allow an authorized collaborator to configure a new workstation and obtain a consistent QuantLab development environment.

Secrets, passwords, recovery codes, tokens and database credentials must never be recorded in this document.

## 2. Current Reference Environment

Initial reference workstation:

- Operating system: Windows
- Project root: `C:\QuantLab\QuantLab`
- Source control: Git
- Remote repository: private GitHub repository `QuantLab`
- Development environment: Visual Studio Code
- Python: 3.14.7
- PostgreSQL client: 17
- Managed database: Azure Database for PostgreSQL Flexible Server
- Authentication: individual accounts; GitHub 2FA enabled

## 3. GitHub Account

Each collaborator must use an individual GitHub account.

Requirements:

- verified email address;
- Two-Factor Authentication (2FA) enabled;
- no shared account credentials.

The initial QuantLab repository is configured as private.

The repository may initially be owned by an individual account and transferred later to a GitHub Organization if QuantLab moves to a corporate environment.

## 4. Git Installation

Git for Windows is installed on the workstation.

Verify with:

```powershell
git --version
```

Reference validated version:

```text
git version 2.55.0.windows.5
```

## 5. Git Identity

Git identity is configured globally:

```powershell
git config --global user.name "<USER NAME>"
git config --global user.email "<GITHUB NOREPLY EMAIL>"
```

The GitHub noreply address is recommended to avoid exposing a collaborator's personal email address in commit metadata.

Verify with:

```powershell
git config --global --list
```

## 6. GitHub CLI

GitHub CLI is used for repository and GitHub Project administration when required.

Verify with:

```powershell
gh --version
```

If the GitHub CLI binary directory is not yet available in the current PowerShell `PATH`, it can be added temporarily with:

```powershell
$ghBin = "C:\Program Files\GitHub CLI"
$env:Path = "$ghBin;$env:Path"
```

Authentication can be verified with:

```powershell
gh auth status
```

Authentication tokens and credentials must never be stored in project documentation.

## 7. Local Repository

The QuantLab repository is located under:

```text
C:\QuantLab\QuantLab
```

Repository status is verified with:

```powershell
git status
```

The authoritative branch is currently:

```text
main
```

Normal development changes must be reviewed before staging and committing.

## 8. Repository Structure

The QuantLab monorepo currently follows this structure:

```text
QuantLab/
|
+-- collectors/
|   +-- nasdaq_halts/
|
+-- analytics/
|
+-- database/
|   +-- migrations/
|   +-- queries/
|   +-- schemas/
|
+-- shared/
|   +-- config/
|   +-- database/
|   +-- logging/
|   +-- utilities/
|
+-- orchestration/
|   +-- jobs/
|
+-- tests/
|   +-- integration/
|
+-- docs/
|
+-- README.md
+-- pyproject.toml
+-- .gitignore
```

The historical local Nasdaq Halt project remains available at:

```text
C:\QuantLab\nasdaq_halts
```

The migration to the monorepo has been completed and validated.

The historical project is retained temporarily as a reference copy. It must not be deleted until its removal is explicitly approved after the PostgreSQL integration and historical-data validation stages.

## 9. Installation Status and Remaining Stages

### Completed stages

1. Configure `.gitignore`.
2. Create initial repository documentation.
3. Perform initial Git commits and pushes.
4. Configure GitHub Projects.
5. Migrate Nasdaq Halt Collector to the monorepo.
6. Establish the common Python virtual environment.
7. Deploy Azure Database for PostgreSQL Flexible Server.
8. Create the `quantlab` database.
9. Apply and validate PostgreSQL migration `001`.
10. Correct and validate halt close status through migration `002`.
11. Configure least-privilege PostgreSQL application roles.
12. Install and validate Psycopg 3 connectivity.
13. Validate PostgreSQL loading against the 744-event baseline.
14. Validate PostgreSQL idempotence.
15. Validate fractional-second timestamp preservation.
16. Configure Visual Studio Code PostgreSQL access.
17. Establish reusable SQL query storage under `database/queries/`.
18. Implement Nasdaq-specific PostgreSQL persistence.
19. Integrate the V0.7 historical processing pipeline directly with PostgreSQL.
20. Validate direct XML-to-PostgreSQL loading against 744 events.
21. Validate XML source-file provenance in PostgreSQL.
22. Validate direct V0.7 persistence idempotence.

### Current stage

Complete and document the Nasdaq Halt V0.7 PostgreSQL integration checkpoint.

The historical XML processing path now writes directly to PostgreSQL without using processed CSV files as the integration layer.

The live/current Nasdaq acquisition path must still be reviewed before the broader collector integration task is considered fully complete.

### Remaining stages

1. Review and integrate the live/current Nasdaq acquisition path with the validated PostgreSQL persistence architecture.
2. Load the five-year Nasdaq halt history.
3. Validate the five-year dataset and current 1:1 RAW-to-CORE assumption.
4. Validate Python deduplication versus the PostgreSQL RAW natural key.
5. Validate timezone semantics.
6. Model the authoritative market calendar.
7. Create Nasdaq Halt analytical database objects.
8. Build the broader database query interface.
9. Configure automated execution.
10. Configure on-demand execution.
11. Configure and validate backup and restore procedures.
12. Configure the Microsoft collaboration environment.
13. Add the second collaborator when available.
14. Prepare TEST and PROD security/infrastructure when required.

## 10. GitHub Projects Configuration

A GitHub Project named `QuantLab` has been created and configured.

Workflow statuses:

```text
Backlog
Ready
In Progress
Review / Test
Done
Cancelled
```

Custom fields include:

```text
Priority
Component
Environment
Target date
Owner
```

Standard Priority values:

```text
Critical
High
Medium
Low
```

Standard Component values include:

```text
Infrastructure
GitHub
Database
Collector
Analytics
Orchestration
Documentation
Collaboration
Security
```

Standard Environment values:

```text
DEV
TEST
PROD
N/A
```

GitHub Issues are used for implementation work, validation activities and other actionable backlog items.

The current collector work is focused on completing the Nasdaq Halt PostgreSQL integration after validation of the V0.7 historical processing path.

## 11. Migration du collecteur Nasdaq Halts

Le projet historique local :

```text
C:\QuantLab\nasdaq_halts
```

a été conservé intact comme copie de référence pendant la migration.

Le collecteur a été migré vers :

```text
C:\QuantLab\QuantLab\collectors\nasdaq_halts
```

Les éléments suivants ont été migrés :

- code source Python;
- configuration non sensible;
- architecture spécifique du collecteur;
- spécification des métriques;
- modèle de données documentaire.

Les éléments suivants ne sont pas ajoutés à Git :

- environnement virtuel `.venv`;
- données RAW;
- données processed;
- logs;
- secrets.

Les règles `.gitignore` excluent les données et logs locaux des composants QuantLab.

Après migration, le moteur V0.6 a d'abord été exécuté depuis son nouvel emplacement afin d'établir le baseline de non-régression.

Le pipeline a ensuite évolué vers V0.7 avec persistance PostgreSQL directe.

Résultats V0.7 de validation :

```text
Événements bruts       : 744
Événements uniques     : 744
HALT Episodes          : 744
Tickers différents     : 235
Lignes quotidiennes    : 322
Jours de marché        : 10
Durées calculables     : 742
```

Statuts de clôture validés :

```text
YES                    : 15
NO                     : 697
UNKNOWN                : 2
MULTI_DAY              : 30
TOTAL                  : 744
```

Tests de non-régression :

```text
QVCG TEST              : PASS
BCARU TEST             : PASS
```

Persistance PostgreSQL après nettoyage de la base DEV :

```text
RAW inserted           : 744
RAW existing           : 0
CORE inserted          : 744
CORE existing          : 0
```

Une réexécution contre les mêmes données a validé l'idempotence :

```text
RAW inserted           : 0
RAW existing           : 744
CORE inserted          : 0
CORE existing          : 744
```

La provenance `source_file` a également été validée avec les noms réels des fichiers XML historiques.

## 12. Python Environment

A common Python virtual environment is maintained at:

```text
C:\QuantLab\QuantLab\.venv
```

Reference Python version:

```text
Python 3.14.7
```

### Activation

From PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

When active, verify the Python executable with:

```powershell
where.exe python
```

The first result should be:

```text
C:\QuantLab\QuantLab\.venv\Scripts\python.exe
```

The `.venv` directory is excluded from Git and must be recreated independently on each development workstation.

### Project dependencies

Python project dependencies are declared in:

```text
pyproject.toml
```

The current PostgreSQL dependency is:

```text
psycopg[binary]>=3.3,<4
```

The validated installed Psycopg version in the current DEV environment is:

```text
3.3.4
```

The Nasdaq V0.7 processing pipeline uses Psycopg for PostgreSQL persistence.

Dependencies should be installed into the monorepo virtual environment rather than globally.

## 13. PostgreSQL DEV Environment

The initial QuantLab managed database is hosted using Azure Database for PostgreSQL Flexible Server.

Reference DEV configuration:

- Azure region: Canada Central
- PostgreSQL version: 17
- compute tier: Burstable
- compute size: B1ms
- vCPU: 1
- memory: 2 GiB
- storage: 32 GiB
- high availability: disabled
- backup retention: 7 days
- authentication: PostgreSQL authentication
- network access: public access restricted by Azure firewall rules
- transport security: TLS

Server endpoint:

```text
quantlab-postgres-dev.postgres.database.azure.com
```

Port:

```text
5432
```

Primary QuantLab database:

```text
quantlab
```

Current schemas:

```text
raw
core
analytics
```

## 14. PostgreSQL Client Installation on Windows

PostgreSQL 17 client tools were installed using Windows Package Manager:

```powershell
winget install --id PostgreSQL.PostgreSQL.17 --exact
```

Verify with:

```powershell
psql --version
```

Reference validated version:

```text
psql (PostgreSQL) 17.11
```

If the PostgreSQL binary directory is not yet available in the current PowerShell `PATH`, it can be added temporarily with:

```powershell
$pgBin = "C:\Program Files\PostgreSQL\17\bin"
$env:Path = "$pgBin;$env:Path"
```

A permanent `PATH` configuration may be performed separately on each workstation.

## 15. Connecting to Azure PostgreSQL

Administrative connection example:

```powershell
psql "host=quantlab-postgres-dev.postgres.database.azure.com port=5432 dbname=quantlab user=quantlab_admin sslmode=require"
```

The password is entered interactively.

A successful connection must report an SSL/TLS connection.

Passwords and database credentials must never be stored in:

- Git;
- GitHub;
- Markdown documentation;
- committed configuration files;
- source code;
- PowerShell scripts committed to the repository.

The administrator account must not be used by the collector for normal application execution.

## 16. Creating the QuantLab Database

During initial provisioning, the administrative connection is made to the default `postgres` database.

The QuantLab database was created with:

```sql
CREATE DATABASE quantlab;
```

The session can switch to the QuantLab database with:

```sql
\c quantlab
```

This provisioning step is already completed in the current DEV environment.

## 17. Database Migrations

Database migrations are maintained under:

```text
database/migrations/
```

### Migration 001

```text
database/migrations/001_create_nasdaq_halts_schema.sql
```

It creates:

```text
raw.nasdaq_trade_halt
core.nasdaq_halt_episode
```

along with the required schemas, indexes and integrity constraints.

It was successfully applied and validated against Azure PostgreSQL 17.

### Migration 002

```text
database/migrations/002_fix_nasdaq_halt_close_status.sql
```

It replaces the original boolean halt-close representation with:

```text
halt_close_status VARCHAR(20)
```

and permits:

```text
YES
NO
UNKNOWN
MULTI_DAY
```

Migration `002` was successfully applied and validated in DEV.

### Migration execution

From `psql` connected to `quantlab`:

```sql
\i 'C:/QuantLab/QuantLab/database/migrations/001_create_nasdaq_halts_schema.sql'
```

then:

```sql
\i 'C:/QuantLab/QuantLab/database/migrations/002_fix_nasdaq_halt_close_status.sql'
```

Migrations must:

1. be versioned in Git;
2. be reviewed before execution;
3. be tested in DEV;
4. be documented;
5. be executed in numeric order;
6. not be modified retroactively after they have been applied.

The future Nasdaq Halt analytics migration is currently reserved as:

```text
003_create_nasdaq_halts_analytics.sql
```

It must not be implemented until the market-calendar and multi-day semantics have been validated.

## 18. PostgreSQL Application Security

QuantLab uses separate administrative and application identities.

### Application role

The current application role is:

```text
quantlab_collector
```

It is configured as a `NOLOGIN` role.

It contains the privileges required for the collector to access the relevant RAW and CORE objects.

### DEV login

The current DEV application login is:

```text
quantlab_collector_dev
```

It is a member of:

```text
quantlab_collector
```

Application code must use the application identity rather than the PostgreSQL administrator account.

Passwords are created and entered interactively and must never be added to project documentation or Git.

## 19. PostgreSQL Environment Variables

The shared Python database connection reads:

```text
QUANTLAB_DB_HOST
QUANTLAB_DB_PORT
QUANTLAB_DB_NAME
QUANTLAB_DB_USER
QUANTLAB_DB_PASSWORD
```

For the current DEV PowerShell session, the non-secret variables can be configured with:

```powershell
$env:QUANTLAB_DB_HOST = "quantlab-postgres-dev.postgres.database.azure.com"
$env:QUANTLAB_DB_PORT = "5432"
$env:QUANTLAB_DB_NAME = "quantlab"
$env:QUANTLAB_DB_USER = "quantlab_collector_dev"
```

The password should be requested securely rather than written literally into shell history:

```powershell
$securePassword = Read-Host "PostgreSQL password for quantlab_collector_dev" -AsSecureString
$env:QUANTLAB_DB_PASSWORD = [System.Net.NetworkCredential]::new("", $securePassword).Password
```

Environment variables configured this way are session-local and must be configured again in a new PowerShell session unless a future secrets-management mechanism is introduced.

No production secret-management decision is implied by this DEV procedure.

## 20. Shared Python PostgreSQL Connection

Common PostgreSQL connectivity is implemented under:

```text
shared/database/
```

Current files:

```text
shared/database/__init__.py
shared/database/connection.py
```

The connection uses Psycopg 3 with:

```text
sslmode=require
```

The connection layer reads its configuration from the environment variables defined in the previous section.

Connectivity from the monorepo virtual environment to Azure PostgreSQL using the DEV application account has been successfully validated.

## 21. Nasdaq PostgreSQL Persistence V0.7

Nasdaq-specific PostgreSQL persistence is implemented in:

```text
collectors/nasdaq_halts/src/nasdaq_postgresql.py
```

It uses the shared connection layer from:

```text
shared/database/
```

The module persists:

```text
unique_events
```

to:

```text
raw.nasdaq_trade_halt
```

and:

```text
episodes
```

to:

```text
core.nasdaq_halt_episode
```

The writer implements:

- RAW natural-key conflict handling;
- idempotent insertion;
- retrieval of existing RAW identifiers;
- XML `source_file` provenance;
- close-status validation;
- strict RAW-to-CORE relationship validation;
- transactional persistence.

The current RAW natural key is:

```text
symbol
halt_date
halt_time
reason_code
market
```

The current CORE model assumes:

```text
1 RAW event -> 1 CORE episode
```

This assumption is validated on the 744-event V0.7 dataset but must be revalidated against the complete historical dataset.

If the writer cannot associate an episode unambiguously with exactly one RAW event under the current model, execution fails explicitly rather than selecting an arbitrary relationship.

## 22. Running the Nasdaq V0.7 Processing Pipeline

Because the V0.7 processor imports modules from the QuantLab monorepo root, the reference execution is performed from:

```text
C:\QuantLab\QuantLab
```

with the monorepo virtual environment active.

Reference command:

```powershell
python -m collectors.nasdaq_halts.src.calculate_halt_metrics
```

Direct execution using the Python file path is not the reference invocation.

### PostgreSQL requirement

In the current V0.7 implementation, PostgreSQL persistence is invoked directly by the processing pipeline.

Therefore, before running the command, the following environment variables must exist in the current PowerShell session:

```text
QUANTLAB_DB_HOST
QUANTLAB_DB_PORT
QUANTLAB_DB_NAME
QUANTLAB_DB_USER
QUANTLAB_DB_PASSWORD
```

The workstation must also:

- have network access to the PostgreSQL endpoint;
- be permitted by the Azure firewall;
- have Psycopg installed in the active virtual environment;
- use an application account with the required RAW and CORE privileges.

A PostgreSQL connection or persistence error causes the current V0.7 execution to fail rather than silently bypassing database persistence.

This behavior reflects the current implementation and should be reconsidered explicitly if a future offline/non-database processing mode is required.

### Validated execution

A clean direct V0.7 load produced:

```text
RAW inserted   : 744
RAW existing   : 0
CORE inserted  : 744
CORE existing  : 0
```

A subsequent execution produced:

```text
RAW inserted   : 0
RAW existing   : 744
CORE inserted  : 0
CORE existing  : 744
```

The non-regression tests remained:

```text
QVCG TEST : PASS
BCARU TEST: PASS
```

## 23. Transitional PostgreSQL CSV Loader

The previous validation loader remains available at:

```text
collectors/nasdaq_halts/src/load_postgresql.py
```

Reference invocation:

```powershell
python -m collectors.nasdaq_halts.src.load_postgresql
```

It reads:

```text
collectors/nasdaq_halts/data/processed/tradehalts.csv
collectors/nasdaq_halts/data/processed/halt_episodes.csv
```

and writes to:

```text
raw.nasdaq_trade_halt
core.nasdaq_halt_episode
```

This loader was used to validate the initial PostgreSQL foundation against the known processed dataset.

It is retained as a validation and migration utility.

It is not the preferred V0.7 integration path.

The current direct processing path is:

```text
XML RAW
        |
        v
Python parsing / normalization
        |
        v
PostgreSQL RAW
        |
        v
PostgreSQL CORE
```

Processed CSV files remain useful for diagnostics, exports and non-regression testing.

## 24. Visual Studio Code PostgreSQL Tools

The Microsoft PostgreSQL extension is installed in Visual Studio Code for DEV database exploration.

The DEV connection is configured against:

```text
quantlab-postgres-dev.postgres.database.azure.com
```

and database:

```text
quantlab
```

The extension can be used to:

- browse PostgreSQL schemas and tables;
- inspect table data;
- execute SQL;
- display result grids;
- execute reusable `.sql` files.

Reusable SQL files are stored under:

```text
database/queries/
```

Current Nasdaq Halt queries are stored under:

```text
database/queries/nasdaq_halts/
```

including:

```text
explore_halt_episodes.sql
get_halts_per_symbol_and_date.sql
visualize_halts_table.sql
```

If a saved SQL file is connected correctly but query execution incorrectly targets an `Untitled` editor, reload the Visual Studio Code window using:

```text
Developer: Reload Window
```

then reopen the saved SQL file and reconnect it if necessary.

## 25. UTF-8 PowerShell Display

QuantLab documentation and source files should be maintained in UTF-8.

If UTF-8 text is displayed incorrectly in a PowerShell terminal, configure the current terminal session with:

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding  = [System.Text.Encoding]::UTF8
```

Markdown files can be explicitly read as UTF-8 with:

```powershell
Get-Content .\docs\installation.md -Raw -Encoding UTF8
```

This affects terminal interpretation/display and does not by itself indicate that the underlying file is corrupted.

## 26. Next Implementation Stage

The V0.7 historical processing path now performs direct PostgreSQL persistence and has been validated against the 744-event baseline.

The immediate next technical checkpoint is to review the live/current Nasdaq acquisition path and determine how it should use the same persistence architecture.

After that integration is validated, the next major data stage is the five-year historical load.

The five-year validation must specifically test:

- RAW natural-key uniqueness;
- Python versus PostgreSQL deduplication semantics;
- RAW-to-CORE cardinality;
- overlapping/merged episodes;
- source-file provenance;
- timestamp precision;
- timezone semantics;
- multi-day behavior;
- market-calendar semantics;
- full-volume idempotence.

The historical dataset must not be considered certified until these checks have been completed.
