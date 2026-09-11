from unittest.mock import patch

from collectors.warrants.src.sec_cik_resolution import (
    build_ticker_cik_map,
    fetch_ticker_cik_map,
    resolve_cik,
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
