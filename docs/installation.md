# QuantLab — Installation and Deployment Procedure

## 1. Purpose

This document defines the reproducible installation and development procedure for a QuantLab workstation and its current PostgreSQL integration.

The objective is to allow an authorized collaborator to configure a compatible environment and reproduce the current validated QuantLab Nasdaq workflow.

Secrets, passwords, recovery codes, tokens and database credentials must never be recorded in this document.

---

## 2. Current Reference Environment

Reference workstation:

- Operating system: Windows
- Project root: `C:\QuantLab\QuantLab`
- Source control: Git
- Remote repository: private GitHub repository `QuantLab`
- Development environment: Visual Studio Code
- Python: 3.14.7
- PostgreSQL client: 17
- Managed database: Azure Database for PostgreSQL Flexible Server
- Authentication: individual accounts
- GitHub 2FA: enabled
- Current shell: Windows PowerShell 5.1
- Repository text standard: UTF-8
- `.editorconfig`: enabled

PowerShell 7 evaluation is deferred until the current Nasdaq/PostgreSQL checkpoint is fully documented and committed.

---

## 3. GitHub Account

Each collaborator must use an individual GitHub account.

Requirements:

- verified email address;
- Two-Factor Authentication enabled;
- no shared credentials.

The repository may initially belong to an individual account and later be transferred to a GitHub Organization without changing the application architecture.

---

## 4. Git Installation

Verify:

```powershell
git --version
```

Reference validated version:

```text
git version 2.55.0.windows.5
```

---

## 5. Git Identity

Configure:

```powershell
git config --global user.name "<USER NAME>"
git config --global user.email "<GITHUB NOREPLY EMAIL>"
```

Verify:

```powershell
git config --global --list
```

A GitHub noreply address is recommended when collaborators do not want personal email addresses exposed in commit metadata.

---

## 6. GitHub CLI

Verify:

```powershell
gh --version
```

If required for the current PowerShell session:

```powershell
$ghBin = "C:\Program Files\GitHub CLI"
$env:Path = "$ghBin;$env:Path"
```

Verify authentication:

```powershell
gh auth status
```

Authentication tokens must never be stored in project documentation.

---

## 7. Local Repository

Reference path:

```text
C:\QuantLab\QuantLab
```

Verify:

```powershell
git status
```

Reference branch:

```text
main
```

Normal changes should be reviewed before staging and committing.

---

