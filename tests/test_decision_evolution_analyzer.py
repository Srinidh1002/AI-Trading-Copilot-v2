import pytest

from services.decision_evolution_analyzer import (
    DecisionEvolutionAnalyzer,
)


def make_entry(
    *,
    decision="NO_TRADE",
    direction="BEARISH",
    regime="TRENDING_BEARISH",
    confidence=70,
    timestamp=None,
):
    return {
        "decision": decision,
        "direction": direction,
        "regime": regime,
        "confidence": confidence,
        "timestamp": timestamp,
    }


def make_analyzer():
    return DecisionEvolutionAnalyzer()


def test_none_entries_returns_empty_analysis():
    result = make_analyzer().analyze(
        None,
        session_date="2026-07-15",
    )

    assert (
        result[
            "cycles_observed"
        ]
        == 0
    )

    assert (
        result[
            "confidence"
        ][
            "trend"
        ]
        == "UNAVAILABLE"
    )


def test_invalid_entries_rejected():
    with pytest.raises(
        ValueError,
        match=(
            "entries must be a list or tuple"
        ),
    ):
        make_analyzer().analyze(
            {
                "decision": "NO_TRADE",
            }
        )


def test_non_dictionary_entries_ignored():
    result = make_analyzer().analyze(
        [
            None,
            "bad",
            123,
            make_entry(),
        ]
    )

    assert (
        result[
            "cycles_observed"
        ]
        == 1
    )


def test_rising_confidence_detected():
    result = make_analyzer().analyze(
        [
            make_entry(
                confidence=60
            ),
            make_entry(
                confidence=70
            ),
            make_entry(
                confidence=80
            ),
        ]
    )

    assert (
        result[
            "confidence"
        ][
            "trend"
        ]
        == "RISING"
    )


def test_falling_confidence_detected():
    result = make_analyzer().analyze(
        [
            make_entry(
                confidence=80
            ),
            make_entry(
                confidence=70
            ),
            make_entry(
                confidence=60
            ),
        ]
    )

    assert (
        result[
            "confidence"
        ][
            "trend"
        ]
        == "FALLING"
    )


def test_flat_confidence_detected():
    result = make_analyzer().analyze(
        [
            make_entry(
                confidence=70
            ),
            make_entry(
                confidence=70
            ),
            make_entry(
                confidence=70
            ),
        ]
    )

    assert (
        result[
            "confidence"
        ][
            "trend"
        ]
        == "FLAT"
    )


def test_mixed_confidence_detected():
    result = make_analyzer().analyze(
        [
            make_entry(
                confidence=60
            ),
            make_entry(
                confidence=80
            ),
            make_entry(
                confidence=70
            ),
        ]
    )

    assert (
        result[
            "confidence"
        ][
            "trend"
        ]
        == "MIXED"
    )


def test_single_confidence_is_unavailable_trend():
    result = make_analyzer().analyze(
        [
            make_entry(
                confidence=70
            ),
        ]
    )

    assert (
        result[
            "confidence"
        ][
            "trend"
        ]
        == "UNAVAILABLE"
    )


def test_confidence_change_calculated():
    result = make_analyzer().analyze(
        [
            make_entry(
                confidence=60
            ),
            make_entry(
                confidence=85
            ),
        ]
    )

    assert (
        result[
            "confidence"
        ][
            "change"
        ]
        == 25.0
    )


def test_longest_increase_sequence_calculated():
    result = make_analyzer().analyze(
        [
            make_entry(
                confidence=60
            ),
            make_entry(
                confidence=65
            ),
            make_entry(
                confidence=70
            ),
            make_entry(
                confidence=75
            ),
            make_entry(
                confidence=70
            ),
        ]
    )

    assert (
        result[
            "confidence"
        ][
            "longest_increase_sequence"
        ]
        == 3
    )


def test_longest_decrease_sequence_calculated():
    result = make_analyzer().analyze(
        [
            make_entry(
                confidence=90
            ),
            make_entry(
                confidence=80
            ),
            make_entry(
                confidence=70
            ),
            make_entry(
                confidence=75
            ),
        ]
    )

    assert (
        result[
            "confidence"
        ][
            "longest_decrease_sequence"
        ]
        == 2
    )


def test_direction_stable_when_unchanged():
    result = make_analyzer().analyze(
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
        ]
    )

    assert (
        result[
            "direction_stability"
        ][
            "stable"
        ]
        is True
    )

    assert (
        result[
            "direction_stability"
        ][
            "changes"
        ]
        == 0
    )


