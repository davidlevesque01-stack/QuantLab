"""Résolution CIK à l'échelle d'un lot de tickers, avec repli (SEC-14).

Construit une version « augmentée » de ticker_cik_map (SEC-05) en
résolvant par recherche de nom les tickers absents de
company_tickers.json — typiquement des émetteurs radiés/acquis depuis
leur épisode HALT. Chaque décision de résolution (directe ou par repli)
est persistée pour traçabilité (raw.sec_ticker_cik_resolution).

Les collecteurs existants (SEC-06/01/09/10) n'ont besoin d'aucune
modification : ils continuent d'appeler resolve_cik(ticker, ticker_cik_map)
sans le savoir — l'augmentation se fait en amont, une fois par lot.
"""

from __future__ import annotations

from datetime import datetime, timezone

from shared.database import get_connection

from collectors.warrants.src.sec_cik_resolution import (
    resolve_cik,
    resolve_cik_with_fallback,
)
from collectors.warrants.src.warrants_postgresql import (
    persist_sec_ticker_cik_resolution,
    read_issue_names_for_tickers,
)


def build_augmented_ticker_cik_map(
    tickers,
    ticker_cik_map,
    *,
    user_agent,
    timeout_seconds=30,
):
    """
    Retourne une copie de ticker_cik_map augmentée des résolutions par
    repli pour les tickers de `tickers` absents de la carte directe.

    Persiste chaque décision de résolution (directe et par repli) dans
    raw.sec_ticker_cik_resolution pour audit — voir
    sec_cik_resolution.resolve_cik_with_fallback pour la sémantique de
    `method` (ticker_map / name_search / not_found).
    """

    augmented = dict(ticker_cik_map)

    unresolved = [
        ticker
        for ticker in tickers
        if resolve_cik(ticker, augmented) is None
    ]

    if not unresolved:
        return augmented

    conn = get_connection()

    try:
        issue_names = read_issue_names_for_tickers(conn, unresolved)
    finally:
        conn.close()

    retrieved_at = datetime.now(timezone.utc)

    for ticker in unresolved:

        resolution = resolve_cik_with_fallback(
            ticker,
            augmented,
            issue_names.get(ticker.upper()),
            user_agent=user_agent,
            timeout_seconds=timeout_seconds,
        )

        persist_sec_ticker_cik_resolution(resolution, retrieved_at)

        if resolution["cik"]:
            augmented[ticker.upper()] = resolution["cik"]

    return augmented
