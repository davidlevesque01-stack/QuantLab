from unittest.mock import patch

from collectors.warrants.src.sec_reverse_split_collector import (
    collect_ticker_reverse_splits,
)


TICKER_CIK_MAP = {"TNON": "0001560293"}


def test_collect_returns_cik_not_found_when_unresolved():
    result = collect_ticker_reverse_splits(
        "ZZZZ",
        TICKER_CIK_MAP,
        user_agent="QuantLab test contact@example.com",
    )

    assert result == {
        "ticker": "ZZZZ",
        "cik": None,
        "status": "cik_not_found",
    }


def test_collect_returns_no_split_found_when_none_discovered():
    with patch(
        "collectors.warrants.src.sec_reverse_split_collector.discover_and_extract_reverse_splits_for_cik",
        return_value=[],
    ):
        result = collect_ticker_reverse_splits(
            "TNON",
            TICKER_CIK_MAP,
            user_agent="QuantLab test contact@example.com",
        )

    assert result == {
        "ticker": "TNON",
        "cik": "0001560293",
        "status": "no_split_found",
    }


def test_collect_persists_discovered_splits():
    events = [
        {
            "accession_number": "0001213900-26-087352",
            "document_url": "https://www.sec.gov/.../8k.htm",
            "filed_date": "2026-08-10",
            "form_type": "8-K",
            "ratio_new": 1,
            "ratio_old": 35,
            "effective_date": "2026-08-10",
            "raw_snippet": "1-for-35 reverse stock split",
        }
    ]

    with patch(
        "collectors.warrants.src.sec_reverse_split_collector.discover_and_extract_reverse_splits_for_cik",
        return_value=events,
    ), patch(
        "collectors.warrants.src.sec_reverse_split_collector.persist_sec_reverse_split_events",
        return_value={"inserted": 1, "skipped": 0},
    ) as mocked_persist:

        result = collect_ticker_reverse_splits(
            "TNON",
            TICKER_CIK_MAP,
            user_agent="QuantLab test contact@example.com",
        )

    assert result["status"] == "ok"
    assert result["inserted"] == 1
    assert result["skipped"] == 0
    mocked_persist.assert_called_once()
    assert mocked_persist.call_args.args[0] == "0001560293"
