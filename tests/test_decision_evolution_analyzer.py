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
def test_candidate_momentum_rising():

    entries = [
        make_entry(
            confidence=70,
            timestamp=(
                "2026-07-16T09:20:00+05:30"
            ),
        ),
        make_entry(
            confidence=72,
            timestamp=(
                "2026-07-16T09:25:00+05:30"
            ),
        ),
        make_entry(
            confidence=75,
            timestamp=(
                "2026-07-16T09:30:00+05:30"
            ),
        ),
        make_entry(
            confidence=80,
            timestamp=(
                "2026-07-16T09:35:00+05:30"
            ),
        ),
    ]

    scores = [
        60,
        70,
        85,
        95,
    ]

    for entry, score in zip(
        entries,
        scores,
    ):
        entry[
            "trade_candidate_score"
        ] = score

    result = make_analyzer().analyze(
        entries,
        session_date="2026-07-16",
    )

    momentum = result[
        "candidate_momentum"
    ]

    assert momentum["observations"] == 4
    assert momentum["trend"] == "RISING"
    assert momentum["first"] == 60.0
    assert momentum["final"] == 95.0
    assert momentum["change"] == 35.0

    assert (
        momentum[
            "longest_increase_sequence"
        ]
        == 3
    )

    assert (
        momentum[
            "longest_decrease_sequence"
        ]
        == 0
    )

    assert momentum["peak"] == {
        "value": 95.0,
        "index": 3,
        "timestamp": (
            "2026-07-16T09:35:00+05:30"
        ),
    }

    assert momentum["lowest"] == {
        "value": 60.0,
        "index": 0,
        "timestamp": (
            "2026-07-16T09:20:00+05:30"
        ),
    }


def test_candidate_momentum_falling():

    entries = [
        make_entry(),
        make_entry(),
        make_entry(),
        make_entry(),
    ]

    scores = [
        95,
        85,
        70,
        60,
    ]

    for entry, score in zip(
        entries,
        scores,
    ):
        entry[
            "trade_candidate_score"
        ] = score

    result = make_analyzer().analyze(
        entries
    )

    momentum = result[
        "candidate_momentum"
    ]

    assert momentum["trend"] == "FALLING"
    assert momentum["first"] == 95.0
    assert momentum["final"] == 60.0
    assert momentum["change"] == -35.0

    assert (
        momentum[
            "longest_increase_sequence"
        ]
        == 0
    )

    assert (
        momentum[
            "longest_decrease_sequence"
        ]
        == 3
    )


def test_candidate_momentum_mixed():

    entries = [
        make_entry(),
        make_entry(),
        make_entry(),
        make_entry(),
    ]

    scores = [
        80,
        85,
        80,
        85,
    ]

    for entry, score in zip(
        entries,
        scores,
    ):
        entry[
            "trade_candidate_score"
        ] = score

    result = make_analyzer().analyze(
        entries
    )

    momentum = result[
        "candidate_momentum"
    ]

    assert momentum["trend"] == "MIXED"
    assert momentum["first"] == 80.0
    assert momentum["final"] == 85.0
    assert momentum["change"] == 5.0

    assert (
        momentum[
            "longest_increase_sequence"
        ]
        == 1
    )

    assert (
        momentum[
            "longest_decrease_sequence"
        ]
        == 1
    )


def test_candidate_momentum_unavailable():

    entries = [
        make_entry(),
    ]

    result = make_analyzer().analyze(
        entries
    )

    momentum = result[
        "candidate_momentum"
    ]

    assert momentum == {
        "observations": 0,
        "trend": "UNAVAILABLE",
        "first": None,
        "final": None,
        "change": None,
        "longest_increase_sequence": 0,
        "longest_decrease_sequence": 0,
        "peak": {
            "value": None,
            "index": None,
            "timestamp": None,
        },
        "lowest": {
            "value": None,
            "index": None,
            "timestamp": None,
        },
        "series": [],
    }


def test_candidate_score_nested_research_fallback():

    entries = [
        make_entry(
            timestamp=(
                "2026-07-16T09:20:00+05:30"
            ),
        ),
        make_entry(
            timestamp=(
                "2026-07-16T09:25:00+05:30"
            ),
        ),
    ]

    entries[0][
        "trade_candidate_research"
    ] = {
        "trade_candidate_score": 70,
    }

    entries[1][
        "trade_candidate_research"
    ] = {
        "trade_candidate_score": 85,
    }

    result = make_analyzer().analyze(
        entries
    )

    momentum = result[
        "candidate_momentum"
    ]

    assert momentum["observations"] == 2
    assert momentum["trend"] == "RISING"
    assert momentum["first"] == 70.0
    assert momentum["final"] == 85.0
    assert momentum["change"] == 15.0

