from copy import deepcopy

import pytest

from services.research_anomaly_outcome_correlation import (
    ResearchAnomalyOutcomeCorrelation,
)
from services.research_evidence_stability_intelligence import (
    ResearchEvidenceStabilityIntelligence,
)


def build_engine():
    return ResearchEvidenceStabilityIntelligence()


def build_outcome(
    session_date,
    realized_pnl,
    index=0,
):
    if realized_pnl > 0:
        outcome = "WIN"
    elif realized_pnl < 0:
        outcome = "LOSS"
    else:
        outcome = "FLAT"

    return {
        "index": index,
        "session_date": session_date,
        "realized_pnl": realized_pnl,
        "outcome": outcome,
    }


def build_record(
    code="ANOMALY_A",
    outcomes=None,
):
    return {
        "code": code,
        "linked_trade_outcomes": deepcopy(
            outcomes or []
        ),
    }


def build_combination(
    codes=None,
    outcomes=None,
):
    return {
        "codes": list(
            codes or ["ANOMALY_A", "ANOMALY_B"]
        ),
        "linked_trade_outcomes": deepcopy(
            outcomes or []
        ),
    }


def build_source(
    anomaly_correlations=None,
    combination_correlations=None,
):
    return {
        "anomaly_correlations": deepcopy(
            anomaly_correlations or []
        ),
        "combination_correlations": deepcopy(
            combination_correlations or []
        ),
    }


def negative_outcomes(
    count=10,
    pnl=-100.0,
    month="06",
):
    return [
        build_outcome(
            f"2026-{month}-{index:02d}",
            pnl,
            index=index,
        )
        for index in range(1, count + 1)
    ]


def positive_outcomes(
    count=10,
    pnl=100.0,
    month="07",
):
    return [
        build_outcome(
            f"2026-{month}-{index:02d}",
            pnl,
            index=index,
        )
        for index in range(1, count + 1)
    ]


def test_empty_source_returns_completed_read_only_result():
    result = build_engine().analyze({})

    assert result["status"] == "COMPLETED"
    assert result["read_only"] is True
    assert result["research_only"] is True
    assert result["correlation_not_causation"] is True
    assert result["anomalies_observed"] == 0
    assert result["combinations_observed"] == 0


def test_none_source_is_rejected():
    with pytest.raises(
        ValueError,
        match="correlation_result cannot be None",
    ):
        build_engine().analyze(None)


@pytest.mark.parametrize(
    "source",
    [
        [],
        "invalid",
        123,
        True,
    ],
)
def test_non_dictionary_source_is_rejected(source):
    with pytest.raises(
        ValueError,
        match=(
            "correlation_result must be a dictionary"
        ),
    ):
        build_engine().analyze(source)


def test_analyze_does_not_mutate_source():
    source = build_source(
        anomaly_correlations=[
            build_record(
                outcomes=(
                    negative_outcomes()
                    + positive_outcomes()
                )
            )
        ]
    )
    original = deepcopy(source)

    build_engine().analyze(source)

    assert source == original


def test_direction_reversal_is_detected():
    outcomes = (
        negative_outcomes(
            count=10,
            pnl=-200.0,
        )
        + positive_outcomes(
            count=10,
            pnl=150.0,
        )
    )

    result = build_engine().analyze(
        build_source(
            anomaly_correlations=[
                build_record(outcomes=outcomes)
            ]
        )
    )

    item = result["anomaly_stability"][0]

    assert item["stability_state"] == (
        "DIRECTION_REVERSAL"
    )
    assert item["earlier_direction"] == "NEGATIVE"
    assert item["recent_direction"] == "POSITIVE"


def test_complete_direction_reversal_has_200_magnitude():
    outcomes = (
        negative_outcomes(
            count=10,
            pnl=-200.0,
        )
        + positive_outcomes(
            count=10,
            pnl=150.0,
        )
    )

    result = build_engine().analyze(
        build_source(
            anomaly_correlations=[
                build_record(outcomes=outcomes)
            ]
        )
    )

    item = result["anomaly_stability"][0]

    assert (
        item["directional_consistency_change"]
        == 0.0
    )
    assert item["stability_magnitude"] == 200.0


