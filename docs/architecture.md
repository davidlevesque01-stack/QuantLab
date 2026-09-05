# QuantLab — System Architecture

## 1. Purpose

QuantLab is a collaborative quantitative data platform designed to acquire, preserve, normalize, store, analyze, and model financial and public datasets.

The architecture initially supports two independent remote collaborators while remaining portable to a future corporate environment.

This document is authoritative for major platform-level architectural decisions. Component-specific implementation details belong in the corresponding technical documents.

---

## 2. Architecture Principles

QuantLab follows these principles:

1. Source code is separated from production data.
2. GitHub is the authoritative source for code and technical documentation.
3. PostgreSQL is the authoritative source for structured production data.
4. Original immutable RAW source files are retained when required for provenance and rebuildability.
5. Collectors operate as independent components.
6. Analytics are separated from acquisition and source normalization.
7. Common functionality is centralized in shared components.
8. Application processes follow the principle of least privilege.
9. Credentials and secrets must never be committed to Git.
10. Database schema changes are implemented through versioned migrations.
11. Applied migrations are not modified retroactively.
12. The architecture must remain portable between infrastructure providers.
13. Database persistence must be idempotent when source data can be processed more than once.
14. Ambiguous data-model relationships must fail explicitly rather than silently discard or arbitrarily associate data.
15. Repeated source observations may enrich structured data without erasing previously known valid information.
16. Observation-level provenance and canonical business representations are distinct concepts.
17. Data-quality corrections must be explicit and testable.
18. PostgreSQL constraints remain the final protection for data integrity.
19. Concurrent cooperating Nasdaq persistence processes are serialized with an application-level PostgreSQL advisory lock.
20. Development tooling must preserve UTF-8 source files without introducing encoding artifacts.

---

## 3. Logical Architecture

Target production data flow:

```text
External Data Sources
        |
        v
    Collectors
        |
        +----> Immutable RAW Source Files
        |          |
        |          +----> Provenance / Rebuild
        |
        v
Parsing / Normalization
        |
        v
Observation Deduplication
        |
        +----------------------+
        |                      |
        v                      v
Structured RAW Canonical   Structured RAW Observations
        |                      |
        +----------+-----------+
                   |
                   v
             PostgreSQL CORE
                   |
                   v
                Analytics
                   |
             +-----+-----+
             |           |
           Models      Reports
```

Processed CSV files may remain available for validation, diagnostics, exports and non-regression testing, but they are not the production integration layer between collectors and PostgreSQL.

---

## 4. Repository Architecture

QuantLab uses a monorepo.

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

Database migrations and reusable SQL queries are centralized under `database/`.

Common application functionality is centralized under `shared/`.

Source-specific persistence rules remain with the source component when they depend on source-specific business semantics.

---

## 5. Nasdaq Halt Collector

The Nasdaq Halt Collector currently provides the most complete reference implementation of the QuantLab ingestion architecture.

Current source modules include:

```text
nasdaq_historical_collector.py
nasdaq_halt_collector.py
nasdaq_xml.py
nasdaq_deduplication.py
nasdaq_episodes.py
nasdaq_postgresql.py
calculate_halt_metrics.py
load_postgresql.py
```

### 5.1 Historical Acquisition

Historical immutable source files use date-based names such as:

```text
tradehalts_2026-08-03.xml
tradehalts_2026-08-04.xml
```

and are stored under the collector RAW historical directory.

### 5.2 Live Acquisition

Live collection creates immutable timestamped XML snapshots such as:

```text
tradehalts_live_YYYYMMDDTHHMMSSZ.xml
```

A convenience copy may also be maintained as:

```text
latest_tradehalts.xml
```

The convenience copy is not the immutable provenance artifact.

### 5.3 Shared Parsing

Historical and live inputs use a common parser:

```text
nasdaq_xml.py
```

The parser normalizes currently observed source differences such as:

```text
Historical : Mkt
Live       : Market
```

### 5.4 Observation Deduplication

Shared observation deduplication is implemented in:

```text
nasdaq_deduplication.py
```

