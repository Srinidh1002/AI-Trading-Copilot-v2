"""Tests for OptionChainIntelligencePolicyV1."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, is_dataclass
from math import inf, nan

import pytest

from services.contracts.option_chain_intelligence_policy_v1 import (
    DEFAULT_OPTION_CHAIN_INTELLIGENCE_POLICY,
    OptionChainIntelligencePolicyV1,
)


CANONICAL_WEIGHTS = (
    ("PCR_OPEN_INTEREST", 0.20),
    ("PCR_VOLUME", 0.10),
    ("OI_CONCENTRATION", 0.15),
    ("OI_BUILDUP", 0.20),
    ("MAX_PAIN", 0.10),
    ("IV_SKEW", 0.10),
    ("SUPPORT_RESISTANCE", 0.15),
)


def make_policy(**overrides) -> OptionChainIntelligencePolicyV1:
    values = {
        "policy_name": (
            "INITIAL_CANONICAL_OPTION_CHAIN_INTELLIGENCE_POLICY"
        ),
        "metric_weights": CANONICAL_WEIGHTS,
        "pcr_bullish_threshold": 1.10,
        "pcr_bearish_threshold": 0.90,
        "pcr_extreme_high_threshold": 1.50,
        "pcr_extreme_low_threshold": 0.60,
        "oi_concentration_high_ratio": 0.35,
        "oi_concentration_low_ratio": 0.15,
        "oi_buildup_minimum_absolute_change": 1,
        "max_pain_near_distance_bps": 50.0,
        "max_pain_far_distance_bps": 200.0,
        "iv_skew_material_difference": 2.0,
        "support_resistance_top_n": 3,
        "minimum_valid_metrics": 4,
        "bullish_score_threshold": 0.15,
        "bearish_score_threshold": -0.15,
        "conflicting_score_tolerance": 0.05,
        "insufficient_metrics_behavior": "BLOCK",
        "missing_metric_behavior": "WARN",
        "conflicting_signal_behavior": "WARN",
        "execution_mode": "PAPER",
        "live_execution_eligible": False,
    }
    values.update(overrides)
    return OptionChainIntelligencePolicyV1(**values)


def test_contract_is_dataclass() -> None:
    assert is_dataclass(OptionChainIntelligencePolicyV1)


def test_contract_is_frozen() -> None:
    policy = make_policy()

    with pytest.raises(FrozenInstanceError):
        policy.policy_name = "OTHER"  # type: ignore[misc]


def test_contract_uses_slots() -> None:
    assert not hasattr(make_policy(), "__dict__")


def test_schema_version() -> None:
    assert (
        make_policy().schema_version
        == "option_chain_intelligence_policy.v1"
    )


def test_expected_fields() -> None:
    assert tuple(
        field.name
        for field in fields(OptionChainIntelligencePolicyV1)
    ) == (
        "policy_name",
        "metric_weights",
        "pcr_bullish_threshold",
        "pcr_bearish_threshold",
        "pcr_extreme_high_threshold",
        "pcr_extreme_low_threshold",
        "oi_concentration_high_ratio",
        "oi_concentration_low_ratio",
        "oi_buildup_minimum_absolute_change",
        "max_pain_near_distance_bps",
        "max_pain_far_distance_bps",
        "iv_skew_material_difference",
        "support_resistance_top_n",
        "minimum_valid_metrics",
        "bullish_score_threshold",
        "bearish_score_threshold",
        "conflicting_score_tolerance",
        "insufficient_metrics_behavior",
        "missing_metric_behavior",
        "conflicting_signal_behavior",
        "execution_mode",
        "live_execution_eligible",
    )


def test_default_policy_type() -> None:
    assert isinstance(
        DEFAULT_OPTION_CHAIN_INTELLIGENCE_POLICY,
        OptionChainIntelligencePolicyV1,
    )


def test_default_policy_name() -> None:
    assert (
        DEFAULT_OPTION_CHAIN_INTELLIGENCE_POLICY.policy_name
        == "INITIAL_CANONICAL_OPTION_CHAIN_INTELLIGENCE_POLICY"
    )


def test_default_execution_mode() -> None:
    assert (
        DEFAULT_OPTION_CHAIN_INTELLIGENCE_POLICY.execution_mode
        == "PAPER"
    )


def test_default_live_execution_disabled() -> None:
    assert (
        DEFAULT_OPTION_CHAIN_INTELLIGENCE_POLICY
        .live_execution_eligible
        is False
    )


def test_required_metrics() -> None:
    assert make_policy().required_metrics == (
        "PCR_OPEN_INTEREST",
        "PCR_VOLUME",
        "OI_CONCENTRATION",
        "OI_BUILDUP",
        "MAX_PAIN",
        "IV_SKEW",
        "SUPPORT_RESISTANCE",
    )


def test_default_metric_weights() -> None:
    assert make_policy().metric_weights == CANONICAL_WEIGHTS


def test_metric_weights_sum_to_one() -> None:
    assert sum(
        weight
        for _, weight in make_policy().metric_weights
    ) == pytest.approx(1.0)


@pytest.mark.parametrize(
    ("metric_name", "expected"),
    CANONICAL_WEIGHTS,
)
def test_metric_weight_lookup(
    metric_name: str,
    expected: float,
) -> None:
    assert make_policy().metric_weight(metric_name) == expected


@pytest.mark.parametrize(
    ("metric_name", "expected"),
    (
        ("pcr_open_interest", 0.20),
        (" PCR_VOLUME ", 0.10),
        ("oi_buildup", 0.20),
        ("support_resistance", 0.15),
    ),
)
def test_metric_weight_lookup_normalizes_name(
    metric_name: str,
    expected: float,
) -> None:
    assert make_policy().metric_weight(metric_name) == expected


@pytest.mark.parametrize(
    "metric_name",
    (
        "UNKNOWN",
        "PCR",
        "OPTION_SELECTION",
        "DECISION",
    ),
)
def test_unknown_metric_weight_rejected(metric_name: str) -> None:
    with pytest.raises(KeyError):
        make_policy().metric_weight(metric_name)


@pytest.mark.parametrize(
    "metric_name",
    (
        "",
        " ",
    ),
)
def test_empty_metric_weight_name_rejected(metric_name: str) -> None:
    with pytest.raises(ValueError):
        make_policy().metric_weight(metric_name)


@pytest.mark.parametrize(
    "metric_name",
    (
        None,
        1,
        True,
        (),
    ),
)
def test_non_string_metric_weight_name_rejected(metric_name) -> None:
    with pytest.raises(TypeError):
        make_policy().metric_weight(metric_name)


@pytest.mark.parametrize(
    ("raw_name", "expected"),
    (
        (
            "INITIAL_CANONICAL_OPTION_CHAIN_INTELLIGENCE_POLICY",
            "INITIAL_CANONICAL_OPTION_CHAIN_INTELLIGENCE_POLICY",
        ),
        (" custom-policy ", "custom-policy"),
    ),
)
def test_policy_name_normalization(
    raw_name: str,
    expected: str,
) -> None:
    assert make_policy(policy_name=raw_name).policy_name == expected


@pytest.mark.parametrize(
    "invalid_name",
    (
        "",
        " ",
        "\t",
    ),
)
def test_empty_policy_name_rejected(invalid_name: str) -> None:
    with pytest.raises(ValueError):
        make_policy(policy_name=invalid_name)


@pytest.mark.parametrize(
    "invalid_name",
    (
        None,
        1,
        True,
        (),
        [],
    ),
)
def test_non_string_policy_name_rejected(invalid_name) -> None:
    with pytest.raises(TypeError):
        make_policy(policy_name=invalid_name)


@pytest.mark.parametrize(
    "invalid_weights",
    (
        [],
        {},
        None,
        "weights",
    ),
)
def test_metric_weights_must_be_tuple(invalid_weights) -> None:
    with pytest.raises(TypeError):
        make_policy(metric_weights=invalid_weights)


def test_metric_weights_require_all_metrics() -> None:
    with pytest.raises(ValueError):
        make_policy(
            metric_weights=CANONICAL_WEIGHTS[:-1]
        )


def test_metric_weights_reject_extra_metric() -> None:
    with pytest.raises(ValueError):
        make_policy(
            metric_weights=CANONICAL_WEIGHTS
            + (("EXTRA_METRIC", 0.0),)
        )


def test_metric_weights_reject_duplicate_names() -> None:
    weights = list(CANONICAL_WEIGHTS)
    weights[-1] = ("PCR_OPEN_INTEREST", 0.15)

    with pytest.raises(ValueError):
        make_policy(metric_weights=tuple(weights))


def test_metric_weights_reject_wrong_order() -> None:
    weights = list(CANONICAL_WEIGHTS)
    weights[0], weights[1] = weights[1], weights[0]

    with pytest.raises(ValueError):
        make_policy(metric_weights=tuple(weights))


@pytest.mark.parametrize(
    "invalid_item",
    (
        ("PCR_OPEN_INTEREST",),
        ("PCR_OPEN_INTEREST", 0.2, "extra"),
        ["PCR_OPEN_INTEREST", 0.2],
        "PCR_OPEN_INTEREST",
        1,
    ),
)
def test_metric_weight_items_must_be_two_item_tuples(
    invalid_item,
) -> None:
    weights = list(CANONICAL_WEIGHTS)
    weights[0] = invalid_item

    with pytest.raises(TypeError):
        make_policy(metric_weights=tuple(weights))


@pytest.mark.parametrize(
    "invalid_name",
    (
        "",
        " ",
        None,
        1,
        True,
    ),
)
def test_invalid_metric_weight_name_rejected(invalid_name) -> None:
    weights = list(CANONICAL_WEIGHTS)
    weights[0] = (invalid_name, 0.20)

    expected = (
        ValueError
        if isinstance(invalid_name, str)
        else TypeError
    )

    with pytest.raises(expected):
        make_policy(metric_weights=tuple(weights))


def test_unsupported_metric_weight_name_rejected() -> None:
    weights = list(CANONICAL_WEIGHTS)
    weights[0] = ("UNKNOWN", 0.20)

    with pytest.raises(ValueError):
        make_policy(metric_weights=tuple(weights))


@pytest.mark.parametrize(
    "invalid_weight",
    (
        -0.1,
        1.1,
        nan,
        inf,
        -inf,
    ),
)
def test_invalid_metric_weight_value_rejected(
    invalid_weight: float,
) -> None:
    weights = list(CANONICAL_WEIGHTS)
    weights[0] = ("PCR_OPEN_INTEREST", invalid_weight)

    with pytest.raises(ValueError):
        make_policy(metric_weights=tuple(weights))


@pytest.mark.parametrize(
    "invalid_weight",
    (
        True,
        False,
        None,
        "0.2",
        (),
        [],
    ),
)
def test_non_numeric_metric_weight_rejected(invalid_weight) -> None:
    weights = list(CANONICAL_WEIGHTS)
    weights[0] = ("PCR_OPEN_INTEREST", invalid_weight)

    with pytest.raises(TypeError):
        make_policy(metric_weights=tuple(weights))


def test_metric_weights_must_sum_to_one() -> None:
    weights = list(CANONICAL_WEIGHTS)
    weights[0] = ("PCR_OPEN_INTEREST", 0.19)

    with pytest.raises(ValueError):
        make_policy(metric_weights=tuple(weights))


@pytest.mark.parametrize(
    "field_name",
    (
        "pcr_bullish_threshold",
        "pcr_bearish_threshold",
        "pcr_extreme_high_threshold",
        "pcr_extreme_low_threshold",
    ),
)
@pytest.mark.parametrize(
    "invalid_value",
    (
        0,
        0.0,
        -1,
        -0.1,
    ),
)
def test_pcr_thresholds_must_be_positive(
    field_name: str,
    invalid_value,
) -> None:
    with pytest.raises(ValueError):
        make_policy(**{field_name: invalid_value})


@pytest.mark.parametrize(
    "field_name",
    (
        "pcr_bullish_threshold",
        "pcr_bearish_threshold",
        "pcr_extreme_high_threshold",
        "pcr_extreme_low_threshold",
    ),
)
@pytest.mark.parametrize(
    "invalid_value",
    (
        nan,
        inf,
        -inf,
    ),
)
def test_pcr_thresholds_must_be_finite(
    field_name: str,
    invalid_value: float,
) -> None:
    with pytest.raises(ValueError):
        make_policy(**{field_name: invalid_value})


@pytest.mark.parametrize(
    "field_name",
    (
        "pcr_bullish_threshold",
        "pcr_bearish_threshold",
        "pcr_extreme_high_threshold",
        "pcr_extreme_low_threshold",
    ),
)
@pytest.mark.parametrize(
    "invalid_value",
    (
        True,
        False,
        None,
        "1.0",
        (),
    ),
)
def test_pcr_thresholds_must_be_numeric(
    field_name: str,
    invalid_value,
) -> None:
    with pytest.raises(TypeError):
        make_policy(**{field_name: invalid_value})


@pytest.mark.parametrize(
    "overrides",
    (
        {
            "pcr_extreme_low_threshold": 0.90,
        },
        {
            "pcr_bearish_threshold": 1.10,
        },
        {
            "pcr_bullish_threshold": 1.50,
        },
        {
            "pcr_extreme_high_threshold": 1.10,
        },
        {
            "pcr_extreme_low_threshold": 1.00,
            "pcr_bearish_threshold": 0.90,
        },
    ),
)
def test_pcr_threshold_order_enforced(overrides) -> None:
    with pytest.raises(ValueError):
        make_policy(**overrides)


@pytest.mark.parametrize(
    "field_name",
    (
        "oi_concentration_high_ratio",
        "oi_concentration_low_ratio",
    ),
)
@pytest.mark.parametrize(
    "value",
    (
        0.0,
        0.1,
        0.5,
        1.0,
    ),
)
def test_concentration_ratios_accept_unit_interval(
    field_name: str,
    value: float,
) -> None:
    overrides = {field_name: value}

    if field_name == "oi_concentration_high_ratio":
        overrides["oi_concentration_low_ratio"] = 0.0

        if value == 0.0:
            with pytest.raises(ValueError):
                make_policy(**overrides)
            return

    if field_name == "oi_concentration_low_ratio":
        overrides["oi_concentration_high_ratio"] = 1.0

        if value == 1.0:
            with pytest.raises(ValueError):
                make_policy(**overrides)
            return

    policy = make_policy(**overrides)

    assert getattr(policy, field_name) == value


@pytest.mark.parametrize(
    "field_name",
    (
        "oi_concentration_high_ratio",
        "oi_concentration_low_ratio",
    ),
)
@pytest.mark.parametrize(
    "invalid_value",
    (
        -0.1,
        1.1,
        nan,
        inf,
        -inf,
    ),
)
def test_concentration_ratios_reject_invalid_values(
    field_name: str,
    invalid_value: float,
) -> None:
    with pytest.raises(ValueError):
        make_policy(**{field_name: invalid_value})


def test_concentration_low_must_be_below_high() -> None:
    with pytest.raises(ValueError):
        make_policy(
            oi_concentration_low_ratio=0.35,
            oi_concentration_high_ratio=0.35,
        )


@pytest.mark.parametrize(
    "value",
    (
        0,
        1,
        100,
    ),
)
def test_oi_buildup_minimum_change_accepts_non_negative_int(
    value: int,
) -> None:
    assert (
        make_policy(
            oi_buildup_minimum_absolute_change=value
        ).oi_buildup_minimum_absolute_change
        == value
    )


@pytest.mark.parametrize(
    "invalid_value",
    (
        -1,
        -10,
    ),
)
def test_oi_buildup_minimum_change_rejects_negative(
    invalid_value: int,
) -> None:
    with pytest.raises(ValueError):
        make_policy(
            oi_buildup_minimum_absolute_change=invalid_value
        )


@pytest.mark.parametrize(
    "invalid_value",
    (
        True,
        False,
        1.5,
        "1",
        None,
    ),
)
def test_oi_buildup_minimum_change_requires_int(
    invalid_value,
) -> None:
    with pytest.raises(TypeError):
        make_policy(
            oi_buildup_minimum_absolute_change=invalid_value
        )


@pytest.mark.parametrize(
    "value",
    (
        0.0,
        10.0,
        50.0,
    ),
)
def test_max_pain_near_distance_accepts_non_negative(
    value: float,
) -> None:
    policy = make_policy(
        max_pain_near_distance_bps=value,
        max_pain_far_distance_bps=200.0,
    )

    assert policy.max_pain_near_distance_bps == value


@pytest.mark.parametrize(
    "invalid_value",
    (
        -1,
        -0.1,
    ),
)
def test_max_pain_near_distance_rejects_negative(
    invalid_value,
) -> None:
    with pytest.raises(ValueError):
        make_policy(
            max_pain_near_distance_bps=invalid_value
        )


@pytest.mark.parametrize(
    "value",
    (
        1.0,
        50.0,
        200.0,
    ),
)
def test_max_pain_far_distance_accepts_positive(
    value: float,
) -> None:
    policy = make_policy(
        max_pain_near_distance_bps=0.0,
        max_pain_far_distance_bps=value,
    )

    assert policy.max_pain_far_distance_bps == value


@pytest.mark.parametrize(
    "invalid_value",
    (
        0,
        0.0,
        -1,
    ),
)
def test_max_pain_far_distance_requires_positive(
    invalid_value,
) -> None:
    with pytest.raises(ValueError):
        make_policy(
            max_pain_far_distance_bps=invalid_value
        )


@pytest.mark.parametrize(
    "near_value",
    (
        200.0,
        201.0,
    ),
)
def test_max_pain_near_must_be_below_far(
    near_value: float,
) -> None:
    with pytest.raises(ValueError):
        make_policy(
            max_pain_near_distance_bps=near_value,
            max_pain_far_distance_bps=200.0,
        )


@pytest.mark.parametrize(
    "value",
    (
        0.0,
        1.0,
        2.0,
        10.0,
    ),
)
def test_iv_skew_material_difference_accepts_non_negative(
    value: float,
) -> None:
    assert (
        make_policy(
            iv_skew_material_difference=value
        ).iv_skew_material_difference
        == value
    )


@pytest.mark.parametrize(
    "invalid_value",
    (
        -0.1,
        -1,
    ),
)
def test_iv_skew_material_difference_rejects_negative(
    invalid_value,
) -> None:
    with pytest.raises(ValueError):
        make_policy(
            iv_skew_material_difference=invalid_value
        )


@pytest.mark.parametrize(
    "value",
    (
        1,
        2,
        3,
        10,
    ),
)
def test_support_resistance_top_n_accepts_positive_int(
    value: int,
) -> None:
    assert (
        make_policy(
            support_resistance_top_n=value
        ).support_resistance_top_n
        == value
    )


@pytest.mark.parametrize(
    "invalid_value",
    (
        0,
        -1,
    ),
)
def test_support_resistance_top_n_rejects_non_positive(
    invalid_value: int,
) -> None:
    with pytest.raises(ValueError):
        make_policy(
            support_resistance_top_n=invalid_value
        )


@pytest.mark.parametrize(
    "invalid_value",
    (
        True,
        False,
        1.5,
        "3",
        None,
    ),
)
def test_support_resistance_top_n_requires_int(
    invalid_value,
) -> None:
    with pytest.raises(TypeError):
        make_policy(
            support_resistance_top_n=invalid_value
        )


@pytest.mark.parametrize(
    "value",
    (
        1,
        4,
        7,
    ),
)
def test_minimum_valid_metrics_accepts_valid_range(
    value: int,
) -> None:
    assert (
        make_policy(
            minimum_valid_metrics=value
        ).minimum_valid_metrics
        == value
    )


@pytest.mark.parametrize(
    "invalid_value",
    (
        0,
        -1,
    ),
)
def test_minimum_valid_metrics_rejects_non_positive(
    invalid_value: int,
) -> None:
    with pytest.raises(ValueError):
        make_policy(
            minimum_valid_metrics=invalid_value
        )


def test_minimum_valid_metrics_cannot_exceed_required_count() -> None:
    with pytest.raises(ValueError):
        make_policy(minimum_valid_metrics=8)


@pytest.mark.parametrize(
    "invalid_value",
    (
        True,
        False,
        1.5,
        "4",
        None,
    ),
)
def test_minimum_valid_metrics_requires_int(
    invalid_value,
) -> None:
    with pytest.raises(TypeError):
        make_policy(
            minimum_valid_metrics=invalid_value
        )


@pytest.mark.parametrize(
    "value",
    (
        0.01,
        0.15,
        0.5,
        1.0,
    ),
)
def test_bullish_score_threshold_accepts_positive_unit_interval(
    value: float,
) -> None:
    policy = make_policy(
        bullish_score_threshold=value,
        conflicting_score_tolerance=min(0.01, value),
    )

    assert policy.bullish_score_threshold == value


@pytest.mark.parametrize(
    "invalid_value",
    (
        0.0,
        -0.1,
        1.1,
    ),
)
def test_bullish_score_threshold_rejects_invalid(
    invalid_value: float,
) -> None:
    with pytest.raises(ValueError):
        make_policy(
            bullish_score_threshold=invalid_value
        )


@pytest.mark.parametrize(
    "value",
    (
        -1.0,
        -0.5,
        -0.15,
        0.0,
    ),
)
def test_bearish_score_threshold_accepts_range(
    value: float,
) -> None:
    tolerance = min(0.01, abs(value))

    policy = make_policy(
        bearish_score_threshold=value,
        conflicting_score_tolerance=tolerance,
    )

    assert policy.bearish_score_threshold == value


@pytest.mark.parametrize(
    "invalid_value",
    (
        -1.1,
        0.1,
        1.0,
    ),
)
def test_bearish_score_threshold_rejects_invalid(
    invalid_value: float,
) -> None:
    with pytest.raises(ValueError):
        make_policy(
            bearish_score_threshold=invalid_value
        )


@pytest.mark.parametrize(
    "value",
    (
        0.0,
        0.01,
        0.05,
        0.15,
    ),
)
def test_conflict_tolerance_accepts_valid_range(
    value: float,
) -> None:
    policy = make_policy(
        conflicting_score_tolerance=value,
    )

    assert policy.conflicting_score_tolerance == value


@pytest.mark.parametrize(
    "invalid_value",
    (
        -0.1,
        1.1,
    ),
)
def test_conflict_tolerance_rejects_outside_unit_interval(
    invalid_value: float,
) -> None:
    with pytest.raises(ValueError):
        make_policy(
            conflicting_score_tolerance=invalid_value
        )


def test_conflict_tolerance_cannot_exceed_bullish_threshold() -> None:
    with pytest.raises(ValueError):
        make_policy(
            bullish_score_threshold=0.10,
            conflicting_score_tolerance=0.11,
        )


def test_conflict_tolerance_cannot_exceed_bearish_magnitude() -> None:
    with pytest.raises(ValueError):
        make_policy(
            bearish_score_threshold=-0.10,
            conflicting_score_tolerance=0.11,
        )


@pytest.mark.parametrize(
    "field_name",
    (
        "insufficient_metrics_behavior",
        "missing_metric_behavior",
        "conflicting_signal_behavior",
    ),
)
@pytest.mark.parametrize(
    ("raw_behavior", "expected"),
    (
        ("BLOCK", "BLOCK"),
        ("warn", "WARN"),
        (" allow ", "ALLOW"),
    ),
)
def test_behavior_normalization(
    field_name: str,
    raw_behavior: str,
    expected: str,
) -> None:
    policy = make_policy(
        **{field_name: raw_behavior}
    )

    assert getattr(policy, field_name) == expected


@pytest.mark.parametrize(
    "field_name",
    (
        "insufficient_metrics_behavior",
        "missing_metric_behavior",
        "conflicting_signal_behavior",
    ),
)
@pytest.mark.parametrize(
    "invalid_behavior",
    (
        "",
        "UNKNOWN",
        "FAIL",
        "IGNORE",
    ),
)
def test_invalid_behavior_rejected(
    field_name: str,
    invalid_behavior: str,
) -> None:
    with pytest.raises(ValueError):
        make_policy(
            **{field_name: invalid_behavior}
        )


@pytest.mark.parametrize(
    "field_name",
    (
        "insufficient_metrics_behavior",
        "missing_metric_behavior",
        "conflicting_signal_behavior",
    ),
)
@pytest.mark.parametrize(
    "invalid_behavior",
    (
        None,
        1,
        True,
        (),
    ),
)
def test_non_string_behavior_rejected(
    field_name: str,
    invalid_behavior,
) -> None:
    with pytest.raises(TypeError):
        make_policy(
            **{field_name: invalid_behavior}
        )


@pytest.mark.parametrize(
    "invalid_execution_mode",
    (
        "LIVE",
        "live",
        "",
        "PAPER ",
    ),
)
def test_execution_mode_must_remain_paper(
    invalid_execution_mode: str,
) -> None:
    with pytest.raises(ValueError):
        make_policy(
            execution_mode=invalid_execution_mode
        )


@pytest.mark.parametrize(
    "invalid_value",
    (
        True,
        1,
        "False",
        None,
    ),
)
def test_live_execution_eligible_must_remain_false(
    invalid_value,
) -> None:
    with pytest.raises(ValueError):
        make_policy(
            live_execution_eligible=invalid_value
        )


def test_to_dict_contains_expected_values() -> None:
    serialized = make_policy().to_dict()

    assert serialized == {
        "schema_version": (
            "option_chain_intelligence_policy.v1"
        ),
        "policy_name": (
            "INITIAL_CANONICAL_OPTION_CHAIN_INTELLIGENCE_POLICY"
        ),
        "required_metrics": [
            "PCR_OPEN_INTEREST",
            "PCR_VOLUME",
            "OI_CONCENTRATION",
            "OI_BUILDUP",
            "MAX_PAIN",
            "IV_SKEW",
            "SUPPORT_RESISTANCE",
        ],
        "metric_weights": [
            ["PCR_OPEN_INTEREST", 0.20],
            ["PCR_VOLUME", 0.10],
            ["OI_CONCENTRATION", 0.15],
            ["OI_BUILDUP", 0.20],
            ["MAX_PAIN", 0.10],
            ["IV_SKEW", 0.10],
            ["SUPPORT_RESISTANCE", 0.15],
        ],
        "pcr_bullish_threshold": 1.10,
        "pcr_bearish_threshold": 0.90,
        "pcr_extreme_high_threshold": 1.50,
        "pcr_extreme_low_threshold": 0.60,
        "oi_concentration_high_ratio": 0.35,
        "oi_concentration_low_ratio": 0.15,
        "oi_buildup_minimum_absolute_change": 1,
        "max_pain_near_distance_bps": 50.0,
        "max_pain_far_distance_bps": 200.0,
        "iv_skew_material_difference": 2.0,
        "support_resistance_top_n": 3,
        "minimum_valid_metrics": 4,
        "bullish_score_threshold": 0.15,
        "bearish_score_threshold": -0.15,
        "conflicting_score_tolerance": 0.05,
        "insufficient_metrics_behavior": "BLOCK",
        "missing_metric_behavior": "WARN",
        "conflicting_signal_behavior": "WARN",
        "execution_mode": "PAPER",
        "live_execution_eligible": False,
    }


def test_to_dict_returns_new_containers() -> None:
    policy = make_policy()

    first = policy.to_dict()
    second = policy.to_dict()

    assert first == second
    assert first is not second
    assert first["required_metrics"] is not second[
        "required_metrics"
    ]
    assert first["metric_weights"] is not second[
        "metric_weights"
    ]


def test_equality_is_value_based() -> None:
    assert make_policy() == make_policy()


def test_policy_is_hashable() -> None:
    policies = {
        make_policy(),
        make_policy(),
    }

    assert len(policies) == 1