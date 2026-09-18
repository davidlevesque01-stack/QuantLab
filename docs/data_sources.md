# QuantLab — Data Sources Registry

Cross-cutting registry of which external provider serves which QuantLab need, and
its current status. This is an index, not a decision narrative — the reasoning
behind each choice lives in the referenced component document. Update this file
whenever a provider decision changes; it should always reflect current reality,
not history (component docs carry the "why" and the timeline).

| Need | Provider | Status | Access mechanism | Details |
|---|---|---|---|---|
| Consolidated U.S. equities OHLCV 1-minute | Massive (formerly Polygon.io), US Stocks SIP `minute_aggs_v1` | Primary, MVP | Paid API, daily bulk flat file | `docs/backtesting/BACKTESTING_COMPONENT.md` |
| Consolidated U.S. trades/quotes (tick) | Massive, `trades_v1`/`quotes_v1` | Optional, validation/future | Paid API | `docs/backtesting/BACKTESTING_COMPONENT.md` |
| Premarket/since-close news | Massive (Benzinga feed via `GET /v2/reference/news`) | Primary | Paid API, same vendor as market data | `collectors/warrants/docs/WARRANTS_COMPONENT.md` |
| Venue microstructure / order book | Databento (`XNAS.ITCH`) or direct venue feeds | Future optional | N/A yet | `docs/backtesting/BACKTESTING_COMPONENT.md` |
| Nasdaq HALTs / resumptions | Nasdaq Trader (existing collector) | Primary, mature | Existing `collectors/nasdaq_halts` | `docs/architecture.md` §5 |
| Nasdaq symbol directory | Nasdaq Trader | Primary | Existing `collectors/warrants/src/nasdaq_symbol_directory.py` | `docs/database.md` §5.13 |
| SEC filings / regulatory data | SEC EDGAR | Primary, authoritative | Existing SEC-native pipeline (SEC-01 through SEC-18) | `docs/database.md` §5.10-5.20 |
| Country / foreign-issuer flag | SEC EDGAR (10-K vs. 20-F, issuer address) | Primary | Existing SEC pipeline — no new vendor | `collectors/warrants/docs/WARRANTS_COMPONENT.md` |
| Per-series warrant/convertible terms (strike, quantity, expiration) | SEC EDGAR (8-K/424B exhibits and text extraction) | Primary, kept active | Existing SEC-native pipeline (SEC-06 through SEC-18) | `collectors/warrants/docs/WARRANTS_COMPONENT.md` |
| Float, institutional ownership %, cash runway, dilution score, ATM/shelf $ amounts | DilutionWatch (dilutionwatch.com) | Primary secondary source | Paid API (`dilutionwatch.com/api/v1/`) | `collectors/warrants/docs/WARRANTS_COMPONENT.md` |
| DilutionTracker (dilutiontracker.com) | — | **Manual reference only, never automated** | Human browsing under own account | `collectors/warrants/docs/DILUTIONTRACKER_GROUND_TRUTH.md` |
| Sector of activity | Not yet confirmed | Open — do not assume TradingView exposes this via API | TBD | `collectors/warrants/docs/WARRANTS_COMPONENT.md` |
| Equity line registered? | Not yet confirmed on DilutionWatch | Open — verify before relying on it | TBD | `collectors/warrants/docs/WARRANTS_COMPONENT.md` |
| ITM/resistance warrant-vs-price calculations | QuantLab Feature Engine (computed, not sourced) | Primary — internal only | SEC terms + Massive price, computed in-house | `docs/backtesting/BACKTESTING_GITHUB_BACKLOG.md` BT-14 |

## Provenance tags

Every value stored across `raw`/`core` should be traceable to one of:

```text
MASSIVE
NASDAQ
FINRA
SEC
DILUTIONWATCH
DILUTIONTRACKER   -- manual ground-truth rows only, never automated
QUANTLAB_DERIVED
```

## Sources evaluated and rejected

Kept here so the reasoning isn't re-litigated from scratch later.

- **DilutionTracker as an automated source** — rejected. No API/export exists;
  Terms of Service explicitly ban all automated access with automatic license
  termination and full account-content deletion on violation. See
  `collectors/warrants/docs/WARRANTS_COMPONENT.md`, "DilutionTracker — corrected
  status".
- **IEX Cloud** — rejected. Shut down permanently 2024-08-31.
- **Tiingo** for intraday — rejected as primary. Intraday coverage is sourced
  through IEX (not full consolidated SIP), better suited to EOD/fundamentals.
- **`dilutracker.com` / `stockdilutiontracker.com`** — not evaluated. These
  domains surface prominently in searches for "DilutionTracker API" despite being
  distinct from the real `dilutiontracker.com`; treat as unverified/low-trust
  until independently vetted, not as the same provider.
