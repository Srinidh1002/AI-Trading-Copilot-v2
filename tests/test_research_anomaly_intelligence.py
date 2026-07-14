"""
Behavioral tests for ResearchAnomalyIntelligence.

IMPORTANT:
- READ ONLY.
- RESEARCH ONLY.
- NO BROKER EXECUTION.
- NO ORDER PLACEMENT.
- NO PAPER-TRADE MUTATION.
- NO RISK AUTHORITY.
- NO STRATEGY TUNING.
- NO MODEL RETRAINING.
"""

from copy import deepcopy

import pytest

from services.research_anomaly_intelligence import (
    ResearchAnomalyIntelligence,
)


def build_engine():
    return ResearchAnomalyIntelligence()


def build_metric_drift(
    drift="STABLE",
):
    return {
        "status": "COMPLETED",
        "drift": drift,
    }


def build_drift_result(
    *,
    confidence="STABLE",
    readiness="STABLE",
    risk_flag_count="STABLE",
    setup_score="STABLE",
    trade_ready=False,
    decision="HOLD",
    regime="TRENDING",
    historical_regime="TRENDING",
    overall_state="STABLE",
):
    return {
        "metric_drift": {
            "confidence": build_metric_drift(
                confidence
            ),
            "readiness": build_metric_drift(
                readiness
            ),
            "risk_flag_count": build_metric_drift(
                risk_flag_count
            ),
            "setup_score": build_metric_drift(
                setup_score
            ),
        },
        "trade_ready_drift": {
            "status": "COMPLETED",
            "drift": "STABLE",
        },
        "decision_drift": {
            "status": "COMPLETED",
            "drift": "STABLE",
        },
        "direction_drift": {
            "status": "COMPLETED",
            "drift": "STABLE",
        },
        "regime_drift": {
            "status": "COMPLETED",
            "historical_dominant": (
                historical_regime
            ),
            "current": regime,
            "drift": (
                "STABLE"
                if historical_regime == regime
                else "SIGNIFICANT"
            ),
        },
        "overall_drift": {
            "state": overall_state,
        },
        "current": {
            "trade_ready_observed": trade_ready,
            "decision": decision,
            "regime": regime,
        },
    }


def build_compound_result():
    return build_drift_result(
        confidence="SIGNIFICANT_INCREASE",
        readiness="SIGNIFICANT_DECREASE",
        risk_flag_count=(
            "SIGNIFICANT_INCREASE"
        ),
        setup_score="SIGNIFICANT_DECREASE",
        trade_ready=True,
        decision="TRADE_READY",
        regime="VOLATILE",
        historical_regime="TRENDING",
        overall_state="SIGNIFICANT_DRIFT",
    )


def anomaly_codes(result):
    return result["anomaly_codes"]


def test_empty_input_returns_completed():
    result = build_engine().analyze()

    assert result["status"] == "COMPLETED"


def test_empty_input_is_read_only():
    result = build_engine().analyze()

    assert result["read_only"] is True


def test_empty_input_is_research_only():
    result = build_engine().analyze()

    assert result["research_only"] is True


def test_empty_input_has_no_anomaly():
    result = build_engine().analyze()

    assert result["anomaly_detected"] is False


def test_empty_input_has_zero_anomalies():
    result = build_engine().analyze()

    assert result["anomaly_count"] == 0
    assert result["base_anomaly_count"] == 0


def test_empty_input_has_no_highest_severity():
    result = build_engine().analyze()

    assert result["highest_severity"] is None


def test_empty_input_has_empty_severity_distribution():
    result = build_engine().analyze()

    assert result["severity_distribution"] == []


def test_empty_input_has_empty_anomaly_codes():
    result = build_engine().analyze()

    assert result["anomaly_codes"] == []


def test_empty_input_has_empty_anomalies():
    result = build_engine().analyze()

    assert result["anomalies"] == []


def test_empty_input_has_no_source_drift_state():
    result = build_engine().analyze()

    assert (
        result["source_overall_drift_state"]
        is None
    )


