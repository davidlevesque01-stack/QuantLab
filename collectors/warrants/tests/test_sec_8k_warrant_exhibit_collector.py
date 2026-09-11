from unittest.mock import patch

from collectors.warrants.src.sec_8k_warrant_exhibit_collector import (
    collect_ticker_8k_warrant_exhibits,
)


TICKER_CIK_MAP = {"TNON": "0001560293"}


def test_collect_returns_cik_not_found_when_unresolved():
    result = collect_ticker_8k_warrant_exhibits(
        "ZZZZ",
        TICKER_CIK_MAP,
        user_agent="QuantLab test contact@example.com",
    )

    assert result == {
        "ticker": "ZZZZ",
        "cik": None,
        "status": "cik_not_found",
    }


def test_collect_returns_none_found_when_no_exhibits():
    with patch(
        "collectors.warrants.src.sec_8k_warrant_exhibit_collector.discover_warrant_exhibits_for_cik",
        return_value=[],
    ):
        result = collect_ticker_8k_warrant_exhibits(
            "TNON",
            TICKER_CIK_MAP,
            user_agent="QuantLab test contact@example.com",
        )

    assert result == {
        "ticker": "TNON",
        "cik": "0001560293",
        "status": "no_warrant_exhibits_found",
    }


def test_collect_persists_discovered_exhibits():
    exhibits = [
        {
            "accession_number": "0001213900-26-095686",
            "filing_date": "2026-08-31",
            "form_type": "8-K",
            "item_codes": "items 1.01, 3.02",
            "filing_index_url": "https://www.sec.gov/.../index.htm",
            "exhibit_seq": 3,
            "exhibit_type": "EX-4.1",
            "description": "FORM OF PRE-FUNDED WARRANT",
            "document_url": "https://www.sec.gov/.../ex4-1.htm",
        }
    ]

    with patch(
        "collectors.warrants.src.sec_8k_warrant_exhibit_collector.discover_warrant_exhibits_for_cik",
        return_value=exhibits,
    ), patch(
        "collectors.warrants.src.sec_8k_warrant_exhibit_collector.persist_sec_8k_warrant_exhibits",
        return_value={"inserted": 1, "skipped": 0},
    ) as mocked_persist:

        result = collect_ticker_8k_warrant_exhibits(
            "TNON",
            TICKER_CIK_MAP,
            user_agent="QuantLab test contact@example.com",
        )

    assert result["status"] == "ok"
    assert result["inserted"] == 1
    assert result["skipped"] == 0
    mocked_persist.assert_called_once()
    assert mocked_persist.call_args.args[0] == "0001560293"