## 8. Repository Structure

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
+-- .editorconfig
```

The historical local project may remain temporarily available under:

```text
C:\QuantLab\nasdaq_halts
```

as a reference copy until its removal is explicitly approved.

---

## 9. Current Implementation Status

Completed major stages include:

1. Git repository creation and GitHub synchronization.
2. GitHub Projects configuration.
3. Nasdaq Halt Collector migration into the monorepo.
4. Common Python virtual environment.
5. Azure PostgreSQL DEV deployment.
6. `quantlab` database creation.
7. Initial PostgreSQL schema deployment.
8. Least-privilege application-role configuration.
9. Psycopg 3 integration.
10. Historical and live parser unification.
11. Direct Python-to-PostgreSQL persistence.
12. CORE-to-RAW relationship table.
13. RAW and CORE V1.1 migration stages.
14. Resumption observation table.
15. Full historical Nasdaq load and analysis.
16. RAW V1.2 natural-key consolidation.
17. CORE V1.2 identity stabilization.
18. `UNIQUE NULLS NOT DISTINCT` resumption fix.
19. Canonical resumption data-quality policy.
20. Full-history sequential idempotence validation.
21. QVCG regression validation.
22. BCARU historical fixture redesign and validation.
23. Referential-integrity validation.
24. PostgreSQL advisory-lock concurrency hardening.
25. Concurrency test with two independent PostgreSQL connections.
26. Migration `006_nasdaq_persistence_v1_2.sql` creation and rollback validation.
27. `.editorconfig` creation for UTF-8 handling.

Current technical checkpoint:

```text
Nasdaq Data Model V1.2
PostgreSQL Persistence V1.2
```

---

## 10. Python Environment

Reference virtual environment:

```text
C:\QuantLab\QuantLab\.venv
```

Reference Python:

```text
Python 3.14.7
```

Activate:

```powershell
.\.venv\Scripts\Activate.ps1
```

Verify:

```powershell
where.exe python
python --version
```

The first Python path should point to:

```text
C:\QuantLab\QuantLab\.venv\Scripts\python.exe
```

The `.venv` directory is excluded from Git.

---

## 11. Project Dependencies

Dependencies are declared in:

```text
pyproject.toml
```

Current PostgreSQL dependency:

```text
psycopg[binary]>=3.3,<4
```

Reference validated Psycopg version:

```text
3.3.4
```

Dependencies should be installed into the repository virtual environment rather than globally.

---

## 12. PostgreSQL DEV Environment

Reference configuration:

- Azure Database for PostgreSQL Flexible Server
- Region: Canada Central
- PostgreSQL: 17
- Compute tier: Burstable
- Size: B1ms
- 1 vCPU
- 2 GiB memory
- 32 GiB storage
- High availability: disabled
- Backup retention: 7 days
- Public access restricted by Azure firewall
- TLS required

Endpoint:

```text
quantlab-postgres-dev.postgres.database.azure.com
```

Port:

```text
5432
```

Database:

```text
quantlab
```

Schemas:

```text
raw
core
analytics
```

---

## 13. PostgreSQL Client Installation

Reference client:

```text
psql 17.11
```

Example installation:

```powershell
winget install --id PostgreSQL.PostgreSQL.17 --exact
```

Verify:

```powershell
psql --version
```

If required for the current PowerShell session:

```powershell
$pgBin = "C:\Program Files\PostgreSQL\17\bin"
$env:Path = "$pgBin;$env:Path"
```

---

## 14. Administrative PostgreSQL Connection

Reference command:

```powershell
psql "host=quantlab-postgres-dev.postgres.database.azure.com port=5432 dbname=quantlab user=quantlab_admin sslmode=require"
```

The password is entered interactively.

The administrator account is reserved for provisioning, migrations, role management and administrative operations.

Normal collector execution must use the application identity.

---

## 15. PostgreSQL Application Security

Application role:

```text
quantlab_collector
```

Type:

```text
NOLOGIN
```

DEV login:

```text
quantlab_collector_dev
```

The DEV login inherits its permissions through membership in the application role.

---

## 16. PostgreSQL Environment Variables

The shared Python database layer reads:

```text
QUANTLAB_DB_HOST
QUANTLAB_DB_PORT
QUANTLAB_DB_NAME
QUANTLAB_DB_USER
QUANTLAB_DB_PASSWORD
```

Example non-secret variables:

```powershell
$env:QUANTLAB_DB_HOST = "quantlab-postgres-dev.postgres.database.azure.com"
$env:QUANTLAB_DB_PORT = "5432"
$env:QUANTLAB_DB_NAME = "quantlab"
$env:QUANTLAB_DB_USER = "quantlab_collector_dev"
```

Secure interactive password entry:

```powershell
$securePassword = Read-Host "PostgreSQL password for quantlab_collector_dev" -AsSecureString
$env:QUANTLAB_DB_PASSWORD = [System.Net.NetworkCredential]::new("", $securePassword).Password
```

These values are session-local.

No secret should be committed to the repository.

---

## 17. Shared PostgreSQL Connection

Common connectivity is implemented under:

```text
shared/database/
```

Current files include:

```text
shared/database/__init__.py
shared/database/connection.py
```

The connection uses Psycopg 3 and TLS.

---

## 18. Database Migrations

Migration directory:

```text
database/migrations/
```

Current files:

```text
001_create_nasdaq_halts_schema.sql
002_core_episode_event.sql
002_fix_nasdaq_halt_close_status.sql
003_update_nasdaq_raw_natural_key_v1_1.sql
004_update_nasdaq_core_natural_key_v1_1.sql
005_create_nasdaq_resumption.sql
006_nasdaq_persistence_v1_2.sql
```

Two historical migrations use prefix `002`.

This numbering anomaly is documented and the files must not be renamed retroactively.

Future migrations must use a new available number.

### Migration rules

Migrations must:

1. be versioned in Git;
2. be reviewed;
3. be tested in DEV;
4. be documented;
5. be executed in the appropriate historical order;
6. not be modified retroactively after application.

### Reference execution

```powershell
psql "host=quantlab-postgres-dev.postgres.database.azure.com port=5432 dbname=quantlab user=quantlab_admin sslmode=require" `
    -v ON_ERROR_STOP=1 `
    -f .\database\migrations\<migration>.sql
