"""Accès générique à l'API SEC EDGAR company-facts et extraction de faits XBRL.

Partagé entre l'extraction des warrants (sec_warrant_xbrl, taxonomie
us-gaap) et celle des shares outstanding (sec_shares_outstanding,
taxonomie dei) — les deux consomment la même ressource company-facts et
l'aplatissent de la même façon.
"""

from __future__ import annotations

from collectors.warrants.src.sec_edgar_client import fetch_json


COMPANY_FACTS_URL_TEMPLATE = (
    "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
)


def fetch_company_facts(
    cik,
    *,
    user_agent,
    timeout_seconds=30,
):
    """
    Récupère l'ensemble des faits XBRL déclarés par un émetteur (toutes
    périodes, tous formulaires) via l'API SEC company-facts.
    """

    url = COMPANY_FACTS_URL_TEMPLATE.format(cik=cik)

    return fetch_json(
        url,
        user_agent=user_agent,
        timeout_seconds=timeout_seconds,
    )


def extract_facts(
    company_facts,
    *,
    taxonomy,
    matches_concept,
):
    """
    Aplatit les faits d'une taxonomie donnée (ex. "us-gaap", "dei") dont le
    nom de concept satisfait matches_concept(concept_name) en observations
    ponctuelles avec leur provenance (accession, formulaire, date de dépôt,
    période).
    """

    taxonomy_facts = company_facts.get("facts", {}).get(taxonomy, {})

    observations = []

    for concept_name, concept_data in taxonomy_facts.items():

        if not matches_concept(concept_name):
            continue

        units = concept_data.get("units", {})

        for unit, entries in units.items():

            for entry in entries:

                observations.append(
                    {
                        "concept": concept_name,
                        "unit": unit,
                        "value": entry.get("val"),
                        "period_start": entry.get("start"),
                        "period_end": entry.get("end"),
                        "form": entry.get("form"),
                        "filed": entry.get("filed"),
                        "accession_number": entry.get("accn"),
                        "fiscal_year": entry.get("fy"),
                        "fiscal_period": entry.get("fp"),
                    }
                )

    return observations
