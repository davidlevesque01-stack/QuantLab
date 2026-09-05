# QuantLab – Nasdaq HALT Metrics Specification

**Version:** V1.0
**Status:** Analytical reference specification — aligned with Nasdaq Data Model V1.2

## 1. Scope

This document defines the official calculation rules for the 11 Nasdaq HALT metrics used by the QuantLab HALT application.

Metrics 1–9 are Historical / Predictive Features.
Metrics 10–11 are Observation-Day Features.

This specification also defines the distinction between HALT reason codes and Resumption reason codes.

## 2. Observation Context

Each calculation is associated with:

- Ticker
- Observation Date `T`
- Lookback Period `X` months
- Reason-code filter type
- Selected reason codes

### 2.1 Observation Date

If supplied:

`T = supplied date`

Otherwise:

`T = today`

### 2.2 Lookback Period

Default:

`X = 36 months`

`X` is configurable in months.

If Period is empty, the historical window begins at the oldest available database date before `T`.

### 2.3 Historical Window

Metrics 1–9 use:

`T-X months → through T, inclusive`

The observation day `T` is included in Metrics 1–9.

### 2.4 Observation-Day Window

Metrics 10–11 use observation day `T`.

## 3. HALT Episode Basis

All episode-based metrics use the QuantLab CORE HALT episode model.

### 3.1 One Continuous HALT = One Episode

A ticker remains in the same CORE episode from `halt_start` until a valid HALT end / resumption is established.

Episode identity does not depend on reason code.

Multiple RAW events, duplicate starts, overlapping records, reason-code changes, or a NULL end followed by a later valid resumption may therefore represent one CORE episode.

### 3.2 HALT Reason Codes

A HALT reason code describes the reason associated with the HALT.

HALT reason codes are used for the primary HALT analytical filtering.

An episode may contain more than one HALT reason code.

### 3.3 Resumption Reason Codes

A Resumption reason code describes an event associated with the resumption of trading.

A Resumption reason code does not create a new CORE HALT episode.

Resumption reason codes are retained as separate episode attributes.

They must not be silently treated as HALT reason codes.

### 3.4 Example – GPUS

For example:

`GPUS / AMEX`

HALT:

`2026-08-14 14:15:13.698`

HALT reason:

`H11`

RESUMPTION:

`2026-08-25 09:00:00`

Resumption reason:

`T3`

This represents:

`1 CORE HALT episode`

not two episodes.

### 3.5 Multiple HALT Reason Codes

Example:

`LUDP 10:45:00 → 10:55:12`

`M 10:45:00 → 10:55:12`

Result:

`1 CORE HALT episode`

Both HALT reason codes are retained.

### 3.6 NULL End

Example:

`ABC 12:45:56 → NULL`

followed by:

`ABC 12:45:56 → 13:23:12`

Result:

`1 CORE HALT episode`

The valid end is used for duration and temporal calculations.

If no valid resumption/end exists:

`halt_end = NULL`


## 3.7 Alignment with PostgreSQL Data Model V1.2

The analytical episode basis defined in this specification is aligned with the validated PostgreSQL V1.2 model.

The three relevant persistence levels are:

```text
Distinct Nasdaq observation
        |
        +----> raw.nasdaq_resumption
        |
        v
Canonical HALT
        |
        v
raw.nasdaq_trade_halt
        |
        v
CORE episode
core.nasdaq_halt_episode
```

The CORE natural identity is:

```text
symbol
market
halt_start
```

`reason_code` is descriptive at CORE level and does not create a distinct episode identity.

The explicit relationship table:

```text
core.nasdaq_halt_episode_event
```

supports:

```text
1 CORE episode -> N RAW HALT events
```

Distinct source observations may also map to one canonical `raw.nasdaq_trade_halt`.

The analytical layer must therefore count qualifying CORE episodes rather than raw source observations unless a metric explicitly states otherwise.

## 4. Historical / Predictive Metrics

### Metric 1 — Number of Halt Days

Number of distinct trading days in the historical window on which the ticker experienced at least one qualifying HALT.

`COUNT(DISTINCT halt_trading_day)`

Multiple HALTs on one trading day count once.

### Metric 2 — Average Halts per Halt Day

