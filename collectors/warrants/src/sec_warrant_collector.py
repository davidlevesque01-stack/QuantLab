"""Orchestrateur SEC-natif de collecte des warrants (SEC-06).

Relie la résolution ticker -> CIK (SEC-05) à l'extraction XBRL
"ClassOfWarrantOrRight" (sec_warrant_xbrl) et à la persistance RAW
(warrants_postgresql). Piste principale, non bloquée par l'accès
DilutionTracker.
"""

from __future__ import annotations

from datetime import datetime, timezone

from collectors.warrants.src.sec_cik_resolution import resolve_cik
from collectors.warrants.src.sec_warrant_xbrl import (
    extract_warrant_facts,
    fetch_company_facts,
)
from collectors.warrants.src.warrants_postgresql import (
    persist_sec_warrant_xbrl_facts,
)


def collect_ticker_warrants(
    ticker,
    ticker_cik_map,
    *,
    user_agent,
    timeout_seconds=30,
):
    """
    Collecte et persiste les faits XBRL de warrants pour un ticker.

    Retourne un résumé incluant le CIK résolu et les compteurs de
    persistance, ou un statut explicite si le ticker n'a pas de CIK
    connu (univers Nasdaq non couvert par company_tickers.json) ou si
    l'émetteur ne balise aucun warrant en XBRL dimensionnel (repli
    full-text/exhibits hors scope de ce module).
    """

    cik = resolve_cik(ticker, ticker_cik_map)

    if cik is None:
        return {
            "ticker": ticker,
            "cik": None,
            "status": "cik_not_found",
        }

    retrieved_at = datetime.now(timezone.utc)

    company_facts = fetch_company_facts(
        cik,
        user_agent=user_agent,
        timeout_seconds=timeout_seconds,
    )

    observations = extract_warrant_facts(company_facts)

    if not observations:
        return {
            "ticker": ticker,
            "cik": cik,
            "status": "no_warrant_facts_tagged",
        }

    counts = persist_sec_warrant_xbrl_facts(
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
