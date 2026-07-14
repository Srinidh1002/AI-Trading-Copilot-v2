from copy import deepcopy

import pytest

from services.research_anomaly_outcome_reliability import (
    ResearchAnomalyOutcomeReliability,
)


def build_engine():
    return ResearchAnomalyOutcomeReliability()


def build_correlation(
    code="ANOMALY_A",
    anomaly_sessions=10,
    linked_closed_trades=10,
    wins=7,
    losses=2,
    flat=1,
    average_realized_pnl=100.0,
    outcome_state="POSITIVE_CORRELATION",
):
    total = wins + losses + flat

    if total > 0:
        win_rate = round(
            wins / total * 100.0,
            4,
        )
        loss_rate = round(
            losses / total * 100.0,
            4,
        )
    else:
        win_rate = 0.0
        loss_rate = 0.0

    return {
        "code": code,
        "anomaly_sessions": anomaly_sessions,
        "linked_closed_trades": (
            linked_closed_trades
        ),
        "wins": wins,
        "losses": losses,
        "flat": flat,
        "win_rate_percent": win_rate,
        "loss_rate_percent": loss_rate,
        "average_realized_pnl": (
            average_realized_pnl
        ),
        "outcome_state": outcome_state,
    }


def build_combination(
    codes=None,
    anomaly_sessions=10,
    linked_closed_trades=10,
    wins=1,
    losses=9,
    flat=0,
    average_realized_pnl=-100.0,
):
    if codes is None:
        codes = [
            "ANOMALY_A",
            "ANOMALY_B",
        ]

    total = wins + losses + flat

    if total > 0:
        win_rate = round(
            wins / total * 100.0,
            4,
        )
        loss_rate = round(
            losses / total * 100.0,
            4,
        )
    else:
        win_rate = 0.0
        loss_rate = 0.0

    return {
        "codes": codes,
        "anomaly_sessions": anomaly_sessions,
        "linked_closed_trades": (
            linked_closed_trades
        ),
        "wins": wins,
        "losses": losses,
        "flat": flat,
        "win_rate_percent": win_rate,
        "loss_rate_percent": loss_rate,
        "average_realized_pnl": (
            average_realized_pnl
        ),
        "outcome_state": (
            "NEGATIVE_CORRELATION"
        ),
    }


def build_source(
    anomaly_correlations=None,
    combination_correlations=None,
):
    return {
        "anomaly_correlations": (
            anomaly_correlations
            if anomaly_correlations is not None
            else []
        ),
        "combination_correlations": (
            combination_correlations
            if combination_correlations is not None
            else []
        ),
    }


def test_none_input_is_rejected():
    with pytest.raises(ValueError):
        build_engine().analyze(None)


@pytest.mark.parametrize(
    "value",
    [
        [],
        (),
        "invalid",
        1,
        1.5,
        True,
    ],
)
def test_non_dictionary_input_is_rejected(value):
    with pytest.raises(ValueError):
        build_engine().analyze(value)


def test_empty_dictionary_returns_completed():
    result = build_engine().analyze({})

    assert result["status"] == "COMPLETED"
    assert result["read_only"] is True
    assert result["research_only"] is True
    assert (
        result["correlation_not_causation"]
        is True
    )


def test_empty_dictionary_has_zero_counts():
    result = build_engine().analyze({})

    assert result["anomalies_observed"] == 0
    assert result["combinations_observed"] == 0


def test_empty_dictionary_has_empty_records():
    result = build_engine().analyze({})

    assert result["anomaly_reliability"] == []
    assert result["combination_reliability"] == []


def test_empty_dictionary_has_no_strongest_evidence():
    result = build_engine().analyze({})

    assert (
        result["strongest_negative_evidence"]
        is None
    )
    assert (
        result["strongest_positive_evidence"]
        is None
    )


def test_empty_dictionary_has_research_observation():
    result = build_engine().analyze({})

    assert result["research_observations"] == [
        (
            "No anomaly outcome correlations "
            "were available for reliability "
            "analysis."
        )
    ]


