from pathlib import Path
import csv
import xml.etree.ElementTree as ET

from datetime import datetime, date, time, timedelta
from collections import defaultdict
from statistics import median

from collectors.nasdaq_halts.src.nasdaq_postgresql import persist_nasdaq_halts


# ============================================================
# QUANTLAB - NASDAQ HALT METRICS
# VERSION 0.7
# ============================================================

VERSION = "0.7"

BASE_DIR = Path(__file__).resolve().parent.parent

RAW_DIR = BASE_DIR / "data" / "raw" / "nasdaq" / "historical"
PROCESSED_DIR = BASE_DIR / "data" / "processed"

TRADEHALTS_FILE = PROCESSED_DIR / "tradehalts.csv"
EPISODES_FILE = PROCESSED_DIR / "halt_episodes.csv"
TICKER_METRICS_FILE = PROCESSED_DIR / "ticker_halt_metrics.csv"
REASON_METRICS_FILE = PROCESSED_DIR / "ticker_halt_reason_metrics.csv"
DAILY_FILE = PROCESSED_DIR / "ticker_halt_daily.csv"

NS = {
    "ndaq": "http://www.nasdaqtrader.com/"
}

# Clôture régulière du marché
MARKET_CLOSE = time(16, 0, 0)


# ============================================================
# OUTILS
# ============================================================

def clean(value):
    """
    Nettoie une valeur provenant du XML Nasdaq.
    """
    if value is None:
        return ""

    return value.strip()


