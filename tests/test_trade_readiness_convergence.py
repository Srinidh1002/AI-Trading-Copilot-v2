import pytest

from services.decision_evolution_analyzer import (
    DecisionEvolutionAnalyzer,
)

from services.trade_readiness_convergence import (
    TradeReadinessConvergence,
)


def make_engine():
    return TradeReadinessConvergence()


def make_analysis(
    *,
    candidate_observations=4,
    candidate_trend="RISING",
    candidate_change=35,
    longest_increase=3,
    trigger_observations=4,
    trigger_trend="CLOSING",
    trigger_speed="ACCELERATING",
    total_distance_closed=0.95,
    final_distance=0.05,
):
    return {
        "candidate_momentum": {
            "observations": (
                candidate_observations
            ),
            "trend": candidate_trend,
            "change": candidate_change,
            "longest_increase_sequence": (
                longest_increase
            ),
        },
        "trigger_approach": {
            "observations": (
                trigger_observations
            ),
            "approach_trend": trigger_trend,
            "approach_speed": trigger_speed,
            "total_distance_closed_percent": (
                total_distance_closed
            ),
            "final_distance_percent": (
                final_distance
            ),
        },
    }


def test_strong_readiness_convergence():

    result = make_engine().analyze(
        make_analysis()
    )

    assert (
        result["convergence"]
        == "STRONG"
    )

    assert (
        result[
            "candidate_signal"
        ]["persistent_rise"]
        is True
    )

    assert (
        result[
            "trigger_signal"
        ]["accelerating"]
        is True
    )


def test_moderate_readiness_convergence():

    result = make_engine().analyze(
        make_analysis(
            longest_increase=1,
            trigger_speed="STEADY",
        )
    )

    assert (
        result["convergence"]
        == "MODERATE"
    )


def test_weak_readiness_convergence():

    result = make_engine().analyze(
        make_analysis(
            candidate_trend="FLAT",
            candidate_change=0,
            longest_increase=0,
            trigger_trend="FLAT",
            trigger_speed="STEADY",
            total_distance_closed=0,
        )
    )

    assert (
        result["convergence"]
        == "WEAK"
    )


def test_falling_candidate_is_diverging():

    result = make_engine().analyze(
        make_analysis(
            candidate_trend="FALLING",
            candidate_change=-35,
            longest_increase=0,
        )
    )

    assert (
        result["convergence"]
        == "DIVERGING"
    )


def test_trigger_moving_away_is_diverging():

    result = make_engine().analyze(
        make_analysis(
            trigger_trend="MOVING_AWAY",
            trigger_speed="UNAVAILABLE",
            total_distance_closed=-0.75,
        )
    )

    assert (
        result["convergence"]
        == "DIVERGING"
    )


def test_insufficient_observations_unavailable():

    result = make_engine().analyze(
        make_analysis(
            candidate_observations=1,
            trigger_observations=1,
        )
    )

    assert (
        result["convergence"]
        == "UNAVAILABLE"
    )

    assert (
        result["reasons"]
        == [
            (
                "Insufficient chronological "
                "observations for convergence "
                "analysis."
            )
        ]
    )


def test_invalid_analysis_raises_value_error():

    with pytest.raises(
        ValueError,
        match=(
            "evolution_analysis must be "
            "a dictionary"
        ),
    ):
        make_engine().analyze(
            None
        )


def test_boolean_numeric_values_are_rejected():

    result = make_engine().analyze(
        make_analysis(
            candidate_change=True,
            total_distance_closed=True,
        )
    )

    assert (
        result["candidate_signal"]["rising"]
        is False
    )

    assert (
        result["trigger_signal"]["closing"]
        is False
    )


def test_input_analysis_is_not_mutated():

    analysis = make_analysis()

    original_candidate = dict(
        analysis["candidate_momentum"]
    )

    original_trigger = dict(
        analysis["trigger_approach"]
    )

    make_engine().analyze(
        analysis
    )

    assert (
        analysis["candidate_momentum"]
        == original_candidate
    )

    assert (
        analysis["trigger_approach"]
        == original_trigger
    )


def test_real_evolution_analysis_produces_strong_convergence():

    entries = [
        {
            "timestamp": (
                "2026-07-16T09:20:00+05:30"
            ),
            "decision": "NO_TRADE",
            "direction": "BULLISH",
            "regime": "TRENDING_BULLISH",
            "direction_confidence": 62,
            "trade_candidate_score": 60,
            "distance_to_trigger_percent": 1.0,
        },
        {
            "timestamp": (
                "2026-07-16T09:25:00+05:30"
            ),
            "decision": "NO_TRADE",
            "direction": "BULLISH",
            "regime": "TRENDING_BULLISH",
            "direction_confidence": 68,
            "trade_candidate_score": 70,
            "distance_to_trigger_percent": 0.8,
        },
        {
            "timestamp": (
                "2026-07-16T09:30:00+05:30"
            ),
            "decision": "NO_TRADE",
            "direction": "BULLISH",
            "regime": "TRENDING_BULLISH",
            "direction_confidence": 75,
            "trade_candidate_score": 85,
            "distance_to_trigger_percent": 0.5,
        },
        {
            "timestamp": (
                "2026-07-16T09:35:00+05:30"
            ),
            "decision": "NO_TRADE",
            "direction": "BULLISH",
            "regime": "TRENDING_BULLISH",
            "direction_confidence": 80,
            "trade_candidate_score": 95,
            "distance_to_trigger_percent": 0.05,
        },
    ]

    evolution = (
        DecisionEvolutionAnalyzer()
        .analyze(
            entries,
            session_date="2026-07-16",
        )
    )

    result = make_engine().analyze(
        evolution,
        session_date="2026-07-16",
    )

    assert (
        evolution[
            "candidate_momentum"
        ]["trend"]
        == "RISING"
    )

    assert (
        evolution[
            "trigger_approach"
        ]["approach_trend"]
        == "CLOSING"
    )

    assert (
        evolution[
            "trigger_approach"
        ]["approach_speed"]
        == "ACCELERATING"
    )

    assert (
        result["convergence"]
        == "STRONG"
    )

    assert result["read_only"] is True
