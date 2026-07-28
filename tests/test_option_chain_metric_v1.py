"""Tests for the canonical OptionChainMetricV1 contract."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, is_dataclass
from math import inf, nan

import pytest

from services.contracts.option_chain_metric_v1 import (
    OptionChainMetricV1,
)


def make_metric(**overrides) -> OptionChainMetricV1:
    values = {
        "metric_name": "PCR_OPEN_INTEREST",
        "value": 1.2,
        "signal": "BULLISH",
        "status": "VALID",
        "sample_size": 20,
        "parameters": (),
        "supporting_strikes": (),
        "blockers": (),
        "warnings": (),
    }
    values.update(overrides)
    return OptionChainMetricV1(**values)


def test_contract_is_dataclass() -> None:
    assert is_dataclass(OptionChainMetricV1)


def test_contract_is_frozen() -> None:
    metric = make_metric()

    with pytest.raises(FrozenInstanceError):
        metric.value = 2.0  # type: ignore[misc]


def test_contract_uses_slots() -> None:
    metric = make_metric()

    assert not hasattr(metric, "__dict__")


def test_schema_version() -> None:
    assert make_metric().schema_version == "option_chain_metric.v1"


def test_execution_mode() -> None:
    assert make_metric().execution_mode == "PAPER"


def test_live_execution_is_disabled() -> None:
    assert make_metric().live_execution_eligible is False


def test_expected_dataclass_fields() -> None:
    assert tuple(field.name for field in fields(OptionChainMetricV1)) == (
        "metric_name",
        "value",
        "signal",
        "status",
        "sample_size",
        "parameters",
        "supporting_strikes",
        "blockers",
        "warnings",
    )


def test_valid_metric_creation() -> None:
    metric = make_metric()

    assert metric.metric_name == "PCR_OPEN_INTEREST"
    assert metric.value == 1.2
    assert metric.signal == "BULLISH"
    assert metric.status == "VALID"
    assert metric.sample_size == 20


@pytest.mark.parametrize(
    ("raw_name", "expected"),
    (
        ("PCR_OPEN_INTEREST", "PCR_OPEN_INTEREST"),
        (" PCR_OPEN_INTEREST ", "PCR_OPEN_INTEREST"),
        ("pcr_open_interest", "pcr_open_interest"),
        ("IV_SKEW", "IV_SKEW"),
        ("MAX_PAIN", "MAX_PAIN"),
    ),
)
def test_metric_name_normalization(
    raw_name: str,
    expected: str,
) -> None:
    metric = make_metric(metric_name=raw_name)

    assert metric.metric_name == expected


@pytest.mark.parametrize(
    "invalid_name",
    (
        "",
        " ",
        "\t",
        "\n",
    ),
)
def test_empty_metric_name_rejected(invalid_name: str) -> None:
    with pytest.raises(ValueError):
        make_metric(metric_name=invalid_name)


@pytest.mark.parametrize(
    "invalid_name",
    (
        None,
        1,
        1.2,
        True,
        (),
        [],
        {},
    ),
)
def test_non_string_metric_name_rejected(invalid_name) -> None:
    with pytest.raises(TypeError):
        make_metric(metric_name=invalid_name)


@pytest.mark.parametrize(
    "signal",
    (
        "BULLISH",
        "BEARISH",
        "NEUTRAL",
        "HIGH",
        "LOW",
        "RISING",
        "FALLING",
        "BALANCED",
        "CONCENTRATED",
        "DISPERSED",
        "NONE",
    ),
)
def test_allowed_valid_signals(signal: str) -> None:
    metric = make_metric(signal=signal)

    assert metric.signal == signal


@pytest.mark.parametrize(
    ("raw_signal", "expected"),
    (
        ("bullish", "BULLISH"),
        (" bearish ", "BEARISH"),
        ("neutral", "NEUTRAL"),
        ("concentrated", "CONCENTRATED"),
    ),
)
def test_signal_is_uppercased(
    raw_signal: str,
    expected: str,
) -> None:
    metric = make_metric(signal=raw_signal)

    assert metric.signal == expected


@pytest.mark.parametrize(
    "invalid_signal",
    (
        "",
        "UNKNOWN",
        "BUY",
        "SELL",
        "CALL",
        "PUT",
        "WAIT",
    ),
)
def test_unsupported_signal_rejected(invalid_signal: str) -> None:
    with pytest.raises(ValueError):
        make_metric(signal=invalid_signal)


@pytest.mark.parametrize(
    "invalid_signal",
    (
        None,
        1,
        True,
        (),
        [],
        {},
    ),
)
def test_non_string_signal_rejected(invalid_signal) -> None:
    with pytest.raises(TypeError):
        make_metric(signal=invalid_signal)


@pytest.mark.parametrize(
    ("raw_status", "expected"),
    (
        ("VALID", "VALID"),
        ("valid", "VALID"),
        (" VALID_WITH_WARNINGS ", "VALID_WITH_WARNINGS"),
    ),
)
def test_valid_status_normalization(
    raw_status: str,
    expected: str,
) -> None:
    warnings = (
        ("test warning",)
        if expected == "VALID_WITH_WARNINGS"
        else ()
    )

    metric = make_metric(
        status=raw_status,
        warnings=warnings,
    )

    assert metric.status == expected


@pytest.mark.parametrize(
    "invalid_status",
    (
        "",
        "READY",
        "BLOCKED",
        "STALE",
        "BUY",
        "UNKNOWN",
    ),
)
def test_unsupported_status_rejected(invalid_status: str) -> None:
    with pytest.raises(ValueError):
        make_metric(status=invalid_status)


@pytest.mark.parametrize(
    "invalid_status",
    (
        None,
        1,
        True,
        (),
        [],
        {},
    ),
)
def test_non_string_status_rejected(invalid_status) -> None:
    with pytest.raises(TypeError):
        make_metric(status=invalid_status)


@pytest.mark.parametrize(
    "value",
    (
        0,
        1,
        -1,
        0.0,
        1.5,
        -2.5,
    ),
)
def test_finite_numeric_values_accepted(value) -> None:
    metric = make_metric(value=value)

    assert metric.value == float(value)


@pytest.mark.parametrize(
    "invalid_value",
    (
        nan,
        inf,
        -inf,
    ),
)
def test_non_finite_values_rejected(invalid_value: float) -> None:
    with pytest.raises(ValueError):
        make_metric(value=invalid_value)


@pytest.mark.parametrize(
    "invalid_value",
    (
        True,
        False,
        "1.2",
        (),
        [],
        {},
    ),
)
def test_non_numeric_values_rejected(invalid_value) -> None:
    with pytest.raises(TypeError):
        make_metric(value=invalid_value)


@pytest.mark.parametrize(
    "sample_size",
    (
        0,
        1,
        10,
        1000,
    ),
)
def test_non_negative_sample_sizes_accepted(sample_size: int) -> None:
    metric = make_metric(sample_size=sample_size)

    assert metric.sample_size == sample_size


@pytest.mark.parametrize(
    "invalid_sample_size",
    (
        -1,
        -10,
    ),
)
def test_negative_sample_size_rejected(
    invalid_sample_size: int,
) -> None:
    with pytest.raises(ValueError):
        make_metric(sample_size=invalid_sample_size)


@pytest.mark.parametrize(
    "invalid_sample_size",
    (
        True,
        False,
        1.2,
        "1",
        None,
        (),
    ),
)
def test_non_integer_sample_size_rejected(invalid_sample_size) -> None:
    with pytest.raises(TypeError):
        make_metric(sample_size=invalid_sample_size)


def test_parameters_are_preserved() -> None:
    metric = make_metric(
        parameters=(
            ("period", 14),
            ("threshold", 1.1),
            ("method", "TOTAL_OI"),
        )
    )

    assert metric.parameters == (
        ("period", 14),
        ("threshold", 1.1),
        ("method", "TOTAL_OI"),
    )


@pytest.mark.parametrize(
    "parameter_value",
    (
        1,
        -1,
        0,
        1.5,
        -2.5,
        "TOTAL_OI",
    ),
)
def test_supported_parameter_values(parameter_value) -> None:
    metric = make_metric(
        parameters=(("parameter", parameter_value),)
    )

    assert metric.parameters[0][1] == parameter_value


@pytest.mark.parametrize(
    "invalid_parameters",
    (
        [],
        {},
        "parameter",
        None,
    ),
)
def test_parameters_must_be_tuple(invalid_parameters) -> None:
    with pytest.raises(TypeError):
        make_metric(parameters=invalid_parameters)


@pytest.mark.parametrize(
    "invalid_item",
    (
        ("only-key",),
        ("a", 1, 2),
        ["a", 1],
        "a",
        1,
    ),
)
def test_parameter_items_must_be_two_item_tuples(
    invalid_item,
) -> None:
    with pytest.raises(TypeError):
        make_metric(parameters=(invalid_item,))


@pytest.mark.parametrize(
    "invalid_key",
    (
        "",
        " ",
        None,
        1,
        True,
    ),
)
def test_invalid_parameter_key_rejected(invalid_key) -> None:
    expected_error = (
        ValueError
        if isinstance(invalid_key, str)
        else TypeError
    )

    with pytest.raises(expected_error):
        make_metric(parameters=((invalid_key, 1),))


def test_duplicate_parameter_keys_rejected() -> None:
    with pytest.raises(ValueError):
        make_metric(
            parameters=(
                ("period", 14),
                ("period", 20),
            )
        )


@pytest.mark.parametrize(
    "invalid_parameter_value",
    (
        True,
        False,
        None,
        (),
        [],
        {},
        object(),
    ),
)
def test_invalid_parameter_values_rejected(
    invalid_parameter_value,
) -> None:
    with pytest.raises(TypeError):
        make_metric(
            parameters=(("parameter", invalid_parameter_value),)
        )


@pytest.mark.parametrize(
    "invalid_parameter_value",
    (
        nan,
        inf,
        -inf,
    ),
)
def test_non_finite_parameter_values_rejected(
    invalid_parameter_value: float,
) -> None:
    with pytest.raises(ValueError):
        make_metric(
            parameters=(("parameter", invalid_parameter_value),)
        )


@pytest.mark.parametrize(
    "invalid_parameter_value",
    (
        "",
        " ",
        "\t",
    ),
)
def test_empty_string_parameter_values_rejected(
    invalid_parameter_value: str,
) -> None:
    with pytest.raises(ValueError):
        make_metric(
            parameters=(("parameter", invalid_parameter_value),)
        )


def test_supporting_strikes_are_converted_to_float() -> None:
    metric = make_metric(
        supporting_strikes=(21900, 22000.0, 22100)
    )

    assert metric.supporting_strikes == (
        21900.0,
        22000.0,
        22100.0,
    )


@pytest.mark.parametrize(
    "invalid_strikes",
    (
        [],
        {},
        "22000",
        None,
    ),
)
def test_supporting_strikes_must_be_tuple(
    invalid_strikes,
) -> None:
    with pytest.raises(TypeError):
        make_metric(supporting_strikes=invalid_strikes)


@pytest.mark.parametrize(
    "invalid_strike",
    (
        True,
        False,
        "22000",
        None,
        (),
        [],
    ),
)
def test_non_numeric_supporting_strike_rejected(
    invalid_strike,
) -> None:
    with pytest.raises(TypeError):
        make_metric(supporting_strikes=(invalid_strike,))


@pytest.mark.parametrize(
    "invalid_strike",
    (
        nan,
        inf,
        -inf,
    ),
)
def test_non_finite_supporting_strike_rejected(
    invalid_strike: float,
) -> None:
    with pytest.raises(ValueError):
        make_metric(supporting_strikes=(invalid_strike,))


@pytest.mark.parametrize(
    "invalid_strike",
    (
        0,
        0.0,
        -1,
        -22000.0,
    ),
)
def test_non_positive_supporting_strike_rejected(
    invalid_strike,
) -> None:
    with pytest.raises(ValueError):
        make_metric(supporting_strikes=(invalid_strike,))


def test_duplicate_supporting_strikes_rejected() -> None:
    with pytest.raises(ValueError):
        make_metric(
            supporting_strikes=(22000.0, 22000.0)
        )


def test_unsorted_supporting_strikes_rejected() -> None:
    with pytest.raises(ValueError):
        make_metric(
            supporting_strikes=(22100.0, 22000.0)
        )


@pytest.mark.parametrize(
    "field_name",
    (
        "blockers",
        "warnings",
    ),
)
def test_message_fields_must_be_tuples(field_name: str) -> None:
    with pytest.raises(TypeError):
        make_metric(**{field_name: ["message"]})


@pytest.mark.parametrize(
    "field_name",
    (
        "blockers",
        "warnings",
    ),
)
@pytest.mark.parametrize(
    "invalid_message",
    (
        "",
        " ",
        "\t",
    ),
)
def test_empty_messages_rejected(
    field_name: str,
    invalid_message: str,
) -> None:
    with pytest.raises(ValueError):
        make_metric(**{field_name: (invalid_message,)})


@pytest.mark.parametrize(
    "field_name",
    (
        "blockers",
        "warnings",
    ),
)
@pytest.mark.parametrize(
    "invalid_message",
    (
        None,
        1,
        True,
        (),
    ),
)
def test_non_string_messages_rejected(
    field_name: str,
    invalid_message,
) -> None:
    with pytest.raises(TypeError):
        make_metric(**{field_name: (invalid_message,)})


@pytest.mark.parametrize(
    "field_name",
    (
        "blockers",
        "warnings",
    ),
)
def test_duplicate_messages_rejected(field_name: str) -> None:
    with pytest.raises(ValueError):
        make_metric(
            **{
                field_name: (
                    "duplicate",
                    "duplicate",
                )
            }
        )


def test_valid_status_rejects_blockers() -> None:
    with pytest.raises(ValueError):
        make_metric(blockers=("blocked",))


def test_valid_status_rejects_warnings() -> None:
    with pytest.raises(ValueError):
        make_metric(warnings=("warning",))


def test_valid_status_requires_value() -> None:
    with pytest.raises(ValueError):
        make_metric(value=None)


def test_valid_status_rejects_unavailable_signal() -> None:
    with pytest.raises(ValueError):
        make_metric(signal="UNAVAILABLE")


def test_valid_with_warnings_creation() -> None:
    metric = make_metric(
        status="VALID_WITH_WARNINGS",
        warnings=("extreme reading",),
    )

    assert metric.status == "VALID_WITH_WARNINGS"
    assert metric.warnings == ("extreme reading",)


def test_valid_with_warnings_requires_warning() -> None:
    with pytest.raises(ValueError):
        make_metric(status="VALID_WITH_WARNINGS")


def test_valid_with_warnings_rejects_blockers() -> None:
    with pytest.raises(ValueError):
        make_metric(
            status="VALID_WITH_WARNINGS",
            blockers=("blocked",),
            warnings=("warning",),
        )


def test_valid_with_warnings_requires_value() -> None:
    with pytest.raises(ValueError):
        make_metric(
            status="VALID_WITH_WARNINGS",
            value=None,
            warnings=("warning",),
        )


def test_valid_with_warnings_rejects_unavailable_signal() -> None:
    with pytest.raises(ValueError):
        make_metric(
            status="VALID_WITH_WARNINGS",
            signal="UNAVAILABLE",
            warnings=("warning",),
        )


@pytest.mark.parametrize(
    "status",
    (
        "INSUFFICIENT_DATA",
        "UNAVAILABLE",
        "MALFORMED",
        "FAILED",
    ),
)
def test_blocking_status_creation(status: str) -> None:
    metric = make_metric(
        value=None,
        signal="UNAVAILABLE",
        status=status,
        blockers=("metric unavailable",),
    )

    assert metric.status == status
    assert metric.value is None
    assert metric.signal == "UNAVAILABLE"


@pytest.mark.parametrize(
    "status",
    (
        "INSUFFICIENT_DATA",
        "UNAVAILABLE",
        "MALFORMED",
        "FAILED",
    ),
)
def test_blocking_status_requires_blocker(status: str) -> None:
    with pytest.raises(ValueError):
        make_metric(
            value=None,
            signal="UNAVAILABLE",
            status=status,
            blockers=(),
        )


@pytest.mark.parametrize(
    "status",
    (
        "INSUFFICIENT_DATA",
        "UNAVAILABLE",
        "MALFORMED",
        "FAILED",
    ),
)
def test_blocking_status_rejects_numeric_value(status: str) -> None:
    with pytest.raises(ValueError):
        make_metric(
            value=1.0,
            signal="UNAVAILABLE",
            status=status,
            blockers=("blocked",),
        )


@pytest.mark.parametrize(
    "status",
    (
        "INSUFFICIENT_DATA",
        "UNAVAILABLE",
        "MALFORMED",
        "FAILED",
    ),
)
@pytest.mark.parametrize(
    "signal",
    (
        "BULLISH",
        "BEARISH",
        "NEUTRAL",
        "NONE",
    ),
)
def test_blocking_status_requires_unavailable_signal(
    status: str,
    signal: str,
) -> None:
    with pytest.raises(ValueError):
        make_metric(
            value=None,
            signal=signal,
            status=status,
            blockers=("blocked",),
        )


def test_deterministic_to_dict() -> None:
    metric = make_metric(
        parameters=(
            ("period", 14),
            ("method", "TOTAL_OI"),
        ),
        supporting_strikes=(
            21900.0,
            22000.0,
        ),
    )

    assert metric.to_dict() == {
        "schema_version": "option_chain_metric.v1",
        "metric_name": "PCR_OPEN_INTEREST",
        "value": 1.2,
        "signal": "BULLISH",
        "status": "VALID",
        "sample_size": 20,
        "parameters": [
            ["period", 14],
            ["method", "TOTAL_OI"],
        ],
        "supporting_strikes": [
            21900.0,
            22000.0,
        ],
        "blockers": [],
        "warnings": [],
        "execution_mode": "PAPER",
        "live_execution_eligible": False,
    }


def test_to_dict_returns_new_mutable_containers() -> None:
    metric = make_metric(
        parameters=(("period", 14),),
        supporting_strikes=(22000.0,),
    )

    first = metric.to_dict()
    second = metric.to_dict()

    assert first == second
    assert first is not second
    assert first["parameters"] is not second["parameters"]
    assert first["supporting_strikes"] is not second[
        "supporting_strikes"
    ]


def test_serialization_contains_only_primitives() -> None:
    serialized = make_metric(
        parameters=(
            ("integer", 1),
            ("float", 1.5),
            ("string", "value"),
        ),
        supporting_strikes=(22000.0,),
    ).to_dict()

    assert isinstance(serialized, dict)
    assert isinstance(serialized["parameters"], list)
    assert isinstance(serialized["supporting_strikes"], list)
    assert isinstance(serialized["blockers"], list)
    assert isinstance(serialized["warnings"], list)


def test_equality_is_value_based() -> None:
    assert make_metric() == make_metric()


def test_hashability() -> None:
    metrics = {make_metric(), make_metric()}

    assert len(metrics) == 1