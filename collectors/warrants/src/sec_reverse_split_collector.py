"""Orchestrateur de découverte des reverse stock splits (SEC-11).

Relie la résolution ticker -> CIK (SEC-05/14) à la découverte/extraction
de splits (sec_reverse_split_extraction) et à la persistance RAW
(warrants_postgresql).
"""

from __future__ import annotations

from datetime import datetime, timezone

from collectors.warrants.src.sec_cik_resolution import resolve_cik
from collectors.warrants.src.sec_reverse_split_extraction import (
    discover_and_extract_reverse_splits_for_cik,
)
from collectors.warrants.src.warrants_postgresql import (
    persist_sec_reverse_split_events,
)


def collect_ticker_reverse_splits(
    ticker,
    ticker_cik_map,
    *,
    user_agent,
    timeout_seconds=30,
):
    """
    Découvre et persiste les événements de reverse split pour un
    ticker. Retourne un statut explicite si le ticker n'a pas de CIK
    connu ou si aucun split n'a été trouvé.
    """

    cik = resolve_cik(ticker, ticker_cik_map)

    if cik is None:
        return {
            "ticker": ticker,
            "cik": None,
            "status": "cik_not_found",
        }

    retrieved_at = datetime.now(timezone.utc)

    events = discover_and_extract_reverse_splits_for_cik(
        cik,
        user_agent=user_agent,
        timeout_seconds=timeout_seconds,
    )

    if not events:
        return {
            "ticker": ticker,
            "cik": cik,
            "status": "no_split_found",
        }

    counts = persist_sec_reverse_split_events(
        cik,
        events,
        retrieved_at,
    )

    return {
        "ticker": ticker,
        "cik": cik,
        "status": "ok",
        "inserted": counts["inserted"],
        "skipped": counts["skipped"],
    }
