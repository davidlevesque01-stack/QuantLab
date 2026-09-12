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

SEC-17 : l'historique 8-K complet (SEC-12) et un cache de requêtes
(SharedFetchCache) sont récupérés UNE SEULE FOIS par ticker et partagés
entre les 4 pipelines qui en dépendent (exhibits, extraction texte
regex/LLM, reverse splits) — avant ça, chacun refaisait sa propre
pagination complète, et les 3 premiers (mêmes filings candidats
1.01/3.02) refaisaient chacun la même requête d'index/document. Chaque
pipeline traite en plus ses filings candidats en parallèle (threads),
ce sont des requêtes réseau indépendantes.

Usage :
    python -m collectors.warrants.src.run_sec_collection --tickers TNON,ABCD
    python -m collectors.warrants.src.run_sec_collection --tickers TNON \
        --user-agent "quantlab-fma contact@example.com"

    # SEC-15 (extraction LLM, en plus du regex, jamais à la place) :
    python -m collectors.warrants.src.run_sec_collection --tickers TNON \
        --use-llm-extraction --anthropic-api-key sk-ant-...
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone

from collectors.warrants.src.sec_8k_warrant_discovery import fetch_all_8k_filings
from collectors.warrants.src.sec_8k_warrant_exhibit_collector import (
    collect_ticker_8k_warrant_exhibits,
)
from collectors.warrants.src.sec_8k_warrant_llm_extraction_collector import (
    collect_ticker_8k_warrant_text_extraction_llm,
)
from collectors.warrants.src.sec_8k_warrant_text_extraction_collector import (
    collect_ticker_8k_warrant_text_extraction,
)
from collectors.warrants.src.sec_cik_resolution import (
    fetch_ticker_cik_map,
    resolve_cik,
)
from collectors.warrants.src.sec_fetch_cache import SharedFetchCache
from collectors.warrants.src.sec_llm_warrant_extraction import DEFAULT_MODEL
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

ANTHROPIC_API_KEY_ENV = "QUANTLAB_ANTHROPIC_API_KEY"


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
    use_llm_extraction=False,
    anthropic_api_key=None,
    llm_model=DEFAULT_MODEL,
):
    """
    Exécute la collecte warrants + shares outstanding pour chaque ticker.

    Retourne une liste de résultats (un par ticker), chacun combinant les
    résumés des deux collectes — ne lève pas si un ticker échoue à être
    résolu ou n'a pas de faits taggués : le statut le reflète.

    `use_llm_extraction` (SEC-15) est un pas EN PLUS de l'extraction
    regex existante (SEC-10), jamais un remplacement — chaque appel API
    a un coût réel, donc explicitement opt-in (jamais déclenché par
    défaut) plutôt qu'activé automatiquement.

    SEC-17 : les 4 pipelines de découverte basés sur les 8-K (exhibits,
    extraction texte regex/LLM, reverse splits) refaisaient chacun leur
    propre pagination complète de l'historique, et les 3 premiers
    (mêmes filings candidats 1.01/3.02) refaisaient chacun les mêmes
    requêtes d'index/document. L'historique est maintenant récupéré une
    seule fois par ticker et partagé (`filings`), de même qu'un cache de
    requêtes partagé entre pipelines (`fetch_cache`, voir
    `SharedFetchCache`).
    """

    results = []

    for ticker in tickers:

        cik = resolve_cik(ticker, ticker_cik_map)
        filings = (
            fetch_all_8k_filings(cik, user_agent=user_agent, timeout_seconds=timeout_seconds)
            if cik is not None
            else None
        )
        fetch_cache = SharedFetchCache() if cik is not None else None

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
            filings=filings,
            fetch_cache=fetch_cache,
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
            filings=filings,
            fetch_cache=fetch_cache,
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
            filings=filings,
            fetch_cache=fetch_cache,
        )
        log_progress(f"{ticker}: reverse_splits -> {reverse_split_result}")

        llm_text_extraction_result = None

        if use_llm_extraction:
            log_progress(
                f"{ticker}: 8-K warrant text extraction via LLM (SEC-15, "
                f"model={llm_model}, full 8-K history — real API cost per "
                "call, can take a while)..."
            )
            llm_text_extraction_result = collect_ticker_8k_warrant_text_extraction_llm(
                ticker,
                ticker_cik_map,
                user_agent=user_agent,
                api_key=anthropic_api_key,
                model=llm_model,
                timeout_seconds=timeout_seconds,
                filings=filings,
                fetch_cache=fetch_cache,
            )
            log_progress(
                f"{ticker}: warrant_text_extraction_llm -> {llm_text_extraction_result}"
            )

        results.append(
            {
                "ticker": ticker,
                "warrants": warrant_result,
                "shares_outstanding": shares_result,
                "warrant_exhibits": exhibits_result,
                "warrant_text_extraction": text_extraction_result,
                "reverse_splits": reverse_split_result,
                "warrant_text_extraction_llm": llm_text_extraction_result,
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

    parser.add_argument(
        "--use-llm-extraction",
        action="store_true",
        help=(
            "Active en plus l'extraction LLM des modalités de warrants "
            "(SEC-15) — opt-in explicite, chaque appel a un coût API réel. "
            "Nécessite --anthropic-api-key ou "
            f"{ANTHROPIC_API_KEY_ENV}."
        ),
    )

    parser.add_argument(
        "--anthropic-api-key",
        default=None,
        help=(
            "Clé API Anthropic pour --use-llm-extraction. À défaut, lue "
            f"depuis {ANTHROPIC_API_KEY_ENV}."
        ),
    )

    parser.add_argument(
        "--llm-model",
        default=DEFAULT_MODEL,
        help=f"Modèle Claude pour --use-llm-extraction (défaut : {DEFAULT_MODEL}).",
    )

    return parser


def main():
    args = build_arg_parser().parse_args()

    user_agent = resolve_user_agent(
        args.user_agent,
        os.environ.get(USER_AGENT_ENV),
    )

    anthropic_api_key = args.anthropic_api_key or os.environ.get(ANTHROPIC_API_KEY_ENV)

    if args.use_llm_extraction and not anthropic_api_key:
        raise ValueError(
            "--use-llm-extraction requires an Anthropic API key: pass "
            f"--anthropic-api-key or set {ANTHROPIC_API_KEY_ENV}."
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
        use_llm_extraction=args.use_llm_extraction,
        anthropic_api_key=anthropic_api_key,
        llm_model=args.llm_model,
    )

    for result in results:
        print(f"--- {result['ticker']} ---")
        print(f"  warrants:           {result['warrants']}")
        print(f"  shares_outstanding: {result['shares_outstanding']}")
        print(f"  warrant_exhibits:   {result['warrant_exhibits']}")
        print(f"  warrant_text:       {result['warrant_text_extraction']}")
        print(f"  reverse_splits:     {result['reverse_splits']}")
        if result["warrant_text_extraction_llm"] is not None:
            print(f"  warrant_text_llm:   {result['warrant_text_extraction_llm']}")


if __name__ == "__main__":
    main()