def test_empty_input_has_research_observation():
    result = build_engine().analyze()

    assert result["research_observations"]


@pytest.mark.parametrize(
    "invalid_input",
    [
        None,
        [],
        "invalid",
        123,
        True,
    ],
)
def test_invalid_input_is_normalized(
    invalid_input,
):
    result = build_engine().analyze(
        invalid_input
    )

    assert result["status"] == "COMPLETED"
    assert result["anomaly_detected"] is False
    assert result["anomaly_count"] == 0


def test_input_is_not_mutated():
    source = build_compound_result()
    original = deepcopy(source)

    build_engine().analyze(source)

    assert source == original


def test_stable_input_has_no_anomaly():
    result = build_engine().analyze(
        build_drift_result()
    )

    assert result["anomaly_detected"] is False
    assert result["anomaly_count"] == 0


def test_stable_input_observation_mentions_no_anomaly():
    result = build_engine().analyze(
        build_drift_result()
    )

    assert (
        "No cross-signal research anomalies "
        "were detected."
        in result["research_observations"]
    )


def test_confidence_readiness_divergence():
    result = build_engine().analyze(
        build_drift_result(
            confidence="SIGNIFICANT_INCREASE",
            readiness="SIGNIFICANT_DECREASE",
        )
    )

    assert (
        "CONFIDENCE_READINESS_DIVERGENCE"
        in anomaly_codes(result)
    )


def test_confidence_readiness_divergence_is_high():
    result = build_engine().analyze(
        build_drift_result(
            confidence="MODERATE_INCREASE",
            readiness="MODERATE_DECREASE",
        )
    )

    anomaly = result["anomalies"][0]

    assert (
        anomaly["code"]
        == "CONFIDENCE_READINESS_DIVERGENCE"
    )
    assert anomaly["severity"] == "HIGH"


def test_confidence_readiness_same_direction_no_anomaly():
    result = build_engine().analyze(
        build_drift_result(
            confidence="SIGNIFICANT_INCREASE",
            readiness="SIGNIFICANT_INCREASE",
        )
    )

    assert (
        "CONFIDENCE_READINESS_DIVERGENCE"
        not in anomaly_codes(result)
    )


def test_confidence_risk_divergence():
    result = build_engine().analyze(
        build_drift_result(
            confidence="SIGNIFICANT_INCREASE",
            risk_flag_count=(
                "SIGNIFICANT_INCREASE"
            ),
        )
    )

    assert (
        "CONFIDENCE_RISK_DIVERGENCE"
        in anomaly_codes(result)
    )


def test_confidence_risk_divergence_is_high():
    result = build_engine().analyze(
        build_drift_result(
            confidence="MODERATE_INCREASE",
            risk_flag_count=(
                "MODERATE_INCREASE"
            ),
        )
    )

    anomaly = result["anomalies"][0]

    assert anomaly["severity"] == "HIGH"


def test_confidence_increase_risk_decrease_no_divergence():
    result = build_engine().analyze(
        build_drift_result(
            confidence="SIGNIFICANT_INCREASE",
            risk_flag_count=(
                "SIGNIFICANT_DECREASE"
            ),
        )
    )

    assert (
        "CONFIDENCE_RISK_DIVERGENCE"
        not in anomaly_codes(result)
    )


def test_trade_ready_readiness_contradiction():
    result = build_engine().analyze(
        build_drift_result(
            readiness="SIGNIFICANT_DECREASE",
            trade_ready=True,
        )
    )

    assert (
        "TRADE_READY_READINESS_CONTRADICTION"
        in anomaly_codes(result)
    )


def test_trade_ready_readiness_contradiction_is_critical():
    result = build_engine().analyze(
        build_drift_result(
            readiness="MODERATE_DECREASE",
            trade_ready=True,
        )
    )

    anomaly = result["anomalies"][0]

    assert anomaly["severity"] == "CRITICAL"


