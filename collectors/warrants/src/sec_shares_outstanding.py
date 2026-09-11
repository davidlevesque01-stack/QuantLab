"""Extraction des shares outstanding via XBRL (SEC-01 / SEC-02).

dei:EntityCommonStockSharesOutstanding est un fait structuré et gratuit de
l'API SEC EDGAR company-facts, indépendant de DilutionTracker — couvre en
principe tous les émetteurs déposants (le champ figure sur la page de
couverture de chaque 10-K/10-Q), contrairement aux warrants où le
balisage XBRL dimensionnel est loin d'être universel.
"""

from __future__ import annotations

from collectors.warrants.src.sec_xbrl_facts import extract_facts, fetch_company_facts


SHARES_OUTSTANDING_CONCEPT = "EntityCommonStockSharesOutstanding"


def extract_shares_outstanding_facts(company_facts):
    """
    Filtre le fait dei:EntityCommonStockSharesOutstanding et l'aplatit en
    observations ponctuelles avec leur provenance (accession, formulaire,
    date de dépôt, période).
    """

    return extract_facts(
        company_facts,
        taxonomy="dei",
        matches_concept=lambda name: name == SHARES_OUTSTANDING_CONCEPT,
    )
