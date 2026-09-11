from collectors.warrants.src.sec_shares_outstanding import (
    extract_shares_outstanding_facts,
)


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
                        },
                        {
                            "end": "2026-03-31",
                            "val": 9500000,
                            "accn": "0001-26-000000",
                            "fy": 2026,
                            "fp": "Q1",
                            "form": "10-Q",
                            "filed": "2026-05-01",
                        },
                    ]
                }
            },
            "EntityCentralIndexKey": {
                "units": {
                    "pure": [
                        {"end": "2026-06-30", "val": 1234567, "accn": "0001-26-000001"}
                    ]
                }
            },
        },
        "us-gaap": {
            "Assets": {
                "units": {
                    "USD": [
                        {"end": "2026-06-30", "val": 999, "accn": "0001-26-000001"}
                    ]
                }
            }
        },
    }
}


def test_extract_shares_outstanding_facts_keeps_only_target_concept():
    observations = extract_shares_outstanding_facts(SAMPLE_COMPANY_FACTS)

    assert len(observations) == 2
    assert all(
        observation["concept"] == "EntityCommonStockSharesOutstanding"
        for observation in observations
    )
    assert {observation["value"] for observation in observations} == {
        10000000,
        9500000,
    }


def test_extract_shares_outstanding_facts_returns_empty_when_absent():
    company_facts_without_shares = {"facts": {"dei": {}}}

    assert extract_shares_outstanding_facts(company_facts_without_shares) == []
