from unittest.mock import patch

from collectors.warrants.src.sec_reverse_split_extraction import (
    discover_and_extract_reverse_splits_for_cik,
    extract_reverse_split,
    filter_split_candidate_filings,
)


# Real excerpt fetched from TNON's 8-K (accession 0001213900-26-087352,
# ea0301424-8k_tenon.htm, filed 2026-08-10, items 3.03/5.03/7.01/9.01),
# after stripping HTML — used verbatim since this extractor was designed
# and validated against this exact real filing, and independently
# confirms the ~35x ratio already deduced by comparing raw warrant data
# against DilutionTracker (SEC-11).
REAL_TNON_SPLIT_8K_EXCERPT = (
    "On August 6, 2026, Tenon Medical, Inc., a Delaware corporation "
    "(the “Company”), filed a Certificate of Amendment to the "
    "Company’s Second Amended and Restated Certificate of "
    "Incorporation (the “Certificate of Amendment”) with the "
    "Secretary of State of Delaware to effect a 1-for-35 reverse stock "
    "split of the shares of the Company’s common stock, par value "
    "$0.001 per share (the “Common Stock”), issued and "
    "outstanding, effective as of 12:01 a.m. Eastern Time on August 10, "
    "2026 (the “Reverse Stock Split”). As previously reported "
    "by the Company, at the Company’s 2026 Annual Meeting of "
    "Stockholders held on July 23, 2026, the Company’s "
    "stockholders approved the amendment ... to effect a reverse stock "
    "split of the Company’s Common Stock at a ratio within the "
    "range of 1-for-2 to 1-for-35, with such ratio to be determined by "
    "the Company’s Board of Directors (the “Board”). "
    "Following the stockholder approval, the Board determined to "
    "effect the Reverse Stock Split at a ratio of 1-for-35 and approved "
    "the corresponding final form of the Certificate of Amendment. As "
    "a result of the Reverse Stock Split, every thirty-five (35) "
    "shares of issued and outstanding Common Stock were automatically "
    "combined into one (1) issued and outstanding share of Common "
    "Stock."
)


def test_extract_reverse_split_finds_ratio_and_date():
    result = extract_reverse_split(REAL_TNON_SPLIT_8K_EXCERPT)

    assert result is not None
    assert result["ratio_new"] == 1
    assert result["ratio_old"] == 35
    assert result["effective_date"] == "2026-08-10"
    assert "1-for-35" in result["raw_snippet"]


def test_extract_reverse_split_uses_first_ratio_mention():
    """
    The excerpt mentions "1-for-35" three times (the actual effected
    ratio) plus a range "1-for-2 to 1-for-35" (the board's authorized
    range, not the ratio actually used). The first regex match in
    document order is the actually-effected ratio, which happens to
    come before the range mention in this real filing — confirms we
    don't accidentally pick up "1-for-2" from the range.
    """

    result = extract_reverse_split(REAL_TNON_SPLIT_8K_EXCERPT)

    assert result["ratio_old"] == 35


def test_extract_reverse_split_returns_none_when_no_ratio_found():
    assert extract_reverse_split("Item 5.03. Some unrelated amendment.") is None


# Real excerpt fetched from TNON's 8-K (accession 0001213900-23-084331,
# ea187680-8k_tenonmed.htm, filed 2023-11-07) — SEC-16 regression fixture:
# this filing's "became effective at ... on <date>" phrasing (no "as of")
# was invisible to the original EFFECTIVE_DATE_PATTERN, even though the
# ratio itself was always extracted correctly (only effective_date was
# NULL). Found via SEC-12's full-history pagination.
REAL_TNON_2023_SPLIT_8K_EXCERPT = (
    "Tenon Medical, Inc. (the “Company”) filed on November 1, 2023 a "
    "Certificate of Amendment to the Second Amended and Restated "
    "Certificate of Incorporation of the Company with the Secretary of "
    "State of the State of Delaware (the “Certificate of Amendment”) "
    "that provides for a 1-for-10 reverse stock split (the “Split”) of "
    "its shares of common stock, par value $0.001 per share (the "
    "“Common Stock”) that became effective at 12:01 a.m. on "
    "November 2, 2023."
)


# Real excerpt fetched from GPUS's 8-K (accession 0001214659-19-002112,
# p3141908k.htm, filed 2019-03-14) — SEC-16 regression fixture: the
# "became effective in the State of Delaware on <date>" phrasing has an
# intervening clause between "effective" and "on <date>", also invisible
# to the original pattern. The digit-format ratio ("1-for-20") and the
# effective-date sentence are far apart in the real document (exhibit
# index vs. body) — combined here with "..." exactly as the existing
# TNON fixture above does, both pieces quoted verbatim from the real
# filing.
REAL_GPUS_2019_SPLIT_8K_EXCERPT = (
    "The Company filed a Certificate of Amendment to its Certificate of "
    "Incorporation with the State of Delaware effectuating the Reverse "
    "Stock Split on March 14, 2019. The Certificate became effective in "
    "the State of Delaware on March 14, 2019. ... Exhibit No. "
    "Description 3.1 Certificate of Amendment to Certificate of "
    "Incorporation (1-for-20 Reverse Stock Split of Common Stock) filed "
    "with the Delaware Secretary of State on March 14, 2019."
)


