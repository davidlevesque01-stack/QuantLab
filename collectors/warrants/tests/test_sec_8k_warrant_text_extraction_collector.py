from unittest.mock import patch

from collectors.warrants.src.sec_8k_warrant_text_extraction_collector import (
    collect_ticker_8k_warrant_text_extraction,
)


TICKER_CIK_MAP = {"TNON": "0001560293"}


def test_collect_returns_cik_not_found_when_unresolved():
    result = collect_ticker_8k_warrant_text_extraction(
        "ZZZZ",
        TICKER_CIK_MAP,
        user_agent="QuantLab test contact@example.com",
    )

    assert result == {
        "ticker": "ZZZZ",
        "cik": None,
        "status": "cik_not_found",
    }


def test_collect_returns_none_extracted_when_no_terms():
    with patch(
        "collectors.warrants.src.sec_8k_warrant_text_extraction_collector.discover_and_extract_warrant_terms_for_cik",
        return_value=[],
    ):
        result = collect_ticker_8k_warrant_text_extraction(
            "TNON",
            TICKER_CIK_MAP,
            user_agent="QuantLab test contact@example.com",
        )

    assert result == {
        "ticker": "TNON",
        "cik": "0001560293",
        "status": "no_terms_extracted",
    }


def test_collect_persists_extracted_terms():
    observations = [
        {
            "accession_number": "0001213900-26-095686",
            "document_url": "https://www.sec.gov/.../ea0303883-8k_tenon.htm",
            "kind": "exercise_price",
            "label": "Each Series A",
            "exercise_price": 5.02,
            "raw_snippet": "Each Series A Warrant has an exercise price of $5.02 per share",
        }
    ]

    with patch(
        "collectors.warrants.src.sec_8k_warrant_text_extraction_collector.discover_and_extract_warrant_terms_for_cik",
        return_value=observations,
    ), patch(
        "collectors.warrants.src.sec_8k_warrant_text_extraction_collector.persist_sec_8k_warrant_text_extractions",
        return_value={"inserted": 1, "skipped": 0},
    ) as mocked_persist:

        result = collect_ticker_8k_warrant_text_extraction(
            "TNON",
            TICKER_CIK_MAP,
            user_agent="QuantLab test contact@example.com",
        )

    assert result["status"] == "ok"
    assert result["inserted"] == 1
    assert result["skipped"] == 0
    mocked_persist.assert_called_once()
    assert mocked_persist.call_args.args[0] == "0001560293"
