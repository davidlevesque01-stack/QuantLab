# ============================================================
# QUANTLAB - NASDAQ HALT DEDUPLICATION
# VERSION 0.8
# ============================================================

VERSION = "0.8"


def deduplicate_events(events):
    """
    Déduplique les événements Nasdaq selon la logique
    historique validée de calculate_halt_metrics.py V0.7.

    Clé de déduplication :

        symbol
        halt_start
        resumption_date
        resumption_trade_time
        reason_code

    En cas de doublon, le dernier événement rencontré
    est conservé.

    Cette logique reproduit volontairement la V0.7.
    Une stratégie distincte sera utilisée pour gérer
    l'évolution des événements dans le flux live.
    """

    unique_events_dict = {}

    for event in events:

        key = (
            event["symbol"],
            event["halt_start"],
            event["resumption_date"],
            event["resumption_trade_time"],
            event["reason_code"],
        )

        unique_events_dict[
            key
        ] = event

    return list(
        unique_events_dict.values()
    )
