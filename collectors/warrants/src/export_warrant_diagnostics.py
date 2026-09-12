"""Export diagnostique des faits warrants / shares outstanding (SEC-08).

CSV à but diagnostique uniquement (convention QuantLab — jamais un chemin
de production entre un collecteur et PostgreSQL). Ajoute, pour chaque
fait, un lien direct vers l'index du filing EDGAR source (reconstruit à
partir du CIK et du numéro d'accession), pour une comparaison visuelle en
un clic contre le document source.
"""

from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path

from shared.database import get_connection

from collectors.warrants.src.sec_cik_resolution import (
    fetch_ticker_cik_map,
    resolve_cik,
)
from collectors.warrants.src.warrants_postgresql import (
    read_sec_8k_warrant_exhibits,
    read_sec_8k_warrant_text_extractions,
    read_sec_shares_outstanding_facts,
    read_sec_warrant_xbrl_facts,
)


USER_AGENT_ENV = "QUANTLAB_SEC_USER_AGENT"

BASE_DIR = Path(__file__).resolve().parent.parent

DEFAULT_OUTPUT_PATH = BASE_DIR / "data" / "processed" / "warrant_diagnostics.csv"

FIELDNAMES = [
    "ticker",
    "cik",
    "source_table",
    "concept",
    "description",
    "unit",
    "value",
    "period_start",
    "period_end",
    "form",
    "filed_date",
    "accession_number",
    "filing_url",
    "raw_snippet",
    "match_reason",
    "extraction_method",
]

_TEXT_EXTRACTION_UNIT_BY_KIND = {
    "share_quantity": "shares",
    "exercise_price": "USD",
    "expiration_years": "years",
}


def build_edgar_filing_url(cik, accession_number):
    """
    Reconstruit l'URL de l'index d'un filing EDGAR à partir du CIK et du
    numéro d'accession (format SEC standard) :

        https://www.sec.gov/Archives/edgar/data/<cik sans zéros>/
            <accession sans tirets>/<accession>-index.htm

    Retourne None si l'un des deux est absent (aucune source à lier).
    """

    if not accession_number or not cik:
        return None

    cik_no_leading_zeros = str(int(cik))
    accession_no_dashes = accession_number.replace("-", "")

    return (
        "https://www.sec.gov/Archives/edgar/data/"
        f"{cik_no_leading_zeros}/{accession_no_dashes}/"
        f"{accession_number}-index.htm"
    )


def build_diagnostic_rows(ticker, cik, source_table, facts):
    """
    Aplatit une liste de faits (voir warrants_postgresql.read_sec_*) en
    lignes CSV prêtes à écrire, avec leur lien de filing.
    """

    rows = []

    for fact in facts:

        rows.append(
            {
                "ticker": ticker,
                "cik": cik,
                "source_table": source_table,
                "concept": fact["concept"],
                "unit": fact["unit"],
                "value": fact["fact_value"],
                "period_start": fact["period_start"],
                "period_end": fact["period_end"],
                "form": fact["form"],
                "filed_date": fact["filed_date"],
                "accession_number": fact["accession_number"],
                "filing_url": build_edgar_filing_url(
                    cik,
                    fact["accession_number"],
                ),
            }
        )

    return rows


def build_exhibit_diagnostic_rows(ticker, cik, exhibits):
    """
    Aplatit les exhibits de warrants découverts via 8-K (SEC-09) en
    lignes CSV — le lien pointe directement vers le document de
    l'exhibit (pas l'index du filing), puisqu'on le connaît déjà.
    """

    rows = []

    for exhibit in exhibits:

        rows.append(
            {
                "ticker": ticker,
                "cik": cik,
                "source_table": "8k_warrant_exhibit",
                "concept": exhibit.get("exhibit_type"),
                "description": exhibit.get("description"),
                "unit": None,
                "value": None,
                "period_start": None,
                "period_end": None,
                "form": exhibit.get("form_type"),
                "filed_date": exhibit.get("filing_date"),
                "accession_number": exhibit.get("accession_number"),
                "filing_url": exhibit.get("document_url"),
                "match_reason": exhibit.get("match_reason"),
            }
        )

    return rows


