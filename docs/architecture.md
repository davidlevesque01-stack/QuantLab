# QuantLab — System Architecture

## 1. Purpose

QuantLab is a collaborative quantitative data platform designed to acquire, store, process, analyze, and model financial and public datasets.

The architecture is designed initially for two independent remote collaborators while remaining scalable to a future corporate environment.

## 2. Architecture Principles

The platform follows these principles:

1. Source code is separated from production data.
2. GitHub is the authoritative source for code and technical documentation.
3. PostgreSQL is the authoritative source for structured production data.
4. Data collectors operate independently.
5. Analytics are separated from data acquisition.
6. Common functionality is centralized in shared components.
7. Automated execution is centralized to prevent duplicate jobs.
8. Manual execution remains possible when authorized.
9. Credentials and secrets must never be committed to Git.
10. The architecture must remain portable between infrastructure providers.

## 3. Logical Architecture

Data flow:

    External Data Sources
            |
            v
        Collectors
            |
            v
      Data Processing
            |
            v
        PostgreSQL
            |
            v
         Analytics
            |
       +----+----+
       |         |
     Models    Reports

## 4. Repository Architecture

QuantLab uses a monorepo.

    QuantLab/
    |
    +-- collectors/
    |   +-- nasdaq_halts/
    |
    +-- analytics/
    +-- database/
    +-- shared/
    +-- orchestration/
    +-- tests/
    +-- docs/
    |
    +-- README.md
    +-- pyproject.toml
    +-- .gitignore

Each collector is designed as an independent component.

## 5. Data Collectors

Collectors retrieve information from external data sources.

Initial collector:

- Nasdaq Trading Halts

Potential future collectors may include:

- market prices;
- SEC filings;
- economic indicators;
- public statistics;
- other financial datasets.

Collectors must not contain unrelated analytics or predictive models.

## 6. Shared Components

Reusable functionality is maintained under `shared/`.

Examples include:

- PostgreSQL connectivity;
- application configuration;
- logging;
- retry mechanisms;
- date/time utilities;
- common validation functions.

Collectors should reuse these components rather than implementing duplicate functionality.

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

    quantlab-postgres-dev.postgres.database.azure.com

Primary database:

    quantlab

The database currently uses the following logical schemas:

- `raw` — structured data close to the original source;
- `core` — normalized business data;
- `analytics` — derived analytical datasets, views, and materialized views.

For the Nasdaq Halt Collector, the original Nasdaq XML files remain the provenance/source files from which the structured PostgreSQL data can be rebuilt.

The initial PostgreSQL migration creates:

    raw.nasdaq_trade_halt
    core.nasdaq_halt_episode

Analytical objects are intentionally deferred until market-calendar and multi-day halt semantics have been validated against the Python V0.6 baseline.

Both collaborators and authorized automated processes will eventually operate against the same authoritative PostgreSQL data source.

Database credentials and other secrets must remain outside the Git repository.

The DEV environment currently uses the PostgreSQL administrator account for initial provisioning and validation only. Dedicated application accounts with least-privilege permissions will be introduced before production use.

## 8. Execution Architecture

QuantLab supports two execution modes.

### Automated

Production collectors and analytical jobs will eventually execute from centralized cloud infrastructure according to defined schedules.

### On Demand

Authorized collaborators may initiate approved jobs manually when required.

Production jobs must implement safeguards against duplicate processing.

## 9. Collaboration Architecture

### GitHub Repository

Used for:

- source code;
- version control;
- technical documentation;
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

## 10. User Architecture

Each collaborator uses an individual account.

Shared credentials should not be used.

Initially, the GitHub repository may be owned by an individual GitHub account and shared with the second collaborator.

If QuantLab becomes a corporate entity, repositories may be transferred to a GitHub Organization.

## 11. Future Protected QuantLab Environment

A future protected analytical environment may operate independently from the Internet.

Validated code and datasets may be transferred into this environment using controlled procedures.

The protected analytical environment will not initially serve as the shared development infrastructure.

## 12. Architecture Evolution

This document is authoritative for major architectural decisions and must be updated whenever a change affects:

- platform components;
- infrastructure;
- data ownership;
- execution model;
- repository organization;
- security architecture;
- collaboration model.

## 13. Work Management with GitHub Projects

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

Backlog → Ready → In Progress → Review / Test → Done

Standard project fields include:

- Priority: Critical / High / Medium / Low
- Component: Infrastructure / GitHub / Database / Collector / Analytics / Orchestration / Documentation / Collaboration / Security
- Environment: DEV / TEST / PROD / N/A
- Target date
- Owner

GitHub Issues and Pull Requests should be linked to the Project when implementation work, discussion, validation, or code changes are required.