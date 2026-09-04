from __future__ import annotations

from datetime import date, datetime
from typing import Any

from shared.database.connection import get_connection


class NasdaqHaltCoreSource:
    """Read Nasdaq HALT episodes from the CORE PostgreSQL dataset."""

    def fetch_core_episodes(
        self,
        *,
        ticker: str,
        start_date: date | None,
        end_date: date,
        reason_codes: tuple[str, ...],
    ) -> list[dict[str, Any]]:
        """Fetch CORE HALT episodes for an analysis context.

        The end date is inclusive. This is intentional because the
        observation day is part of the historical window.
        """
        if not reason_codes:
            return []

        query = """
            SELECT
                symbol,
                reason_code,
                halt_start,
                halt_end,
                halt_start::date AS trading_date,
                duration_minutes,
                halt_close_status
            FROM core.nasdaq_halt_episode
            WHERE symbol = %s
              AND halt_start < (%s::date + INTERVAL '1 day')
              AND reason_code = ANY(%s)
        """

        params: list[Any] = [
            ticker,
            end_date,
            list(reason_codes),
        ]

        if start_date is not None:
            query += """
              AND halt_start >= %s::date
            """
            params.append(start_date)

        query += """
            ORDER BY halt_start
        """

        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                rows = cursor.fetchall()

        return [
            {
                "symbol": row[0],
                "reason_code": row[1],
                "halt_start": row[2],
                "halt_end": row[3],
                "trading_date": row[4],
                "duration_minutes": row[5],
                "halt_close_status": row[6],
            }
            for row in rows
        ]
