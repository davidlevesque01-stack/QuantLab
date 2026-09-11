"""Résolution ticker -> CIK via SEC company_tickers.json (SEC-05),
avec repli par recherche de nom pour les tickers absents (SEC-14).
"""

from __future__ import annotations

from collectors.warrants.src.sec_company_name_search import resolve_cik_by_name
from collectors.warrants.src.sec_edgar_client import fetch_json


COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"


def fetch_ticker_cik_map(
    *,
    user_agent,
    timeout_seconds=30,
):
    """
    Télécharge company_tickers.json et retourne {ticker: cik}.
    """

    payload = fetch_json(
        COMPANY_TICKERS_URL,
        user_agent=user_agent,
        timeout_seconds=timeout_seconds,
    )

    return build_ticker_cik_map(payload)


def build_ticker_cik_map(payload):
    """
    Construit {ticker: cik} à partir du payload brut company_tickers.json
    (dict indexé numériquement, chaque valeur ayant cik_str/ticker/title).

    Le CIK est retourné sur 10 chiffres, zero-paddé — le format attendu par
    les endpoints EDGAR (full-text search, submissions, company-facts).
    """

    ticker_cik_map = {}

    for record in payload.values():

        ticker = record["ticker"].upper()
        cik = str(record["cik_str"]).zfill(10)

        ticker_cik_map[ticker] = cik

    return ticker_cik_map


def resolve_cik(
    ticker,
    ticker_cik_map,
):
    """
    Résout un ticker vers son CIK EDGAR, ou None si absent de la carte.
    """

    return ticker_cik_map.get(ticker.upper())


def resolve_cik_with_fallback(
    ticker,
    ticker_cik_map,
    issuer_name=None,
    *,
    user_agent,
    timeout_seconds=30,
):
    """
    Résout un ticker vers son CIK, avec repli par recherche de nom si
    absent de company_tickers.json (SEC-14) — typiquement un émetteur
    radié/acquis depuis (company_tickers.json ne couvre que les
    émetteurs actuellement enregistrés).

    `issuer_name` doit venir d'une source déjà connue et fiable pour ce
    ticker (ex. core.nasdaq_halt_episode.issue_name), jamais deviné.

    Retourne un dict {ticker, cik, method, issuer_name_used, matched_name}
    où `method` est "ticker_map", "name_search", ou "not_found". La
    recherche par nom est volontairement stricte (voir
    sec_company_name_search.find_best_match) — une correspondance
    ambiguë retourne "not_found" plutôt qu'un mauvais rapprochement
    silencieux.
    """

    cik = resolve_cik(ticker, ticker_cik_map)

    if cik is not None:
        return {
            "ticker": ticker,
            "cik": cik,
            "method": "ticker_map",
            "issuer_name_used": issuer_name,
            "matched_name": None,
        }

    if not issuer_name:
        return {
            "ticker": ticker,
            "cik": None,
            "method": "not_found",
            "issuer_name_used": issuer_name,
            "matched_name": None,
        }

    fallback_cik = resolve_cik_by_name(
        issuer_name,
        user_agent=user_agent,
        timeout_seconds=timeout_seconds,
    )

    if fallback_cik is not None:
        return {
            "ticker": ticker,
            "cik": fallback_cik,
            "method": "name_search",
            "issuer_name_used": issuer_name,
            "matched_name": issuer_name,
        }

    return {
        "ticker": ticker,
        "cik": None,
        "method": "not_found",
        "issuer_name_used": issuer_name,
        "matched_name": None,
    }
