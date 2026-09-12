from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from collectors.warrants.src.sec_8k_warrant_discovery import (
    DEFAULT_PAGE_SIZE,
    build_8k_filings_feed_url,
    discover_warrant_exhibits_for_cik,
    fetch_8k_filings,
    fetch_all_8k_filings,
    fetch_url,
    filter_candidate_filings,
    filter_warrant_exhibits,
    find_main_document,
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
<td scope="row"><a href="/ix?doc=/Archives/edgar/data/1560293/x/ea0303883-8k_tenon.htm">ea0303883-8k_tenon.htm &#160;&#160;<span style="color: green">iXBRL</span></a></td>
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
    assert warrant_exhibits[0]["match_reason"] == "description+exhibit_type"


def test_filter_warrant_exhibits_falls_back_to_exhibit_type_code():
    """
    SEC-13 regression: a filer (e.g. GPUS) that never writes a
    descriptive exhibit title ("EXHIBIT 4.1" instead of "FORM OF
    PRE-FUNDED WARRANT") must still be caught, via the EX-4.x exhibit
    type code alone (Item 601(b)(4) of Regulation S-K).
    """

    documents = [
        {"seq": 1, "exhibit_type": "8-K", "description": "CURRENT REPORT", "url": "a"},
        {"seq": 2, "exhibit_type": "EX-1.1", "description": "AGENCY AGREEMENT", "url": "b"},
        {"seq": 3, "exhibit_type": "EX-4.1", "description": "EXHIBIT 4.1", "url": "c"},
    ]

    warrant_exhibits = filter_warrant_exhibits(documents)

    assert len(warrant_exhibits) == 1
    assert warrant_exhibits[0]["description"] == "EXHIBIT 4.1"
    assert warrant_exhibits[0]["match_reason"] == "exhibit_type"


def test_filter_warrant_exhibits_matches_description_without_ex4_type():
    """
    A description-only match (e.g. a warrant referenced under a
    non-EX-4 exhibit type) is still kept, tagged with its own reason.
    """

    documents = [
        {"seq": 4, "exhibit_type": "EX-10.1", "description": "WARRANT AGREEMENT", "url": "d"},
    ]

    warrant_exhibits = filter_warrant_exhibits(documents)

    assert len(warrant_exhibits) == 1
    assert warrant_exhibits[0]["match_reason"] == "description"


def test_discover_warrant_exhibits_for_cik_combines_discovery_steps():
    with patch(
        "collectors.warrants.src.sec_8k_warrant_discovery.fetch_all_8k_filings",
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
    assert results[0]["match_reason"] == "description+exhibit_type"
    # Only the candidate filing's index should have been fetched, not the
    # non-candidate one.
    mocked_fetch_url.assert_called_once()


def test_build_8k_filings_feed_url_includes_start_param():
    url = build_8k_filings_feed_url("0001560293", count=100, start=200)

    assert "count=100" in url
    assert "start=200" in url


def test_fetch_all_8k_filings_stops_on_short_page():
    """
    A single page shorter than page_size means we've reached the end of
    the filer's history — no further page should be requested.
    """

    with patch(
        "collectors.warrants.src.sec_8k_warrant_discovery.fetch_8k_filings",
        return_value=parse_filings_atom(SAMPLE_ATOM),
    ) as mocked_fetch:

        filings = fetch_all_8k_filings(
            "0001560293",
            user_agent="QuantLab test contact@example.com",
            page_size=DEFAULT_PAGE_SIZE,
        )

    assert len(filings) == 2
    mocked_fetch.assert_called_once_with(
        "0001560293",
        user_agent="QuantLab test contact@example.com",
        timeout_seconds=30,
        count=DEFAULT_PAGE_SIZE,
        start=0,
    )


def test_fetch_all_8k_filings_paginates_across_full_pages():
    """
    SEC-12: a high-frequency filer (e.g. GPUS) whose full history spans
    more than one page must have every page fetched, walking `start`
    forward by `page_size` each time, until a short (or empty) page ends
    the walk.
    """

    full_page = parse_filings_atom(SAMPLE_ATOM) * 1  # 2 entries
    # Simulate page_size=2: first two pages full, third page short (0).
    with patch(
        "collectors.warrants.src.sec_8k_warrant_discovery.fetch_8k_filings",
        side_effect=[full_page, full_page, []],
    ) as mocked_fetch:

        filings = fetch_all_8k_filings(
            "0001560293",
            user_agent="QuantLab test contact@example.com",
            page_size=2,
        )

    assert len(filings) == 4
    assert mocked_fetch.call_count == 3
    assert mocked_fetch.call_args_list[0].kwargs["start"] == 0
    assert mocked_fetch.call_args_list[1].kwargs["start"] == 2
    assert mocked_fetch.call_args_list[2].kwargs["start"] == 4


def test_fetch_all_8k_filings_respects_max_pages_guard():
    full_page = parse_filings_atom(SAMPLE_ATOM)  # 2 entries, == page_size

    with patch(
        "collectors.warrants.src.sec_8k_warrant_discovery.fetch_8k_filings",
        return_value=full_page,
    ) as mocked_fetch:

        filings = fetch_all_8k_filings(
            "0001560293",
            user_agent="QuantLab test contact@example.com",
            page_size=2,
            max_pages=3,
        )

    assert mocked_fetch.call_count == 3
    assert len(filings) == 6


def test_find_main_document_skips_numbered_exhibits():
    documents = parse_filing_index_documents(SAMPLE_INDEX_HTML)

    main_document = find_main_document(documents)

    assert main_document["seq"] == 1
    assert main_document["exhibit_type"] == "8-K"
    assert main_document["description"] == "CURRENT REPORT"


def test_parse_filing_index_documents_unwraps_ixbrl_viewer_url():
    """
    Regression test: a document with inline XBRL links to the
    interactive viewer ("/ix?doc=/Archives/...") in the filing index,
    not the raw document. Fetching that viewer URL directly does not
    return the document's own text (it's a JS-rendered shell page), so
    it must be unwrapped to the real document URL — this broke SEC-10's
    text extraction in production (silently returned zero results)
    before being caught and fixed.
    """

    documents = parse_filing_index_documents(SAMPLE_INDEX_HTML)

    main_document = find_main_document(documents)

    assert main_document["url"] == (
        "https://www.sec.gov/Archives/edgar/data/1560293/x/ea0303883-8k_tenon.htm"
    )
    assert "/ix?doc=" not in main_document["url"]


def test_find_main_document_returns_none_when_only_exhibits():
    documents = [
        {"seq": 2, "exhibit_type": "EX-1.1", "description": "AGREEMENT", "url": "x"},
        {"seq": 3, "exhibit_type": "EX-4.1", "description": "FORM OF WARRANT", "url": "y"},
    ]

    assert find_main_document(documents) is None


def _http_error(code):
    return HTTPError("https://www.sec.gov/x", code, "error", {}, None)


def test_fetch_url_retries_on_503_then_succeeds():
    mock_response = MagicMock()
    mock_response.read.return_value = b"ok"
    mock_response.__enter__.return_value = mock_response

    with patch(
        "collectors.warrants.src.sec_8k_warrant_discovery.urlopen",
        side_effect=[_http_error(503), mock_response],
    ) as mocked_urlopen, patch(
        "collectors.warrants.src.sec_8k_warrant_discovery.time.sleep",
    ) as mocked_sleep:

        result = fetch_url(
            "https://www.sec.gov/x",
            user_agent="QuantLab test contact@example.com",
            max_retries=3,
            retry_delay_seconds=1,
        )

    assert result == b"ok"
    assert mocked_urlopen.call_count == 2
    mocked_sleep.assert_called_once()


def test_fetch_url_does_not_retry_on_404():
    with patch(
        "collectors.warrants.src.sec_8k_warrant_discovery.urlopen",
        side_effect=_http_error(404),
    ) as mocked_urlopen:

        try:
            fetch_url(
                "https://www.sec.gov/x",
                user_agent="QuantLab test contact@example.com",
                max_retries=3,
            )
            assert False, "expected HTTPError to propagate"
        except HTTPError as error:
            assert error.code == 404

    mocked_urlopen.assert_called_once()


def test_fetch_url_raises_after_exhausting_retries():
    with patch(
        "collectors.warrants.src.sec_8k_warrant_discovery.urlopen",
        side_effect=_http_error(503),
    ) as mocked_urlopen, patch(
        "collectors.warrants.src.sec_8k_warrant_discovery.time.sleep",
    ):

        try:
            fetch_url(
                "https://www.sec.gov/x",
                user_agent="QuantLab test contact@example.com",
                max_retries=2,
                retry_delay_seconds=0,
            )
            assert False, "expected HTTPError to propagate"
        except HTTPError as error:
            assert error.code == 503

    assert mocked_urlopen.call_count == 3


def test_fetch_url_retries_on_url_error():
    mock_response = MagicMock()
    mock_response.read.return_value = b"ok"
    mock_response.__enter__.return_value = mock_response

    with patch(
        "collectors.warrants.src.sec_8k_warrant_discovery.urlopen",
        side_effect=[URLError("connection reset"), mock_response],
    ) as mocked_urlopen, patch(
        "collectors.warrants.src.sec_8k_warrant_discovery.time.sleep",
    ):

        result = fetch_url(
            "https://www.sec.gov/x",
            user_agent="QuantLab test contact@example.com",
            max_retries=3,
        )

    assert result == b"ok"
    assert mocked_urlopen.call_count == 2


def test_fetch_url_retries_on_timeout_error():
    """
    Regression test: TimeoutError (raised directly by the ssl/socket
    layer on a read timeout, observed in production on TNON,
    2026-09-11) is an OSError but NOT a URLError subclass — it slipped
    through the original except URLError clause silently uncaught by
    the retry logic before this was caught and fixed.
    """

    mock_response = MagicMock()
    mock_response.read.return_value = b"ok"
    mock_response.__enter__.return_value = mock_response

    with patch(
        "collectors.warrants.src.sec_8k_warrant_discovery.urlopen",
        side_effect=[TimeoutError("The read operation timed out"), mock_response],
    ) as mocked_urlopen, patch(
        "collectors.warrants.src.sec_8k_warrant_discovery.time.sleep",
    ):

        result = fetch_url(
            "https://www.sec.gov/x",
            user_agent="QuantLab test contact@example.com",
            max_retries=3,
        )

    assert result == b"ok"
    assert mocked_urlopen.call_count == 2