def test_trigger_approach_closing_and_accelerating():

    entries = [
        make_entry(),
        make_entry(),
        make_entry(),
        make_entry(),
    ]

    distances = [
        1.00,
        0.80,
        0.50,
        0.05,
    ]

    for entry, distance in zip(
        entries,
        distances,
    ):
        entry[
            "distance_to_trigger_percent"
        ] = distance

    result = make_analyzer().analyze(
        entries
    )

    approach = result[
        "trigger_approach"
    ]

    assert approach["observations"] == 4

    assert (
        approach["approach_trend"]
        == "CLOSING"
    )

    assert (
        approach["approach_speed"]
        == "ACCELERATING"
    )

    assert (
        approach["first_distance_percent"]
        == 1.0
    )

    assert (
        approach["final_distance_percent"]
        == 0.05
    )

    assert (
        approach["distance_change_percent"]
        == -0.95
    )

    assert (
        approach[
            "total_distance_closed_percent"
        ]
        == 0.95
    )

    assert approach["closing_steps"] == [
        0.2,
        0.3,
        0.45,
    ]


def test_trigger_approach_closing_and_slowing():

    entries = [
        make_entry(),
        make_entry(),
        make_entry(),
        make_entry(),
    ]

    distances = [
        1.00,
        0.50,
        0.20,
        0.05,
    ]

    for entry, distance in zip(
        entries,
        distances,
    ):
        entry[
            "distance_to_trigger_percent"
        ] = distance

    result = make_analyzer().analyze(
        entries
    )

    approach = result[
        "trigger_approach"
    ]

    assert (
        approach["approach_trend"]
        == "CLOSING"
    )

    assert (
        approach["approach_speed"]
        == "SLOWING"
    )

    assert approach["closing_steps"] == [
        0.5,
        0.3,
        0.15,
    ]


def test_trigger_approach_moving_away():

    entries = [
        make_entry(),
        make_entry(),
        make_entry(),
        make_entry(),
    ]

    distances = [
        0.05,
        0.20,
        0.45,
        0.80,
    ]

    for entry, distance in zip(
        entries,
        distances,
    ):
        entry[
            "distance_to_trigger_percent"
        ] = distance

    result = make_analyzer().analyze(
        entries
    )

    approach = result[
        "trigger_approach"
    ]

    assert (
        approach["approach_trend"]
        == "MOVING_AWAY"
    )

    assert (
        approach["approach_speed"]
        == "UNAVAILABLE"
    )

    assert approach["closing_steps"] == []

    assert (
        approach[
            "total_distance_closed_percent"
        ]
        == -0.75
    )


def test_trigger_approach_mixed():

    entries = [
        make_entry(),
        make_entry(),
        make_entry(),
        make_entry(),
    ]

    distances = [
        0.20,
        0.25,
        0.18,
        0.22,
    ]

    for entry, distance in zip(
        entries,
        distances,
    ):
        entry[
            "distance_to_trigger_percent"
        ] = distance

    result = make_analyzer().analyze(
        entries
    )

    approach = result[
        "trigger_approach"
    ]

    assert (
        approach["approach_trend"]
        == "MIXED"
    )

    assert (
        approach["approach_speed"]
        == "UNAVAILABLE"
    )

    assert approach["closing_steps"] == [
        0.07,
    ]


def test_trigger_approach_unavailable():

    entries = [
        make_entry(),
    ]

    result = make_analyzer().analyze(
        entries
    )

    approach = result[
        "trigger_approach"
    ]

    assert approach == {
        "observations": 0,
        "approach_trend": "UNAVAILABLE",
        "approach_speed": "UNAVAILABLE",
        "first_distance_percent": None,
        "final_distance_percent": None,
        "distance_change_percent": None,
        "total_distance_closed_percent": None,
        "closing_steps": [],
        "series": [],
    }


def test_trigger_approach_nested_setup_fallback():

    entries = [
        make_entry(
            timestamp=(
                "2026-07-16T09:20:00+05:30"
            ),
        ),
        make_entry(
            timestamp=(
                "2026-07-16T09:25:00+05:30"
            ),
        ),
        make_entry(
            timestamp=(
                "2026-07-16T09:30:00+05:30"
            ),
        ),
    ]

    distances = [
        0.80,
        0.45,
        0.20,
    ]

    for entry, distance in zip(
        entries,
        distances,
    ):
        entry["setup_trigger"] = {
            "distance_to_trigger_percent": (
                distance
            ),
        }

    result = make_analyzer().analyze(
        entries
    )

    approach = result[
        "trigger_approach"
    ]

    assert approach["observations"] == 3

    assert (
        approach["approach_trend"]
        == "CLOSING"
    )

    assert approach["series"][0] == {
        "index": 0,
        "timestamp": (
            "2026-07-16T09:20:00+05:30"
        ),
        "distance_to_trigger_percent": 0.8,
    }

    assert approach["series"][-1] == {
        "index": 2,
        "timestamp": (
            "2026-07-16T09:30:00+05:30"
        ),
        "distance_to_trigger_percent": 0.2,
    }


def test_trigger_approach_rejects_negative_distance():

    entries = [
        make_entry(),
        make_entry(),
    ]

    entries[0][
        "distance_to_trigger_percent"
    ] = -0.10

    entries[1][
        "distance_to_trigger_percent"
    ] = 0.20

    result = make_analyzer().analyze(
        entries
    )

    approach = result[
        "trigger_approach"
    ]

    assert approach["observations"] == 1

    assert (
        approach["approach_trend"]
        == "UNAVAILABLE"
    )
