"""
Tests for CrossSessionResearchIntelligence.
"""

from copy import deepcopy

import pytest

from services.cross_session_research_intelligence import (
    CrossSessionResearchIntelligence,
)


@pytest.fixture
def engine():
    return CrossSessionResearchIntelligence()


def build_report(
    *,
    session_date,
    decision="TRADE_BLOCKED",
    direction="BULLISH",
    regime="TRENDING",
    confidence=60.0,
    confidence_trend="STABLE",
    readiness=50.0,
    readiness_momentum="STABLE",
    risk_flag_count=1,
    setup_score=55.0,
    trade_ready_observed=False,
    final_blocked=True,
    final_blockers=None,
    blocker_statistics=None,
    positive_combinations=None,
    negative_combinations=None,
    best_observed_combination=None,
    worst_observed_combination=None,
):
    if final_blockers is None:
        final_blockers = []

    if blocker_statistics is None:
        blocker_statistics = []

    if positive_combinations is None:
        positive_combinations = []

    if negative_combinations is None:
        negative_combinations = []

    return {
        "status": "COMPLETED",
        "read_only": True,
        "research_only": True,
        "session_date": session_date,
        "cycles_observed": 10,
        "trades_observed": 3,
        "research_snapshot": {
            "final_decision": decision,
            "final_direction": direction,
            "final_regime": regime,
            "final_confidence": confidence,
            "confidence_trend": confidence_trend,
            "readiness_momentum": readiness_momentum,
            "final_readiness": readiness,
            "final_risk_flag_count": risk_flag_count,
            "final_setup_score": setup_score,
            "trade_ready_observed": trade_ready_observed,
            "final_blocked": final_blocked,
            "final_blocker_state": {
                "blockers": deepcopy(
                    final_blockers
                ),
                "blocked": final_blocked,
                "state": (
                    "BLOCKED"
                    if final_blocked
                    else "CLEAR"
                ),
            },
            "positive_strategy_regime_combinations": len(
                positive_combinations
            ),
            "negative_strategy_regime_combinations": len(
                negative_combinations
            ),
            "best_observed_combination": deepcopy(
                best_observed_combination
            ),
            "worst_observed_combination": deepcopy(
                worst_observed_combination
            ),
        },
        "blocker_intelligence": {
            "blocker_statistics": deepcopy(
                blocker_statistics
            ),
        },
        "strategy_regime_performance": {
            "positive_combinations": deepcopy(
                positive_combinations
            ),
            "negative_combinations": deepcopy(
                negative_combinations
            ),
        },
    }


def test_analyze_empty_reports(engine):
    result = engine.analyze([])

    assert result["status"] == "COMPLETED"
    assert result["read_only"] is True
    assert result["research_only"] is True
    assert result["sessions_observed"] == 0
    assert result["session_dates"] == []
    assert result["session_records"] == []

    assert (
        result["confidence_intelligence"]["trend"]
        == "UNAVAILABLE"
    )

    assert result["research_observations"] == [
        "No archived research sessions were observed."
    ]


def test_none_reports_are_treated_as_empty(engine):
    result = engine.analyze(None)

    assert result["sessions_observed"] == 0
    assert result["session_records"] == []


@pytest.mark.parametrize(
    "reports",
    [
        {},
        "invalid",
        123,
        True,
    ],
)
def test_invalid_reports_container_raises(
    engine,
    reports,
):
    with pytest.raises(
        ValueError,
        match="reports must be a list or tuple",
    ):
        engine.analyze(
            reports
        )


def test_invalid_report_items_are_ignored(engine):
    report = build_report(
        session_date="2026-07-01",
    )

    result = engine.analyze(
        [
            None,
            "invalid",
            123,
            report,
        ]
    )

    assert result["sessions_observed"] == 1
    assert result["session_dates"] == [
        "2026-07-01"
    ]


def test_input_reports_are_not_modified(engine):
    reports = [
        build_report(
            session_date="2026-07-01",
            final_blockers=[
                "HIGH_RISK"
            ],
        )
    ]

    original = deepcopy(
        reports
    )

    engine.analyze(
        reports
    )

    assert reports == original