```

---

## 19. Migration 006 — Nasdaq Persistence V1.2

File:

```text
database/migrations/006_nasdaq_persistence_v1_2.sql
```

Purpose:

- consolidate RAW duplicates under V1.2 identity;
- preserve CORE/RAW relationships;
- apply RAW V1.2 uniqueness;
- apply CORE V1.2 uniqueness;
- deduplicate resumption observations;
- apply `UNIQUE NULLS NOT DISTINCT`;
- validate referential integrity;
- serialize with Nasdaq persistence using the same advisory lock.

PostgreSQL requirement:

```text
PostgreSQL 15+
```

because `UNIQUE NULLS NOT DISTINCT` is required.

A temporary test copy was executed completely against DEV with the final transaction changed to `ROLLBACK`. All statements and validation blocks completed successfully.

---

## 20. Nasdaq PostgreSQL Persistence V1.2

Module:

```text
collectors/nasdaq_halts/src/nasdaq_postgresql.py
```

Current version marker:

```text
VERSION = "1.2"
```

The module persists:

```text
canonical HALTs
-> raw.nasdaq_trade_halt

resumption observations
-> raw.nasdaq_resumption

business episodes
-> core.nasdaq_halt_episode

episode/RAW relationships
-> core.nasdaq_halt_episode_event
```

---

## 21. Running the Historical Nasdaq Pipeline

Reference execution is from the monorepo root:

```text
C:\QuantLab\QuantLab
```

with the virtual environment active.

Command:

```powershell
python -m collectors.nasdaq_halts.src.calculate_halt_metrics
```

The PostgreSQL environment variables must be available in the current shell.

Network access and Azure firewall authorization are required.

A PostgreSQL error causes the current persistence-enabled execution to fail rather than silently skipping database persistence.

---

## 22. Full Historical Validation

Validated historical period:

```text
2020-01-01 -> 2026-08-28
```

Source XML files:

```text
2432
```

Observed market days:

```text
1738
```

Validated results:

```text
Raw source events        : 69186
Distinct observations    : 68170
Canonical RAW HALTs      : 68072
CORE episodes            : 68017
Distinct tickers         : 9718
Daily rows               : 50000
Calculated durations     : 67983
```

Close status:

```text
YES       : 1777
NO        : 62902
UNKNOWN   : 34
```

---

## 23. Reference Idempotence Result

Current reference rerun:

```text
RAW inserted          : 0
RAW updated           : 0
RAW unchanged         : 68072

RESUMPTION inserted   : 0
RESUMPTION existing   : 68147

