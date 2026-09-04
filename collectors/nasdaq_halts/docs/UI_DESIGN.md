# QuantLab - Nasdaq HALT Application UI Design

**Version:** V1.0  
**Status:** Design specification

---

## 1. Purpose

This document defines the user-interface design for the QuantLab Nasdaq HALT
Analytics application.

The UI shall provide two input modes:

1. Manual Mode
2. File Mode

The UI shall collect user inputs, validate them, invoke the analytical
service, display results, and provide batch output.

The UI shall not implement HALT metric calculation logic or direct database
business logic.

Functional behavior shall comply with:

- `REQUIREMENTS.md`
- `METRICS_SPECIFICATION.md`

---

## 2. Technology

### 2.1 GUI Framework

The application shall use:

**PySide6 (Qt for Python)**

The application is intended to run as a Windows desktop application.

### 2.2 Language

All user-visible GUI text shall be in English.

---

## 3. UI Architecture

The UI shall be separated from the analytical and persistence layers.

```text
User
  |
  v
GUI
  |
  v
Input Validation
  |
  v
Analysis Service
  |
  v
Metrics Engine
  |
  v
PostgreSQL CORE
```

The GUI shall not:

- calculate Metrics 1---11 directly;
- implement CORE episode construction;
- implement HALT reason-code qualification;
- implement trading-calendar calculations;
- contain PostgreSQL business rules.

---

## 4. Application Navigation

The main window shall provide two primary input modes:

```text
[ Manual Mode ]    [ File Mode ]
```

Only one input mode shall be active at a time.

The user shall be able to return to the main input selection after
completing a calculation.

---

# 5. Main Window

## 5.1 Main Screen

The main screen shall identify the application as:

**QuantLab - Nasdaq HALT Analytics**

The user shall be presented with:

```text
INPUT MODE

[ MANUAL MODE ]

[ FILE MODE ]
```

The interface shall remain intentionally simple.

---

# 6. Manual Mode

## 6.1 Input Fields

Manual Mode shall provide the following fields.

### Ticker

Label:

`Ticker`

Control:

Text field

Behavior:

- User enters a ticker ID.
- The value shall be normalized/displayed in uppercase.

### Start Date

Label:

`Start Date`

Control:

Date field

Format:

`DD/MM/YYYY`

Default:

Today's date.

This field defines observation date `T`.

### Historical Period

Label:

`Historical Period (months)`

Control:

Numeric field

Default:

`36`

The value defines `X`, the number of months preceding `T` used for historical
metrics.

The user may configure the value.

If the field is empty, the historical window shall begin at the oldest
available database date before `T`.

### HALT Reason Code

Label:

`HALT Reason Code`

Control:

Multi-select list.

Default:

`LUDP`

The control shall support:

- one reason code;
- multiple reason codes.

Multiple selected codes represent an OR qualification.

---

# 7. Manual Mode Layout

```text
+---------------------------------------------------------------+
| QuantLab - Nasdaq HALT Analytics                 Manual Mode   |
+---------------------------------------------------------------+
|                                                               |
| Ticker                                                        |
| [ ABCD                                                     ] |
|                                                               |
| Start Date                                                    |
| [ 04/09/2026                                               ] |
|                                                               |
| Historical Period (months)                                    |
| [ 36                                                       ] |
|                                                               |
| HALT Reason Code                                              |
| [ LUDP                                                     v] |
|                                                               |
|                                                               |
|                    [ CALCULATE ]                              |
|                                                               |
|                    [ File Mode ]                              |
+---------------------------------------------------------------+
```

---

# 8. Reason-Code Selection

The reason-code selector shall allow multiple selections.

Example:

```text
HALT Reason Code

+---------------------------+
| --- LUDP                    |
| --- M                       |
| --- T1                      |
| --- T2                      |
| --- T3                      |
| --- T12                     |
| --- D                       |
| --- H11                     |
+---------------------------+
```

When multiple codes are selected, the UI shall display the selected
qualification context.

Example:

`LUDP, M, T1`

The UI shall pass the selected codes to the analytical service.

The UI shall not determine whether multiple events constitute one CORE
episode. That is an analytical-layer responsibility.

---

# 9. Manual Validation

Validation shall occur before the analytical service is invoked.

The UI shall validate:

