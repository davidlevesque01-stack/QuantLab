# Nasdaq Halt Collector

The Nasdaq Halt Collector is a QuantLab data acquisition, processing and persistence component for Nasdaq trading halt information.

It is one independent collector within the broader QuantLab platform.

## Purpose

The component:

- retrieves historical and live Nasdaq trading halt data;
- preserves the original Nasdaq XML source files;
- parses and normalizes halt events through a shared XML parser;
- deduplicates events;
- builds logical halt episodes through a shared episode builder;
- persists structured RAW and CORE data directly to PostgreSQL;
- supports enrichment of previously incomplete live halt events;
- generates derived CSV datasets;
- calculates analytical halt metrics;
- performs non-regression and PostgreSQL integration validation.

## Current Status

Current integration version:

```text
V0.8
```

V0.8 extends the validated V0.7 PostgreSQL architecture to the live/current Nasdaq acquisition path.

The historical metric calculation remains V0.7 and continues to reproduce the validated V0.6 metric behavior.

V0.8 adds:

- shared XML parsing for historical and live Nasdaq feeds;
- support for both historical `Mkt` and live `Market` XML fields;
- shared event deduplication;
- shared halt-episode construction;
- immutable timestamped live XML snapshots;
- direct live persistence to PostgreSQL RAW and CORE;
- live event enrichment when Nasdaq supplies additional information;
- protection against regression from known values to NULL;
- protection against regression from a final close status to `UNKNOWN`;
- `inserted / updated / unchanged` persistence accounting;
- live PostgreSQL integration testing with transaction rollback;
- optional live CSV export that is not part of the PostgreSQL integration path.

The V0.6 results remain the functional non-regression baseline for historical metrics.

Current historical validation dataset:

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

PostgreSQL V0.8 historical baseline validation produced:

```text
RAW inserted          : 0
RAW updated           : 0
RAW unchanged         : 744

CORE inserted         : 0
CORE updated          : 0
CORE unchanged        : 744
```

This confirms that the V0.8 update logic does not modify the validated historical baseline when the incoming information is unchanged.

Live PostgreSQL persistence has also been validated successfully.

The complete five-year historical dataset has not yet been loaded or certified.

## Components

### Source

```text
src/
```

Current scripts and modules:

- `nasdaq_halt_collector.py`
- `nasdaq_historical_collector.py`
- `calculate_halt_metrics.py`
- `nasdaq_historical_test.py`
- `nasdaq_postgresql.py`
- `nasdaq_xml.py`
- `nasdaq_deduplication.py`
- `nasdaq_episodes.py`
- `load_postgresql.py`

### `nasdaq_historical_collector.py`

Acquires historical Nasdaq XML files on a date-by-date basis and preserves them under the local RAW data layer.

The historical collector remains focused on acquisition.

### `calculate_halt_metrics.py`

Current V0.7 historical processing and metric pipeline.

It performs:

- XML parsing through the shared parser;
- normalization;
- event deduplication through the shared deduplication module;
- episode construction through the shared episode module;
- PostgreSQL persistence through the V0.8 persistence layer;
- derived CSV generation;
- metric calculation;
- non-regression tests.

### `nasdaq_halt_collector.py`

Current V0.8 live acquisition and persistence path.

It performs:

- download of the current Nasdaq RSS feed;
- creation of an immutable timestamped XML snapshot;
- refresh of `latest_tradehalts.xml` as a convenience copy;
- parsing through the shared XML parser;
- event deduplication;
- halt-episode construction;
- direct PostgreSQL RAW and CORE persistence;
- optional live CSV export;
- execution summary with inserted, updated and unchanged counts.

The live CSV is not used as an intermediate step before PostgreSQL.

### `nasdaq_xml.py`

Shared Nasdaq XML parser used by both historical and live processing.

It normalizes Nasdaq XML fields into a common event representation.

It supports the currently observed market-field difference between:

```text
Historical XML : Mkt
Live XML       : Market
```

Timestamp parsing preserves fractional-second precision.

### `nasdaq_deduplication.py`

Shared event-deduplication logic.

The current implementation intentionally preserves the historical V0.7 deduplication behavior.

The live RSS snapshots validated to date contain one event per PostgreSQL natural key.

If future live snapshots contain multiple observations of the same natural halt within a single snapshot, the live deduplication strategy must be reviewed explicitly rather than changed implicitly.

### `nasdaq_episodes.py`

Shared halt-episode construction logic.

It preserves the historical episode-building behavior used by the validated metric baseline.

It calculates:

- halt start;
- halt end;
- duration;
- close status;
- sequential collector episode identifier.

Current close statuses are:

