import argparse
import json
import time
import xml.etree.ElementTree as ET

from datetime import date, timedelta
from pathlib import Path
from urllib.request import Request, urlopen

from collectors.nasdaq_halts.src.nasdaq_paths import (
    resolve_raw_directory,
)


# ============================================================
# QUANTLAB - NASDAQ HISTORICAL COLLECTOR
# VERSION 0.5
# ============================================================

VERSION = "0.5.1"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = PROJECT_ROOT / "config" / "config.json"


# ============================================================
# CONFIGURATION
# ============================================================

def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


config = load_config()


# ============================================================
# RÉPERTOIRES RAW
# ============================================================

HISTORICAL_RAW_DIRECTORY = (
    resolve_raw_directory(
        PROJECT_ROOT,
        config,
    )
    / "historical"
)

HALTS_RAW_DIRECTORY = HISTORICAL_RAW_DIRECTORY

RESUMPTIONS_RAW_DIRECTORY = (
    HISTORICAL_RAW_DIRECTORY
    / "resumptions"
)

HALTS_RAW_DIRECTORY.mkdir(
    parents=True,
    exist_ok=True,
)

RESUMPTIONS_RAW_DIRECTORY.mkdir(
    parents=True,
    exist_ok=True,
)

LOG_DIRECTORY = PROJECT_ROOT / "logs"

LOG_DIRECTORY.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# ARGUMENTS
# ============================================================

def parse_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "Télécharge l'historique Nasdaq Trade Halts "
            "pour une plage de dates donnée."
        )
    )

    parser.add_argument(
        "--start-date",
        required=True,
        type=date.fromisoformat,
        help="Date de début au format YYYY-MM-DD.",
    )

    parser.add_argument(
        "--end-date",
        required=True,
        type=date.fromisoformat,
        help="Date de fin au format YYYY-MM-DD.",
    )

    parser.add_argument(
        "--feed",
        choices=(
            "halts",
            "resumptions",
        ),
        default="halts",
        help=(
            "Flux Nasdaq à collecter. "
            "'halts' utilise haltdate et demeure le défaut. "
            "'resumptions' utilise resumedate."
        ),
    )

    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=2.0,
        help="Délai entre les dates. Défaut : 2 secondes.",
    )

    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Nombre maximal de tentatives par date. Défaut : 3.",
    )

    parser.add_argument(
        "--retry-delay-seconds",
        type=float,
        default=5.0,
        help=(
            "Délai avant la tentative 2. "
            "Les tentatives suivantes utilisent un multiple "
            "de ce délai. Défaut : 5 secondes "
            "(5 s avant tentative 2, 10 s avant tentative 3)."
        ),
    )

    return parser.parse_args()


# ============================================================
# VALIDATION DES ARGUMENTS
# ============================================================

def validate_arguments(args):
    if args.start_date > args.end_date:
        raise ValueError(
            "La date de début doit être antérieure "
            "ou égale à la date de fin."
        )

    if args.end_date > date.today():
        raise ValueError(
            "La date de fin ne peut pas être dans le futur."
        )

    if args.delay_seconds < 0:
        raise ValueError(
            "--delay-seconds ne peut pas être négatif."
        )

    if args.max_retries < 1:
        raise ValueError(
            "--max-retries doit être supérieur ou égal à 1."
        )

    if args.retry_delay_seconds < 0:
        raise ValueError(
            "--retry-delay-seconds ne peut pas être négatif."
        )


# ============================================================
# CONFIGURATION DU FLUX
# ============================================================

def get_feed_settings(feed):
    if feed == "halts":
        return {
            "query_parameter": "haltdate",
            "raw_directory": HALTS_RAW_DIRECTORY,
            "filename_prefix": "tradehalts",
            "display_name": "HALTS",
        }

    if feed == "resumptions":
        return {
            "query_parameter": "resumedate",
            "raw_directory": RESUMPTIONS_RAW_DIRECTORY,
            "filename_prefix": "resumptions",
            "display_name": "RESUMPTIONS",
        }

    raise ValueError(
        f"Flux non supporté : {feed}"
    )


# ============================================================
# CHECKPOINT SPÉCIFIQUE À LA PLAGE ET AU FLUX
# ============================================================

def get_progress_file(
    feed,
    start_date,
    end_date,
):
    return (
        LOG_DIRECTORY
        / (
            f"historical_{feed}_progress_"
            f"{start_date.isoformat()}_"
            f"{end_date.isoformat()}.json"
        )
    )


