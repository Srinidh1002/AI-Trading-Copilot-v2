"""Tests for deterministic option-chain support/resistance intelligence."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from services.contracts.option_chain_intelligence_policy_v1 import (
    DEFAULT_OPTION_CHAIN_INTELLIGENCE_POLICY,
    OptionChainIntelligencePolicyV1,
)
from services.contracts.option_chain_snapshot_v1 import (
    OptionChainSnapshotV1,
)
from services.contracts.option_quote_v1 import OptionQuoteV1
from services.contracts.option_strike_row_v1 import OptionStrikeRowV1
from services.option_chain_intelligence.support_resistance import (
    SUPPORT_RESISTANCE_METRIC_NAME,
    SupportResistanceAnalysis,
    analyze_support_resistance,
    calculate_support_resistance,
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


def make_quote(
    *,
    quote_id: str,
    strike: float,
    option_type: str,
    open_interest: int | None,
    symbol: str = "NIFTY",
    exchange: str = "NSE",
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
        volume=100,
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


def make_row(
    *,
    row_id: str,
    strike: float,
    call_oi: int | None = 100,
    put_oi: int | None = 100,
    include_call: bool = True,
    include_put: bool = True,
    symbol: str = "NIFTY",
    exchange: str = "NSE",
) -> OptionStrikeRowV1:
    return OptionStrikeRowV1(
        strike_row_id=row_id,
        underlying_symbol=symbol,
        exchange=exchange,
        expiry=EXPIRY,
        strike=strike,
        call=(
            make_quote(
                quote_id=f"{row_id}-call",
                strike=strike,
                option_type="CALL",
                open_interest=call_oi,
                symbol=symbol,
                exchange=exchange,
            )
            if include_call
            else None
        ),
        put=(
            make_quote(
                quote_id=f"{row_id}-put",
                strike=strike,
                option_type="PUT",
                open_interest=put_oi,
                symbol=symbol,
                exchange=exchange,
            )
            if include_put
            else None
        ),
        blockers=(),
        warnings=(),
    )


def make_snapshot(
    rows: tuple[OptionStrikeRowV1, ...],
    *,
    underlying_value: float | None = 22000.0,
    symbol: str = "NIFTY",
    exchange: str = "NSE",
) -> OptionChainSnapshotV1:
    strikes = tuple(row.strike for row in rows)

    return OptionChainSnapshotV1(
        option_chain_snapshot_id="snapshot-1",
        created_at=CREATED_AT,
        underlying_symbol=symbol,
        exchange=exchange,
        expiry=EXPIRY,
        underlying_value=underlying_value,
        strike_rows=rows,
        strike_count=len(rows),
        complete_pair_count=sum(
            row.call is not None and row.put is not None
            for row in rows
        ),
        call_only_count=sum(
            row.call is not None and row.put is None
            for row in rows
        ),
        put_only_count=sum(
            row.call is None and row.put is not None
            for row in rows
        ),
        minimum_strike=min(strikes) if strikes else None,
        maximum_strike=max(strikes) if strikes else None,
        source_timestamp=CREATED_AT,
        provider_name="TEST",
        blockers=(),
        warnings=(),
        execution_mode="PAPER",
        live_execution_eligible=False,
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


def canonical_snapshot() -> OptionChainSnapshotV1:
    return make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=21800.0,
                call_oi=50,
                put_oi=400,
            ),
            make_row(
                row_id="row-2",
                strike=21900.0,
                call_oi=100,
                put_oi=600,
            ),
            make_row(
                row_id="row-3",
                strike=22000.0,
                call_oi=300,
                put_oi=500,
            ),
            make_row(
                row_id="row-4",
                strike=22100.0,
                call_oi=700,
                put_oi=100,
            ),
            make_row(
                row_id="row-5",
                strike=22200.0,
                call_oi=500,
                put_oi=50,
            ),
        )
    )


def test_metric_name_constant() -> None:
    assert (
        SUPPORT_RESISTANCE_METRIC_NAME
        == "SUPPORT_RESISTANCE"
    )


def test_analysis_contract_type() -> None:
    analysis = analyze_support_resistance(
        snapshot=canonical_snapshot()
    )

    assert isinstance(
        analysis,
        SupportResistanceAnalysis,
    )


def test_basic_support_resistance_analysis() -> None:
    analysis = analyze_support_resistance(
        snapshot=canonical_snapshot()
    )

    assert analysis.support_strikes == (
        21800.0,
        21900.0,
        22000.0,
    )
    assert analysis.resistance_strikes == (
        22000.0,
        22100.0,
        22200.0,
    )
    assert dict(analysis.metric.parameters)["strongest_support"] == 21900.0
    assert dict(analysis.metric.parameters)["strongest_resistance"] == 22100.0


def test_basic_metric_calculation() -> None:
    metric = calculate_support_resistance(
        snapshot=canonical_snapshot()
    )

    assert metric.metric_name == "SUPPORT_RESISTANCE"
    assert metric.value == 0.0
    assert metric.signal == "NEUTRAL"
    assert metric.status == "VALID"
    assert metric.sample_size == 10


def test_metric_supporting_strikes_are_combined_and_sorted() -> None:
    metric = calculate_support_resistance(
        snapshot=canonical_snapshot()
    )

    assert metric.supporting_strikes == (
        21800.0,
        21900.0,
        22000.0,
        22100.0,
        22200.0,
    )


def test_support_candidates_are_at_or_below_underlying() -> None:
    analysis = analyze_support_resistance(
        snapshot=canonical_snapshot()
    )

    assert all(
        strike <= 22000.0
        for strike in analysis.support_strikes
    )


def test_resistance_candidates_are_at_or_above_underlying() -> None:
    analysis = analyze_support_resistance(
        snapshot=canonical_snapshot()
    )

    assert all(
        strike >= 22000.0
        for strike in analysis.resistance_strikes
    )


def test_underlying_strike_can_be_both_support_and_resistance() -> None:
    analysis = analyze_support_resistance(
        snapshot=canonical_snapshot()
    )

    assert 22000.0 in analysis.support_strikes
    assert 22000.0 in analysis.resistance_strikes


def test_support_ranking_prefers_higher_put_oi() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=21800.0,
                put_oi=300,
            ),
            make_row(
                row_id="row-2",
                strike=21900.0,
                put_oi=500,
            ),
            make_row(
                row_id="row-3",
                strike=22000.0,
                put_oi=400,
            ),
        )
    )

    analysis = analyze_support_resistance(
        snapshot=snapshot
    )

    assert dict(analysis.metric.parameters)["strongest_support"] == 21900.0


def test_resistance_ranking_prefers_higher_call_oi() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22000.0,
                call_oi=400,
            ),
            make_row(
                row_id="row-2",
                strike=22100.0,
                call_oi=600,
            ),
            make_row(
                row_id="row-3",
                strike=22200.0,
                call_oi=500,
            ),
        )
    )

    analysis = analyze_support_resistance(
        snapshot=snapshot
    )

    assert dict(analysis.metric.parameters)["strongest_resistance"] == 22100.0


def test_support_tie_prefers_nearer_strike() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=21800.0,
                put_oi=500,
            ),
            make_row(
                row_id="row-2",
                strike=21900.0,
                put_oi=500,
            ),
        )
    )

    analysis = analyze_support_resistance(
        snapshot=snapshot
    )

    assert dict(analysis.metric.parameters)["strongest_support"] == 21900.0


def test_resistance_tie_prefers_nearer_strike() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22100.0,
                call_oi=500,
            ),
            make_row(
                row_id="row-2",
                strike=22200.0,
                call_oi=500,
            ),
        )
    )

    analysis = analyze_support_resistance(
        snapshot=snapshot
    )

    assert dict(analysis.metric.parameters)["strongest_resistance"] == 22100.0


def test_top_n_policy_limits_results() -> None:
    policy = make_policy(
        support_resistance_top_n=2
    )

    analysis = analyze_support_resistance(
        snapshot=canonical_snapshot(),
        policy=policy,
    )

    assert len(analysis.support_strikes) == 2
    assert len(analysis.resistance_strikes) == 2


def test_default_top_n_is_three() -> None:
    analysis = analyze_support_resistance(
        snapshot=canonical_snapshot()
    )

    assert len(analysis.support_strikes) == 3
    assert len(analysis.resistance_strikes) == 3


def test_bullish_balance_signal() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=21900.0,
                call_oi=10,
                put_oi=900,
            ),
            make_row(
                row_id="row-2",
                strike=22000.0,
                call_oi=100,
                put_oi=500,
            ),
            make_row(
                row_id="row-3",
                strike=22100.0,
                call_oi=300,
                put_oi=10,
            ),
        )
    )

    metric = calculate_support_resistance(
        snapshot=snapshot
    )

    assert metric.value > 0
    assert metric.signal == "BULLISH"


def test_bearish_balance_signal() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=21900.0,
                call_oi=10,
                put_oi=300,
            ),
            make_row(
                row_id="row-2",
                strike=22000.0,
                call_oi=500,
                put_oi=100,
            ),
            make_row(
                row_id="row-3",
                strike=22100.0,
                call_oi=900,
                put_oi=10,
            ),
        )
    )

    metric = calculate_support_resistance(
        snapshot=snapshot
    )

    assert metric.value < 0
    assert metric.signal == "BEARISH"


def test_equal_balance_is_neutral() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=21900.0,
                call_oi=10,
                put_oi=500,
            ),
            make_row(
                row_id="row-2",
                strike=22100.0,
                call_oi=500,
                put_oi=10,
            ),
        )
    )

    metric = calculate_support_resistance(
        snapshot=snapshot
    )

    assert metric.value == 0.0
    assert metric.signal == "NEUTRAL"


def test_missing_underlying_is_unavailable() -> None:
    snapshot = make_snapshot(
        canonical_snapshot().strike_rows,
        underlying_value=None,
    )

    metric = calculate_support_resistance(
        snapshot=snapshot
    )

    assert metric.value is None
    assert metric.signal == "UNAVAILABLE"
    assert metric.status == "UNAVAILABLE"
    assert metric.blockers == (
        "underlying value is unavailable",
    )


def test_empty_chain_is_unavailable() -> None:
    metric = calculate_support_resistance(
        snapshot=make_snapshot(())
    )

    assert metric.status == "UNAVAILABLE"
    assert metric.sample_size == 0


def test_no_support_candidates_returns_bearish_warning() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=22100.0,
                call_oi=500,
                put_oi=100,
            ),
            make_row(
                row_id="row-2",
                strike=22200.0,
                call_oi=500,
                put_oi=100,
            ),
        )
    )

    metric = calculate_support_resistance(
        snapshot=snapshot
    )

    assert metric.status == "VALID_WITH_WARNINGS"
    assert metric.value == -1.0
    assert metric.signal == "BEARISH"
    assert metric.warnings == (
        "no eligible support strike was available",
    )


def test_no_resistance_candidates_returns_bullish_warning() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=21800.0,
                call_oi=100,
                put_oi=500,
            ),
            make_row(
                row_id="row-2",
                strike=21900.0,
                call_oi=100,
                put_oi=500,
            ),
        )
    )

    metric = calculate_support_resistance(
        snapshot=snapshot
    )

    assert metric.status == "VALID_WITH_WARNINGS"
    assert metric.value == 1.0
    assert metric.signal == "BULLISH"
    assert metric.warnings == (
        "no eligible resistance strike was available",
    )


def test_missing_put_oi_is_ignored_for_support() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=21900.0,
                put_oi=None,
            ),
            make_row(
                row_id="row-2",
                strike=22000.0,
                put_oi=500,
                call_oi=500,
            ),
            make_row(
                row_id="row-3",
                strike=22100.0,
                call_oi=500,
            ),
        )
    )

    analysis = analyze_support_resistance(
        snapshot=snapshot
    )

    assert 21900.0 not in analysis.support_strikes


def test_missing_call_oi_is_ignored_for_resistance() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=21900.0,
                put_oi=500,
            ),
            make_row(
                row_id="row-2",
                strike=22000.0,
                put_oi=500,
                call_oi=500,
            ),
            make_row(
                row_id="row-3",
                strike=22100.0,
                call_oi=None,
            ),
        )
    )

    analysis = analyze_support_resistance(
        snapshot=snapshot
    )

    assert 22100.0 not in analysis.resistance_strikes


def test_zero_open_interest_candidates_are_retained() -> None:
    snapshot = make_snapshot(
        (
            make_row(
                row_id="row-1",
                strike=21900.0,
                put_oi=0,
            ),
            make_row(
                row_id="row-2",
                strike=22000.0,
                call_oi=0,
                put_oi=100,
            ),
            make_row(
                row_id="row-3",
                strike=22100.0,
                call_oi=100,
            ),
        )
    )

    analysis = analyze_support_resistance(
        snapshot=snapshot
    )

    assert 21900.0 in analysis.support_strikes
    assert 22000.0 in analysis.resistance_strikes


def test_analysis_parameters_reconcile() -> None:
    analysis = analyze_support_resistance(
        snapshot=canonical_snapshot()
    )

    parameters = dict(analysis.metric.parameters)

    assert parameters["underlying_value"] == 22000.0
    assert parameters["top_n"] == 3
    assert parameters["support_open_interest"] == 1500
    assert parameters["resistance_open_interest"] == 1500


def test_metric_parameters_reconcile() -> None:
    metric = calculate_support_resistance(
        snapshot=canonical_snapshot()
    )

    parameters = dict(metric.parameters)

    assert parameters["underlying_value"] == 22000.0
    assert parameters["top_n"] == 3
    assert parameters["support_open_interest"] == 1500
    assert parameters["resistance_open_interest"] == 1500
    assert parameters["strongest_support"] == 21900.0
    assert parameters["strongest_resistance"] == 22100.0


def test_snapshot_type_validation() -> None:
    with pytest.raises(TypeError):
        analyze_support_resistance(
            snapshot="snapshot"
        )

    with pytest.raises(TypeError):
        calculate_support_resistance(
            snapshot="snapshot"
        )


def test_policy_type_validation() -> None:
    snapshot = canonical_snapshot()

    with pytest.raises(TypeError):
        analyze_support_resistance(
            snapshot=snapshot,
            policy="policy",
        )

    with pytest.raises(TypeError):
        calculate_support_resistance(
            snapshot=snapshot,
            policy="policy",
        )


def test_snapshot_is_not_mutated() -> None:
    snapshot = canonical_snapshot()
    before = snapshot.to_dict()

    analyze_support_resistance(snapshot=snapshot)
    calculate_support_resistance(snapshot=snapshot)

    assert snapshot.to_dict() == before


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
    rows = (
        make_row(
            row_id="row-1",
            strike=21900.0,
            call_oi=100,
            put_oi=500,
            symbol=symbol,
            exchange=exchange,
        ),
        make_row(
            row_id="row-2",
            strike=22000.0,
            call_oi=300,
            put_oi=500,
            symbol=symbol,
            exchange=exchange,
        ),
        make_row(
            row_id="row-3",
            strike=22100.0,
            call_oi=700,
            put_oi=100,
            symbol=symbol,
            exchange=exchange,
        ),
    )

    snapshot = make_snapshot(
        rows,
        symbol=symbol,
        exchange=exchange,
    )

    metric = calculate_support_resistance(
        snapshot=snapshot
    )

    assert metric.status == "VALID"
    assert metric.supporting_strikes == (
        21900.0,
        22000.0,
        22100.0,
    )


def test_no_decision_or_execution_output() -> None:
    serialized = calculate_support_resistance(
        snapshot=canonical_snapshot()
    ).to_dict()

    assert "action" not in serialized
    assert "decision" not in serialized
    assert "ranking" not in serialized
    assert "risk" not in serialized
    assert "execution" not in serialized