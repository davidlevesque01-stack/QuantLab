from unittest.mock import patch

from collectors.warrants.src.sec_warrant_xbrl import (
    extract_warrant_facts,
    fetch_company_facts,
)


SAMPLE_COMPANY_FACTS = {
    "cik": 1234567,
    "entityName": "Example Corp",
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
            "ClassOfWarrantOrRightExercisePriceOfWarrantsOrRights1": {
                "units": {
                    "USD/shares": [
                        {
                            "end": "2026-06-30",
                            "val": 11.5,
                            "accn": "0001-26-000001",
                            "fy": 2026,
                            "fp": "Q2",
                            "form": "10-Q",
                            "filed": "2026-08-01",
                        }
                    ]
                }
            },
            "ClassOfWarrantOrRightOutstanding": {
                "units": {
                    "shares": [
                        {
                            "end": "2026-06-30",
                            "val": 5000000,
                            "accn": "0001-26-000001",
                            "fy": 2026,
                            "fp": "Q2",
                            "form": "10-Q",
                            "filed": "2026-08-01",
                        },
                        {
                            "end": "2025-12-31",
                            "val": 5000000,
                            "accn": "0001-26-000000",
                            "fy": 2025,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2026-02-15",
                        },
                    ]
                }
            },
            "Assets": {
                "units": {
                    "USD": [
                        {
                            "end": "2026-06-30",
                            "val": 999,
                            "accn": "0001-26-000001",
                            "fy": 2026,
                            "fp": "Q2",
                            "form": "10-Q",
                            "filed": "2026-08-01",
                        }
                    ]
                }
            },
        },
    },
}


def test_extract_warrant_facts_only_keeps_class_of_warrant_concepts():
    observations = extract_warrant_facts(SAMPLE_COMPANY_FACTS)

    concepts = {observation["concept"] for observation in observations}

    assert concepts == {
        "ClassOfWarrantOrRightExercisePriceOfWarrantsOrRights1",
        "ClassOfWarrantOrRightOutstanding",
    }
    assert len(observations) == 3


def test_extract_warrant_facts_preserves_provenance():
    observations = extract_warrant_facts(SAMPLE_COMPANY_FACTS)

    outstanding = [
        observation
        for observation in observations
        if observation["concept"] == "ClassOfWarrantOrRightOutstanding"
    ]

    assert len(outstanding) == 2
    assert {observation["accession_number"] for observation in outstanding} == {
        "0001-26-000001",
        "0001-26-000000",
    }
    assert all(observation["unit"] == "shares" for observation in outstanding)


def test_extract_warrant_facts_returns_empty_list_when_no_warrant_concepts():
    company_facts_without_warrants = {
        "facts": {
            "us-gaap": {
                "Assets": SAMPLE_COMPANY_FACTS["facts"]["us-gaap"]["Assets"],
            }
        }
    }

    assert extract_warrant_facts(company_facts_without_warrants) == []


def test_fetch_company_facts_builds_expected_url():
    with patch(
        "collectors.warrants.src.sec_warrant_xbrl.fetch_json",
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