The Python observation identity is intentionally not identical to the PostgreSQL canonical RAW natural key.

`unique_events` represents distinct Nasdaq observations, not necessarily one row in `raw.nasdaq_trade_halt`.

### 5.5 Episode Construction

Shared episode construction is implemented in:

```text
nasdaq_episodes.py
```

The CORE V1.2 identity is:

```text
symbol
market
halt_start
```

`reason_code` is descriptive at CORE level and is not part of the V1.2 CORE identity.

---

## 6. Nasdaq PostgreSQL Persistence V1.2

Nasdaq-specific PostgreSQL persistence is implemented in:

```text
collectors/nasdaq_halts/src/nasdaq_postgresql.py
```

Current application persistence version:

```text
VERSION = "1.2"
```

The module uses the common database connectivity layer under:

```text
shared/database/
```

Its responsibilities include:

- canonical RAW HALT persistence;
- resumption observation persistence;
- CORE episode persistence;
- CORE-to-RAW relationship maintenance;
- natural-key handling;
- canonical resumption selection;
- data-quality guards;
- `inserted / updated / unchanged` accounting;
- idempotence;
- referential-integrity validation;
- transaction control;
- concurrency serialization.

### 6.1 V1.2 Data Flow

```text
Nasdaq XML
    |
    v
Parsing / Normalization
    |
    v
Distinct Nasdaq Observations
    |
    +----------------------------+
    |                            |
    v                            v
Canonical RAW HALT          RAW Resumption Observations
raw.nasdaq_trade_halt       raw.nasdaq_resumption
    |
    v
Episode Builder
    |
    v
core.nasdaq_halt_episode
    |
    v
core.nasdaq_halt_episode_event
```

---

## 7. PostgreSQL Data Architecture

Production structured data is stored in centralized managed PostgreSQL.

### 7.1 DEV Environment

Current DEV reference environment:

- Azure Database for PostgreSQL Flexible Server
- Azure region: Canada Central
- PostgreSQL: 17
- Burstable compute
- B1ms
- 1 vCore
- 2 GiB memory
- 32 GiB storage
- High availability: disabled
- Backup retention: 7 days
- Public network access restricted by Azure firewall rules
- TLS enabled
- PostgreSQL authentication

Server:

```text
quantlab-postgres-dev.postgres.database.azure.com
```

Database:

```text
quantlab
```

Logical schemas:

```text
raw
core
analytics
```

---

## 8. Nasdaq Data Model V1.2

The physical Nasdaq PostgreSQL model is:

```text
Data Model V1.2
```

Primary objects:

```text
raw.nasdaq_trade_halt
raw.nasdaq_resumption
core.nasdaq_halt_episode
core.nasdaq_halt_episode_event
```

### 8.1 Canonical RAW HALT

`raw.nasdaq_trade_halt` represents one canonical HALT per V1.2 RAW natural key:

```text
symbol
market
halt_date
halt_time
reason_code
```

Multiple source observations may map to one canonical RAW HALT.

### 8.2 RAW Resumption Observations

`raw.nasdaq_resumption` preserves distinct resumption observations.

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

The observation uniqueness constraint uses PostgreSQL:

```sql
UNIQUE NULLS NOT DISTINCT
```

so observations containing nullable quote/trade times remain idempotent.

### 8.3 CORE Episode

`core.nasdaq_halt_episode` represents the business episode.

V1.2 CORE identity:

```text
symbol
market
halt_start
```

### 8.4 CORE-to-RAW Relationship

`core.nasdaq_halt_episode_event` models:

```text
1 CORE episode -> N RAW events
```

The pair:

```text
episode_id
trade_halt_id
```

is unique.

---

## 9. Canonical Resumption Policy

Canonical RAW resumption fields are selected atomically from one source observation.

Observations are classified conceptually as:

```text
Rank 2 : complete and temporally valid
Rank 1 : partial but admissible
Rank 0 : no usable resumption or temporally invalid
```

For multiple valid complete observations, the latest valid `halt_end` is selected deterministically.

An impossible observation such as:

