"""Extraction LLM des modalités de warrants depuis le texte des 8-K (SEC-15).

Remplace (en parallèle, pas en remplacement destructif) l'extraction par
expressions régulières de SEC-10 (`sec_8k_warrant_text_extraction.py`),
qui a été validée sur un seul filing réel (TNON, 2026-08-31) et a
immédiatement échoué sur 3 autres filings réels du même émetteur —
formulation différente pour la quantité ("up to an aggregate of X" vs
"up to X" vs "an aggregate of X"), le prix d'exercice ("has an exercise
price of $X per share" vs "with an exercise price of $X") et
l'expiration ("five (5) years from issuance" vs "on the fifth
anniversary of the date of issuance"). Continuer à corriger le regex au
cas par cas ne converge pas — le nombre de formulations possibles à
travers des centaines d'émetteurs, chacun avec les conventions de
rédaction de son propre cabinet juridique, est en pratique non borné.

Même discipline de traçabilité que SEC-10 : chaque fait extrait doit
citer verbatim la phrase source (`raw_snippet`) — un extrait de texte
qui n'existe PAS dans le document source est rejeté, pas seulement
signalé, pour borner le risque d'hallucination du modèle. Réutilise la
même forme de résultat (kind/label/share_quantity/exercise_price/
expiration_years/raw_snippet) que SEC-10, donc la même table
`raw.sec_8k_warrant_text_extraction` (voir migration 017 pour la
colonne `extraction_method` qui distingue les deux méthodes).
"""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor

import anthropic

from collectors.warrants.src.sec_8k_warrant_discovery import (
    fetch_all_8k_filings,
    fetch_url,
    filter_candidate_filings,
    find_main_document,
    parse_filing_index_documents,
)
from collectors.warrants.src.sec_8k_warrant_text_extraction import fetch_document_text


DEFAULT_MODEL = "claude-sonnet-5"

DEFAULT_MAX_TOKENS = 2048

# Plus conservateur que sec_8k_warrant_discovery.DEFAULT_MAX_WORKERS (6) :
# chaque appel a un coût API réel et est soumis aux limites de débit
# d'Anthropic, contrairement aux requêtes SEC.gov (gratuites, limite
# de débit plus généreuse) — SEC-17.
DEFAULT_LLM_MAX_WORKERS = 3

VALID_KINDS = ("share_quantity", "exercise_price", "expiration_years")

EXTRACTION_SYSTEM_PROMPT = (
    "You extract warrant terms from SEC 8-K filing text. Return ONLY a JSON array "
    "(no prose, no markdown code fences). Each element must have exactly these keys: "
    '"kind" (one of "share_quantity", "exercise_price", "expiration_years"), '
    '"label" (the warrant series name as it appears in the text, e.g. "Series A"), '
    '"value" (a number: share count, dollar price, or number of years), and '
    '"raw_snippet" (the exact verbatim sentence or clause from the source text that '
    "states this value, copied character-for-character — never paraphrased). "
    "Only extract facts explicitly stated in the text. If nothing is found, return []."
)


def build_extraction_prompt(document_text):
    return (
        "Extract every warrant share quantity, exercise price, and expiration term "
        "stated in the following SEC 8-K filing text.\n\n"
        f"<document>\n{document_text}\n</document>"
    )


def _coerce_value(kind, value):
    """Convertit `value` vers le type attendu par colonne ; None si invalide."""

    try:
        if kind == "share_quantity":
            return int(value)
        if kind == "exercise_price":
            return float(value)
        if kind == "expiration_years":
            return int(value)
    except (TypeError, ValueError):
        return None

    return None


def _validate_and_normalize_observation(item, document_text):
    """
    Valide un élément brut renvoyé par le modèle et le normalise vers la
    forme attendue par `raw.sec_8k_warrant_text_extraction`. Retourne
    None (rejet silencieux) si :

    - `kind` n'est pas une des 3 valeurs acceptées par la contrainte
      CHECK de la table ;
    - `raw_snippet` ne peut pas être retrouvé mot pour mot dans le texte
      source — c'est le principal garde-fou anti-hallucination : un
      "fait" dont la citation source n'existe pas dans le document
      n'est jamais persisté comme vérifiable ;
    - `value` est absent ou ne peut pas être converti dans le type
      numérique attendu pour ce `kind`.
    """

    kind = item.get("kind")

    if kind not in VALID_KINDS:
        return None

    raw_snippet = item.get("raw_snippet")

    if not raw_snippet or not isinstance(raw_snippet, str) or raw_snippet not in document_text:
        return None

    numeric_value = _coerce_value(kind, item.get("value"))

    if numeric_value is None:
        return None

    observation = {
        "kind": kind,
        "label": item.get("label"),
        "raw_snippet": raw_snippet,
        "extraction_method": "llm",
    }

    observation[kind] = numeric_value

    return observation


