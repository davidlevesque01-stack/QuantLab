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

## 3. Logical Architecture

Target production data flow:

```text
External Data Sources
        |
        v
    Collectors
        |
        +----> Original RAW Files
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

The Nasdaq Halt Collector currently contains the validated Python V0.6 processing pipeline.

The collector preserves original Nasdaq XML files locally as RAW source files.

The existing V0.6 pipeline can generate processed CSV datasets used for validation, diagnostics and non-regression testing.

The production target is not to use CSV files as the integration layer between the collector and PostgreSQL.

The target flow is:

```text
Nasdaq Web / RSS
        |
        v
Nasdaq Halt Collector
        |
        +----> XML RAW retained
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
```

Direct collector-to-PostgreSQL integration remains an implementation step.

## 6. Shared Components

Reusable functionality is maintained under `shared/`.

Current and planned responsibilities include:

- PostgreSQL connectivity;
- application configuration;
- logging;
- retry mechanisms;
- date/time utilities;
- common validation functions.

Collectors should reuse these components rather than implementing duplicate functionality.

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

For the Nasdaq Halt Collector, the original Nasdaq XML files remain the provenance/source files from which the structured PostgreSQL data can be rebuilt.

The current PostgreSQL model contains:

```text
raw.nasdaq_trade_halt
core.nasdaq_halt_episode
```

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

with the supported values:

```text
YES
NO
UNKNOWN
MULTI_DAY
```

This preserves the semantics of multi-day episodes observed in the Python V0.6 baseline.

The current validated V0.6 dataset contains:

```text
RAW events      : 744
CORE episodes   : 744

YES             : 15
NO              : 697
UNKNOWN         : 2
MULTI_DAY       : 30
```

The current 1:1 relationship between RAW events and CORE episodes has been validated against these 744 events but must be revalidated against the complete five-year history.

Fractional-second Nasdaq timestamps are preserved through the current parsing and PostgreSQL storage path.

### Analytics Layer

The `analytics` schema exists, but Nasdaq Halt analytical objects are intentionally deferred.

Before implementing them, QuantLab must validate:

- market-calendar semantics;
- weekends and market holidays;
- multi-day halt behavior;
- close-status semantics;
- equivalence with Python V0.6 metrics.

The future Nasdaq Halt analytics migration is currently planned as:

```text
database/migrations/003_create_nasdaq_halts_analytics.sql
```

The metric `halts_per_market_day` must not be implemented until an authoritative market-day denominator is modeled.

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

A transitional PostgreSQL loader currently exists at:

```text
collectors/nasdaq_halts/src/load_postgresql.py
```

It loads the known V0.6 CSV datasets into PostgreSQL for schema and integration validation.

This loader has validated:

```text
First execution

RAW inserted   : 744
RAW existing   : 0
CORE inserted  : 744
CORE existing  : 0
```

and:

```text
Second execution

RAW inserted   : 0
RAW existing   : 744
CORE inserted  : 0
CORE existing  : 744
```

The second execution confirms idempotent behavior for the validated V0.6 dataset.

The loader also validated:

- application-role database access;
- transaction rollback behavior;
- natural-key conflict handling;
- RAW-to-CORE relationships;
- categorical close status;
- preservation of fractional-second timestamps.

This loader is a validation and migration mechanism, not the final production integration architecture.

The next architectural implementation step is to provide reusable PostgreSQL write functionality that can be invoked directly by the collector without requiring intermediate CSV files.

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
- manual database inspection.

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
- safeguards against duplicate processing.

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