CORE inserted         : 0
CORE updated          : 0
CORE unchanged        : 68017
```

Regression tests:

```text
QVCG TEST  : PASS
BCARU TEST : PASS
```

Any future change to Nasdaq persistence should preserve or intentionally update this checkpoint.

---

## 24. CORE V1.2 Identity

CORE natural key:

```text
symbol
market
halt_start
```

`reason_code` is descriptive and not part of CORE identity.

The explicit relationship table supports:

```text
1 CORE episode -> N RAW events
```

This replaces the earlier provisional 1:1 assumption.

---

## 25. RAW V1.2 Identity

Canonical RAW natural key:

```text
symbol
market
halt_date
halt_time
reason_code
```

Multiple distinct source observations may map to one RAW HALT.

This is expected behavior.

---

## 26. Resumption Observation Identity

Observation identity:

```text
symbol
market
halt_date
halt_time
reason_code
resumption_date
resumption_quote_time
resumption_trade_time
```

PostgreSQL uniqueness uses:

```sql
UNIQUE NULLS NOT DISTINCT
```

This is required for correct idempotence when quote or trade resumption times are NULL.

---

## 27. Canonical Resumption Policy

Canonical RAW resumption selection distinguishes:

```text
complete valid
partial admissible
invalid / unusable
```

For multiple valid complete observations, the latest valid `halt_end` is selected.

Resumption fields are selected atomically from one observation.

Invalid source observations remain preserved in `raw.nasdaq_resumption`.

If every available resumption is invalid, the canonical RAW resumption fields are NULL.

---

## 28. Concurrency Control

The Nasdaq persistence transaction acquires:

```sql
pg_advisory_xact_lock(716203, 1)
```

Migration 006 acquires the same lock.

The lock is held until `COMMIT` or `ROLLBACK`.

A two-connection test validated blocking behavior:

```text
holder: lock acquired
holder: transaction completed
waiter: lock acquired after 5.03 seconds
waiter: transaction completed
```

This protects cooperating Nasdaq processes from lookup/insert races across the whole persistence transaction.

---

## 29. Referential Integrity Validation

Current validated checks:

```text
broken CORE -> RAW refs         : 0
broken relation -> CORE refs    : 0
broken relation -> RAW refs     : 0
duplicate relationship pairs    : 0
```

These checks should remain part of future validation after schema or persistence changes.

---

## 30. BCARU Regression Fixture

BCARU uses a historical fixture through:

```text
2026-08-27
```

The fixture validates:

```text
21 CORE episodes
13 dates
```

and separately validates the 2026-08-03 close status.

This fixture is intentionally fixed so future source dates do not invalidate the historical regression test.

---

## 31. Transitional CSV Loader

Legacy loader:

```text
collectors/nasdaq_halts/src/load_postgresql.py
```

Reference invocation:

```powershell
python -m collectors.nasdaq_halts.src.load_postgresql
```

It is retained as a migration/validation utility.

It is not the production integration path.

---

## 32. SQL Query Tools

Reusable SQL is stored under:

```text
database/queries/
```

Nasdaq-specific queries:

```text
database/queries/nasdaq_halts/
```

These files are used for exploration, validation, integrity checks, diagnostics and provenance queries.

Visual Studio Code with the PostgreSQL extension remains a supported DEV query tool.

---

## 33. UTF-8 and PowerShell 5.1

The repository includes:

```text
.editorconfig
```

Current settings include:

```text
charset = utf-8
```

PowerShell 5.1 can write a UTF-8 BOM when using:

```powershell
Set-Content -Encoding utf8
```

This previously caused a SQL migration test to fail because `psql` interpreted the BOM as text.

For files requiring UTF-8 without BOM, use:

```powershell
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

[System.IO.File]::WriteAllText(
    $path,
    $content,
    $utf8NoBom
)
```

PowerShell 7 can be evaluated later as the preferred shell once the current PostgreSQL checkpoint is committed.

---

## 34. `.editorconfig`

Repository file:

```text
.editorconfig
```

Reference content includes:

```text
root = true

[*]
charset = utf-8
end_of_line = crlf
insert_final_newline = true
trim_trailing_whitespace = true
```

SQL and Python files are explicitly covered by UTF-8 rules.

---

## 35. Current Remaining Stages

Major remaining work after the V1.2 persistence checkpoint:

1. Update all remaining project and collector documentation.
2. Apply/record the final V1.2 migration state consistently in DEV if required by the chosen migration-tracking procedure.
3. Re-run the full idempotence checkpoint after any final database migration execution.
4. Review Git status and commit the V1.2 checkpoint.
5. Push the validated checkpoint.
6. Model the official market calendar.
7. Build PostgreSQL analytics.
8. Define backup and restore procedures.
9. Implement centralized scheduled execution.
10. Implement controlled on-demand execution.
11. Prepare TEST and PROD when required.
12. Define production secrets management.
13. Formalize Nasdaq timezone semantics.
14. Evaluate PowerShell 7 for the standard Windows development shell.

---

## 36. Current Checkpoint

Current validated state:

```text
Data Model V1.2
PostgreSQL Persistence V1.2
```

Validation status:

```text
Full historical processing          : PASS
RAW V1.2 identity                    : PASS
Resumption observation model         : PASS
CORE V1.2 identity                   : PASS
CORE -> RAW relationships            : PASS
Canonical resumption policy          : PASS
Invalid source observation retention : PASS
Sequential idempotence               : PASS
Referential integrity                : PASS
Concurrency advisory lock            : PASS
Migration 006 rollback validation    : PASS
QVCG regression                      : PASS
BCARU historical fixture             : PASS
Fractional timestamps                : PASS
```
