from unittest.mock import patch

from collectors.warrants.src.nasdaq_symbol_directory import (
    fetch_and_parse_symbol_directory,
    parse_nasdaq_listed,
    parse_other_listed,
)


SAMPLE_NASDAQ_LISTED = (
    "Symbol|Security Name|Market Category|Test Issue|Financial Status|"
    "Round Lot Size|ETF|NextShares\n"
    "AAAP|Pacer Barings CLO Market Flex ETF|G|N|N|100|Y|N\n"
    "TNON|Tenon Medical, Inc. - Common Stock|Q|N|N|100|N|N\n"
    "File Creation Time: 0911202614:01|||||||\n"
)

SAMPLE_OTHER_LISTED = (
    "ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|"
    "Test Issue|NASDAQ Symbol\n"
    "A|Agilent Technologies, Inc. Common Stock|N|A|N|100|N|A\n"
    "File Creation Time: 0911202614:01||||||\n"
)


def test_parse_nasdaq_listed_extracts_expected_fields():
    rows = parse_nasdaq_listed(SAMPLE_NASDAQ_LISTED)

    assert len(rows) == 2
    tnon = next(row for row in rows if row["symbol"] == "TNON")
    assert tnon["security_name"] == "Tenon Medical, Inc. - Common Stock"
    assert tnon["exchange"] == "Q"
    assert tnon["source_file"] == "nasdaqlisted"
    assert tnon["payload"]["Symbol"] == "TNON"


def test_parse_nasdaq_listed_skips_footer_line():
    rows = parse_nasdaq_listed(SAMPLE_NASDAQ_LISTED)

    assert all(row["symbol"] != "File Creation Time: 0911202614:01" for row in rows)


def test_parse_other_listed_uses_act_symbol_and_exchange_column():
    rows = parse_other_listed(SAMPLE_OTHER_LISTED)

    assert len(rows) == 1
    assert rows[0]["symbol"] == "A"
    assert rows[0]["exchange"] == "N"
    assert rows[0]["source_file"] == "otherlisted"


def test_fetch_and_parse_symbol_directory_combines_both_files():
    with patch(
        "collectors.warrants.src.nasdaq_symbol_directory.fetch_symbol_directory",
        side_effect=[SAMPLE_NASDAQ_LISTED, SAMPLE_OTHER_LISTED],
    ) as mocked_fetch:

        rows = fetch_and_parse_symbol_directory(
            user_agent="QuantLab test contact@example.com",
        )

    assert len(rows) == 3
    assert {row["source_file"] for row in rows} == {"nasdaqlisted", "otherlisted"}
    assert mocked_fetch.call_count == 2