def test_decision_distribution_and_dominance(engine):
    reports = [
        build_report(
            session_date="2026-07-01",
            decision="TRADE_BLOCKED",
        ),
        build_report(
            session_date="2026-07-02",
            decision="TRADE_BLOCKED",
        ),
        build_report(
            session_date="2026-07-03",
            decision="TRADE_ALLOWED",
        ),
    ]

    result = engine.analyze(
        reports
    )

    intelligence = result[
        "decision_intelligence"
    ]

    assert intelligence["distribution"] == [
        {
            "decision": "TRADE_BLOCKED",
            "count": 2,
        },
        {
            "decision": "TRADE_ALLOWED",
            "count": 1,
        },
    ]

    assert intelligence["dominant"] == {
        "decision": "TRADE_BLOCKED",
        "count": 2,
        "sessions_observed": 3,
        "persistence_percent": 66.67,
    }


def test_decision_transitions_ignore_same_state(engine):
    reports = [
        build_report(
            session_date="2026-07-01",
            decision="TRADE_BLOCKED",
        ),
        build_report(
            session_date="2026-07-02",
            decision="TRADE_BLOCKED",
        ),
        build_report(
            session_date="2026-07-03",
            decision="TRADE_ALLOWED",
        ),
        build_report(
            session_date="2026-07-04",
            decision="TRADE_BLOCKED",
        ),
    ]

    result = engine.analyze(
        reports
    )

    assert result[
        "decision_intelligence"
    ]["transitions"] == [
        {
            "from": "TRADE_BLOCKED",
            "to": "TRADE_ALLOWED",
            "count": 1,
        },
        {
            "from": "TRADE_ALLOWED",
            "to": "TRADE_BLOCKED",
            "count": 1,
        },
    ]


def test_longest_decision_streak(engine):
    reports = [
        build_report(
            session_date="2026-07-01",
            decision="TRADE_BLOCKED",
        ),
        build_report(
            session_date="2026-07-02",
            decision="TRADE_BLOCKED",
        ),
        build_report(
            session_date="2026-07-03",
            decision="TRADE_BLOCKED",
        ),
        build_report(
            session_date="2026-07-04",
            decision="TRADE_ALLOWED",
        ),
    ]

    result = engine.analyze(
        reports
    )

    assert result[
        "decision_intelligence"
    ]["longest_streak"] == {
        "decision": "TRADE_BLOCKED",
        "sessions": 3,
        "start_index": 0,
        "end_index": 2,
    }


def test_direction_and_regime_intelligence(engine):
    reports = [
        build_report(
            session_date="2026-07-01",
            direction="BULLISH",
            regime="TRENDING",
        ),
        build_report(
            session_date="2026-07-02",
            direction="BULLISH",
            regime="TRENDING",
        ),
        build_report(
            session_date="2026-07-03",
            direction="BEARISH",
            regime="VOLATILE",
        ),
    ]

    result = engine.analyze(
        reports
    )

    assert result[
        "direction_intelligence"
    ]["dominant"]["direction"] == "BULLISH"

    assert result[
        "regime_intelligence"
    ]["dominant"]["regime"] == "TRENDING"

    assert result[
        "direction_intelligence"
    ]["transitions"] == [
        {
            "from": "BULLISH",
            "to": "BEARISH",
            "count": 1,
        }
    ]

    assert result[
        "regime_intelligence"
    ]["transitions"] == [
        {
            "from": "TRENDING",
            "to": "VOLATILE",
            "count": 1,
        }
    ]


@pytest.mark.parametrize(
    (
        "values",
        "expected_trend",
    ),
    [
        (
            [
                10,
                20,
                30,
            ],
            "RISING",
        ),
        (
            [
                30,
                20,
                10,
            ],
            "FALLING",
        ),
        (
            [
                20,
                20,
                20,
            ],
            "FLAT",
        ),
        (
            [
                10,
                30,
                20,
            ],
            "MIXED",
        ),
    ],
)
def test_confidence_trend_detection(
    engine,
    values,
    expected_trend,
):
    reports = [
        build_report(
            session_date=(
                f"2026-07-0{index + 1}"
            ),
            confidence=value,
        )
        for (
            index,
            value,
        ) in enumerate(
            values
        )
    ]

    result = engine.analyze(
        reports
    )

    assert result[
        "confidence_intelligence"
    ]["trend"] == expected_trend


def test_numeric_intelligence_metrics(engine):
    reports = [
        build_report(
            session_date="2026-07-01",
            readiness=40,
        ),
        build_report(
            session_date="2026-07-02",
            readiness=50,
        ),
        build_report(
            session_date="2026-07-03",
            readiness=70,
        ),
    ]

    result = engine.analyze(
        reports
    )

    intelligence = result[
        "readiness_intelligence"
    ]

    assert intelligence["observations"] == 3
    assert intelligence["first"] == 40.0
    assert intelligence["final"] == 70.0
    assert intelligence["minimum"] == 40.0
    assert intelligence["maximum"] == 70.0
    assert intelligence["average"] == 53.3333
    assert intelligence["change"] == 30.0
    assert intelligence["trend"] == "RISING"