def test_not_trade_ready_readiness_decrease_no_contradiction():
    result = build_engine().analyze(
        build_drift_result(
            readiness="SIGNIFICANT_DECREASE",
            trade_ready=False,
        )
    )

    assert (
        "TRADE_READY_READINESS_CONTRADICTION"
        not in anomaly_codes(result)
    )


def test_trade_ready_risk_contradiction():
    result = build_engine().analyze(
        build_drift_result(
            risk_flag_count=(
                "SIGNIFICANT_INCREASE"
            ),
            trade_ready=True,
        )
    )

    assert (
        "TRADE_READY_RISK_CONTRADICTION"
        in anomaly_codes(result)
    )


def test_trade_ready_risk_contradiction_is_critical():
    result = build_engine().analyze(
        build_drift_result(
            risk_flag_count=(
                "MODERATE_INCREASE"
            ),
            trade_ready=True,
        )
    )

    anomaly = result["anomalies"][0]

    assert anomaly["severity"] == "CRITICAL"


def test_trade_ready_risk_decrease_no_contradiction():
    result = build_engine().analyze(
        build_drift_result(
            risk_flag_count=(
                "SIGNIFICANT_DECREASE"
            ),
            trade_ready=True,
        )
    )

    assert (
        "TRADE_READY_RISK_CONTRADICTION"
        not in anomaly_codes(result)
    )


def test_confidence_setup_divergence():
    result = build_engine().analyze(
        build_drift_result(
            confidence="SIGNIFICANT_INCREASE",
            setup_score="SIGNIFICANT_DECREASE",
        )
    )

    assert (
        "CONFIDENCE_SETUP_DIVERGENCE"
        in anomaly_codes(result)
    )


def test_confidence_setup_divergence_is_high():
    result = build_engine().analyze(
        build_drift_result(
            confidence="MODERATE_INCREASE",
            setup_score="MODERATE_DECREASE",
        )
    )

    anomaly = result["anomalies"][0]

    assert anomaly["severity"] == "HIGH"


def test_confidence_setup_same_direction_no_divergence():
    result = build_engine().analyze(
        build_drift_result(
            confidence="SIGNIFICANT_INCREASE",
            setup_score="SIGNIFICANT_INCREASE",
        )
    )

    assert (
        "CONFIDENCE_SETUP_DIVERGENCE"
        not in anomaly_codes(result)
    )


def test_regime_transition_trade_ready_anomaly():
    result = build_engine().analyze(
        build_drift_result(
            trade_ready=True,
            regime="VOLATILE",
            historical_regime="TRENDING",
        )
    )

    assert (
        "REGIME_TRANSITION_TRADE_READY_ANOMALY"
        in anomaly_codes(result)
    )


def test_regime_transition_decision_trade_ready_anomaly():
    result = build_engine().analyze(
        build_drift_result(
            trade_ready=False,
            decision="TRADE_READY",
            regime="VOLATILE",
            historical_regime="TRENDING",
        )
    )

    assert (
        "REGIME_TRANSITION_TRADE_READY_ANOMALY"
        in anomaly_codes(result)
    )


def test_regime_transition_trade_ready_anomaly_is_high():
    result = build_engine().analyze(
        build_drift_result(
            trade_ready=True,
            regime="VOLATILE",
            historical_regime="TRENDING",
        )
    )

    anomaly = result["anomalies"][0]

    assert anomaly["severity"] == "HIGH"


def test_same_regime_trade_ready_has_no_regime_anomaly():
    result = build_engine().analyze(
        build_drift_result(
            trade_ready=True,
            regime="TRENDING",
            historical_regime="TRENDING",
        )
    )

    assert (
        "REGIME_TRANSITION_TRADE_READY_ANOMALY"
        not in anomaly_codes(result)
    )


def test_regime_transition_without_trade_ready_has_no_anomaly():
    result = build_engine().analyze(
        build_drift_result(
            trade_ready=False,
            decision="HOLD",
            regime="VOLATILE",
            historical_regime="TRENDING",
        )
    )

    assert (
        "REGIME_TRANSITION_TRADE_READY_ANOMALY"
        not in anomaly_codes(result)
    )