def test_positive_to_negative_reversal_has_200_magnitude():
    outcomes = (
        positive_outcomes(
            count=10,
            pnl=200.0,
            month="06",
        )
        + negative_outcomes(
            count=10,
            pnl=-150.0,
            month="07",
        )
    )

    result = build_engine().analyze(
        build_source(
            anomaly_correlations=[
                build_record(outcomes=outcomes)
            ]
        )
    )

    item = result["anomaly_stability"][0]

    assert item["earlier_direction"] == "POSITIVE"
    assert item["recent_direction"] == "NEGATIVE"
    assert item["stability_state"] == (
        "DIRECTION_REVERSAL"
    )
    assert item["stability_magnitude"] == 200.0


def test_average_pnl_change_is_preserved():
    outcomes = (
        negative_outcomes(
            count=10,
            pnl=-200.0,
        )
        + positive_outcomes(
            count=10,
            pnl=150.0,
        )
    )

    result = build_engine().analyze(
        build_source(
            anomaly_correlations=[
                build_record(outcomes=outcomes)
            ]
        )
    )

    item = result["anomaly_stability"][0]

    assert item["average_pnl_change"] == 350.0


def test_insufficient_data_is_reported():
    outcomes = (
        negative_outcomes(
            count=2,
            pnl=-100.0,
        )
        + positive_outcomes(
            count=2,
            pnl=100.0,
        )
    )

    result = build_engine().analyze(
        build_source(
            anomaly_correlations=[
                build_record(outcomes=outcomes)
            ]
        )
    )

    item = result["anomaly_stability"][0]

    assert item["stability_state"] == (
        "INSUFFICIENT_DATA"
    )
    assert item["stability_magnitude"] is None


def test_strongest_reversal_uses_directional_magnitude():
    complete_reversal = (
        negative_outcomes(
            count=10,
            pnl=-100.0,
            month="06",
        )
        + positive_outcomes(
            count=10,
            pnl=100.0,
            month="07",
        )
    )

    partial_reversal = []

    for index in range(1, 11):
        pnl = -100.0 if index <= 6 else 0.0

        partial_reversal.append(
            build_outcome(
                f"2026-06-{index:02d}",
                pnl,
                index=index,
            )
        )

    for index in range(1, 11):
        pnl = 100.0 if index <= 9 else 0.0

        partial_reversal.append(
            build_outcome(
                f"2026-07-{index:02d}",
                pnl,
                index=index + 10,
            )
        )

    result = build_engine().analyze(
        build_source(
            anomaly_correlations=[
                build_record(
                    code="COMPLETE_REVERSAL",
                    outcomes=complete_reversal,
                ),
                build_record(
                    code="PARTIAL_REVERSAL",
                    outcomes=partial_reversal,
                ),
            ]
        )
    )

    strongest = result[
        "strongest_direction_reversal"
    ]

    assert strongest["code"] == "COMPLETE_REVERSAL"
    assert strongest["stability_magnitude"] == 200.0


def test_combination_stability_is_analyzed():
    outcomes = (
        negative_outcomes()
        + positive_outcomes()
    )

    result = build_engine().analyze(
        build_source(
            combination_correlations=[
                build_combination(
                    outcomes=outcomes
                )
            ]
        )
    )

    assert result["combinations_observed"] == 1
    assert len(result["combination_stability"]) == 1
    assert (
        result["combination_stability"][0][
            "record_type"
        ]
        == "COMBINATION"
    )


def test_reversal_observation_is_added():
    outcomes = (
        negative_outcomes()
        + positive_outcomes()
    )

    result = build_engine().analyze(
        build_source(
            anomaly_correlations=[
                build_record(
                    code="ANOMALY_A",
                    outcomes=outcomes,
                )
            ]
        )
    )

    assert (
        "ANOMALY_A showed a direction reversal "
        "between earlier and recent outcome evidence."
        in result["research_observations"]
    )


