from unittest.mock import patch

from collectors.warrants.src.sec_xbrl_facts import extract_facts, fetch_company_facts


SAMPLE_COMPANY_FACTS = {
    "facts": {
        "dei": {
            "EntityCommonStockSharesOutstanding": {
                "units": {
                    "shares": [
                        {
                            "end": "2026-06-30",
                            "val": 10000000,
                            "accn": "0001-26-000001",
                            "fy": 2026,
                            "fp": "Q2",
                            "form": "10-Q",
                            "filed": "2026-08-01",
                        }
                    ]
                }
            }
        },
        "us-gaap": {
            "Assets": {
                "units": {
                    "USD": [
                        {
                            "end": "2026-06-30",
                            "val": 999,
                            "accn": "0001-26-000001",
                        }
                    ]
                }
            },
        },
    },
}


def test_fetch_company_facts_builds_expected_url():
    with patch(
        "collectors.warrants.src.sec_xbrl_facts.fetch_json",
        return_value=SAMPLE_COMPANY_FACTS,
    ) as mocked_fetch:

        result = fetch_company_facts(
            "0001234567",
            user_agent="QuantLab test contact@example.com",
            timeout_seconds=9,
        )

    mocked_fetch.assert_called_once_with(
        "https://data.sec.gov/api/xbrl/companyfacts/CIK0001234567.json",
        user_agent="QuantLab test contact@example.com",
        timeout_seconds=9,
    )
    assert result == SAMPLE_COMPANY_FACTS


def test_extract_facts_filters_by_taxonomy_and_predicate():
    observations = extract_facts(
        SAMPLE_COMPANY_FACTS,
        taxonomy="dei",
        matches_concept=lambda name: name == "EntityCommonStockSharesOutstanding",
    )

    assert len(observations) == 1
    assert observations[0]["value"] == 10000000
    assert observations[0]["accession_number"] == "0001-26-000001"


def test_extract_facts_returns_empty_when_taxonomy_absent():
    observations = extract_facts(
        {"facts": {}},
        taxonomy="dei",
        matches_concept=lambda name: True,
    )

    assert observations == []
