# QuantLab — System Architecture

## 1. Purpose

QuantLab is a collaborative quantitative data platform designed to acquire, store, process, analyze, and model financial and public datasets.

The architecture is designed initially for two independent remote collaborators while remaining scalable to a future corporate environment.

## 2. Architecture Principles

The platform follows these principles:

1. Source code is separated from production data.
2. GitHub is the authoritative source for code and technical documentation.
3. PostgreSQL is the authoritative source for structured production data.
4. Original RAW source files are retained when required for provenance and rebuildability.
5. Data collectors operate independently.
6. Analytics are separated from data acquisition.
7. Common functionality is centralized in shared components.
8. Automated execution is centralized to prevent duplicate jobs.
9. Manual execution remains possible when authorized.
10. Application processes follow the principle of least privilege.
11. Credentials and secrets must never be committed to Git.
12. Database schema changes are implemented through versioned migrations.
13. The architecture must remain portable between infrastructure providers.
14. Database persistence must be idempotent where source data may be processed more than once.
15. Data-model ambiguities must fail explicitly rather than silently discard or arbitrarily associate source data.
16. Incremental source observations may enrich existing structured data without erasing previously known information.
17. Immutable source snapshots should be retained when repeated observations are required for provenance or reconstruction.

## 3. Logical Architecture

Target production data flow:

```text
External Data Sources
        |
        v
    Collectors
        |
        +----> Original / Immutable RAW Files
        |          |
        |          +----> Provenance / Rebuild
        |
        v
Parsing / Normalization
        |
        v
PostgreSQL RAW
        |
        v
PostgreSQL CORE
        |
        v
     Analytics
        |
   +----+----+
   |         |
 Models    Reports
```

For sources where original files are retained, PostgreSQL provides the authoritative structured representation while the original RAW files preserve provenance and rebuildability.

Processed CSV files may be retained as validation, diagnostic, export or non-regression artifacts, but they are not the production integration layer between collectors and PostgreSQL.

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
```

Each collector is designed as an independent component.

Database migrations and reusable SQL queries are centralized under `database/`.

Common application functionality is centralized under `shared/`.

Source-specific PostgreSQL persistence logic remains with the source component when it depends on source-specific business semantics.

Integration tests that exercise multiple architectural layers are maintained under:

```text
tests/integration/
```

## 5. Data Collectors

Collectors retrieve information from external data sources.

Initial collector:

- Nasdaq Trading Halts.

Potential future collectors may include:

- market prices;
- warrants and other securities data;
- SEC filings;
- economic indicators;
- public statistics;
- other financial datasets.

Collectors must not contain unrelated analytics or predictive models.

### Nasdaq Halt Collector

The Nasdaq Halt Collector currently uses the V0.8 integration architecture.

The historical metric pipeline remains functionally compatible with the validated V0.6/V0.7 baseline while shared parsing, episode construction and PostgreSQL persistence are now used by both historical and live processing.

Current source modules include:

```text
nasdaq_historical_collector.py
nasdaq_halt_collector.py
nasdaq_xml.py
nasdaq_deduplication.py
nasdaq_episodes.py
nasdaq_postgresql.py
calculate_halt_metrics.py
```

### Historical Acquisition

Historical RAW files use immutable date-based names such as:

```text
tradehalts_2026-08-03.xml
tradehalts_2026-08-04.xml
```

and are stored under:

```text
collectors/nasdaq_halts/data/raw/nasdaq/historical/
```

### Live Acquisition

Each live collection creates an immutable timestamped XML snapshot under:

```text
collectors/nasdaq_halts/data/raw/nasdaq/live/
```

using:

```text
tradehalts_live_YYYYMMDDTHHMMSSZ.xml
```

The collector also maintains:

```text
latest_tradehalts.xml
```

as a convenience copy of the most recent feed.

`latest_tradehalts.xml` is not the immutable provenance artifact.

### Shared Processing

Historical and live data use a common XML parser:

```text
nasdaq_xml.py
```

The parser normalizes the currently observed source difference:

```text
Historical : Mkt
Live       : Market
```

Shared deduplication is implemented in:

```text
nasdaq_deduplication.py
```

Shared episode construction is implemented in:

```text
nasdaq_episodes.py
```

### Nasdaq V0.8 Data Flow

```text
                 Nasdaq
                /      \
               /        \
              v          v
        Historical      Live RSS
             |             |
             v             v
      Historical XML   Immutable Live
                       XML Snapshot
             \             /
              \           /
               v         v
             Shared XML Parser
                    |
                    v
              Normalized Events
                    |
                    v
               Deduplication
                    |
                    v
               unique_events
                /        \
               v          v
       PostgreSQL RAW   Optional /
               |        Derived CSV
               v
        Episode Builder
               |
               v
            episodes
               |
               v
       PostgreSQL CORE
               |
               v
       Analytics / Metrics
