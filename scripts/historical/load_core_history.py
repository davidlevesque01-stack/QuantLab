from pathlib import Path
import argparse
import json
from datetime import datetime, timezone
from time import perf_counter

from collectors.nasdaq_halts.src.nasdaq_xml import parse_xml_file
from collectors.nasdaq_halts.src.nasdaq_deduplication import deduplicate_events
from collectors.nasdaq_halts.src.nasdaq_episodes import build_halt_episodes
from collectors.nasdaq_halts.src.nasdaq_postgresql import (
    write_trade_halts,
    write_halt_episodes,
)
from collectors.nasdaq_halts.src.nasdaq_paths import resolve_raw_directory
from shared.database import get_connection


START_DATE = "2020-01-01"
END_DATE = "2026-08-29"  # exclusive: includes through 2026-08-28
CHECKPOINT_NAME = "load_core_history_checkpoint.json"


def write_checkpoint(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def validate_counts(
    raw_inserted,
    raw_updated,
    raw_unchanged,
    core_inserted,
    core_updated,
    core_unchanged,
    expected_raw,
    expected_core,
):
    raw_classified = raw_inserted + raw_updated + raw_unchanged
    core_classified = core_inserted + core_updated + core_unchanged

    if raw_classified != expected_raw:
        raise RuntimeError(
            f"RAW classification mismatch: "
            f"{raw_classified} != {expected_raw}"
        )

    if core_classified != expected_core:
        raise RuntimeError(
            f"CORE classification mismatch: "
            f"{core_classified} != {expected_core}"
        )


def validate_relationships(conn, expected_core, expected_raw):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM core.nasdaq_halt_episode;"
        )
        core_count = cur.fetchone()[0]

        cur.execute(
            "SELECT COUNT(*) FROM core.nasdaq_halt_episode_event;"
        )
        relationship_count = cur.fetchone()[0]

        cur.execute(
            """
            SELECT COUNT(*)
            FROM (
                SELECT trade_halt_id
                FROM core.nasdaq_halt_episode_event
                GROUP BY trade_halt_id
                HAVING COUNT(*) > 1
            ) x;
            """
        )
        duplicate_raw_links = cur.fetchone()[0]

        cur.execute(
            """
            SELECT COUNT(*)
            FROM (
                SELECT episode_id
                FROM core.nasdaq_halt_episode_event
                GROUP BY episode_id
                HAVING COUNT(*) > 1
            ) x;
            """
        )
        multi_raw_episodes = cur.fetchone()[0]

    if core_count < expected_core:
        raise RuntimeError(
            f"CORE validation failed: {core_count} < {expected_core}"
        )

    if relationship_count < expected_raw:
        raise RuntimeError(
            "CORE→RAW validation failed: "
            f"{relationship_count} < {expected_raw}"
        )

    if duplicate_raw_links != 0:
        raise RuntimeError(
            f"RAW linked to multiple CORE episodes: {duplicate_raw_links}"
        )

    return (
        core_count,
        relationship_count,
        duplicate_raw_links,
        multi_raw_episodes,
    )


