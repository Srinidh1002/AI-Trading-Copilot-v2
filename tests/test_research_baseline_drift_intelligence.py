"""
Behavioral tests for ResearchBaselineDriftIntelligence.

IMPORTANT:
- READ ONLY.
- RESEARCH ONLY.
- NO BROKER EXECUTION.
- NO ORDER PLACEMENT.
- NO PAPER-TRADE MUTATION.
- NO STRATEGY TUNING.
- NO MODEL RETRAINING.
"""

from copy import deepcopy

import pytest

from services.research_baseline_drift_intelligence import (
    ResearchBaselineDriftIntelligence,
)


def build_engine():
    return ResearchBaselineDriftIntelligence()


def build_record(
    *,
    session_date="2026-07-14",
    confidence=70,
    readiness=60,
    risk_flag_count=1,
    setup_score=65,
    trade_ready_observed=False,
    decision="HOLD",
    direction="BULLISH",
    regime="TRENDING",
):
    return {
        "session_date": session_date,
        "confidence": confidence,
        "readiness": readiness,
        "risk_flag_count": risk_flag_count,
        "setup_score": setup_score,
        "trade_ready_observed": trade_ready_observed,
        "decision": decision,
        "direction": direction,
        "regime": regime,
    }


def build_stable_records():
    return [
        build_record(
            session_date="2026-07-10",
            confidence=70,
            readiness=60,
            risk_flag_count=1,
            setup_score=65,
        ),
        build_record(
            session_date="2026-07-11",
            confidence=70,
            readiness=60,
            risk_flag_count=1,
            setup_score=65,
        ),
        build_record(
            session_date="2026-07-12",
            confidence=70,
            readiness=60,
            risk_flag_count=1,
            setup_score=65,
        ),
        build_record(
            session_date="2026-07-13",
            confidence=70,
            readiness=60,
            risk_flag_count=1,
            setup_score=65,
        ),
        build_record(
            session_date="2026-07-14",
            confidence=70,
            readiness=60,
            risk_flag_count=1,
            setup_score=65,
        ),
    ]


def build_significant_drift_records():
    return [
        build_record(
            session_date="2026-07-10",
            confidence=70,
            readiness=60,
            risk_flag_count=1,
            setup_score=66,
        ),
        build_record(
            session_date="2026-07-11",
            confidence=72,
            readiness=62,
            risk_flag_count=1,
            setup_score=68,
        ),
        build_record(
            session_date="2026-07-12",
            confidence=71,
            readiness=61,
            risk_flag_count=1,
            setup_score=67,
        ),
        build_record(
            session_date="2026-07-13",
            confidence=73,
            readiness=64,
            risk_flag_count=1,
            setup_score=70,
        ),
        build_record(
            session_date="2026-07-14",
            confidence=90,
            readiness=30,
            risk_flag_count=5,
            setup_score=40,
            trade_ready_observed=True,
            decision="TRADE_READY",
            direction="BEARISH",
            regime="VOLATILE",
        ),
    ]


def test_empty_input_returns_completed():
    result = build_engine().analyze([])

    assert result["status"] == "COMPLETED"


def test_empty_input_is_read_only():
    result = build_engine().analyze([])

    assert result["read_only"] is True


def test_empty_input_is_research_only():
    result = build_engine().analyze([])

    assert result["research_only"] is True


def test_empty_input_observes_zero_sessions():
    result = build_engine().analyze([])

    assert result["sessions_observed"] == 0


def test_empty_input_has_zero_historical_sessions():
    result = build_engine().analyze([])

    assert result["historical_sessions"] == 0


def test_empty_input_has_no_current_session_date():
    result = build_engine().analyze([])

    assert result["current_session_date"] is None


def test_empty_input_overall_drift_is_unavailable():
    result = build_engine().analyze([])

    assert (
        result["overall_drift"]["state"]
        == "UNAVAILABLE"
    )


def test_empty_input_has_research_observation():
    result = build_engine().analyze([])

    assert result["research_observations"]


@pytest.mark.parametrize(
    "invalid_input",
    [
        None,
        {},
        "invalid",
        123,
        True,
    ],
)
def test_invalid_collection_is_normalized(
    invalid_input,
):
    result = build_engine().analyze(
        invalid_input
    )

    assert result["sessions_observed"] == 0
    assert (
        result["overall_drift"]["state"]
        == "UNAVAILABLE"
    )


def test_invalid_records_are_ignored():
    records = [
        None,
        [],
        "invalid",
        123,
        True,
        build_record(),
    ]

    result = build_engine().analyze(
        records
    )

    assert result["sessions_observed"] == 1


