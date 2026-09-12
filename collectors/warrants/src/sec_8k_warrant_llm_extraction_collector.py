"""Orchestrateur d'extraction LLM des modalités de warrants (SEC-15).

Relie la résolution ticker -> CIK (SEC-05) à l'extraction LLM
(sec_llm_warrant_extraction) et à la persistance RAW
(warrants_postgresql) — variante de
sec_8k_warrant_text_extraction_collector.py (SEC-10), même table de
destination.
"""

from __future__ import annotations

from datetime import datetime, timezone

from collectors.warrants.src.sec_cik_resolution import resolve_cik
from collectors.warrants.src.sec_llm_warrant_extraction import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    discover_and_extract_warrant_terms_for_cik_llm,
)
from collectors.warrants.src.warrants_postgresql import (
    persist_sec_8k_warrant_text_extractions,
)


def collect_ticker_8k_warrant_text_extraction_llm(
    ticker,
    ticker_cik_map,
    *,
    user_agent,
    api_key,
    model=DEFAULT_MODEL,
    max_tokens=DEFAULT_MAX_TOKENS,
    timeout_seconds=30,
    filings=None,
    fetch_cache=None,
):
    """
    Extrait (via LLM) et persiste les modalités de warrants trouvées
    dans le texte des 8-K pour un ticker. Retourne un statut explicite
    si le ticker n'a pas de CIK connu ou si aucune observation n'a été
    extraite.

    `filings`/`fetch_cache` (SEC-17) : voir
    `sec_8k_warrant_discovery.discover_warrant_exhibits_for_cik` — le
    partage de `fetch_cache` avec SEC-10 est particulièrement utile ici
    (même document principal nécessaire aux deux pipelines).
    """

    cik = resolve_cik(ticker, ticker_cik_map)

    if cik is None:
        return {
            "ticker": ticker,
            "cik": None,
            "status": "cik_not_found",
        }

    retrieved_at = datetime.now(timezone.utc)

    observations = discover_and_extract_warrant_terms_for_cik_llm(
        cik,
        user_agent=user_agent,
        api_key=api_key,
        model=model,
        max_tokens=max_tokens,
        timeout_seconds=timeout_seconds,
        filings=filings,
        fetch_cache=fetch_cache,
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
