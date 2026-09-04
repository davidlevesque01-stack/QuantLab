# ============================================================
# QUANTLAB - NASDAQ PATH RESOLUTION
# ============================================================

import os
from pathlib import Path


ENV_RAW_DIRECTORY = "QUANTLAB_NASDAQ_RAW_DIRECTORY"


def resolve_raw_directory(base_dir, config):
    """
    Retourne la racine RAW du collector Nasdaq.

    Priorité :
        1. QUANTLAB_NASDAQ_RAW_DIRECTORY
        2. config["raw_directory"]

    Le chemin utilisateur n'est jamais stocké dans Git.
    """
    configured = os.environ.get(ENV_RAW_DIRECTORY)

    if configured:
        return Path(configured).expanduser()

    return (
        Path(base_dir)
        / config["raw_directory"]
    )