def test_input_records_are_not_mutated():
    records = build_significant_drift_records()
    original = deepcopy(records)

    build_engine().analyze(records)

    assert records == original


def test_latest_valid_record_is_current():
    records = build_stable_records()

    result = build_engine().analyze(records)

    assert (
        result["current_session_date"]
        == "2026-07-14"
    )


def test_prior_records_form_historical_baseline():
    records = build_stable_records()

    result = build_engine().analyze(records)

    assert result["historical_sessions"] == 4
    assert result["baseline"]["sessions"] == 4


def test_single_record_has_no_historical_baseline():
    result = build_engine().analyze(
        [
            build_record(),
        ]
    )

    assert result["sessions_observed"] == 1
    assert result["historical_sessions"] == 0
    assert result["baseline"]["sessions"] == 0


def test_confidence_baseline_average():
    result = build_engine().analyze(
        build_significant_drift_records()
    )

    metric = (
        result["baseline"]["metrics"][
            "confidence"
        ]
    )

    assert metric["observations"] == 4
    assert metric["minimum"] == 70.0
    assert metric["maximum"] == 73.0
    assert metric["average"] == 71.5


def test_readiness_baseline_average():
    result = build_engine().analyze(
        build_significant_drift_records()
    )

    metric = (
        result["baseline"]["metrics"][
            "readiness"
        ]
    )

    assert metric["average"] == 61.75


def test_risk_flag_baseline_average():
    result = build_engine().analyze(
        build_significant_drift_records()
    )

    metric = (
        result["baseline"]["metrics"][
            "risk_flag_count"
        ]
    )

    assert metric["average"] == 1.0


def test_setup_score_baseline_average():
    result = build_engine().analyze(
        build_significant_drift_records()
    )

    metric = (
        result["baseline"]["metrics"][
            "setup_score"
        ]
    )

    assert metric["average"] == 67.75


def test_trade_ready_baseline_frequency():
    result = build_engine().analyze(
        build_significant_drift_records()
    )

    assert (
        result["baseline"][
            "trade_ready_frequency_percent"
        ]
        == 0.0
    )


def test_decision_baseline_distribution():
    result = build_engine().analyze(
        build_significant_drift_records()
    )

    assert (
        result["baseline"][
            "decision_distribution"
        ]
        == [
            {
                "value": "HOLD",
                "count": 4,
            },
        ]
    )


def test_direction_baseline_distribution():
    result = build_engine().analyze(
        build_significant_drift_records()
    )

    assert (
        result["baseline"][
            "direction_distribution"
        ]
        == [
            {
                "value": "BULLISH",
                "count": 4,
            },
        ]
    )


def test_regime_baseline_distribution():
    result = build_engine().analyze(
        build_significant_drift_records()
    )

    assert (
        result["baseline"][
            "regime_distribution"
        ]
        == [
            {
                "value": "TRENDING",
                "count": 4,
            },
        ]
    )


def test_current_snapshot_uses_latest_values():
    result = build_engine().analyze(
        build_significant_drift_records()
    )

    current = result["current"]

    assert current["confidence"] == 90.0
    assert current["readiness"] == 30.0
    assert current["risk_flag_count"] == 5.0
    assert current["setup_score"] == 40.0
    assert current["trade_ready_observed"] is True
    assert current["decision"] == "TRADE_READY"
    assert current["direction"] == "BEARISH"
    assert current["regime"] == "VOLATILE"


def test_confidence_significant_increase():
    result = build_engine().analyze(
        build_significant_drift_records()
    )

    drift = (
        result["metric_drift"]["confidence"]
    )

    assert drift["baseline_average"] == 71.5
    assert drift["current"] == 90.0
    assert drift["difference"] == 18.5
    assert drift["direction"] == "INCREASE"
    assert drift["severity"] == "SIGNIFICANT"
    assert (
        drift["drift"]
        == "SIGNIFICANT_INCREASE"
    )


def test_readiness_significant_decrease():
    result = build_engine().analyze(
        build_significant_drift_records()
    )

    drift = (
        result["metric_drift"]["readiness"]
    )

    assert drift["direction"] == "DECREASE"
    assert drift["severity"] == "SIGNIFICANT"
    assert (
        drift["drift"]
        == "SIGNIFICANT_DECREASE"
    )