def build_text_extraction_diagnostic_rows(ticker, cik, extractions):
    """
    Aplatit les observations extraites du texte des 8-K (SEC-10) en
    lignes CSV. `value` prend la valeur du champ pertinent selon `kind`
    (share_quantity / exercise_price / expiration_years) ; `raw_snippet`
    reste toujours visible pour vérification humaine — cette extraction
    est heuristique, jamais une valeur canonique.
    """

    rows = []

    for extraction in extractions:

        kind = extraction["kind"]
        value = (
            extraction.get("share_quantity")
            if kind == "share_quantity"
            else extraction.get("exercise_price")
            if kind == "exercise_price"
            else extraction.get("expiration_years")
        )

        rows.append(
            {
                "ticker": ticker,
                "cik": cik,
                "source_table": "8k_warrant_text_extraction",
                "concept": kind,
                "description": extraction.get("label"),
                "unit": _TEXT_EXTRACTION_UNIT_BY_KIND.get(kind),
                "value": value,
                "period_start": None,
                "period_end": None,
                "form": extraction.get("form_type"),
                "filed_date": extraction.get("filed_date"),
                "accession_number": extraction.get("accession_number"),
                "filing_url": extraction.get("document_url"),
                "raw_snippet": extraction.get("raw_snippet"),
                "extraction_method": extraction.get("extraction_method"),
            }
        )

    return rows


def export_diagnostic_rows(conn, tickers, ticker_cik_map):
    """
    Pour chaque ticker résolu vers un CIK, lit les faits warrants et
    shares outstanding déjà en base et les aplatit en lignes CSV.

    Un ticker non résolu (absent de ticker_cik_map) est simplement ignoré
    — pas d'erreur, car il peut légitimement n'avoir jamais été collecté.
    """

    rows = []

    for ticker in tickers:

        cik = resolve_cik(ticker, ticker_cik_map)

        if cik is None:
            continue

        warrant_facts = read_sec_warrant_xbrl_facts(conn, cik)
        rows.extend(
            build_diagnostic_rows(ticker, cik, "warrant", warrant_facts)
        )

        shares_facts = read_sec_shares_outstanding_facts(conn, cik)
        rows.extend(
            build_diagnostic_rows(
                ticker,
                cik,
                "shares_outstanding",
                shares_facts,
            )
        )

        warrant_exhibits = read_sec_8k_warrant_exhibits(conn, cik)
        rows.extend(
            build_exhibit_diagnostic_rows(ticker, cik, warrant_exhibits)
        )

        text_extractions = read_sec_8k_warrant_text_extractions(conn, cik)
        rows.extend(
            build_text_extraction_diagnostic_rows(ticker, cik, text_extractions)
        )

    return rows


def write_csv(rows, output_path):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Export CSV diagnostique des faits warrants/shares "
            "outstanding déjà collectés, avec lien direct vers le "
            "filing EDGAR source."
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
            "User-Agent SEC (nom + contact), requis pour résoudre les "
            f"CIK. À défaut, lu depuis {USER_AGENT_ENV}."
        ),
    )

    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
    )

    return parser


def main():
    args = build_arg_parser().parse_args()

    user_agent = args.user_agent or os.environ.get(USER_AGENT_ENV)

    if not user_agent:
        raise ValueError(
            "No SEC User-Agent provided: pass --user-agent or set "
            f"{USER_AGENT_ENV}."
        )

    tickers = [
        ticker.strip().upper()
        for ticker in args.tickers.split(",")
        if ticker.strip()
    ]

    ticker_cik_map = fetch_ticker_cik_map(user_agent=user_agent)

    conn = get_connection()

    try:
        rows = export_diagnostic_rows(conn, tickers, ticker_cik_map)
    finally:
        conn.close()

    write_csv(rows, args.output)

    print(f"{len(rows)} lignes écrites dans {args.output}")


if __name__ == "__main__":
    main()
