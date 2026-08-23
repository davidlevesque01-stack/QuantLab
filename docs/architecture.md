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

Production structured data will be stored in a centralized managed PostgreSQL instance.

Both collaborators and authorized automated processes will operate against the same authoritative data source.

Database credentials must remain outside the Git repository.

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