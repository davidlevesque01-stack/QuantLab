"""CLI de collecte réelle de l'annuaire des titres Nasdaq (SEC-03).

Télécharge nasdaqlisted.txt + otherlisted.txt et persiste un snapshot
horodaté complet dans raw.nasdaq_symbol_directory — l'univers de
référence des sociétés/titres à suivre (~13 000 lignes au total).

Usage :
    python -m collectors.warrants.src.run_nasdaq_symbol_directory_collection \
        --user-agent "quantlab-fma contact@example.com"
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone

from collectors.warrants.src.nasdaq_symbol_directory import (
    fetch_and_parse_symbol_directory,
)
from collectors.warrants.src.warrants_postgresql import (
    persist_nasdaq_symbol_directory,
)


USER_AGENT_ENV = "QUANTLAB_SEC_USER_AGENT"


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="Backfill réel de l'annuaire des titres Nasdaq Trader."
    )

    parser.add_argument(
        "--user-agent",
        default=None,
        help=f"User-Agent (nom + contact). À défaut, lu depuis {USER_AGENT_ENV}.",
    )

    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=30,
    )

    return parser


def main():
    args = build_arg_parser().parse_args()

    user_agent = args.user_agent or os.environ.get(USER_AGENT_ENV)

    if not user_agent:
        raise ValueError(
            "No User-Agent provided: pass --user-agent or set "
            f"{USER_AGENT_ENV}."
        )

    retrieved_at = datetime.now(timezone.utc)

    records = fetch_and_parse_symbol_directory(
        user_agent=user_agent,
        timeout_seconds=args.timeout_seconds,
    )

    counts = persist_nasdaq_symbol_directory(records, retrieved_at)

    print(f"Records downloaded: {len(records)}")
    print(f"Inserted: {counts['inserted']}, skipped (duplicates): {counts['skipped']}")


if __name__ == "__main__":
    main()
