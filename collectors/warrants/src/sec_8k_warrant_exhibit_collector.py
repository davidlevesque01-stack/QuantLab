"""Orchestrateur de découverte des exhibits de warrants via 8-K (SEC-09).

Relie la résolution ticker -> CIK (SEC-05) à la découverte d'exhibits
(sec_8k_warrant_discovery) et à la persistance RAW (warrants_postgresql).
Repli explicite pour les warrants invisibles au pipeline XBRL (SEC-06).
"""

from __future__ import annotations

from datetime import datetime, timezone

from collectors.warrants.src.sec_8k_warrant_discovery import (
    discover_warrant_exhibits_for_cik,
)
from collectors.warrants.src.sec_cik_resolution import resolve_cik
from collectors.warrants.src.warrants_postgresql import (
    persist_sec_8k_warrant_exhibits,
)


def collect_ticker_8k_warrant_exhibits(
    ticker,
    ticker_cik_map,
    *,
    user_agent,
    timeout_seconds=30,
):
    """
    Découvre et persiste les exhibits de 8-K probablement liés à un
    warrant pour un ticker. Retourne un statut explicite si le ticker
    n'a pas de CIK connu ou si aucun exhibit candidat n'a été trouvé.
    """

    cik = resolve_cik(ticker, ticker_cik_map)

    if cik is None:
        return {
            "ticker": ticker,
            "cik": None,
            "status": "cik_not_found",
        }

    retrieved_at = datetime.now(timezone.utc)

    exhibits = discover_warrant_exhibits_for_cik(
        cik,
        user_agent=user_agent,
        timeout_seconds=timeout_seconds,
    )

    if not exhibits:
        return {
            "ticker": ticker,
            "cik": cik,
            "status": "no_warrant_exhibits_found",
        }

    counts = persist_sec_8k_warrant_exhibits(
        cik,
        exhibits,
        retrieved_at,
    )

    return {
        "ticker": ticker,
        "cik": cik,
        "status": "ok",
        "inserted": counts["inserted"],
        "skipped": counts["skipped"],
    }