def test_input_is_not_mutated():
    source = build_source(
        anomaly_correlations=[
            build_correlation(),
        ],
        combination_correlations=[
            build_combination(),
        ],
    )

    original = deepcopy(source)

    build_engine().analyze(source)

    assert source == original


def test_result_is_independent_from_input():
    source = build_source(
        anomaly_correlations=[
            build_correlation(),
        ],
    )

    result = build_engine().analyze(source)

    source[
        "anomaly_correlations"
    ][0]["code"] = "CHANGED"

    assert (
        result["anomaly_reliability"][0]["code"]
        == "ANOMALY_A"
    )


def test_result_calls_are_independent():
    engine = build_engine()

    first = engine.analyze(
        build_source(
            anomaly_correlations=[
                build_correlation(),
            ],
        )
    )

    first["anomaly_reliability"][0][
        "code"
    ] = "CHANGED"

    second = engine.analyze(
        build_source(
            anomaly_correlations=[
                build_correlation(),
            ],
        )
    )

    assert (
        second["anomaly_reliability"][0]["code"]
        == "ANOMALY_A"
    )


@pytest.mark.parametrize(
    (
        "linked_closed_trades",
        "expected",
    ),
    [
        (0, "NONE"),
        (1, "VERY_LOW"),
        (4, "VERY_LOW"),
        (5, "LOW"),
        (9, "LOW"),
        (10, "MODERATE"),
        (19, "MODERATE"),
        (20, "HIGH"),
        (49, "HIGH"),
        (50, "VERY_HIGH"),
        (100, "VERY_HIGH"),
    ],
)
def test_evidence_level_boundaries(
    linked_closed_trades,
    expected,
):
    correlation = build_correlation(
        linked_closed_trades=(
            linked_closed_trades
        ),
    )

    result = build_engine().analyze(
        build_source(
            anomaly_correlations=[
                correlation,
            ],
        )
    )

    record = result[
        "anomaly_reliability"
    ][0]

    assert record["evidence_level"] == expected


def test_zero_outcomes_have_no_directional_consistency():
    correlation = build_correlation(
        linked_closed_trades=0,
        wins=0,
        losses=0,
        flat=0,
        average_realized_pnl=None,
    )

    result = build_engine().analyze(
        build_source(
            anomaly_correlations=[
                correlation,
            ],
        )
    )

    record = result[
        "anomaly_reliability"
    ][0]

    assert (
        record[
            "directional_consistency_percent"
        ]
        is None
    )


def test_zero_outcomes_have_no_standard_error():
    correlation = build_correlation(
        linked_closed_trades=0,
        wins=0,
        losses=0,
        flat=0,
        average_realized_pnl=None,
    )

    result = build_engine().analyze(
        build_source(
            anomaly_correlations=[
                correlation,
            ],
        )
    )

    record = result[
        "anomaly_reliability"
    ][0]

    assert (
        record["proportion_standard_error"]
        is None
    )


def test_directional_consistency_uses_dominant_outcome():
    correlation = build_correlation(
        linked_closed_trades=10,
        wins=2,
        losses=7,
        flat=1,
        average_realized_pnl=-50,
    )

    result = build_engine().analyze(
        build_source(
            anomaly_correlations=[
                correlation,
            ],
        )
    )

    record = result[
        "anomaly_reliability"
    ][0]

    assert (
        record[
            "directional_consistency_percent"
        ]
        == 70.0
    )


def test_standard_error_is_calculated():
    correlation = build_correlation(
        linked_closed_trades=10,
        wins=2,
        losses=7,
        flat=1,
        average_realized_pnl=-50,
    )

    result = build_engine().analyze(
        build_source(
            anomaly_correlations=[
                correlation,
            ],
        )
    )

    record = result[
        "anomaly_reliability"
    ][0]

    assert (
        record["proportion_standard_error"]
        == 0.144914
    )


