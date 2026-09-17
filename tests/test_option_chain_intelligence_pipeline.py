"""Integration tests for the canonical option-chain intelligence pipeline."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.contracts.option_chain_intelligence_policy_v1 import (
    DEFAULT_OPTION_CHAIN_INTELLIGENCE_POLICY,
    OptionChainIntelligencePolicyV1,
)
from services.contracts.option_chain_quality_result_v1 import (
    OptionChainQualityResultV1,
)
from services.option_chain_intelligence.intelligence_pipeline import (
    build_canonical_option_chain_intelligence,
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
    total_strikes: int = 3,
    complete_pair_count: int = 3,
    missing_call_count: int = 0,
    missing_put_count: int = 0,
) -> OptionChainQualityResultV1:
    completeness_ratio = (
        complete_pair_count / total_strikes
        if total_strikes
        else 0.0
    )

    return OptionChainQualityResultV1(
        option_chain_quality_result_id="quality-1",
        created_at=CREATED_AT,
        option_chain_snapshot_id=snapshot_id,
        underlying_symbol=symbol,
        exchange=exchange,
        expiry=EXPIRY,
        quality_status=status,
        age_seconds=0.0,
        total_strikes=total_strikes,
        complete_pair_count=complete_pair_count,
        missing_call_count=missing_call_count,
        missing_put_count=missing_put_count,
        malformed_quote_count=0,
        duplicate_strike_count=0,
        completeness_ratio=completeness_ratio,
        blockers=blockers,
        warnings=warnings,
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


def canonical_snapshot():
    return make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=21900.0,
                call_oi=100,
                put_oi=300,
                call_volume=100,
                put_volume=150,
            ),
            make_row(
                row_id="row-2",
                strike=22000.0,
                call_oi=300,
                put_oi=500,
                call_volume=200,
                put_volume=240,
            ),
            make_row(
                row_id="row-3",
                strike=22100.0,
                call_oi=500,
                put_oi=100,
                call_volume=300,
                put_volume=210,
            ),
        )
    )


def build(snapshot=None, quality_result=None, **overrides):
    resolved_snapshot = snapshot or canonical_snapshot()
    resolved_quality = quality_result or make_quality()

    values = {
        "snapshot": resolved_snapshot,
        "quality_result": resolved_quality,
        "clock": lambda: RESULT_TIME,
        "option_chain_intelligence_result_id_factory": (
            lambda: "intelligence-1"
        ),
    }
    values.update(overrides)

    return build_canonical_option_chain_intelligence(**values)


def test_pipeline_returns_canonical_result() -> None:
    result = build()

    assert (
        result.schema_version
        == "option_chain_intelligence_result.v1"
    )
    assert (
        result.option_chain_intelligence_result_id
        == "intelligence-1"
    )
    assert result.created_at == RESULT_TIME
    assert result.option_chain_snapshot_id == "snapshot-1"
    assert result.option_chain_quality_result_id == "quality-1"


def test_pipeline_builds_exact_metric_order() -> None:
    result = build()

    assert tuple(
        metric.metric_name
        for metric in result.metrics
    ) == (
        "PCR_OPEN_INTEREST",
        "PCR_VOLUME",
        "OI_CONCENTRATION",
        "OI_BUILDUP",
        "MAX_PAIN",
        "IV_SKEW",
        "SUPPORT_RESISTANCE",
    )


def test_pipeline_builds_exactly_seven_metrics() -> None:
    result = build()

    assert len(result.metrics) == 7
    assert result.valid_metric_count == 7
    assert result.unavailable_metric_count == 0


def test_pipeline_preserves_market_identity() -> None:
    result = build()

    assert result.underlying_symbol == "NIFTY"
    assert result.exchange == "NSE"
    assert result.expiry == EXPIRY


def test_pipeline_preserves_support_strikes() -> None:
    result = build()

    assert result.support_strikes == (
        21900.0,
        22000.0,
    )


def test_pipeline_preserves_resistance_strikes() -> None:
    result = build()

    assert result.resistance_strikes == (
        22000.0,
        22100.0,
    )


def test_pipeline_preserves_max_pain_strike() -> None:
    result = build()

    max_pain_metric = result.metric_by_name("MAX_PAIN")

    assert max_pain_metric.status in {
        "VALID",
        "VALID_WITH_WARNINGS",
    }
    assert result.max_pain_strike == max_pain_metric.value


def test_pipeline_result_is_paper_only() -> None:
    result = build()

    assert result.execution_mode == "PAPER"
    assert result.live_execution_eligible is False


def test_pipeline_produces_ready_result_for_complete_chain() -> None:
    result = build()

    assert result.intelligence_status in {
        "READY",
        "READY_WITH_WARNINGS",
        "CONFLICTING",
    }
    assert result.aggregate_bias in {
        "BULLISH",
        "BEARISH",
        "NEUTRAL",
        "MIXED",
    }


def test_pipeline_uses_custom_policy_thresholds() -> None:
    policy = make_policy(
        pcr_bullish_threshold=2.0,
        pcr_bearish_threshold=0.5,
        pcr_extreme_high_threshold=3.0,
        pcr_extreme_low_threshold=0.25,
    )

    result = build(policy=policy)

    oi_pcr = result.metric_by_name(
        "PCR_OPEN_INTEREST"
    )
    volume_pcr = result.metric_by_name("PCR_VOLUME")

    assert oi_pcr.signal == "NEUTRAL"
    assert volume_pcr.signal == "NEUTRAL"


def test_pipeline_uses_custom_support_resistance_top_n() -> None:
    policy = make_policy(
        support_resistance_top_n=1
    )

    result = build(policy=policy)

    assert len(result.support_strikes) == 1
    assert len(result.resistance_strikes) == 1


def test_pipeline_uses_custom_iv_skew_threshold() -> None:
    policy = make_policy(
        iv_skew_material_difference=100.0
    )

    result = build(policy=policy)

    assert (
        result.metric_by_name("IV_SKEW").signal
        == "NEUTRAL"
    )


def test_quality_warning_is_propagated() -> None:
    result = build(
        quality_result=make_quality(
            status="VALID_WITH_WARNINGS",
            warnings=("quality warning",),
        )
    )

    assert result.intelligence_status in {
        "READY_WITH_WARNINGS",
        "CONFLICTING",
    }
    assert "QUALITY WARNING" in result.warnings


def test_blocking_quality_prevents_ready_intelligence() -> None:
    result = build(
        quality_result=make_quality(
            status="STALE",
            blockers=("option chain is stale",),
        )
    )

    assert (
        result.intelligence_status
        == "INSUFFICIENT_METRICS"
    )
    assert result.aggregate_bias == "UNAVAILABLE"
    assert result.aggregate_strength == 0.0
    assert "OPTION CHAIN IS STALE" in result.blockers


def test_blocking_quality_still_returns_seven_metrics() -> None:
    result = build(
        quality_result=make_quality(
            status="STALE",
            blockers=("option chain is stale",),
        )
    )

    assert len(result.metrics) == 7
    assert tuple(
        metric.metric_name
        for metric in result.metrics
    ) == (
        "PCR_OPEN_INTEREST",
        "PCR_VOLUME",
        "OI_CONCENTRATION",
        "OI_BUILDUP",
        "MAX_PAIN",
        "IV_SKEW",
        "SUPPORT_RESISTANCE",
    )


def test_empty_chain_returns_blocked_intelligence() -> None:
    snapshot = make_snapshot(())

    quality = make_quality(
        status="EMPTY",
        blockers=("option chain is empty",),
        total_strikes=0,
        complete_pair_count=0,
    )

    result = build(
        snapshot=snapshot,
        quality_result=quality,
    )

    assert (
        result.intelligence_status
        == "INSUFFICIENT_METRICS"
    )
    assert result.aggregate_bias == "UNAVAILABLE"
    assert result.aggregate_strength == 0.0


def test_empty_chain_metrics_are_unavailable() -> None:
    snapshot = make_snapshot(())

    quality = make_quality(
        status="EMPTY",
        blockers=("option chain is empty",),
        total_strikes=0,
        complete_pair_count=0,
    )

    result = build(
        snapshot=snapshot,
        quality_result=quality,
    )

    assert all(
        metric.status
        in {
            "UNAVAILABLE",
            "INSUFFICIENT_DATA",
            "MALFORMED",
            "FAILED",
        }
        for metric in result.metrics
    )


def test_pipeline_snapshot_type_validation() -> None:
    with pytest.raises(TypeError):
        build_canonical_option_chain_intelligence(
            snapshot="snapshot",
            quality_result=make_quality(),
        )


def test_pipeline_quality_type_validation() -> None:
    with pytest.raises(TypeError):
        build_canonical_option_chain_intelligence(
            snapshot=canonical_snapshot(),
            quality_result="quality",
        )


def test_pipeline_policy_type_validation() -> None:
    with pytest.raises(TypeError):
        build(
            policy="policy",
        )


def test_quality_snapshot_reference_must_match() -> None:
    with pytest.raises(ValueError):
        build(
            quality_result=make_quality(
                snapshot_id="other-snapshot",
            )
        )


def test_quality_identity_must_match_snapshot() -> None:
    with pytest.raises(ValueError):
        build(
            quality_result=make_quality(
                symbol="SENSEX",
                exchange="BSE",
            )
        )


def test_clock_must_return_timezone_aware_datetime() -> None:
    with pytest.raises(ValueError):
        build(
            clock=lambda: datetime(
                2026,
                1,
                1,
                10,
                0,
            )
        )


@pytest.mark.parametrize(
    ("symbol", "exchange"),
    (
        ("NIFTY", "NSE"),
        ("BANKNIFTY", "NSE"),
        ("FINNIFTY", "NSE"),
        ("SENSEX", "BSE"),
    ),
)
def test_four_market_compatibility(
    symbol: str,
    exchange: str,
) -> None:
    from services.contracts.option_chain_snapshot_v1 import (
        OptionChainSnapshotV1,
    )
    from services.contracts.option_quote_v1 import OptionQuoteV1
    from services.contracts.option_strike_row_v1 import (
        OptionStrikeRowV1,
    )

    def quote(
        quote_id: str,
        strike: float,
        option_type: str,
        open_interest: int,
        volume: int,
    ) -> OptionQuoteV1:
        return OptionQuoteV1(
            option_quote_id=quote_id,
            created_at=CREATED_AT,
            underlying_symbol=symbol,
            exchange=exchange,
            expiry=EXPIRY,
            strike=strike,
            option_type=option_type,
            ltp=100.0,
            bid_price=99.0,
            ask_price=101.0,
            bid_quantity=10,
            ask_quantity=10,
            volume=volume,
            open_interest=open_interest,
            change_in_open_interest=10,
            implied_volatility=15.0,
            underlying_value=22000.0,
            source_timestamp=CREATED_AT,
            is_complete=True,
            provider_name="TEST",
            source_record_id=quote_id,
            blockers=(),
            warnings=(),
            execution_mode="PAPER",
            live_execution_eligible=False,
        )

    row_specs = (
        (21900.0, 100, 300, 100, 150),
        (22000.0, 300, 500, 200, 240),
        (22100.0, 500, 100, 300, 210),
    )

    rows = tuple(
        OptionStrikeRowV1(
            strike_row_id=f"row-{index}",
            underlying_symbol=symbol,
            exchange=exchange,
            expiry=EXPIRY,
            strike=strike,
            call=quote(
                f"row-{index}-call",
                strike,
                "CALL",
                call_oi,
                call_volume,
            ),
            put=quote(
                f"row-{index}-put",
                strike,
                "PUT",
                put_oi,
                put_volume,
            ),
            blockers=(),
            warnings=(),
        )
        for index, (
            strike,
            call_oi,
            put_oi,
            call_volume,
            put_volume,
        ) in enumerate(row_specs, start=1)
    )

    snapshot = OptionChainSnapshotV1(
        option_chain_snapshot_id="snapshot-1",
        created_at=CREATED_AT,
        underlying_symbol=symbol,
        exchange=exchange,
        expiry=EXPIRY,
        underlying_value=22000.0,
        strike_rows=rows,
        strike_count=3,
        complete_pair_count=3,
        call_only_count=0,
        put_only_count=0,
        minimum_strike=21900.0,
        maximum_strike=22100.0,
        source_timestamp=CREATED_AT,
        provider_name="TEST",
        blockers=(),
        warnings=(),
        execution_mode="PAPER",
        live_execution_eligible=False,
    )

    quality = make_quality(
        symbol=symbol,
        exchange=exchange,
    )

    result = build(
        snapshot=snapshot,
        quality_result=quality,
    )

    assert result.underlying_symbol == symbol
    assert result.exchange == exchange
    assert len(result.metrics) == 7

def test_serialized_result_has_no_decision_output() -> None:
    serialized = build().to_dict()

    assert "action" not in serialized
    assert "decision" not in serialized
    assert "option_selection" not in serialized
    assert "ranking" not in serialized
    assert "risk" not in serialized
    assert "execution" not in serialized


def test_serialized_metrics_have_no_execution_output() -> None:
    serialized_metrics = build().to_dict()["metrics"]

    assert all(
        "action" not in metric
        and "decision" not in metric
        and "risk" not in metric
        and "execution" not in metric
        for metric in serialized_metrics
    )


def test_pipeline_is_deterministic_with_fixed_inputs() -> None:
    first = build()
    second = build()

    assert first == second
    assert first.to_dict() == second.to_dict()