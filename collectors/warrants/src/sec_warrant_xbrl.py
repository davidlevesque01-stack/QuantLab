"""Extraction des modalités de warrants via XBRL (SEC-06 — volet XBRL).

Couvre uniquement les émetteurs qui balisent leurs warrants avec la
dimension "ClassOfWarrantOrRight" de la taxonomie us-gaap (typiquement les
ex-SPAC depuis 2021). La découverte par full-text search et le repli sur le
texte des filings pour les émetteurs non taggués restent un travail de
suivi distinct.
"""

from __future__ import annotations

from collectors.warrants.src.sec_edgar_client import fetch_json


COMPANY_FACTS_URL_TEMPLATE = (
    "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
)

WARRANT_CONCEPT_PREFIX = "ClassOfWarrantOrRight"


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


def extract_warrant_facts(company_facts):
    """
    Filtre les faits us-gaap dont le concept commence par
    "ClassOfWarrantOrRight" et les aplatit en observations ponctuelles
    avec leur provenance (accession, formulaire, date de dépôt, période).
    """

    us_gaap_facts = company_facts.get("facts", {}).get("us-gaap", {})

    observations = []

    for concept_name, concept_data in us_gaap_facts.items():

        if not concept_name.startswith(WARRANT_CONCEPT_PREFIX):
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