def test_no_linked_trades_is_insufficient_data():
    correlation = build_correlation(
        linked_closed_trades=0,
        wins=0,
        losses=0,
        flat=0,
        average_realized_pnl=None,
    )

    result = build_engine().analyze(
        build_source(
            anomaly_correlations=[
                correlation,
            ],
        )
    )

    assert (
        result["anomaly_reliability"][0][
            "reliability_state"
        ]
        == "INSUFFICIENT_DATA"
    )


def test_missing_average_pnl_is_insufficient_data():
    correlation = build_correlation(
        linked_closed_trades=10,
        wins=7,
        losses=2,
        flat=1,
        average_realized_pnl=None,
    )

    result = build_engine().analyze(
        build_source(
            anomaly_correlations=[
                correlation,
            ],
        )
    )

    assert (
        result["anomaly_reliability"][0][
            "reliability_state"
        ]
        == "INSUFFICIENT_DATA"
    )


@pytest.mark.parametrize(
    "linked_closed_trades",
    [
        1,
        2,
        3,
        4,
    ],
)
def test_tiny_sample_is_weak_evidence(
    linked_closed_trades,
):
    correlation = build_correlation(
        linked_closed_trades=(
            linked_closed_trades
        ),
        wins=0,
        losses=linked_closed_trades,
        flat=0,
        average_realized_pnl=-1000,
    )

    result = build_engine().analyze(
        build_source(
            anomaly_correlations=[
                correlation,
            ],
        )
    )

    assert (
        result["anomaly_reliability"][0][
            "reliability_state"
        ]
        == "WEAK_EVIDENCE"
    )


def test_two_of_two_losses_are_not_strong_evidence():
    correlation = build_correlation(
        linked_closed_trades=2,
        wins=0,
        losses=2,
        flat=0,
        average_realized_pnl=-500,
    )

    result = build_engine().analyze(
        build_source(
            anomaly_correlations=[
                correlation,
            ],
        )
    )

    record = result[
        "anomaly_reliability"
    ][0]

    assert (
        record[
            "directional_consistency_percent"
        ]
        == 100.0
    )
    assert (
        record["reliability_state"]
        == "WEAK_EVIDENCE"
    )


def test_five_negative_trades_are_weak_negative():
    correlation = build_correlation(
        linked_closed_trades=5,
        wins=0,
        losses=5,
        flat=0,
        average_realized_pnl=-100,
    )

    result = build_engine().analyze(
        build_source(
            anomaly_correlations=[
                correlation,
            ],
        )
    )

    assert (
        result["anomaly_reliability"][0][
            "reliability_state"
        ]
        == "WEAK_NEGATIVE_EVIDENCE"
    )


def test_five_positive_trades_are_weak_positive():
    correlation = build_correlation(
        linked_closed_trades=5,
        wins=5,
        losses=0,
        flat=0,
        average_realized_pnl=100,
    )

    result = build_engine().analyze(
        build_source(
            anomaly_correlations=[
                correlation,
            ],
        )
    )

    assert (
        result["anomaly_reliability"][0][
            "reliability_state"
        ]
        == "WEAK_POSITIVE_EVIDENCE"
    )


def test_ten_trades_sixty_percent_negative_is_moderate():
    correlation = build_correlation(
        linked_closed_trades=10,
        wins=4,
        losses=6,
        flat=0,
        average_realized_pnl=-100,
    )

    result = build_engine().analyze(
        build_source(
            anomaly_correlations=[
                correlation,
            ],
        )
    )

    assert (
        result["anomaly_reliability"][0][
            "reliability_state"
        ]
        == "MODERATE_NEGATIVE_EVIDENCE"
    )


def test_ten_trades_sixty_percent_positive_is_moderate():
    correlation = build_correlation(
        linked_closed_trades=10,
        wins=6,
        losses=4,
        flat=0,
        average_realized_pnl=100,
    )

    result = build_engine().analyze(
        build_source(
            anomaly_correlations=[
                correlation,
            ],
        )
    )

    assert (
        result["anomaly_reliability"][0][
            "reliability_state"
        ]
        == "MODERATE_POSITIVE_EVIDENCE"
    )


