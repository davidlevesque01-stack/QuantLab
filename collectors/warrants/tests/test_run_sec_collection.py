import pytest
from unittest.mock import patch

from collectors.warrants.src.run_sec_collection import (
    parse_tickers,
    resolve_user_agent,
    run_collection,
)


def test_resolve_user_agent_prefers_cli_value():
    assert resolve_user_agent("cli-agent", "env-agent") == "cli-agent"


def test_resolve_user_agent_falls_back_to_env():
    assert resolve_user_agent(None, "env-agent") == "env-agent"


def test_resolve_user_agent_raises_when_neither_provided():
    with pytest.raises(ValueError):
        resolve_user_agent(None, None)


def test_parse_tickers_strips_and_uppercases_and_drops_blanks():
    assert parse_tickers("tnon, abcd ,, zzzz") == ["TNON", "ABCD", "ZZZZ"]


def test_run_collection_calls_all_five_collectors_per_ticker():
    ticker_cik_map = {"TNON": "0001234567"}

    with patch(
        "collectors.warrants.src.run_sec_collection.collect_ticker_warrants",
        return_value={"ticker": "TNON", "cik": "0001234567", "status": "ok"},
    ) as mocked_warrants, patch(
        "collectors.warrants.src.run_sec_collection.collect_ticker_shares_outstanding",
        return_value={"ticker": "TNON", "cik": "0001234567", "status": "ok"},
    ) as mocked_shares, patch(
        "collectors.warrants.src.run_sec_collection.collect_ticker_8k_warrant_exhibits",
        return_value={"ticker": "TNON", "cik": "0001234567", "status": "ok"},
    ) as mocked_exhibits, patch(
        "collectors.warrants.src.run_sec_collection.collect_ticker_8k_warrant_text_extraction",
        return_value={"ticker": "TNON", "cik": "0001234567", "status": "ok"},
    ) as mocked_text_extraction, patch(
        "collectors.warrants.src.run_sec_collection.collect_ticker_reverse_splits",
        return_value={"ticker": "TNON", "cik": "0001234567", "status": "ok"},
    ) as mocked_reverse_splits:

        results = run_collection(
            ["TNON"],
            ticker_cik_map,
            user_agent="QuantLab test contact@example.com",
            timeout_seconds=5,
        )

    assert len(results) == 1
    assert results[0]["ticker"] == "TNON"
    assert results[0]["warrants"]["status"] == "ok"
    assert results[0]["shares_outstanding"]["status"] == "ok"
    assert results[0]["warrant_exhibits"]["status"] == "ok"
    assert results[0]["warrant_text_extraction"]["status"] == "ok"
    assert results[0]["reverse_splits"]["status"] == "ok"
    mocked_warrants.assert_called_once_with(
        "TNON",
        ticker_cik_map,
        user_agent="QuantLab test contact@example.com",
        timeout_seconds=5,
    )
    mocked_shares.assert_called_once_with(
        "TNON",
        ticker_cik_map,
        user_agent="QuantLab test contact@example.com",
        timeout_seconds=5,
    )
    mocked_exhibits.assert_called_once_with(
        "TNON",
        ticker_cik_map,
        user_agent="QuantLab test contact@example.com",
        timeout_seconds=5,
    )
    mocked_text_extraction.assert_called_once_with(
        "TNON",
        ticker_cik_map,
        user_agent="QuantLab test contact@example.com",
        timeout_seconds=5,
    )
    mocked_reverse_splits.assert_called_once_with(
        "TNON",
        ticker_cik_map,
        user_agent="QuantLab test contact@example.com",
        timeout_seconds=5,
    )
