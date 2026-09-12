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
    fake_filings = [{"accession_number": "A", "item_codes": "items 1.01, 3.02and9.01"}]

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
    ) as mocked_reverse_splits, patch(
        "collectors.warrants.src.run_sec_collection.fetch_all_8k_filings",
        return_value=fake_filings,
    ) as mocked_fetch_all_8k_filings:

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

    # SEC-17: the 8-K filing history is fetched exactly once per ticker
    # (shared across pipelines), not once per pipeline.
    mocked_fetch_all_8k_filings.assert_called_once_with(
        "0001234567",
        user_agent="QuantLab test contact@example.com",
        timeout_seconds=5,
    )

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

    # The 3 8-K-based pipelines all receive the SAME shared filings list
    # and the SAME shared fetch_cache instance (SEC-17) — captured from
    # one call and compared by identity/equality across the others.
    exhibits_kwargs = mocked_exhibits.call_args.kwargs
    assert exhibits_kwargs["filings"] == fake_filings
    shared_fetch_cache = exhibits_kwargs["fetch_cache"]
    assert shared_fetch_cache is not None

    mocked_exhibits.assert_called_once_with(
        "TNON",
        ticker_cik_map,
        user_agent="QuantLab test contact@example.com",
        timeout_seconds=5,
        filings=fake_filings,
        fetch_cache=shared_fetch_cache,
    )
    mocked_text_extraction.assert_called_once_with(
        "TNON",
        ticker_cik_map,
        user_agent="QuantLab test contact@example.com",
        timeout_seconds=5,
        filings=fake_filings,
        fetch_cache=shared_fetch_cache,
    )
    mocked_reverse_splits.assert_called_once_with(
        "TNON",
        ticker_cik_map,
        user_agent="QuantLab test contact@example.com",
        timeout_seconds=5,
        filings=fake_filings,
        fetch_cache=shared_fetch_cache,
    )


def test_run_collection_passes_shared_filings_and_cache_to_llm_extraction():
    """
    The LLM extraction pipeline (SEC-15) also shares the same
    pre-fetched filings and fetch_cache (SEC-17) as the exhibit/regex/
    reverse-split pipelines when --use-llm-extraction is set.
    """

    ticker_cik_map = {"TNON": "0001234567"}
    fake_filings = [{"accession_number": "A", "item_codes": "items 1.01, 3.02and9.01"}]

    with patch(
        "collectors.warrants.src.run_sec_collection.collect_ticker_warrants",
        return_value={"ticker": "TNON", "cik": "0001234567", "status": "ok"},
    ), patch(
        "collectors.warrants.src.run_sec_collection.collect_ticker_shares_outstanding",
        return_value={"ticker": "TNON", "cik": "0001234567", "status": "ok"},
    ), patch(
        "collectors.warrants.src.run_sec_collection.collect_ticker_8k_warrant_exhibits",
        return_value={"ticker": "TNON", "cik": "0001234567", "status": "ok"},
    ), patch(
        "collectors.warrants.src.run_sec_collection.collect_ticker_8k_warrant_text_extraction",
        return_value={"ticker": "TNON", "cik": "0001234567", "status": "ok"},
    ), patch(
        "collectors.warrants.src.run_sec_collection.collect_ticker_reverse_splits",
        return_value={"ticker": "TNON", "cik": "0001234567", "status": "ok"},
    ), patch(
        "collectors.warrants.src.run_sec_collection.collect_ticker_8k_warrant_text_extraction_llm",
        return_value={"ticker": "TNON", "cik": "0001234567", "status": "ok"},
    ) as mocked_llm_extraction, patch(
        "collectors.warrants.src.run_sec_collection.fetch_all_8k_filings",
        return_value=fake_filings,
    ):

        run_collection(
            ["TNON"],
            ticker_cik_map,
            user_agent="QuantLab test contact@example.com",
            timeout_seconds=5,
            use_llm_extraction=True,
            anthropic_api_key="sk-test-key",
            llm_model="claude-sonnet-5",
        )

    mocked_llm_extraction.assert_called_once_with(
        "TNON",
        ticker_cik_map,
        user_agent="QuantLab test contact@example.com",
        api_key="sk-test-key",
        model="claude-sonnet-5",
        timeout_seconds=5,
        filings=fake_filings,
        fetch_cache=mocked_llm_extraction.call_args.kwargs["fetch_cache"],
    )