def test_ten_trades_below_sixty_percent_is_weak():
    correlation = build_correlation(
        linked_closed_trades=10,
        wins=5,
        losses=4,
        flat=1,
        average_realized_pnl=100,
    )

    result = build_engine().analyze(
        build_source(
            anomaly_correlations=[
                correlation,
            ],
        )
    )

    assert (
        result["anomaly_reliability"][0][
            "reliability_state"
        ]
        == "WEAK_POSITIVE_EVIDENCE"
    )


def test_twenty_trades_seventy_percent_negative_is_strong():
    correlation = build_correlation(
        linked_closed_trades=20,
        wins=5,
        losses=14,
        flat=1,
        average_realized_pnl=-100,
    )

    result = build_engine().analyze(
        build_source(
            anomaly_correlations=[
                correlation,
            ],
        )
    )

    assert (
        result["anomaly_reliability"][0][
            "reliability_state"
        ]
        == "STRONG_NEGATIVE_EVIDENCE"
    )


def test_twenty_trades_seventy_percent_positive_is_strong():
    correlation = build_correlation(
        linked_closed_trades=20,
        wins=14,
        losses=5,
        flat=1,
        average_realized_pnl=100,
    )

    result = build_engine().analyze(
        build_source(
            anomaly_correlations=[
                correlation,
            ],
        )
    )

    assert (
        result["anomaly_reliability"][0][
            "reliability_state"
        ]
        == "STRONG_POSITIVE_EVIDENCE"
    )


def test_twenty_trades_below_seventy_can_be_moderate():
    correlation = build_correlation(
        linked_closed_trades=20,
        wins=13,
        losses=6,
        flat=1,
        average_realized_pnl=100,
    )

    result = build_engine().analyze(
        build_source(
            anomaly_correlations=[
                correlation,
            ],
        )
    )

    assert (
        result["anomaly_reliability"][0][
            "reliability_state"
        ]
        == "MODERATE_POSITIVE_EVIDENCE"
    )


def test_zero_average_pnl_is_neutral_evidence():
    correlation = build_correlation(
        linked_closed_trades=10,
        wins=5,
        losses=5,
        flat=0,
        average_realized_pnl=0,
    )

    result = build_engine().analyze(
        build_source(
            anomaly_correlations=[
                correlation,
            ],
        )
    )

    assert (
        result["anomaly_reliability"][0][
            "reliability_state"
        ]
        == "NEUTRAL_EVIDENCE"
    )


def test_zero_average_pnl_with_twenty_trades_is_strong_neutral():
    correlation = build_correlation(
        linked_closed_trades=20,
        wins=10,
        losses=10,
        flat=0,
        average_realized_pnl=0,
    )

    result = build_engine().analyze(
        build_source(
            anomaly_correlations=[
                correlation,
            ],
        )
    )

    assert (
        result["anomaly_reliability"][0][
            "reliability_state"
        ]
        == "STRONG_NEUTRAL_EVIDENCE"
    )


def test_anomaly_record_has_record_type():
    result = build_engine().analyze(
        build_source(
            anomaly_correlations=[
                build_correlation(),
            ],
        )
    )

    assert (
        result["anomaly_reliability"][0][
            "record_type"
        ]
        == "ANOMALY"
    )


def test_combination_record_has_record_type():
    result = build_engine().analyze(
        build_source(
            combination_correlations=[
                build_combination(),
            ],
        )
    )

    assert (
        result["combination_reliability"][0][
            "record_type"
        ]
        == "COMBINATION"
    )


def test_combination_codes_are_sorted_and_deduplicated():
    combination = build_combination(
        codes=[
            "B",
            "A",
            "B",
            "",
            None,
        ],
    )

    result = build_engine().analyze(
        build_source(
            combination_correlations=[
                combination,
            ],
        )
    )

    assert (
        result["combination_reliability"][0][
            "codes"
        ]
        == ["A", "B"]
    )


def test_anomaly_records_are_sorted_by_code():
    source = build_source(
        anomaly_correlations=[
            build_correlation(code="Z"),
            build_correlation(code="A"),
            build_correlation(code="M"),
        ],
    )

    result = build_engine().analyze(source)

    assert [
        item["code"]
        for item in result["anomaly_reliability"]
    ] == [
        "A",
        "M",
        "Z",
    ]