def parse_llm_response(response_text, document_text):
    """
    Parse la réponse du modèle en une liste d'observations validées.

    Tolère un bloc de code Markdown (```json ... ```) autour du JSON —
    malgré la consigne du prompt, le modèle en ajoute parfois un.
    Toute réponse qui n'est pas un JSON valide, ou pas une liste,
    retourne une liste vide plutôt que de lever — une réponse
    inexploitable ne doit jamais faire planter la collecte d'un ticker.
    """

    text = response_text.strip()

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)

    try:
        raw_items = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return []

    if not isinstance(raw_items, list):
        return []

    observations = []

    for item in raw_items:

        if not isinstance(item, dict):
            continue

        normalized = _validate_and_normalize_observation(item, document_text)

        if normalized is not None:
            observations.append(normalized)

    return observations


def extract_warrant_terms_llm(
    document_text,
    *,
    api_key,
    model=DEFAULT_MODEL,
    max_tokens=DEFAULT_MAX_TOKENS,
):
    """
    Appelle l'API Claude pour extraire les modalités de warrants du
    texte d'un 8-K. Contrairement à `extract_warrant_terms` (SEC-10,
    regex), robuste aux formulations juridiques variées par
    construction plutôt que par accumulation de motifs.
    """

    client = anthropic.Anthropic(api_key=api_key)

    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=EXTRACTION_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": build_extraction_prompt(document_text),
            }
        ],
    )

    response_text = "".join(
        block.text
        for block in response.content
        if getattr(block, "type", None) == "text"
    )

    return parse_llm_response(response_text, document_text)


def _llm_terms_for_candidate(
    filing,
    *,
    user_agent,
    api_key,
    model,
    max_tokens,
    timeout_seconds,
    fetch_cache,
):
    """
    Traite UN filing candidat : ouvre son document principal, l'envoie
    au modèle, et retourne les observations trouvées (peut être vide).
    Isolé pour exécution parallèle (SEC-17).
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
            **observation,
        }
        for observation in extract_warrant_terms_llm(
            document_text,
            api_key=api_key,
            model=model,
            max_tokens=max_tokens,
        )
    ]


def discover_and_extract_warrant_terms_for_cik_llm(
    cik,
    *,
    user_agent,
    api_key,
    model=DEFAULT_MODEL,
    max_tokens=DEFAULT_MAX_TOKENS,
    timeout_seconds=30,
    filings=None,
    fetch_cache=None,
    max_workers=DEFAULT_LLM_MAX_WORKERS,
):
    """
    Pour un CIK : liste l'historique complet des 8-K (SEC-12) candidats
    (items 1.01/3.02, réutilise sec_8k_warrant_discovery), ouvre le
    document PRINCIPAL de chacun (pas les exhibits, mêmes que SEC-10),
    et y applique l'extraction LLM plutôt que le regex.

    `filings`/`fetch_cache` (SEC-17) : voir
    `sec_8k_warrant_discovery.discover_warrant_exhibits_for_cik` — le
    fetch_cache est particulièrement utile ici, puisque SEC-10 (regex)
    et ce pipeline LLM ont besoin du MÊME texte de document principal
    pour les mêmes filings candidats. `max_workers` par défaut plus bas
    que les autres pipelines (voir DEFAULT_LLM_MAX_WORKERS) : chaque
    candidat traité en parallèle ici déclenche un appel API payant,
    contrairement aux requêtes SEC.gov gratuites des autres pipelines.

    Même forme de résultat que
    `sec_8k_warrant_text_extraction.discover_and_extract_warrant_terms_for_cik`,
    prête à persister dans la même table.
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
            lambda filing: _llm_terms_for_candidate(
                filing,
                user_agent=user_agent,
                api_key=api_key,
                model=model,
                max_tokens=max_tokens,
                timeout_seconds=timeout_seconds,
                fetch_cache=fetch_cache,
            ),
            candidates,
        )

        return [observation for results in per_filing_results for observation in results]