`Total qualifying CORE HALT episodes / Number of Halt Days`

If Number of Halt Days is zero:

`N/A`

Multiple reason codes for one continuous episode count once.

### Metric 3 — Days Since Last Halt

Number of calendar days between the most recent Halt Day and `T`.

`T - most_recent_halt_day`

If no qualifying HALT occurred in the historical window:

`N/A`

### Metric 4 — Average Time Between Halt Days

Average number of calendar days between consecutive distinct Halt Days.

If fewer than two Halt Days are available:

`N/A`

### Metric 5 — Sequential Halt Days Identified

`Yes` when at least two consecutive trading sessions contain a qualifying HALT; otherwise `No`.

Weekends and market holidays do not interrupt a sequential block.

### Metric 6 — Number of Sequential Halt-Day Blocks

Number of distinct blocks containing at least two consecutive trading days with a qualifying HALT.

### Metric 7 — Average Sequential Block Length

Average number of trading days across all sequential Halt-Day blocks.

If no sequential block exists:

`N/A`

### Metric 8 — Maximum Sequential Block Length

Maximum number of consecutive trading days in any sequential Halt-Day block.

If no sequential block exists:

`N/A`

### Metric 9 — Number of Halt Days at Close

Number of distinct trading days in the historical window for which the ticker remained in HALT at market close.

Market close:

`16:00 ET`

A multi-day episode may contribute one Halt-at-Close day for each trading day on which it remains halted at 16:00 ET.

Example:

`Monday 14:30 → Wednesday 10:00`

contributes:

- Monday = Halt at close
- Tuesday = Halt at close
- Wednesday = not Halt at close

Result:

`2 Halt Days at Close`

## 5. Observation-Day Metrics

### Metric 10 — Did the Ticker HALT the Specified Day?

`Yes` if at least one qualifying CORE HALT episode occurred on `T`; otherwise `No`.

### Metric 11 — Number of HALTs on the Specified Day

If Metric 10 = `Yes`, return the number of qualifying CORE HALT episodes during `T`.

If Metric 10 = `No`, return `0`.

Multiple reason codes for one continuous episode count once.

## 6. Reason-Code Filtering

The application supports three analytical filter contexts:

1. HALT Reason Code
2. Resumption Reason Code
3. Both

### 6.1 HALT Reason Code Filter

The selected codes qualify an episode according to its HALT reason codes.

Default selection:

`LUDP`

Multiple selected HALT reason codes act as a logical OR.

If several selected HALT reason codes occur in the same continuous episode, that episode is counted once.

### 6.2 Resumption Reason Code Filter

The selected codes qualify an episode according to its Resumption reason codes.

A Resumption reason code does not redefine the original HALT reason.

### 6.3 Both

When both filter types are selected, the application shall explicitly define the logical relationship between the two selections.

The implementation must not infer this relationship implicitly.

### 6.4 Reason-Code Trail

The system shall preserve the reason-code information associated with an episode.

HALT reason codes and Resumption reason codes shall remain distinguishable.

The application shall expose both categories when episode data is displayed.

## 7. RAW and CORE Data Integrity

### 7.1 Immutable Source Provenance

The immutable Nasdaq XML files are the primary RAW source-of-truth artifacts.

Historical files and timestamped live snapshots must not be modified to rewrite source history.

The PostgreSQL RAW layer is structured persistence derived from those immutable source files and is not itself an append-only copy of every source snapshot.

### 7.2 Canonical RAW HALT

`raw.nasdaq_trade_halt` contains one canonical structured HALT per V1.2 natural key:

```text
symbol
market
halt_date
halt_time
reason_code
```

Multiple distinct Nasdaq observations may map to the same canonical RAW HALT.

A later valid observation may enrich the canonical structured representation without modifying the immutable source XML.

### 7.3 Resumption Observations

Distinct resumption observations are retained in:

```text
raw.nasdaq_resumption
```

Their observation identity includes:

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

The PostgreSQL uniqueness rule uses `UNIQUE NULLS NOT DISTINCT` so observations containing nullable quote/trade times remain idempotent.

Invalid source observations may remain preserved in `raw.nasdaq_resumption` even when they are not eligible to become the canonical RAW resumption.