```

The production PostgreSQL path does not depend on processed CSV files.

Processed CSV datasets remain useful for:

- non-regression testing;
- diagnostics;
- comparison;
- manual inspection;
- optional exports.

The legacy CSV PostgreSQL loader remains available as a transitional validation/migration mechanism but is not the production integration architecture.

## 6. Shared Components

Reusable functionality is maintained under `shared/`.

Current and planned responsibilities include:

- PostgreSQL connectivity;
- application configuration;
- logging;
- retry mechanisms;
- date/time utilities;
- common validation functions.

Collectors should reuse these components rather than implementing duplicate generic functionality.

### PostgreSQL Connectivity

Shared Python PostgreSQL connectivity is implemented under:

```text
shared/database/
```

The current implementation uses Psycopg 3.

The dependency is declared in:

```text
pyproject.toml
```

with:

```text
psycopg[binary]>=3.3,<4
```

Database connection parameters are supplied through environment variables rather than committed configuration files.

Current variable names are:

```text
QUANTLAB_DB_HOST
QUANTLAB_DB_PORT
QUANTLAB_DB_NAME
QUANTLAB_DB_USER
QUANTLAB_DB_PASSWORD
```

Secrets must never be committed to Git.

### Source-Specific Persistence

Nasdaq-specific PostgreSQL persistence is implemented in:

```text
collectors/nasdaq_halts/src/nasdaq_postgresql.py
```

This module uses the generic shared PostgreSQL connection layer but owns Nasdaq-specific persistence rules.

Its current responsibilities include:

- RAW event insertion;
- RAW event enrichment;
- CORE episode insertion;
- CORE episode enrichment;
- natural-key handling;
- RAW identifier resolution;
- first-source-file provenance preservation;
- close-status validation;
- protection against incomplete incoming observations;
- idempotent persistence;
- explicit RAW-to-CORE relationship validation;
- transaction-safe RAW and CORE persistence;
- `inserted / updated / unchanged` execution accounting.

This separation prevents the generic `shared/database/` layer from acquiring Nasdaq-specific business semantics.

## 7. Data Architecture

Production structured data is stored in a centralized managed PostgreSQL instance.

### DEV Environment

The initial QuantLab database environment uses Azure Database for PostgreSQL Flexible Server.

Current DEV configuration:

- Azure region: Canada Central;
- PostgreSQL version: 17;
- compute tier: Burstable;
- compute size: B1ms, 1 vCore, 2 GiB memory;
- storage: 32 GiB;
- high availability: disabled;
- backup retention: 7 days;
- network access: public access restricted by Azure firewall rules;
- transport encryption: TLS;
- authentication: PostgreSQL authentication.

Server:

```text
quantlab-postgres-dev.postgres.database.azure.com
```

Primary database:

```text
quantlab
```

The database currently uses the following logical schemas:

- `raw` — structured data close to the original source;
- `core` — normalized business data;
- `analytics` — derived analytical datasets, views and materialized views.

### Nasdaq Halt Data Model

For the Nasdaq Halt Collector, original Nasdaq XML files remain the provenance/source files from which structured PostgreSQL data can be rebuilt.

The current PostgreSQL model contains:

```text
raw.nasdaq_trade_halt
core.nasdaq_halt_episode
```

The physical PostgreSQL model remains:

```text
Data Model V1.1
```

The V0.8 work changes persistence semantics but does not require an additional schema migration.

The initial schema was created through:

```text
database/migrations/001_create_nasdaq_halts_schema.sql
```

A second migration corrected the representation of the halt close status:

```text
database/migrations/002_fix_nasdaq_halt_close_status.sql
```

The original boolean representation:

```text
halt_at_close BOOLEAN
```

was replaced by:

```text
halt_close_status VARCHAR(20)
```

with supported values:

```text
YES
NO
UNKNOWN
MULTI_DAY
```

### Validated Historical Baseline

The historical validation dataset contains:

```text
RAW events           : 744
Unique events        : 744
CORE episodes        : 744
Distinct tickers     : 235
Daily rows           : 322
Market days          : 10
Calculated durations : 742

