from pathlib import Path
import argparse

from collectors.nasdaq_halts.src.nasdaq_xml import parse_xml_file
from collectors.nasdaq_halts.src.nasdaq_deduplication import deduplicate_events
from collectors.nasdaq_halts.src.nasdaq_postgresql import write_trade_halts
from shared.database import get_connection


def main():

    parser = argparse.ArgumentParser(
        description="Load Nasdaq historical XML files into PostgreSQL RAW."
    )

    parser.add_argument(
        "--year",
        type=int,
        required=True,
    )

    parser.add_argument(
        "--month",
        type=int,
        required=True,
    )

    args = parser.parse_args()

    year = args.year
    month = args.month

    if month < 1 or month > 12:
        raise ValueError("Month must be between 1 and 12.")

    repo_root = Path(__file__).resolve().parents[2]

    raw_dir = (
        repo_root
        / "collectors"
        / "nasdaq_halts"
        / "data"
        / "raw"
        / "nasdaq"
        / "historical"
    )

    pattern = f"tradehalts_{year}-{month:02d}-*.xml"

    xml_files = sorted(raw_dir.glob(pattern))

    print()
    print("=" * 60)
    print("QUANTLAB - NASDAQ RAW MONTHLY LOAD")
    print("=" * 60)
    print()
    print(f"Période : {year}-{month:02d}")
    print(f"XML     : {len(xml_files)}")
    print()

    if not xml_files:
        raise RuntimeError(
            f"Aucun fichier XML trouvé pour {year}-{month:02d}"
        )

    # --------------------------------------------------------
    # 1. PARSING
    # --------------------------------------------------------

    raw_events = []

    for xml_file in xml_files:

        events = parse_xml_file(xml_file)

        raw_events.extend(events)

    print(
        f"Événements parser : {len(raw_events)}"
    )

    # --------------------------------------------------------
    # 2. DÉDUPLICATION
    # --------------------------------------------------------

    unique_events = deduplicate_events(
        raw_events
    )

    print(
        f"Événements uniques : {len(unique_events)}"
    )

    # --------------------------------------------------------
    # 3. PERSISTANCE RAW
    # --------------------------------------------------------

    print()
    print("Persistance RAW...")
    print()

    with get_connection() as conn:

        (
            inserted,
            updated,
            unchanged,
            raw_ids,
        ) = write_trade_halts(
            conn,
            unique_events
        )

    print()
    print("=" * 60)
    print("RAW LOAD SUMMARY")
    print("=" * 60)
    print()
    print(f"XML files           : {len(xml_files)}")
    print(f"Parsed events       : {len(raw_events)}")
    print(f"Unique events       : {len(unique_events)}")
    print(f"RAW inserted        : {inserted}")
    print(f"RAW updated         : {updated}")
    print(f"RAW unchanged       : {unchanged}")
    print(f"RAW IDs returned    : {len(raw_ids)}")
    print()

    if inserted + updated + unchanged != len(unique_events):
        raise RuntimeError(
            "RAW persistence count mismatch."
        )

    print("RAW MONTH LOAD : PASS")
    print()


if __name__ == "__main__":
    main()