@pytest.mark.parametrize(
    "historical_regime",
    [
        None,
        "",
        "UNKNOWN",
        "UNAVAILABLE",
        "NONE",
        "NULL",
    ],
)
def test_invalid_historical_regime_prevents_regime_anomaly(
    historical_regime,
):
    result = build_engine().analyze(
        build_drift_result(
            trade_ready=True,
            regime="VOLATILE",
            historical_regime=historical_regime,
        )
    )

    assert (
        "REGIME_TRANSITION_TRADE_READY_ANOMALY"
        not in anomaly_codes(result)
    )


@pytest.mark.parametrize(
    "current_regime",
    [
        None,
        "",
        "UNKNOWN",
        "UNAVAILABLE",
        "NONE",
        "NULL",
    ],
)
def test_invalid_current_regime_prevents_regime_anomaly(
    current_regime,
):
    result = build_engine().analyze(
        build_drift_result(
            trade_ready=True,
            regime=current_regime,
            historical_regime="TRENDING",
        )
    )

    assert (
        "REGIME_TRANSITION_TRADE_READY_ANOMALY"
        not in anomaly_codes(result)
    )


def test_compound_case_has_six_base_anomalies():
    result = build_engine().analyze(
        build_compound_result()
    )

    assert result["base_anomaly_count"] == 6


def test_compound_case_has_seven_total_anomalies():
    result = build_engine().analyze(
        build_compound_result()
    )

    assert result["anomaly_count"] == 7


def test_compound_case_detects_anomaly():
    result = build_engine().analyze(
        build_compound_result()
    )

    assert result["anomaly_detected"] is True


def test_compound_case_adds_compound_anomaly():
    result = build_engine().analyze(
        build_compound_result()
    )

    assert (
        "COMPOUND_RESEARCH_ANOMALY"
        in anomaly_codes(result)
    )


def test_two_base_anomalies_do_not_add_compound():
    result = build_engine().analyze(
        build_drift_result(
            confidence="SIGNIFICANT_INCREASE",
            readiness="SIGNIFICANT_DECREASE",
            setup_score="SIGNIFICANT_DECREASE",
        )
    )

    assert result["base_anomaly_count"] == 2
    assert (
        "COMPOUND_RESEARCH_ANOMALY"
        not in anomaly_codes(result)
    )


def test_three_base_anomalies_add_compound():
    result = build_engine().analyze(
        build_drift_result(
            confidence="SIGNIFICANT_INCREASE",
            readiness="SIGNIFICANT_DECREASE",
            setup_score="SIGNIFICANT_DECREASE",
            trade_ready=True,
        )
    )

    assert result["base_anomaly_count"] == 3
    assert (
        "COMPOUND_RESEARCH_ANOMALY"
        in anomaly_codes(result)
    )


def test_compound_anomaly_contains_base_codes_as_signals():
    result = build_engine().analyze(
        build_compound_result()
    )

    compound = next(
        anomaly
        for anomaly in result["anomalies"]
        if anomaly["code"]
        == "COMPOUND_RESEARCH_ANOMALY"
    )

    assert (
        "CONFIDENCE_READINESS_DIVERGENCE"
        in compound["signals"]
    )
    assert (
        "TRADE_READY_RISK_CONTRADICTION"
        in compound["signals"]
    )


def test_compound_case_highest_severity_is_critical():
    result = build_engine().analyze(
        build_compound_result()
    )

    assert result["highest_severity"] == "CRITICAL"


def test_high_only_case_highest_severity_is_high():
    result = build_engine().analyze(
        build_drift_result(
            confidence="SIGNIFICANT_INCREASE",
            readiness="SIGNIFICANT_DECREASE",
        )
    )

    assert result["highest_severity"] == "HIGH"


def test_critical_case_highest_severity_is_critical():
    result = build_engine().analyze(
        build_drift_result(
            readiness="SIGNIFICANT_DECREASE",
            trade_ready=True,
        )
    )

    assert result["highest_severity"] == "CRITICAL"


