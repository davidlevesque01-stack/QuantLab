"""Recherche SEC EDGAR par nom de société — repli pour SEC-14.

`company_tickers.json` (SEC-05) ne couvre que les émetteurs actuellement
enregistrés chez SEC. Pour un ticker historique dont la société a depuis
été radiée/acquise (ex. CinCor Pharma -> rachetée par AstraZeneca en
2023), il faut chercher par nom — en utilisant le nom déjà connu via
`core.nasdaq_halt_episode.issue_name` — plutôt que par ticker.

Piège découvert en construisant ceci : l'endpoint `browse-edgar` en
sortie `output=atom` a un bug côté SEC pour la recherche par nom — le
nom de la société n'apparaît nulle part dans le XML (juste des
références mémoire brutes du type "ARRAY(0x...)"). La page HTML
(sans `output=atom`) fonctionne correctement et est donc utilisée ici.

Deux gabarits HTML différents selon le nombre de résultats :
- un seul résultat : `<span class="companyName">NOM ... CIK=XXXXXXXXXX`
- plusieurs résultats : une table, une ligne par société.
"""

from __future__ import annotations

import re
from urllib.parse import quote

from collectors.warrants.src.sec_8k_warrant_discovery import fetch_url


COMPANY_SEARCH_URL_TEMPLATE = (
    "https://www.sec.gov/cgi-bin/browse-edgar"
    "?action=getcompany&company={name}&type=&dateb=&owner=include&count=100"
)

_SINGLE_RESULT_PATTERN = re.compile(
    r'<span class="companyName">(?P<name>.+?)\s*'
    r'<acronym title="Central Index Key">CIK</acronym>#:.*?CIK=(?P<cik>\d{10})',
    re.DOTALL,
)

_ROW_PATTERN = re.compile(r"<tr>.*?</tr>", re.DOTALL)
_ROW_CIK_PATTERN = re.compile(r"CIK=(\d{10})")
_ROW_NAME_PATTERN = re.compile(r'<td scope="row">(.+?)<br', re.DOTALL)

_NAME_SUFFIX_PATTERN = re.compile(
    r"[,.]?\s*(inc\.?|incorporated|corp\.?|corporation|co\.?|company|"
    r"ltd\.?|limited|llc|holdings?|plc)\s*$",
    re.IGNORECASE,
)


def fetch_company_search_html(name, *, user_agent, timeout_seconds=30):
    """Requête brute de la page de recherche par nom (HTML, pas atom)."""

    url = COMPANY_SEARCH_URL_TEMPLATE.format(name=quote(name))

    return fetch_url(
        url,
        user_agent=user_agent,
        timeout_seconds=timeout_seconds,
    ).decode("utf-8", errors="replace")


def parse_company_search_html(html):
    """
    Parse la page de résultats (les deux gabarits possibles) en liste de
    dicts {name, cik} (CIK sur 10 chiffres, zero-paddé).
    """

    single = _SINGLE_RESULT_PATTERN.search(html)

    if single:
        return [
            {
                "name": single.group("name").strip(),
                "cik": single.group("cik"),
            }
        ]

    results = []

    for row in _ROW_PATTERN.findall(html):

        cik_match = _ROW_CIK_PATTERN.search(row)
        name_match = _ROW_NAME_PATTERN.search(row)

        if cik_match and name_match:
            results.append(
                {
                    "name": name_match.group(1).strip(),
                    "cik": cik_match.group(1),
                }
            )

    return results


def search_companies_by_name(name, *, user_agent, timeout_seconds=30):
    """Recherche + parsing combinés."""

    html = fetch_company_search_html(
        name,
        user_agent=user_agent,
        timeout_seconds=timeout_seconds,
    )

    return parse_company_search_html(html)


def normalize_company_name(name):
    """
    Normalise un nom de société pour comparaison : minuscules, dépouillé
    des suffixes juridiques usuels (Inc., Corp., LLC, Holdings, ...) et
    de la ponctuation, espaces réduits.
    """

    normalized = name.strip().lower()
    normalized = _NAME_SUFFIX_PATTERN.sub("", normalized)
    normalized = re.sub(r"[^\w\s]", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()

    return normalized


def _is_word_prefix(shorter, longer):
    """
    True si `shorter` est un préfixe de `longer` s'arrêtant sur une
    frontière de mot (pas une simple sous-chaîne) — ex. "cerevel
    therapeutics" est un préfixe-mot de "cerevel therapeutics holdings"
    mais "cere" ne l'est pas.
    """

    return longer == shorter or longer.startswith(shorter + " ")


def find_best_match(target_name, candidates):
    """
    Retourne le candidat correspondant au nom cible, uniquement si un
    seul candidat correspond. Deux niveaux, du plus sûr au plus
    permissif — jamais de correspondance floue/scorée, car un mauvais
    rapprochement attribuerait silencieusement les données d'un émetteur
    à un autre :

    1. Égalité exacte après normalisation.
    2. À défaut, préfixe-mot dans un sens ou l'autre (ex. notre
       `issue_name` interne omet parfois "Holdings"/"Inc." que le nom
       légal SEC inclut, ou l'inverse) — trouvé en validant CERE
       ("Cerevel Therapeutics" en base vs "Cerevel Therapeutics
       Holdings, Inc." chez SEC), un seul candidat retourné par la
       recherche SEC dans ce cas, donc pas d'ambiguïté réelle.

    Retourne None en cas d'ambiguïté (plusieurs candidats à un niveau
    donné) ou d'absence de correspondance à tout niveau, plutôt que de
    deviner.
    """

    target_normalized = normalize_company_name(target_name)

    exact_matches = [
        candidate
        for candidate in candidates
        if normalize_company_name(candidate["name"]) == target_normalized
    ]

    if len(exact_matches) == 1:
        return exact_matches[0]

    if exact_matches:
        return None

    prefix_matches = [
        candidate
        for candidate in candidates
        if _is_word_prefix(
            *sorted(
                [target_normalized, normalize_company_name(candidate["name"])],
                key=len,
            )
        )
    ]

    if len(prefix_matches) == 1:
        return prefix_matches[0]

    return None


def resolve_cik_by_name(issuer_name, *, user_agent, timeout_seconds=30):
    """
    Recherche un CIK par nom de société (repli pour un ticker absent de
    company_tickers.json). Retourne le CIK (str, 10 chiffres) si une
    correspondance unique et exacte est trouvée, sinon None.
    """

    candidates = search_companies_by_name(
        issuer_name,
        user_agent=user_agent,
        timeout_seconds=timeout_seconds,
    )

    match = find_best_match(issuer_name, candidates)

    return match["cik"] if match else None
