from __future__ import annotations

from datetime import date, datetime
from typing import Any

from shared.database.connection import get_connection


class MarketBarSource:
    """Read 1-minute market bars from the CORE PostgreSQL dataset.

    This is the Historical Data API (BT-17): the Replay Engine's only path to
    market bars. It never calls a Source Adapter (CSVAdapter/MassiveAdapter)
    directly -- those exist purely to get data into raw/core.market_bar_1m,
    not to serve replay-time reads. See
    docs/backtesting/BACKTESTING_COMPONENT.md, "Source Adapter and Historical
    Data API are not the same component".
    """

    def fetch_bars(
        self,
        *,
        ticker: str,
        trading_day: date,
        as_of: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch 1-minute bars for `ticker` on `trading_day`, ordered by
        `bar_start`.

        If `as_of` is given, only bars with `bar_start <= as_of` are
        returned -- the point-in-time guard MarketContext (BT-03) relies on.
        Returns the same canonical shape as QuantLabAdapter.fetch_bars()
        (BT-01), so downstream code never needs to know whether a bar came
        from a live adapter or from CORE.
        """

        query = """
            SELECT
                ticker,
                market,
                bar_start,
                open,
                high,
                low,
                close,
                volume
            FROM core.market_bar_1m
            WHERE ticker = %s
              AND bar_start >= %s::date
              AND bar_start < (%s::date + INTERVAL '1 day')
        """

        params: list[Any] = [ticker, trading_day, trading_day]

        if as_of is not None:
            query += " AND bar_start <= %s"
            params.append(as_of)

        query += " ORDER BY bar_start"

        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                rows = cursor.fetchall()

        return [
            {
                "ticker": row[0],
                "market": row[1],
                "bar_start": row[2],
                # open/high/low/close are NUMERIC in PostgreSQL -- psycopg
                # returns Decimal. Cast to float so this matches
                # QuantLabAdapter.fetch_bars()'s canonical shape (BT-01)
                # exactly; downstream code must not care which path a bar
                # came from.
                "open": float(row[3]),
                "high": float(row[4]),
                "low": float(row[5]),
                "close": float(row[6]),
                "volume": row[7],
            }
            for row in rows
        ]