def test_combination_records_are_sorted_by_codes():
    source = build_source(
        combination_correlations=[
            build_combination(
                codes=["Z", "Y"],
            ),
            build_combination(
                codes=["B", "A"],
            ),
        ],
    )

    result = build_engine().analyze(source)

    assert [
        item["codes"]
        for item in result[
            "combination_reliability"
        ]
    ] == [
        ["A", "B"],
        ["Y", "Z"],
    ]


def test_evidence_distribution_is_counted():
    source = build_source(
        anomaly_correlations=[
            build_correlation(
                code="A",
                linked_closed_trades=2,
            ),
            build_correlation(
                code="B",
                linked_closed_trades=12,
            ),
            build_correlation(
                code="C",
                linked_closed_trades=30,
            ),
        ],
    )

    result = build_engine().analyze(source)

    assert result["evidence_distribution"] == [
        {
            "evidence_level": "VERY_LOW",
            "count": 1,
        },
        {
            "evidence_level": "MODERATE",
            "count": 1,
        },
        {
            "evidence_level": "HIGH",
            "count": 1,
        },
    ]


def test_reliability_distribution_is_counted():
    source = build_source(
        anomaly_correlations=[
            build_correlation(
                code="A",
                linked_closed_trades=2,
                wins=0,
                losses=2,
                flat=0,
                average_realized_pnl=-100,
            ),
            build_correlation(
                code="B",
                linked_closed_trades=10,
                wins=6,
                losses=4,
                flat=0,
                average_realized_pnl=100,
            ),
        ],
    )

    result = build_engine().analyze(source)

    assert result[
        "reliability_distribution"
    ] == [
        {
            "reliability_state": (
                "MODERATE_POSITIVE_EVIDENCE"
            ),
            "count": 1,
        },
        {
            "reliability_state": (
                "WEAK_EVIDENCE"
            ),
            "count": 1,
        },
    ]


def test_strongest_negative_prefers_more_trades():
    source = build_source(
        anomaly_correlations=[
            build_correlation(
                code="A",
                linked_closed_trades=20,
                wins=2,
                losses=18,
                flat=0,
                average_realized_pnl=-500,
            ),
            build_correlation(
                code="B",
                linked_closed_trades=30,
                wins=8,
                losses=22,
                flat=0,
                average_realized_pnl=-100,
            ),
        ],
    )

    result = build_engine().analyze(source)

    assert (
        result["strongest_negative_evidence"][
            "code"
        ]
        == "B"
    )


def test_strongest_positive_prefers_more_trades():
    source = build_source(
        anomaly_correlations=[
            build_correlation(
                code="A",
                linked_closed_trades=20,
                wins=18,
                losses=2,
                flat=0,
                average_realized_pnl=500,
            ),
            build_correlation(
                code="B",
                linked_closed_trades=30,
                wins=22,
                losses=8,
                flat=0,
                average_realized_pnl=100,
            ),
        ],
    )

    result = build_engine().analyze(source)

    assert (
        result["strongest_positive_evidence"][
            "code"
        ]
        == "B"
    )


def test_strongest_negative_prefers_consistency_on_trade_tie():
    source = build_source(
        anomaly_correlations=[
            build_correlation(
                code="A",
                linked_closed_trades=20,
                wins=6,
                losses=14,
                flat=0,
                average_realized_pnl=-500,
            ),
            build_correlation(
                code="B",
                linked_closed_trades=20,
                wins=2,
                losses=18,
                flat=0,
                average_realized_pnl=-100,
            ),
        ],
    )

    result = build_engine().analyze(source)

    assert (
        result["strongest_negative_evidence"][
            "code"
        ]
        == "B"
    )