def test_risk_flags_significant_increase():
    result = build_engine().analyze(
        build_significant_drift_records()
    )

    drift = (
        result["metric_drift"][
            "risk_flag_count"
        ]
    )

    assert drift["difference"] == 4.0
    assert (
        drift["relative_change_percent"]
        == 400.0
    )
    assert (
        drift["drift"]
        == "SIGNIFICANT_INCREASE"
    )


def test_setup_score_significant_decrease():
    result = build_engine().analyze(
        build_significant_drift_records()
    )

    drift = (
        result["metric_drift"]["setup_score"]
    )

    assert (
        drift["drift"]
        == "SIGNIFICANT_DECREASE"
    )


def test_stable_metric_drift():
    result = build_engine().analyze(
        build_stable_records()
    )

    for drift in (
        result["metric_drift"].values()
    ):
        assert drift["direction"] == "STABLE"
        assert drift["severity"] == "STABLE"
        assert drift["drift"] == "STABLE"


def test_metric_change_below_five_percent_is_stable():
    records = build_stable_records()
    records[-1]["confidence"] = 72

    result = build_engine().analyze(records)

    drift = (
        result["metric_drift"]["confidence"]
    )

    assert drift["severity"] == "STABLE"
    assert drift["drift"] == "STABLE"


def test_metric_change_at_five_percent_is_moderate():
    records = build_stable_records()
    records[-1]["confidence"] = 73.5

    result = build_engine().analyze(records)

    drift = (
        result["metric_drift"]["confidence"]
    )

    assert drift["severity"] == "MODERATE"
    assert (
        drift["drift"]
        == "MODERATE_INCREASE"
    )


def test_metric_change_below_fifteen_percent_is_moderate():
    records = build_stable_records()
    records[-1]["confidence"] = 80

    result = build_engine().analyze(records)

    drift = (
        result["metric_drift"]["confidence"]
    )

    assert drift["severity"] == "MODERATE"


def test_metric_change_at_fifteen_percent_is_significant():
    records = build_stable_records()
    records[-1]["confidence"] = 80.5

    result = build_engine().analyze(records)

    drift = (
        result["metric_drift"]["confidence"]
    )

    assert drift["severity"] == "SIGNIFICANT"


def test_zero_baseline_equal_current_is_stable():
    records = build_stable_records()

    for record in records:
        record["risk_flag_count"] = 0

    result = build_engine().analyze(records)

    drift = (
        result["metric_drift"][
            "risk_flag_count"
        ]
    )

    assert drift["relative_change_percent"] is None
    assert drift["severity"] == "STABLE"
    assert drift["drift"] == "STABLE"


def test_zero_baseline_nonzero_current_is_significant():
    records = build_stable_records()

    for record in records[:-1]:
        record["risk_flag_count"] = 0

    records[-1]["risk_flag_count"] = 1

    result = build_engine().analyze(records)

    drift = (
        result["metric_drift"][
            "risk_flag_count"
        ]
    )

    assert drift["relative_change_percent"] is None
    assert drift["severity"] == "SIGNIFICANT"
    assert (
        drift["drift"]
        == "SIGNIFICANT_INCREASE"
    )


@pytest.mark.parametrize(
    "value",
    [
        None,
        "70",
        [],
        {},
        True,
    ],
)
def test_invalid_current_metric_is_unavailable(
    value,
):
    records = build_stable_records()
    records[-1]["confidence"] = value

    result = build_engine().analyze(records)

    drift = (
        result["metric_drift"]["confidence"]
    )

    assert drift["status"] == "UNAVAILABLE"
    assert drift["drift"] == "UNAVAILABLE"


def test_invalid_historical_metrics_are_ignored():
    records = build_stable_records()

    records[0]["confidence"] = None
    records[1]["confidence"] = "70"
    records[2]["confidence"] = True

    result = build_engine().analyze(records)

    baseline = (
        result["baseline"]["metrics"][
            "confidence"
        ]
    )

    assert baseline["observations"] == 1
    assert baseline["average"] == 70.0


def test_trade_ready_significant_increase():
    result = build_engine().analyze(
        build_significant_drift_records()
    )

    drift = result["trade_ready_drift"]

    assert (
        drift["historical_frequency_percent"]
        == 0.0
    )
    assert drift["current_trade_ready"] is True
    assert (
        drift["difference_percentage_points"]
        == 100.0
    )
    assert (
        drift["drift"]
        == "SIGNIFICANT_INCREASE"
    )


def test_trade_ready_significant_decrease():
    records = build_stable_records()

    for record in records[:-1]:
        record["trade_ready_observed"] = True

    records[-1]["trade_ready_observed"] = False

    result = build_engine().analyze(records)

    assert (
        result["trade_ready_drift"]["drift"]
        == "SIGNIFICANT_DECREASE"
    )


