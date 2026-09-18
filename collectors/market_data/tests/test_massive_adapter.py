import gzip
import shutil
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

import collectors.market_data.src.massive_adapter as massive_adapter_module
from collectors.market_data.src.massive_adapter import MassiveAdapter, _window_start_to_utc

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "massive"
TRADING_DAY = date(2026, 8, 14)


class FakeS3Client:
    """Stands in for boto3's S3 client: copies a local fixture file instead
    of calling files.massive.com, so tests never hit the network.
    """

    def __init__(self, source_path):
        self._source_path = source_path
        self.calls = []

    def download_file(self, bucket, key, local_path):
        self.calls.append((bucket, key, local_path))
        shutil.copyfile(self._source_path, local_path)


def _write_gz_csv(path: Path, rows: list[dict]):
    fieldnames = ["ticker", "volume", "open", "close", "high", "low", "window_start", "transactions"]
    path.parent.mkdir(parents=True, exist_ok=True)

    with gzip.open(path, "wt", encoding="utf-8", newline="") as handle:
        handle.write(",".join(fieldnames) + "\n")
        for row in rows:
            handle.write(",".join(str(row[key]) for key in fieldnames) + "\n")


def test_window_start_nanosecond_conversion():
    ns = 1_786_665_600_000_000_000  # 2026-08-14T00:00:00Z, sanity anchor
    utc_dt = _window_start_to_utc(ns)

    assert utc_dt == datetime(2026, 8, 14, 0, 0, 0, tzinfo=timezone.utc)


def test_fetch_bars_filters_by_ticker_and_strips_to_canonical_shape(tmp_path):
    fake_client = FakeS3Client(FIXTURES_DIR / "2026-08-14.csv.gz")
    adapter = MassiveAdapter(tmp_path, s3_client=fake_client)

    bars = adapter.fetch_bars("GPUS", TRADING_DAY)

    assert len(fake_client.calls) == 1  # one download for the whole day
    assert len(bars) == 4  # GPUS has 4 rows in the fixture

    for bar in bars:
        assert set(bar.keys()) == {
            "ticker", "market", "bar_start", "open", "high", "low", "close", "volume",
        }
        assert bar["ticker"] == "GPUS"
        assert bar["market"] is None

    assert bars == sorted(bars, key=lambda b: b["bar_start"])


def test_fetch_bars_caches_day_across_calls(tmp_path):
    fake_client = FakeS3Client(FIXTURES_DIR / "2026-08-14.csv.gz")
    adapter = MassiveAdapter(tmp_path, s3_client=fake_client)

    adapter.fetch_bars("GPUS", TRADING_DAY)
    adapter.fetch_bars("TNON", TRADING_DAY)

    assert len(fake_client.calls) == 1  # second call reuses the in-memory cache


def test_ingest_trading_day_enriches_rows_and_respects_watchlist(tmp_path, monkeypatch):
    fake_client = FakeS3Client(FIXTURES_DIR / "2026-08-14.csv.gz")
    adapter = MassiveAdapter(tmp_path, s3_client=fake_client)

    captured = {}

    def fake_persist_market_bars(bars, source):
        captured["bars"] = bars
        captured["source"] = source
        return {"raw": {"inserted": len(bars), "skipped": 0}, "core": {"inserted": len(bars), "skipped": 0}}

    monkeypatch.setattr(massive_adapter_module, "persist_market_bars", fake_persist_market_bars)

    result = adapter.ingest_trading_day(TRADING_DAY, tickers=frozenset({"GPUS"}))

    assert captured["source"] == "MASSIVE"
    assert {bar["ticker"] for bar in captured["bars"]} == {"GPUS"}
    assert len(captured["bars"]) == 4

    for bar in captured["bars"]:
        assert bar["market"] is None
        assert bar["market_scope"] == "CONSOLIDATED_US"
        assert bar["session"] in ("PRE_MARKET", "REGULAR", "AFTER_HOURS")
        assert bar["source_provider"] == "MASSIVE"
        assert bar["source_dataset"] == "us_stocks_sip/minute_aggs_v1"
        assert bar["dataset_version"] == "minute_aggs_v1"
        assert bar["security_id"] is None

    assert result["raw"]["inserted"] == 4


def test_out_of_session_row_is_skipped_not_raised(tmp_path):
    # window_start well before 4am ET (e.g. 02:00 ET == 06:00 UTC).
    _write_gz_csv(
        tmp_path / "source.csv.gz",
        [
            {
                "ticker": "GPUS",
                "volume": 100,
                "open": 1.0,
                "close": 1.0,
                "high": 1.0,
                "low": 1.0,
                "window_start": 1_786_687_200_000_000_000,  # 2026-08-14T06:00:00Z == 02:00 EDT
                "transactions": 1,
            },
            {
                "ticker": "GPUS",
                "volume": 200,
                "open": 2.0,
                "close": 2.0,
                "high": 2.0,
                "low": 2.0,
                "window_start": 1_786_716_000_000_000_000,  # 10:00 EDT, in-session
                "transactions": 2,
            },
        ],
    )

    fake_client = FakeS3Client(tmp_path / "source.csv.gz")
    adapter = MassiveAdapter(tmp_path, s3_client=fake_client)

    bars = adapter.fetch_bars("GPUS", TRADING_DAY)

    assert len(bars) == 1
    assert bars[0]["volume"] == 200


def test_row_with_mismatched_trading_day_is_skipped(tmp_path):
    _write_gz_csv(
        tmp_path / "source.csv.gz",
        [
            {
                "ticker": "GPUS",
                "volume": 100,
                "open": 1.0,
                "close": 1.0,
                "high": 1.0,
                "low": 1.0,
                "window_start": 1_786_716_000_000_000_000,  # 2026-08-14, correct day
                "transactions": 1,
            },
            {
                "ticker": "GPUS",
                "volume": 300,
                "open": 3.0,
                "close": 3.0,
                "high": 3.0,
                "low": 3.0,
                "window_start": 1_786_802_400_000_000_000,  # 2026-08-15, mismatched day
                "transactions": 3,
            },
        ],
    )

    fake_client = FakeS3Client(tmp_path / "source.csv.gz")
    adapter = MassiveAdapter(tmp_path, s3_client=fake_client)

    bars = adapter.fetch_bars("GPUS", TRADING_DAY)

    assert len(bars) == 1
    assert bars[0]["volume"] == 100


def test_fetch_bars_raises_on_non_trading_day(tmp_path):
    fake_client = FakeS3Client(FIXTURES_DIR / "2026-08-14.csv.gz")
    adapter = MassiveAdapter(tmp_path, s3_client=fake_client)

    with pytest.raises(ValueError):
        adapter.fetch_bars("GPUS", date(2026, 8, 15))  # a Saturday