def test_compound_severity_distribution():
    result = build_engine().analyze(
        build_compound_result()
    )

    assert result["severity_distribution"] == [
        {
            "severity": "CRITICAL",
            "count": 3,
        },
        {
            "severity": "HIGH",
            "count": 4,
        },
    ]


def test_high_only_severity_distribution():
    result = build_engine().analyze(
        build_drift_result(
            confidence="SIGNIFICANT_INCREASE",
            readiness="SIGNIFICANT_DECREASE",
        )
    )

    assert result["severity_distribution"] == [
        {
            "severity": "HIGH",
            "count": 1,
        },
    ]


def test_anomaly_codes_match_anomaly_order():
    result = build_engine().analyze(
        build_compound_result()
    )

    assert result["anomaly_codes"] == [
        anomaly["code"]
        for anomaly in result["anomalies"]
    ]


def test_compound_anomaly_is_last():
    result = build_engine().analyze(
        build_compound_result()
    )

    assert (
        result["anomaly_codes"][-1]
        == "COMPOUND_RESEARCH_ANOMALY"
    )


def test_source_overall_drift_is_preserved():
    result = build_engine().analyze(
        build_compound_result()
    )

    assert (
        result["source_overall_drift_state"]
        == "SIGNIFICANT_DRIFT"
    )


def test_source_overall_drift_is_normalized():
    source = build_compound_result()

    source["overall_drift"]["state"] = (
        " significant_drift "
    )

    result = build_engine().analyze(source)

    assert (
        result["source_overall_drift_state"]
        == "SIGNIFICANT_DRIFT"
    )


def test_significant_drift_anomaly_adds_coincidence_observation():
    result = build_engine().analyze(
        build_compound_result()
    )

    assert (
        "Cross-signal anomalies coincided "
        "with significant baseline drift."
        in result["research_observations"]
    )


def test_stable_source_with_anomaly_does_not_add_coincidence_observation():
    result = build_engine().analyze(
        build_drift_result(
            confidence="SIGNIFICANT_INCREASE",
            readiness="SIGNIFICANT_DECREASE",
            overall_state="STABLE",
        )
    )

    assert (
        "Cross-signal anomalies coincided "
        "with significant baseline drift."
        not in result["research_observations"]
    )


def test_each_compound_anomaly_description_is_observed():
    result = build_engine().analyze(
        build_compound_result()
    )

    observations = result[
        "research_observations"
    ]

    for anomaly in result["anomalies"]:
        assert (
            anomaly["description"]
            in observations
        )


def test_research_observations_are_deduplicated():
    result = build_engine().analyze(
        build_compound_result()
    )

    observations = result[
        "research_observations"
    ]

    assert len(observations) == len(
        set(observations)
    )


@pytest.mark.parametrize(
    "drift_value",
    [
        None,
        "",
        [],
        {},
        True,
        123,
    ],
)
def test_invalid_metric_drift_does_not_create_anomaly(
    drift_value,
):
    source = build_drift_result()

    source["metric_drift"]["confidence"] = {
        "drift": drift_value,
    }

    source["metric_drift"]["readiness"] = {
        "drift": "SIGNIFICANT_DECREASE",
    }

    result = build_engine().analyze(source)

    assert (
        "CONFIDENCE_READINESS_DIVERGENCE"
        not in anomaly_codes(result)
    )


def test_metric_drift_is_case_normalized():
    result = build_engine().analyze(
        build_drift_result(
            confidence=" significant_increase ",
            readiness=" significant_decrease ",
        )
    )

    assert (
        "CONFIDENCE_READINESS_DIVERGENCE"
        in anomaly_codes(result)
    )


def test_moderate_increase_counts_as_increase():
    result = build_engine().analyze(
        build_drift_result(
            confidence="MODERATE_INCREASE",
            readiness="MODERATE_DECREASE",
        )
    )

    assert result["anomaly_detected"] is True


