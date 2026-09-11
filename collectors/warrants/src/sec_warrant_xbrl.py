"""Extraction des modalités de warrants via XBRL (SEC-06 — volet XBRL).

Couvre uniquement les émetteurs qui balisent leurs warrants avec la
dimension "ClassOfWarrantOrRight" de la taxonomie us-gaap (typiquement les
ex-SPAC depuis 2021). La découverte par full-text search et le repli sur le
texte des filings pour les émetteurs non taggués restent un travail de
suivi distinct.
"""

from __future__ import annotations

from collectors.warrants.src.sec_xbrl_facts import (
    extract_facts,
    fetch_company_facts,
)


WARRANT_CONCEPT_PREFIX = "ClassOfWarrantOrRight"


def extract_warrant_facts(company_facts):
    """
    Filtre les faits us-gaap dont le concept commence par
    "ClassOfWarrantOrRight" et les aplatit en observations ponctuelles
    avec leur provenance (accession, formulaire, date de dépôt, période).
    """

    return extract_facts(
        company_facts,
        taxonomy="us-gaap",
        matches_concept=lambda name: name.startswith(WARRANT_CONCEPT_PREFIX),
    )
