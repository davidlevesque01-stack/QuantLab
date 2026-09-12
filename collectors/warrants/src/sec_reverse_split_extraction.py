"""Découverte et extraction des reverse stock splits (SEC-11, root cause #1).

Un reverse split est annoncé via les items 3.03 (Material Modification to
Rights of Security Holders) et 5.03 (Amendments to Articles of
Incorporation) — jamais 1.01/3.02, donc invisible à la découverte de
warrants (SEC-09/SEC-10). Sans ça, `raw.sec_8k_warrant_text_extraction`
ne reflète que les modalités d'origine, jamais les modalités actuelles
ajustées.

Validé sur un cas réel (TNON, 8-K du 2026-08-10, accession
0001213900-26-087352) : « ... to effect a 1-for-35 reverse stock split
... effective as of 12:01 a.m. Eastern Time on August 10, 2026 » —
confirme exactement le ratio ~35x déjà déduit en comparant nos données
brutes à DilutionTracker sur 3 séries de warrants indépendantes.

SEC-16 : `EFFECTIVE_DATE_PATTERN` ne matchait que cette formulation
précise ("effective as of ... on <date>"). Deux filings réels plus
anciens, atteints par SEC-12 (pagination de l'historique complet), ont
révélé des formulations différentes — le ratio était toujours extrait
correctement, seule la date d'effet restait NULL :
- TNON, 2023-11-07 : « ... became effective at 12:01 a.m. on
  November 2, 2023 »
- GPUS, 2019-03-14 : « ... became effective in the State of Delaware
  on March 14, 2019 »
Généralisé en un motif plus souple (« effective » suivi de texte
libre borné, puis « on <date> ») plutôt que d'empiler un motif par
formulation — même logique que SEC-15 (formulations juridiques non
bornées à travers les émetteurs/années).

Portée volontairement minimale (capture RAW de l'événement de split
seulement) : appliquer rétroactivement le ratio aux lignes déjà
capturées dans raw.sec_8k_warrant_text_extraction nécessite un concept
CORE (lié à WRT-06), explicitement hors scope ici.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from collectors.warrants.src.sec_8k_warrant_discovery import (
    DEFAULT_MAX_WORKERS,
    fetch_all_8k_filings,
    fetch_url,
    find_main_document,
    parse_filing_index_documents,
)
from collectors.warrants.src.sec_8k_warrant_text_extraction import (
    fetch_document_text,
)


SPLIT_ITEM_CODES = ("3.03", "5.03")

SPLIT_RATIO_PATTERN = re.compile(
    r"(?P<ratio_new>\d+)-for-(?P<ratio_old>\d+)\s+reverse stock split",
    re.IGNORECASE,
)

EFFECTIVE_DATE_PATTERN = re.compile(
    r"effective\b.{0,60}?on (?P<date>[A-Z][a-z]+ \d{1,2}, \d{4})",
    re.IGNORECASE,
)


def filter_split_candidate_filings(filings):
    """
    Garde les dépôts dont les items évoquent une modification des droits
    des porteurs de titres ou des statuts constitutifs (3.03/5.03) —
    typiquement un reverse/forward split.
    """

    return [
        filing
        for filing in filings
        if any(
            code in (filing.get("item_codes") or "")
            for code in SPLIT_ITEM_CODES
        )
    ]


def extract_reverse_split(text):
    """
    Extrait le ratio et la date d'effet d'un reverse stock split depuis
    le texte d'un 8-K. Retourne None si le texte ne mentionne pas de
    ratio « N-for-M reverse stock split » reconnu (ex. un 3.03/5.03 pour
    une raison autre qu'un split, ou une formulation non couverte).

    `ratio_new`/`ratio_old` : N nouvelles actions pour M anciennes,
    dans l'ordre où le texte les cite (ex. "1-for-35" -> ratio_new=1,
    ratio_old=35 -> 35 anciennes actions deviennent 1 nouvelle ;
    facteur de consolidation = ratio_old / ratio_new).
    """

    ratio_match = SPLIT_RATIO_PATTERN.search(text)

    if not ratio_match:
        return None

    date_match = EFFECTIVE_DATE_PATTERN.search(text)

    effective_date = None
    if date_match:
        try:
            effective_date = datetime.strptime(
                date_match.group("date"),
                "%B %d, %Y",
            ).date().isoformat()
        except ValueError:
            effective_date = None

    return {
        "ratio_new": int(ratio_match.group("ratio_new")),
        "ratio_old": int(ratio_match.group("ratio_old")),
        "effective_date": effective_date,
        "raw_snippet": ratio_match.group(0),
    }


def _split_for_candidate(filing, *, user_agent, timeout_seconds, fetch_cache):
    """
    Traite UN filing candidat : ouvre son document principal et y
    cherche un événement de split (None si aucun trouvé). Isolé pour
    exécution parallèle (SEC-17). Contrairement aux pipelines 1.01/3.02
    (exhibits/SEC-10/SEC-15), ce pipeline traite un ensemble de filings
    candidats différent (3.03/5.03) — `fetch_cache` reste accepté par
    cohérence d'API, mais n'a d'effet que si un autre appel a déjà
    traité EXACTEMENT le même filing (rare, aucun recoupement garanti).
    """

    index_url = filing["filing_index_url"]

    if index_url is None:
        return None

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
        return None

    def _fetch_text(url):
        return fetch_document_text(url, user_agent=user_agent, timeout_seconds=timeout_seconds)

    if fetch_cache is not None:
        document_text = fetch_cache.get_document_text(main_document["url"], _fetch_text)
    else:
        document_text = _fetch_text(main_document["url"])

    split_event = extract_reverse_split(document_text)

    if split_event is None:
        return None

    return {
        "accession_number": filing["accession_number"],
        "document_url": main_document["url"],
        "filed_date": filing["filing_date"],
        "form_type": filing["form_type"],
        **split_event,
    }


def discover_and_extract_reverse_splits_for_cik(
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
    limité aux 40 plus récents) candidats (items 3.03/5.03), ouvre le
    document principal de chacun, et y cherche un ratio de reverse
    split. Retourne une liste d'événements de split trouvés (un par
    filing où un ratio a été reconnu), chacun annoté de son
    accession_number, document_url, filed_date et form_type.

    `filings`/`fetch_cache` (SEC-17) : voir
    `sec_8k_warrant_discovery.discover_warrant_exhibits_for_cik`.
    Traitement en parallèle (`max_workers` threads) des filings
    candidats.
    """

    if filings is None:
        filings = fetch_all_8k_filings(
            cik,
            user_agent=user_agent,
            timeout_seconds=timeout_seconds,
        )

    candidates = filter_split_candidate_filings(filings)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        split_events = executor.map(
            lambda filing: _split_for_candidate(
                filing,
                user_agent=user_agent,
                timeout_seconds=timeout_seconds,
                fetch_cache=fetch_cache,
            ),
            candidates,
        )

        return [event for event in split_events if event is not None]