```text
halt_end < halt_start
```

is not used as the canonical RAW resumption.

It is still preserved in:

```text
raw.nasdaq_resumption
```

for source fidelity.

If all available resumption observations for a HALT are invalid, the canonical RAW resumption fields remain `NULL`.

The V1.2 validation explicitly covered five all-invalid historical RAW keys.

---

## 10. Migration Architecture

Current migration files:

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

This is a documented historical numbering anomaly and the files must not be renamed retroactively.

Future migrations must use a new available migration number.

### 10.1 Migration 006

`006_nasdaq_persistence_v1_2.sql` aligns the physical PostgreSQL schema with the validated V1.2 persistence model.

It includes:

- RAW V1.2 deduplication and identity;
- CORE V1.2 identity;
- resumption observation deduplication;
- `UNIQUE NULLS NOT DISTINCT`;
- CORE/RAW relationship preservation;
- referential-integrity validation;
- transaction-scoped advisory locking.

The migration has been validated end-to-end in DEV using a test copy that completed all statements and rolled back successfully.

---

## 11. Concurrency Architecture

Nasdaq PostgreSQL persistence uses:

```sql
pg_advisory_xact_lock(716203, 1)
```

Reserved QuantLab Nasdaq lock key:

```text
(716203, 1)
```

The lock is acquired before persistence reads and writes and is held through:

```text
RAW
RESUMPTION
CORE
CORE-to-RAW relationships
```

It is automatically released by `COMMIT` or `ROLLBACK`.

Migration 006 uses the same lock, preventing a cooperating V1.2 migration and the Nasdaq persistence transaction from modifying the same model concurrently.

A two-connection concurrency test validated that a second connection blocks until the first transaction releases the lock.

Database uniqueness and referential constraints remain the final integrity safeguards.

---

## 12. Historical Validation Status

The full historical corpus has now been processed and validated.

Period:

```text
2020-01-01 -> 2026-08-28
```

Historical source files:

```text
2432
```

Observed market days:

```text
1738
```

Pipeline results:

```text
Raw source events        : 69186
Distinct observations    : 68170
Canonical RAW HALTs      : 68072
CORE episodes            : 68017
Distinct tickers         : 9718
Daily rows               : 50000
Calculated durations     : 67983
```

Close-status counts:

```text
YES       : 1777
NO        : 62902
UNKNOWN   : 34
```

The full-history validation replaced several provisional assumptions from the earlier 744-event baseline.

---

## 13. Idempotence Status

The current V1.2 reference rerun produces:

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

Non-regression:

```text
QVCG TEST  : PASS
BCARU TEST : PASS
```

This is the current sequential idempotence checkpoint.

---

## 14. BCARU Historical Fixture

BCARU now uses a fixed historical regression fixture through:

```text
2026-08-27
```

The fixture validates:

```text
21 CORE episodes
13 historical dates
```

and separately validates the 2026-08-03 close condition.

Official BCARU observations also confirmed important V1.2 semantics:

- partial and complete observations for the same HALT;
- multiple HALTs on the same day;
- T1/T2/T3 reason codes for the same `halt_start`;
- `reason_code` must remain descriptive rather than part of CORE identity.

---

## 15. Referential Integrity

Current validated integrity checks return zero for:

```text
broken CORE -> RAW references
broken relationship -> CORE references
broken relationship -> RAW references
duplicate episode_id / trade_halt_id relationship pairs
```

These validations are also represented in migration 006.

---

## 16. Shared Components

Reusable functionality is maintained under:

```text
shared/
```

Responsibilities include:

- PostgreSQL connectivity;
- configuration;
- logging;
- retry mechanisms;
- date/time utilities;
- common validation functions.

Current shared PostgreSQL dependency:

```text
psycopg[binary]>=3.3,<4
```

Environment variables:

```text
QUANTLAB_DB_HOST
QUANTLAB_DB_PORT
QUANTLAB_DB_NAME
QUANTLAB_DB_USER
QUANTLAB_DB_PASSWORD
```

Secrets must never be committed to Git.

---

## 17. Database Access Architecture

