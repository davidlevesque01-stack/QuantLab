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


def _read_tradehalt_rows():
    rows = []

    with TRADEHALTS_FILE.open(
        "r",
        newline="",
        encoding="utf-8-sig",
    ) as f:
        reader = csv.DictReader(f)

        for row in reader:
            rows.append(
                (
                    row["symbol"].strip(),
                    empty_to_none(row["issue_name"]),
                    row["market"].strip(),
                    row["reason_code"].strip(),
                    parse_date(row["halt_date"]),
                    parse_time(row["halt_time"]),
                    parse_date(row["resumption_date"]),
                    parse_time(row["resumption_quote_time"]),
                    parse_time(row["resumption_trade_time"]),
                    parse_decimal(row["pause_threshold_price"]),
                    TRADEHALTS_FILE.name,
                )
            )

    return rows


def _read_episode_rows():
    rows = []

    with EPISODES_FILE.open(
        "r",
        newline="",
        encoding="utf-8-sig",
    ) as f:
        reader = csv.DictReader(f)

        for row in reader:
            halt_start = parse_timestamp(row["halt_start"])

            if halt_start is None:
                raise RuntimeError(
                    "CORE episode has no halt_start"
                )

            rows.append(
                (
                    empty_to_none(row["episode_id"]),
                    row["symbol"].strip(),
                    empty_to_none(row["issue_name"]),
                    row["market"].strip(),
                    empty_to_none(row["reason_code"]),
                    halt_start,
                    parse_timestamp(row["halt_end"]),
                    empty_to_none(row["duration_minutes"]),
                    parse_halt_close_status(
                        row["halt_at_close"]
                    ),
                )
            )

    return rows


def _create_stage_tables(cur):
    cur.execute(
        """
        CREATE TEMP TABLE stage_nasdaq_tradehalt_v12 (
            symbol varchar(20) NOT NULL,
            issue_name text,
            market varchar(10) NOT NULL,
            reason_code varchar(20) NOT NULL,
            halt_date date NOT NULL,
            halt_time time NOT NULL,
            resumption_date date,
            resumption_quote_time time,
            resumption_trade_time time,
            pause_threshold_price numeric(18,6),
            source_file text
        ) ON COMMIT DROP;

        CREATE TEMP TABLE stage_nasdaq_episode_v12 (
            collector_episode_id varchar(20),
            symbol varchar(20) NOT NULL,
            issue_name text,
            market varchar(10) NOT NULL,
            reason_code varchar(20),
            halt_start timestamp NOT NULL,
            halt_end timestamp,
            duration_minutes numeric(12,3),
            halt_close_status varchar(20)
        ) ON COMMIT DROP;
        """
    )


def _copy_rows(cur, table_name, columns, rows):
    if not rows:
        return

    column_sql = ", ".join(columns)

    with cur.copy(
        f"COPY {table_name} ({column_sql}) FROM STDIN"
    ) as copy:
        for row in rows:
            copy.write_row(row)


def load_tradehalts(cur):
    """
    Charge en mode set-based les identités RAW V1.2.

    Le CSV peut contenir plusieurs observations pour une même
    identité RAW. La staging table est donc dédupliquée avant
    l'INSERT.
    """
    cur.execute(
        """
        WITH source AS (
            SELECT DISTINCT ON (
                symbol,
                market,
                halt_date,
                halt_time,
                reason_code
            )
                symbol,
                issue_name,
                market,
                reason_code,
                halt_date,
                halt_time,
                pause_threshold_price,
                source_file
            FROM stage_nasdaq_tradehalt_v12
            ORDER BY
                symbol,
                market,
                halt_date,
                halt_time,
                reason_code,
                (issue_name IS NOT NULL) DESC,
                (pause_threshold_price IS NOT NULL) DESC
        ),
        inserted AS (
            INSERT INTO raw.nasdaq_trade_halt (
                symbol,
                issue_name,
                market,
                reason_code,
                halt_date,
                halt_time,
                pause_threshold_price,
                source_file
            )
            SELECT
                symbol,
                issue_name,
                market,
                reason_code,
                halt_date,
                halt_time,
                pause_threshold_price,
                source_file
            FROM source
            ON CONFLICT (
                symbol,
                halt_date,
                halt_time,
                reason_code,
                market
            )
            DO NOTHING
            RETURNING 1
        )
        SELECT
            (SELECT count(*) FROM inserted),
            (SELECT count(*) FROM source);
        """
    )

    inserted, total = cur.fetchone()
    return inserted, total - inserted


