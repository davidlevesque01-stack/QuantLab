# ============================================================
# QUANTLAB - MARKET DATA PATH RESOLUTION
# ============================================================

import os
from pathlib import Path


ENV_RAW_DIRECTORY = "QUANTLAB_MARKET_DATA_RAW_DIRECTORY"


def resolve_raw_directory(base_dir, config):
    """
    Returns the RAW root for the market data collector.

    Priority:
        1. QUANTLAB_MARKET_DATA_RAW_DIRECTORY
        2. config["raw_directory"]

    The user path is never stored in Git.
    """
    configured = os.environ.get(ENV_RAW_DIRECTORY)

    if configured:
        return Path(configured).expanduser()

    return (
        Path(base_dir)
        / config["raw_directory"]
    )