YES                  : 15
NO                   : 697
UNKNOWN              : 2
MULTI_DAY            : 30
```

Non-regression tests:

```text
QVCG : PASS
BCARU: PASS
```

After introduction of V0.8 persistence semantics, a complete historical rerun produced:

```text
RAW inserted          : 0
RAW updated           : 0
RAW unchanged         : 744

CORE inserted         : 0
CORE updated          : 0
CORE unchanged        : 744
```

This confirms that the V0.8 persistence logic does not generate unnecessary changes against the validated historical baseline.

Fractional-second Nasdaq timestamps remain preserved through XML parsing, Python processing and PostgreSQL storage.

### Validated Live Baseline

A real Nasdaq RSS collection was processed through the V0.8 live pipeline.

The validated lot contained:

```text
Raw events            : 35
Unique events         : 35
CORE episodes         : 35
Calculated durations  : 23

YES                   : 2
NO                    : 17
UNKNOWN               : 12
MULTI_DAY             : 4
```

First PostgreSQL persistence:

```text
RAW inserted          : 35
RAW updated           : 0
RAW unchanged         : 0

CORE inserted         : 35
CORE updated          : 0
CORE unchanged        : 0
```

A second collection against unchanged source content produced:

```text
RAW inserted          : 0
RAW updated           : 0
RAW unchanged         : 35

CORE inserted         : 0
CORE updated          : 0
CORE unchanged        : 35
```

This validates real live idempotence for the current V0.8 architecture.

### RAW Provenance

Each structured RAW record contains:

```text
raw.nasdaq_trade_halt.source_file
```

Historical examples:

```text
tradehalts_2026-08-03.xml
tradehalts_2026-08-04.xml
```

Live example:

```text
tradehalts_live_20260828T205115Z.xml
```

In V0.8, an existing RAW event retains the `source_file` of the first snapshot that created the structured event.

Later snapshots may enrich the event without replacing this value.

The immutable XML snapshot archive remains the primary provenance layer.

PostgreSQL does not currently model the complete relationship:

```text
N source snapshots -> 1 RAW event
```

A future source-observation/provenance model may be added if required.

### RAW Natural Key

The current PostgreSQL RAW natural key is:

```text
symbol
halt_date
halt_time
reason_code
market
```

This key is enforced by a UNIQUE constraint.

The Python deduplication key is not identical to the PostgreSQL RAW natural key.

The historical baseline contains no collision.

A validated live snapshot also contained:

```text
Events                 : 35
Natural keys           : 35
Duplicate natural keys : 0
```

This difference must continue to be monitored and must be explicitly validated against the complete historical dataset.

### RAW-to-CORE Relationship

The current PostgreSQL schema models:

```text
1 RAW event -> 1 CORE episode
```

This relationship is valid for:

```text
744 historical RAW / CORE records
35 live RAW / CORE records
```

under the currently validated datasets.

However, the Python episode-building algorithm can theoretically combine multiple overlapping RAW events into one episode.

For this reason, `nasdaq_postgresql.py` uses strict relationship validation.

If an episode cannot be associated unambiguously with exactly one RAW event, persistence fails explicitly rather than arbitrarily selecting a RAW event.

The 1:1 model must be revalidated against the complete five-year history before being considered permanent.

### Analytics Layer

The `analytics` schema exists, but Nasdaq Halt analytical database objects are intentionally deferred.

Before implementing them, QuantLab must validate:

- authoritative market-calendar semantics;
- weekends and market holidays;
- multi-day halt behavior;
- close-status semantics;
- equivalence with the validated Python metrics.

The current Python implementation does not yet constitute an authoritative exchange calendar.

The future Nasdaq Halt analytics migration is currently planned as:

```text
database/migrations/003_create_nasdaq_halts_analytics.sql
```

The metric:

```text
halts_per_market_day
```

must not be implemented as a PostgreSQL analytical metric until an authoritative market-day denominator is modeled.

## 8. Database Access Architecture

QuantLab applies least-privilege database access.

### Administrative Access

The PostgreSQL administrator account is reserved for:

- initial provisioning;
- schema migrations;
- role and privilege management;
- operations explicitly requiring administrative privileges.

Application code must not use the administrator account for normal collector execution.

### Application Role

The current application role is:

```text
quantlab_collector
```

It is a `NOLOGIN` role containing the privileges required by the Nasdaq collector on its RAW and CORE objects.

### DEV Login

The current DEV application login is:

```text
quantlab_collector_dev
```

This login inherits its application privileges through membership in:

```text
quantlab_collector
```

Future environments should follow the same separation between application roles and environment-specific login identities.

### Secrets

Database passwords and other secrets must remain outside:

- Git;
- GitHub;
- Markdown documentation;
- committed source code;
- committed configuration files.

The current Python connection layer receives database credentials through environment variables.

A centralized production secrets-management mechanism will be selected before PROD.

## 9. PostgreSQL Integration Strategy

### Direct V0.8 Persistence

Direct Nasdaq-to-PostgreSQL persistence is implemented in:

```text
collectors/nasdaq_halts/src/nasdaq_postgresql.py
```

It is used by both:

```text
calculate_halt_metrics.py
nasdaq_halt_collector.py
```

for historical processing and live processing respectively.

The integration writes:

```text
unique_events
    |
    v
