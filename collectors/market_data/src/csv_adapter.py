"""Stub/CSV market data adapter (BT-01).

Reads 1-minute OHLCV bars from a local CSV fixture instead of a real
intraday data provider. Used to develop and validate the Replay Engine
(Simulated Clock/MarketContext, Aggregation Engine, Feature Engine, viewer)
end-to-end before a real provider (Databento/Massive, BT-11) is decided and
wired in behind the same QuantLabAdapter interface -- see
docs/backtesting/BACKTESTING_COMPONENT.md.
"""

from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path


class CSVAdapter:
    """Implements QuantLabAdapter against fixture CSV files.

    Each fixture is named `<ticker>_<trading_day>.csv` (ISO date) under
    `fixtures_directory`, with columns:
    ticker,market,bar_start,open,high,low,close,volume
    """

    def __init__(self, fixtures_directory: Path):
        self._fixtures_directory = Path(fixtures_directory)

    def fetch_bars(self, ticker: str, trading_day: date) -> list[dict]:
        path = self._fixtures_directory / f"{ticker}_{trading_day.isoformat()}.csv"

        if not path.exists():
            raise FileNotFoundError(
                f"No market data fixture for {ticker} on {trading_day}: {path}"
            )

        bars = []

        with open(path, newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)

            for row in reader:
                bars.append(
                    {
                        "ticker": row["ticker"],
                        "market": row["market"],
                        "bar_start": datetime.fromisoformat(row["bar_start"]),
                        "open": float(row["open"]),
                        "high": float(row["high"]),
                        "low": float(row["low"]),
                        "close": float(row["close"]),
                        "volume": int(row["volume"]),
                    }
                )

        bars.sort(key=lambda bar: bar["bar_start"])

        return bars
