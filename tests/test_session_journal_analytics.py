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


def test_direction_confidence_takes_priority_over_legacy_confidence():

    entry = make_entry(
        decision="NO_TRADE",
        confidence=20,
    )

    entry[
        "direction_confidence"
    ] = 88

    result = make_engine().analyze(
        [
            entry,
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
        == 88.0
    )


def test_legacy_confidence_fallback_remains_supported():

    entry = make_entry(
        decision="NO_TRADE",
        confidence=73,
    )

    result = make_engine().analyze(
        [
            entry,
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
        == 73.0
    )


def test_evidence_strength_by_decision_uses_top_level_score():

    entry = make_entry(
        decision="NO_TRADE",
        confidence=80,
    )

    entry[
        "evidence_strength_score"
    ] = 47

    result = make_engine().analyze(
        [
            entry,
        ]
    )

    assert (
        result[
            "evidence_strength_by_decision"
        ][
            "NO_TRADE"
        ]
        == {
            "observations": 1,
            "average": 47.0,
            "minimum": 47.0,
            "maximum": 47.0,
        }
    )


def test_evidence_strength_uses_nested_strategy_fallback():

    entry = make_entry(
        decision="TRADE_REJECTED",
        confidence=90,
    )

    entry[
        "strategy"
    ] = {
        "evidence_strength_score": 73,
    }

    result = make_engine().analyze(
        [
            entry,
        ]
    )

    assert (
        result[
            "evidence_strength_by_decision"
        ][
            "TRADE_REJECTED"
        ][
            "average"
        ]
        == 73.0
    )


def test_top_level_evidence_strength_takes_priority():

    entry = make_entry(
        decision="NO_TRADE",
        confidence=80,
    )

    entry[
        "evidence_strength_score"
    ] = 47

    entry[
        "strategy"
    ] = {
        "evidence_strength_score": 93,
    }

    result = make_engine().analyze(
        [
            entry,
        ]
    )

    assert (
        result[
            "evidence_strength_by_decision"
        ][
            "NO_TRADE"
        ][
            "average"
        ]
        == 47.0
    )


def test_invalid_evidence_strength_is_ignored():

    entries = []

    for value in [
        None,
        True,
        "INVALID",
    ]:
        entry = make_entry(
            decision="NO_TRADE",
            confidence=80,
        )

        entry[
            "evidence_strength_score"
        ] = value

        entries.append(
            entry
        )

    result = make_engine().analyze(
        entries
    )

    assert (
        result[
            "evidence_strength_by_decision"
        ]
        == {}
    )


def test_evidence_strength_statistics_group_by_decision():

    first = make_entry(
        decision="NO_TRADE",
        confidence=80,
    )

    first[
        "evidence_strength_score"
    ] = 40

    second = make_entry(
        decision="NO_TRADE",
        confidence=90,
    )

    second[
        "evidence_strength_score"
    ] = 60

    third = make_entry(
        decision="TRADE_READY",
        confidence=95,
    )

    third[
        "evidence_strength_score"
    ] = 90

    result = make_engine().analyze(
        [
            first,
            second,
            third,
        ]
    )

    assert (
        result[
            "evidence_strength_by_decision"
        ][
            "NO_TRADE"
        ]
        == {
            "observations": 2,
            "average": 50.0,
            "minimum": 40.0,
            "maximum": 60.0,
        }
    )

    assert (
        result[
            "evidence_strength_by_decision"
        ][
            "TRADE_READY"
        ][
            "average"
        ]
        == 90.0
    )
def test_setup_formation_research_correlates_evidence_and_maturity():

    entries = [
        {
            **make_entry(
                decision="NO_TRADE",
                timestamp="2026-07-16T09:15:00+05:30",
            ),
            "formation_status": "NEAR_TRIGGER",
            "evidence_strength_score": 80,
            "setup_maturity_score": 90,
            "distance_to_trigger_percent": 0.05,
        },
        {
            **make_entry(
                decision="NO_TRADE",
                timestamp="2026-07-16T09:20:00+05:30",
            ),
            "formation_status": "NEAR_TRIGGER",
            "evidence_strength_score": 60,
            "setup_maturity_score": 80,
            "distance_to_trigger_percent": 0.15,
        },
        {
            **make_entry(
                decision="NO_TRADE",
                timestamp="2026-07-16T09:25:00+05:30",
            ),
            "formation_status": "DEVELOPING",
            "evidence_strength_score": 40,
            "setup_maturity_score": 60,
            "distance_to_trigger_percent": 0.8,
        },
    ]

    result = make_engine().analyze(
        entries,
        session_date="2026-07-16",
    )

    research = result[
        "setup_formation_research"
    ]

    assert research[
        "NEAR_TRIGGER"
    ] == {
        "observations": 2,
        "average_evidence_strength": 70.0,
        "average_setup_maturity": 85.0,
        "average_distance_to_trigger_percent": 0.1,
    }

    assert research[
        "DEVELOPING"
    ] == {
        "observations": 1,
        "average_evidence_strength": 40.0,
        "average_setup_maturity": 60.0,
        "average_distance_to_trigger_percent": 0.8,
    }


def test_setup_formation_research_keeps_partial_observations():

    entries = [
        {
            **make_entry(
                timestamp="2026-07-16T09:15:00+05:30",
            ),
            "formation_status": "NEAR_TRIGGER",
            "evidence_strength_score": 80,
            "setup_maturity_score": None,
            "distance_to_trigger_percent": 0.05,
        },
    ]

    result = make_engine().analyze(
        entries,
        session_date="2026-07-16",
    )

    research = result[
        "setup_formation_research"
    ][
        "NEAR_TRIGGER"
    ]

    assert research["observations"] == 1

    assert (
        research["average_evidence_strength"]
        == 80.0
    )

    assert (
        research["average_setup_maturity"]
        is None
    )

    assert (
        research[
            "average_distance_to_trigger_percent"
        ]
        == 0.05
    )


def test_setup_formation_research_supports_nested_setup_trigger():

    entries = [
        {
            **make_entry(
                timestamp="2026-07-16T09:15:00+05:30",
            ),
            "evidence_strength_score": 70,
            "setup_trigger": {
                "formation_status": "DEVELOPING",
                "setup_maturity_score": 65,
                "distance_to_trigger_percent": 0.7,
            },
        },
    ]

    result = make_engine().analyze(
        entries,
        session_date="2026-07-16",
    )

    research = result[
        "setup_formation_research"
    ][
        "DEVELOPING"
    ]

    assert research["observations"] == 1

    assert (
        research["average_evidence_strength"]
        == 70.0
    )

    assert (
        research["average_setup_maturity"]
        == 65.0
    )

    assert (
        research[
            "average_distance_to_trigger_percent"
        ]
        == 0.7
    )

def test_near_miss_intelligence():

    entries = [
        make_entry(
            decision="NO_TRADE",
            timestamp=(
                "2026-07-16T09:20:00+05:30"
            ),
        ),
        make_entry(
            decision="NO_TRADE",
            timestamp=(
                "2026-07-16T09:25:00+05:30"
            ),
        ),
        make_entry(
            decision="NO_TRADE",
            timestamp=(
                "2026-07-16T09:30:00+05:30"
            ),
        ),
        make_entry(
            decision="NO_TRADE",
            timestamp=(
                "2026-07-16T09:35:00+05:30"
            ),
        ),
    ]

    entries[0].update(
        {
            "trade_candidate_score": 60,
            "candidate_label": "DEVELOPING",
            "candidate_missing_conditions": [
                "Setup maturity >= 80",
            ],
        }
    )

    entries[1].update(
        {
            "trade_candidate_score": 85,
            "candidate_label": "CLOSE",
            "candidate_missing_conditions": [
                "Full timeframe alignment",
                "Resolve risk flags",
            ],
        }
    )

    entries[2].update(
        {
            "trade_candidate_score": 95,
            "candidate_label": "VERY_CLOSE",
            "candidate_missing_conditions": [
                "Full timeframe alignment",
            ],
        }
    )

    entries[3].update(
        {
            "trade_candidate_score": 80,
            "candidate_label": "CLOSE",
            "candidate_missing_conditions": [
                "Resolve risk flags",
            ],
        }
    )

    result = make_engine().analyze(
        entries,
        session_date="2026-07-16",
    )

    near_miss = result[
        "near_miss_intelligence"
    ]

    assert (
        near_miss["near_miss_count"]
        == 3
    )

    assert (
        near_miss[
            "candidate_label_distribution"
        ]
        == {
            "DEVELOPING": 1,
            "CLOSE": 2,
            "VERY_CLOSE": 1,
        }
    )

    assert (
        near_miss["candidate_score"]
        == {
            "observations": 4,
            "average": 80.0,
            "minimum": 60.0,
            "maximum": 95.0,
        }
    )

    assert (
        near_miss[
            "top_missing_conditions"
        ]
        == {
            "Full timeframe alignment": 2,
            "Resolve risk flags": 2,
        }
    )

    assert (
        near_miss["peak_candidate"]
        == {
            "score": 95.0,
            "timestamp": (
                "2026-07-16T09:30:00+05:30"
            ),
            "label": "VERY_CLOSE",
        }
    )


def test_near_miss_intelligence_empty_candidate_data():

    entries = [
        make_entry(
            timestamp=(
                "2026-07-16T09:20:00+05:30"
            ),
        ),
    ]

    result = make_engine().analyze(
        entries,
        session_date="2026-07-16",
    )

    near_miss = result[
        "near_miss_intelligence"
    ]

    assert (
        near_miss["near_miss_count"]
        == 0
    )

    assert (
        near_miss[
            "candidate_label_distribution"
        ]
        == {}
    )

    assert (
        near_miss["candidate_score"]
        == {
            "observations": 0,
            "average": None,
            "minimum": None,
            "maximum": None,
        }
    )

    assert (
        near_miss[
            "top_missing_conditions"
        ]
        == {}
    )

    assert (
        near_miss["peak_candidate"]
        == {
            "score": None,
            "timestamp": None,
            "label": None,
        }
    )


def test_only_close_labels_count_as_near_misses():

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

    entries[0].update(
        {
            "trade_candidate_score": 70,
            "candidate_label": "DEVELOPING",
            "candidate_missing_conditions": [
                "Full timeframe alignment",
            ],
        }
    )

    entries[1].update(
        {
            "trade_candidate_score": 85,
            "candidate_label": "CLOSE",
            "candidate_missing_conditions": [
                "Resolve risk flags",
            ],
        }
    )

    entries[2].update(
        {
            "trade_candidate_score": 100,
            "candidate_label": "AUTHORIZED",
            "candidate_missing_conditions": [
                "SHOULD NOT COUNT",
            ],
        }
    )

    result = make_engine().analyze(
        entries,
        session_date="2026-07-16",
    )

    near_miss = result[
        "near_miss_intelligence"
    ]

    assert (
        near_miss["near_miss_count"]
        == 1
    )

    assert (
        near_miss[
            "top_missing_conditions"
        ]
        == {
            "Resolve risk flags": 1,
        }
    )