raw.nasdaq_trade_halt

episodes
    |
    v
core.nasdaq_halt_episode
```

RAW and CORE persistence execute in a common PostgreSQL transaction.

Database errors therefore prevent a partial operation from being treated as successful.

### Incremental Update Semantics

The V0.8 persistence layer distinguishes:

```text
inserted
updated
unchanged
```

An incoming live observation may enrich an existing event.

General rule:

```text
Existing NULL + incoming value
-> update

Existing value + incoming NULL
-> preserve existing value

Existing value A + incoming A
-> unchanged

Existing value A + incoming value B
-> update with B
```

This permits an initially open HALT to be completed later when Nasdaq publishes resumption information.

For CORE close status, an incoming:

```text
UNKNOWN
```

does not overwrite a stored final:

```text
YES
NO
MULTI_DAY
```

### Controlled Integration Test

The update lifecycle is validated through:

```text
tests/integration/test_nasdaq_postgresql_live_update.py
```

The test covers:

```text
open HALT
-> completed HALT
-> identical repeat
-> regressive incomplete observation
```

It runs inside a PostgreSQL transaction and performs a rollback after validation.

The test database was verified to contain no residual synthetic test rows after execution.

### Transitional CSV Loader

A transitional PostgreSQL loader remains at:

```text
collectors/nasdaq_halts/src/load_postgresql.py
```

It was used to validate the initial PostgreSQL schema and integration against known CSV outputs.

The CSV loader is retained as a validation/migration utility.

It is not the production collector-to-PostgreSQL integration path.

## 10. SQL Query Architecture

Reusable SQL queries are stored under:

```text
database/queries/
```

Nasdaq Halt queries are currently stored under:

```text
database/queries/nasdaq_halts/
```

Current query files include:

```text
explore_halt_episodes.sql
get_halts_per_symbol_and_date.sql
visualize_halts_table.sql
```

These queries support:

- development;
- data exploration;
- validation;
- troubleshooting;
- manual database inspection;
- RAW source-file provenance inspection.

For example:

```sql
SELECT DISTINCT
    source_file