- ticker presence;
- ticker format;
- date validity;
- period validity when supplied;
- reason-code selection.

Validation errors shall be presented as user-readable messages.

Python exceptions and raw PostgreSQL exceptions shall not be displayed
directly to the user.

Examples:

```text
Ticker is required.
```

```text
Invalid date.
```

```text
Historical period must be a positive number of months.
```

---

# 10. Manual Calculation

When the user selects:

`CALCULATE`

the UI shall create an observation context containing:

```text
Ticker
Observation Date T
Historical Period X
Reason-Code Selection
```

The observation context shall be passed to the Analysis Service.

The GUI shall not calculate the metrics itself.

---

# 11. Calculation Progress

While a calculation is running, the UI shall indicate that processing is
in progress.

Example:

```text
+---------------------------------------------------------------+
|                       CALCULATING                             |
+---------------------------------------------------------------+
|                                                               |
| Ticker              ABCD                                     |
| Observation Date    04/09/2026                               |
| Historical Period   36 months                                |
| HALT Reason         LUDP                                     |
|                                                               |
| Preparing historical data...                                  |
|                                                               |
| [===============================>             ]               |
|                                                               |
|                         Please wait                           |
+---------------------------------------------------------------+
```

For batch processing, the UI may display:

```text
Processing observations

127 / 350
```

The implementation shall not impose a fixed maximum batch size.

---

# 12. Manual Results

The Manual Mode results shall be displayed in a structure equivalent to the
batch output structure.

The result shall display:

- Ticker
- Observation Date
- Historical Period
- HALT Reason Code
- Metrics 1---11

The metric order shall be:

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

Example:

```text
+---------------------------------------------------------------+
| RESULTS                                                       |
+---------------------------------------------------------------+
| Ticker              ABCD                                     |
| Observation Date    04/09/2026                               |
| Historical Period   36 months                                |
| HALT Reason         LUDP                                     |
+---------------------------------------------------------------+
| Metric                                      | Value           |
+----------------------------------------------+----------------+
| Number of Halt Days                          | 12              |
| Average Halts per Halt Day                   | 1.42            |
| Days Since Last Halt                         | 18              |
| Average Time Between Halt Days               | 31.7            |
| Sequential Halt Days Identified              | Yes             |
| Number of Sequential Halt-Day Blocks         | 2               |
| Average Sequential Block Length              | 2.5             |
| Maximum Sequential Block Length              | 3               |
| Number of Halt Days at Close                 | 4               |
| Did the Ticker HALT the Specified Day?       | No              |
| Number of HALTs on the Specified Day         | 0               |
+---------------------------------------------------------------+

[ NEW CALCULATION ]
```

---

# 13. File Mode

File Mode shall allow the user to select an input file.

Supported formats:

- XLSX (default)
- CSV (optional)

CSV separators:

- comma `,`
- semicolon `;`

The input file shall contain:

```text
Date
Ticker
```

Each row represents one observation.

---

# 14. File Mode Layout

```text
+---------------------------------------------------------------+
| QuantLab - Nasdaq HALT Analytics                    File Mode |
+---------------------------------------------------------------+
|                                                               |
| Input File                                                    |
| [ C:\...\observations.xlsx                    ] [ Browse ]    |
|                                                               |
| File Format                                                   |
|   --- XLSX                                                      |
|   --- CSV                                                       |
|                                                               |
| CSV Separator                                                 |
|   --- Comma (,)                                                 |
|   --- Semicolon (;)                                             |
|                                                               |
+---------------------------------------------------------------+
| ANALYSIS PARAMETERS                                            |
|                                                               |
| Historical Period (months)                                    |
| [ 36                                                        ] |
|                                                               |
| HALT Reason Code                                              |
| [ LUDP                                                     v] |
|                                                               |
|                                                               |
|                 [ VALIDATE FILE ]                             |
+---------------------------------------------------------------+
```

The Period and HALT Reason Code parameters shall apply to the batch.

---

# 15. File Validation

The application shall validate the input file before calculation.

Validation shall include:

- file existence;
- supported file format;
- required Date column;
- required Ticker column;
- valid dates;
- valid ticker values.

The validation result shall be displayed before calculation starts.

Example:

