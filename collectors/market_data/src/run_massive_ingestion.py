"""CLI: ingest one Nasdaq trading day's Massive minute_aggs_v1 flat file
into raw.market_bar_1m / core.market_bar_1m (BT-11).

Downloads and caches the whole day's flat file on disk regardless of the
watchlist (see collectors/market_data/config/watchlist.json) -- only what
gets persisted into Postgres is filtered. Massive data for a given trading
day lags roughly one day (published ~11:00 ET the next day), so
--trading-day must be in the past.

Usage:
    python -m collectors.market_data.src.run_massive_ingestion \
        --trading-day 2026-08-14
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from collectors.market_data.src.market_data_paths import resolve_raw_directory
from collectors.market_data.src.market_data_watchlist import load_watchlist
from collectors.market_data.src.massive_adapter import MassiveAdapter

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = PROJECT_ROOT / "config" / "config.json"
WATCHLIST_FILE = PROJECT_ROOT / "config" / "watchlist.json"


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trading-day", required=True, type=date.fromisoformat)

    return parser.parse_args()


def main():
    args = parse_arguments()

    if args.trading_day >= date.today():
        raise ValueError(
            "Massive data lags roughly one trading day; --trading-day must be in the past."
        )

    with open(CONFIG_FILE, encoding="utf-8") as handle:
        config = json.load(handle)

    raw_directory = resolve_raw_directory(PROJECT_ROOT, config)
    tickers = load_watchlist(WATCHLIST_FILE)

    if not tickers:
        raise ValueError(
            f"{WATCHLIST_FILE} has no tickers configured -- add at least one "
            "before running a real ingestion (the raw flat file is still "
            "downloaded and cached in full regardless)."
        )

    adapter = MassiveAdapter(raw_directory)
    result = adapter.ingest_trading_day(args.trading_day, tickers=tickers)

    print(f"trading_day: {args.trading_day.isoformat()}")
    print(f"tickers: {sorted(tickers)}")
    print(f"raw: {result['raw']}")
    print(f"core: {result['core']}")


if __name__ == "__main__":
    main()