### 7.4 Canonical Resumption

The canonical RAW resumption is selected from one source observation.

Resumption fields must not be assembled by combining values from multiple observations.

Conceptually:

```text
Rank 2 = complete and temporally valid
Rank 1 = partial but admissible
Rank 0 = unusable or temporally invalid
```

For multiple complete valid observations, the latest valid HALT end is selected deterministically.

If all available observations are invalid, the canonical resumption fields in `raw.nasdaq_trade_halt` remain `NULL`.

### 7.5 Complementary Collection

Historical collection may use complementary Nasdaq views or queries, including HALT-oriented and resumption-oriented information.

These views must not automatically be treated as independent CORE HALT episodes.

### 7.6 CORE Enrichment

Later source information may enrich the canonical RAW representation and the associated CORE episode.

A resumption observation does not create a new CORE episode solely because it carries different descriptive reason information.

### 7.7 Provenance

The system shall preserve sufficient provenance to identify the source file and collection context of HALT and resumption information.

Immutable XML files remain the authoritative source provenance.


## 8. Temporal Integrity / Look-Ahead Prevention

Metrics 1–9 shall use the historical window ending on `T`, inclusive.

Therefore:

- events after `T` cannot influence Metrics 1–9;
- `T` itself is included in Metrics 1–9;
- Metrics 10–11 explicitly use `T`.

Information about a resumption after `T` shall not be used to determine a metric for an observation date before that information was temporally available, unless the analytical definition explicitly permits retrospective reconstruction.

This distinction is mandatory for future predictive-model use.

## 9. Trading Calendar

Sequential-day calculations use the market trading calendar.

Weekends and market holidays do not break a sequential block.

Calendar-day arithmetic is used for Metrics 3 and 4.

The official QuantLab market-calendar implementation is not yet certified in PostgreSQL.

Therefore, Metrics 5–9 remain governed by this specification, but any implementation that depends on trading-session boundaries must be validated against the future official market-calendar model before PROD analytical certification.

## 10. Output Order

The output metric columns shall appear in this order:

1. Number of Halt Days
2. Average Halts per Halt Day
3. Days Since Last Halt
4. Average Time Between Halt Days
5. Sequential Halt Days Identified
6. Number of Sequential Halt-Day Blocks
7. Average Sequential Block Length
8. Maximum Sequential Block Length
9. Number of Halt Days at Close
10. Did the Ticker HALT the Specified Day?
11. Number of HALTs on the Specified Day

## 11. Episode Data Exposure

When an episode is exposed by the application, both HALT and Resumption information shall be available when present.

At minimum:

- Ticker
- Market
- HALT Start
- HALT Reason Code(s)
- Resumption Date/Time
- Resumption Reason Code(s)
- HALT End
- Duration
- Halt-at-Close status

The application shall not collapse HALT and Resumption reason codes into one undifferentiated field.

## 12. Historical Backfill and Rebuild

The V1.2 persistence architecture supports historical rebuild from immutable Nasdaq XML provenance.

When additional historical resumption information is collected or the persistence model changes, the rebuild process shall:

1. Preserve immutable source XML files.
2. Collect missing source information when required.
3. Deduplicate distinct Nasdaq observations.
4. Rebuild canonical RAW HALTs.
5. Preserve distinct resumption observations.
6. Associate RAW events with the correct CORE episode.
7. Rebuild or update CORE derived data.
8. Recalculate dependent analytical datasets.
9. Validate results against known reference cases.

The full historical corpus through 2026-08-28 has been processed under the V1.2 persistence model.

Reference persistence counts are:

```text
Distinct observations       : 68170
Canonical RAW HALTs         : 68072
Resumption observations     : 68147
CORE episodes               : 68017
```

QVCG and the fixed BCARU historical fixture currently pass.

The GPUS episode spanning 2026-08-14 through 2026-08-25 remains an important analytical validation case for HALT-versus-resumption semantics.

## 13. Batch Calculation Principle

For each ticker/date/reason-code context, Metrics 1–9 should be derived from a reusable historical HALT dataset rather than independently re-reading and recalculating the same source data for each metric.

The implementation shall support potentially large batch files and should reuse overlapping historical calculations where practical without changing metric results.
