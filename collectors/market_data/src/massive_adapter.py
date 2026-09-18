"""Real intraday data provider integration: Massive minute_aggs_v1 (BT-11).

Implements the same QuantLabAdapter interface as CSVAdapter (BT-01) --
zero changes required in the Feature Engine or models. Massive's real
distribution is whole-market-per-day (one flat file, no per-ticker
download), so fetch_bars() exists for Protocol parity (downloads/parses/
caches the whole day once per adapter instance, then filters in-memory),
while ingest_trading_day() is the production bulk-ingestion path described
by the issue ("calls persist_market_bars() for every relevant row") -- see
docs/backtesting/BACKTESTING_GITHUB_BACKLOG.md#bt-11.
"""

from __future__ import annotations

import csv
import gzip
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from shared.calendar.trading_calendar import (
    classify_session,
    get_session_bounds,
    is_trading_day,
    to_nasdaq_local,
)

from collectors.market_data.src.market_data_postgresql import persist_market_bars
from collectors.market_data.src.massive_flatfile_client import (
    MASSIVE_DATASET,
    download_flat_file,
)

SOURCE_PROVIDER = "MASSIVE"
DATASET_VERSION = "minute_aggs_v1"
MARKET_SCOPE = "CONSOLIDATED_US"

_CANONICAL_KEYS = (
    "ticker",
    "market",
    "bar_start",
    "open",
    "high",
    "low",
    "close",
    "volume",
)


def _window_start_to_utc(window_start_ns: int) -> datetime:
    return datetime.fromtimestamp(window_start_ns / 1_000_000_000, tz=timezone.utc)


class MassiveAdapter:
    """Implements QuantLabAdapter against Massive's minute_aggs_v1 SIP flat
    files.
    """

    def __init__(self, raw_directory: Path, s3_client=None):
        self._raw_directory = Path(raw_directory)
        self._s3_client = s3_client
        self._day_cache: dict[date, list[dict]] = {}

    def fetch_bars(self, ticker: str, trading_day: date) -> list[dict]:
        """QuantLabAdapter Protocol method: returns the canonical 8-key bar
        shape for `ticker`, sorted by bar_start. Not limited to the
        watchlist -- any ticker present in the cached day's file can be
        fetched.
        """

        bars = self._load_day(trading_day)

        ticker_bars = [
            {key: bar[key] for key in _CANONICAL_KEYS}
            for bar in bars
            if bar["ticker"] == ticker
        ]
        ticker_bars.sort(key=lambda bar: bar["bar_start"])

        return ticker_bars

    def ingest_trading_day(
        self, trading_day: date, tickers: frozenset[str] | None = None, source: str = "MASSIVE"
    ) -> dict:
        """Production ingestion path: downloads/parses the whole day, then
        persists every enriched row (or only `tickers`, if given -- see the
        watchlist convention in market_data_watchlist.py) via
        persist_market_bars(). Raw flat-file archive on disk always covers
        the whole market regardless of `tickers`.
        """

        bars = self._load_day(trading_day)

        if tickers is not None:
            bars = [bar for bar in bars if bar["ticker"] in tickers]

        return persist_market_bars(bars, source)

    def _load_day(self, trading_day: date) -> list[dict]:
        if trading_day not in self._day_cache:
            if not is_trading_day(trading_day):
                raise ValueError(f"{trading_day} is not a Nasdaq trading day")

            result = download_flat_file(self._raw_directory, trading_day, self._s3_client)
            self._day_cache[trading_day] = self._parse_flat_file(
                result.local_path, trading_day
            )

        return self._day_cache[trading_day]

    def _parse_flat_file(self, path: Path, trading_day: date) -> list[dict]:
        bounds = get_session_bounds(trading_day)
        run_id = uuid.uuid4().hex
        bars = []

        with gzip.open(path, mode="rt", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)

            for row in reader:
                bar_start = to_nasdaq_local(_window_start_to_utc(int(row["window_start"])))

                if bar_start.date() != trading_day:
                    continue  # defensive: guards against S3-key/date mismatch

                try:
                    session = classify_session(bar_start, bounds)
                except ValueError:
                    continue  # outside 4am-8pm ET; skip, don't fail the day

                bars.append(
                    {
                        "ticker": row["ticker"],
                        "market": None,
                        "bar_start": bar_start,
                        "open": float(row["open"]),
                        "high": float(row["high"]),
                        "low": float(row["low"]),
                        "close": float(row["close"]),
                        "volume": int(row["volume"]),
                        "market_scope": MARKET_SCOPE,
                        "session": session,
                        "transaction_count": int(row["transactions"]),
                        "source_provider": SOURCE_PROVIDER,
                        "source_dataset": MASSIVE_DATASET,
                        "dataset_version": DATASET_VERSION,
                        "ingestion_run_id": run_id,
                        "security_id": None,
                    }
                )

        bars.sort(key=lambda bar: bar["bar_start"])

        return bars