QuantLab applies least privilege.

Administrative access is reserved for:

- initial provisioning;
- migrations;
- role and privilege management;
- administrative operations.

Application role:

```text
quantlab_collector
```

DEV login:

```text
quantlab_collector_dev
```

Application code must not use the PostgreSQL administrator account during normal collector execution.

---

## 18. Execution Architecture

QuantLab supports two execution modes.

### Automated

Future centralized infrastructure will execute collectors and analytical jobs on defined schedules.

Centralized execution must include:

- idempotence;
- execution logging;
- error handling;
- appropriate retries;
- duplicate-processing safeguards;
- concurrency controls.

### On Demand

Authorized collaborators may execute approved jobs manually.

On-demand execution must use the same production persistence rules and integrity protections as scheduled execution.

The Nasdaq persistence layer is already concurrency-hardened for cooperating processes through its PostgreSQL advisory lock.

The final centralized orchestration infrastructure remains to be implemented.

---

## 19. Analytics Layer

The `analytics` schema exists, but Nasdaq Halt analytical database objects are not yet implemented.

Conceptual objects include:

```text
analytics.ticker_halt_daily
analytics.ticker_halt_metrics
analytics.ticker_halt_reason_metrics
```

Before certification, PostgreSQL analytics must be reconciled with validated Python metrics.

The official market-calendar model remains a prerequisite for metrics such as:

```text
halts_per_market_day
```

No analytics migration number is currently reserved.

A future migration number must be selected from the actual migration directory state at implementation time.

---

## 20. Collaboration Architecture

### GitHub

Used for:

- source code;
- version control;
- technical documentation;
- database migrations;
- SQL queries;
- releases;
- pull requests;
- code review.

### GitHub Projects

Used for:

- backlog;
- action items;
- priorities;
- ownership;
- status;
- target dates;
- component and environment classification.

### PostgreSQL

Used as the centralized authoritative structured data store.

### Microsoft Ecosystem

Teams / SharePoint / Office documents may be used for collaborative non-code project material.

---

## 21. Encoding and Tooling

The repository includes:

```text
.editorconfig
```

with UTF-8 configuration.

PowerShell 5.1 requires special care because:

```powershell
Set-Content -Encoding utf8
```

may write a UTF-8 BOM.

For files that must be UTF-8 without BOM, particularly SQL migration files, use a no-BOM writer such as:

```powershell
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
```

PowerShell 7 evaluation is deferred until the Nasdaq/PostgreSQL checkpoint is fully documented and committed.

---

## 22. Current Architecture Status

Nasdaq PostgreSQL persistence has reached:

```text
Data Model V1.2
PostgreSQL Persistence V1.2
```

Validated capabilities include:

- full historical acquisition and processing;
- live acquisition architecture;
- immutable RAW XML provenance;
- shared XML parsing;
- observation-level deduplication;
- canonical RAW HALT persistence;
- resumption observation persistence;
- CORE V1.2 identity;
- 1 CORE -> N RAW relationship modeling;
- canonical resumption selection;
- invalid-resumption preservation;
- referential integrity;
- sequential idempotence;
- concurrency advisory locking;
- migration 006 validation;
- QVCG regression;
- BCARU historical fixture;
- fractional-second timestamp preservation.

Primary remaining architectural work includes:

- official market-calendar modeling;
- PostgreSQL analytics;
- centralized orchestration;
- backup / restore validation;
- TEST / PROD preparation;
- secrets-management strategy;
- formal Nasdaq timezone semantics;
- future hardening of nullable schema fields where justified.

---

## 23. Architecture Evolution

This document must be updated whenever a change affects:

- platform components;
- infrastructure;
- data ownership;
- data flow;
- execution model;
- repository organization;
- database architecture;
- security architecture;
- collaboration model.

Detailed database semantics belong in:

```text
docs/database.md
```

Collector-specific architecture belongs in:

```text
collectors/nasdaq_halts/docs/ARCHITECTURE.md
```

Implementation work resulting from architecture changes should also be reflected in the QuantLab GitHub Project.