def parse_datetime(date_text, time_text):
    """
    Convertit HaltDate + HaltTime Nasdaq en datetime.

    Exemples :
        08/10/2026 + 15:50:07.393
        08/10/2026 + 15:50:07
    """

    date_text = clean(date_text)
    time_text = clean(time_text)

    if not date_text or not time_text:
        return None

    time_text = time_text.replace(" ", "")

    formats = [
        "%m/%d/%Y %H:%M:%S.%f",
        "%m/%d/%Y %H:%M:%S",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(
                f"{date_text} {time_text}",
                fmt
            )
        except ValueError:
            continue

    return None


def parse_xml_file(xml_file):
    """
    Lit un fichier XML Nasdaq et retourne les HALT bruts.
    """

    tree = ET.parse(xml_file)
    root = tree.getroot()

    events = []

    for item in root.findall(".//item"):

        symbol = clean(
            item.findtext(
                "ndaq:IssueSymbol",
                default="",
                namespaces=NS
            )
        )

        if not symbol:
            continue

        issue_name = clean(
            item.findtext(
                "ndaq:IssueName",
                default="",
                namespaces=NS
            )
        )

        market = clean(
            item.findtext(
                "ndaq:Mkt",
                default="",
                namespaces=NS
            )
        )

        reason_code = clean(
            item.findtext(
                "ndaq:ReasonCode",
                default="",
                namespaces=NS
            )
        )

        pause_threshold = clean(
            item.findtext(
                "ndaq:PauseThresholdPrice",
                default="",
                namespaces=NS
            )
        )

        halt_date = clean(
            item.findtext(
                "ndaq:HaltDate",
                default="",
                namespaces=NS
            )
        )

        halt_time = clean(
            item.findtext(
                "ndaq:HaltTime",
                default="",
                namespaces=NS
            )
        )

        resumption_date = clean(
            item.findtext(
                "ndaq:ResumptionDate",
                default="",
                namespaces=NS
            )
        )

        resumption_quote_time = clean(
            item.findtext(
                "ndaq:ResumptionQuoteTime",
                default="",
                namespaces=NS
            )
        )

        resumption_trade_time = clean(
            item.findtext(
                "ndaq:ResumptionTradeTime",
                default="",
                namespaces=NS
            )
        )

        halt_start = parse_datetime(
            halt_date,
            halt_time
        )

        # Priorité à ResumptionTradeTime.
        #
        # Le titre est considéré halted jusqu'à la reprise
        # des transactions.

        resumption_time = resumption_trade_time

        if not resumption_time:
            resumption_time = resumption_quote_time

        halt_end = parse_datetime(
            resumption_date,
            resumption_time
        )

        events.append({
            "symbol": symbol,
            "issue_name": issue_name,
            "market": market,
            "reason_code": reason_code,
            "halt_date": halt_date,
            "halt_time": halt_time,
            "resumption_date": resumption_date,
            "resumption_quote_time": resumption_quote_time,
            "resumption_trade_time": resumption_trade_time,
            "pause_threshold_price": pause_threshold,
            "source_file": xml_file.name,
            "halt_start": halt_start,
            "halt_end": halt_end,
        })

    return events


def get_market_days(xml_files):
    """
    Détermine les jours de marché couverts par les fichiers XML.

    Les noms attendus sont :

        tradehalts_YYYY-MM-DD.xml

    Seuls les lundi-vendredi sont retenus.
    """

    market_days = set()

    for xml_file in xml_files:

        name = xml_file.stem

        if not name.startswith("tradehalts_"):
            continue

        date_text = name.replace(
            "tradehalts_",
            "",
            1
        )

        try:
            d = datetime.strptime(
                date_text,
                "%Y-%m-%d"
            ).date()

            if d.weekday() < 5:
                market_days.add(d)

        except ValueError:
            continue

    return sorted(market_days)


# ============================================================
# 1. LECTURE DES FICHIERS
# ============================================================

print()
print("============================================================")
print(f"QUANTLAB - NASDAQ HALT METRICS V{VERSION}")
print("============================================================")
print()

xml_files = sorted(
    RAW_DIR.glob("tradehalts_*.xml")
)

print(
    f"Fichiers XML trouvés : {len(xml_files)}"
)

market_days = get_market_days(xml_files)

print(
    f"Jours de marché      : {len(market_days)}"
)

if market_days:
    print(
        f"Période              : "
        f"{market_days[0]} -> {market_days[-1]}"
    )

raw_events = []

for xml_file in xml_files:

    try:

        events = parse_xml_file(
            xml_file
        )

        raw_events.extend(
            events
        )

    except Exception as e:

        print(
            f"ERREUR : {xml_file.name} -> {e}"
        )

print()

print(
    f"Événements bruts       : "
    f"{len(raw_events)}"
)


# ============================================================
# 2. DÉDUPLICATION
# ============================================================

unique_events_dict = {}

for event in raw_events:

    key = (
        event["symbol"],
        event["halt_start"],
        event["resumption_date"],
        event["resumption_trade_time"],
        event["reason_code"],
    )

    unique_events_dict[key] = event


unique_events = list(
    unique_events_dict.values()
)

print(
    f"Événements uniques     : "
    f"{len(unique_events)}"
)


# ============================================================
# 3. CONSTRUCTION DES HALT EPISODES
# ============================================================

events_by_symbol = defaultdict(list)

for event in unique_events:

    if event["halt_start"] is not None:

        events_by_symbol[
            event["symbol"]
        ].append(event)


episodes = []

for symbol, events in events_by_symbol.items():

    events.sort(
        key=lambda x: x["halt_start"]
    )

    current = None

    for event in events:

        start = event["halt_start"]
        end = event["halt_end"]

        # ----------------------------------------------------
        # Premier événement
        # ----------------------------------------------------

        if current is None:

            current = {
                "symbol": symbol,
                "issue_name":
                    event["issue_name"],
                "market":
                    event["market"],
                "reason_code":
                    event["reason_code"],
                "halt_start":
                    start,
                "halt_end":
                    end,
                "pause_threshold_price":
                    event[
                        "pause_threshold_price"
                    ],
            }

            continue

        current_start = current[
            "halt_start"
        ]

        current_end = current[
            "halt_end"
        ]

        # ----------------------------------------------------
        # Même épisode :
        #
        # - même début
        # - ou chevauchement
        # ----------------------------------------------------

        same_episode = False

        if start == current_start:

            same_episode = True

        elif (
            current_end is not None
            and start <= current_end
        ):

            same_episode = True

        if same_episode:

            if start < current_start:

                current[
                    "halt_start"
                ] = start

            if end is not None:

                if (
                    current_end is None
                    or end > current_end
                ):

                    current[
                        "halt_end"
                    ] = end

        else:

            episodes.append(
                current
            )

            current = {
                "symbol": symbol,
                "issue_name":
                    event["issue_name"],
                "market":
                    event["market"],
                "reason_code":
                    event["reason_code"],
                "halt_start":
                    start,
                "halt_end":
                    end,
                "pause_threshold_price":
                    event[
                        "pause_threshold_price"
                    ],
            }

    if current is not None:

        episodes.append(
            current
        )


# Identifiant unique d'épisode

for index, episode in enumerate(
    episodes,
    start=1
):

    episode[
        "episode_id"
    ] = f"H{index:08d}"


print(
    f"HALT Episodes          : "
    f"{len(episodes)}"
)


# ============================================================
# 4. CALCUL DES DURÉES
# ============================================================

duration_count = 0

for episode in episodes:

    start = episode[
        "halt_start"
    ]

    end = episode[
        "halt_end"
    ]

    if (
        start is not None
        and end is not None
        and end >= start
    ):

        duration = (
            end - start
        ).total_seconds() / 60.0

        episode[
            "duration_minutes"
        ] = round(
            duration,
            3
        )

        duration_count += 1

    else:

        episode[
            "duration_minutes"
        ] = ""


print(
    f"Durées calculables     : "
    f"{duration_count}"
)


# ============================================================
# 5. STATUT HALT À LA CLÔTURE DE L'ÉPISODE
# ============================================================

close_yes = 0
close_no = 0
close_unknown = 0

for episode in episodes:

    start = episode[
        "halt_start"
    ]

    end = episode[
        "halt_end"
    ]

    if (
        start is None
        or end is None
    ):

        episode[
            "halt_at_close"
        ] = "UNKNOWN"

        close_unknown += 1

        continue

    # --------------------------------------------------------
    # Même journée
    # --------------------------------------------------------

    if start.date() == end.date():

        if (
            start.time()
            <= MARKET_CLOSE
            <= end.time()
        ):

            episode[
                "halt_at_close"
            ] = "YES"

            close_yes += 1

        else:

            episode[
                "halt_at_close"
            ] = "NO"

            close_no += 1

    else:

        # Episode multi-day.
        #
        # Le statut de clôture est calculé au niveau DAILY.

        episode[
            "halt_at_close"
        ] = "MULTI_DAY"


# ============================================================
# 6. PERSISTANCE POSTGRESQL
# ============================================================

persist_nasdaq_halts(
    unique_events,
    episodes
)


# ============================================================
# 7. NIVEAU 1 - TRADEHALTS
# ============================================================

with TRADEHALTS_FILE.open(
    "w",
    newline="",
    encoding="utf-8-sig"
) as f:

    writer = csv.writer(f)

    writer.writerow([
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
    ])

    for event in unique_events:

        writer.writerow([
            event["symbol"],
            event["issue_name"],
            event["market"],
            event["reason_code"],
            event["halt_date"],
            event["halt_time"],
            event["resumption_date"],
            event["resumption_quote_time"],
            event["resumption_trade_time"],
            event[
                "pause_threshold_price"
            ],
        ])


# ============================================================
# 8. NIVEAU 2 - HALT EPISODES
# ============================================================

with EPISODES_FILE.open(
    "w",
    newline="",
    encoding="utf-8-sig"
) as f:

    writer = csv.writer(f)

    writer.writerow([
        "episode_id",
        "symbol",
        "issue_name",
        "market",
        "reason_code",
        "halt_start",
        "halt_end",
        "duration_minutes",
        "halt_at_close",
    ])

    for episode in episodes:

        writer.writerow([
            episode["episode_id"],
            episode["symbol"],
            episode["issue_name"],
            episode["market"],
            episode["reason_code"],
            episode["halt_start"],
            episode["halt_end"],
            episode["duration_minutes"],
            episode["halt_at_close"],
        ])


# ============================================================
# 9. NIVEAU 3 - DAILY
# ============================================================

daily = defaultdict(list)

for episode in episodes:

    start = episode[
        "halt_start"
    ]

    if start is None:
        continue

    start_date = start.date()

    end = episode[
        "halt_end"
    ]

    # --------------------------------------------------------
    # Déterminer toutes les dates couvertes
    # --------------------------------------------------------

    if end is None:

        dates = [
            start_date
        ]

    else:

        dates = []

        current_date = start_date

        while current_date <= end.date():

            if current_date.weekday() < 5:

                dates.append(
                    current_date
                )

            current_date += timedelta(
                days=1
            )

    for d in dates:

        daily[
            (
                episode["symbol"],
                d
            )
        ].append(
            episode
        )


daily_rows = []

for (
    symbol,
    trading_date
), day_episodes in sorted(
    daily.items()
):

    episodes_count = len(
        day_episodes
    )

    halt_at_close = False

    # --------------------------------------------------------
    # Chaque journée est évaluée indépendamment.
    # --------------------------------------------------------

    for episode in day_episodes:

        start = episode[
            "halt_start"
        ]

        end = episode[
            "halt_end"
        ]

        if start is None:
            continue

        # Heure de début effective

        if start.date() < trading_date:

            effective_start = time(
                0, 0, 0
            )

        else:

            effective_start = start.time()

        # Heure de fin effective

        if end is None:

            effective_end = time(
                23,
                59,
                59,
                999999
            )

        elif end.date() > trading_date:

            effective_end = time(
                23,
                59,
                59,
                999999
            )

        else:

            effective_end = end.time()

        # ----------------------------------------------------
        # HALT présent à la clôture ?
        # ----------------------------------------------------

        if (
            effective_start
            <= MARKET_CLOSE
            <= effective_end
        ):

            halt_at_close = True

            break

    daily_rows.append({

        "symbol":
            symbol,

        "date":
            trading_date,

        "halt_present":
            "YES",

        "episode_count":
            episodes_count,

        "halt_at_close":
            "YES"
            if halt_at_close
            else "NO",
    })


# ------------------------------------------------------------
# Écriture DAILY
# ------------------------------------------------------------

with DAILY_FILE.open(
    "w",
    newline="",
    encoding="utf-8-sig"
) as f:

    writer = csv.writer(f)

    writer.writerow([
        "symbol",
        "date",
        "halt_present",
        "episode_count",
        "halt_at_close",
    ])

    for row in daily_rows:

        writer.writerow([
            row["symbol"],
            row["date"],
            row["halt_present"],
            row["episode_count"],
            row["halt_at_close"],
        ])


# ============================================================
# 10. NIVEAU 4 - TICKER METRICS V0.7
# ============================================================

episodes_by_symbol = defaultdict(list)

for episode in episodes:

    episodes_by_symbol[
        episode["symbol"]
    ].append(
        episode
    )


daily_by_symbol = defaultdict(list)

for row in daily_rows:

    daily_by_symbol[
        row["symbol"]
    ].append(
        row
    )


ticker_metrics = []

for symbol in sorted(
    episodes_by_symbol
):

    ticker_episodes = (
        episodes_by_symbol[
            symbol
        ]
    )

    ticker_daily = (
        daily_by_symbol[
            symbol
        ]
    )

    # --------------------------------------------------------
    # Nombre total d'épisodes
    # --------------------------------------------------------

    total_halt_episodes = len(
        ticker_episodes
    )

    # --------------------------------------------------------
    # Nombre de jours avec au moins un HALT
    # --------------------------------------------------------

    halt_days = len(
        ticker_daily
    )

    # --------------------------------------------------------
    # Nombre de jours avec HALT à la clôture
    # --------------------------------------------------------

    halt_days_at_close = sum(

        1

        for row in ticker_daily

        if row[
            "halt_at_close"
        ] == "YES"
    )

    # --------------------------------------------------------
    # Pourcentage de jours HALT avec présence à la clôture
    #
    # halt_days_at_close / halt_days
    # --------------------------------------------------------

    if halt_days > 0:

        halt_at_close_pct = round(

            (
                halt_days_at_close
                / halt_days
            ) * 100,

            4
        )

    else:

        halt_at_close_pct = 0


    # --------------------------------------------------------
    # V0.7
    #
    # Nombre moyen de HALT par jour avec HALT
    # --------------------------------------------------------

    if halt_days > 0:

        halts_per_halt_day = round(

            total_halt_episodes
            / halt_days,

            4
        )

    else:

        halts_per_halt_day = 0


    # --------------------------------------------------------
    # V0.7
    #
    # Nombre moyen de HALT par jour de marché
    # --------------------------------------------------------

    if len(market_days) > 0:

        halts_per_market_day = round(

            total_halt_episodes
            / len(market_days),

            4
        )

    else:

        halts_per_market_day = 0


    # --------------------------------------------------------
    # Durées
    # --------------------------------------------------------

    durations = [

        e["duration_minutes"]

        for e in ticker_episodes

        if isinstance(
            e["duration_minutes"],
            (
                int,
                float
            )
        )
    ]


    if durations:

        avg_duration = round(

            sum(durations)
            / len(durations),

            3
        )

        median_duration = round(

            median(durations),

            3
        )

        min_duration = min(
            durations
        )

        max_duration = max(
            durations
        )

    else:

        avg_duration = ""
        median_duration = ""
        min_duration = ""
        max_duration = ""


    # --------------------------------------------------------
    # Première / dernière date
    # --------------------------------------------------------

    valid_dates = [

        e["halt_start"].date()

        for e in ticker_episodes

        if e["halt_start"] is not None
    ]


    if valid_dates:

        first_halt = min(
            valid_dates
        )

        last_halt = max(
            valid_dates
        )

    else:

        first_halt = ""
        last_halt = ""


    ticker_metrics.append([

        symbol,

        total_halt_episodes,

        halt_days,

        halt_days_at_close,

        halt_at_close_pct,

        halts_per_halt_day,

        halts_per_market_day,

        avg_duration,

        median_duration,

        min_duration,

        max_duration,

        first_halt,

        last_halt,
    ])


# ------------------------------------------------------------
# Écriture TICKER METRICS
# ------------------------------------------------------------

with TICKER_METRICS_FILE.open(
    "w",
    newline="",
    encoding="utf-8-sig"
) as f:

    writer = csv.writer(f)

    writer.writerow([

        "symbol",

        "total_halt_episodes",

        "halt_days",

        "halt_days_at_close",

        "halt_at_close_pct",

        "halts_per_halt_day",

        "halts_per_market_day",

        "avg_halt_duration_minutes",

        "median_halt_duration_minutes",

        "min_halt_duration_minutes",

        "max_halt_duration_minutes",

        "first_halt_date",

        "last_halt_date",
    ])

    writer.writerows(
        ticker_metrics
    )


# ============================================================
# 11. NIVEAU 5 - REASON METRICS
# ============================================================

reason_data = defaultdict(list)

for episode in episodes:

    reason_data[
        (
            episode["symbol"],
            episode["reason_code"]
        )
    ].append(
        episode
    )


with REASON_METRICS_FILE.open(
    "w",
    newline="",
    encoding="utf-8-sig"
) as f:

    writer = csv.writer(f)

    writer.writerow([

        "symbol",

        "reason_code",

        "halt_episodes",

        "avg_duration_minutes",

        "min_duration_minutes",

        "max_duration_minutes",
    ])


    for (
        symbol,
        reason
    ), reason_episodes in sorted(
        reason_data.items()
    ):

        durations = [

            e["duration_minutes"]

            for e in reason_episodes

            if isinstance(
                e["duration_minutes"],
                (
                    int,
                    float
                )
            )
        ]


        if durations:

            avg = round(

                sum(durations)
                / len(durations),

                3
            )

            minimum = min(
                durations
            )

            maximum = max(
                durations
            )

        else:

            avg = ""
            minimum = ""
            maximum = ""


        writer.writerow([

            symbol,

            reason,

            len(
                reason_episodes
            ),

            avg,

            minimum,

            maximum,
        ])


# ============================================================
# 12. TEST DE NON-RÉGRESSION - QVCG
# ============================================================

print()

print("============================================================")
print("TEST DE NON-RÉGRESSION - QVCG")
print("============================================================")


qvcg_episodes = [

    e

    for e in episodes

    if e["symbol"] == "QVCG"
]


qvcg_daily = [

    r

    for r in daily_rows

    if r["symbol"] == "QVCG"
]


qvcg_halt_days = len(
    qvcg_daily
)


qvcg_close_days = sum(

    1

    for r in qvcg_daily

    if r[
        "halt_at_close"
    ] == "YES"
)


qvcg_metrics = [

    row

    for row in ticker_metrics

    if row[0] == "QVCG"
]


expected_qvcg_episodes = 2
expected_qvcg_halt_days = 2
expected_qvcg_close_days = 2


qvcg_test_passed = (

    len(qvcg_episodes)
    == expected_qvcg_episodes

    and

    qvcg_halt_days
    == expected_qvcg_halt_days

    and

    qvcg_close_days
    == expected_qvcg_close_days
)


print(
    f"QVCG épisodes       : "
    f"{len(qvcg_episodes)} "
    f"(attendu {expected_qvcg_episodes})"
)

print(
    f"QVCG jours HALT     : "
    f"{qvcg_halt_days} "
    f"(attendu {expected_qvcg_halt_days})"
)

print(
    f"QVCG jours clôture  : "
    f"{qvcg_close_days} "
    f"(attendu {expected_qvcg_close_days})"
)


if qvcg_metrics:

    q = qvcg_metrics[0]

    print(
        f"QVCG halts/jour HALT : {q[5]}"
    )

    print(
        f"QVCG halts/jour marché : {q[6]}"
    )

    print(
        f"QVCG durée médiane   : {q[8]}"
    )


if qvcg_test_passed:

    print()
    print("QVCG TEST : PASS ✓")

else:

    print()
    print("QVCG TEST : FAIL ✗")


# ============================================================
# 13. TEST DE NON-RÉGRESSION - BCARU
# ============================================================

print()

print("============================================================")
print("TEST DE NON-RÉGRESSION - BCARU")
print("============================================================")


bcaru_episodes = [

    e

    for e in episodes

    if e["symbol"] == "BCARU"
]


bcaru_daily = [

    r

    for r in daily_rows

    if r["symbol"] == "BCARU"
]


bcaru_metrics = [

    row

    for row in ticker_metrics

    if row[0] == "BCARU"
]


expected_bcaru_episodes = 12
expected_bcaru_halt_days = 5
expected_bcaru_close_days = 1


bcaru_test_passed = (

    len(bcaru_episodes)
    == expected_bcaru_episodes

    and

    len(bcaru_daily)
    == expected_bcaru_halt_days

    and

    sum(
        1
        for r in bcaru_daily
        if r["halt_at_close"] == "YES"
    )
    == expected_bcaru_close_days
)


print(
    f"BCARU épisodes       : "
    f"{len(bcaru_episodes)} "
    f"(attendu {expected_bcaru_episodes})"
)

print(
    f"BCARU jours HALT     : "
    f"{len(bcaru_daily)} "
    f"(attendu {expected_bcaru_halt_days})"
)

print(
    f"BCARU jours clôture  : "
    f"{sum(1 for r in bcaru_daily if r['halt_at_close'] == 'YES')} "
    f"(attendu {expected_bcaru_close_days})"
)


if bcaru_metrics:

    b = bcaru_metrics[0]

    print(
        f"BCARU halts/jour HALT : {b[5]}"
    )

    print(
        f"BCARU halts/jour marché : {b[6]}"
    )

    print(
        f"BCARU durée médiane   : {b[8]}"
    )


if bcaru_test_passed:

    print()
    print("BCARU TEST : PASS ✓")

else:

    print()
    print("BCARU TEST : FAIL ✗")


# ============================================================
# 14. VALIDATION FINALE
# ============================================================

print()

print("============================================================")
print(f"VALIDATION V{VERSION}")
print("============================================================")

print(
    f"Événements bruts       : "
    f"{len(raw_events)}"
)

print(
    f"Événements uniques     : "
    f"{len(unique_events)}"
)

print(
    f"HALT Episodes          : "
    f"{len(episodes)}"
)

print(
    f"Tickers différents     : "
    f"{len(episodes_by_symbol)}"
)

print(
    f"Lignes quotidiennes    : "
    f"{len(daily_rows)}"
)

print(
    f"Jours de marché        : "
    f"{len(market_days)}"
)

print(
    f"Durées calculables     : "
    f"{duration_count}"
)

print(
    f"HALT clôture YES       : "
    f"{close_yes}"
)

print(
    f"HALT clôture NO        : "
    f"{close_no}"
)

print(
    f"HALT clôture UNKNOWN   : "
    f"{close_unknown}"
)

print()

print(
    f"QVCG TEST              : "
    f"{'PASS ✓' if qvcg_test_passed else 'FAIL ✗'}"
)

print(
    f"BCARU TEST             : "
    f"{'PASS ✓' if bcaru_test_passed else 'FAIL ✗'}"
)

print()

print("Fichiers générés :")

print(
    f"  {TRADEHALTS_FILE}"
)

print(
    f"  {EPISODES_FILE}"
)

print(
    f"  {TICKER_METRICS_FILE}"
)

print(
    f"  {REASON_METRICS_FILE}"
)

print(
    f"  {DAILY_FILE}"
)

print()

print("============================================================")
print(f"CALCUL V{VERSION} TERMINÉ")
print("============================================================")
