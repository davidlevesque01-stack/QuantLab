from unittest.mock import patch

from collectors.warrants.src.sec_8k_warrant_llm_extraction_collector import (
    collect_ticker_8k_warrant_text_extraction_llm,
)


TICKER_CIK_MAP = {"TNON": "0001560293"}


def test_collect_returns_cik_not_found_when_unresolved():
    result = collect_ticker_8k_warrant_text_extraction_llm(
        "ZZZZ",
        TICKER_CIK_MAP,
        user_agent="QuantLab test contact@example.com",
        api_key="sk-test-key",
    )

    assert result == {
        "ticker": "ZZZZ",
        "cik": None,
        "status": "cik_not_found",
    }


def test_collect_returns_none_extracted_when_no_observations():
    with patch(
        "collectors.warrants.src.sec_8k_warrant_llm_extraction_collector."
        "discover_and_extract_warrant_terms_for_cik_llm",
        return_value=[],
    ):
        result = collect_ticker_8k_warrant_text_extraction_llm(
            "TNON",
            TICKER_CIK_MAP,
            user_agent="QuantLab test contact@example.com",
            api_key="sk-test-key",
        )

    assert result == {
        "ticker": "TNON",
        "cik": "0001560293",
        "status": "no_terms_extracted",
    }


def test_collect_persists_extracted_observations():
    observations = [
        {
            "accession_number": "0001213900-26-095686",
            "document_url": "https://www.sec.gov/.../8k.htm",
            "filed_date": "2026-08-31",
            "form_type": "8-K",
            "kind": "exercise_price",
            "label": "Series A",
            "exercise_price": 5.02,
            "raw_snippet": "Each Series A Warrant has an exercise price of $5.02 per share",
            "extraction_method": "llm",
        }
    ]

    with patch(
        "collectors.warrants.src.sec_8k_warrant_llm_extraction_collector."
        "discover_and_extract_warrant_terms_for_cik_llm",
        return_value=observations,
    ), patch(
        "collectors.warrants.src.sec_8k_warrant_llm_extraction_collector."
        "persist_sec_8k_warrant_text_extractions",
        return_value={"inserted": 1, "skipped": 0},
    ) as mocked_persist:

        result = collect_ticker_8k_warrant_text_extraction_llm(
            "TNON",
            TICKER_CIK_MAP,
            user_agent="QuantLab test contact@example.com",
            api_key="sk-test-key",
        )

    assert result["status"] == "ok"
    assert result["inserted"] == 1
    assert result["skipped"] == 0
    mocked_persist.assert_called_once()
    assert mocked_persist.call_args.args[0] == "0001560293"
