from unittest.mock import patch

from collectors.warrants.src.sec_shares_outstanding_collector import (
    collect_ticker_shares_outstanding,
)


TICKER_CIK_MAP = {"TNON": "0001234567"}


def test_collect_returns_cik_not_found_when_unresolved():
    result = collect_ticker_shares_outstanding(
        "ZZZZ",
        TICKER_CIK_MAP,
        user_agent="QuantLab test contact@example.com",
    )

    assert result == {
        "ticker": "ZZZZ",
        "cik": None,
        "status": "cik_not_found",
    }


def test_collect_returns_no_facts_when_absent():
    with patch(
        "collectors.warrants.src.sec_shares_outstanding_collector.fetch_company_facts",
        return_value={"facts": {"dei": {}}},
    ):
        result = collect_ticker_shares_outstanding(
            "TNON",
            TICKER_CIK_MAP,
            user_agent="QuantLab test contact@example.com",
        )

    assert result == {
        "ticker": "TNON",
        "cik": "0001234567",
        "status": "no_shares_outstanding_facts",
    }


def test_collect_persists_extracted_facts():
    company_facts = {
        "facts": {
            "dei": {
                "EntityCommonStockSharesOutstanding": {
                    "units": {
                        "shares": [
                            {"end": "2026-06-30", "val": 10000000, "accn": "0001-26-000001"}
                        ]
                    }
                }
            }
        }
    }

    with patch(
        "collectors.warrants.src.sec_shares_outstanding_collector.fetch_company_facts",
        return_value=company_facts,
    ), patch(
        "collectors.warrants.src.sec_shares_outstanding_collector.persist_sec_shares_outstanding_facts",
        return_value={"inserted": 1, "skipped": 0},
    ) as mocked_persist:

        result = collect_ticker_shares_outstanding(
            "TNON",
            TICKER_CIK_MAP,
            user_agent="QuantLab test contact@example.com",
        )

    assert result["status"] == "ok"
    assert result["inserted"] == 1
    assert result["skipped"] == 0
    mocked_persist.assert_called_once()
    assert mocked_persist.call_args.args[0] == "0001234567"
