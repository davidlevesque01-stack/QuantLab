"""Orchestrateur d'extraction texte des modalités de warrants (SEC-10).

Relie la résolution ticker -> CIK (SEC-05) à l'extraction texte
(sec_8k_warrant_text_extraction) et à la persistance RAW
(warrants_postgresql).
"""

from __future__ import annotations

from datetime import datetime, timezone

from collectors.warrants.src.sec_8k_warrant_text_extraction import (
    discover_and_extract_warrant_terms_for_cik,
)
from collectors.warrants.src.sec_cik_resolution import resolve_cik
from collectors.warrants.src.warrants_postgresql import (
    persist_sec_8k_warrant_text_extractions,
)


def collect_ticker_8k_warrant_text_extraction(
    ticker,
    ticker_cik_map,
    *,
    user_agent,
    timeout_seconds=30,
):
    """
    Extrait et persiste les modalités de warrants trouvées dans le texte
    des 8-K pour un ticker. Retourne un statut explicite si le ticker
    n'a pas de CIK connu ou si aucune observation n'a été extraite.
    """

    cik = resolve_cik(ticker, ticker_cik_map)

    if cik is None:
        return {
            "ticker": ticker,
            "cik": None,
            "status": "cik_not_found",
        }

    retrieved_at = datetime.now(timezone.utc)

    observations = discover_and_extract_warrant_terms_for_cik(
        cik,
        user_agent=user_agent,
        timeout_seconds=timeout_seconds,
    )

    if not observations:
        return {
            "ticker": ticker,
            "cik": cik,
            "status": "no_terms_extracted",
        }

    counts = persist_sec_8k_warrant_text_extractions(
        cik,
        observations,
        retrieved_at,
    )

    return {
        "ticker": ticker,
        "cik": cik,
        "status": "ok",
        "inserted": counts["inserted"],
        "skipped": counts["skipped"],
    }
