import json
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.request import Request, urlopen


# ============================================================
# QuantLab - Nasdaq Historical Collector V0.3
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = PROJECT_ROOT / "config" / "config.json"

with open(CONFIG_FILE, "r", encoding="utf-8") as file:
    config = json.load(file)


# ============================================================
# PÉRIODE DE COLLECTE
# ============================================================

START_DATE = date(2026, 8, 1)
END_DATE = date(2026, 8, 15)

# Pour l'instant : 5 secondes
DELAY_SECONDS = 5


# ============================================================
# RÉPERTOIRES
# ============================================================

RAW_DIRECTORY = (
    PROJECT_ROOT
    / config["raw_directory"]
    / "historical"
)

RAW_DIRECTORY.mkdir(
    parents=True,
    exist_ok=True
)

LOG_DIRECTORY = PROJECT_ROOT / "logs"

LOG_DIRECTORY.mkdir(
    parents=True,
    exist_ok=True
)

PROGRESS_FILE = LOG_DIRECTORY / "progress.json"


# ============================================================
# PROGRESSION
# ============================================================

def load_progress():

    if not PROGRESS_FILE.exists():

        return {
            "last_completed_date": None,
            "successful_days": 0,
            "failed_days": 0
        }

    with open(
        PROGRESS_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


def save_progress(progress):

    with open(
        PROGRESS_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            progress,
            file,
            indent=4
        )


# ============================================================
# DÉTERMINATION DE LA DATE DE REPRISE
# ============================================================

def get_start_date(progress):

    last_completed = progress.get(
        "last_completed_date"
    )

    if not last_completed:

        return START_DATE

    last_date = date.fromisoformat(
        last_completed
    )

    next_date = last_date + timedelta(days=1)

    return max(
        next_date,
        START_DATE
    )


# ============================================================
# TÉLÉCHARGEMENT
# ============================================================

def download_halts_for_date(target_date):

    date_string = target_date.strftime(
        "%m%d%Y"
    )

    url = (
        f'{config["nasdaq_rss_base_url"]}'
        f'&haltdate={date_string}'
    )

    output_file = (
        RAW_DIRECTORY
        / f"tradehalts_{target_date.isoformat()}.xml"
    )

    # --------------------------------------------------------
    # Fichier déjà présent
    # --------------------------------------------------------

    if output_file.exists():

        print(
            f"{target_date} : fichier déjà présent ✓"
        )

        return "existing"

    print()
    print("=" * 60)
    print(
        f"Téléchargement : {target_date}"
    )
    print("=" * 60)

    print(
        f"URL : {url}"
    )

    request = Request(
        url,
        headers={
            "User-Agent": config["user_agent"]
        }
    )

    with urlopen(
        request,
        timeout=config[
            "request_timeout_seconds"
        ]
    ) as response:

        xml_data = response.read()

    output_file.write_bytes(
        xml_data
    )

    print(
        f"XML sauvegardé : {output_file}"
    )

    print(
        f"Données reçues : "
        f"{len(xml_data)} octets"
    )

    return "downloaded"


# ============================================================
# PROGRAMME PRINCIPAL
# ============================================================

progress = load_progress()

resume_date = get_start_date(
    progress
)

print()
print("=" * 60)
print(
    "QuantLab - Nasdaq Historical Collector V0.3"
)
print("=" * 60)

print()
print(
    f"Période cible : "
    f"{START_DATE} → {END_DATE}"
)

print()
print(
    f"Dernière date complétée : "
    f"{progress.get('last_completed_date')}"
)

print()
print(
    f"Prochaine date : "
    f"{resume_date}"
)

print()
print(
    f"Délai entre requêtes : "
    f"{DELAY_SECONDS} secondes"
)


# ============================================================
# AUCUNE COLLECTE NÉCESSAIRE
# ============================================================

if resume_date > END_DATE:

    print()
    print("=" * 60)
    print("COLLECTE DÉJÀ COMPLÈTE")
    print("=" * 60)

    print()
    print(
        f"Dernière date : "
        f"{progress.get('last_completed_date')}"
    )

    print()
    print(
        "Aucune nouvelle requête effectuée."
    )

    raise SystemExit


# ============================================================
# COLLECTE
# ============================================================

current_date = resume_date

session_downloaded = 0
session_existing = 0
session_failed = 0

while current_date <= END_DATE:

    try:

        result = download_halts_for_date(
            current_date
        )

        if result == "downloaded":

            session_downloaded += 1

            progress[
                "successful_days"
            ] += 1

        elif result == "existing":

            session_existing += 1

        # ----------------------------------------------------
        # Progression
        # ----------------------------------------------------

        progress[
            "last_completed_date"
        ] = current_date.isoformat()

        save_progress(
            progress
        )

    except Exception as error:

        session_failed += 1

        progress[
            "failed_days"
        ] += 1

        save_progress(
            progress
        )

        print()
        print(
            f"ERREUR : {current_date}"
        )

        print(
            f"Détail : {error}"
        )

        # ----------------------------------------------------
        # On arrête ici pour éviter de sauter une journée.
        # La prochaine exécution reprendra cette date.
        # ----------------------------------------------------

        print()
        print(
            "La collecte est interrompue."
        )

        print(
            "La prochaine exécution "
            "reprendra cette date."
        )

        break

    current_date += timedelta(days=1)

    # --------------------------------------------------------
    # Pause entre les requêtes
    # --------------------------------------------------------

    if current_date <= END_DATE:

        print()
        print(
            f"Pause de {DELAY_SECONDS} secondes..."
        )

        time.sleep(
            DELAY_SECONDS
        )


# ============================================================
# RÉSUMÉ
# ============================================================

print()
print("=" * 60)
print("COLLECTE TERMINÉE")
print("=" * 60)

print()
print(
    f"Nouveaux téléchargements : "
    f"{session_downloaded}"
)

print(
    f"Fichiers déjà présents : "
    f"{session_existing}"
)

print(
    f"Échecs durant cette session : "
    f"{session_failed}"
)

print()
print(
    f"Dernière date enregistrée : "
    f"{progress.get('last_completed_date')}"
)

print()
print(
    f"Progression : "
    f"{PROGRESS_FILE}"
)

print(
    f"XML : "
    f"{RAW_DIRECTORY}"
)