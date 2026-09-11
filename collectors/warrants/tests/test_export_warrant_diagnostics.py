import csv
from unittest.mock import patch

from collectors.warrants.src.export_warrant_diagnostics import (
    build_diagnostic_rows,
    build_edgar_filing_url,
    build_exhibit_diagnostic_rows,
    build_text_extraction_diagnostic_rows,
    export_diagnostic_rows,
    write_csv,
)


def test_build_edgar_filing_url_strips_leading_zeros_and_dashes():
    url = build_edgar_filing_url("0001560293", "0001560293-26-000042")

    assert url == (
        "https://www.sec.gov/Archives/edgar/data/1560293/"
        "000156029326000042/0001560293-26-000042-index.htm"
    )


def test_build_edgar_filing_url_returns_none_when_accession_missing():
    assert build_edgar_filing_url("0001560293", None) is None
    assert build_edgar_filing_url("0001560293", "") is None


def test_build_diagnostic_rows_flattens_facts_with_filing_url():
    facts = [
        {
            "concept": "ClassOfWarrantOrRightOutstanding",
            "unit": "shares",
            "fact_value": 5000000,
            "period_start": None,
            "period_end": "2026-06-30",
            "form": "10-Q",
            "filed_date": "2026-08-01",
            "accession_number": "0001560293-26-000042",
        }
    ]

    rows = build_diagnostic_rows("TNON", "0001560293", "warrant", facts)

    assert len(rows) == 1
    row = rows[0]
    assert row["ticker"] == "TNON"
    assert row["cik"] == "0001560293"
    assert row["source_table"] == "warrant"
    assert row["value"] == 5000000
    assert row["filing_url"].endswith("-index.htm")


def test_export_diagnostic_rows_skips_unresolved_tickers():
    ticker_cik_map = {"TNON": "0001560293"}

    with patch(
        "collectors.warrants.src.export_warrant_diagnostics.read_sec_warrant_xbrl_facts",
        return_value=[],
    ), patch(
        "collectors.warrants.src.export_warrant_diagnostics.read_sec_shares_outstanding_facts",
        return_value=[],
    ) as mocked_shares, patch(
        "collectors.warrants.src.export_warrant_diagnostics.read_sec_8k_warrant_exhibits",
        return_value=[],
    ), patch(
        "collectors.warrants.src.export_warrant_diagnostics.read_sec_8k_warrant_text_extractions",
        return_value=[],
    ):

        rows = export_diagnostic_rows(
            conn=object(),
            tickers=["TNON", "ZZZZ"],
            ticker_cik_map=ticker_cik_map,
        )

    assert rows == []
    # Only called once, for the resolved ticker — ZZZZ is skipped entirely.
    mocked_shares.assert_called_once()


def test_export_diagnostic_rows_combines_both_sources():
    ticker_cik_map = {"TNON": "0001560293"}

    warrant_fact = {
        "concept": "ClassOfWarrantOrRightOutstanding",
        "unit": "shares",
        "fact_value": 5000000,
        "period_start": None,
        "period_end": "2026-06-30",
        "form": "10-Q",
        "filed_date": "2026-08-01",
        "accession_number": "0001560293-26-000042",
    }
    shares_fact = {
        "concept": "EntityCommonStockSharesOutstanding",
        "unit": "shares",
        "fact_value": 10000000,
        "period_start": None,
        "period_end": "2026-06-30",
        "form": "10-Q",
        "filed_date": "2026-08-01",
        "accession_number": "0001560293-26-000042",
    }

    exhibit = {
        "accession_number": "0001213900-26-095686",
        "filing_date": "2026-08-31",
        "form_type": "8-K",
        "exhibit_type": "EX-4.1",
        "description": "FORM OF PRE-FUNDED WARRANT",
        "document_url": "https://www.sec.gov/.../ex4-1.htm",
    }

    text_extraction = {
        "accession_number": "0001213900-26-095686",
        "document_url": "https://www.sec.gov/.../ea0303883-8k_tenon.htm",
        "kind": "exercise_price",
        "label": "Each Series A",
        "share_quantity": None,
        "exercise_price": 5.02,
        "expiration_years": None,
        "raw_snippet": "Each Series A Warrant has an exercise price of $5.02 per share",
    }

    with patch(
        "collectors.warrants.src.export_warrant_diagnostics.read_sec_warrant_xbrl_facts",
        return_value=[warrant_fact],
    ), patch(
        "collectors.warrants.src.export_warrant_diagnostics.read_sec_shares_outstanding_facts",
        return_value=[shares_fact],
    ), patch(
        "collectors.warrants.src.export_warrant_diagnostics.read_sec_8k_warrant_exhibits",
        return_value=[exhibit],
    ), patch(
        "collectors.warrants.src.export_warrant_diagnostics.read_sec_8k_warrant_text_extractions",
        return_value=[text_extraction],
    ):

        rows = export_diagnostic_rows(
            conn=object(),
            tickers=["TNON"],
            ticker_cik_map=ticker_cik_map,
        )

    assert {row["source_table"] for row in rows} == {
        "warrant",
        "shares_outstanding",
        "8k_warrant_exhibit",
        "8k_warrant_text_extraction",
    }
    assert len(rows) == 4


