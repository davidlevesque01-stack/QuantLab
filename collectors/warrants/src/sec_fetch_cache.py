"""Cache de requêtes HTTP partagé entre pipelines de découverte (SEC-17).

Trois pipelines de découverte (exhibits SEC-09, extraction texte regex
SEC-10, extraction texte LLM SEC-15) filtrent tous sur les mêmes items
1.01/3.02 — ils traitent donc le même ensemble de filings candidats.
Sans ce cache, chacun refait sa propre requête d'index de filing et de
texte de document pour le même accession_number, soit jusqu'à 3x la
même requête réseau à chaque backfill complet d'un ticker.

`SharedFetchCache` est un cache mémoire simple (par exécution), pas
persistant — construit une fois par ticker dans `run_sec_collection.py`
et partagé entre les appels séquentiels aux différents pipelines de
découverte. Aucun verrou nécessaire : les pipelines qui le partagent
s'exécutent séquentiellement (jamais concurremment entre eux), donc pas
de compétition d'écriture sur la même clé entre pipelines. La
concurrence interne à CHAQUE pipeline (un thread par filing candidat)
opère sur des clés différentes (un accession_number par thread), donc
sans compétition non plus.
"""

from __future__ import annotations


class SharedFetchCache:
    """
    Mémorise les résultats de `parse_filing_index_documents` (par URL
    d'index) et de `fetch_document_text` (par URL de document), pour
    éviter de refaire la même requête réseau plusieurs fois au sein
    d'un même backfill de ticker.
    """

    def __init__(self):
        self._index_documents = {}
        self._document_text = {}

    def get_index_documents(self, index_url, fetch_fn):
        """
        Retourne les documents parsés de l'index à `index_url`, en
        appelant `fetch_fn(index_url)` seulement si pas déjà en cache.
        """

        if index_url not in self._index_documents:
            self._index_documents[index_url] = fetch_fn(index_url)

        return self._index_documents[index_url]

    def get_document_text(self, document_url, fetch_fn):
        """
        Retourne le texte du document à `document_url`, en appelant
        `fetch_fn(document_url)` seulement si pas déjà en cache.
        """

        if document_url not in self._document_text:
            self._document_text[document_url] = fetch_fn(document_url)

        return self._document_text[document_url]
