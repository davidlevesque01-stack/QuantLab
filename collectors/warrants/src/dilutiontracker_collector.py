"""
DilutionTracker collector placeholder.

Implementation intentionally deferred until real API payloads have been captured
and the RAW data contract has been finalized.

Design requirements:
- authorized API access only;
- never log secrets/tokens;
- persist lossless raw responses before normalization;
- record endpoint, ticker, retrieval timestamp and API version when available;
- make ingestion idempotent;
- keep business rules outside transport code.
"""

from __future__ import annotations


def collect_ticker(ticker: str) -> None:
    """Collect DilutionTracker data for one ticker.

    This is a component scaffold only. The API contract and persistence model
    will be implemented after the payload-validation POC.
    """
    raise NotImplementedError("DilutionTracker API contract not finalized yet.")
