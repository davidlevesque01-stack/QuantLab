"""Central Nasdaq HALT / RESUMPTION reason-code reference for the UI.

Keep analytical HALT selectors separate from resumption action codes.
"""

ALL_REASON_CODE = "ALL"
DEFAULT_HALT_REASON_CODE = "LUDP"

# Codes currently exposed as normal HALT analytical selectors.
# T3 is intentionally excluded: it is a resumption/action code.
HALT_REASON_CODES = (
    "LUDP",
    "M",
    "T1",
    "T2",
    "T12",
    "D",
    "H11",
)

# Quick-reference descriptions shown by the UI.
# This table is informational; analytical selection is governed by
# HALT_REASON_CODES above.
HALT_REASON_REFERENCE = (
    ("LUDP", "Volatility Trading Pause", "HALT"),
    ("M", "Volatility Trading Pause / market-specific halt", "HALT"),
    ("T1", "News Pending", "HALT"),
    ("T2", "News Released", "HALT"),
    ("T5", "Single-stock trading pause in effect", "HALT"),
    ("T6", "Extraordinary market activity", "HALT"),
    ("T8", "Exchange-traded product halt", "HALT"),
    ("T12", "Additional information requested", "HALT"),
    ("H4", "Non-compliance", "HALT"),
    ("H9", "Filings not current", "HALT"),
    ("H10", "SEC trading suspension", "HALT"),
    ("H11", "Regulatory concern", "HALT"),
    ("O1", "Operations halt", "HALT"),
    ("IPO1", "IPO issue not yet trading", "HALT"),
    ("M1", "Corporate action", "HALT"),
    ("M2", "Quotation not available", "HALT"),
    ("LUDS", "Volatility pause — straddle condition", "HALT"),
    ("MWC1", "Market-wide circuit breaker level 1", "HALT"),
    ("MWC2", "Market-wide circuit breaker level 2", "HALT"),
    ("MWC3", "Market-wide circuit breaker level 3", "HALT"),
    ("MWC0", "Market-wide circuit breaker carry-over", "HALT"),
    ("D", "Security deletion / issue-specific action", "HALT"),
)

RESUMPTION_REASON_REFERENCE = (
    ("T3", "News and resumption times", "RESUMPTION"),
    ("T7", "Single-stock trading pause / quotation resumption", "RESUMPTION"),
    ("R4", "Qualifications issue resolved", "RESUMPTION"),
    ("R9", "Filings issue resolved", "RESUMPTION"),
    ("C3", "Issuer news / quotation resumption", "RESUMPTION"),
    ("C4", "Qualifications / quotation resumption", "RESUMPTION"),
    ("C9", "Filings / quotation resumption", "RESUMPTION"),
    ("C11", "Regulatory concern / quotation resumption", "RESUMPTION"),
    ("R1", "New issue available", "RESUMPTION"),
    ("R2", "Issue available for quotation", "RESUMPTION"),
    ("IPOQ", "IPO quotation release", "RESUMPTION"),
    ("IPOE", "IPO quotation-only period ended", "RESUMPTION"),
    ("MWCQ", "Market-wide circuit breaker quotation resumption", "RESUMPTION"),
)


def analytical_reason_choices() -> tuple[str, ...]:
    """Return the UI analytical choices in display order."""
    return (ALL_REASON_CODE, *HALT_REASON_CODES)