def test_significant_increase_counts_as_increase():
    result = build_engine().analyze(
        build_drift_result(
            confidence="SIGNIFICANT_INCREASE",
            readiness="SIGNIFICANT_DECREASE",
        )
    )

    assert result["anomaly_detected"] is True


def test_stable_drift_does_not_count_as_increase():
    result = build_engine().analyze(
        build_drift_result(
            confidence="STABLE",
            readiness="SIGNIFICANT_DECREASE",
        )
    )

    assert result["anomaly_detected"] is False


def test_trade_ready_must_be_real_boolean_true():
    source = build_drift_result(
        readiness="SIGNIFICANT_DECREASE",
    )

    source["current"][
        "trade_ready_observed"
    ] = 1

    result = build_engine().analyze(source)

    assert (
        "TRADE_READY_READINESS_CONTRADICTION"
        not in anomaly_codes(result)
    )


@pytest.mark.parametrize(
    "value",
    [
        "true",
        "TRUE",
        1,
        0,
        [],
        {},
    ],
)
def test_non_boolean_trade_ready_is_not_treated_as_true(
    value,
):
    source = build_drift_result(
        risk_flag_count=(
            "SIGNIFICANT_INCREASE"
        ),
    )

    source["current"][
        "trade_ready_observed"
    ] = value

    result = build_engine().analyze(source)

    assert (
        "TRADE_READY_RISK_CONTRADICTION"
        not in anomaly_codes(result)
    )


def test_decision_category_is_case_normalized():
    result = build_engine().analyze(
        build_drift_result(
            trade_ready=False,
            decision=" trade_ready ",
            regime="VOLATILE",
            historical_regime="TRENDING",
        )
    )

    assert (
        "REGIME_TRANSITION_TRADE_READY_ANOMALY"
        in anomaly_codes(result)
    )


def test_analyse_alias_matches_analyze():
    source = build_compound_result()
    engine = build_engine()

    assert engine.analyse(source) == engine.analyze(
        source
    )


def test_result_is_independent_after_source_mutation():
    source = build_compound_result()

    result = build_engine().analyze(source)

    source["current"]["decision"] = "CHANGED"
    source["metric_drift"][
        "confidence"
    ]["drift"] = "STABLE"

    assert result["anomaly_detected"] is True
    assert (
        "CONFIDENCE_READINESS_DIVERGENCE"
        in result["anomaly_codes"]
    )


def test_public_result_contains_expected_sections():
    result = build_engine().analyze(
        build_compound_result()
    )

    expected = {
        "status",
        "read_only",
        "research_only",
        "anomaly_detected",
        "anomaly_count",
        "base_anomaly_count",
        "highest_severity",
        "severity_distribution",
        "anomaly_codes",
        "anomalies",
        "source_overall_drift_state",
        "research_observations",
    }

    assert expected.issubset(
        result.keys()
    )


def test_anomaly_records_have_expected_schema():
    result = build_engine().analyze(
        build_compound_result()
    )

    for anomaly in result["anomalies"]:
        assert set(anomaly.keys()) == {
            "code",
            "severity",
            "signals",
            "description",
        }


def test_anomaly_codes_are_unique():
    result = build_engine().analyze(
        build_compound_result()
    )

    codes = result["anomaly_codes"]

    assert len(codes) == len(set(codes))


def test_compound_case_exact_codes():
    result = build_engine().analyze(
        build_compound_result()
    )

    assert result["anomaly_codes"] == [
        "CONFIDENCE_READINESS_DIVERGENCE",
        "CONFIDENCE_RISK_DIVERGENCE",
        (
            "TRADE_READY_READINESS_"
            "CONTRADICTION"
        ),
        "TRADE_READY_RISK_CONTRADICTION",
        "CONFIDENCE_SETUP_DIVERGENCE",
        (
            "REGIME_TRANSITION_TRADE_READY_"
            "ANOMALY"
        ),
        "COMPOUND_RESEARCH_ANOMALY",
    ]