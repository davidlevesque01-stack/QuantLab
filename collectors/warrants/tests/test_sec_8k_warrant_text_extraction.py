from unittest.mock import patch

from collectors.warrants.src.sec_8k_warrant_text_extraction import (
    discover_and_extract_warrant_terms_for_cik,
    extract_exercise_prices,
    extract_expiration_terms,
    extract_warrant_quantities,
    extract_warrant_terms,
    fetch_document_text,
    strip_html_to_text,
)


# Real excerpt fetched from TNON's 8-K (accession 0001213900-26-095686,
# ea0303883-8k_tenon.htm), Item 1.01, after stripping HTML — used
# verbatim as a regression fixture since the extraction was designed and
# validated against this exact real filing.
REAL_TNON_8K_EXCERPT = (
    "private placement (the “ Private Placement ”) of (i) "
    "pre-funded warrants (the “ Pre-Funded Warrants ”) to "
    "purchase up to an aggregate of 597,610 shares (the “ "
    "Pre-Funded Warrant Shares ”) of the Company’s common "
    "stock, par value $0.001 per share (the “ Common Stock ”), "
    "at a purchase price of $5.019 per Pre-Funded Warrant, and (ii) "
    "Series A warrants to purchase up to an aggregate of 1,058,517 "
    "shares of Common Stock (the “ Series A Warrants ,” and "
    "the shares issuable upon exercise thereof, the “ Series A "
    "Warrant Shares ”). The Private Placement closed on August 31, "
    "2026. The Company received gross proceeds of $2,999,404.59 (which "
    "does not include $597.61 that the Company may receive from the "
    "Purchaser upon exercise of the Pre-Funded Warrants) from the "
    "Private Placement. Each Series A Warrant has an exercise price of "
    "$5.02 per share. The Series A Warrants are immediately exercisable "
    "and will expire five (5) years from issuance. A holder may not "
    "exercise any portion of the Series A Warrants to the extent the "
    "Purchaser would own more than 4.99% of the outstanding Common "
    "Stock immediately after exercise. ... The Pre-Funded Warrants are "
    "immediately exercisable and may be exercised at a nominal exercise "
    "price of $0.001 per share of Common Stock at any time until all of "
    "the Pre-Funded Warrants are exercised in full."
)


def test_strip_html_to_text_removes_tags_and_entities():
    html = "<p>Exercise&nbsp;Price:&#160;<b>$5.02</b></p>"

    assert strip_html_to_text(html) == "Exercise Price: $5.02"


def test_extract_warrant_quantities_finds_both_series():
    results = extract_warrant_quantities(REAL_TNON_8K_EXCERPT)

    quantities = {item["share_quantity"] for item in results}
    assert 1058517 in quantities
    assert 597610 in quantities

    series_a = next(item for item in results if item["share_quantity"] == 1058517)
    assert "series a" in series_a["label"].lower()


def test_extract_exercise_prices_finds_series_a_and_nominal_pre_funded():
    results = extract_exercise_prices(REAL_TNON_8K_EXCERPT)

    prices = {item["exercise_price"] for item in results}
    assert 5.02 in prices
    assert 0.001 in prices

    pre_funded = next(item for item in results if item["exercise_price"] == 0.001)
    assert pre_funded["label"] == "Pre-Funded Warrant"


def test_extract_expiration_terms_finds_five_years():
    results = extract_expiration_terms(REAL_TNON_8K_EXCERPT)

    assert len(results) == 1
    assert results[0]["expiration_years"] == 5


def test_extract_warrant_terms_combines_all_kinds():
    observations = extract_warrant_terms(REAL_TNON_8K_EXCERPT)

    kinds = {observation["kind"] for observation in observations}
    assert kinds == {"share_quantity", "exercise_price", "expiration_years"}
    assert len(observations) == 5  # 2 quantities + 2 prices + 1 expiration


def test_fetch_document_text_strips_and_decodes():
    with patch(
        "collectors.warrants.src.sec_8k_warrant_text_extraction.fetch_url",
        return_value="<p>Exercise Price: $5.02</p>".encode("utf-8"),
    ) as mocked_fetch:

        text = fetch_document_text(
            "https://www.sec.gov/example.htm",
            user_agent="QuantLab test contact@example.com",
            timeout_seconds=9,
        )

    assert text == "Exercise Price: $5.02"
    mocked_fetch.assert_called_once_with(
        "https://www.sec.gov/example.htm",
        user_agent="QuantLab test contact@example.com",
        timeout_seconds=9,
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
    "<html><body><p>Item 1.01. "
    "Series A warrants to purchase up to an aggregate of 1,058,517 "
    "shares of Common Stock. Each Series A Warrant has an exercise "
    "price of $5.02 per share. The Series A Warrants are immediately "
    "exercisable and will expire five (5) years from issuance."
    "</p></body></html>"
).encode("utf-8")


def test_discover_and_extract_warrant_terms_for_cik_uses_main_document():
    with patch(
        "collectors.warrants.src.sec_8k_warrant_text_extraction.fetch_all_8k_filings",
        return_value=[
            {
                "accession_number": "0001213900-26-095686",
                "filing_date": "2026-08-31",
                "form_type": "8-K",
                "item_codes": "items 1.01, 3.02, 8.01and9.01",
                "filing_index_url": "https://www.sec.gov/index.htm",
            }
        ],
    ), patch(
        "collectors.warrants.src.sec_8k_warrant_text_extraction.fetch_url",
        side_effect=[SAMPLE_INDEX_HTML, SAMPLE_8K_BODY_HTML],
    ) as mocked_fetch_url:

        results = discover_and_extract_warrant_terms_for_cik(
            "0001560293",
            user_agent="QuantLab test contact@example.com",
        )

    assert mocked_fetch_url.call_count == 2
    # First call fetches the filing index, second fetches the MAIN
    # document (ea0303883-8k_tenon.htm) — never the EX-4.1 exhibit.
    fetched_urls = [call.args[0] for call in mocked_fetch_url.call_args_list]
    assert fetched_urls[1].endswith("ea0303883-8k_tenon.htm")

    kinds = {observation["kind"] for observation in results}
    assert kinds == {"share_quantity", "exercise_price", "expiration_years"}
    assert all(
        observation["filed_date"] == "2026-08-31"
        and observation["form_type"] == "8-K"
        for observation in results
    )
    assert all(
        observation["accession_number"] == "0001213900-26-095686"
        for observation in results
    )