```text
YES
NO
UNKNOWN
MULTI_DAY
```

### `nasdaq_postgresql.py`

Nasdaq-specific PostgreSQL persistence layer.

Current version:

```text
V0.8
```

It writes unique events to:

```text
raw.nasdaq_trade_halt
```

and halt episodes to:

```text
core.nasdaq_halt_episode
```

The V0.8 persistence layer distinguishes:

```text
inserted
updated
unchanged
```

for both RAW and CORE.

It also supports live event enrichment while protecting previously known information from incomplete later observations.

### `load_postgresql.py`

Transitional CSV-based PostgreSQL loader retained for validation and migration purposes.

It is not the production persistence path.

The preferred architecture is direct Python-object-to-PostgreSQL persistence.

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

Detailed component architecture, historical and live processing layers, PostgreSQL integration, validation baseline and known limitations.

### `docs/DATA_MODEL.md`

PostgreSQL RAW/CORE data model, provenance, update semantics, relationships and historical-validation requirements.

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

## Historical Data Flow

The historical processing path is:

```text
Nasdaq Trader
      |
      v
Historical Collector
      |
      v
Immutable RAW XML
      |
      v
Shared XML Parser
      |
      v
Deduplication
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
Shared Episode Builder
   |
   +----> PostgreSQL CORE
   |
   v
Daily / Metrics
   |
   v
Derived CSV
```

Processed CSV files are not required as the integration layer between the historical processor and PostgreSQL.

## Live Data Flow

The validated V0.8 live path is:

```text
Nasdaq RSS
    |
    v
Live Collector
    |
    v
Immutable timestamped XML snapshot
    |
    +----> latest_tradehalts.xml
    |      convenience copy
    |
    v
Shared XML Parser
    |
    v
Deduplication
    |
    v
Unique Events
    |
    +----> PostgreSQL RAW
    |
    v
Shared Episode Builder
    |
    +----> PostgreSQL CORE
    |
    v
Optional live CSV export
```

The live CSV export is therefore a derived convenience artifact and not an ingestion dependency.

## Live XML Provenance

Each live collection creates an immutable snapshot under:

```text
data/raw/nasdaq/live/
```

using the format:

```text
tradehalts_live_YYYYMMDDTHHMMSSZ.xml
```

Example:

```text
tradehalts_live_20260828T205115Z.xml
```

The timestamp is UTC.

The collector also maintains:

```text
data/raw/nasdaq/latest_tradehalts.xml
```

as a convenience copy of the latest downloaded feed.

`latest_tradehalts.xml` is not the immutable provenance artifact.

The immutable timestamped snapshot is supplied as the event `source_file`.

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

## PostgreSQL V0.8 Update Semantics

The PostgreSQL RAW natural key is:

```text
symbol
halt_date
halt_time
reason_code
market
```

A repeated observation of the same natural halt does not create another RAW row.

For mutable RAW information, V0.8 applies the following rules:

```text
Existing NULL + incoming NULL
    -> unchanged

Existing NULL + incoming value
    -> update with incoming value

Existing value + incoming NULL
    -> preserve existing value

Existing value A + incoming A
    -> unchanged

Existing value A + incoming value B
    -> update with B
```

This allows a live halt initially received without resumption information to be enriched when Nasdaq later publishes the resumption.

Current mutable RAW fields include:

- issue name;
- resumption date;
- resumption quote time;
- resumption trade time;
- pause threshold price.

The RAW `source_file` is intentionally not replaced during an update.

It currently represents the first immutable snapshot that created the structured RAW event.

The XML snapshot archive remains the authoritative source provenance.

A future provenance association model may explicitly represent multiple snapshots observing the same RAW event.

## CORE Update Semantics

The current model maintains a strict one-to-one relationship between the validated RAW event and CORE halt episode.

CORE may be enriched with updated:

- issue name;
- market when previously NULL;
- reason code when previously NULL;
- halt end;
- duration;
- close status.

Known values are protected from incoming NULL values.

For close status specifically:

```text
final status -> UNKNOWN
```

does not regress the stored value.

Current final statuses are:

```text
YES
NO
MULTI_DAY
```

A later non-UNKNOWN final status may replace an earlier final status when Nasdaq supplies corrected information.

The sequential `collector_episode_id` is not treated as a persistent business identity and is preserved after the initial CORE insertion.

## Running Historical Processing

From the QuantLab monorepo root:

```text
C:\QuantLab\QuantLab
```

activate the virtual environment and run:

```powershell
python -m collectors.nasdaq_halts.src.calculate_halt_metrics
```

PostgreSQL connection environment variables must be configured before execution.

The detailed workstation and database setup procedure is documented in:

