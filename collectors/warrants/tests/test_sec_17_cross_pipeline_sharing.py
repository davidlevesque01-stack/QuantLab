"""
SEC-17 : tests d'intégration légère confirmant le bénéfice réel visé —
plusieurs pipelines de découverte qui traitent le même filing candidat
(items 1.01/3.02) ne doivent PAS refaire chacun la même requête réseau
quand ils partagent un `SharedFetchCache`.
"""

from unittest.mock import patch

from collectors.warrants.src.sec_8k_warrant_discovery import (
    discover_warrant_exhibits_for_cik,
    parse_filings_atom,
)
from collectors.warrants.src.sec_8k_warrant_text_extraction import (
    discover_and_extract_warrant_terms_for_cik,
)
from collectors.warrants.src.sec_fetch_cache import SharedFetchCache


SAMPLE_ATOM = b"""<?xml version="1.0" encoding="ISO-8859-1" ?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <content type="text/xml">
      <accession-number>0001213900-26-095686</accession-number>
      <filing-date>2026-08-31</filing-date>
      <filing-href>https://www.sec.gov/Archives/edgar/data/1560293/000121390026095686/0001213900-26-095686-index.htm</filing-href>
      <filing-type>8-K</filing-type>
      <items-desc>items 1.01, 3.02, 8.01and9.01</items-desc>
    </content>
  </entry>
</feed>
"""

SAMPLE_INDEX_HTML = b"""<html><body>
<table class="tableFile" summary="Document Format Files">
<tr><th>Seq</th><th>Description</th><th>Document</th><th>Type</th><th>Size</th></tr>
<tr>
<td scope="row">1</td>
<td scope="row">CURRENT REPORT</td>
<td scope="row"><a href="/Archives/edgar/data/1560293/x/ea0303883-8k_tenon.htm">ea0303883-8k_tenon.htm</a></td>
<td scope="row">8-K</td>
<td scope="row">45377</td>
</tr>
<tr>
<td scope="row">3</td>
<td scope="row">FORM OF PRE-FUNDED WARRANT</td>
<td scope="row"><a href="/Archives/edgar/data/1560293/x/ea030388301ex4-1.htm">ea030388301ex4-1.htm</a></td>
<td scope="row">EX-4.1</td>
<td scope="row">88886</td>
</tr>
</table>
</body></html>
"""

SAMPLE_8K_BODY_HTML = (
    "<html><body><p>Item 1.01. Series A warrants to purchase up to an "
    "aggregate of 1,058,517 shares of Common Stock. Each Series A "
    "Warrant has an exercise price of $5.02 per share. The Series A "
    "Warrants are immediately exercisable and will expire five (5) "
    "years from issuance.</p></body></html>"
).encode("utf-8")


def test_exhibits_and_text_extraction_pipelines_share_one_index_fetch():
    """
    Both pipelines filter on the same items 1.01/3.02 candidate and, for
    this shared candidate, both need the filing's index page. With a
    shared `fetch_cache`, that index page is fetched over the network
    only once across both pipeline calls combined — before SEC-17, each
    pipeline fetched it independently (2x the same request).
    """

    filings = parse_filings_atom(SAMPLE_ATOM)
    cache = SharedFetchCache()

    with patch(
        "collectors.warrants.src.sec_8k_warrant_discovery.fetch_url",
        return_value=SAMPLE_INDEX_HTML,
    ) as mocked_exhibits_fetch_url, patch(
        "collectors.warrants.src.sec_8k_warrant_text_extraction.fetch_url",
        return_value=SAMPLE_INDEX_HTML,
    ) as mocked_text_extraction_fetch_url, patch(
        "collectors.warrants.src.sec_8k_warrant_text_extraction.fetch_document_text",
        return_value=SAMPLE_8K_BODY_HTML.decode("utf-8"),
    ):

        exhibit_results = discover_warrant_exhibits_for_cik(
            "0001560293",
            user_agent="QuantLab test contact@example.com",
            filings=filings,
            fetch_cache=cache,
        )
        text_results = discover_and_extract_warrant_terms_for_cik(
            "0001560293",
            user_agent="QuantLab test contact@example.com",
            filings=filings,
            fetch_cache=cache,
        )

    assert len(exhibit_results) == 1
    assert len(text_results) == 3  # share_quantity + exercise_price + expiration_years

    # The index page is the same URL for both pipelines (same filing) --
    # fetched once total, not once per pipeline.
    assert mocked_exhibits_fetch_url.call_count == 1
    assert mocked_text_extraction_fetch_url.call_count == 0
