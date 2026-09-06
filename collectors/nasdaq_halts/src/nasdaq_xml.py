from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET


NS = {
    "ndaq": "http://www.nasdaqtrader.com/"
}

SOURCE_TYPE_HALT = "halt"
SOURCE_TYPE_RESUMPTION = "resumption"

VALID_SOURCE_TYPES = {
    SOURCE_TYPE_HALT,
    SOURCE_TYPE_RESUMPTION,
}


def clean(value):
    if value is None:
        return None

    value = value.strip()

    if not value:
        return None

    return value


def parse_datetime(date_text, time_text):
    date_text = clean(date_text)
    time_text = clean(time_text)

    if not date_text or not time_text:
        return None

    time_text = time_text.replace(
        " ",
        ""
    )

    return datetime.fromisoformat(
        f"{datetime.strptime(date_text, '%m/%d/%Y').date()} "
        f"{time_text}"
    )


def get_field(item, field):
    node = item.find(
        f"ndaq:{field}",
        NS
    )

    if node is None:
        return None

    return clean(
        node.text
    )


def get_market(item):
    market = get_field(
        item,
        "Mkt"
    )

    if market:
        return market

    return get_field(
        item,
        "Market"
    )


def validate_source_type(source_type):
    if source_type not in VALID_SOURCE_TYPES:
        raise ValueError(
            "Unsupported Nasdaq XML source_type: "
            f"{source_type!r}. "
            "Expected 'halt' or 'resumption'."
        )


def parse_xml_root(
    root,
    source_file,
    source_type=SOURCE_TYPE_HALT,
):
    """
    Parse un flux Nasdaq Trade Halts.

    source_type='halt':
        ReasonCode -> reason_code

    source_type='resumption':
        ReasonCode -> resumption_reason_code

    Le sens de ReasonCode est donc déterminé par le type de
    requête Nasdaq ayant produit le XML, jamais par sa valeur.
    """

    validate_source_type(
        source_type
    )

    events = []

    for item in root.findall(
        ".//item"
    ):
        symbol = get_field(
            item,
            "IssueSymbol"
        )

        if not symbol:
            continue

        issue_name = get_field(
            item,
            "IssueName"
        )

        market = get_market(
            item
        )

        source_reason_code = get_field(
            item,
            "ReasonCode"
        )

        if source_type == SOURCE_TYPE_RESUMPTION:
            reason_code = None
            resumption_reason_code = source_reason_code
        else:
            reason_code = source_reason_code
            resumption_reason_code = None

        pause_threshold = get_field(
            item,
            "PauseThresholdPrice"
        )

        halt_date = get_field(
            item,
            "HaltDate"
        )

        halt_time = get_field(
            item,
            "HaltTime"
        )

        resumption_date = get_field(
            item,
            "ResumptionDate"
        )

        resumption_quote_time = get_field(
            item,
            "ResumptionQuoteTime"
        )

        resumption_trade_time = get_field(
            item,
            "ResumptionTradeTime"
        )

        halt_start = parse_datetime(
            halt_date,
            halt_time
        )

        resumption_time = (
            resumption_trade_time
            or resumption_quote_time
        )

        halt_end = parse_datetime(
            resumption_date,
            resumption_time
        )

        events.append(
            {
                "symbol": symbol,
                "issue_name": issue_name,
                "market": market,
                "reason_code": reason_code,
                "resumption_reason_code":
                    resumption_reason_code,
                "halt_date": halt_date,
                "halt_time": halt_time,
                "resumption_date":
                    resumption_date,
                "resumption_quote_time":
                    resumption_quote_time,
                "resumption_trade_time":
                    resumption_trade_time,
                "pause_threshold_price":
                    pause_threshold,
                "halt_start": halt_start,
                "halt_end": halt_end,
                "source_file": source_file,
                "source_type": source_type,
            }
        )

    return events


def parse_xml_file(
    xml_file,
    source_type=SOURCE_TYPE_HALT,
):
    xml_file = Path(
        xml_file
    )

    tree = ET.parse(
        xml_file
    )

    return parse_xml_root(
        tree.getroot(),
        xml_file.name,
        source_type=source_type,
    )


def parse_xml_bytes(
    xml_data,
    source_file,
    source_type=SOURCE_TYPE_HALT,
):
    root = ET.fromstring(
        xml_data
    )

    return parse_xml_root(
        root,
        source_file,
        source_type=source_type,
    )
