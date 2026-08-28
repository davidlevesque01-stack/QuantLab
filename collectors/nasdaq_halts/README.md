# Nasdaq Halt Collector

The Nasdaq Halt Collector is a QuantLab data acquisition, processing and persistence component for Nasdaq trading halt information.

It is one independent collector within the broader QuantLab platform.

## Purpose

The component:

- retrieves Nasdaq trading halt data;
- preserves the original Nasdaq XML source files;
- parses and normalizes halt events;
- deduplicates events;
- builds logical halt episodes;
- persists structured RAW and CORE data to PostgreSQL;
- generates derived CSV datasets;
- calculates analytical halt metrics;
- performs non-regression validation.

## Current Status

Current processing version:

```text
V0.7
```

V0.7 adds direct PostgreSQL persistence to the historical XML processing path while preserving the validated V0.6 metric behavior.

The V0.6 results remain the functional non-regression baseline.

Current V0.7 validation dataset:

```text
XML files              : 15
Raw events             : 744
Unique events          : 744
HALT episodes          : 744
Distinct tickers       : 235
Daily rows             : 322
Market days            : 10
Calculated durations   : 742
```

Close-status distribution:

```text
YES       : 15
NO        : 697
UNKNOWN   : 2
MULTI_DAY : 30
TOTAL     : 744
```

Non-regression tests:

```text
QVCG : PASS
BCARU: PASS
```

Direct PostgreSQL persistence has also been validated against this baseline.

The complete five-year historical dataset has not yet been loaded or certified.

## Components

### Source

```text
src/
```

Current scripts:

- `nasdaq_halt_collector.py`
- `nasdaq_historical_collector.py`
- `calculate_halt_metrics.py`
- `nasdaq_historical_test.py`
- `nasdaq_postgresql.py`
- `load_postgresql.py`

### `nasdaq_historical_collector.py`

Acquires historical Nasdaq XML files on a date-by-date basis and preserves them under the local RAW data layer.

### `calculate_halt_metrics.py`

Current V0.7 historical processing pipeline.

It performs:

- XML parsing;
- normalization;
- event deduplication;
- episode construction;
- PostgreSQL persistence;
- derived CSV generation;
- metric calculation;
- non-regression tests.

### `nasdaq_postgresql.py`

Nasdaq-specific PostgreSQL persistence layer.

It writes:

```text
unique_events
```

to:

```text
raw.nasdaq_trade_halt
```

and episodes to:

```text
core.nasdaq_halt_episode
```

It implements idempotent persistence and strict validation of the current RAW-to-CORE relationship.

### `load_postgresql.py`

Transitional CSV-based PostgreSQL loader retained for validation and migration purposes.

It is not the preferred V0.7 persistence path.

### `nasdaq_halt_collector.py`

Existing live/current acquisition path.

This path still requires review before the complete Nasdaq collector PostgreSQL integration is considered finished.

## Configuration

```text
config/config.json
```

Contains non-sensitive runtime parameters including:

- Nasdaq source URL;
- local data paths;
- request timeout;
- user agent;
- test parameters.

Secrets and credentials must never be stored in this file.

PostgreSQL credentials are supplied through environment variables and must not be committed to Git.

## Documentation

Collector-specific documentation is located under:

```text
docs/
```

### `docs/ARCHITECTURE.md`

Detailed component architecture, processing layers, PostgreSQL integration, validation baseline and known limitations.

### `docs/DATA_MODEL.md`

PostgreSQL RAW/CORE data model, provenance, relationships and historical-validation requirements.

### `docs/METRICS_SPECIFICATION.md`

Authoritative definitions of the calculated halt metrics.

General QuantLab documentation is located under the monorepo root:

```text
docs/
```

including:

```text
docs/architecture.md
docs/database.md
docs/installation.md
```

## Data Flow

The validated historical V0.7 path is:

```text
Nasdaq Trader
      |
      v
Historical Collector
      |
      v
RAW XML
      |
      v
Parsing / Normalization
      |
      v
Unique Events
     / \
    /   \
   v     v
PostgreSQL RAW
         Derived CSV
   |
   v
HALT Episodes
   |
   +----> PostgreSQL CORE
   |
   v
Daily / Metrics
   |
   v
Derived CSV
```

Processed CSV files are not required as the integration layer between the V0.7 historical processor and PostgreSQL.

## PostgreSQL

The shared structured data store is PostgreSQL.

Current schemas:

```text
raw
core
analytics
```

Current Nasdaq objects:

```text
raw.nasdaq_trade_halt
core.nasdaq_halt_episode
```

The `analytics` schema exists, but Nasdaq analytical database objects are intentionally deferred until the required market-calendar and multi-day semantics are validated.

## Running V0.7

From the QuantLab monorepo root:

```text
C:\QuantLab\QuantLab
```

activate the virtual environment and run:

```powershell
python -m collectors.nasdaq_halts.src.calculate_halt_metrics
```

The current V0.7 implementation invokes PostgreSQL persistence directly.

The PostgreSQL connection environment variables must therefore be configured before execution.

The detailed workstation and database setup procedure is documented in:

```text
docs/installation.md
```

## Data Principles

The collector follows these principles:

- original Nasdaq XML is preserved for provenance and reconstruction;
- RAW source files are not manually modified;
- PostgreSQL RAW contains the structured source representation;
- PostgreSQL CORE contains normalized business objects;
- processed CSV datasets are derived and reconstructible;
- repeated ingestion must not create duplicates;
- ambiguous RAW-to-CORE relationships must fail explicitly rather than be guessed;
- metric behavior must remain reproducible;
- code and technical documentation are version controlled;
- generated data and secrets are not stored in Git.

## Local Data

Local collector data is stored under:

```text
collectors/nasdaq_halts/data/
```

including:

```text
data/raw/
data/processed/
```

These directories are excluded from Git.

The historical pre-monorepo project remains temporarily available at:

```text
C:\QuantLab\nasdaq_halts
```

as a reference copy.

It should not be treated as the active QuantLab codebase.

## PostgreSQL Validation

A clean V0.7 persistence test produced:

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

This validates idempotence for the current baseline.

XML source provenance was also validated through:

```text
raw.nasdaq_trade_halt.source_file
```

The five-year historical load must revalidate these assumptions at full scale.

## Known Validation Requirements

Before the Nasdaq Halt data model is considered stable, the five-year historical validation must examine:

- RAW natural-key uniqueness;
- Python versus PostgreSQL deduplication;
- RAW-to-CORE cardinality;
- overlapping and merged episodes;
- multi-day behavior;
- XML provenance;
- timestamp precision;
- timezone semantics;
- official market-calendar semantics;
- full-volume idempotence.

The live/current acquisition path must also be aligned with the V0.7 PostgreSQL persistence architecture.

## Platform Architecture

The overall QuantLab collaboration, GitHub, PostgreSQL, automation and infrastructure architecture is documented in:

```text
docs/architecture.md
```