```text
docs/installation.md
```

## Running Live Collection

From the QuantLab monorepo root with the virtual environment active and PostgreSQL environment variables configured:

```powershell
python -m collectors.nasdaq_halts.src.nasdaq_halt_collector
```

The live collector downloads the current Nasdaq RSS feed and writes directly to PostgreSQL.

A successful execution reports RAW and CORE counts for:

```text
inserted
updated
unchanged
```

## V0.8 Validation

### Historical Baseline

The validated historical dataset contains:

```text
744 RAW events
744 CORE episodes
```

After conversion of the persistence layer to V0.8, a complete historical rerun produced:

```text
RAW inserted          : 0
RAW updated           : 0
RAW unchanged         : 744

CORE inserted         : 0
CORE updated          : 0
CORE unchanged        : 744
```

Historical non-regression tests remained:

```text
QVCG : PASS
BCARU: PASS
```

### Controlled Live-Update Test

An integration test validates the live update lifecycle inside a PostgreSQL transaction.

Test file:

```text
tests/integration/test_nasdaq_postgresql_live_update.py
```

Validated scenarios:

```text
1. Open HALT
   RAW  : 1 inserted
   CORE : 1 inserted

2. Same HALT completed
   RAW  : 1 updated
   CORE : 1 updated

3. Same completed HALT repeated
   RAW  : 1 unchanged
   CORE : 1 unchanged

4. Later incomplete observation
   RAW  : 1 unchanged
   CORE : 1 unchanged
```

The test also validates:

- `NULL -> known value` enrichment;
- preservation of known values when incoming data is NULL;
- preservation of final close status against incoming `UNKNOWN`;
- preservation of the first RAW `source_file`;
- idempotence.

The integration test ends with a transaction rollback.

Database verification confirmed:

```text
QLV08TEST RAW rows  : 0
QLV08TEST CORE rows : 0
```

after execution.

### Real Live Collection

The first validated V0.8 live PostgreSQL execution processed:

```text
Raw events        : 35
Unique events     : 35
HALT episodes     : 35
Calculated durations : 23
```

Close-status distribution:

```text
YES       : 2
NO        : 17
UNKNOWN   : 12
MULTI_DAY : 4
TOTAL     : 35
```

First PostgreSQL execution:

```text
RAW inserted          : 35
RAW updated           : 0
RAW unchanged         : 0

CORE inserted         : 35
CORE updated          : 0
CORE unchanged        : 0
```

A subsequent live execution against an unchanged Nasdaq feed produced:

```text
RAW inserted          : 0
RAW updated           : 0
RAW unchanged         : 35

CORE inserted         : 0
CORE updated          : 0
CORE unchanged        : 35
```

This validates live idempotence against a real Nasdaq RSS snapshot.

The observed live snapshot also contained:

```text
35 events
35 PostgreSQL natural keys
0 duplicate natural keys
```

The apparent duplicate rows visible on the Nasdaq website were therefore not present as duplicate natural keys in the validated RSS XML snapshot.

## Data Principles

The collector follows these principles:

- original Nasdaq XML is preserved for provenance and reconstruction;
- historical RAW XML files are immutable;
- timestamped live RAW XML snapshots are immutable;
- `latest_tradehalts.xml` is only a convenience copy;
- RAW source files are not manually modified;
- PostgreSQL RAW contains the structured source representation;
- PostgreSQL CORE contains normalized business objects;
- PostgreSQL is written directly from normalized Python objects;
- processed CSV datasets are derived and reconstructible;
- CSV is not a required database-ingestion intermediate;
- repeated ingestion must not create duplicates;
- incomplete later observations must not erase known information;
- Nasdaq corrections may enrich or correct mutable values;
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
data/raw/nasdaq/live/
data/processed/
```

These directories are excluded from Git.

The historical pre-monorepo project remains temporarily available at:

```text
C:\QuantLab\nasdaq_halts
```

as a reference copy.

It should not be treated as the active QuantLab codebase.

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

Additional live validation must examine:

- repeated observations across many live snapshots;
- actual open-to-completed HALT transitions observed naturally in Nasdaq RSS;
- Nasdaq corrections to already known non-NULL values;
- whether multiple observations of one natural halt can ever coexist inside a single RSS snapshot;
- long-term snapshot provenance requirements.

The current strict RAW-to-CORE mapping remains fail-fast. If expanded historical or live data violates the current one-to-one assumption, the database model must be reviewed rather than silently approximated.

## Platform Architecture

The overall QuantLab collaboration, GitHub, PostgreSQL, automation and infrastructure architecture is documented in:

```text
docs/architecture.md
```
