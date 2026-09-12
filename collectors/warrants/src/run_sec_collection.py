"""CLI de backfill réel SEC-natif (SEC-07, étendu par SEC-09/SEC-10/SEC-14).

Exécute pour de vrai (pas en rollback) collect_ticker_warrants,
collect_ticker_shares_outstanding, collect_ticker_8k_warrant_exhibits et
collect_ticker_8k_warrant_text_extraction sur une liste de tickers
fournie par l'appelant, pour peupler raw.sec_warrant_xbrl_fact,
raw.sec_shares_outstanding_fact, raw.sec_8k_warrant_exhibit et
raw.sec_8k_warrant_text_extraction avec de vraies données avant
validation visuelle (SEC-08).

La carte ticker -> CIK est augmentée avant collecte (SEC-14) : un
ticker absent de company_tickers.json (émetteur radié/acquis depuis)
est résolu par repli via recherche de nom, en utilisant
core.nasdaq_halt_episode.issue_name comme source de nom fiable.

Usage :
    python -m collectors.warrants.src.run_sec_collection --tickers TNON,ABCD
    python -m collectors.warrants.src.run_sec_collection --tickers TNON \
        --user-agent "quantlab-fma contact@example.com"
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone

from collectors.warrants.src.sec_8k_warrant_exhibit_collector import (
    collect_ticker_8k_warrant_exhibits,
)
from collectors.warrants.src.sec_8k_warrant_text_extraction_collector import (
    collect_ticker_8k_warrant_text_extraction,
)
from collectors.warrants.src.sec_cik_resolution import fetch_ticker_cik_map
from collectors.warrants.src.sec_reverse_split_collector import (
    collect_ticker_reverse_splits,
)
from collectors.warrants.src.sec_ticker_universe_resolution import (
    build_augmented_ticker_cik_map,
)
from collectors.warrants.src.sec_shares_outstanding_collector import (
    collect_ticker_shares_outstanding,
)
from collectors.warrants.src.sec_warrant_collector import collect_ticker_warrants


USER_AGENT_ENV = "QUANTLAB_SEC_USER_AGENT"


def log_progress(message):
    """
    Affiche un message de progression horodaté sur stdout, avec flush
    immédiat (`print(..., flush=True)`).

    Sans ça, cette CLI reste silencieuse pendant toute la durée d'un
    ticker (potentiellement plusieurs minutes depuis SEC-12, qui pagine
    l'historique COMPLET des 8-K sur 3 pipelines de découverte
    distincts) — aucun moyen de distinguer "en cours" de "bloqué" sans
    au moins un signal de vie régulier.
    """

    timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


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

        log_progress(f"{ticker}: starting (warrant XBRL facts, SEC-06)...")
        warrant_result = collect_ticker_warrants(
            ticker,
            ticker_cik_map,
            user_agent=user_agent,
            timeout_seconds=timeout_seconds,
        )
        log_progress(f"{ticker}: warrants -> {warrant_result}")

        log_progress(f"{ticker}: shares outstanding (SEC-01/02)...")
        shares_result = collect_ticker_shares_outstanding(
            ticker,
            ticker_cik_map,
            user_agent=user_agent,
            timeout_seconds=timeout_seconds,
        )
        log_progress(f"{ticker}: shares_outstanding -> {shares_result}")

        log_progress(
            f"{ticker}: 8-K warrant exhibits (SEC-09/12/13, full 8-K "
            "history — can take a while)..."
        )
        exhibits_result = collect_ticker_8k_warrant_exhibits(
            ticker,
            ticker_cik_map,
            user_agent=user_agent,
            timeout_seconds=timeout_seconds,
        )
        log_progress(f"{ticker}: warrant_exhibits -> {exhibits_result}")

        log_progress(
            f"{ticker}: 8-K warrant text extraction (SEC-10/12, full "
            "8-K history — can take a while)..."
        )
        text_extraction_result = collect_ticker_8k_warrant_text_extraction(
            ticker,
            ticker_cik_map,
            user_agent=user_agent,
            timeout_seconds=timeout_seconds,
        )
        log_progress(f"{ticker}: warrant_text_extraction -> {text_extraction_result}")

        log_progress(
            f"{ticker}: reverse stock split events (SEC-11/12, full "
            "8-K history — can take a while)..."
        )
        reverse_split_result = collect_ticker_reverse_splits(
            ticker,
            ticker_cik_map,
            user_agent=user_agent,
            timeout_seconds=timeout_seconds,
        )
        log_progress(f"{ticker}: reverse_splits -> {reverse_split_result}")

        results.append(
            {
                "ticker": ticker,
                "warrants": warrant_result,
                "shares_outstanding": shares_result,
                "warrant_exhibits": exhibits_result,
                "warrant_text_extraction": text_extraction_result,
                "reverse_splits": reverse_split_result,
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

    ticker_cik_map = build_augmented_ticker_cik_map(
        tickers,
        ticker_cik_map,
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
        print(f"  reverse_splits:     {result['reverse_splits']}")


if __name__ == "__main__":
    main()
