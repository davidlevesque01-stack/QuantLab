# Warrants Component — Architecture Decision and Delivery Plan

**Project:** QuantLab  
**Domain:** Capital Structure & Dilution  
**Component:** Warrants  
**Status:** Approved for implementation

## Decision

QuantLab will create a dedicated `warrants` component as the first implementation
unit of the broader Capital Structure & Dilution capability.

The component will use a hybrid source strategy:

- SEC EDGAR remains the authoritative legal source.
- Nasdaq Trader and FINRA provide security/listing/corporate-action metadata.
- DilutionTracker is used as a licensed, structured secondary source for bootstrap,
  normalization and validation.

QuantLab will preserve its independence from DilutionTracker by storing provenance,
linking material records back to SEC filings, and progressively developing its own
primary-source ingestion.

## DilutionTracker bootstrap

QuantLab has obtained written confirmation from DilutionTracker regarding retention
and continued internal use of historical data acquired while subscribed.

The planned bootstrap is therefore:

1. Activate the plan supporting 5,000 unique tickers/month and five years of history.
2. Load the historical universe into QuantLab.
3. Keep the original API responses in the RAW layer.
4. Build normalized point-in-time CORE records.
5. Reconcile selected records to SEC EDGAR.
6. At the end of the bootstrap period, measure ongoing value and choose whether to
   retain a lower plan, use periodic reconciliation subscriptions, or stop the service.

## Architectural principles

### 1. RAW is immutable evidence

Every DilutionTracker response used by QuantLab should be stored with:

- ticker;
- endpoint;
- retrieval timestamp;
- API version if available;
- complete JSON payload or an equivalent lossless representation.

### 2. CORE is normalized and point-in-time

CORE records must represent historical state, not only the latest state.

### 3. Provenance is first-class data

Important values must identify their origin:

- `DILUTIONTRACKER`
- `SEC`
- `NASDAQ`
- `FINRA`
- `QUANTLAB_DERIVED`

### 4. SEC remains the source of truth

A DilutionTracker value can be useful and operationally trusted while still being
classified as derived/secondary data. Material discrepancies should trigger review
against the corresponding SEC filing.

### 5. No website scraping

Use only authorized/documented access mechanisms for DilutionTracker. Do not scrape
the website to build QuantLab datasets.

## Initial logical data model

### `core.security`

Represents securities associated with an issuer.

Candidate security types:

- COMMON_STOCK
- WARRANT
- PREFUNDED_WARRANT
- PREFERRED
- CONVERTIBLE
- UNIT
- RIGHT

### `core.warrant`

Stable identity and relatively invariant warrant attributes.

Candidate fields:

- `id`
- `issuer_id`
- `security_id`
- `warrant_type`
- `issue_date`
- `exercise_start_date`
- `expiration_date`
- `exchange_traded`
- `status`

### `core.warrant_term_history`

Point-in-time terms and quantities.

Candidate fields:

- `id`
- `warrant_id`
- `effective_from`
- `effective_to`
- `exercise_price`
- `exercise_ratio`
- `warrants_outstanding`
- `underlying_shares`
- `cash_exercise`
- `cashless_exercise`
- `redemption_price`
- `redemption_trigger_price`
- `source_type`
- `source_reference`
- `source_date`
- `retrieved_at`

The physical PostgreSQL schema will be finalized after inspection of real API payloads.

## Validation POC

Before full backfill, select 5–10 representative tickers, including difficult cases:

- listed public warrant;
- pre-funded warrant;
- company with multiple warrant series;
- amended/repriced warrant;
- expired/exercised warrant;
- issuer with a recent HALT.

For each ticker:

1. retrieve DilutionTracker data;
2. retain raw payload;
3. normalize expected warrant records;
4. locate referenced SEC filings;
5. compare quantities, strike, expiration and type;
6. record discrepancies.

The full backfill starts only after this validation passes.

## Long-term target

DilutionTracker should become optional.

Target maturity:

```text
SEC + Nasdaq + FINRA
        ↓
QuantLab collectors
        ↓
RAW
        ↓
CORE Capital Structure
        ↓
Analytics
        ↓
HALT × dilution × market data
```

DilutionTracker can remain a reconciliation/benchmark source if its ongoing value
justifies the subscription cost.