FROM raw.nasdaq_trade_halt
ORDER BY source_file;
```

Visual Studio Code with the PostgreSQL extension is currently used as a DEV database exploration and query tool.

A broader user-facing database query interface remains a future implementation activity.

## 11. Execution Architecture

QuantLab supports two execution modes.

### Automated

Production collectors and analytical jobs will eventually execute from centralized infrastructure according to defined schedules.

Centralized execution is required to avoid multiple collaborators independently triggering duplicate scheduled processing.

Automated jobs must implement:

- idempotence;
- execution logging;
- error handling;
- retry behavior where appropriate;
- safeguards against duplicate processing;
- concurrency control where simultaneous execution could affect database integrity.

Automated centralized execution has not yet been implemented.

### Concurrency

The current Nasdaq V0.8 writer is validated for sequential execution.

Its persistence logic performs a lookup followed by an insert or update.

PostgreSQL UNIQUE constraints protect the natural key, but two collector processes running concurrently could compete between the lookup and insertion steps.

Before allowing concurrent centralized execution, QuantLab must define an explicit strategy such as:

```text
PostgreSQL ON CONFLICT
```

or an appropriate locking mechanism.

### On Demand

Authorized collaborators may initiate approved jobs manually when required.

On-demand execution must use the same production processing logic and data-integrity safeguards as scheduled execution.

The final centralized execution infrastructure has not yet been implemented.

## 12. Collaboration Architecture

### GitHub Repository

Used for:

- source code;
- version control;
- technical documentation;
- database migrations;
- reusable SQL queries;
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
- development tracking.

### PostgreSQL

Used as the centralized authoritative structured data store.

### Microsoft Teams / SharePoint

Used for:

- Word documents;
- Excel workbooks;
- meeting material;
- collaborative Office documents;
- non-code project files.

## 13. User Architecture

Each collaborator uses an individual account.

Shared credentials should not be used.

Initially, the GitHub repository may be owned by an individual GitHub account and shared with the second collaborator.

If QuantLab becomes a corporate entity, repositories may be transferred to a GitHub Organization.

The architecture should similarly permit future migration of cloud infrastructure from an individual environment to a corporate environment without redesigning the application architecture.

## 14. Future Protected QuantLab Environment

A future protected analytical environment may operate independently from the Internet.

Validated code and datasets may be transferred into this environment using controlled procedures.

The protected analytical environment will not initially serve as the shared development infrastructure.

Its purpose is to permit sensitive or controlled analytical workloads to operate separately from Internet-facing collection infrastructure.

## 15. Architecture Evolution

This document is authoritative for major architectural decisions and must be updated whenever a change affects:

- platform components;
- infrastructure;
- data ownership;
- data flow;
- execution model;
- repository organization;
- database architecture;
- security architecture;
- collaboration model.

Component-specific implementation details should be documented in the appropriate specialized documents, including:

```text
docs/database.md
collectors/nasdaq_halts/docs/ARCHITECTURE.md
collectors/nasdaq_halts/docs/DATA_MODEL.md
```

Architecture changes that require implementation work should also be reflected in the QuantLab GitHub Project.

## 16. Work Management with GitHub Projects

QuantLab uses a GitHub Project as the central work-management layer for the platform.

The GitHub Project is used to manage:

- backlog;
- action items;
- priorities;
- ownership;
- status;
- target dates;
- component classification;
- environment classification.

The standard workflow is:

```text
Backlog
  |
  v
Ready
  |
  v
In Progress
  |
  v
Review / Test
  |
  v
Done
```

Standard project fields include:

- Priority: Critical / High / Medium / Low
- Component: Infrastructure / GitHub / Database / Collector / Analytics / Orchestration / Documentation / Collaboration / Security
- Environment: DEV / TEST / PROD / N/A
- Target date
- Owner

GitHub Issues and Pull Requests should be linked to the Project when implementation work, discussion, validation or code changes are required.

## 17. Current Nasdaq Integration Status

The Nasdaq Halt PostgreSQL integration has reached the V0.8 validation checkpoint.

Validated capabilities include:

- historical XML acquisition;
- live RSS acquisition;
- immutable historical RAW XML;
- immutable timestamped live snapshots;
- common historical/live XML parsing;
- common deduplication;
- common episode construction;
- direct PostgreSQL RAW persistence;
- direct PostgreSQL CORE persistence;
- incremental enrichment of live HALTs;
- protection against incomplete observations;
- transaction-safe persistence;
- historical idempotence;
- live idempotence;
- fractional-second timestamp preservation;
- controlled live lifecycle integration testing;
- QVCG and BCARU historical non-regression.

The next major Nasdaq data milestone is the construction, loading and validation of the complete five-year historical dataset.

That validation must re-examine the assumptions that remain provisional, particularly:

- RAW natural-key uniqueness;
- Python/PostgreSQL deduplication equivalence;
- RAW-to-CORE cardinality;
- merged episodes;
- multi-day behavior;
- timezone semantics;
- source provenance;
- official market-calendar semantics;
- full-volume idempotence.
