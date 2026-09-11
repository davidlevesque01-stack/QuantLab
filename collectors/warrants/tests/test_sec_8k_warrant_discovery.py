from unittest.mock import patch

from collectors.warrants.src.sec_8k_warrant_discovery import (
    discover_warrant_exhibits_for_cik,
    filter_candidate_filings,
    filter_warrant_exhibits,
    parse_filing_index_documents,
    parse_filings_atom,
)


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
  <entry>
    <content type="text/xml">
      <accession-number>0001213900-26-098232</accession-number>
      <filing-date>2026-09-09</filing-date>
      <filing-href>https://www.sec.gov/Archives/edgar/data/1560293/000121390026098232/0001213900-26-098232-index.htm</filing-href>
      <filing-type>8-K</filing-type>
      <items-desc>items 8.01 and 9.01</items-desc>
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
<tr class="evenRow">
<td scope="row">2</td>
<td scope="row">PLACEMENT AGENCY AGREEMENT DATED AUGUST 27, 2026</td>
<td scope="row"><a href="/Archives/edgar/data/1560293/x/ea030388301ex1-1.htm">ea030388301ex1-1.htm</a></td>
<td scope="row">EX-1.1</td>
<td scope="row">82673</td>
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


def test_parse_filings_atom_extracts_expected_fields():
    filings = parse_filings_atom(SAMPLE_ATOM)

    assert len(filings) == 2
    assert filings[0]["accession_number"] == "0001213900-26-095686"
    assert filings[0]["filing_date"] == "2026-08-31"
    assert filings[0]["form_type"] == "8-K"
    assert "1.01" in filings[0]["item_codes"]


def test_filter_candidate_filings_keeps_only_1_01_or_3_02():
    filings = parse_filings_atom(SAMPLE_ATOM)

    candidates = filter_candidate_filings(filings)

    assert len(candidates) == 1
    assert candidates[0]["accession_number"] == "0001213900-26-095686"


def test_parse_filing_index_documents_skips_header_and_resolves_urls():
    documents = parse_filing_index_documents(SAMPLE_INDEX_HTML)

    assert len(documents) == 3
    assert documents[0]["seq"] == 1
    assert documents[2]["description"] == "FORM OF PRE-FUNDED WARRANT"
    assert documents[2]["url"] == (
        "https://www.sec.gov/Archives/edgar/data/1560293/x/ea030388301ex4-1.htm"
    )
    assert documents[2]["exhibit_type"] == "EX-4.1"


def test_filter_warrant_exhibits_keeps_only_warrant_descriptions():
    documents = parse_filing_index_documents(SAMPLE_INDEX_HTML)

    warrant_exhibits = filter_warrant_exhibits(documents)

    assert len(warrant_exhibits) == 1
    assert warrant_exhibits[0]["description"] == "FORM OF PRE-FUNDED WARRANT"


def test_discover_warrant_exhibits_for_cik_combines_discovery_steps():
    with patch(
        "collectors.warrants.src.sec_8k_warrant_discovery.fetch_8k_filings",
        return_value=parse_filings_atom(SAMPLE_ATOM),
    ), patch(
        "collectors.warrants.src.sec_8k_warrant_discovery.fetch_url",
        return_value=SAMPLE_INDEX_HTML,
    ) as mocked_fetch_url:

        results = discover_warrant_exhibits_for_cik(
            "0001560293",
            user_agent="QuantLab test contact@example.com",
        )

    assert len(results) == 1
    assert results[0]["accession_number"] == "0001213900-26-095686"
    assert results[0]["description"] == "FORM OF PRE-FUNDED WARRANT"
    assert results[0]["exhibit_seq"] == 3
    # Only the candidate filing's index should have been fetched, not the
    # non-candidate one.
    mocked_fetch_url.assert_called_once()