def test_trade_ready_stable():
    result = build_engine().analyze(
        build_stable_records()
    )

    assert (
        result["trade_ready_drift"]["drift"]
        == "STABLE"
    )


def test_trade_ready_unavailable_without_history():
    result = build_engine().analyze(
        [
            build_record(),
        ]
    )

    assert (
        result["trade_ready_drift"]["status"]
        == "UNAVAILABLE"
    )


def test_decision_significant_drift():
    result = build_engine().analyze(
        build_significant_drift_records()
    )

    drift = result["decision_drift"]

    assert drift["historical_dominant"] == "HOLD"
    assert (
        drift["historical_dominant_percent"]
        == 100.0
    )
    assert drift["current"] == "TRADE_READY"
    assert (
        drift["matches_historical_dominant"]
        is False
    )
    assert drift["drift"] == "SIGNIFICANT"


def test_direction_significant_drift():
    result = build_engine().analyze(
        build_significant_drift_records()
    )

    assert (
        result["direction_drift"]["drift"]
        == "SIGNIFICANT"
    )


def test_regime_significant_drift():
    result = build_engine().analyze(
        build_significant_drift_records()
    )

    assert (
        result["regime_drift"]["drift"]
        == "SIGNIFICANT"
    )


def test_categorical_match_is_stable():
    result = build_engine().analyze(
        build_stable_records()
    )

    assert (
        result["decision_drift"]["drift"]
        == "STABLE"
    )
    assert (
        result["direction_drift"]["drift"]
        == "STABLE"
    )
    assert (
        result["regime_drift"]["drift"]
        == "STABLE"
    )


def test_categorical_difference_with_weak_dominance_is_moderate():
    records = build_stable_records()

    records[0]["decision"] = "HOLD"
    records[1]["decision"] = "HOLD"
    records[2]["decision"] = "WAIT"
    records[3]["decision"] = "WAIT"
    records[4]["decision"] = "TRADE_READY"

    result = build_engine().analyze(records)

    drift = result["decision_drift"]

    assert (
        drift["historical_dominant_percent"]
        == 50.0
    )
    assert drift["drift"] == "MODERATE"


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "UNKNOWN",
        "UNAVAILABLE",
        "NONE",
        "NULL",
    ],
)
def test_invalid_current_category_is_unavailable(
    value,
):
    records = build_stable_records()
    records[-1]["decision"] = value

    result = build_engine().analyze(records)

    assert (
        result["decision_drift"]["status"]
        == "UNAVAILABLE"
    )


def test_categories_are_normalized_to_uppercase():
    records = build_stable_records()

    for record in records:
        record["decision"] = " hold "
        record["direction"] = " bullish "
        record["regime"] = " trending "

    result = build_engine().analyze(records)

    assert result["current"]["decision"] == "HOLD"
    assert result["current"]["direction"] == "BULLISH"
    assert result["current"]["regime"] == "TRENDING"


def test_significant_synthetic_case_has_eight_signals():
    result = build_engine().analyze(
        build_significant_drift_records()
    )

    overall = result["overall_drift"]

    assert overall["significant_signals"] == 8
    assert overall["moderate_signals"] == 0
    assert overall["stable_signals"] == 0
    assert overall["available_signals"] == 8


def test_significant_synthetic_case_is_significant_drift():
    result = build_engine().analyze(
        build_significant_drift_records()
    )

    assert (
        result["overall_drift"]["state"]
        == "SIGNIFICANT_DRIFT"
    )


def test_stable_case_is_stable():
    result = build_engine().analyze(
        build_stable_records()
    )

    assert (
        result["overall_drift"]["state"]
        == "STABLE"
    )


def test_one_significant_signal_is_elevated_drift():
    records = build_stable_records()
    records[-1]["confidence"] = 90

    result = build_engine().analyze(records)

    overall = result["overall_drift"]

    assert overall["significant_signals"] == 1
    assert overall["state"] == "ELEVATED_DRIFT"


def test_one_moderate_signal_is_low_drift():
    records = build_stable_records()
    records[-1]["confidence"] = 75

    result = build_engine().analyze(records)

    overall = result["overall_drift"]

    assert overall["moderate_signals"] == 1
    assert overall["state"] == "LOW_DRIFT"


def test_two_moderate_signals_are_moderate_drift():
    records = build_stable_records()
    records[-1]["confidence"] = 75
    records[-1]["readiness"] = 64

    result = build_engine().analyze(records)

    overall = result["overall_drift"]

    assert overall["moderate_signals"] == 2
    assert overall["state"] == "MODERATE_DRIFT"


