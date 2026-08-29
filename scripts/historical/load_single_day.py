from pathlib import Path

from collectors.nasdaq_halts.src.nasdaq_xml import parse_xml_file
from collectors.nasdaq_halts.src.nasdaq_deduplication import deduplicate_events
from collectors.nasdaq_halts.src.nasdaq_episodes import build_halt_episodes
from collectors.nasdaq_halts.src.nasdaq_postgresql import persist_nasdaq_halts


DATE = "2026-01-14"

XML_FILE = (
    Path(__file__).resolve().parents[2]
    / "collectors"
    / "nasdaq_halts"
    / "data"
    / "raw"
    / "nasdaq"
    / "historical"
    / f"tradehalts_{DATE}.xml"
)


def main():

    print()
    print("=" * 60)
    print("QUANTLAB - SINGLE DAY POSTGRESQL PILOT")
    print("=" * 60)
    print()
    print(f"Date : {DATE}")
    print(f"XML  : {XML_FILE}")
    print()

    if not XML_FILE.exists():
        raise FileNotFoundError(
            f"Fichier XML introuvable : {XML_FILE}"
        )

    # --------------------------------------------------------
    # 1. PARSING
    # --------------------------------------------------------

    raw_events = parse_xml_file(XML_FILE)

    print(f"Événements RAW parser : {len(raw_events)}")

    # --------------------------------------------------------
    # 2. DÉDUPLICATION
    # --------------------------------------------------------

    unique_events = deduplicate_events(raw_events)

    print(f"Événements uniques    : {len(unique_events)}")

    # --------------------------------------------------------
    # 3. ÉPISODES
    # --------------------------------------------------------

    episodes, stats = build_halt_episodes(
        unique_events
    )

    print(f"HALT Episodes         : {len(episodes)}")
    print(f"Durées calculables    : {stats['duration_count']}")
    print(f"HALT à clôture YES    : {stats['close_yes']}")
    print(f"HALT à clôture NO     : {stats['close_no']}")
    print(f"HALT UNKNOWN          : {stats['close_unknown']}")
    print(f"HALT MULTI_DAY        : {stats['close_multi_day']}")

    # --------------------------------------------------------
    # 4. PERSISTANCE
    # --------------------------------------------------------

    print()
    print("Début de la persistance PostgreSQL...")
    print()

    result = persist_nasdaq_halts(
        unique_events,
        episodes
    )

    print()
    print("=" * 60)
    print("PILOTE TERMINÉ")
    print("=" * 60)
    print()

    print(f"RAW inserted          : {result['raw_inserted']}")
    print(f"RAW updated           : {result['raw_updated']}")
    print(f"RAW unchanged         : {result['raw_unchanged']}")
    print(f"CORE inserted         : {result['core_inserted']}")
    print(f"CORE updated          : {result['core_updated']}")
    print(f"CORE unchanged        : {result['core_unchanged']}")
    print()


if __name__ == "__main__":
    main()
