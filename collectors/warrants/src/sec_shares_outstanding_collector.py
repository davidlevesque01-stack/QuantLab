"""Orchestrateur de collecte des shares outstanding (SEC-01 / SEC-02).

Relie la résolution ticker -> CIK (SEC-05) à l'extraction XBRL
dei:EntityCommonStockSharesOutstanding (sec_shares_outstanding) et à la
persistance RAW (warrants_postgresql). Source structurée et gratuite,
indépendante de DilutionTracker.
"""

from __future__ import annotations

from datetime import datetime, timezone

from collectors.warrants.src.sec_cik_resolution import resolve_cik
from collectors.warrants.src.sec_shares_outstanding import (
    extract_shares_outstanding_facts,
)
from collectors.warrants.src.sec_xbrl_facts import fetch_company_facts
from collectors.warrants.src.warrants_postgresql import (
    persist_sec_shares_outstanding_facts,
)


def collect_ticker_shares_outstanding(
    ticker,
    ticker_cik_map,
    *,
    user_agent,
    timeout_seconds=30,
):
    """
    Collecte et persiste les faits XBRL de shares outstanding pour un
    ticker. Retourne un statut explicite si le ticker n'a pas de CIK
    connu, ou si l'émetteur n'a jamais déposé ce fait (rare, mais
    possible pour certains types d'émetteurs/formulaires).
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

    observations = extract_shares_outstanding_facts(company_facts)

    if not observations:
        return {
            "ticker": ticker,
            "cik": cik,
            "status": "no_shares_outstanding_facts",
        }

    counts = persist_sec_shares_outstanding_facts(
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
