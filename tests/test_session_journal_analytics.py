import pytest

from services.session_journal_analytics import (
    SessionJournalAnalyticsEngine,
)


def make_entry(
    *,
    decision="NO_TRADE",
    direction="BEARISH",
    regime="TRENDING_BEARISH",
    confidence=70,
    risk_flags=None,
    timestamp=None,
):
    return {
        "decision": decision,
        "direction": direction,
        "regime": regime,
        "confidence": confidence,
        "risk_flags": (
            []
            if risk_flags is None
            else risk_flags
        ),
        "timestamp": timestamp,
    }


def make_engine():
    return SessionJournalAnalyticsEngine()


def test_none_entries_returns_empty_analysis():
    result = make_engine().analyze(
        None,
        session_date="2026-07-15",
    )

    assert (
        result[
            "total_cycles"
        ]
        == 0
    )

    assert (
        result[
            "trade_opportunity"
        ][
            "opportunity_rate_percent"
        ]
        == 0.0
    )


def test_invalid_entries_rejected():
    with pytest.raises(
        ValueError,
        match=(
            "entries must be a list or tuple"
        ),
    ):
        make_engine().analyze(
            {
                "decision": "NO_TRADE",
            }
        )


def test_non_dictionary_entries_are_ignored():
    result = make_engine().analyze(
        [
            None,
            "bad",
            123,
            make_entry(),
        ]
    )

    assert (
        result[
            "total_cycles"
        ]
        == 1
    )


def test_total_cycles_counted():
    result = make_engine().analyze(
        [
            make_entry(),
            make_entry(),
            make_entry(),
        ]
    )

    assert (
        result[
            "total_cycles"
        ]
        == 3
    )


def test_trade_ready_counted():
    result = make_engine().analyze(
        [
            make_entry(
                decision="NO_TRADE"
            ),
            make_entry(
                decision="TRADE_READY"
            ),
            make_entry(
                decision="NO_TRADE"
            ),
        ]
    )

    assert (
        result[
            "trade_opportunity"
        ][
            "trade_ready"
        ]
        == 1
    )


def test_trade_opportunity_rate_calculated():
    result = make_engine().analyze(
        [
            make_entry(
                decision="TRADE_READY"
            ),
            make_entry(
                decision="NO_TRADE"
            ),
            make_entry(
                decision="NO_TRADE"
            ),
            make_entry(
                decision="NO_TRADE"
            ),
        ]
    )

    assert (
        result[
            "trade_opportunity"
        ][
            "opportunity_rate_percent"
        ]
        == 25.0
    )


def test_decision_distribution_created():
    result = make_engine().analyze(
        [
            make_entry(
                decision="NO_TRADE"
            ),
            make_entry(
                decision="NO_TRADE"
            ),
            make_entry(
                decision="TRADE_READY"
            ),
        ]
    )

    assert (
        result[
            "decision_distribution"
        ]
        == {
            "NO_TRADE": 2,
            "TRADE_READY": 1,
        }
    )


def test_direction_distribution_created():
    result = make_engine().analyze(
        [
            make_entry(
                direction="BEARISH"
            ),
            make_entry(
                direction="BEARISH"
            ),
            make_entry(
                direction="BULLISH"
            ),
        ]
    )

    assert (
        result[
            "direction_distribution"
        ]
        == {
            "BEARISH": 2,
            "BULLISH": 1,
        }
    )


def test_regime_dictionary_supported():
    result = make_engine().analyze(
        [
            make_entry(
                regime={
                    "primary_regime": (
                        "TRENDING_BEARISH"
                    ),
                }
            ),
        ]
    )

    assert (
        result[
            "regime_distribution"
        ]
        == {
            "TRENDING_BEARISH": 1,
        }
    )


def test_risk_flags_counted():
    result = make_engine().analyze(
        [
            make_entry(
                risk_flags=[
                    "Weak volume",
                    "Conflicting patterns",
                ]
            ),
            make_entry(
                risk_flags=[
                    "Weak volume",
                ]
            ),
        ]
    )

    assert (
        result[
            "top_trade_blockers"
        ][
            "Weak volume"
        ]
        == 2
    )

    assert (
        result[
            "top_trade_blockers"
        ][
            "Conflicting patterns"
        ]
        == 1
    )


def test_string_risk_flag_supported():
    result = make_engine().analyze(
        [
            make_entry(
                risk_flags="Weak volume"
            ),
        ]
    )

    assert (
        result[
            "top_trade_blockers"
        ]
        == {
            "Weak volume": 1,
        }
    )


