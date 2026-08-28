import csv
from datetime import datetime, time
from pathlib import Path

from shared.database import get_connection


BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"

TRADEHALTS_FILE = PROCESSED_DIR / "tradehalts.csv"
EPISODES_FILE = PROCESSED_DIR / "halt_episodes.csv"


def empty_to_none(value: str | None):
    if value is None:
        return None

    value = value.strip()

    return value if value else None


def parse_date(value: str | None):
    value = empty_to_none(value)

    if value is None:
        return None

    return datetime.strptime(
        value,
        "%m/%d/%Y",
    ).date()


def parse_time(value: str | None):
    value = empty_to_none(value)

    if value is None:
        return None

    # Certains fichiers Nasdaq contiennent des espaces
    # avant les millisecondes, par exemple:
    # "08:52:20                      .892"
    # On retire les espaces tout en conservant
    # la précision des fractions de seconde.
    value = value.replace(" ", "")

    return time.fromisoformat(value)


def parse_timestamp(value: str | None):
    value = empty_to_none(value)

    if value is None:
        return None

    return datetime.fromisoformat(value)


def parse_decimal(value: str | None):
    value = empty_to_none(value)

    if value is None:
        return None

    return value


def parse_halt_close_status(value: str | None):
    value = empty_to_none(value)

    if value is None:
        return None

    value = value.upper()

    allowed_values = {
        "YES",
        "NO",
        "UNKNOWN",
        "MULTI_DAY",
    }

    if value not in allowed_values:
        raise ValueError(
            f"Unexpected halt_close_status value: {value}"
        )

    return value


def load_tradehalts(conn):
    inserted = 0
    existing = 0

    sql = """
        INSERT INTO raw.nasdaq_trade_halt (
            symbol,
            issue_name,
            market,
            reason_code,
            halt_date,
            halt_time,
            resumption_date,
            resumption_quote_time,
            resumption_trade_time,
            pause_threshold_price,
            source_file
        )
        VALUES (
            %(symbol)s,
            %(issue_name)s,
            %(market)s,
            %(reason_code)s,
            %(halt_date)s,
            %(halt_time)s,
            %(resumption_date)s,
            %(resumption_quote_time)s,
            %(resumption_trade_time)s,
            %(pause_threshold_price)s,
            %(source_file)s
        )
        ON CONFLICT (
            symbol,
            halt_date,
            halt_time,
            reason_code,
            market
        )
        DO NOTHING
        RETURNING id;
    """

    with TRADEHALTS_FILE.open(
        "r",
        newline="",
        encoding="utf-8-sig",
    ) as f:
        reader = csv.DictReader(f)

        with conn.cursor() as cur:
            for row in reader:
                params = {
                    "symbol": row["symbol"].strip(),
                    "issue_name": empty_to_none(
                        row["issue_name"]
                    ),
                    "market": row["market"].strip(),
                    "reason_code": row[
                        "reason_code"
                    ].strip(),
                    "halt_date": parse_date(
                        row["halt_date"]
                    ),
                    "halt_time": parse_time(
                        row["halt_time"]
                    ),
                    "resumption_date": parse_date(
                        row["resumption_date"]
                    ),
                    "resumption_quote_time": parse_time(
                        row["resumption_quote_time"]
                    ),
                    "resumption_trade_time": parse_time(
                        row["resumption_trade_time"]
                    ),
                    "pause_threshold_price": parse_decimal(
                        row["pause_threshold_price"]
                    ),
                    "source_file": TRADEHALTS_FILE.name,
                }

                cur.execute(sql, params)

                if cur.fetchone() is None:
                    existing += 1
                else:
                    inserted += 1

    return inserted, existing


def load_episodes(conn):
    inserted = 0
    existing = 0

    select_raw_sql = """
        SELECT id
        FROM raw.nasdaq_trade_halt
        WHERE symbol = %(symbol)s
          AND market = %(market)s
          AND reason_code = %(reason_code)s
          AND halt_date = %(halt_date)s
          AND halt_time = %(halt_time)s;
    """

    insert_episode_sql = """
        INSERT INTO core.nasdaq_halt_episode (
            trade_halt_id,
            collector_episode_id,
            symbol,
            issue_name,
            market,
            reason_code,
            halt_start,
            halt_end,
            duration_minutes,
            halt_close_status
        )
        VALUES (
            %(trade_halt_id)s,
            %(collector_episode_id)s,
            %(symbol)s,
            %(issue_name)s,
            %(market)s,
            %(reason_code)s,
            %(halt_start)s,
            %(halt_end)s,
            %(duration_minutes)s,
            %(halt_close_status)s
        )
        ON CONFLICT (trade_halt_id)
        DO NOTHING
        RETURNING id;
    """

    with EPISODES_FILE.open(
        "r",
        newline="",
        encoding="utf-8-sig",
    ) as f:
        reader = csv.DictReader(f)

        with conn.cursor() as cur:
            for row in reader:
                halt_start = parse_timestamp(
                    row["halt_start"]
                )

                params = {
                    "collector_episode_id": empty_to_none(
                        row["episode_id"]
                    ),
                    "symbol": row["symbol"].strip(),
                    "issue_name": empty_to_none(
                        row["issue_name"]
                    ),
                    "market": row["market"].strip(),
                    "reason_code": row["reason_code"].strip(),
                    "halt_start": halt_start,
                    "halt_end": parse_timestamp(
                        row["halt_end"]
                    ),
                    "duration_minutes": empty_to_none(
                        row["duration_minutes"]
                    ),
                    "halt_close_status": parse_halt_close_status(
                        row["halt_at_close"]
                    ),
                    "halt_date": halt_start.date(),
                    "halt_time": halt_start.time(),
                }

                cur.execute(select_raw_sql, params)
                raw_result = cur.fetchone()

                if raw_result is None:
                    raise RuntimeError(
                        "RAW halt not found for "
                        f"{params['symbol']} "
                        f"{params['halt_date']} "
                        f"{params['halt_time']} "
                        f"{params['reason_code']} "
                        f"{params['market']}"
                    )

                params["trade_halt_id"] = raw_result[0]

                cur.execute(
                    insert_episode_sql,
                    params,
                )

                result = cur.fetchone()

                if result is None:
                    existing += 1
                else:
                    inserted += 1

    return inserted, existing

def main():
    print("QuantLab - Nasdaq PostgreSQL Loader")
    print()

    with get_connection() as conn:
        raw_inserted, raw_existing = load_tradehalts(
            conn
        )

        episode_inserted, episode_existing = (
            load_episodes(conn)
        )

    print(
        f"RAW inserted   : {raw_inserted}"
    )
    print(
        f"RAW existing   : {raw_existing}"
    )
    print(
        f"CORE inserted  : {episode_inserted}"
    )
    print(
        f"CORE existing  : {episode_existing}"
    )


if __name__ == "__main__":
    main()
