"""Capture RAW de l'annuaire des titres Nasdaq / autres marchés (SEC-03).

Nasdaq Trader publie quotidiennement deux fichiers texte délimités par
« | » listant l'univers complet des titres cotés :

- nasdaqlisted.txt : titres cotés sur Nasdaq
- otherlisted.txt  : titres cotés sur les autres marchés (NYSE, etc.),
  rapportés au tape consolidé

Nasdaq Trader n'apporte que l'identité/le listing — jamais les modalités
de warrants (voir sec_warrant_xbrl.py pour ça).
"""

from __future__ import annotations

from urllib.request import Request, urlopen


NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"

FOOTER_PREFIX = "File Creation Time"


def fetch_symbol_directory(url, *, user_agent, timeout_seconds=30):
    """Téléchargement brut d'un fichier annuaire Nasdaq Trader."""

    request = Request(url, headers={"User-Agent": user_agent})

    with urlopen(request, timeout=timeout_seconds) as response:
        return response.read().decode("utf-8")


def _parse_pipe_delimited(text, source_file, symbol_field):
    """
    Parse un fichier délimité par « | » avec en-tête sur la première
    ligne et une ligne de pied « File Creation Time: ... » à ignorer.
    """

    lines = [line for line in text.splitlines() if line.strip()]

    if not lines:
        return []

    header = lines[0].split("|")
    rows = []

    for line in lines[1:]:

        if line.startswith(FOOTER_PREFIX):
            continue

        fields = line.split("|")

        if len(fields) != len(header):
            continue

        record = dict(zip(header, fields))

        rows.append(
            {
                "symbol": record.get(symbol_field),
                "security_name": record.get("Security Name"),
                "exchange": (
                    record.get("Exchange")
                    or record.get("Market Category")
                ),
                "test_issue": record.get("Test Issue"),
                "round_lot_size": record.get("Round Lot Size"),
                "etf": record.get("ETF"),
                "source_file": source_file,
                "payload": record,
            }
        )

    return rows


def parse_nasdaq_listed(text):
    """
    Parse nasdaqlisted.txt : Symbol|Security Name|Market Category|Test
    Issue|Financial Status|Round Lot Size|ETF|NextShares
    """

    return _parse_pipe_delimited(text, "nasdaqlisted", symbol_field="Symbol")


def parse_other_listed(text):
    """
    Parse otherlisted.txt : ACT Symbol|Security Name|Exchange|CQS
    Symbol|ETF|Round Lot Size|Test Issue|NASDAQ Symbol
    """

    return _parse_pipe_delimited(text, "otherlisted", symbol_field="ACT Symbol")


def fetch_and_parse_symbol_directory(*, user_agent, timeout_seconds=30):
    """
    Télécharge et parse les deux fichiers annuaires, retourne la liste
    combinée des enregistrements (nasdaqlisted + otherlisted).
    """

    nasdaq_text = fetch_symbol_directory(
        NASDAQ_LISTED_URL,
        user_agent=user_agent,
        timeout_seconds=timeout_seconds,
    )
    other_text = fetch_symbol_directory(
        OTHER_LISTED_URL,
        user_agent=user_agent,
        timeout_seconds=timeout_seconds,
    )

    return parse_nasdaq_listed(nasdaq_text) + parse_other_listed(other_text)
