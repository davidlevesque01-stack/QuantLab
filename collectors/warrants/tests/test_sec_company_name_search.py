from unittest.mock import patch

from collectors.warrants.src.sec_company_name_search import (
    find_best_match,
    normalize_company_name,
    parse_company_search_html,
    resolve_cik_by_name,
    search_companies_by_name,
)


# Minimal real-shape fixtures, mirroring the two actual HTML templates
# SEC's browse-edgar company-name search returns (confirmed live against
# "CinCor Pharma, Inc." on 2026-09-11 — output=atom is broken for this
# endpoint, returning "ARRAY(0x...)" instead of the company name, hence
# using the HTML page instead).

SINGLE_RESULT_HTML = """
<div class="companyInfo">
   <span class="companyName">CinCor Pharma, Inc. <acronym title="Central Index Key">CIK</acronym>#: <a href="/cgi-bin/browse-edgar?action=getcompany&amp;CIK=0001868734&amp;owner=include&amp;count=40">0001868734 (see all company filings)</a></span>
   <p class="identInfo">SIC: 2834 - PHARMACEUTICAL PREPARATIONS</p>
</div>
"""

MULTI_RESULT_HTML = """
<table>
<tr>
<td valign="top" scope="row"><a href="/cgi-bin/browse-edgar?action=getcompany&amp;CIK=0001787005&amp;owner=include&amp;count=40">0001787005</a></td>
<td scope="row">Cincinnati Bancorp, Inc.<br />SIC: 6035</td>
</tr>
<tr>
<td valign="top" scope="row"><a href="/cgi-bin/browse-edgar?action=getcompany&amp;CIK=0000020279&amp;owner=include&amp;count=40">0000020279</a></td>
<td scope="row">CINCINNATI BELL TELEPHONE CO /OH<br />SIC: 4813</td>
</tr>
</table>
"""

NO_RESULTS_HTML = "<p>No matching companies</p>"


def test_parse_company_search_html_single_result():
    results = parse_company_search_html(SINGLE_RESULT_HTML)

    assert results == [{"name": "CinCor Pharma, Inc.", "cik": "0001868734"}]


def test_parse_company_search_html_multi_result():
    results = parse_company_search_html(MULTI_RESULT_HTML)

    assert len(results) == 2
    assert results[0] == {"name": "Cincinnati Bancorp, Inc.", "cik": "0001787005"}
    assert results[1]["cik"] == "0000020279"


def test_parse_company_search_html_no_results():
    assert parse_company_search_html(NO_RESULTS_HTML) == []


def test_normalize_company_name_strips_suffixes_and_punctuation():
    assert normalize_company_name("CinCor Pharma, Inc.") == "cincor pharma"
    assert normalize_company_name("Cerevel Therapeutics Holdings") == (
        "cerevel therapeutics"
    )
    assert normalize_company_name("Acme Corp.") == "acme"
    assert normalize_company_name("Acme LLC") == "acme"


def test_find_best_match_returns_unique_exact_match():
    candidates = [
        {"name": "CinCor Pharma, Inc.", "cik": "0001868734"},
        {"name": "Cincinnati Bancorp, Inc.", "cik": "0001787005"},
    ]

    match = find_best_match("CinCor Pharma, Inc.", candidates)

    assert match == {"name": "CinCor Pharma, Inc.", "cik": "0001868734"}


def test_find_best_match_returns_none_when_ambiguous():
    candidates = [
        {"name": "Acme Inc.", "cik": "0000000001"},
        {"name": "Acme Corp.", "cik": "0000000002"},
    ]

    # Both normalize to "acme" -> ambiguous, must not guess.
    assert find_best_match("Acme Holdings", candidates) is None


def test_find_best_match_returns_none_when_no_match():
    candidates = [{"name": "Cincinnati Bancorp, Inc.", "cik": "0001787005"}]

    assert find_best_match("CinCor Pharma, Inc.", candidates) is None


def test_find_best_match_accepts_word_prefix_when_unambiguous():
    """
    Real case found validating CERE (2026-09-11): our own issue_name
    ("Cerevel Therapeutics") is missing "Holdings" that the SEC legal
    name ("Cerevel Therapeutics Holdings, Inc.") includes. SEC's search
    returned exactly this one candidate — no real ambiguity — so a
    word-boundary prefix match should be accepted.
    """

    candidates = [
        {"name": "Cerevel Therapeutics Holdings, Inc.", "cik": "0001805387"},
    ]

    match = find_best_match("Cerevel Therapeutics", candidates)

    assert match == {
        "name": "Cerevel Therapeutics Holdings, Inc.",
        "cik": "0001805387",
    }


def test_find_best_match_rejects_prefix_match_on_word_boundary_violation():
    # "cere" is a substring but NOT a word-prefix of "cerevel therapeutics"
    # — must not match, otherwise short/truncated names would over-match.
    candidates = [{"name": "Cerevel Therapeutics Holdings, Inc.", "cik": "0001805387"}]

    assert find_best_match("Cere", candidates) is None


def test_find_best_match_prefers_exact_over_prefix_and_stays_none_if_exact_is_ambiguous():
    candidates = [
        {"name": "Acme Inc.", "cik": "0000000001"},
        {"name": "Acme Corp.", "cik": "0000000002"},
        {"name": "Acme International", "cik": "0000000003"},
    ]

    # "Acme" normalizes the same as both Inc./Corp. candidates (exact,
    # ambiguous) — must stay None rather than falling through to the
    # prefix level and picking "Acme International" too.
    assert find_best_match("Acme", candidates) is None


def test_find_best_match_returns_none_when_multiple_prefix_matches():
    candidates = [
        {"name": "Cerevel Therapeutics Holdings, Inc.", "cik": "0001805387"},
        {"name": "Cerevel Therapeutics International Ltd.", "cik": "0009999999"},
    ]

    assert find_best_match("Cerevel Therapeutics", candidates) is None


def test_resolve_cik_by_name_uses_search_and_match():
    with patch(
        "collectors.warrants.src.sec_company_name_search.search_companies_by_name",
        return_value=[
            {"name": "CinCor Pharma, Inc.", "cik": "0001868734"},
            {"name": "Cincinnati Bancorp, Inc.", "cik": "0001787005"},
        ],
    ):
        cik = resolve_cik_by_name(
            "CinCor Pharma, Inc.",
            user_agent="QuantLab test contact@example.com",
        )

    assert cik == "0001868734"


def test_resolve_cik_by_name_returns_none_when_unmatched():
    with patch(
        "collectors.warrants.src.sec_company_name_search.search_companies_by_name",
        return_value=[],
    ):
        cik = resolve_cik_by_name(
            "Some Unknown Corp.",
            user_agent="QuantLab test contact@example.com",
        )

    assert cik is None