def create_empty_progress(
    feed,
    start_date,
    end_date,
):
    return {
        "version": VERSION,
        "feed": feed,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "last_completed_date": None,
        "successful_days": 0,
        "existing_days": 0,
        "failed_days": 0,
        "failed_dates": [],
    }


def load_progress(
    progress_file,
    feed,
    start_date,
    end_date,
):
    if not progress_file.exists():
        return create_empty_progress(
            feed,
            start_date,
            end_date,
        )

    with open(
        progress_file,
        "r",
        encoding="utf-8",
    ) as file:
        progress = json.load(file)

    if progress.get("feed") not in (
        None,
        feed,
    ):
        raise RuntimeError(
            "Le checkpoint ne correspond pas "
            "au flux demandé."
        )

    if progress.get("start_date") != start_date.isoformat():
        raise RuntimeError(
            "Le checkpoint ne correspond pas "
            "à la date de début demandée."
        )

    if progress.get("end_date") != end_date.isoformat():
        raise RuntimeError(
            "Le checkpoint ne correspond pas "
            "à la date de fin demandée."
        )

    progress["feed"] = feed

    progress.setdefault(
        "successful_days",
        0,
    )

    progress.setdefault(
        "existing_days",
        0,
    )

    progress.setdefault(
        "failed_days",
        0,
    )

    progress.setdefault(
        "failed_dates",
        [],
    )

    return progress


def save_progress(progress_file, progress):
    temporary_file = progress_file.with_suffix(
        ".json.tmp"
    )

    with open(
        temporary_file,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            progress,
            file,
            indent=4,
        )

    temporary_file.replace(
        progress_file
    )


# ============================================================
# DATE DE REPRISE DU CHECKPOINT
# ============================================================

def get_resume_date(progress, start_date):
    last_completed = progress.get(
        "last_completed_date"
    )

    if not last_completed:
        return start_date

    last_date = date.fromisoformat(
        last_completed
    )

    return max(
        last_date + timedelta(days=1),
        start_date,
    )


# ============================================================
# VALIDATION XML
# ============================================================

def validate_xml(xml_data):
    if not xml_data:
        raise ValueError(
            "Réponse Nasdaq vide."
        )

    try:
        ET.fromstring(
            xml_data
        )

    except ET.ParseError as error:
        raise ValueError(
            "La réponse reçue n'est pas un XML valide."
        ) from error


# ============================================================
# ÉCRITURE ATOMIQUE DU XML
# ============================================================

def save_xml_atomic(output_file, xml_data):
    temporary_file = output_file.with_suffix(
        ".xml.tmp"
    )

    temporary_file.write_bytes(
        xml_data
    )

    temporary_file.replace(
        output_file
    )


# ============================================================
# URL NASDAQ
# ============================================================

def build_url(
    target_date,
    feed,
):
    date_string = target_date.strftime(
        "%m%d%Y"
    )

    settings = get_feed_settings(
        feed
    )

    return (
        f'{config["nasdaq_rss_base_url"]}'
        f'&{settings["query_parameter"]}={date_string}'
    )


# ============================================================
# TÉLÉCHARGEMENT D'UNE DATE
# ============================================================

def download_for_date(
    target_date,
    feed,
    max_retries,
    retry_delay_seconds,
):
    settings = get_feed_settings(
        feed
    )

    output_file = (
        settings["raw_directory"]
        / (
            f'{settings["filename_prefix"]}_'
            f"{target_date.isoformat()}.xml"
        )
    )

    if output_file.exists():
        print(
            f"{target_date} : fichier déjà présent"
        )

        return "existing"

    url = build_url(
        target_date,
        feed,
    )

    print()
    print("=" * 60)
    print(
        f'Téléchargement {settings["display_name"]} : '
        f"{target_date}"
    )
    print("=" * 60)

    print(
        f"URL : {url}"
    )

    request = Request(
        url,
        headers={
            "User-Agent": config["user_agent"],
        },
    )

    last_error = None

    for attempt in range(
        1,
        max_retries + 1,
    ):
        try:
            print(
                f"Tentative {attempt}/{max_retries}"
            )

            with urlopen(
                request,
                timeout=config[
                    "request_timeout_seconds"
                ],
            ) as response:
                xml_data = response.read()

            validate_xml(
                xml_data
            )

            save_xml_atomic(
                output_file,
                xml_data,
            )

            print(
                f"XML sauvegardé : {output_file}"
            )

            print(
                f"Données reçues : "
                f"{len(xml_data)} octets"
            )

            return "downloaded"

        except Exception as error:
            last_error = error

            print(
                f"Échec tentative {attempt}: {error}"
            )

            if attempt < max_retries:
                delay = (
                    retry_delay_seconds
                    * attempt
                )

                print(
                    f"Nouvelle tentative dans "
                    f"{delay:g} secondes..."
                )

                time.sleep(
                    delay
                )

    raise RuntimeError(
        f"Échec après {max_retries} tentative(s) "
        f"pour {target_date}: {last_error}"
    )


