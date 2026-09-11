"""Extraction des modalités de warrants depuis le texte des 8-K (SEC-10).

Suivi de SEC-09 : les exhibits "FORM OF ... WARRANT" sont des gabarits
avec des blancs (`[*]`, `______`), pas l'instrument réel rempli. Les
vraies modalités (prix d'exercice, quantité, expiration) vivent dans le
récit de l'Item 1.01 du corps du 8-K lui-même.

Vérifié sur un cas réel (TNON, 8-K du 2026-08-31) : « Series A warrants
to purchase up to an aggregate of 1,058,517 shares ... Each Series A
Warrant has an exercise price of $5.02 per share ... will expire five
(5) years from issuance » — correspond exactement aux valeurs vues sur
DilutionTracker.

Extraction heuristique par expressions régulières, validée sur cet
exemple réel. La généralisation à d'autres émetteurs/gabarits d'avocats
reste à élargir au fur et à mesure de nouveaux cas réels — chaque
résultat conserve l'extrait de texte source (`raw_snippet`) pour
vérification humaine, jamais présenté comme une valeur canonique sans
traçabilité.
"""

from __future__ import annotations

import html
import re

from collectors.warrants.src.sec_8k_warrant_discovery import (
    fetch_8k_filings,
    fetch_url,
    filter_candidate_filings,
    find_main_document,
    parse_filing_index_documents,
)


WARRANT_QUANTITY_PATTERN = re.compile(
    r"(?P<label>[\w\-]+(?:\s+[\w\-]+){0,3})\s+[Ww]arrants?\s*"
    r"(?:\([^)]*\)\s*)?"
    r"to purchase up to an aggregate of (?P<qty>[\d,]+)\s+shares"
)

EXERCISE_PRICE_PATTERN = re.compile(
    r"(?P<label>[\w\-]+(?:\s+[\w\-]+){0,3})\s+[Ww]arrant\s+"
    r"has an exercise price of \$(?P<price>[\d.]+) per share"
)

NOMINAL_EXERCISE_PRICE_PATTERN = re.compile(
    r"exercised at a nominal exercise price of \$(?P<price>[\d.]+) per share"
)

EXPIRATION_YEARS_PATTERN = re.compile(
    r"will expire \w+ \((?P<years>\d+)\)\s*years? from issuance"
)


def strip_html_to_text(html_content):
    """Convertit un document HTML EDGAR en texte brut normalisé."""

    text = re.sub(r"<[^>]+>", " ", html_content)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def fetch_document_text(document_url, *, user_agent, timeout_seconds=30):
    """Télécharge un document EDGAR et retourne son texte brut normalisé."""

    html_bytes = fetch_url(
        document_url,
        user_agent=user_agent,
        timeout_seconds=timeout_seconds,
    )

    return strip_html_to_text(html_bytes.decode("utf-8", errors="replace"))


def extract_warrant_quantities(text):
    """
    Extrait les paires (label, quantité) du type « Series A warrants to
    purchase up to an aggregate of 1,058,517 shares ».
    """

    return [
        {
            "label": match.group("label").strip(),
            "share_quantity": int(match.group("qty").replace(",", "")),
            "raw_snippet": match.group(0),
        }
        for match in WARRANT_QUANTITY_PATTERN.finditer(text)
    ]


def extract_exercise_prices(text):
    """
    Extrait les prix d'exercice explicites (« Each Series A Warrant has
    an exercise price of $5.02 per share ») et les prix nominaux des
    pre-funded warrants (« nominal exercise price of $0.001 per share »).
    """

    results = [
        {
            "label": match.group("label").strip(),
            "exercise_price": float(match.group("price")),
            "raw_snippet": match.group(0),
        }
        for match in EXERCISE_PRICE_PATTERN.finditer(text)
    ]

    results.extend(
        {
            "label": "Pre-Funded Warrant",
            "exercise_price": float(match.group("price")),
            "raw_snippet": match.group(0),
        }
        for match in NOMINAL_EXERCISE_PRICE_PATTERN.finditer(text)
    )

    return results


def extract_expiration_terms(text):
    """
    Extrait les durées d'expiration relatives (« will expire five (5)
    years from issuance »).
    """

    return [
        {
            "expiration_years": int(match.group("years")),
            "raw_snippet": match.group(0),
        }
        for match in EXPIRATION_YEARS_PATTERN.finditer(text)
    ]


def extract_warrant_terms(text):
    """
    Combine les trois extractions ci-dessus en une liste d'observations
    « à plat », une par fait trouvé (quantité, prix, ou expiration).

    Ne tente pas de relier les faits entre eux par warrant individuel —
    cette corrélation nécessiterait une compréhension du contexte
    au-delà de simples correspondances regex, laissée à la lecture
    humaine du raw_snippet.
    """

    observations = []

    observations.extend(
        {"kind": "share_quantity", **item}
        for item in extract_warrant_quantities(text)
    )
    observations.extend(
        {"kind": "exercise_price", **item}
        for item in extract_exercise_prices(text)
    )
    observations.extend(
        {"kind": "expiration_years", **item}
        for item in extract_expiration_terms(text)
    )

    return observations


def discover_and_extract_warrant_terms_for_cik(
    cik,
    *,
    user_agent,
    timeout_seconds=30,
):
    """
    Pour un CIK : liste les 8-K candidats (items 1.01/3.02, réutilise
    sec_8k_warrant_discovery), ouvre le document PRINCIPAL de chacun
    (pas les exhibits), en extrait le texte, et y applique
    extract_warrant_terms.

    Retourne une liste d'observations aplaties, chacune annotée de son
    accession_number, document_url, filed_date et form_type d'origine,
    prêtes à persister.
    """

    filings = fetch_8k_filings(
        cik,
        user_agent=user_agent,
        timeout_seconds=timeout_seconds,
    )

    candidates = filter_candidate_filings(filings)

    results = []

    for filing in candidates:

        index_url = filing["filing_index_url"]

        if index_url is None:
            continue

        index_html = fetch_url(
            index_url,
            user_agent=user_agent,
            timeout_seconds=timeout_seconds,
        )

        documents = parse_filing_index_documents(index_html)
        main_document = find_main_document(documents)

        if main_document is None:
            continue

        document_text = fetch_document_text(
            main_document["url"],
            user_agent=user_agent,
            timeout_seconds=timeout_seconds,
        )

        for observation in extract_warrant_terms(document_text):

            results.append(
                {
                    "accession_number": filing["accession_number"],
                    "document_url": main_document["url"],
                    "filed_date": filing["filing_date"],
                    "form_type": filing["form_type"],
                    **observation,
                }
            )

    return results
