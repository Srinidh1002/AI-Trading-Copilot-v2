"""Tests for canonical option-chain intelligence aggregation."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.contracts.option_chain_intelligence_policy_v1 import (
    DEFAULT_OPTION_CHAIN_INTELLIGENCE_POLICY,
    OptionChainIntelligencePolicyV1,
)
from services.contracts.option_chain_metric_v1 import (
    OptionChainMetricV1,
)
from services.contracts.option_chain_quality_result_v1 import (
    OptionChainQualityResultV1,
)
from services.option_chain_intelligence.aggregation import (
    aggregate_option_chain_intelligence,
)
from tests.test_option_chain_pcr import (
    CREATED_AT,
    EXPIRY,
    make_row,
    make_snapshot,
)


RESULT_TIME = datetime(
    2026,
    1,
    1,
    10,
    1,
    tzinfo=timezone.utc,
)


def make_quality(
    *,
    snapshot_id: str = "snapshot-1",
    symbol: str = "NIFTY",
    exchange: str = "NSE",
    status: str = "VALID",
    blockers: tuple[str, ...] = (),
    warnings: tuple[str, ...] = (),
) -> OptionChainQualityResultV1:
    return OptionChainQualityResultV1(
        option_chain_quality_result_id="quality-1",
        created_at=CREATED_AT,
        option_chain_snapshot_id=snapshot_id,
        underlying_symbol=symbol,
        exchange=exchange,
        expiry=EXPIRY,
        quality_status=status,
        age_seconds=0.0,
        total_strikes=1,
        complete_pair_count=1,
        missing_call_count=0,
        missing_put_count=0,
        malformed_quote_count=0,
        duplicate_strike_count=0,
        completeness_ratio=1.0,
        blockers=blockers,
        warnings=warnings,
    )


def make_metric(
    metric_name: str,
    *,
    signal: str = "NEUTRAL",
    value: float = 0.0,
    status: str = "VALID",
    blockers: tuple[str, ...] = (),
    warnings: tuple[str, ...] = (),
) -> OptionChainMetricV1:
    return OptionChainMetricV1(
        metric_name=metric_name,
        value=(
            None
            if status
            not in {"VALID", "VALID_WITH_WARNINGS"}
            else value
        ),
        signal=(
            "UNAVAILABLE"
            if status
            not in {"VALID", "VALID_WITH_WARNINGS"}
            else signal
        ),
        status=status,
        sample_size=1,
        blockers=blockers,
        warnings=warnings,
    )


def canonical_metrics(
    *,
    pcr_oi: str = "NEUTRAL",
    pcr_volume: str = "NEUTRAL",
    oi_concentration: str = "BALANCED",
    oi_buildup: str = "NEUTRAL",
    max_pain: str = "NEUTRAL",
    iv_skew: str = "NEUTRAL",
    support_resistance: str = "NEUTRAL",
) -> tuple[OptionChainMetricV1, ...]:
    return (
        make_metric(
            "PCR_OPEN_INTEREST",
            signal=pcr_oi,
            value=1.0,
        ),
        make_metric(
            "PCR_VOLUME",
            signal=pcr_volume,
            value=1.0,
        ),
        make_metric(
            "OI_CONCENTRATION",
            signal=oi_concentration,
            value=0.25,
        ),
        make_metric(
            "OI_BUILDUP",
            signal=oi_buildup,
            value=0.0,
        ),
        make_metric(
            "MAX_PAIN",
            signal=max_pain,
            value=22000.0,
        ),
        make_metric(
            "IV_SKEW",
            signal=iv_skew,
            value=0.0,
        ),
        make_metric(
            "SUPPORT_RESISTANCE",
            signal=support_resistance,
            value=0.0,
        ),
    )


def make_policy(**overrides) -> OptionChainIntelligencePolicyV1:
    values = DEFAULT_OPTION_CHAIN_INTELLIGENCE_POLICY.to_dict()

    values.pop("schema_version")
    values.pop("required_metrics")
    values["metric_weights"] = tuple(
        tuple(item)
        for item in values["metric_weights"]
    )
    values.update(overrides)

    return OptionChainIntelligencePolicyV1(**values)


def base_snapshot():
    return make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
            ),
        )
    )


def aggregate(
    metrics: tuple[OptionChainMetricV1, ...],
    **overrides,
):
    values = {
        "snapshot": base_snapshot(),
        "quality_result": make_quality(),
        "metrics": metrics,
        "clock": lambda: RESULT_TIME,
        "option_chain_intelligence_result_id_factory": (
            lambda: "intelligence-1"
        ),
    }
    values.update(overrides)

    return aggregate_option_chain_intelligence(**values)


def test_all_neutral_metrics_produce_ready_neutral() -> None:
    result = aggregate(canonical_metrics())

    assert result.intelligence_status == "READY"
    assert result.aggregate_bias == "NEUTRAL"
    assert result.aggregate_strength == 0.0
    assert result.bullish_metrics == ()
    assert result.bearish_metrics == ()
    assert result.valid_metric_count == 7
    assert result.unavailable_metric_count == 0


def test_weighted_bullish_aggregation() -> None:
    result = aggregate(
        canonical_metrics(
            pcr_oi="BULLISH",
            oi_buildup="BULLISH",
            support_resistance="BULLISH",
        )
    )

    assert result.intelligence_status == "READY"
    assert result.aggregate_bias == "BULLISH"
    assert result.aggregate_strength == pytest.approx(0.55)
    assert result.bullish_metrics == (
        "PCR_OPEN_INTEREST",
        "OI_BUILDUP",
        "SUPPORT_RESISTANCE",
    )


def test_weighted_bearish_aggregation() -> None:
    result = aggregate(
        canonical_metrics(
            pcr_oi="BEARISH",
            oi_buildup="BEARISH",
            support_resistance="BEARISH",
        )
    )

    assert result.intelligence_status == "READY"
    assert result.aggregate_bias == "BEARISH"
    assert result.aggregate_strength == pytest.approx(0.55)
    assert result.bearish_metrics == (
        "PCR_OPEN_INTEREST",
        "OI_BUILDUP",
        "SUPPORT_RESISTANCE",
    )


def test_exact_bullish_threshold_is_bullish() -> None:
    result = aggregate(
        canonical_metrics(
            support_resistance="BULLISH",
        )
    )

    assert result.aggregate_strength == pytest.approx(0.15)
    assert result.aggregate_bias == "BULLISH"


def test_exact_bearish_threshold_is_bearish() -> None:
    result = aggregate(
        canonical_metrics(
            support_resistance="BEARISH",
        )
    )

    assert result.aggregate_strength == pytest.approx(0.15)
    assert result.aggregate_bias == "BEARISH"


def test_structural_signals_have_zero_directional_weight() -> None:
    result = aggregate(
        canonical_metrics(
            oi_concentration="CONCENTRATED",
        )
    )

    assert result.aggregate_strength == 0.0
    assert result.aggregate_bias == "NEUTRAL"
    assert result.neutral_metrics == (
        "PCR_OPEN_INTEREST",
        "PCR_VOLUME",
        "OI_CONCENTRATION",
        "OI_BUILDUP",
        "MAX_PAIN",
        "IV_SKEW",
        "SUPPORT_RESISTANCE",
    )


def test_low_score_bullish_bearish_conflict() -> None:
    result = aggregate(
        canonical_metrics(
            pcr_volume="BULLISH",
            iv_skew="BEARISH",
        )
    )

    assert result.intelligence_status == "CONFLICTING"
    assert result.aggregate_bias == "MIXED"
    assert result.aggregate_strength == 0.0
    assert result.bullish_metrics == ("PCR_VOLUME",)
    assert result.bearish_metrics == ("IV_SKEW",)
    assert result.warnings == (
    "BULLISH AND BEARISH OPTION-CHAIN METRICS CONFLICT "
    "WITHIN THE CONFIGURED SCORE TOLERANCE",
    )


def test_conflict_block_behavior() -> None:
    result = aggregate(
        canonical_metrics(
            pcr_volume="BULLISH",
            iv_skew="BEARISH",
        ),
        policy=make_policy(
            conflicting_signal_behavior="BLOCK",
        ),
    )

    assert result.intelligence_status == "CONFLICTING"
    assert result.aggregate_bias == "MIXED"
    assert result.blockers == (
    "BULLISH AND BEARISH OPTION-CHAIN METRICS CONFLICT "
    "WITHIN THE CONFIGURED SCORE TOLERANCE",
    )


def test_conflict_allow_behavior_returns_neutral() -> None:
    result = aggregate(
        canonical_metrics(
            pcr_volume="BULLISH",
            iv_skew="BEARISH",
        ),
        policy=make_policy(
            conflicting_signal_behavior="ALLOW",
        ),
    )

    assert result.intelligence_status == "READY"
    assert result.aggregate_bias == "NEUTRAL"
    assert result.aggregate_strength == 0.0


def test_metric_warning_produces_ready_with_warnings() -> None:
    metrics = list(canonical_metrics())
    metrics[0] = make_metric(
        "PCR_OPEN_INTEREST",
        signal="BULLISH",
        value=1.5,
        status="VALID_WITH_WARNINGS",
        warnings=("EXTREME PCR READING",),
    )

    result = aggregate(tuple(metrics))

    assert result.intelligence_status == "READY_WITH_WARNINGS"
    assert result.warnings == ("EXTREME PCR READING",)


def test_quality_warning_is_propagated() -> None:
    result = aggregate(
        canonical_metrics(),
        quality_result=make_quality(
            status="VALID_WITH_WARNINGS",
            warnings=("QUALITY WARNING",),
        ),
    )

    assert result.intelligence_status == "READY_WITH_WARNINGS"
    assert result.warnings == ("QUALITY WARNING",)


def test_unavailable_metric_weight_is_not_renormalized() -> None:
    metrics = list(
        canonical_metrics(
            pcr_oi="BULLISH",
        )
    )
    metrics[3] = make_metric(
        "OI_BUILDUP",
        status="UNAVAILABLE",
        blockers=("OI buildup unavailable",),
    )

    result = aggregate(tuple(metrics))

    assert result.aggregate_strength == pytest.approx(0.20)
    assert result.aggregate_bias == "BULLISH"
    assert result.valid_metric_count == 6
    assert result.unavailable_metric_count == 1
    assert result.unavailable_metrics == ("OI_BUILDUP",)
    assert "OI BUILDUP UNAVAILABLE" in result.warnings


def test_insufficient_valid_metrics_blocks() -> None:
    metrics = (
        make_metric(
            "PCR_OPEN_INTEREST",
            signal="BULLISH",
            value=1.2,
        ),
        make_metric(
            "PCR_VOLUME",
            signal="BULLISH",
            value=1.2,
        ),
        make_metric(
            "OI_CONCENTRATION",
            signal="BALANCED",
            value=0.25,
        ),
        make_metric(
            "OI_BUILDUP",
            status="UNAVAILABLE",
            blockers=("unavailable",),
        ),
        make_metric(
            "MAX_PAIN",
            status="UNAVAILABLE",
            blockers=("unavailable",),
        ),
        make_metric(
            "IV_SKEW",
            status="UNAVAILABLE",
            blockers=("unavailable",),
        ),
        make_metric(
            "SUPPORT_RESISTANCE",
            status="UNAVAILABLE",
            blockers=("unavailable",),
        ),
    )

    result = aggregate(metrics)

    assert result.intelligence_status == "INSUFFICIENT_METRICS"
    assert result.aggregate_bias == "UNAVAILABLE"
    assert result.aggregate_strength == 0.0
    assert (
        "VALID OPTION-CHAIN METRIC COUNT IS BELOW THE CONFIGURED "
        "MINIMUM"
    ) in result.blockers


def test_missing_required_metric_is_classified_unavailable() -> None:
    metrics = canonical_metrics()[:-1]

    result = aggregate(metrics)

    assert result.unavailable_metric_count == 0
    assert result.unavailable_metrics == ()
    assert result.warnings == (
        "REQUIRED OPTION-CHAIN METRICS ARE MISSING: "
        "SUPPORT_RESISTANCE",
    )
   


def test_missing_metric_block_behavior() -> None:
    result = aggregate(
        canonical_metrics()[:-1],
        policy=make_policy(
            missing_metric_behavior="BLOCK",
        ),
    )

    assert result.intelligence_status == "INSUFFICIENT_METRICS"
    assert result.aggregate_bias == "UNAVAILABLE"
    assert result.blockers == (
    "REQUIRED OPTION-CHAIN METRICS ARE MISSING: "
    "SUPPORT_RESISTANCE",
    )


def test_quality_blocking_status_blocks_intelligence() -> None:
    result = aggregate(
        canonical_metrics(),
        quality_result=make_quality(
            status="STALE",
            blockers=("option chain is stale",),
        ),
    )

    assert result.intelligence_status == "INSUFFICIENT_METRICS"
    assert result.aggregate_bias == "UNAVAILABLE"
    assert result.aggregate_strength == 0.0
    assert result.blockers == (
    "OPTION CHAIN IS STALE",
    "OPTION-CHAIN QUALITY STATUS DOES NOT PERMIT "
    "INTELLIGENCE AGGREGATION",
    )


def test_support_resistance_and_max_pain_are_preserved() -> None:
    result = aggregate(
        canonical_metrics(),
        support_strikes=(21900.0, 22000.0),
        resistance_strikes=(22000.0, 22100.0),
        max_pain_strike=22000.0,
    )

    assert result.support_strikes == (
        21900.0,
        22000.0,
    )
    assert result.resistance_strikes == (
        22000.0,
        22100.0,
    )
    assert result.max_pain_strike == 22000.0


def test_deterministic_clock_and_id_factory() -> None:
    result = aggregate(canonical_metrics())

    assert result.created_at == RESULT_TIME
    assert (
        result.option_chain_intelligence_result_id
        == "intelligence-1"
    )


def test_snapshot_reference_is_preserved() -> None:
    result = aggregate(canonical_metrics())

    assert result.option_chain_snapshot_id == "snapshot-1"
    assert result.option_chain_quality_result_id == "quality-1"


def test_snapshot_type_validation() -> None:
    with pytest.raises(TypeError):
        aggregate_option_chain_intelligence(
            snapshot="snapshot",
            quality_result=make_quality(),
            metrics=canonical_metrics(),
        )


def test_quality_result_type_validation() -> None:
    with pytest.raises(TypeError):
        aggregate_option_chain_intelligence(
            snapshot=base_snapshot(),
            quality_result="quality",
            metrics=canonical_metrics(),
        )


def test_policy_type_validation() -> None:
    with pytest.raises(TypeError):
        aggregate(
            canonical_metrics(),
            policy="policy",
        )


def test_metrics_must_be_tuple() -> None:
    with pytest.raises(TypeError):
        aggregate(
            list(canonical_metrics()),
        )


def test_metrics_must_contain_metric_contracts() -> None:
    with pytest.raises(TypeError):
        aggregate(("metric",))


def test_duplicate_metric_names_rejected() -> None:
    metric = make_metric(
        "PCR_OPEN_INTEREST",
        signal="BULLISH",
        value=1.2,
    )

    with pytest.raises(ValueError):
        aggregate((metric, metric))


def test_quality_snapshot_reference_must_match() -> None:
    with pytest.raises(ValueError):
        aggregate(
            canonical_metrics(),
            quality_result=make_quality(
                snapshot_id="other-snapshot",
            ),
        )


def test_quality_identity_must_match_snapshot() -> None:
    with pytest.raises(ValueError):
        aggregate(
            canonical_metrics(),
            quality_result=make_quality(
                symbol="SENSEX",
                exchange="BSE",
            ),
        )


@pytest.mark.parametrize(
    "field_name",
    (
        "support_strikes",
        "resistance_strikes",
    ),
)
def test_strike_fields_must_be_tuples(field_name: str) -> None:
    with pytest.raises(TypeError):
        aggregate(
            canonical_metrics(),
            **{field_name: [22000.0]},
        )


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
        0.0,
        -1.0,
    ),
)
def test_invalid_strikes_rejected(
    field_name: str,
    invalid_strike: float,
) -> None:
    with pytest.raises(ValueError):
        aggregate(
            canonical_metrics(),
            **{field_name: (invalid_strike,)},
        )


def test_duplicate_support_strikes_rejected() -> None:
    with pytest.raises(ValueError):
        aggregate(
            canonical_metrics(),
            support_strikes=(22000.0, 22000.0),
        )


def test_unsorted_resistance_strikes_rejected() -> None:
    with pytest.raises(ValueError):
        aggregate(
            canonical_metrics(),
            resistance_strikes=(22100.0, 22000.0),
        )


@pytest.mark.parametrize(
    "invalid_max_pain",
    (
        0.0,
        -1.0,
    ),
)
def test_invalid_max_pain_rejected(
    invalid_max_pain: float,
) -> None:
    with pytest.raises(ValueError):
        aggregate(
            canonical_metrics(),
            max_pain_strike=invalid_max_pain,
        )


def test_clock_must_return_timezone_aware_datetime() -> None:
    with pytest.raises(ValueError):
        aggregate(
            canonical_metrics(),
            clock=lambda: datetime(2026, 1, 1, 10, 0),
        )


@pytest.mark.parametrize(
    "invalid_id",
    (
        "",
        " ",
        None,
        1,
    ),
)
def test_result_id_factory_must_return_nonempty_string(
    invalid_id,
) -> None:
    with pytest.raises(ValueError):
        aggregate(
            canonical_metrics(),
            option_chain_intelligence_result_id_factory=(
                lambda: invalid_id
            ),
        )


def test_snapshot_and_metrics_are_not_mutated() -> None:
    snapshot = base_snapshot()
    metrics = canonical_metrics()

    snapshot_before = snapshot.to_dict()
    metrics_before = tuple(
        metric.to_dict()
        for metric in metrics
    )

    aggregate(
        metrics,
        snapshot=snapshot,
    )

    assert snapshot.to_dict() == snapshot_before
    assert tuple(
        metric.to_dict()
        for metric in metrics
    ) == metrics_before


def test_no_decision_ranking_risk_or_execution_output() -> None:
    serialized = aggregate(
        canonical_metrics()
    ).to_dict()

    assert "action" not in serialized
    assert "decision" not in serialized
    assert "ranking" not in serialized
    assert "risk" not in serialized
    assert "execution" not in serialized