def load_resumptions(cur):
    """
    Charge les observations de reprise en une opération set-based.

    La contrainte V1.2 UNIQUE NULLS NOT DISTINCT rend le
    ON CONFLICT idempotent même lorsque quote/trade time est NULL.
    """
    cur.execute(
        """
        WITH source AS (
            SELECT DISTINCT
                symbol,
                market,
                halt_date,
                halt_time,
                reason_code,
                resumption_date,
                resumption_quote_time,
                resumption_trade_time,
                source_file
            FROM stage_nasdaq_tradehalt_v12
            WHERE resumption_date IS NOT NULL
        ),
        inserted AS (
            INSERT INTO raw.nasdaq_resumption (
                symbol,
                market,
                halt_date,
                halt_time,
                reason_code,
                resumption_date,
                resumption_quote_time,
                resumption_trade_time,
                source_file
            )
            SELECT
                symbol,
                market,
                halt_date,
                halt_time,
                reason_code,
                resumption_date,
                resumption_quote_time,
                resumption_trade_time,
                source_file
            FROM source
            ON CONFLICT (
                symbol,
                market,
                halt_date,
                halt_time,
                reason_code,
                resumption_date,
                resumption_quote_time,
                resumption_trade_time
            )
            DO NOTHING
            RETURNING 1
        )
        SELECT
            (SELECT count(*) FROM inserted),
            (SELECT count(*) FROM source);
        """
    )

    inserted, total = cur.fetchone()
    return inserted, total - inserted


