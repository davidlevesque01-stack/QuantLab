# QuantLab â€“ Nasdaq HALT Metrics Specification

**Version:** V0.8
**Status:** Analytical reference specification

## 1. Scope

This document defines the official calculation rules for the 11 Nasdaq HALT metrics used by the QuantLab HALT application.

Metrics 1â€“9 are **Historical / Predictive Features**.
Metrics 10â€“11 are **Observation-Day Features**.

## 2. Observation Context

Each calculation is associated with:
- Ticker
- Observation Date `T`
- Lookback Period `X` months
- HALT reason-code selection

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

Metrics 1â€“9 use:

`T-X months â†’ before T`

The observation day `T` is excluded from Metrics 1â€“9.

### 2.4 Observation-Day Window

Metrics 10â€“11 use observation day `T`.

## 3. HALT Episode Basis

All episode-based metrics use the QuantLab CORE HALT episode model.

### 3.1 One Continuous HALT = One Episode

A ticker remains in the same episode from `halt_start` until a valid HALT end is established.

Episode identity does not depend on reason code.

Multiple RAW events, reason codes, duplicate starts, overlapping records, or a NULL end combined with a valid end may therefore represent one CORE episode.

### 3.2 Multiple Reason Codes

Example:

`LUDP 10:45:00 â†’ 10:55:12`
`M 10:45:00 â†’ 10:55:12`

Result:

`1 CORE HALT episode`

Both reason codes may remain as descriptive attributes.

### 3.3 NULL End

Example:

`ABC 12:45:56 â†’ NULL`
`ABC 12:45:56 â†’ 13:23:12`

Result:

`1 CORE HALT episode`

The valid end is used for duration/temporal calculations.

If no valid end exists, `halt_end = NULL`.

## 4. Historical / Predictive Metrics

### Metric 1 â€” Number of Halt Days

Number of distinct trading days in the historical window on which the ticker experienced at least one qualifying HALT.

`COUNT(DISTINCT halt_trading_day)`

Multiple HALTs on one trading day count once.

### Metric 2 â€” Average Halts per Halt Day

`Total qualifying CORE HALT episodes / Number of Halt Days`

If Number of Halt Days is zero:

`N/A`

Multiple reason codes for one continuous episode count once.

### Metric 3 â€” Days Since Last Halt

Number of calendar days between the most recent Halt Day and `T`.

`T - most_recent_halt_day`

If no qualifying HALT occurred in the historical window:

`N/A`

### Metric 4 â€” Average Time Between Halt Days

Average number of calendar days between consecutive distinct Halt Days.

If fewer than two Halt Days are available:

`N/A`

### Metric 5 â€” Sequential Halt Days Identified

`Yes` when at least two consecutive trading sessions contain a qualifying HALT; otherwise `No`.

Weekends and market holidays do not interrupt a sequential block.

### Metric 6 â€” Number of Sequential Halt-Day Blocks

Number of distinct blocks containing at least two consecutive trading days with a qualifying HALT.

### Metric 7 â€” Average Sequential Block Length

Average number of trading days across all sequential Halt-Day blocks.

If no sequential block exists:

`N/A`

### Metric 8 â€” Maximum Sequential Block Length

Maximum number of consecutive trading days in any sequential Halt-Day block.

If no sequential block exists:

`N/A`

### Metric 9 â€” Number of Halt Days at Close

Number of distinct trading days in the historical window for which the ticker remained in HALT at market close.

Market close:

`16:00 ET`

A multi-day episode may contribute one Halt-at-Close day for each trading day on which it remains halted at 16:00 ET.

Example:

`Monday 14:30 â†’ Wednesday 10:00`

contributes:
- Monday = Halt at close
- Tuesday = Halt at close
- Wednesday = not Halt at close

Result:

`2 Halt Days at Close`

## 5. Observation-Day Metrics

### Metric 10 â€” Did the Ticker HALT the Specified Day?

`Yes` if at least one qualifying CORE HALT episode occurred on `T`; otherwise `No`.

### Metric 11 â€” Number of HALTs on the Specified Day

If Metric 10 = `Yes`, return the number of qualifying CORE HALT episodes during `T`.

If Metric 10 = `No`, return `0`.

Multiple reason codes for one continuous episode count once.

## 6. Reason-Code Filtering

Default selection:

`LULD`

The application supports:
- a single reason code
- aggregation of multiple reason codes

An aggregation acts as a logical OR for qualification.

If several selected reason codes occur in the same continuous episode, that episode is counted once.

## 7. Temporal Integrity / Look-Ahead Prevention

Metrics 1â€“9 shall use only information available before `T`.

Therefore:
- events after `T` cannot influence Metrics 1â€“9;
- `T` itself is excluded from Metrics 1â€“9;
- Metrics 10â€“11 explicitly use `T`.

This distinction is mandatory for future predictive-model use.

## 8. Trading Calendar

Sequential-day calculations use the market trading calendar.

Weekends and market holidays do not break a sequential block.

Calendar-day arithmetic is used for Metrics 3 and 4.

## 9. Output Order

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

## 10. Batch Calculation Principle

For each ticker/date/reason-code context, Metrics 1â€“9 should be derived from a reusable historical HALT dataset rather than independently re-reading and recalculating the same source data for each metric.

The implementation shall support potentially large batch files and should reuse overlapping historical calculations where practical without changing metric results.
