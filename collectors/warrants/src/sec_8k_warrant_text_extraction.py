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
from concurrent.futures import ThreadPoolExecutor

from collectors.warrants.src.sec_8k_warrant_discovery import (
    DEFAULT_MAX_WORKERS,
    fetch_all_8k_filings,
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


def _terms_for_candidate(filing, *, user_agent, timeout_seconds, fetch_cache):
    """
    Traite UN filing candidat : ouvre son document principal, en
    extrait le texte, et retourne les observations regex trouvées
    (peut être vide). Isolé pour exécution parallèle (SEC-17).
    """

    index_url = filing["filing_index_url"]

    if index_url is None:
        return []

    def _fetch_and_parse(url):
        return parse_filing_index_documents(
            fetch_url(url, user_agent=user_agent, timeout_seconds=timeout_seconds)
        )

    if fetch_cache is not None:
        documents = fetch_cache.get_index_documents(index_url, _fetch_and_parse)
    else:
        documents = _fetch_and_parse(index_url)

    main_document = find_main_document(documents)

    if main_document is None:
        return []

    def _fetch_text(url):
        return fetch_document_text(url, user_agent=user_agent, timeout_seconds=timeout_seconds)

    if fetch_cache is not None:
        document_text = fetch_cache.get_document_text(main_document["url"], _fetch_text)
    else:
        document_text = _fetch_text(main_document["url"])

    return [
        {
            "accession_number": filing["accession_number"],
            "document_url": main_document["url"],
            "filed_date": filing["filing_date"],
            "form_type": filing["form_type"],
            "extraction_method": "regex",
            **observation,
        }
        for observation in extract_warrant_terms(document_text)
    ]


def discover_and_extract_warrant_terms_for_cik(
    cik,
    *,
    user_agent,
    timeout_seconds=30,
    filings=None,
    fetch_cache=None,
    max_workers=DEFAULT_MAX_WORKERS,
):
    """
    Pour un CIK : liste l'historique COMPLET des 8-K (SEC-12, plus
    limité aux 40 plus récents) candidats (items 1.01/3.02, réutilise
    sec_8k_warrant_discovery), ouvre le document PRINCIPAL de chacun
    (pas les exhibits), en extrait le texte, et y applique
    extract_warrant_terms.

    `filings`/`fetch_cache` (SEC-17) : voir
    `sec_8k_warrant_discovery.discover_warrant_exhibits_for_cik` — même
    convention de partage entre pipelines de découverte qui traitent les
    mêmes filings candidats (1.01/3.02). Traitement en parallèle
    (`max_workers` threads) des filings candidats.

    Retourne une liste d'observations aplaties, chacune annotée de son
    accession_number, document_url, filed_date et form_type d'origine,
    prêtes à persister.
    """

    if filings is None:
        filings = fetch_all_8k_filings(
            cik,
            user_agent=user_agent,
            timeout_seconds=timeout_seconds,
        )

    candidates = filter_candidate_filings(filings)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        per_filing_results = executor.map(
            lambda filing: _terms_for_candidate(
                filing,
                user_agent=user_agent,
                timeout_seconds=timeout_seconds,
                fetch_cache=fetch_cache,
            ),
            candidates,
        )

        return [observation for results in per_filing_results for observation in results]
