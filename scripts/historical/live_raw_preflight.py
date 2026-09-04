# ============================================================
# QUANTLAB - NASDAQ LIVE RAW PREFLIGHT
# ============================================================

import os
from pathlib import Path

from collectors.nasdaq_halts.src.nasdaq_halt_collector import (
    download_nasdaq_feed,
    load_config,
    save_raw_snapshot,
)


def main():
    print()
    print("=" * 60)
    print("QUANTLAB - NASDAQ LIVE RAW PREFLIGHT")
    print("=" * 60)
    print()

    config = load_config()

    raw_root = os.environ.get(
        "QUANTLAB_NASDAQ_RAW_DIRECTORY"
    )

    if not raw_root:
        raise RuntimeError(
            "QUANTLAB_NASDAQ_RAW_DIRECTORY n'est pas défini."
        )

    raw_directory = Path(raw_root)

    print(f"RAW root : {raw_directory}")
    print(f"Existe   : {raw_directory.exists()}")
    print()

    if not raw_directory.exists():
        raise RuntimeError(
            f"RAW directory inexistant : {raw_directory}"
        )

    url = config["nasdaq_rss_base_url"]
    timeout = config.get("request_timeout_seconds", 30)
    user_agent = config.get(
        "user_agent",
        "QuantLab Nasdaq Halt Collector/0.8",
    )

    print("Téléchargement du flux Nasdaq...")
    xml_bytes = download_nasdaq_feed(
        url,
        timeout,
        user_agent,
    )

    print(f"Flux reçu : {len(xml_bytes)} octets")
    print()

    print("Écriture du snapshot RAW OneDrive...")
    snapshot_file, latest_file = save_raw_snapshot(
        xml_bytes,
        raw_directory,
    )

    print(f"Snapshot : {snapshot_file}")
    print(f"Latest   : {latest_file}")
    print()

    if not snapshot_file.exists():
        raise RuntimeError(
            f"Snapshot non créé : {snapshot_file}"
        )

    if not latest_file.exists():
        raise RuntimeError(
            f"Latest non créé : {latest_file}"
        )

    snapshot_size = snapshot_file.stat().st_size
    latest_size = latest_file.stat().st_size

    if snapshot_size != len(xml_bytes):
        raise RuntimeError(
            f"Taille snapshot incorrecte : "
            f"{snapshot_size} != {len(xml_bytes)}"
        )

    if latest_size != len(xml_bytes):
        raise RuntimeError(
            f"Taille latest incorrecte : "
            f"{latest_size} != {len(xml_bytes)}"
        )

    print(f"Taille snapshot : {snapshot_size} octets")
    print(f"Taille latest   : {latest_size} octets")
    print()
    print("POSTGRESQL : NON APPELÉ")
    print("Écriture PostgreSQL : AUCUNE")
    print()
    print("=" * 60)
    print("NASDAQ LIVE RAW PREFLIGHT : PASS")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()