def test_extract_reverse_split_finds_became_effective_at_phrasing():
    result = extract_reverse_split(REAL_TNON_2023_SPLIT_8K_EXCERPT)

    assert result is not None
    assert result["ratio_new"] == 1
    assert result["ratio_old"] == 10
    assert result["effective_date"] == "2023-11-02"


def test_extract_reverse_split_finds_became_effective_in_state_phrasing():
    result = extract_reverse_split(REAL_GPUS_2019_SPLIT_8K_EXCERPT)

    assert result is not None
    assert result["ratio_new"] == 1
    assert result["ratio_old"] == 20
    assert result["effective_date"] == "2019-03-14"


def test_filter_split_candidate_filings_keeps_only_3_03_or_5_03():
    filings = [
        {"accession_number": "A", "item_codes": "items 3.03, 5.03, 7.01and9.01"},
        {"accession_number": "B", "item_codes": "items 1.01, 3.02, 8.01and9.01"},
        {"accession_number": "C", "item_codes": "items 8.01 and 9.01"},
    ]

    candidates = filter_split_candidate_filings(filings)

    assert [f["accession_number"] for f in candidates] == ["A"]


def test_discover_and_extract_reverse_splits_for_cik_end_to_end():
    with patch(
        "collectors.warrants.src.sec_reverse_split_extraction.fetch_all_8k_filings",
        return_value=[
            {
                "accession_number": "0001213900-26-087352",
                "filing_date": "2026-08-10",
                "form_type": "8-K",
                "item_codes": "items 3.03, 5.03, 7.01and9.01",
                "filing_index_url": "https://www.sec.gov/index.htm",
            }
        ],
    ), patch(
        "collectors.warrants.src.sec_reverse_split_extraction.fetch_url",
        return_value=(
            b"<html><body><table class=\"tableFile\" summary=\"Document Format Files\">"
            b"<tr><th>Seq</th><th>Description</th><th>Document</th><th>Type</th><th>Size</th></tr>"
            b"<tr><td scope=\"row\">1</td><td scope=\"row\">CURRENT REPORT</td>"
            b"<td scope=\"row\"><a href=\"/Archives/edgar/data/x/8k.htm\">8k.htm</a></td>"
            b"<td scope=\"row\">8-K</td><td scope=\"row\">1</td></tr>"
            b"</table></body></html>"
        ),
    ), patch(
        "collectors.warrants.src.sec_reverse_split_extraction.fetch_document_text",
        return_value=REAL_TNON_SPLIT_8K_EXCERPT,
    ):

        results = discover_and_extract_reverse_splits_for_cik(
            "0001560293",
            user_agent="QuantLab test contact@example.com",
        )

    assert len(results) == 1
    assert results[0]["accession_number"] == "0001213900-26-087352"
    assert results[0]["filed_date"] == "2026-08-10"
    assert results[0]["ratio_new"] == 1
    assert results[0]["ratio_old"] == 35
    assert results[0]["effective_date"] == "2026-08-10"


def test_discover_and_extract_reverse_splits_skips_filings_without_a_ratio():
    with patch(
        "collectors.warrants.src.sec_reverse_split_extraction.fetch_all_8k_filings",
        return_value=[
            {
                "accession_number": "0001213900-26-000001",
                "filing_date": "2026-01-01",
                "form_type": "8-K",
                "item_codes": "items 3.03, 9.01",
                "filing_index_url": "https://www.sec.gov/index.htm",
            }
        ],
    ), patch(
        "collectors.warrants.src.sec_reverse_split_extraction.fetch_url",
        return_value=(
            b"<html><body><table class=\"tableFile\" summary=\"Document Format Files\">"
            b"<tr><th>Seq</th><th>Description</th><th>Document</th><th>Type</th><th>Size</th></tr>"
            b"<tr><td scope=\"row\">1</td><td scope=\"row\">CURRENT REPORT</td>"
            b"<td scope=\"row\"><a href=\"/Archives/edgar/data/x/8k.htm\">8k.htm</a></td>"
            b"<td scope=\"row\">8-K</td><td scope=\"row\">1</td></tr>"
            b"</table></body></html>"
        ),
    ), patch(
        "collectors.warrants.src.sec_reverse_split_extraction.fetch_document_text",
        return_value="Item 3.03. An unrelated modification of rights, no split involved.",
    ):

        results = discover_and_extract_reverse_splits_for_cik(
            "0001560293",
            user_agent="QuantLab test contact@example.com",
        )

    assert results == []
