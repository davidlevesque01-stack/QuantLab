from unittest.mock import patch

from collectors.warrants.src.sec_ticker_universe_resolution import (
    build_augmented_ticker_cik_map,
)


def test_build_augmented_map_skips_already_resolvable_tickers():
    ticker_cik_map = {"TNON": "0001560293"}

    with patch(
        "collectors.warrants.src.sec_ticker_universe_resolution.get_connection",
    ) as mocked_get_conn, patch(
        "collectors.warrants.src.sec_ticker_universe_resolution.read_issue_names_for_tickers",
    ) as mocked_read_names, patch(
        "collectors.warrants.src.sec_ticker_universe_resolution.persist_sec_ticker_cik_resolution",
    ) as mocked_persist:

        result = build_augmented_ticker_cik_map(
            ["TNON"],
            ticker_cik_map,
            user_agent="QuantLab test contact@example.com",
        )

    assert result == {"TNON": "0001560293"}
    mocked_get_conn.assert_not_called()
    mocked_read_names.assert_not_called()
    mocked_persist.assert_not_called()


def test_build_augmented_map_resolves_and_persists_unresolvable_tickers():
    ticker_cik_map = {}

    with patch(
        "collectors.warrants.src.sec_ticker_universe_resolution.get_connection",
    ), patch(
        "collectors.warrants.src.sec_ticker_universe_resolution.read_issue_names_for_tickers",
        return_value={"CINC": "CinCor Pharma, Inc."},
    ), patch(
        "collectors.warrants.src.sec_ticker_universe_resolution.resolve_cik_with_fallback",
        return_value={
            "ticker": "CINC",
            "cik": "0001868734",
            "method": "name_search",
            "issuer_name_used": "CinCor Pharma, Inc.",
            "matched_name": "CinCor Pharma, Inc.",
        },
    ) as mocked_resolve, patch(
        "collectors.warrants.src.sec_ticker_universe_resolution.persist_sec_ticker_cik_resolution",
        return_value={"inserted": 1, "skipped": 0},
    ) as mocked_persist:

        result = build_augmented_ticker_cik_map(
            ["CINC"],
            ticker_cik_map,
            user_agent="QuantLab test contact@example.com",
        )

    assert result == {"CINC": "0001868734"}
    mocked_resolve.assert_called_once()
    assert mocked_resolve.call_args.args[0] == "CINC"
    assert mocked_resolve.call_args.args[2] == "CinCor Pharma, Inc."
    mocked_persist.assert_called_once()


def test_build_augmented_map_leaves_unresolved_tickers_out_of_the_map():
    ticker_cik_map = {}

    with patch(
        "collectors.warrants.src.sec_ticker_universe_resolution.get_connection",
    ), patch(
        "collectors.warrants.src.sec_ticker_universe_resolution.read_issue_names_for_tickers",
        return_value={},
    ), patch(
        "collectors.warrants.src.sec_ticker_universe_resolution.resolve_cik_with_fallback",
        return_value={
            "ticker": "ZZZZ",
            "cik": None,
            "method": "not_found",
            "issuer_name_used": None,
            "matched_name": None,
        },
    ), patch(
        "collectors.warrants.src.sec_ticker_universe_resolution.persist_sec_ticker_cik_resolution",
        return_value={"inserted": 1, "skipped": 0},
    ):

        result = build_augmented_ticker_cik_map(
            ["ZZZZ"],
            ticker_cik_map,
            user_agent="QuantLab test contact@example.com",
        )

    assert result == {}
