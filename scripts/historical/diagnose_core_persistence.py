from pathlib import Path
from time import perf_counter

from collectors.nasdaq_halts.src.nasdaq_xml import parse_xml_file
from collectors.nasdaq_halts.src.nasdaq_deduplication import deduplicate_events
from collectors.nasdaq_halts.src.nasdaq_episodes import build_halt_episodes
from collectors.nasdaq_halts.src import nasdaq_postgresql as pg
from shared.database import get_connection

START_DATE = "2026-06-01"
END_DATE = "2026-09-01"

def main():
    repo_root = Path(__file__).resolve().parents[2]
    raw_dir = repo_root / "collectors" / "nasdaq_halts" / "data" / "raw" / "nasdaq" / "historical"
    xml_files = []
    for path in sorted(raw_dir.glob("tradehalts_*.xml")):
        day = path.stem.replace("tradehalts_", "")
        if START_DATE <= day < END_DATE:
            xml_files.append(path)

    print("=" * 70)
    print("QUANTLAB - CORE PERSISTENCE DIAGNOSTIC")
    print("=" * 70)
    print(f"Période : {START_DATE} → {END_DATE}")
    print(f"XML     : {len(xml_files)}")
    print("Mode    : POSTGRESQL / ROLLBACK")
    print()

    t0 = perf_counter()
    raw_events = []
    for path in xml_files:
        raw_events.extend(parse_xml_file(path))
    t_parse = perf_counter() - t0

    t0 = perf_counter()
    unique_events = deduplicate_events(raw_events)
    t_dedup = perf_counter() - t0

    t0 = perf_counter()
    episodes, stats = build_halt_episodes(unique_events)
    t_core = perf_counter() - t0

    print(f"RAW parser : {len(raw_events)}")
    print(f"RAW unique : {len(unique_events)}")
    print(f"CORE       : {len(episodes)}")
    print()
    print(f"Parsing             : {t_parse:.3f} s")
    print(f"Déduplication       : {t_dedup:.3f} s")
    print(f"CORE construction   : {t_core:.3f} s")
    print()

    with get_connection() as conn:
        try:
            t0 = perf_counter()
            raw_result = pg.write_trade_halts(conn, unique_events)
            t_raw = perf_counter() - t0
            print(f"RAW PostgreSQL      : {t_raw:.3f} s")

            t0 = perf_counter()
            prepared_groups = pg._prepare_episode_raw_groups(
                episodes, unique_events, raw_result[3]
            )
            t_prepare = perf_counter() - t0
            print(f"CORE preparation    : {t_prepare:.3f} s ({len(prepared_groups)} groups)")

            t0 = perf_counter()
            core_result = pg.write_halt_episodes(
                conn, episodes, unique_events, raw_result[3]
            )
            t_core_db = perf_counter() - t0
            print(f"CORE PostgreSQL     : {t_core_db:.3f} s")
            print(f"CORE result         : inserted={core_result[0]}, updated={core_result[1]}, unchanged={core_result[2]}")

            t0 = perf_counter()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM core.nasdaq_halt_episode WHERE halt_start >= %s AND halt_start < %s",
                    (START_DATE, END_DATE),
                )
                core_count = cur.fetchone()[0]
                cur.execute(
                    """SELECT COUNT(*) FROM core.nasdaq_halt_episode_event e
                       JOIN core.nasdaq_halt_episode ep ON ep.id = e.episode_id
                       WHERE ep.halt_start >= %s AND ep.halt_start < %s""",
                    (START_DATE, END_DATE),
                )
                relation_count = cur.fetchone()[0]
            t_validation = perf_counter() - t0

            print(f"Validation queries  : {t_validation:.3f} s")
            print(f"CORE observed       : {core_count}")
            print(f"CORE expected       : {len(episodes)}")
            print(f"RAW links observed  : {relation_count}")
            print(f"RAW links expected  : {len(unique_events)}")

            if core_count != len(episodes) or relation_count != len(unique_events):
                raise RuntimeError("Diagnostic validation failed.")

            print()
            print("VALIDATION : PASS")
            print("ROLLBACK...")
            conn.rollback()
            print("ROLLBACK : PASS")
        except Exception:
            conn.rollback()
            raise

    print()
    print("=" * 70)
    print("DIAGNOSTIC SUMMARY")
    print("=" * 70)
    print(f"Parsing             : {t_parse:.3f} s")
    print(f"Déduplication       : {t_dedup:.3f} s")
    print(f"CORE construction   : {t_core:.3f} s")
    print(f"RAW PostgreSQL      : {t_raw:.3f} s")
    print(f"CORE preparation    : {t_prepare:.3f} s")
    print(f"CORE PostgreSQL     : {t_core_db:.3f} s")
    print(f"Validation          : {t_validation:.3f} s")
    print()
    print("CORE PERSISTENCE DIAGNOSTIC : PASS")

if __name__ == "__main__":
    main()