# ============================================================
# MISE À JOUR DU CHECKPOINT
# ============================================================

def mark_success(
    progress,
    target_date,
    result,
):
    progress[
        "last_completed_date"
    ] = target_date.isoformat()

    if result == "downloaded":
        progress[
            "successful_days"
        ] += 1

    elif result == "existing":
        progress[
            "existing_days"
        ] += 1

    target_string = target_date.isoformat()

    progress[
        "failed_dates"
    ] = [
        value
        for value in progress[
            "failed_dates"
        ]
        if value != target_string
    ]


def mark_failure(
    progress,
    target_date,
):
    progress[
        "failed_days"
    ] += 1

    target_string = target_date.isoformat()

    if (
        target_string
        not in progress["failed_dates"]
    ):
        progress[
            "failed_dates"
        ].append(
            target_string
        )


# ============================================================
# PROGRAMME PRINCIPAL
# ============================================================

def main():
    args = parse_arguments()

    validate_arguments(
        args
    )

    settings = get_feed_settings(
        args.feed
    )

    progress_file = get_progress_file(
        args.feed,
        args.start_date,
        args.end_date,
    )

    progress = load_progress(
        progress_file,
        args.feed,
        args.start_date,
        args.end_date,
    )

    resume_date = get_resume_date(
        progress,
        args.start_date,
    )

    print()
    print("=" * 60)
    print(
        f"QuantLab - Nasdaq Historical Collector V{VERSION}"
    )
    print("=" * 60)

    print()
    print(
        f"Flux : "
        f'{settings["display_name"]}'
    )

    print(
        f"Période cible : "
        f"{args.start_date} → {args.end_date}"
    )

    print(
        f"Dernière date complétée : "
        f"{progress.get('last_completed_date')}"
    )

    print(
        f"Prochaine date : "
        f"{resume_date}"
    )

    print(
        f"Délai entre dates : "
        f"{args.delay_seconds:g} secondes"
    )

    print(
        f"Tentatives maximales : "
        f"{args.max_retries}"
    )

    print(
        f"Checkpoint : "
        f"{progress_file}"
    )

    print(
        f"Répertoire RAW : "
        f'{settings["raw_directory"]}'
    )

    if resume_date > args.end_date:
        print()
        print("=" * 60)
        print(
            "COLLECTE DÉJÀ COMPLÈTE"
        )
        print("=" * 60)

        print(
            "Aucune nouvelle requête effectuée."
        )

        return

    current_date = resume_date

    session_downloaded = 0
    session_existing = 0
    session_failed = 0

    while current_date <= args.end_date:
        try:
            result = download_for_date(
                current_date,
                args.feed,
                args.max_retries,
                args.retry_delay_seconds,
            )

            if result == "downloaded":
                session_downloaded += 1

            elif result == "existing":
                session_existing += 1

            mark_success(
                progress,
                current_date,
                result,
            )

            save_progress(
                progress_file,
                progress,
            )

        except Exception as error:
            session_failed += 1

            mark_failure(
                progress,
                current_date,
            )

            save_progress(
                progress_file,
                progress,
            )

            print()
            print(
                f"ERREUR : {current_date}"
            )

            print(
                f"Détail : {error}"
            )

            print()
            print(
                "La collecte est interrompue."
            )

            print(
                "La prochaine exécution "
                "reprendra cette date."
            )

            break

        current_date += timedelta(
            days=1
        )

        if (
            result == "downloaded"
            and current_date <= args.end_date
        ):
            print()
            print(
                f"Pause de "
                f"{args.delay_seconds:g} secondes..."
            )

            time.sleep(
                args.delay_seconds
            )

    print()
    print("=" * 60)
    print(
        "COLLECTE TERMINÉE"
    )
    print("=" * 60)

    print(
        f"Flux : "
        f'{settings["display_name"]}'
    )

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

    print(
        f"Dernière date enregistrée : "
        f"{progress.get('last_completed_date')}"
    )

    print(
        f"Échecs cumulés : "
        f"{progress.get('failed_days')}"
    )

    print(
        f"Dates actuellement en échec : "
        f"{progress.get('failed_dates')}"
    )

    print(
        f"Checkpoint : "
        f"{progress_file}"
    )

    print(
        f"XML : "
        f'{settings["raw_directory"]}'
    )


if __name__ == "__main__":
    main()
