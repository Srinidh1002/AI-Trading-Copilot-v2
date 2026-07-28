"""Tests for OptionChainIntelligenceResultV1."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, is_dataclass
from datetime import date, datetime, timezone
from math import inf, nan

import pytest

from services.contracts.option_chain_intelligence_result_v1 import (
    OptionChainIntelligenceResultV1,
)
from services.contracts.option_chain_metric_v1 import (
    OptionChainMetricV1,
)


CREATED_AT = datetime(
    2026,
    1,
    1,
    10,
    0,
    tzinfo=timezone.utc,
)
EXPIRY = date(2026, 1, 29)


def valid_metric(
    metric_name: str = "PCR_OPEN_INTEREST",
    *,
    signal: str = "BULLISH",
    value: float = 1.2,
) -> OptionChainMetricV1:
    return OptionChainMetricV1(
        metric_name=metric_name,
        value=value,
        signal=signal,
        status="VALID",
        sample_size=10,
    )


def unavailable_metric(
    metric_name: str = "IV_SKEW",
) -> OptionChainMetricV1:
    return OptionChainMetricV1(
        metric_name=metric_name,
        value=None,
        signal="UNAVAILABLE",
        status="UNAVAILABLE",
        sample_size=0,
        blockers=("metric unavailable",),
    )


def make_result(**overrides) -> OptionChainIntelligenceResultV1:
    metric = valid_metric()

    values = {
        "option_chain_intelligence_result_id": "result-1",
        "created_at": CREATED_AT,
        "option_chain_snapshot_id": "snapshot-1",
        "option_chain_quality_result_id": "quality-1",
        "underlying_symbol": "NIFTY",
        "exchange": "NSE",
        "expiry": EXPIRY,
        "metrics": (metric,),
        "intelligence_status": "READY",
        "aggregate_bias": "BULLISH",
        "aggregate_strength": 0.20,
        "bullish_metrics": ("PCR_OPEN_INTEREST",),
        "bearish_metrics": (),
        "neutral_metrics": (),
        "unavailable_metrics": (),
        "valid_metric_count": 1,
        "unavailable_metric_count": 0,
        "support_strikes": (),
        "resistance_strikes": (),
        "max_pain_strike": None,
        "blockers": (),
        "warnings": (),
        "execution_mode": "PAPER",
        "live_execution_eligible": False,
    }
    values.update(overrides)

    return OptionChainIntelligenceResultV1(**values)


def test_contract_is_dataclass() -> None:
    assert is_dataclass(OptionChainIntelligenceResultV1)


def test_contract_is_frozen() -> None:
    result = make_result()

    with pytest.raises(FrozenInstanceError):
        result.aggregate_strength = 0.5  # type: ignore[misc]


def test_contract_uses_slots() -> None:
    assert not hasattr(make_result(), "__dict__")


def test_schema_version() -> None:
    assert (
        make_result().schema_version
        == "option_chain_intelligence_result.v1"
    )


def test_execution_mode() -> None:
    assert make_result().execution_mode == "PAPER"


def test_live_execution_disabled() -> None:
    assert make_result().live_execution_eligible is False


def test_expected_fields() -> None:
    assert tuple(
        field.name
        for field in fields(OptionChainIntelligenceResultV1)
    ) == (
        "option_chain_intelligence_result_id",
        "created_at",
        "option_chain_snapshot_id",
        "option_chain_quality_result_id",
        "underlying_symbol",
        "exchange",
        "expiry",
        "metrics",
        "intelligence_status",
        "aggregate_bias",
        "aggregate_strength",
        "bullish_metrics",
        "bearish_metrics",
        "neutral_metrics",
        "unavailable_metrics",
        "valid_metric_count",
        "unavailable_metric_count",
        "support_strikes",
        "resistance_strikes",
        "max_pain_strike",
        "blockers",
        "warnings",
        "execution_mode",
        "live_execution_eligible",
    )


def test_valid_result_creation() -> None:
    result = make_result()

    assert result.option_chain_intelligence_result_id == "result-1"
    assert result.created_at == CREATED_AT
    assert result.option_chain_snapshot_id == "snapshot-1"
    assert result.option_chain_quality_result_id == "quality-1"
    assert result.underlying_symbol == "NIFTY"
    assert result.exchange == "NSE"
    assert result.expiry == EXPIRY


@pytest.mark.parametrize(
    ("symbol", "exchange"),
    (
        ("NIFTY", "NSE"),
        ("BANKNIFTY", "NSE"),
        ("FINNIFTY", "NSE"),
        ("SENSEX", "BSE"),
    ),
)
def test_four_canonical_markets_supported(
    symbol: str,
    exchange: str,
) -> None:
    result = make_result(
        underlying_symbol=symbol,
        exchange=exchange,
    )

    assert result.underlying_symbol == symbol
    assert result.exchange == exchange


@pytest.mark.parametrize(
    ("symbol", "exchange"),
    (
        ("nifty", "nse"),
        (" banknifty ", " nse "),
        ("finnifty", "NSE"),
        ("sensex", "bse"),
    ),
)
def test_market_identity_normalized(
    symbol: str,
    exchange: str,
) -> None:
    result = make_result(
        underlying_symbol=symbol,
        exchange=exchange,
    )

    assert (
        result.underlying_symbol,
        result.exchange,
    ) in {
        ("NIFTY", "NSE"),
        ("BANKNIFTY", "NSE"),
        ("FINNIFTY", "NSE"),
        ("SENSEX", "BSE"),
    }


@pytest.mark.parametrize(
    ("symbol", "exchange"),
    (
        ("NIFTY", "BSE"),
        ("SENSEX", "NSE"),
        ("BANKNIFTY", "BSE"),
        ("FINNIFTY", "BSE"),
        ("MIDCPNIFTY", "NSE"),
        ("NIFTY50", "NSE"),
        ("", "NSE"),
        ("NIFTY", ""),
    ),
)
def test_noncanonical_market_identity_rejected(
    symbol: str,
    exchange: str,
) -> None:
    with pytest.raises(ValueError):
        make_result(
            underlying_symbol=symbol,
            exchange=exchange,
        )


@pytest.mark.parametrize(
    "field_name",
    (
        "option_chain_intelligence_result_id",
        "option_chain_snapshot_id",
        "option_chain_quality_result_id",
    ),
)
@pytest.mark.parametrize(
    "invalid_value",
    (
        "",
        " ",
        "\t",
    ),
)
def test_empty_ids_rejected(
    field_name: str,
    invalid_value: str,
) -> None:
    with pytest.raises(ValueError):
        make_result(**{field_name: invalid_value})


@pytest.mark.parametrize(
    "field_name",
    (
        "option_chain_intelligence_result_id",
        "option_chain_snapshot_id",
        "option_chain_quality_result_id",
    ),
)
@pytest.mark.parametrize(
    "invalid_value",
    (
        None,
        1,
        True,
        (),
        [],
    ),
)
def test_non_string_ids_rejected(
    field_name: str,
    invalid_value,
) -> None:
    with pytest.raises(TypeError):
        make_result(**{field_name: invalid_value})


def test_ids_are_trimmed() -> None:
    result = make_result(
        option_chain_intelligence_result_id=" result-1 ",
        option_chain_snapshot_id=" snapshot-1 ",
        option_chain_quality_result_id=" quality-1 ",
    )

    assert result.option_chain_intelligence_result_id == "result-1"
    assert result.option_chain_snapshot_id == "snapshot-1"
    assert result.option_chain_quality_result_id == "quality-1"


def test_created_at_must_be_datetime() -> None:
    with pytest.raises(TypeError):
        make_result(created_at="2026-01-01")


def test_created_at_must_be_timezone_aware() -> None:
    with pytest.raises(ValueError):
        make_result(
            created_at=datetime(2026, 1, 1, 10, 0)
        )


def test_expiry_must_be_date() -> None:
    with pytest.raises(TypeError):
        make_result(expiry="2026-01-29")


def test_expiry_rejects_datetime() -> None:
    with pytest.raises(TypeError):
        make_result(expiry=CREATED_AT)


def test_metrics_must_be_tuple() -> None:
    with pytest.raises(TypeError):
        make_result(metrics=[])


def test_metrics_must_contain_metric_contracts() -> None:
    with pytest.raises(TypeError):
        make_result(metrics=("PCR_OPEN_INTEREST",))


def test_duplicate_metric_names_rejected() -> None:
    first = valid_metric()
    second = valid_metric()

    with pytest.raises(ValueError):
        make_result(
            metrics=(first, second),
            bullish_metrics=("PCR_OPEN_INTEREST",),
            valid_metric_count=2,
        )


def test_metric_lookup() -> None:
    metrics = (
        valid_metric("PCR_OPEN_INTEREST"),
        valid_metric(
            "IV_SKEW",
            signal="BEARISH",
            value=4.0,
        ),
    )

    result = make_result(
        metrics=metrics,
        bullish_metrics=("PCR_OPEN_INTEREST",),
        bearish_metrics=("IV_SKEW",),
        valid_metric_count=2,
    )

    assert (
        result.metric_by_name("iv_skew").metric_name
        == "IV_SKEW"
    )


def test_unknown_metric_lookup_rejected() -> None:
    with pytest.raises(KeyError):
        make_result().metric_by_name("UNKNOWN")


@pytest.mark.parametrize(
    "invalid_name",
    (
        "",
        " ",
    ),
)
def test_empty_metric_lookup_name_rejected(
    invalid_name: str,
) -> None:
    with pytest.raises(ValueError):
        make_result().metric_by_name(invalid_name)


@pytest.mark.parametrize(
    "invalid_name",
    (
        None,
        1,
        True,
        (),
    ),
)
def test_non_string_metric_lookup_name_rejected(
    invalid_name,
) -> None:
    with pytest.raises(TypeError):
        make_result().metric_by_name(invalid_name)


@pytest.mark.parametrize(
    "status",
    (
        "READY",
        "READY_WITH_WARNINGS",
        "INSUFFICIENT_METRICS",
        "CONFLICTING",
        "MALFORMED",
        "UNSUPPORTED",
        "FAILED",
    ),
)
def test_supported_statuses(status: str) -> None:
    if status == "READY":
        result = make_result()

    elif status == "READY_WITH_WARNINGS":
        result = make_result(
            intelligence_status=status,
            warnings=("warning",),
        )

    elif status == "CONFLICTING":
        bearish = valid_metric(
            "IV_SKEW",
            signal="BEARISH",
            value=4.0,
        )
        bullish = valid_metric()

        result = make_result(
            metrics=(bullish, bearish),
            intelligence_status=status,
            aggregate_bias="MIXED",
            aggregate_strength=0.0,
            bullish_metrics=("PCR_OPEN_INTEREST",),
            bearish_metrics=("IV_SKEW",),
            valid_metric_count=2,
            warnings=("signals conflict",),
        )

    else:
        result = make_result(
            intelligence_status=status,
            aggregate_bias="UNAVAILABLE",
            aggregate_strength=0.0,
            blockers=("blocked",),
        )

    assert result.intelligence_status == status


@pytest.mark.parametrize(
    ("raw_status", "expected"),
    (
        ("ready", "READY"),
        (" READY ", "READY"),
        (
            "ready_with_warnings",
            "READY_WITH_WARNINGS",
        ),
    ),
)
def test_status_normalization(
    raw_status: str,
    expected: str,
) -> None:
    warnings = (
        ("warning",)
        if expected == "READY_WITH_WARNINGS"
        else ()
    )

    result = make_result(
        intelligence_status=raw_status,
        warnings=warnings,
    )

    assert result.intelligence_status == expected


@pytest.mark.parametrize(
    "invalid_status",
    (
        "",
        "VALID",
        "BUY",
        "SELL",
        "WAIT",
        "UNKNOWN",
    ),
)
def test_unsupported_status_rejected(
    invalid_status: str,
) -> None:
    with pytest.raises(ValueError):
        make_result(intelligence_status=invalid_status)


@pytest.mark.parametrize(
    "bias",
    (
        "BULLISH",
        "BEARISH",
        "NEUTRAL",
        "MIXED",
        "UNAVAILABLE",
    ),
)
def test_supported_biases(bias: str) -> None:
    if bias == "BULLISH":
        result = make_result()

    elif bias == "BEARISH":
        metric = valid_metric(
            "IV_SKEW",
            signal="BEARISH",
            value=4.0,
        )
        result = make_result(
            metrics=(metric,),
            aggregate_bias=bias,
            bullish_metrics=(),
            bearish_metrics=("IV_SKEW",),
        )

    elif bias == "NEUTRAL":
        metric = valid_metric(
            signal="NEUTRAL",
        )
        result = make_result(
            metrics=(metric,),
            aggregate_bias=bias,
            aggregate_strength=0.0,
            bullish_metrics=(),
            neutral_metrics=("PCR_OPEN_INTEREST",),
        )

    elif bias == "MIXED":
        bullish = valid_metric()
        bearish = valid_metric(
            "IV_SKEW",
            signal="BEARISH",
            value=4.0,
        )
        result = make_result(
            metrics=(bullish, bearish),
            intelligence_status="CONFLICTING",
            aggregate_bias=bias,
            aggregate_strength=0.0,
            bullish_metrics=("PCR_OPEN_INTEREST",),
            bearish_metrics=("IV_SKEW",),
            valid_metric_count=2,
            warnings=("signals conflict",),
        )

    else:
        result = make_result(
            intelligence_status="FAILED",
            aggregate_bias=bias,
            aggregate_strength=0.0,
            blockers=("failed",),
        )

    assert result.aggregate_bias == bias


@pytest.mark.parametrize(
    "invalid_bias",
    (
        "",
        "BUY",
        "SELL",
        "CALL",
        "PUT",
        "UNKNOWN",
    ),
)
def test_unsupported_bias_rejected(
    invalid_bias: str,
) -> None:
    with pytest.raises(ValueError):
        make_result(aggregate_bias=invalid_bias)


@pytest.mark.parametrize(
    "value",
    (
        0.0,
        0.1,
        0.5,
        1.0,
    ),
)
def test_strength_accepts_unit_interval(value: float) -> None:
    result = make_result(
        aggregate_strength=value,
    )

    assert result.aggregate_strength == value


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
def test_invalid_strength_rejected(
    invalid_value: float,
) -> None:
    with pytest.raises(ValueError):
        make_result(
            aggregate_strength=invalid_value
        )


@pytest.mark.parametrize(
    "invalid_value",
    (
        True,
        False,
        "0.2",
        None,
        (),
    ),
)
def test_non_numeric_strength_rejected(invalid_value) -> None:
    with pytest.raises(TypeError):
        make_result(
            aggregate_strength=invalid_value
        )


@pytest.mark.parametrize(
    "field_name",
    (
        "bullish_metrics",
        "bearish_metrics",
        "neutral_metrics",
        "unavailable_metrics",
        "blockers",
        "warnings",
    ),
)
def test_tuple_fields_require_tuple(field_name: str) -> None:
    with pytest.raises(TypeError):
        make_result(**{field_name: []})


def test_metric_classification_must_cover_all_metrics() -> None:
    with pytest.raises(ValueError):
        make_result(
            bullish_metrics=(),
        )


def test_metric_classifications_must_not_overlap() -> None:
    with pytest.raises(ValueError):
        make_result(
            bullish_metrics=("PCR_OPEN_INTEREST",),
            neutral_metrics=("PCR_OPEN_INTEREST",),
        )


def test_metric_classification_rejects_unknown_name() -> None:
    with pytest.raises(ValueError):
        make_result(
            bullish_metrics=("PCR_OPEN_INTEREST",),
            neutral_metrics=("UNKNOWN",),
        )


def test_valid_and_unavailable_counts_reconcile() -> None:
    unavailable = unavailable_metric()

    result = make_result(
        metrics=(
            valid_metric(),
            unavailable,
        ),
        intelligence_status="READY_WITH_WARNINGS",
        bullish_metrics=("PCR_OPEN_INTEREST",),
        unavailable_metrics=("IV_SKEW",),
        valid_metric_count=1,
        unavailable_metric_count=1,
        warnings=("metric unavailable",),
    )

    assert result.valid_metric_count == 1
    assert result.unavailable_metric_count == 1


def test_invalid_valid_metric_count_rejected() -> None:
    with pytest.raises(ValueError):
        make_result(valid_metric_count=0)


def test_invalid_unavailable_metric_count_rejected() -> None:
    with pytest.raises(ValueError):
        make_result(unavailable_metric_count=1)


@pytest.mark.parametrize(
    "field_name",
    (
        "valid_metric_count",
        "unavailable_metric_count",
    ),
)
@pytest.mark.parametrize(
    "invalid_value",
    (
        -1,
        -10,
    ),
)
def test_negative_metric_counts_rejected(
    field_name: str,
    invalid_value: int,
) -> None:
    with pytest.raises(ValueError):
        make_result(**{field_name: invalid_value})


@pytest.mark.parametrize(
    "field_name",
    (
        "valid_metric_count",
        "unavailable_metric_count",
    ),
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
def test_non_integer_metric_counts_rejected(
    field_name: str,
    invalid_value,
) -> None:
    with pytest.raises(TypeError):
        make_result(**{field_name: invalid_value})


@pytest.mark.parametrize(
    "field_name",
    (
        "support_strikes",
        "resistance_strikes",
    ),
)
def test_strike_fields_convert_to_float(
    field_name: str,
) -> None:
    result = make_result(
        **{field_name: (21900, 22000)}
    )

    assert getattr(result, field_name) == (
        21900.0,
        22000.0,
    )


@pytest.mark.parametrize(
    "field_name",
    (
        "support_strikes",
        "resistance_strikes",
    ),
)
def test_strike_fields_require_tuple(field_name: str) -> None:
    with pytest.raises(TypeError):
        make_result(**{field_name: [22000.0]})


@pytest.mark.parametrize(
    "field_name",
    (
        "support_strikes",
        "resistance_strikes",
    ),
)
@pytest.mark.parametrize(
    "invalid_strike",
    (
        0,
        -1,
        nan,
        inf,
        -inf,
    ),
)
def test_invalid_strike_values_rejected(
    field_name: str,
    invalid_strike: float,
) -> None:
    with pytest.raises(ValueError):
        make_result(
            **{field_name: (invalid_strike,)}
        )


@pytest.mark.parametrize(
    "field_name",
    (
        "support_strikes",
        "resistance_strikes",
    ),
)
def test_duplicate_strikes_rejected(field_name: str) -> None:
    with pytest.raises(ValueError):
        make_result(
            **{field_name: (22000.0, 22000.0)}
        )


@pytest.mark.parametrize(
    "field_name",
    (
        "support_strikes",
        "resistance_strikes",
    ),
)
def test_unsorted_strikes_rejected(field_name: str) -> None:
    with pytest.raises(ValueError):
        make_result(
            **{field_name: (22100.0, 22000.0)}
        )


@pytest.mark.parametrize(
    "value",
    (
        None,
        22000,
        22000.0,
    ),
)
def test_max_pain_strike_accepts_none_or_positive(
    value,
) -> None:
    result = make_result(max_pain_strike=value)

    assert result.max_pain_strike == (
        None if value is None else float(value)
    )


@pytest.mark.parametrize(
    "invalid_value",
    (
        0,
        -1,
        nan,
        inf,
        -inf,
    ),
)
def test_invalid_max_pain_strike_rejected(
    invalid_value: float,
) -> None:
    with pytest.raises(ValueError):
        make_result(max_pain_strike=invalid_value)


@pytest.mark.parametrize(
    "invalid_value",
    (
        True,
        "22000",
        (),
        [],
    ),
)
def test_non_numeric_max_pain_strike_rejected(
    invalid_value,
) -> None:
    with pytest.raises(TypeError):
        make_result(max_pain_strike=invalid_value)


def test_ready_rejects_blockers() -> None:
    with pytest.raises(ValueError):
        make_result(blockers=("blocked",))


def test_ready_rejects_warnings() -> None:
    with pytest.raises(ValueError):
        make_result(warnings=("warning",))


def test_ready_rejects_unavailable_bias() -> None:
    with pytest.raises(ValueError):
        make_result(
            aggregate_bias="UNAVAILABLE",
            aggregate_strength=0.0,
        )


def test_ready_rejects_unavailable_metrics() -> None:
    unavailable = unavailable_metric()

    with pytest.raises(ValueError):
        make_result(
            metrics=(
                valid_metric(),
                unavailable,
            ),
            bullish_metrics=("PCR_OPEN_INTEREST",),
            unavailable_metrics=("IV_SKEW",),
            valid_metric_count=1,
            unavailable_metric_count=1,
        )


def test_ready_with_warnings_requires_warning() -> None:
    with pytest.raises(ValueError):
        make_result(
            intelligence_status="READY_WITH_WARNINGS"
        )


def test_ready_with_warnings_rejects_blockers() -> None:
    with pytest.raises(ValueError):
        make_result(
            intelligence_status="READY_WITH_WARNINGS",
            blockers=("blocked",),
            warnings=("warning",),
        )


def test_conflicting_requires_diagnostic() -> None:
    bearish = valid_metric(
        "IV_SKEW",
        signal="BEARISH",
        value=4.0,
    )

    with pytest.raises(ValueError):
        make_result(
            metrics=(
                valid_metric(),
                bearish,
            ),
            intelligence_status="CONFLICTING",
            aggregate_bias="MIXED",
            aggregate_strength=0.0,
            bullish_metrics=("PCR_OPEN_INTEREST",),
            bearish_metrics=("IV_SKEW",),
            valid_metric_count=2,
        )


@pytest.mark.parametrize(
    "bias",
    (
        "BULLISH",
        "BEARISH",
        "UNAVAILABLE",
    ),
)
def test_conflicting_requires_mixed_or_neutral_bias(
    bias: str,
) -> None:
    bearish = valid_metric(
        "IV_SKEW",
        signal="BEARISH",
        value=4.0,
    )

    with pytest.raises(ValueError):
        make_result(
            metrics=(
                valid_metric(),
                bearish,
            ),
            intelligence_status="CONFLICTING",
            aggregate_bias=bias,
            aggregate_strength=0.0,
            bullish_metrics=("PCR_OPEN_INTEREST",),
            bearish_metrics=("IV_SKEW",),
            valid_metric_count=2,
            warnings=("conflict",),
        )


@pytest.mark.parametrize(
    "status",
    (
        "INSUFFICIENT_METRICS",
        "MALFORMED",
        "UNSUPPORTED",
        "FAILED",
    ),
)
def test_blocking_status_creation(status: str) -> None:
    result = make_result(
        intelligence_status=status,
        aggregate_bias="UNAVAILABLE",
        aggregate_strength=0.0,
        blockers=("blocked",),
    )

    assert result.intelligence_status == status
    assert result.aggregate_bias == "UNAVAILABLE"
    assert result.aggregate_strength == 0.0


@pytest.mark.parametrize(
    "status",
    (
        "INSUFFICIENT_METRICS",
        "MALFORMED",
        "UNSUPPORTED",
        "FAILED",
    ),
)
def test_blocking_status_requires_blocker(
    status: str,
) -> None:
    with pytest.raises(ValueError):
        make_result(
            intelligence_status=status,
            aggregate_bias="UNAVAILABLE",
            aggregate_strength=0.0,
            blockers=(),
        )


@pytest.mark.parametrize(
    "status",
    (
        "INSUFFICIENT_METRICS",
        "MALFORMED",
        "UNSUPPORTED",
        "FAILED",
    ),
)
def test_blocking_status_requires_unavailable_bias(
    status: str,
) -> None:
    with pytest.raises(ValueError):
        make_result(
            intelligence_status=status,
            aggregate_bias="BULLISH",
            aggregate_strength=0.0,
            blockers=("blocked",),
        )


@pytest.mark.parametrize(
    "status",
    (
        "INSUFFICIENT_METRICS",
        "MALFORMED",
        "UNSUPPORTED",
        "FAILED",
    ),
)
def test_blocking_status_requires_zero_strength(
    status: str,
) -> None:
    with pytest.raises(ValueError):
        make_result(
            intelligence_status=status,
            aggregate_bias="UNAVAILABLE",
            aggregate_strength=0.1,
            blockers=("blocked",),
        )


def test_unavailable_bias_requires_zero_strength() -> None:
    with pytest.raises(ValueError):
        make_result(
            intelligence_status="FAILED",
            aggregate_bias="UNAVAILABLE",
            aggregate_strength=0.1,
            blockers=("failed",),
        )


def test_bullish_bias_requires_bullish_metric() -> None:
    metric = valid_metric(
        signal="NEUTRAL",
    )

    with pytest.raises(ValueError):
        make_result(
            metrics=(metric,),
            aggregate_bias="BULLISH",
            bullish_metrics=(),
            neutral_metrics=("PCR_OPEN_INTEREST",),
        )


def test_bearish_bias_requires_bearish_metric() -> None:
    with pytest.raises(ValueError):
        make_result(
            aggregate_bias="BEARISH",
            bullish_metrics=("PCR_OPEN_INTEREST",),
            bearish_metrics=(),
        )


def test_mixed_bias_requires_bullish_and_bearish_metrics() -> None:
    with pytest.raises(ValueError):
        make_result(
            intelligence_status="CONFLICTING",
            aggregate_bias="MIXED",
            warnings=("conflict",),
        )


@pytest.mark.parametrize(
    "invalid_mode",
    (
        "LIVE",
        "live",
        "",
        "PAPER ",
    ),
)
def test_execution_mode_must_remain_paper(
    invalid_mode: str,
) -> None:
    with pytest.raises(ValueError):
        make_result(execution_mode=invalid_mode)


@pytest.mark.parametrize(
    "invalid_value",
    (
        True,
        1,
        "False",
        None,
    ),
)
def test_live_execution_must_remain_false(
    invalid_value,
) -> None:
    with pytest.raises(ValueError):
        make_result(
            live_execution_eligible=invalid_value
        )


def test_deterministic_serialization() -> None:
    metric = valid_metric()

    result = make_result(
        metrics=(metric,),
        support_strikes=(21900.0,),
        resistance_strikes=(22100.0,),
        max_pain_strike=22000.0,
    )

    assert result.to_dict() == {
        "schema_version": (
            "option_chain_intelligence_result.v1"
        ),
        "option_chain_intelligence_result_id": "result-1",
        "created_at": "2026-01-01T10:00:00+00:00",
        "option_chain_snapshot_id": "snapshot-1",
        "option_chain_quality_result_id": "quality-1",
        "underlying_symbol": "NIFTY",
        "exchange": "NSE",
        "expiry": "2026-01-29",
        "metrics": [metric.to_dict()],
        "intelligence_status": "READY",
        "aggregate_bias": "BULLISH",
        "aggregate_strength": 0.20,
        "bullish_metrics": ["PCR_OPEN_INTEREST"],
        "bearish_metrics": [],
        "neutral_metrics": [],
        "unavailable_metrics": [],
        "valid_metric_count": 1,
        "unavailable_metric_count": 0,
        "support_strikes": [21900.0],
        "resistance_strikes": [22100.0],
        "max_pain_strike": 22000.0,
        "blockers": [],
        "warnings": [],
        "execution_mode": "PAPER",
        "live_execution_eligible": False,
    }


def test_serialization_returns_new_containers() -> None:
    result = make_result(
        support_strikes=(21900.0,),
        resistance_strikes=(22100.0,),
    )

    first = result.to_dict()
    second = result.to_dict()

    assert first == second
    assert first is not second
    assert first["metrics"] is not second["metrics"]
    assert first["bullish_metrics"] is not second[
        "bullish_metrics"
    ]
    assert first["support_strikes"] is not second[
        "support_strikes"
    ]


def test_equality_is_value_based() -> None:
    assert make_result() == make_result()


def test_result_is_hashable() -> None:
    results = {
        make_result(),
        make_result(),
    }

    assert len(results) == 1