def main():
    parser = argparse.ArgumentParser(
        description=(
            "QuantLab Nasdaq historical RAW/CORE loader. "
            "Dry-run by default; --commit is required to persist."
        )
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Persist the load. Without this flag, the transaction is rolled back.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]

    config_path = (
        repo_root
        / "collectors"
        / "nasdaq_halts"
        / "config"
        / "config.json"
    )
    config = json.loads(config_path.read_text(encoding="utf-8"))

    raw_root = resolve_raw_directory(
        repo_root / "collectors" / "nasdaq_halts",
        config,
    )
    raw_dir = raw_root / "historical"

    checkpoint_path = (
        repo_root
        / "collectors"
        / "nasdaq_halts"
        / "logs"
        / CHECKPOINT_NAME
    )

    start = datetime.fromisoformat(START_DATE)
    end = datetime.fromisoformat(END_DATE)

    xml_files = []

    for path in sorted(raw_dir.glob("tradehalts_*.xml")):
        date_text = path.stem.replace("tradehalts_", "")

        try:
            file_date = datetime.strptime(
                date_text,
                "%Y-%m-%d",
            )
        except ValueError:
            continue

        if start <= file_date < end:
            xml_files.append(path)

    print()
    print("=" * 70)
    print("QUANTLAB - NASDAQ HISTORICAL CORE LOAD V1.1")
    print("=" * 70)
    print()
    print(f"Période       : {START_DATE} → 2026-08-28")
    print(f"XML           : {len(xml_files)}")
    print(f"RAW root      : {raw_root}")
    print(
        f"Mode          : "
        f"{'COMMIT' if args.commit else 'DRY-RUN / ROLLBACK'}"
    )
    print()

    if not xml_files:
        raise RuntimeError(
            f"Aucun XML trouvé dans : {raw_dir}"
        )

    checkpoint = {
        "loader": "load_core_history.py",
        "version": "1.1",
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "start_date": START_DATE,
        "end_date_exclusive": END_DATE,
        "xml_count": len(xml_files),
        "first_xml": xml_files[0].name,
        "last_xml": xml_files[-1].name,
        "mode": "commit" if args.commit else "dry-run",
        "phase": "started",
    }
    write_checkpoint(checkpoint_path, checkpoint)

    total_start = perf_counter()

    # --------------------------------------------------------
    # 1. GLOBAL PARSING
    # --------------------------------------------------------
    phase = perf_counter()
    raw_events = []

    for index, xml_file in enumerate(xml_files, start=1):
        raw_events.extend(parse_xml_file(xml_file))

        if (
            index == 1
            or index % 100 == 0
            or index == len(xml_files)
        ):
            print(
                f"Parsing : {index}/{len(xml_files)} "
                f"| événements : {len(raw_events)}"
            )

    parsing_seconds = perf_counter() - phase

    # --------------------------------------------------------
    # 2. GLOBAL DEDUPLICATION
    # --------------------------------------------------------
    phase = perf_counter()
    unique_events = deduplicate_events(raw_events)
    dedup_seconds = perf_counter() - phase

    # --------------------------------------------------------
    # 3. GLOBAL CORE CONSTRUCTION
    #
    # Must remain global so multi-day episodes crossing an XML
    # or calendar boundary are not split.
    # --------------------------------------------------------
    phase = perf_counter()
    episodes, stats = build_halt_episodes(unique_events)
    core_seconds = perf_counter() - phase

    checkpoint.update(
        {
            "phase": "dataset_built",
            "raw_parser_events": len(raw_events),
            "raw_unique_events": len(unique_events),
            "core_episodes": len(episodes),
            "duration_count": stats["duration_count"],
            "parsing_seconds": parsing_seconds,
            "dedup_seconds": dedup_seconds,
            "core_construction_seconds": core_seconds,
        }
    )
    write_checkpoint(checkpoint_path, checkpoint)

    print()
    print(f"Événements RAW parser : {len(raw_events)}")
    print(f"Événements uniques    : {len(unique_events)}")
    print(f"CORE episodes         : {len(episodes)}")
    print(f"Durées calculables    : {stats['duration_count']}")
    print(f"HALT close YES        : {stats['close_yes']}")
    print(f"HALT close NO         : {stats['close_no']}")
    print(f"HALT UNKNOWN          : {stats['close_unknown']}")
    print(f"HALT MULTI_DAY        : {stats['close_multi_day']}")
    print()
    print(f"Parsing               : {parsing_seconds:.3f} s")
    print(f"Déduplication         : {dedup_seconds:.3f} s")
    print(f"CORE construction     : {core_seconds:.3f} s")
    print()

    # --------------------------------------------------------
    # 4. ATOMIC DATABASE TRANSACTION
    #
    # V1.1 persistence is bulk and fast enough for the complete
    # historical dataset. Keeping RAW + CORE + relationships in
    # one transaction also preserves atomicity.
    #
    # Recovery is idempotent: rerunning after rollback/interruption
    # is safe and the persistence layer classifies existing rows as
    # INSERTED / UPDATED / UNCHANGED.
    # --------------------------------------------------------
    print("Début de la transaction PostgreSQL...")
    print(
        "Atomicité : RAW + CORE + CORE→RAW dans une seule transaction."
    )
    print(
        "Sans --commit : ROLLBACK obligatoire."
    )
    print()

    db_start = perf_counter()

    with get_connection() as conn:
        try:
            phase = perf_counter()

            (
                raw_inserted,
                raw_updated,
                raw_unchanged,
                raw_ids,
            ) = write_trade_halts(
                conn,
                unique_events,
            )

            raw_db_seconds = perf_counter() - phase

            print(
                f"RAW PostgreSQL      : {raw_db_seconds:.3f} s"
            )

            phase = perf_counter()

            (
                core_inserted,
                core_updated,
                core_unchanged,
            ) = write_halt_episodes(
                conn,
                episodes,
                unique_events,
                raw_ids,
            )

            core_db_seconds = perf_counter() - phase

            print(
                f"CORE PostgreSQL     : {core_db_seconds:.3f} s"
            )

            validate_counts(
                raw_inserted,
                raw_updated,
                raw_unchanged,
                core_inserted,
                core_updated,
                core_unchanged,
                len(unique_events),
                len(episodes),
            )

            phase = perf_counter()

            (
                core_count,
                relationship_count,
                duplicate_raw_links,
                multi_raw_episodes,
            ) = validate_relationships(
                conn,
                len(episodes),
                len(unique_events),
            )

            validation_seconds = perf_counter() - phase

            print()
            print("=" * 70)
            print("HISTORICAL LOAD RESULT")
            print("=" * 70)
            print()
            print(f"RAW inserted             : {raw_inserted}")
            print(f"RAW updated              : {raw_updated}")
            print(f"RAW unchanged            : {raw_unchanged}")
            print()
            print(f"CORE inserted            : {core_inserted}")
            print(f"CORE updated             : {core_updated}")
            print(f"CORE unchanged           : {core_unchanged}")
            print()
            print(f"CORE classified          : {core_inserted + core_updated + core_unchanged}")
            print(f"CORE expected            : {len(episodes)}")
            print()
            print(f"CORE rows observed       : {core_count}")
            print(f"CORE→RAW relations       : {relationship_count}")
            print(f"RAW expected             : {len(unique_events)}")
            print(f"RAW with >1 CORE         : {duplicate_raw_links}")
            print(f"CORE with >1 RAW         : {multi_raw_episodes}")
            print()
            print(f"RAW PostgreSQL           : {raw_db_seconds:.3f} s")
            print(f"CORE PostgreSQL          : {core_db_seconds:.3f} s")
            print(f"Validation               : {validation_seconds:.3f} s")

            print()
            print("HISTORICAL VALIDATION : PASS")

            checkpoint.update(
                {
                    "phase": "validated",
                    "raw_inserted": raw_inserted,
                    "raw_updated": raw_updated,
                    "raw_unchanged": raw_unchanged,
                    "core_inserted": core_inserted,
                    "core_updated": core_updated,
                    "core_unchanged": core_unchanged,
                    "core_rows_observed": core_count,
                    "relationship_count": relationship_count,
                    "validation_seconds": validation_seconds,
                }
            )
            write_checkpoint(checkpoint_path, checkpoint)

            if args.commit:
                conn.commit()
                checkpoint["phase"] = "committed"
                checkpoint["completed_at_utc"] = (
                    datetime.now(timezone.utc).isoformat()
                )
                write_checkpoint(checkpoint_path, checkpoint)
                print()
                print("COMMIT : PASS")
            else:
                conn.rollback()
                checkpoint["phase"] = "rolled_back"
                checkpoint["completed_at_utc"] = (
                    datetime.now(timezone.utc).isoformat()
                )
                write_checkpoint(checkpoint_path, checkpoint)
                print()
                print("ROLLBACK : PASS")

        except Exception:
            conn.rollback()
            checkpoint["phase"] = "failed_rollback"
            checkpoint["failed_at_utc"] = (
                datetime.now(timezone.utc).isoformat()
            )
            write_checkpoint(checkpoint_path, checkpoint)
            raise

    db_seconds = perf_counter() - db_start
    total_seconds = perf_counter() - total_start

    print()
    print("=" * 70)
    print("PERFORMANCE SUMMARY")
    print("=" * 70)
    print()
    print(f"Parsing               : {parsing_seconds:.3f} s")
    print(f"Déduplication         : {dedup_seconds:.3f} s")
    print(f"CORE construction     : {core_seconds:.3f} s")
    print(f"PostgreSQL total      : {db_seconds:.3f} s")
    print(f"TOTAL                 : {total_seconds:.3f} s")
    print()
    print(
        "NASDAQ HISTORICAL CORE LOAD : "
        f"{'COMMIT PASS' if args.commit else 'DRY-RUN PASS'}"
    )
    print()


if __name__ == "__main__":
    main()
