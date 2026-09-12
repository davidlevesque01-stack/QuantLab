"""Canonical market data adapter interface (BT-01).

Any intraday data provider (Databento, Massive, or the stub/CSV adapter used
for the vertical slice) must satisfy this interface. The Aggregation Engine,
Feature Engine, models and viewer never depend on which adapter produced a
bar -- only on the canonical shape returned here. See
docs/backtesting/BACKTESTING_COMPONENT.md, "Provider independence".
"""

from __future__ import annotations

from datetime import date
from typing import Protocol


class QuantLabAdapter(Protocol):
    def fetch_bars(self, ticker: str, trading_day: date) -> list[dict]:
        """
        Return 1-minute OHLCV bars for `ticker` on `trading_day`, ordered by
        `bar_start`, each as:

            {
                "ticker": str,
                "market": str,
                "bar_start": datetime,  # naive, Nasdaq-local wall-clock time
                "open": float,
                "high": float,
                "low": float,
                "close": float,
                "volume": int,
            }

        Only 1-minute bars are ever returned -- every larger timeframe is
        computed on demand by the Aggregation Engine (BT-02), never sourced
        from a provider's own aggregation.
        """
        ...
