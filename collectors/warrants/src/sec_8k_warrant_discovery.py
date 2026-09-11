"""Découverte de warrants via exhibits de 8-K (SEC-09).

Repli explicite pour les warrants invisibles au pipeline XBRL de SEC-06 :
un 8-K annonçant un placement privé de warrants (items 1.01/3.02) ne porte
presque jamais de balisage XBRL détaillé — les modalités vivent dans le
texte d'un exhibit ("FORM OF ... WARRANT"), pas dans un fait structuré.

Ce module ne fait QUE de la découverte : il identifie quels exhibits
décrivent probablement un warrant et capture un lien direct vers le
document. Il n'extrait pas (encore) le prix d'exercice/la quantité/
l'expiration du texte légal de l'exhibit — un travail de suivi distinct,
plus risqué à bien faire sans avoir vu plusieurs gabarits réels.
"""

from __future__ import annotations

import re
import time
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree


ATOM_NS = "{http://www.w3.org/2005/Atom}"

WARRANT_ITEM_CODES = ("1.01", "3.02")

WARRANT_DESCRIPTION_PATTERN = re.compile(r"warrant", re.IGNORECASE)

RETRYABLE_HTTP_STATUS_CODES = {500, 502, 503, 504}


def fetch_url(
    url,
    *,
    user_agent,
    timeout_seconds=30,
    max_retries=3,
    retry_delay_seconds=2,
):
    """
    Requête HTTP brute avec le User-Agent requis par SEC.

    Réessaie avec un backoff linéaire simple sur les erreurs
    transitoires (5xx, timeouts, erreurs réseau) — SEC.gov renvoie
    occasionnellement un 503 même en conditions d'usage normales
    (observé en pratique sur GPUS, 2026-09-11), et un timeout de
    lecture SSL/socket est apparu séparément sur TNON (2026-09-11).
    Les erreurs non transitoires (404, etc.) sont levées immédiatement,
    sans réessai.

    `URLError` et `TimeoutError` sont tous deux des `OSError` (mais
    `TimeoutError` n'hérite PAS de `URLError`) — capturer `OSError`
    couvre les deux, en plus des resets de connexion.
    """

    request = Request(url, headers={"User-Agent": user_agent})

    for attempt in range(max_retries + 1):

        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                return response.read()

        except HTTPError as error:
            if error.code not in RETRYABLE_HTTP_STATUS_CODES or attempt == max_retries:
                raise

        except OSError:
            if attempt == max_retries:
                raise

        time.sleep(retry_delay_seconds * (attempt + 1))


def build_8k_filings_feed_url(cik, count=40):
    return (
        "https://www.sec.gov/cgi-bin/browse-edgar"
        f"?action=getcompany&CIK={cik}&type=8-K"
        f"&dateb=&owner=include&count={count}&output=atom"
    )


def fetch_8k_filings(cik, *, user_agent, timeout_seconds=30, count=40):
    """
    Récupère et parse le flux Atom des dépôts 8-K (et 8-K/A) pour un CIK.
    """

    atom_bytes = fetch_url(
        build_8k_filings_feed_url(cik, count=count),
        user_agent=user_agent,
        timeout_seconds=timeout_seconds,
    )

    return parse_filings_atom(atom_bytes)


def parse_filings_atom(atom_bytes):
    """
    Aplatit le flux Atom EDGAR (browse-edgar ... output=atom) en une
    liste de dicts : accession_number, filing_date, form_type,
    item_codes, filing_index_url.
    """

    root = ElementTree.fromstring(atom_bytes)

    filings = []

    for entry in root.findall(f"{ATOM_NS}entry"):

        content = entry.find(f"{ATOM_NS}content")

        if content is None:
            continue

        accession_el = content.find(f"{ATOM_NS}accession-number")
        date_el = content.find(f"{ATOM_NS}filing-date")
        type_el = content.find(f"{ATOM_NS}filing-type")
        items_el = content.find(f"{ATOM_NS}items-desc")
        href_el = content.find(f"{ATOM_NS}filing-href")

        filings.append(
            {
                "accession_number": (
                    accession_el.text if accession_el is not None else None
                ),
                "filing_date": date_el.text if date_el is not None else None,
                "form_type": type_el.text if type_el is not None else None,
                "item_codes": items_el.text if items_el is not None else "",
                "filing_index_url": (
                    href_el.text if href_el is not None else None
                ),
            }
        )

    return filings


def filter_candidate_filings(filings):
    """
    Garde les dépôts dont le texte des items mentionne au moins un des
    codes susceptibles d'annoncer un placement de warrants (1.01, 3.02).
    """

    return [
        filing
        for filing in filings
        if any(
            code in (filing.get("item_codes") or "")
            for code in WARRANT_ITEM_CODES
        )
    ]