def test_invalid_numeric_values_are_ignored(engine):
    reports = [
        build_report(
            session_date="2026-07-01",
            confidence=True,
        ),
        build_report(
            session_date="2026-07-02",
            confidence="invalid",
        ),
        build_report(
            session_date="2026-07-03",
            confidence=70,
        ),
    ]

    result = engine.analyze(
        reports
    )

    intelligence = result[
        "confidence_intelligence"
    ]

    assert intelligence["observations"] == 1
    assert intelligence["first"] == 70.0
    assert intelligence["final"] == 70.0
    assert intelligence["trend"] == "UNAVAILABLE"


def test_blocker_recurrence(engine):
    reports = [
        build_report(
            session_date="2026-07-01",
            blocker_statistics=[
                {
                    "blocker": "HIGH_RISK",
                    "occurrences": 4,
                },
                {
                    "blocker": "LOW_CONFIDENCE",
                    "occurrences": 2,
                },
            ],
        ),
        build_report(
            session_date="2026-07-02",
            blocker_statistics=[
                {
                    "blocker": "HIGH_RISK",
                    "occurrences": 3,
                },
            ],
        ),
    ]

    result = engine.analyze(
        reports
    )

    assert result["blocker_recurrence"] == [
        {
            "blocker": "HIGH_RISK",
            "occurrences": 7.0,
            "sessions_observed": 2,
        },
        {
            "blocker": "LOW_CONFIDENCE",
            "occurrences": 2.0,
            "sessions_observed": 1,
        },
    ]


def test_final_blocker_recurrence(engine):
    reports = [
        build_report(
            session_date="2026-07-01",
            final_blockers=[
                "HIGH_RISK",
                "LOW_CONFIDENCE",
            ],
        ),
        build_report(
            session_date="2026-07-02",
            final_blockers=[
                "HIGH_RISK",
            ],
        ),
        build_report(
            session_date="2026-07-03",
            final_blockers=[],
            final_blocked=False,
        ),
    ]

    result = engine.analyze(
        reports
    )

    assert result[
        "final_blocker_recurrence"
    ] == [
        {
            "blocker": "HIGH_RISK",
            "sessions": 2,
            "persistence_percent": 66.67,
        },
        {
            "blocker": "LOW_CONFIDENCE",
            "sessions": 1,
            "persistence_percent": 33.33,
        },
    ]


def test_trade_ready_intelligence(engine):
    reports = [
        build_report(
            session_date="2026-07-01",
            trade_ready_observed=False,
        ),
        build_report(
            session_date="2026-07-02",
            trade_ready_observed=True,
            final_blocked=False,
        ),
        build_report(
            session_date="2026-07-03",
            trade_ready_observed=True,
            final_blocked=False,
        ),
    ]

    result = engine.analyze(
        reports
    )

    intelligence = result[
        "trade_ready_intelligence"
    ]

    assert intelligence[
        "sessions_observed"
    ] == 3

    assert intelligence[
        "trade_ready_sessions"
    ] == 2

    assert intelligence[
        "trade_ready_frequency_percent"
    ] == 66.67

    assert intelligence[
        "first_trade_ready_session"
    ]["session_date"] == "2026-07-02"

    assert intelligence[
        "last_trade_ready_session"
    ]["session_date"] == "2026-07-03"


def test_strategy_regime_observations(engine):
    positive = {
        "market_regime": "TRENDING",
        "strategy": "MOMENTUM",
    }

    negative = {
        "market_regime": "VOLATILE",
        "strategy": "BREAKOUT",
    }

    reports = [
        build_report(
            session_date="2026-07-01",
            positive_combinations=[
                positive
            ],
            negative_combinations=[
                negative
            ],
        ),
        build_report(
            session_date="2026-07-02",
            positive_combinations=[
                positive
            ],
        ),
    ]

    result = engine.analyze(
        reports
    )

    assert result[
        "strategy_regime_observations"
    ]["positive"] == [
        {
            "market_regime": "TRENDING",
            "strategy": "MOMENTUM",
            "sessions_observed": 2,
        }
    ]

    assert result[
        "strategy_regime_observations"
    ]["negative"] == [
        {
            "market_regime": "VOLATILE",
            "strategy": "BREAKOUT",
            "sessions_observed": 1,
        }
    ]


