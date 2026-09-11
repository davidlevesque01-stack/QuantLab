"""SEC EDGAR HTTP client helpers."""

from __future__ import annotations

import json
from urllib.request import Request, urlopen


def fetch_json(
    url,
    *,
    user_agent,
    timeout_seconds=30,
):
    """
    Récupère et parse une ressource JSON depuis SEC EDGAR.

    SEC exige un User-Agent identifiant l'appelant (nom + contact) pour tout
    accès automatisé — voir https://www.sec.gov/os/webmaster-faq#developers.
    """

    request = Request(
        url,
        headers={
            "User-Agent": user_agent,
        },
    )

    with urlopen(
        request,
        timeout=timeout_seconds,
    ) as response:

        return json.loads(response.read())
