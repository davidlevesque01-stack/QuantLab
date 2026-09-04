# QuantLab – Nasdaq HALT Application Requirements

**Version:** V1.0
**Status:** Functional requirements

## 1. Purpose

The application shall provide a user interface for querying and calculating historical Nasdaq HALT statistics for individual ticker/date observations and for batch files containing ticker/date observations.

The application shall support exploratory/manual analysis and batch generation of outputs suitable for integration into a Master Model.

The implementation shall support a potentially large number of ticker/date observations and shall not assume a fixed batch size such as approximately 350 records.

## 2. Input Requirements

### 2.1 Input Modes

The input GUI shall support:
1. Manual mode
2. File mode

### 2.2 GUI Language

The GUI shall be in English.

### 2.3 Manual Mode

**Ticker name**
- Text field
- Displayed/formatted in CAPS
- Value = ticker ID

**Start Date**
- Date field, format `DD/MM/YYYY`
- Default = today's date
- Defines observation date `T`
- If omitted, `T = today`

**Period (months from Start Date)**
- Number field
- Default = 36 months
- Configurable by the user
- Defines the number of months before Start Date used for historical calculations
- If empty, the historical period begins at the oldest available date in the database before `T`

**HALT reason code**
- List of Nasdaq HALT reason codes
- Default = LUDP
- Supports a single code or aggregation of multiple codes
- Selected codes determine which HALT episodes qualify

### 2.4 File Mode

Input shall be `.XLSX` by default or `.CSV` optionally.

CSV separators supported:
- `,`
- `;`

Each row is a separate observation and shall contain:

| Date | Ticker |
|---|---|
| 03/01/2024 | ABCD |
| 03/04/2024 | DEFG |
| 03/07/2024 | HIJK |
| 03/12/2024 | TUVW |

## 3. Output Requirements

### 3.1 File Mode

Default output = `.XLSX`.

CSV output may be supported optionally with separator `,`.

The output shall contain the original input columns plus Metrics 1–11.

There shall be exactly one output row for each input ticker/date observation.

Columns shall be:

`Date | Ticker | Metric 1 | Metric 2 | ... | Metric 11`

Each metric shall occupy its own column for direct integration into a Master Model.

### 3.2 Manual Mode

The metrics shall be displayed in the GUI in a format equivalent to the output-file structure.

## 4. Metric Groups

### 4.1 Historical / Predictive Features

Metrics 1–9 use only information available before observation date `T`, inclusive.

Historical window:

`T-X months → through T, inclusive`

where:
- `X = 36 months` by default
- `X` is configurable in months
- if Period is empty, the window begins at the oldest available database date before `T`

### 4.2 Observation-Day Features

Metrics 10–11 use information from observation day `T`.

## 5. Required Metrics

### Metric 1 — Number of Halt Days

Number of distinct trading days during the historical lookback period on which the ticker experienced at least one qualifying HALT.

Multiple HALTs on the same trading day count as one Halt Day.

### Metric 2 — Average Halts per Halt Day

`Total qualifying CORE HALT episodes / Number of distinct Halt Days`

If there are no Halt Days, return `N/A`.

Multiple reason codes describing one continuous HALT count as one episode.

### Metric 3 — Days Since Last Halt

Number of calendar days between the most recent Halt Day in the historical window and observation date `T`.

If no HALT occurred during the lookback period, return `N/A`.

### Metric 4 — Average Time Between Halt Days

Average number of calendar days between consecutive distinct Halt Days.

If fewer than two Halt Days are available, return `N/A`.

### Metric 5 — Sequential Halt Days Identified

`Yes` if the ticker halted on two or more consecutive trading days; otherwise `No`.

Consecutive means consecutive trading sessions. Weekends and market holidays do not interrupt a sequential block.

### Metric 6 — Number of Sequential Halt-Day Blocks

Number of distinct blocks containing at least two consecutive trading days on which the ticker experienced a qualifying HALT.

### Metric 7 — Average Sequential Block Length

Average number of consecutive trading days across all identified sequential Halt-Day blocks.

If no sequential block exists, return `N/A`.

### Metric 8 — Maximum Sequential Block Length

Maximum number of consecutive trading days in any identified sequential Halt-Day block.

If no sequential block exists, return `N/A`.

### Metric 9 — Number of Halt Days at Close

Number of distinct trading days during the historical lookback period for which the ticker was still in HALT at market close.

Market close = `16:00 ET`.

A multi-day episode may contribute one Halt-at-Close day for each trading day on which the ticker remained halted at 16:00 ET.

### Metric 10 — Did the Ticker HALT the Specified Day?

`Yes` if the ticker experienced at least one qualifying HALT episode on observation day `T`; otherwise `No`.

### Metric 11 — Number of HALTs on the Specified Day

If Metric 10 is `Yes`, return the number of qualifying CORE HALT episodes during observation day `T`.

If Metric 10 is `No`, return `0`.

## 6. HALT Episode Business Rules

### 6.1 Continuous HALT = One Episode

Once a ticker enters HALT, it remains in the same episode until a valid HALT end is established.

A continuous HALT is one episode regardless of:
- number of RAW events
- number of reason codes
- multiple records with the same `halt_start`
- duplicate or overlapping records
- a NULL end combined with another valid end for the same continuous HALT

### 6.2 Multiple Reason Codes

Example:

`M 10:45:00 → 10:55:12`
`LUDP 10:45:00 → 10:55:12`

These represent one continuous HALT episode, not two HALTs.

Reason codes remain available as episode attributes.

### 6.3 NULL HALT End

Example:

`ABC 12:45:56 → NULL`
`ABC 12:45:56 → 13:23:12`

Result = one CORE HALT episode, using the valid end.

If no valid end exists, CORE `halt_end` remains NULL.

## 7. Reason-Code Filtering

The default HALT reason selection is `LUDP`.

The application shall support:
- one reason code
- an aggregation of multiple reason codes

Multiple selected codes shall act as a logical OR for event qualification.

Even when multiple selected reason codes occur in the same continuous episode, the episode counts once.

## 8. Temporal Integrity

Metrics 1–9 are historical/predictive features and shall use the historical window ending on `T`, inclusive.

Metric 10 and Metric 11 explicitly use day `T`.

This distinction shall be preserved to prevent look-ahead/data leakage in future predictive models.

## 9. Trading Calendar

Sequential calculations shall use the market trading calendar.

Weekends and market holidays do not interrupt sequential Halt-Day blocks.

Calendar-day arithmetic is used for Metrics 3 and 4.

## 10. Scalability

The implementation shall support potentially large batch files.

The design should avoid independently re-reading and recalculating the same historical data for every metric or repeated observation context.

Metrics 1–9 should be calculated from a reusable historical HALT dataset for each applicable ticker/date/reason-code context.

## 11. Acceptance Criteria

The application is compliant when:
1. Manual and file modes are available.
2. GUI language is English.
3. Ticker input is normalized/displayed in CAPS.
4. Start Date defaults to today.
5. Period defaults to 36 months and is configurable.
6. Empty Period uses the oldest available database date before T.
7. LUDP is the default reason selection.
8. Single and multiple reason selections are supported.
9. XLSX and CSV input are supported.
10. XLSX is the default output.
11. One output row is produced per input ticker/date observation.
12. Metrics 1–9 use the historical window ending on T, inclusive.
13. Metrics 10–11 use observation day T.
14. Continuous HALTs are counted as one episode regardless of reason-code multiplicity or duplicate/overlapping RAW records.
15. Sequential days use trading sessions rather than calendar dates.
16. Metric 9 counts distinct trading days halted at 16:00 ET.
17. Output is suitable for Master Model integration.