class _DocumentTableParser(HTMLParser):
    """
    Parse la table "Document Format Files" d'une page d'index EDGAR
    (class="tableFile") en lignes (seq, description, filename, href,
    exhibit_type, size) — colonnes : Seq | Description | Document | Type
    | Size.
    """

    def __init__(self):
        super().__init__()
        self._in_table = False
        self._table_depth = 0
        self._in_row = False
        self._current_cells = []
        self._current_cell_text = []
        self._current_href = None
        self.rows = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)

        if tag == "table" and "tableFile" in (attrs_dict.get("class") or ""):
            self._in_table = True
            return

        if not self._in_table:
            return

        if tag == "tr":
            self._in_row = True
            self._current_cells = []
        elif tag == "td" and self._in_row:
            self._current_cell_text = []
            self._current_href = None
        elif tag == "a" and self._in_row:
            self._current_href = attrs_dict.get("href")

    def handle_data(self, data):
        if self._in_table and self._in_row:
            self._current_cell_text.append(data)

    def handle_endtag(self, tag):
        if tag == "table" and self._in_table:
            self._in_table = False
            return

        if not self._in_table:
            return

        if tag == "td" and self._in_row:
            text = "".join(self._current_cell_text).strip()
            self._current_cells.append((text, self._current_href))
        elif tag == "tr" and self._in_row:
            self._in_row = False
            if self._current_cells:
                self.rows.append(self._current_cells)


def parse_filing_index_documents(index_html_bytes):
    """
    Parse la page d'index d'un filing EDGAR en une liste de documents :
    seq, description, filename, url, exhibit_type, size.

    Ignore la ligne d'en-tête (Seq/Description/Document/Type/Size) et
    toute ligne sans lien de document exploitable.
    """

    parser = _DocumentTableParser()
    parser.feed(index_html_bytes.decode("utf-8", errors="replace"))

    documents = []

    for row in parser.rows:

        if len(row) < 5:
            continue

        seq_text, _ = row[0]
        description, _ = row[1]
        filename, href = row[2]
        exhibit_type, _ = row[3]
        size_text, _ = row[4]

        if href is None or not seq_text.isdigit():
            continue

        url = href

        # Documents with inline XBRL link to the interactive viewer
        # ("/ix?doc=/Archives/...") rather than the raw document — unwrap
        # it so callers always get the actual document, not the viewer
        # shell page.
        ix_doc_prefix = "/ix?doc="
        if url.startswith(ix_doc_prefix):
            url = url[len(ix_doc_prefix):]

        if url.startswith("/"):
            url = f"https://www.sec.gov{url}"

        documents.append(
            {
                "seq": int(seq_text),
                "description": description,
                "filename": filename,
                "url": url,
                "exhibit_type": exhibit_type,
                "size": size_text,
            }
        )

    return documents


def filter_warrant_exhibits(documents):
    """Garde les documents dont la description mentionne "warrant"."""

    return [
        document
        for document in documents
        if WARRANT_DESCRIPTION_PATTERN.search(document.get("description") or "")
    ]


def find_main_document(documents):
    """
    Retourne le document principal d'un filing (celui qui n'est pas un
    exhibit numéroté EX-x.x) — typiquement celui avec le plus petit
    "seq" (habituellement 1). Retourne None si aucun document non-exhibit
    n'est trouvé.

    C'est ce document, et non les exhibits "FORM OF ... WARRANT", qui
    porte les modalités réelles d'un placement de warrants (voir
    sec_8k_warrant_text_extraction.py) — les exhibits sont des gabarits
    avec des blancs.
    """

    non_exhibit_docs = [
        document
        for document in documents
        if not (document.get("exhibit_type") or "").upper().startswith("EX-")
    ]

    if not non_exhibit_docs:
        return None

    return min(non_exhibit_docs, key=lambda document: document["seq"])


def discover_warrant_exhibits_for_cik(cik, *, user_agent, timeout_seconds=30):
    """
    Pour un CIK : liste les 8-K, filtre ceux dont les items évoquent un
    placement (1.01/3.02), ouvre leur index et garde les exhibits dont
    la description mentionne "warrant".

    Retourne une liste de dicts prêts à persister (voir
    warrants_postgresql.write_sec_8k_warrant_exhibits), un par exhibit
    candidat trouvé.
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
        warrant_exhibits = filter_warrant_exhibits(documents)

        for exhibit in warrant_exhibits:

            results.append(
                {
                    "accession_number": filing["accession_number"],
                    "filing_date": filing["filing_date"],
                    "form_type": filing["form_type"],
                    "item_codes": filing["item_codes"],
                    "filing_index_url": index_url,
                    "exhibit_seq": exhibit["seq"],
                    "exhibit_type": exhibit["exhibit_type"],
                    "description": exhibit["description"],
                    "document_url": exhibit["url"],
                }
            )

    return results
