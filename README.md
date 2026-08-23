# QuantLab

QuantLab is a collaborative quantitative data collection, analytics, and research platform.

## Objectives

QuantLab is designed to:

- collect financial and public data from multiple independent sources;
- centralize validated data in a shared PostgreSQL database;
- provide reusable data-processing and analytics capabilities;
- support quantitative research, statistical analysis, and predictive models;
- allow multiple collaborators to work from the same source code and data;
- support automated and on-demand execution of data collectors and analytical jobs.

## Architecture

QuantLab is organized as a monorepo.

Main components:

- `collectors/` — independent data acquisition tools;
- `analytics/` — quantitative analysis and modeling;
- `database/` — database schemas and migrations;
- `shared/` — common Python components and utilities;
- `orchestration/` — scheduled and on-demand jobs;
- `tests/` — integration and platform-level tests;
- `docs/` — technical and operational documentation.

## Initial Data Collector

The first implemented collector is:

`collectors/nasdaq_halts`

It retrieves and processes Nasdaq trading halt information.

Additional collectors will be added independently as the QuantLab platform evolves.

## Data Architecture

The target architecture uses a centralized managed PostgreSQL database as the authoritative shared data source.

Local CSV files may be used for development, validation, staging, or controlled exports but are not intended to become the authoritative production data source.

## Collaboration

QuantLab uses:

- GitHub Repository for source code and technical documentation;
- GitHub Projects for backlog, tasks, priorities, ownership, and development tracking;
- PostgreSQL for centralized structured data;
- Microsoft Teams / SharePoint for collaborative Office documents and non-code project material.

## Status

QuantLab is currently under initial platform deployment and migration of the existing Nasdaq Halt Collector.