```text
+---------------------------------------------------------------+
| FILE VALIDATION                                               |
+---------------------------------------------------------------+
|                                                               |
| File              observations.xlsx                           |
| Format            XLSX                                       |
| Observations      350                                        |
|                                                               |
| Date column       --- Found                                     |
| Ticker column     --- Found                                     |
| Invalid dates     0                                          |
| Empty tickers     0                                          |
|                                                               |
|                  [ START CALCULATION ]                        |
+---------------------------------------------------------------+
```

---

# 16. Batch Processing

The batch processor shall process one observation context per input row.

For each row:

```text
Date
Ticker
```

the application shall create the corresponding observation context using
the selected batch parameters.

The implementation shall support potentially large input files.

The application shall not assume that the batch contains approximately 350
records.

---

# 17. Batch Output

The default output format shall be XLSX.

CSV output may optionally be supported.

The output shall contain:

```text
Date
Ticker
Metric 1
Metric 2
...
Metric 11
```

There shall be one output row for every input ticker/date observation.

The metric columns shall follow the official metric order.

---

# 18. Batch Completion

After successful batch processing, the UI shall display a completion
summary.

Example:

```text
+---------------------------------------------------------------+
| BATCH COMPLETE                                                |
+---------------------------------------------------------------+
|                                                               |
| Input observations       350                                  |
| Successfully calculated  350                                  |
|                                                               |
| Output file                                                    |
| [ C:\QuantLab\output\results.xlsx                            ] |
|                                                               |
|             [ OPEN OUTPUT ]    [ NEW ANALYSIS ]               |
+---------------------------------------------------------------+
```

The output file shall be suitable for integration into the Master Model.

---

# 19. Metric Display Rules

The UI shall display metric values returned by the analytical service.

The UI shall not alter metric values.

Special values shall be displayed according to the analytical specification.

Examples:

```text
N/A
Yes
No
0
```

The distinction between:

- historical metrics;
- observation-day metrics;

shall be preserved.

Metrics 1---9 use the historical window before `T`.

Metrics 10---11 use observation day `T`.

---

# 20. Error Handling

The application shall distinguish between:

### Input errors

Examples:

```text
Invalid ticker.
Invalid date.
Invalid period.
Invalid input file.
Missing required column.
```

### Processing errors

Example:

```text
Unable to calculate the requested observation.
```

### Database/service errors

The user shall receive a readable application-level message.

Technical details shall be available through application logging rather than
being exposed directly in the GUI.

---

# 21. UI / Analytics Boundary

The following responsibilities belong to the Analytics layer, not the UI:

- historical-window calculation;
- temporal filtering;
- CORE episode qualification;
- reason-code qualification;
- trading-calendar logic;
- sequential Halt-Day calculation;
- Halt-at-Close calculation;
- observation-day calculation;
- all Metric 1---11 formulas.

The UI is responsible only for:

- collecting inputs;
- validating inputs;
- presenting progress;
- invoking the Analysis Service;
- displaying results;
- initiating output generation.

---

# 22. Future Acquisition Integration

Automatic data acquisition is intentionally outside the scope of this UI V1.

The UI shall nevertheless communicate with the analytical layer through a
defined service boundary.

This allows a future acquisition workflow to update the underlying data
without requiring changes to the UI calculation workflow.

```text
Future:

Automatic Acquisition
        |
        v
      CORE
        |
        v
Analysis Service
        |
        v
       GUI
```

---

# 23. V1 Scope

The following are included:

- PySide6 desktop GUI
- English interface
- Manual Mode
- File Mode
- XLSX input
- CSV input
- CSV separator selection
- configurable historical period
- default 36-month period
- default LUDP reason selection
- multiple reason-code selection
- manual metric display
- batch calculation
- XLSX output
- optional CSV output
- calculation progress
- input validation
- application-level error handling

The following are outside the V1 UI scope:

- automatic Nasdaq acquisition;
- scheduling;
- predictive modelling;
- dashboards;
- database administration;
- RAW-data management;
- user authentication.

---

# 24. Design Principles

1. Keep the user interface simple.
2. Keep analytical logic outside the UI.
3. Preserve the official metric definitions.
4. Prevent look-ahead/data leakage.
5. Support large batch files.
6. Make Manual Mode and File Mode use the same analytical service.
7. Keep future automatic acquisition independent from the UI.
8. Do not introduce functional requirements that are not defined by the
   application requirements or metric specification.
