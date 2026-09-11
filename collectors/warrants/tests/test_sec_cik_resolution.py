from unittest.mock import patch

from collectors.warrants.src.sec_cik_resolution import (
    build_ticker_cik_map,
    fetch_ticker_cik_map,
    resolve_cik,
    resolve_cik_with_fallback,
)


SAMPLE_PAYLOAD = {
    "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    "1": {"cik_str": 1318605, "ticker": "TSLA", "title": "Tesla, Inc."},
}


def test_build_ticker_cik_map_zero_pads_and_uppercases():
    result = build_ticker_cik_map(SAMPLE_PAYLOAD)

    assert result["AAPL"] == "0000320193"
    assert result["TSLA"] == "0001318605"


def test_resolve_cik_found_case_insensitive():
    ticker_cik_map = build_ticker_cik_map(SAMPLE_PAYLOAD)

    assert resolve_cik("aapl", ticker_cik_map) == "0000320193"


def test_resolve_cik_not_found_returns_none():
    ticker_cik_map = build_ticker_cik_map(SAMPLE_PAYLOAD)

    assert resolve_cik("ZZZZ", ticker_cik_map) is None


def test_fetch_ticker_cik_map_uses_sec_edgar_client():
    with patch(
        "collectors.warrants.src.sec_cik_resolution.fetch_json",
        return_value=SAMPLE_PAYLOAD,
    ) as mocked_fetch:

        result = fetch_ticker_cik_map(
            user_agent="QuantLab test contact@example.com",
            timeout_seconds=5,
        )

    mocked_fetch.assert_called_once_with(
        "https://www.sec.gov/files/company_tickers.json",
        user_agent="QuantLab test contact@example.com",
        timeout_seconds=5,
    )
    assert result["AAPL"] == "0000320193"


def test_resolve_cik_with_fallback_prefers_ticker_map():
    ticker_cik_map = build_ticker_cik_map(SAMPLE_PAYLOAD)

    with patch(
        "collectors.warrants.src.sec_cik_resolution.resolve_cik_by_name"
    ) as mocked_name_search:

        result = resolve_cik_with_fallback(
            "aapl",
            ticker_cik_map,
            "Apple Inc.",
            user_agent="QuantLab test contact@example.com",
        )

    assert result == {
        "ticker": "aapl",
        "cik": "0000320193",
        "method": "ticker_map",
        "issuer_name_used": "Apple Inc.",
        "matched_name": None,
    }
    mocked_name_search.assert_not_called()


def test_resolve_cik_with_fallback_uses_name_search_when_absent():
    ticker_cik_map = build_ticker_cik_map(SAMPLE_PAYLOAD)

    with patch(
        "collectors.warrants.src.sec_cik_resolution.resolve_cik_by_name",
        return_value="0001868734",
    ) as mocked_name_search:

        result = resolve_cik_with_fallback(
            "CINC",
            ticker_cik_map,
            "CinCor Pharma, Inc.",
            user_agent="QuantLab test contact@example.com",
        )

    assert result == {
        "ticker": "CINC",
        "cik": "0001868734",
        "method": "name_search",
        "issuer_name_used": "CinCor Pharma, Inc.",
        "matched_name": "CinCor Pharma, Inc.",
    }
    mocked_name_search.assert_called_once_with(
        "CinCor Pharma, Inc.",
        user_agent="QuantLab test contact@example.com",
        timeout_seconds=30,
    )


def test_resolve_cik_with_fallback_not_found_without_issuer_name():
    ticker_cik_map = build_ticker_cik_map(SAMPLE_PAYLOAD)

    with patch(
        "collectors.warrants.src.sec_cik_resolution.resolve_cik_by_name"
    ) as mocked_name_search:

        result = resolve_cik_with_fallback(
            "ZZZZ",
            ticker_cik_map,
            None,
            user_agent="QuantLab test contact@example.com",
        )

    assert result == {
        "ticker": "ZZZZ",
        "cik": None,
        "method": "not_found",
        "issuer_name_used": None,
        "matched_name": None,
    }
    mocked_name_search.assert_not_called()


def test_resolve_cik_with_fallback_not_found_when_name_search_fails():
    ticker_cik_map = build_ticker_cik_map(SAMPLE_PAYLOAD)

    with patch(
        "collectors.warrants.src.sec_cik_resolution.resolve_cik_by_name",
        return_value=None,
    ):

        result = resolve_cik_with_fallback(
            "ZZZZ",
            ticker_cik_map,
            "Some Ambiguous Corp.",
            user_agent="QuantLab test contact@example.com",
        )

    assert result == {
        "ticker": "ZZZZ",
        "cik": None,
        "method": "not_found",
        "issuer_name_used": "Some Ambiguous Corp.",
        "matched_name": None,
    }