def test_direction_persistence_created():
    result = make_engine().analyze(
        [
            make_entry(
                direction="BEARISH"
            ),
            make_entry(
                direction="BEARISH"
            ),
            make_entry(
                direction="BEARISH"
            ),
            make_entry(
                direction="BULLISH"
            ),
            make_entry(
                direction="BULLISH"
            ),
        ]
    )

    assert (
        result[
            "direction_persistence"
        ][
            "BEARISH"
        ]
        == 3
    )

    assert (
        result[
            "direction_persistence"
        ][
            "BULLISH"
        ]
        == 2
    )


def test_non_consecutive_values_not_combined():
    result = make_engine().analyze(
        [
            make_entry(
                direction="BEARISH"
            ),
            make_entry(
                direction="BEARISH"
            ),
            make_entry(
                direction="BULLISH"
            ),
            make_entry(
                direction="BEARISH"
            ),
        ]
    )

    assert (
        result[
            "direction_persistence"
        ][
            "BEARISH"
        ]
        == 2
    )


def test_regime_persistence_created():
    result = make_engine().analyze(
        [
            make_entry(
                regime="RANGING"
            ),
            make_entry(
                regime="RANGING"
            ),
            make_entry(
                regime="RANGING"
            ),
        ]
    )

    assert (
        result[
            "regime_persistence"
        ][
            "RANGING"
        ]
        == 3
    )


def test_confidence_by_decision_created():
    result = make_engine().analyze(
        [
            make_entry(
                decision="NO_TRADE",
                confidence=60,
            ),
            make_entry(
                decision="NO_TRADE",
                confidence=80,
            ),
            make_entry(
                decision="TRADE_READY",
                confidence=90,
            ),
        ]
    )

    assert (
        result[
            "confidence_by_decision"
        ][
            "NO_TRADE"
        ][
            "average"
        ]
        == 70.0
    )

    assert (
        result[
            "confidence_by_decision"
        ][
            "TRADE_READY"
        ][
            "average"
        ]
        == 90.0
    )


def test_invalid_confidence_ignored():
    result = make_engine().analyze(
        [
            make_entry(
                confidence="bad"
            ),
        ]
    )

    assert (
        result[
            "confidence_by_decision"
        ]
        == {}
    )


def test_decision_transition_counted():
    result = make_engine().analyze(
        [
            make_entry(
                decision="NO_TRADE"
            ),
            make_entry(
                decision="NO_TRADE"
            ),
            make_entry(
                decision="TRADE_READY"
            ),
            make_entry(
                decision="NO_TRADE"
            ),
        ]
    )

    assert (
        result[
            "decision_transitions"
        ][
            "count"
        ]
        == 2
    )


def test_same_decision_is_not_transition():
    result = make_engine().analyze(
        [
            make_entry(
                decision="NO_TRADE"
            ),
            make_entry(
                decision="NO_TRADE"
            ),
        ]
    )

    assert (
        result[
            "decision_transitions"
        ][
            "count"
        ]
        == 0
    )


def test_trade_ready_event_created():
    result = make_engine().analyze(
        [
            make_entry(
                decision="NO_TRADE",
                timestamp=(
                    "2026-07-15T09:15:00+05:30"
                ),
            ),
            make_entry(
                decision="TRADE_READY",
                confidence=91,
                timestamp=(
                    "2026-07-15T09:16:00+05:30"
                ),
            ),
        ]
    )

    events = result[
        "trade_ready_events"
    ]

    assert len(
        events
    ) == 1

    assert (
        events[
            0
        ][
            "index"
        ]
        == 1
    )

    assert (
        events[
            0
        ][
            "confidence"
        ]
        == 91.0
    )


def test_trade_ready_event_contains_context():
    result = make_engine().analyze(
        [
            make_entry(
                decision="TRADE_READY",
                direction="BEARISH",
                regime="TRENDING_BEARISH",
                confidence=88,
            ),
        ]
    )

    event = result[
        "trade_ready_events"
    ][
        0
    ]

    assert (
        event[
            "direction"
        ]
        == "BEARISH"
    )

    assert (
        event[
            "regime"
        ]
        == "TRENDING_BEARISH"
    )


def test_session_date_preserved():
    result = make_engine().analyze(
        [],
        session_date="2026-07-15",
    )

    assert (
        result[
            "session_date"
        ]
        == "2026-07-15"
    )


def test_result_is_read_only():
    result = make_engine().analyze(
        []
    )

    assert (
        result[
            "read_only"
        ]
        is True
    )


def test_input_entries_not_modified():
    entries = [
        make_entry(
            risk_flags=[
                "Weak volume",
            ]
        ),
    ]

    original = [
        make_entry(
            risk_flags=[
                "Weak volume",
            ]
        ),
    ]

    make_engine().analyze(
        entries
    )

    assert entries == original