def load_episodes(cur):
    """
    Charge CORE et les relations CORE -> RAW en mode set-based.

    Identité CORE V1.2:
        (symbol, market, halt_start)

    reason_code demeure descriptif.

    CORE conserve les libellés de marché du dataset analytique
    (NASDAQ / NYSE / AMEX / P / Z), tandis que RAW conserve les
    codes source Nasdaq (Q / N / A / P / Z). La conversion est
    appliquée uniquement lors des jointures CORE -> RAW.
    """
    cur.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM stage_nasdaq_episode_v12 s
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM raw.nasdaq_trade_halt r
                    WHERE r.symbol = s.symbol
                      AND r.market = CASE s.market
                          WHEN 'NASDAQ' THEN 'Q'
                          WHEN 'NYSE' THEN 'N'
                          WHEN 'AMEX' THEN 'A'
                          ELSE s.market
                      END
                      AND r.halt_date = s.halt_start::date
                      AND r.halt_time = s.halt_start::time
                )
            ) THEN
                RAISE EXCEPTION
                    'At least one CORE episode has no matching RAW halt';
            END IF;
        END
        $$;
        """
    )

    cur.execute(
        """
        WITH source AS (
            SELECT DISTINCT ON (
                symbol,
                market,
                halt_start
            )
                collector_episode_id,
                symbol,
                issue_name,
                market,
                reason_code,
                halt_start,
                halt_end,
                duration_minutes,
                halt_close_status
            FROM stage_nasdaq_episode_v12
            ORDER BY
                symbol,
                market,
                halt_start,
                (halt_end IS NOT NULL) DESC,
                halt_end DESC NULLS LAST,
                collector_episode_id NULLS LAST
        ),
        prepared AS (
            SELECT
                s.*,
                representative.id AS trade_halt_id
            FROM source s
            CROSS JOIN LATERAL (
                SELECT r.id
                FROM raw.nasdaq_trade_halt r
                WHERE r.symbol = s.symbol
                  AND r.market = CASE s.market
                      WHEN 'NASDAQ' THEN 'Q'
                      WHEN 'NYSE' THEN 'N'
                      WHEN 'AMEX' THEN 'A'
                      ELSE s.market
                  END
                  AND r.halt_date = s.halt_start::date
                  AND r.halt_time = s.halt_start::time
                ORDER BY
                    CASE
                        WHEN r.reason_code = s.reason_code
                            THEN 0
                        ELSE 1
                    END,
                    r.id
                LIMIT 1
            ) representative
        ),
        inserted AS (
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
            SELECT
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
            FROM prepared
            ON CONFLICT (
                symbol,
                market,
                halt_start
            )
            DO NOTHING
            RETURNING 1
        )
        SELECT
            (SELECT count(*) FROM inserted),
            (SELECT count(*) FROM source);
        """
    )

    inserted, total = cur.fetchone()
    existing = total - inserted

    cur.execute(
        """
        WITH desired AS (
            SELECT DISTINCT
                e.id AS episode_id,
                r.id AS trade_halt_id
            FROM stage_nasdaq_episode_v12 s
            JOIN core.nasdaq_halt_episode e
              ON e.symbol = s.symbol
             AND e.market = s.market
             AND e.halt_start = s.halt_start
            JOIN raw.nasdaq_trade_halt r
              ON r.symbol = s.symbol
             AND r.market = CASE s.market
                 WHEN 'NASDAQ' THEN 'Q'
                 WHEN 'NYSE' THEN 'N'
                 WHEN 'AMEX' THEN 'A'
                 ELSE s.market
             END
             AND r.halt_date = s.halt_start::date
             AND r.halt_time = s.halt_start::time
        ),
        inserted AS (
            INSERT INTO core.nasdaq_halt_episode_event (
                episode_id,
                trade_halt_id
            )
            SELECT
                episode_id,
                trade_halt_id
            FROM desired
            ON CONFLICT (
                episode_id,
                trade_halt_id
            )
            DO NOTHING
            RETURNING 1
        )
        SELECT
            (SELECT count(*) FROM inserted),
            (SELECT count(*) FROM desired);
        """
    )

    relations_inserted, relations_total = cur.fetchone()

    return (
        inserted,
        existing,
        relations_inserted,
        relations_total - relations_inserted,
    )


def main():
    print("QuantLab - Nasdaq PostgreSQL Loader V1.2 (batch)")
    print()

    print("Lecture des CSV...")
    tradehalt_rows = _read_tradehalt_rows()
    episode_rows = _read_episode_rows()

    print(
        f"Observations tradehalts : {len(tradehalt_rows)}"
    )
    print(
        f"Episodes CSV            : {len(episode_rows)}"
    )
    print("Connexion PostgreSQL...")

    with get_connection() as conn:
        with conn.cursor() as cur:
            print("Acquisition du verrou Nasdaq V1.2...")
            cur.execute(
                "SELECT pg_advisory_xact_lock(%s, %s);",
                (716203, 1),
            )
            print("Verrou acquis.")

            _create_stage_tables(cur)

            print("COPY staging tradehalts...")
            _copy_rows(
                cur,
                "stage_nasdaq_tradehalt_v12",
                (
                    "symbol",
                    "issue_name",
                    "market",
                    "reason_code",
                    "halt_date",
                    "halt_time",
                    "resumption_date",
                    "resumption_quote_time",
                    "resumption_trade_time",
                    "pause_threshold_price",
                    "source_file",
                ),
                tradehalt_rows,
            )

            print("COPY staging episodes...")
            _copy_rows(
                cur,
                "stage_nasdaq_episode_v12",
                (
                    "collector_episode_id",
                    "symbol",
                    "issue_name",
                    "market",
                    "reason_code",
                    "halt_start",
                    "halt_end",
                    "duration_minutes",
                    "halt_close_status",
                ),
                episode_rows,
            )

            print("Chargement RAW...")
            raw_inserted, raw_existing = load_tradehalts(
                cur
            )

            print("Chargement RESUMPTION...")
            (
                resumption_inserted,
                resumption_existing,
            ) = load_resumptions(cur)

            print("Chargement CORE et relations...")
            (
                episode_inserted,
                episode_existing,
                relation_inserted,
                relation_existing,
            ) = load_episodes(cur)

    print()
    print("POSTGRESQL LOADER V1.2 TERMINÉ")
    print(
        f"RAW inserted          : {raw_inserted}"
    )
    print(
        f"RAW existing          : {raw_existing}"
    )
    print(
        f"RESUMPTION inserted   : {resumption_inserted}"
    )
    print(
        f"RESUMPTION existing   : {resumption_existing}"
    )
    print(
        f"CORE inserted         : {episode_inserted}"
    )
    print(
        f"CORE existing         : {episode_existing}"
    )
    print(
        f"RELATION inserted     : {relation_inserted}"
    )
    print(
        f"RELATION existing     : {relation_existing}"
    )


if __name__ == "__main__":
    main()
