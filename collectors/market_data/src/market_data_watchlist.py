"""Watchlist loader for Massive ingestion (BT-11).

Massive's flat-file distribution always downloads/parses the whole US SIP
market for a trading day -- there is no partial-download option. The raw
flat file is retained on disk in full regardless. The watchlist only
controls which tickers get persisted into Postgres, so adding a ticker
later never requires re-downloading anything from Massive -- just
re-parsing the already-cached local file.
"""

from __future__ import annotations

import json
from pathlib import Path


def load_watchlist(path: Path) -> frozenset[str]:
    """Returns the set of tickers to persist to Postgres, read from a
    `{"tickers": [...]}` JSON file (see collectors/market_data/config/
    watchlist.json). An empty list means nothing gets persisted -- callers
    should treat that as "not configured yet", not silently ingest
    everything.
    """

    with open(path, encoding="utf-8") as handle:
        config = json.load(handle)

    return frozenset(config["tickers"])