def test_returned_result_is_independent_of_source():
    outcomes = (
        negative_outcomes()
        + positive_outcomes()
    )

    source = build_source(
        anomaly_correlations=[
            build_record(outcomes=outcomes)
        ]
    )

    result = build_engine().analyze(source)

    result["anomaly_stability"][0][
        "earlier_window"
    ]["trades"] = 999

    assert (
        source["anomaly_correlations"][0][
            "linked_trade_outcomes"
        ][0]["realized_pnl"]
        == -100.0
    )


def test_task16_to_task18_real_integration_detects_reversal():
    sessions = [
        {
            "session_date": f"2026-06-{index:02d}",
            "research_anomaly_intelligence": {
                "anomaly_codes": [
                    "CONFIDENCE_RISK_DIVERGENCE",
                ],
            },
        }
        for index in range(1, 11)
    ]

    sessions += [
        {
            "session_date": f"2026-07-{index:02d}",
            "research_anomaly_intelligence": {
                "anomaly_codes": [
                    "CONFIDENCE_RISK_DIVERGENCE",
                ],
            },
        }
        for index in range(1, 11)
    ]

    trades = [
        {
            "status": "CLOSED",
            "realized_pnl": -200.0,
            "session_date": f"2026-06-{index:02d}",
        }
        for index in range(1, 11)
    ]

    trades += [
        {
            "status": "CLOSED",
            "realized_pnl": 150.0,
            "session_date": f"2026-07-{index:02d}",
        }
        for index in range(1, 11)
    ]

    correlation_result = (
        ResearchAnomalyOutcomeCorrelation().analyze(
            sessions,
            trades,
        )
    )

    linked_outcomes = (
        correlation_result[
            "anomaly_correlations"
        ][0]["linked_trade_outcomes"]
    )

    assert len(linked_outcomes) == 20

    result = build_engine().analyze(
        correlation_result
    )

    assert result["status"] == "COMPLETED"
    assert result["read_only"] is True
    assert result["research_only"] is True
    assert result["correlation_not_causation"] is True
    assert result["anomalies_observed"] == 1

    item = result["anomaly_stability"][0]

    assert item["code"] == (
        "CONFIDENCE_RISK_DIVERGENCE"
    )
    assert item["linked_closed_trades"] == 20

    assert item["earlier_window"]["trades"] == 10
    assert item["earlier_window"]["wins"] == 0
    assert item["earlier_window"]["losses"] == 10
    assert (
        item["earlier_window"]["direction"]
        == "NEGATIVE"
    )
    assert (
        item["earlier_window"][
            "average_realized_pnl"
        ]
        == -200.0
    )

    assert item["recent_window"]["trades"] == 10
    assert item["recent_window"]["wins"] == 10
    assert item["recent_window"]["losses"] == 0
    assert (
        item["recent_window"]["direction"]
        == "POSITIVE"
    )
    assert (
        item["recent_window"][
            "average_realized_pnl"
        ]
        == 150.0
    )

    assert item["earlier_direction"] == "NEGATIVE"
    assert item["recent_direction"] == "POSITIVE"

    assert (
        item["stability_state"]
        == "DIRECTION_REVERSAL"
    )

    assert (
        item["directional_consistency_change"]
        == 0.0
    )
    assert item["average_pnl_change"] == 350.0
    assert item["stability_magnitude"] == 200.0

    strongest = result[
        "strongest_direction_reversal"
    ]

    assert strongest is not None
    assert strongest["code"] == (
        "CONFIDENCE_RISK_DIVERGENCE"
    )
    assert (
        strongest["stability_state"]
        == "DIRECTION_REVERSAL"
    )
    assert (
        strongest["stability_magnitude"]
        == 200.0
    )

    assert (
        "CONFIDENCE_RISK_DIVERGENCE showed a "
        "direction reversal between earlier and "
        "recent outcome evidence."
        in result["research_observations"]
    )