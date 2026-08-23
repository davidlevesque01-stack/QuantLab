# Nasdaq Halt Collector

The Nasdaq Halt Collector is a QuantLab data acquisition and processing component for Nasdaq trading halt information.

## Purpose

The collector retrieves Nasdaq trading halt data, preserves the original source data, transforms halt events, builds logical halt episodes, and generates analytical halt metrics.

It is one independent collector within the broader QuantLab platform.

## Current Status

Current validated metrics baseline:

`V0.6`

The existing V0.6 metrics engine is considered the functional reference baseline.

Development of the historical collector toward V1.0 must preserve the validated V0.6 metric definitions unless a confirmed and documented defect requires modification.

## Components

### Source

`src/`

Current scripts:

- `nasdaq_halt_collector.py`
- `nasdaq_historical_collector.py`
- `calculate_halt_metrics.py`
- `nasdaq_historical_test.py`

The current script organization is preserved during the initial monorepo migration. Refactoring will be performed separately after migration validation.

### Configuration

`config/config.json`

Contains non-sensitive runtime parameters including:

- Nasdaq source URL;
- local data paths;
- request timeout;
- user agent;
- test parameters.

Secrets and credentials must never be stored in this file.

### Documentation

`docs/ARCHITECTURE.md`

Detailed architecture, processing layers, validation baseline and collector-specific design principles.

`docs/METRICS_SPECIFICATION.md`

Authoritative definitions of the calculated halt metrics.

## Data Flow

    Nasdaq Trader
          |
          v
       Collector
          |
          v
       RAW XML
          |
          v
    Transformation
          |
          v
     Halt Episodes
          |
          v
       Metrics

## Data Principles

The current collector architecture follows these principles:

- original Nasdaq XML is preserved;
- RAW data is not manually modified;
- derived datasets must be reproducible;
- processing must be idempotent;
- analytical outputs can be regenerated from RAW data;
- calculation logic must remain independent from Internet access;
- code and technical documentation are version controlled;
- generated data is not stored in Git.

## Current Local Data

During the monorepo migration, the existing historical and processed data remains preserved under the original project:

`C:\QuantLab\nasdaq_halts\data`

It is intentionally not copied into the Git repository.

Future production data storage will be integrated with the centralized QuantLab PostgreSQL architecture.

## Platform Architecture

The overall collaboration, GitHub, PostgreSQL, automation and infrastructure architecture is documented in:

`QuantLab/docs/architecture.md`