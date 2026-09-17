import pytest

from tests.test_scheduled_market_event_v1 import make


@pytest.mark.parametrize(
    ("category", "severity", "identities", "exchanges", "override", "entry_allowed"),
    (
        ("RBI_POLICY", "HIGH", (), (), "NONE", True),
        ("CPI", "LOW", (), (), "NONE", True),
        ("WPI", "MODERATE", (), (), "NONE", True),
        ("GDP", "MODERATE", (), (), "NONE", True),
        ("UNION_BUDGET", "EXTREME", (("BANKNIFTY", "NSE"), ("FINNIFTY", "NSE"), ("NIFTY", "NSE"), ("SENSEX", "BSE")), ("BSE", "NSE"), "NONE", True),
        ("ELECTION", "HIGH", (), (), "NONE", True),
        ("EXCHANGE_HOLIDAY", "LOW", (), ("NSE",), "MARKET_CLOSED", False),
        ("EXCHANGE_HOLIDAY", "LOW", (), ("BSE",), "MARKET_CLOSED", False),
        ("EXCHANGE_HOLIDAY", "LOW", (), ("BSE", "NSE"), "MARKET_CLOSED", False),
        ("SPECIAL_SESSION", "MODERATE", (), ("NSE",), "SPECIAL_SESSION", True),
        ("WEEKLY_EXPIRY", "MODERATE", (("NIFTY", "NSE"),), ("NSE",), "NONE", True),
        ("MONTHLY_EXPIRY", "MODERATE", (("SENSEX", "BSE"),), ("BSE",), "NONE", True),
        ("ROLLOVER", "MODERATE", (("NIFTY", "NSE"),), ("NSE",), "NONE", True),
        ("OTHER_SCHEDULED_MACRO", "LOW", (), (), "NONE", True),
    ),
)
def test_category_matrix(category, severity, identities, exchanges, override, entry_allowed):
    assert make(
        event_category=category,
        severity=severity,
        affected_market_identities=identities,
        affected_exchanges=exchanges,
        session_override_state=override,
        new_entries_allowed=entry_allowed,
    )


@pytest.mark.parametrize(
    "changes",
    (
        {"event_category": "EXCHANGE_HOLIDAY", "affected_exchanges": (), "session_override_state": "MARKET_CLOSED", "new_entries_allowed": False},
        {"event_category": "EXCHANGE_HOLIDAY", "affected_exchanges": ("NSE",), "session_override_state": "NONE", "new_entries_allowed": False},
        {"event_category": "SPECIAL_SESSION", "affected_exchanges": (), "session_override_state": "SPECIAL_SESSION"},
        {"event_category": "WEEKLY_EXPIRY", "affected_exchanges": ("NSE",), "session_override_state": "NONE"},
        {"event_category": "ROLLOVER", "session_override_state": "NONE"},
        {"event_category": "CPI", "session_override_state": "MARKET_CLOSED"},
        {"event_category": "RBI_POLICY", "severity": "LOW"},
        {"event_category": "INVALID"},
        {"severity": "INVALID"},
        {"event_status": "INVALID"},
        {"confirmation_state": "INVALID"},
    ),
)
def test_invalid_category_and_state_combinations_are_rejected(changes):
    with pytest.raises(ValueError):
        make(**changes)


def test_tentative_election_and_unavailable_severity_do_not_create_policy_block():
    assert make(
        event_category="ELECTION",
        confirmation_state="TENTATIVE",
        warnings=("Election schedule remains provisional",),
    )
    assert make(severity="UNAVAILABLE")
