"""Résolution ticker -> CIK via SEC company_tickers.json (SEC-05)."""

from __future__ import annotations

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
