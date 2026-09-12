from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from collectors.warrants.src.sec_llm_warrant_extraction import (
    build_extraction_prompt,
    discover_and_extract_warrant_terms_for_cik_llm,
    extract_warrant_terms_llm,
    parse_llm_response,
)


# Real excerpt fetched from TNON's 8-K (accession 0001213900-26-095686), Item
# 1.01 — same fixture used to validate SEC-10's regex extraction
# (test_sec_8k_warrant_text_extraction.py), reused here so both extraction
# paths are validated against the same real source text.
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
    "Warrant Shares ”). Each Series A Warrant has an exercise price of "
    "$5.02 per share. The Series A Warrants are immediately exercisable "
    "and will expire five (5) years from issuance."
)


def _text_block(text):
    return SimpleNamespace(type="text", text=text)


def test_build_extraction_prompt_includes_document_text():
    prompt = build_extraction_prompt(REAL_TNON_8K_EXCERPT)

    assert REAL_TNON_8K_EXCERPT in prompt
    assert "<document>" in prompt


def test_parse_llm_response_parses_valid_json_array():
    response_text = """[
        {"kind": "share_quantity", "label": "Series A", "value": 1058517,
         "raw_snippet": "Series A warrants to purchase up to an aggregate of 1,058,517 shares of Common Stock"},
        {"kind": "exercise_price", "label": "Series A", "value": 5.02,
         "raw_snippet": "Each Series A Warrant has an exercise price of $5.02 per share"}
    ]"""

    observations = parse_llm_response(response_text, REAL_TNON_8K_EXCERPT)

    assert len(observations) == 2
    kinds = {obs["kind"] for obs in observations}
    assert kinds == {"share_quantity", "exercise_price"}

    share_qty_obs = next(o for o in observations if o["kind"] == "share_quantity")
    assert share_qty_obs["share_quantity"] == 1058517
    assert share_qty_obs["extraction_method"] == "llm"

    price_obs = next(o for o in observations if o["kind"] == "exercise_price")
    assert price_obs["exercise_price"] == 5.02


def test_parse_llm_response_strips_markdown_code_fence():
    response_text = (
        "```json\n"
        '[{"kind": "expiration_years", "label": "Series A", "value": 5, '
        '"raw_snippet": "will expire five (5) years from issuance"}]\n'
        "```"
    )

    observations = parse_llm_response(response_text, REAL_TNON_8K_EXCERPT)

    assert len(observations) == 1
    assert observations[0]["expiration_years"] == 5


def test_parse_llm_response_rejects_snippet_not_in_document():
    """
    Anti-hallucination guard: a raw_snippet that doesn't appear verbatim
    in the source document must never be persisted as a fact, even if
    the rest of the item looks well-formed.
    """

    response_text = (
        '[{"kind": "share_quantity", "label": "Series Z", "value": 999999999, '
        '"raw_snippet": "this sentence was never in the source document"}]'
    )

    observations = parse_llm_response(response_text, REAL_TNON_8K_EXCERPT)

    assert observations == []


def test_parse_llm_response_rejects_invalid_kind():
    response_text = (
        '[{"kind": "made_up_kind", "label": "Series A", "value": 1, '
        '"raw_snippet": "Each Series A Warrant has an exercise price of $5.02 per share"}]'
    )

    assert parse_llm_response(response_text, REAL_TNON_8K_EXCERPT) == []


def test_parse_llm_response_rejects_non_numeric_value():
    response_text = (
        '[{"kind": "exercise_price", "label": "Series A", "value": "not a number", '
        '"raw_snippet": "Each Series A Warrant has an exercise price of $5.02 per share"}]'
    )

    assert parse_llm_response(response_text, REAL_TNON_8K_EXCERPT) == []


def test_parse_llm_response_returns_empty_list_on_malformed_json():
    assert parse_llm_response("not json at all {{{", REAL_TNON_8K_EXCERPT) == []


def test_parse_llm_response_returns_empty_list_when_not_a_list():
    assert parse_llm_response('{"kind": "share_quantity"}', REAL_TNON_8K_EXCERPT) == []


def test_parse_llm_response_returns_empty_list_for_empty_array():
    assert parse_llm_response("[]", REAL_TNON_8K_EXCERPT) == []


def test_extract_warrant_terms_llm_calls_api_and_parses_response():
    mock_response = SimpleNamespace(
        content=[
            _text_block(
                '[{"kind": "exercise_price", "label": "Series A", "value": 5.02, '
                '"raw_snippet": "Each Series A Warrant has an exercise price of $5.02 per share"}]'
            )
        ]
    )

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    with patch(
        "collectors.warrants.src.sec_llm_warrant_extraction.anthropic.Anthropic",
        return_value=mock_client,
    ) as mocked_anthropic:

        observations = extract_warrant_terms_llm(
            REAL_TNON_8K_EXCERPT,
            api_key="sk-test-key",
            model="claude-sonnet-5",
        )

    mocked_anthropic.assert_called_once_with(api_key="sk-test-key")
    mock_client.messages.create.assert_called_once()
    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-sonnet-5"
    assert REAL_TNON_8K_EXCERPT in call_kwargs["messages"][0]["content"]

    assert len(observations) == 1
    assert observations[0]["exercise_price"] == 5.02


def test_discover_and_extract_warrant_terms_for_cik_llm_end_to_end():
    with patch(
        "collectors.warrants.src.sec_llm_warrant_extraction.fetch_all_8k_filings",
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
        "collectors.warrants.src.sec_llm_warrant_extraction.fetch_url",
        return_value=(
            b"<html><body><table class=\"tableFile\" summary=\"Document Format Files\">"
            b"<tr><th>Seq</th><th>Description</th><th>Document</th><th>Type</th><th>Size</th></tr>"
            b"<tr><td scope=\"row\">1</td><td scope=\"row\">CURRENT REPORT</td>"
            b"<td scope=\"row\"><a href=\"/Archives/edgar/data/x/8k.htm\">8k.htm</a></td>"
            b"<td scope=\"row\">8-K</td><td scope=\"row\">1</td></tr>"
            b"</table></body></html>"
        ),
    ), patch(
        "collectors.warrants.src.sec_llm_warrant_extraction.fetch_document_text",
        return_value=REAL_TNON_8K_EXCERPT,
    ), patch(
        "collectors.warrants.src.sec_llm_warrant_extraction.extract_warrant_terms_llm",
        return_value=[
            {
                "kind": "exercise_price",
                "label": "Series A",
                "exercise_price": 5.02,
                "raw_snippet": "Each Series A Warrant has an exercise price of $5.02 per share",
                "extraction_method": "llm",
            }
        ],
    ):

        results = discover_and_extract_warrant_terms_for_cik_llm(
            "0001560293",
            user_agent="QuantLab test contact@example.com",
            api_key="sk-test-key",
        )

    assert len(results) == 1
    assert results[0]["accession_number"] == "0001213900-26-095686"
    assert results[0]["filed_date"] == "2026-08-31"
    assert results[0]["extraction_method"] == "llm"
    assert results[0]["exercise_price"] == 5.02
