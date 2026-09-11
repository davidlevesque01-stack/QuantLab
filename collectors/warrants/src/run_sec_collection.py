"""CLI de backfill réel SEC-natif (SEC-07, étendu par SEC-09).

Exécute pour de vrai (pas en rollback) collect_ticker_warrants,
collect_ticker_shares_outstanding et collect_ticker_8k_warrant_exhibits
sur une liste de tickers fournie par l'appelant, pour peupler
raw.sec_warrant_xbrl_fact, raw.sec_shares_outstanding_fact et
raw.sec_8k_warrant_exhibit avec de vraies données avant validation
visuelle (SEC-08).

Usage :
    python -m collectors.warrants.src.run_sec_collection --tickers TNON,ABCD
    python -m collectors.warrants.src.run_sec_collection --tickers TNON \
        --user-agent "quantlab-fma contact@example.com"
"""

from __future__ import annotations

import argparse
import os

from collectors.warrants.src.sec_8k_warrant_exhibit_collector import (
    collect_ticker_8k_warrant_exhibits,
)
from collectors.warrants.src.sec_8k_warrant_text_extraction_collector import (
    collect_ticker_8k_warrant_text_extraction,
)
from collectors.warrants.src.sec_cik_resolution import fetch_ticker_cik_map
from collectors.warrants.src.sec_shares_outstanding_collector import (
    collect_ticker_shares_outstanding,
)
from collectors.warrants.src.sec_warrant_collector import collect_ticker_warrants


USER_AGENT_ENV = "QUANTLAB_SEC_USER_AGENT"


def resolve_user_agent(cli_value, env_value):
    """
    Priorité : argument --user-agent, puis variable d'environnement
    QUANTLAB_SEC_USER_AGENT. Lève une erreur explicite si aucun des deux
    n'est fourni — SEC exige un User-Agent identifiant l'appelant pour
    tout accès automatisé.
    """

    if cli_value:
        return cli_value

    if env_value:
        return env_value

    raise ValueError(
        "No SEC User-Agent provided: pass --user-agent or set "
        f"{USER_AGENT_ENV}."
    )


def run_collection(
    tickers,
    ticker_cik_map,
    *,
    user_agent,
    timeout_seconds=30,
):
    """
    Exécute la collecte warrants + shares outstanding pour chaque ticker.

    Retourne une liste de résultats (un par ticker), chacun combinant les
    résumés des deux collectes — ne lève pas si un ticker échoue à être
    résolu ou n'a pas de faits taggués : le statut le reflète.
    """

    results = []

    for ticker in tickers:

        warrant_result = collect_ticker_warrants(
            ticker,
            ticker_cik_map,
            user_agent=user_agent,
            timeout_seconds=timeout_seconds,
        )

        shares_result = collect_ticker_shares_outstanding(
            ticker,
            ticker_cik_map,
            user_agent=user_agent,
            timeout_seconds=timeout_seconds,
        )

        exhibits_result = collect_ticker_8k_warrant_exhibits(
            ticker,
            ticker_cik_map,
            user_agent=user_agent,
            timeout_seconds=timeout_seconds,
        )

        text_extraction_result = collect_ticker_8k_warrant_text_extraction(
            ticker,
            ticker_cik_map,
            user_agent=user_agent,
            timeout_seconds=timeout_seconds,
        )

        results.append(
            {
                "ticker": ticker,
                "warrants": warrant_result,
                "shares_outstanding": shares_result,
                "warrant_exhibits": exhibits_result,
                "warrant_text_extraction": text_extraction_result,
            }
        )

    return results


def parse_tickers(raw_value):
    """
    Découpe une liste de tickers séparés par des virgules, en ignorant les
    espaces et les entrées vides.
    """

    return [
        ticker.strip().upper()
        for ticker in raw_value.split(",")
        if ticker.strip()
    ]


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Backfill réel SEC-natif (warrants + shares outstanding) "
            "pour une liste de tickers."
        )
    )

    parser.add_argument(
        "--tickers",
        required=True,
        help="Tickers séparés par des virgules, ex. TNON,ABCD",
    )

    parser.add_argument(
        "--user-agent",
        default=None,
        help=(
            "User-Agent SEC (nom + contact). À défaut, lu depuis "
            f"{USER_AGENT_ENV}."
        ),
    )

    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=30,
    )

    return parser


def main():
    args = build_arg_parser().parse_args()

    user_agent = resolve_user_agent(
        args.user_agent,
        os.environ.get(USER_AGENT_ENV),
    )

    tickers = parse_tickers(args.tickers)

    ticker_cik_map = fetch_ticker_cik_map(
        user_agent=user_agent,
        timeout_seconds=args.timeout_seconds,
    )

    results = run_collection(
        tickers,
        ticker_cik_map,
        user_agent=user_agent,
        timeout_seconds=args.timeout_seconds,
    )

    for result in results:
        print(f"--- {result['ticker']} ---")
        print(f"  warrants:           {result['warrants']}")
        print(f"  shares_outstanding: {result['shares_outstanding']}")
        print(f"  warrant_exhibits:   {result['warrant_exhibits']}")
        print(f"  warrant_text:       {result['warrant_text_extraction']}")


if __name__ == "__main__":
    main()