def test_direction_change_counted():
    result = make_analyzer().analyze(
        [
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
            "direction_stability"
        ][
            "changes"
        ]
        == 2
    )


def test_regime_stability_created():
    result = make_analyzer().analyze(
        [
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
            "regime_stability"
        ][
            "stable"
        ]
        is True
    )


def test_regime_dictionary_supported():
    result = make_analyzer().analyze(
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
            "final_state"
        ][
            "regime"
        ]
        == "TRENDING_BEARISH"
    )


def test_decision_evolution_removes_duplicates():
    result = make_analyzer().analyze(
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
                decision="TRADE_READY"
            ),
            make_entry(
                decision="NO_TRADE"
            ),
        ]
    )

    assert (
        result[
            "decision_evolution"
        ]
        == [
            "NO_TRADE",
            "TRADE_READY",
            "NO_TRADE",
        ]
    )


def test_decision_stability_change_counted():
    result = make_analyzer().analyze(
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
            "decision_stability"
        ][
            "changes"
        ]
        == 2
    )


def test_peak_confidence_created():
    result = make_analyzer().analyze(
        [
            make_entry(
                confidence=60,
                timestamp="T1",
            ),
            make_entry(
                confidence=95,
                timestamp="T2",
            ),
            make_entry(
                confidence=80,
                timestamp="T3",
            ),
        ]
    )

    assert (
        result[
            "confidence"
        ][
            "peak"
        ]
        == {
            "value": 95.0,
            "index": 1,
            "timestamp": "T2",
        }
    )


def test_lowest_confidence_created():
    result = make_analyzer().analyze(
        [
            make_entry(
                confidence=60,
                timestamp="T1",
            ),
            make_entry(
                confidence=95,
                timestamp="T2",
            ),
        ]
    )

    assert (
        result[
            "confidence"
        ][
            "lowest"
        ][
            "value"
        ]
        == 60.0
    )


def test_invalid_confidence_ignored():
    result = make_analyzer().analyze(
        [
            make_entry(
                confidence="bad"
            ),
            make_entry(
                confidence=80
            ),
        ]
    )

    assert (
        result[
            "confidence"
        ][
            "observations"
        ]
        == 1
    )


def test_boolean_confidence_ignored():
    result = make_analyzer().analyze(
        [
            make_entry(
                confidence=True
            ),
        ]
    )

    assert (
        result[
            "confidence"
        ][
            "observations"
        ]
        == 0
    )


def test_strategy_confidence_supported():
    entry = make_entry(
        confidence=None
    )

    entry[
        "strategy"
    ] = {
        "confidence": 88,
    }

    result = make_analyzer().analyze(
        [
            entry,
        ]
    )

    assert (
        result[
            "confidence"
        ][
            "first"
        ]
        == 88.0
    )


def test_final_state_created():
    result = make_analyzer().analyze(
        [
            make_entry(
                decision="NO_TRADE",
                direction="BEARISH",
                confidence=70,
            ),
            make_entry(
                decision="TRADE_READY",
                direction="BEARISH",
                regime="TRENDING_BEARISH",
                confidence=90,
                timestamp="FINAL",
            ),
        ]
    )

    assert (
        result[
            "final_state"
        ]
        == {
            "decision": "TRADE_READY",
            "direction": "BEARISH",
            "regime": "TRENDING_BEARISH",
            "confidence": 90.0,
            "timestamp": "FINAL",
        }
    )


def test_empty_final_state():
    result = make_analyzer().analyze(
        []
    )

    assert (
        result[
            "final_state"
        ][
            "decision"
        ]
        is None
    )


def test_session_date_preserved():
    result = make_analyzer().analyze(
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
    result = make_analyzer().analyze(
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
            confidence=70
        ),
    ]

    original = [
        make_entry(
            confidence=70
        ),
    ]

    make_analyzer().analyze(
        entries
    )

    assert entries == original


def test_direction_confidence_takes_priority_over_legacy_confidence():

    entry = make_entry(
        confidence=20
    )

    entry[
        "direction_confidence"
    ] = 88

    result = make_analyzer().analyze(
        [
            entry,
        ]
    )

    assert (
        result[
            "confidence"
        ][
            "first"
        ]
        == 88.0
    )


def test_legacy_confidence_fallback_remains_supported():

    entry = make_entry(
        confidence=73
    )

    result = make_analyzer().analyze(
        [
            entry,
        ]
    )

    assert (
        result[
            "confidence"
        ][
            "first"
        ]
        == 73.0
    )