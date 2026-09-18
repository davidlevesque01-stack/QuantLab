"""Massive (formerly Polygon.io) flat-file S3 client (BT-11).

Downloads and caches one day's whole-market minute_aggs_v1 flat file from
Massive's S3-compatible flat-file distribution. Every trading day's file is
retained locally in full (immutable RAW archive), alongside a SHA-256
checksum and provenance sidecar -- see
docs/backtesting/BACKTESTING_GITHUB_BACKLOG.md#bt-11.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import boto3
from botocore.config import Config

MASSIVE_S3_ENDPOINT = "https://files.massive.com"
MASSIVE_S3_BUCKET = "flatfiles"
MASSIVE_DATASET = "us_stocks_sip/minute_aggs_v1"

ENV_ACCESS_KEY_ID = "QUANTLAB_MASSIVE_S3_ACCESS_KEY_ID"
ENV_SECRET_ACCESS_KEY = "QUANTLAB_MASSIVE_S3_SECRET_ACCESS_KEY"


@dataclass(frozen=True)
class DownloadResult:
    local_path: Path
    sha256: str
    file_size_bytes: int
    s3_key: str
    already_cached: bool


def _build_s3_client():
    access_key_id = os.environ[ENV_ACCESS_KEY_ID]
    secret_access_key = os.environ[ENV_SECRET_ACCESS_KEY]

    return boto3.client(
        "s3",
        endpoint_url=MASSIVE_S3_ENDPOINT,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        config=Config(signature_version="s3v4"),
    )


def build_s3_key(trading_day: date) -> str:
    return (
        f"{MASSIVE_DATASET}/{trading_day:%Y}/{trading_day:%m}/"
        f"{trading_day.isoformat()}.csv.gz"
    )


def resolve_local_paths(raw_directory: Path, trading_day: date) -> tuple[Path, Path]:
    """Returns (flatfile_path, provenance_path), mirroring the S3 key
    layout 1:1 under raw_directory/massive/... for easy cross-reference.
    """

    subdir = (
        Path(raw_directory)
        / "massive"
        / MASSIVE_DATASET
        / f"{trading_day:%Y}"
        / f"{trading_day:%m}"
    )
    stem = trading_day.isoformat()

    return subdir / f"{stem}.csv.gz", subdir / f"{stem}.provenance.json"


def download_flat_file(raw_directory: Path, trading_day: date, s3_client=None) -> DownloadResult:
    """Downloads (if not already cached) one day's whole-market flat file,
    computes a SHA-256 checksum, and writes a provenance sidecar. A local
    cache hit (both the flat file and its provenance sidecar already exist)
    short-circuits the S3 call entirely.
    """

    flatfile_path, provenance_path = resolve_local_paths(raw_directory, trading_day)
    s3_key = build_s3_key(trading_day)

    if flatfile_path.exists() and provenance_path.exists():
        digest = hashlib.sha256(flatfile_path.read_bytes()).hexdigest()
        return DownloadResult(
            flatfile_path, digest, flatfile_path.stat().st_size, s3_key, True
        )

    flatfile_path.parent.mkdir(parents=True, exist_ok=True)
    client = s3_client or _build_s3_client()

    tmp_path = flatfile_path.with_suffix(flatfile_path.suffix + ".tmp")
    client.download_file(MASSIVE_S3_BUCKET, s3_key, str(tmp_path))
    tmp_path.replace(flatfile_path)

    raw_bytes = flatfile_path.read_bytes()
    digest = hashlib.sha256(raw_bytes).hexdigest()

    provenance = {
        "provider": "MASSIVE",
        "dataset": MASSIVE_DATASET,
        "trading_day": trading_day.isoformat(),
        "s3_bucket": MASSIVE_S3_BUCKET,
        "s3_key": s3_key,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "sha256": digest,
        "file_size_bytes": len(raw_bytes),
    }

    tmp_provenance_path = provenance_path.with_suffix(".json.tmp")
    tmp_provenance_path.write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    tmp_provenance_path.replace(provenance_path)

    return DownloadResult(flatfile_path, digest, len(raw_bytes), s3_key, False)