def test_research_observations_detect_persistence(
    engine,
):
    reports = [
        build_report(
            session_date="2026-07-01",
            decision="TRADE_BLOCKED",
            direction="BULLISH",
            regime="TRENDING",
        ),
        build_report(
            session_date="2026-07-02",
            decision="TRADE_BLOCKED",
            direction="BULLISH",
            regime="TRENDING",
        ),
        build_report(
            session_date="2026-07-03",
            decision="TRADE_BLOCKED",
            direction="BULLISH",
            regime="TRENDING",
        ),
        build_report(
            session_date="2026-07-04",
            decision="TRADE_ALLOWED",
            direction="BEARISH",
            regime="VOLATILE",
        ),
    ]

    result = engine.analyze(
        reports
    )

    observations = result[
        "research_observations"
    ]

    assert (
        "A dominant final decision persisted "
        "across most observed sessions."
        in observations
    )

    assert (
        "A dominant market direction persisted "
        "across most observed sessions."
        in observations
    )

    assert (
        "A dominant market regime persisted "
        "across most observed sessions."
        in observations
    )


def test_research_observations_detect_numeric_trends(
    engine,
):
    reports = [
        build_report(
            session_date="2026-07-01",
            confidence=40,
            readiness=70,
        ),
        build_report(
            session_date="2026-07-02",
            confidence=50,
            readiness=60,
        ),
        build_report(
            session_date="2026-07-03",
            confidence=60,
            readiness=50,
        ),
    ]

    result = engine.analyze(
        reports
    )

    observations = result[
        "research_observations"
    ]

    assert (
        "Final session confidence increased "
        "across the observed research window."
        in observations
    )

    assert (
        "Final trade readiness weakened "
        "across the observed research window."
        in observations
    )


def test_research_observations_detect_blockers(
    engine,
):
    reports = [
        build_report(
            session_date="2026-07-01",
            blocker_statistics=[
                {
                    "blocker": "HIGH_RISK",
                    "occurrences": 2,
                }
            ],
        )
    ]

    result = engine.analyze(
        reports
    )

    assert (
        "One or more blockers recurred "
        "across archived market sessions."
        in result["research_observations"]
    )


def test_no_trade_ready_observation(engine):
    reports = [
        build_report(
            session_date="2026-07-01",
            trade_ready_observed=False,
        ),
        build_report(
            session_date="2026-07-02",
            trade_ready_observed=False,
        ),
    ]

    result = engine.analyze(
        reports
    )

    assert (
        "No archived session observed "
        "a TRADE_READY state."
        in result["research_observations"]
    )


def test_trade_ready_frequency_observation(engine):
    reports = [
        build_report(
            session_date="2026-07-01",
            trade_ready_observed=True,
            final_blocked=False,
        ),
        build_report(
            session_date="2026-07-02",
            trade_ready_observed=False,
        ),
    ]

    result = engine.analyze(
        reports
    )

    assert (
        "TRADE_READY was observed in at least "
        "half of archived sessions."
        in result["research_observations"]
    )


def test_strategy_regime_research_observations(engine):
    reports = [
        build_report(
            session_date="2026-07-01",
            positive_combinations=[
                {
                    "market_regime": "TRENDING",
                    "strategy": "MOMENTUM",
                }
            ],
            negative_combinations=[
                {
                    "market_regime": "VOLATILE",
                    "strategy": "BREAKOUT",
                }
            ],
        )
    ]

    result = engine.analyze(
        reports
    )

    observations = result[
        "research_observations"
    ]

    assert (
        "A historically positive strategy-regime "
        "combination recurred across reports."
        in observations
    )

    assert (
        "A historically negative strategy-regime "
        "combination recurred across reports."
        in observations
    )


def test_unknown_labels_are_excluded_from_distribution(
    engine,
):
    reports = [
        build_report(
            session_date="2026-07-01",
            decision=None,
            direction="",
            regime=None,
        )
    ]

    result = engine.analyze(
        reports
    )

    assert result[
        "decision_intelligence"
    ]["distribution"] == []

    assert result[
        "direction_intelligence"
    ]["distribution"] == []

    assert result[
        "regime_intelligence"
    ]["distribution"] == []


def test_result_is_independent_from_input_mutation(
    engine,
):
    report = build_report(
        session_date="2026-07-01",
        final_blockers=[
            "HIGH_RISK"
        ],
    )

    result = engine.analyze(
        [
            report
        ]
    )

    report[
        "research_snapshot"
    ][
        "final_blocker_state"
    ][
        "blockers"
    ].append(
        "MUTATED"
    )

    assert result[
        "session_records"
    ][
        0
    ][
        "final_blockers"
    ] == [
        "HIGH_RISK"
    ]