"""
Tests for the decision audit-trail service.
"""

import pytest

from services.decision_audit_trail import (
    DecisionAuditTrail,
)


def fixed_timestamp():
    return "2026-07-12T10:00:00+00:00"


def make_audit():
    return DecisionAuditTrail(
        timestamp_factory=fixed_timestamp,
    )


def test_new_audit_trail_is_empty():

    audit = make_audit()

    assert audit.get_events() == []
    assert audit.latest_event() is None


def test_record_creates_structured_event():

    audit = make_audit()

    event = audit.record(
        stage="market_session",
        status="passed",
        decision="market_open",
        reasons=[
            "Market is open."
        ],
        details={
            "exchange": "NSE",
        },
    )

    assert event["sequence"] == 1

    assert (
        event["timestamp"]
        == "2026-07-12T10:00:00+00:00"
    )

    assert (
        event["stage"]
        == "MARKET_SESSION"
    )

    assert (
        event["status"]
        == "PASSED"
    )

    assert (
        event["decision"]
        == "MARKET_OPEN"
    )

    assert event["reasons"] == [
        "Market is open."
    ]

    assert event["details"] == {
        "exchange": "NSE",
    }


def test_sequence_increments():

    audit = make_audit()

    first = audit.record(
        stage="market_analysis",
        status="completed",
    )

    second = audit.record(
        stage="option_chain",
        status="completed",
    )

    assert first["sequence"] == 1
    assert second["sequence"] == 2


def test_reasons_accept_single_string():

    audit = make_audit()

    event = audit.record(
        stage="risk_plan",
        status="blocked",
        reasons="Risk limit exceeded.",
    )

    assert event["reasons"] == [
        "Risk limit exceeded."
    ]


def test_empty_reasons_are_removed():

    audit = make_audit()

    event = audit.record(
        stage="market_analysis",
        status="completed",
        reasons=[
            None,
            "",
            "   ",
            "Valid reason.",
        ],
    )

    assert event["reasons"] == [
        "Valid reason."
    ]


def test_details_must_be_dictionary():

    audit = make_audit()

    with pytest.raises(
        TypeError,
        match=(
            "Audit event details must "
            "be a dictionary"
        ),
    ):
        audit.record(
            stage="market_analysis",
            status="completed",
            details=[
                "invalid"
            ],
        )


def test_record_returns_copy():

    audit = make_audit()

    event = audit.record(
        stage="contract_selection",
        status="completed",
        details={
            "symbol": "NIFTYCE",
        },
    )

    event["details"][
        "symbol"
    ] = "MUTATED"

    stored = audit.latest_event()

    assert (
        stored["details"]["symbol"]
        == "NIFTYCE"
    )


def test_get_events_returns_copy():

    audit = make_audit()

    audit.record(
        stage="market_analysis",
        status="completed",
    )

    events = audit.get_events()

    events[0][
        "stage"
    ] = "MUTATED"

    stored = audit.get_events()

    assert (
        stored[0]["stage"]
        == "MARKET_ANALYSIS"
    )


def test_latest_event_returns_latest_record():

    audit = make_audit()

    audit.record(
        stage="market_analysis",
        status="completed",
    )

    audit.record(
        stage="final_decision",
        status="completed",
        decision="trade_allowed",
    )

    latest = audit.latest_event()

    assert (
        latest["stage"]
        == "FINAL_DECISION"
    )

    assert (
        latest["decision"]
        == "TRADE_ALLOWED"
    )


def test_clear_removes_all_events():

    audit = make_audit()

    audit.record(
        stage="market_analysis",
        status="completed",
    )

    audit.clear()

    assert audit.get_events() == []
    assert audit.latest_event() is None


def test_build_summary_uses_latest_decision():

    audit = make_audit()

    audit.record(
        stage="market_analysis",
        status="completed",
        decision="no_trade",
    )

    audit.record(
        stage="final_decision",
        status="completed",
        decision="waiting_for_breakout",
    )

    summary = audit.build_summary()

    assert (
        summary["final_decision"]
        == "WAITING_FOR_BREAKOUT"
    )

    assert (
        summary["event_count"]
        == 2
    )

    assert (
        len(
            summary["events"]
        )
        == 2
    )


def test_build_summary_accepts_explicit_final_decision():

    audit = make_audit()

    audit.record(
        stage="market_analysis",
        status="completed",
    )

    summary = audit.build_summary(
        final_decision="trade_rejected"
    )

    assert (
        summary["final_decision"]
        == "TRADE_REJECTED"
    )

    assert (
        summary["event_count"]
        == 1
    )


def test_build_summary_on_empty_trail():

    audit = make_audit()

    summary = audit.build_summary()

    assert (
        summary["final_decision"]
        is None
    )

    assert (
        summary["event_count"]
        == 0
    )

    assert (
        summary["events"]
        == []
    )