def test_significant_case_has_multiple_observations():
    result = build_engine().analyze(
        build_significant_drift_records()
    )

    observations = result[
        "research_observations"
    ]

    assert len(observations) >= 5


def test_significant_case_mentions_confidence():
    result = build_engine().analyze(
        build_significant_drift_records()
    )

    assert any(
        "Confidence"
        in observation
        for observation in result[
            "research_observations"
        ]
    )


def test_significant_case_mentions_readiness():
    result = build_engine().analyze(
        build_significant_drift_records()
    )

    assert any(
        "Readiness"
        in observation
        for observation in result[
            "research_observations"
        ]
    )


def test_significant_case_mentions_risk_flags():
    result = build_engine().analyze(
        build_significant_drift_records()
    )

    assert any(
        "Risk Flag Count"
        in observation
        for observation in result[
            "research_observations"
        ]
    )


def test_significant_case_mentions_setup_score():
    result = build_engine().analyze(
        build_significant_drift_records()
    )

    assert any(
        "Setup Score"
        in observation
        for observation in result[
            "research_observations"
        ]
    )


def test_significant_case_mentions_trade_ready():
    result = build_engine().analyze(
        build_significant_drift_records()
    )

    assert any(
        "TRADE_READY"
        in observation
        for observation in result[
            "research_observations"
        ]
    )


def test_significant_case_mentions_multiple_signals():
    result = build_engine().analyze(
        build_significant_drift_records()
    )

    assert (
        "Multiple research signals showed "
        "significant behavioural drift."
        in result["research_observations"]
    )


def test_stable_case_has_stable_observation():
    result = build_engine().analyze(
        build_stable_records()
    )

    assert (
        "Observed research behaviour remained "
        "within the historical baseline."
        in result["research_observations"]
    )


def test_single_session_mentions_missing_baseline():
    result = build_engine().analyze(
        [
            build_record(),
        ]
    )

    assert any(
        "Historical research baseline"
        in observation
        for observation in result[
            "research_observations"
        ]
    )


def test_observations_are_deduplicated():
    result = build_engine().analyze(
        build_significant_drift_records()
    )

    observations = result[
        "research_observations"
    ]

    assert len(observations) == len(
        set(observations)
    )


def test_analyse_alias_matches_analyze():
    records = build_significant_drift_records()

    engine = build_engine()

    assert engine.analyse(records) == engine.analyze(
        records
    )


def test_result_is_independent_from_input_after_analysis():
    records = build_significant_drift_records()

    result = build_engine().analyze(records)

    records[-1]["confidence"] = 1
    records[-1]["decision"] = "CHANGED"

    assert result["current"]["confidence"] == 90.0
    assert (
        result["current"]["decision"]
        == "TRADE_READY"
    )


def test_boolean_numeric_values_are_rejected():
    records = build_stable_records()

    for record in records[:-1]:
        record["confidence"] = True

    result = build_engine().analyze(records)

    assert (
        result["baseline"]["metrics"][
            "confidence"
        ]["observations"]
        == 0
    )

    assert (
        result["metric_drift"]["confidence"][
            "status"
        ]
        == "UNAVAILABLE"
    )


def test_distribution_is_sorted_by_count_then_name():
    records = [
        build_record(
            session_date="2026-07-10",
            decision="WAIT",
        ),
        build_record(
            session_date="2026-07-11",
            decision="HOLD",
        ),
        build_record(
            session_date="2026-07-12",
            decision="WAIT",
        ),
        build_record(
            session_date="2026-07-13",
            decision="HOLD",
        ),
        build_record(
            session_date="2026-07-14",
            decision="TRADE_READY",
        ),
    ]

    result = build_engine().analyze(records)

    assert (
        result["baseline"][
            "decision_distribution"
        ]
        == [
            {
                "value": "HOLD",
                "count": 2,
            },
            {
                "value": "WAIT",
                "count": 2,
            },
        ]
    )


def test_public_result_contains_expected_sections():
    result = build_engine().analyze(
        build_stable_records()
    )

    expected = {
        "status",
        "read_only",
        "research_only",
        "sessions_observed",
        "historical_sessions",
        "current_session_date",
        "baseline",
        "current",
        "metric_drift",
        "trade_ready_drift",
        "decision_drift",
        "direction_drift",
        "regime_drift",
        "overall_drift",
        "research_observations",
    }

    assert expected.issubset(
        result.keys()
    )