def test_build_exhibit_diagnostic_rows_uses_document_url_as_filing_url():
    exhibits = [
        {
            "accession_number": "0001213900-26-095686",
            "filing_date": "2026-08-31",
            "form_type": "8-K",
            "exhibit_type": "EX-4.1",
            "description": "FORM OF PRE-FUNDED WARRANT",
            "document_url": "https://www.sec.gov/.../ex4-1.htm",
        }
    ]

    rows = build_exhibit_diagnostic_rows("TNON", "0001560293", exhibits)

    assert len(rows) == 1
    row = rows[0]
    assert row["source_table"] == "8k_warrant_exhibit"
    assert row["description"] == "FORM OF PRE-FUNDED WARRANT"
    assert row["filing_url"] == "https://www.sec.gov/.../ex4-1.htm"


def test_build_text_extraction_diagnostic_rows_picks_value_by_kind():
    extractions = [
        {
            "accession_number": "0001213900-26-095686",
            "document_url": "https://www.sec.gov/.../ea0303883-8k_tenon.htm",
            "filed_date": "2026-08-31",
            "form_type": "8-K",
            "kind": "exercise_price",
            "label": "Each Series A",
            "share_quantity": None,
            "exercise_price": 5.02,
            "expiration_years": None,
            "raw_snippet": "Each Series A Warrant has an exercise price of $5.02 per share",
        },
        {
            "accession_number": "0001213900-26-095686",
            "document_url": "https://www.sec.gov/.../ea0303883-8k_tenon.htm",
            "kind": "share_quantity",
            "label": "Series A",
            "share_quantity": 1058517,
            "exercise_price": None,
            "expiration_years": None,
            "raw_snippet": "Series A warrants to purchase up to an aggregate of 1,058,517 shares",
        },
    ]

    rows = build_text_extraction_diagnostic_rows("TNON", "0001560293", extractions)

    assert len(rows) == 2

    price_row = next(row for row in rows if row["concept"] == "exercise_price")
    assert price_row["value"] == 5.02
    assert price_row["unit"] == "USD"
    assert price_row["source_table"] == "8k_warrant_text_extraction"
    assert price_row["filed_date"] == "2026-08-31"
    assert price_row["form"] == "8-K"
    assert "raw_snippet" in price_row

    qty_row = next(row for row in rows if row["concept"] == "share_quantity")
    assert qty_row["value"] == 1058517
    assert qty_row["unit"] == "shares"


def test_write_csv_round_trip(tmp_path):
    rows = [
        {
            "ticker": "TNON",
            "cik": "0001560293",
            "source_table": "warrant",
            "concept": "ClassOfWarrantOrRightOutstanding",
            "unit": "shares",
            "value": 5000000,
            "period_start": None,
            "period_end": "2026-06-30",
            "form": "10-Q",
            "filed_date": "2026-08-01",
            "accession_number": "0001560293-26-000042",
            "filing_url": "https://www.sec.gov/Archives/edgar/data/1560293/x/y-index.htm",
        }
    ]

    output_path = tmp_path / "nested" / "warrant_diagnostics.csv"

    write_csv(rows, output_path)

    with open(output_path, newline="", encoding="utf-8") as csv_file:
        reader = list(csv.DictReader(csv_file))

    assert len(reader) == 1
    assert reader[0]["ticker"] == "TNON"
    assert reader[0]["filing_url"].endswith("y-index.htm")