def test_strongest_positive_prefers_consistency_on_trade_tie():
    source = build_source(
        anomaly_correlations=[
            build_correlation(
                code="A",
                linked_closed_trades=20,
                wins=14,
                losses=6,
                flat=0,
                average_realized_pnl=500,
            ),
            build_correlation(
                code="B",
                linked_closed_trades=20,
                wins=18,
                losses=2,
                flat=0,
                average_realized_pnl=100,
            ),
        ],
    )

    result = build_engine().analyze(source)

    assert (
        result["strongest_positive_evidence"][
            "code"
        ]
        == "B"
    )


def test_malformed_correlation_lists_are_safe():
    result = build_engine().analyze(
        {
            "anomaly_correlations": "invalid",
            "combination_correlations": 123,
        }
    )

    assert result["anomaly_reliability"] == []
    assert result["combination_reliability"] == []


def test_non_dictionary_records_are_ignored():
    result = build_engine().analyze(
        {
            "anomaly_correlations": [
                None,
                "invalid",
                123,
                build_correlation(),
            ],
            "combination_correlations": [
                [],
                True,
                build_combination(),
            ],
        }
    )

    assert result["anomalies_observed"] == 1
    assert result["combinations_observed"] == 1


@pytest.mark.parametrize(
    "value",
    [
        None,
        "invalid",
        object(),
        True,
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_invalid_average_pnl_becomes_none(value):
    correlation = build_correlation(
        average_realized_pnl=value,
    )

    result = build_engine().analyze(
        build_source(
            anomaly_correlations=[
                correlation,
            ],
        )
    )

    assert (
        result["anomaly_reliability"][0][
            "average_realized_pnl"
        ]
        is None
    )


@pytest.mark.parametrize(
    "field",
    [
        "anomaly_sessions",
        "linked_closed_trades",
        "wins",
        "losses",
        "flat",
    ],
)
def test_invalid_integer_fields_are_normalized(field):
    correlation = build_correlation()
    correlation[field] = "invalid"

    result = build_engine().analyze(
        build_source(
            anomaly_correlations=[
                correlation,
            ],
        )
    )

    assert (
        result["anomaly_reliability"][0][field]
        == 0
    )


@pytest.mark.parametrize(
    "field",
    [
        "anomaly_sessions",
        "linked_closed_trades",
        "wins",
        "losses",
        "flat",
    ],
)
def test_negative_integer_fields_are_clamped(field):
    correlation = build_correlation()
    correlation[field] = -100

    result = build_engine().analyze(
        build_source(
            anomaly_correlations=[
                correlation,
            ],
        )
    )

    assert (
        result["anomaly_reliability"][0][field]
        == 0
    )


def test_tuple_correlation_collections_are_supported():
    result = build_engine().analyze(
        {
            "anomaly_correlations": (
                build_correlation(),
            ),
            "combination_correlations": (
                build_combination(),
            ),
        }
    )

    assert result["anomalies_observed"] == 1
    assert result["combinations_observed"] == 1


def test_tuple_codes_are_supported():
    combination = build_combination(
        codes=(
            "B",
            "A",
            "B",
        ),
    )

    result = build_engine().analyze(
        build_source(
            combination_correlations=[
                combination,
            ],
        )
    )

    assert (
        result["combination_reliability"][0][
            "codes"
        ]
        == ["A", "B"]
    )


def test_strong_evidence_observation_is_added():
    correlation = build_correlation(
        linked_closed_trades=20,
        wins=2,
        losses=18,
        flat=0,
        average_realized_pnl=-100,
    )

    result = build_engine().analyze(
        build_source(
            anomaly_correlations=[
                correlation,
            ],
        )
    )

    assert (
        "At least one anomaly correlation "
        "showed strong repeated outcome "
        "evidence."
        in result["research_observations"]
    )


def test_strongest_negative_observation_is_added():
    correlation = build_correlation(
        code="BAD_SIGNAL",
        linked_closed_trades=20,
        wins=2,
        losses=18,
        flat=0,
        average_realized_pnl=-100,
    )

    result = build_engine().analyze(
        build_source(
            anomaly_correlations=[
                correlation,
            ],
        )
    )

    assert (
        "BAD_SIGNAL showed the strongest repeated "
        "negative outcome evidence."
        in result["research_observations"]
    )


def test_strongest_positive_observation_is_added():
    correlation = build_correlation(
        code="GOOD_SIGNAL",
        linked_closed_trades=20,
        wins=18,
        losses=2,
        flat=0,
        average_realized_pnl=100,
    )

    result = build_engine().analyze(
        build_source(
            anomaly_correlations=[
                correlation,
            ],
        )
    )

    assert (
        "GOOD_SIGNAL showed the strongest repeated "
        "positive outcome evidence."
        in result["research_observations"]
    )


def test_recurring_combination_observation_is_added():
    combination = build_combination(
        anomaly_sessions=2,
    )

    result = build_engine().analyze(
        build_source(
            combination_correlations=[
                combination,
            ],
        )
    )

    assert (
        "At least one recurring multi-anomaly "
        "combination had linked closed-trade "
        "outcome evidence."
        in result["research_observations"]
    )


def test_single_session_combination_does_not_add_recurring_observation():
    combination = build_combination(
        anomaly_sessions=1,
    )

    result = build_engine().analyze(
        build_source(
            combination_correlations=[
                combination,
            ],
        )
    )

    assert (
        "At least one recurring multi-anomaly "
        "combination had linked closed-trade "
        "outcome evidence."
        not in result["research_observations"]
    )


def test_all_weak_records_add_limited_reliability_observation():
    source = build_source(
        anomaly_correlations=[
            build_correlation(
                code="A",
                linked_closed_trades=2,
                wins=0,
                losses=2,
                flat=0,
                average_realized_pnl=-100,
            ),
            build_correlation(
                code="B",
                linked_closed_trades=3,
                wins=3,
                losses=0,
                flat=0,
                average_realized_pnl=100,
            ),
        ],
    )

    result = build_engine().analyze(source)

    assert (
        "Observed anomaly correlations remain "
        "too limited or inconsistent for "
        "strong research reliability."
        in result["research_observations"]
    )


def test_mixed_reliability_does_not_claim_all_are_weak():
    source = build_source(
        anomaly_correlations=[
            build_correlation(
                code="A",
                linked_closed_trades=2,
                wins=0,
                losses=2,
                flat=0,
                average_realized_pnl=-100,
            ),
            build_correlation(
                code="B",
                linked_closed_trades=20,
                wins=18,
                losses=2,
                flat=0,
                average_realized_pnl=100,
            ),
        ],
    )

    result = build_engine().analyze(source)

    assert (
        "Observed anomaly correlations remain "
        "too limited or inconsistent for "
        "strong research reliability."
        not in result["research_observations"]
    )


def test_neutral_only_result_has_noncausation_observation():
    correlation = build_correlation(
        linked_closed_trades=10,
        wins=5,
        losses=5,
        flat=0,
        average_realized_pnl=0,
    )

    result = build_engine().analyze(
        build_source(
            anomaly_correlations=[
                correlation,
            ],
        )
    )

    assert result["research_observations"] == [
        (
            "Anomaly outcome reliability was "
            "measured without establishing "
            "causation."
        )
    ]


def test_output_contains_no_execution_authority_fields():
    result = build_engine().analyze(
        build_source(
            anomaly_correlations=[
                build_correlation(),
            ],
        )
    )

    forbidden = {
        "execute",
        "place_order",
        "order",
        "broker",
        "quantity",
        "capital",
        "position_size",
        "stop_loss",
        "target",
        "confidence_adjustment",
        "risk_adjustment",
        "strategy_adjustment",
    }

    assert forbidden.isdisjoint(result)


def test_reliability_record_contains_no_execution_authority_fields():
    result = build_engine().analyze(
        build_source(
            anomaly_correlations=[
                build_correlation(),
            ],
        )
    )

    record = result[
        "anomaly_reliability"
    ][0]

    forbidden = {
        "execute",
        "place_order",
        "order",
        "broker",
        "quantity",
        "capital",
        "position_size",
        "stop_loss",
        "target",
        "confidence_adjustment",
        "risk_adjustment",
        "strategy_adjustment",
    }

    assert forbidden.isdisjoint(record)