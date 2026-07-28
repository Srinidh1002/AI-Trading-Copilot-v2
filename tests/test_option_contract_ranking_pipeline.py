from datetime import date, datetime, timezone

import pytest

from services.contracts.option_chain_intelligence_result_v1 import (
    OptionChainIntelligenceResultV1,
)
from services.contracts.option_chain_metric_v1 import (
    OptionChainMetricV1,
)
from services.contracts.option_contract_universe_v1 import (
    OptionContractUniverseV1,
)
from services.contracts.option_contract_v1 import (
    OptionContractV1,
)
from services.option_contract_ranking.ranking_pipeline import (
    build_canonical_option_contract_ranking,
)


NOW = datetime(2026, 7, 27, tzinfo=timezone.utc)
EXPIRY = date(2026, 7, 30)


def make_metric(
    *,
    signal="BULLISH",
    status="VALID",
    blockers=(),
    warnings=(),
):
    return OptionChainMetricV1(
        metric_name="PCR_OPEN_INTEREST",
        value=1.2 if status.startswith("VALID") else None,
        signal=signal,
        status=status,
        sample_size=10,
        blockers=blockers,
        warnings=warnings,
    )


def make_intelligence(**changes):
    metric = changes.pop(
        "metric",
        make_metric(),
    )
    values = dict(
        option_chain_intelligence_result_id="i1",
        created_at=NOW,
        option_chain_snapshot_id="s1",
        option_chain_quality_result_id="q1",
        underlying_symbol="NIFTY",
        exchange="NSE",
        expiry=EXPIRY,
        metrics=(metric,),
        intelligence_status="READY",
        aggregate_bias="BULLISH",
        aggregate_strength=0.8,
        bullish_metrics=("PCR_OPEN_INTEREST",),
        bearish_metrics=(),
        neutral_metrics=(),
        unavailable_metrics=(),
        valid_metric_count=1,
        unavailable_metric_count=0,
    )
    values.update(changes)
    return OptionChainIntelligenceResultV1(**values)


def make_contract(
    *,
    contract_id="c1",
    option_type="CALL",
    expiry_date=EXPIRY,
    underlying_symbol="NIFTY",
    exchange="NSE",
):
    return OptionContractV1(
        contract_id=contract_id,
        underlying_symbol=underlying_symbol,
        exchange=exchange,
        trading_symbol=f"{contract_id}-SYMBOL",
        option_type=option_type,
        strike=25000,
        expiry_date=expiry_date,
        lot_size=25,
        market_timestamp=NOW,
        last_price=100,
        bid_price=99,
        ask_price=101,
        open_interest=2000,
        volume=1000,
        implied_volatility=18,
    )


def make_universe(
    contracts=None,
    **changes,
):
    values = dict(
        universe_id="u1",
        underlying_symbol="NIFTY",
        exchange="NSE",
        captured_at=NOW,
        spot_price=25000,
        contracts=tuple(
            contracts
            if contracts is not None
            else (make_contract(),)
        ),
        source_name="synthetic",
        trusted=True,
    )
    values.update(changes)
    return OptionContractUniverseV1(**values)


def run_pipeline(
    intelligence=None,
    universe=None,
):
    return build_canonical_option_contract_ranking(
        intelligence_result=(
            intelligence or make_intelligence()
        ),
        universe=universe or make_universe(),
        now=NOW,
        ranking_id_factory=lambda: "r1",
    )


def test_ready_bullish_intelligence_ranks_calls():
    result = run_pipeline()

    assert result.ranking_status == "RANKED"
    assert result.required_option_type == "CALL"
    assert result.selected_candidate.contract.option_type == "CALL"
    assert result.intelligence_result_id == "i1"


def test_ready_bearish_intelligence_ranks_puts():
    intelligence = make_intelligence(
        metric=make_metric(signal="BEARISH"),
        aggregate_bias="BEARISH",
        bullish_metrics=(),
        bearish_metrics=("PCR_OPEN_INTEREST",),
    )
    universe = make_universe(
        (make_contract(option_type="PUT"),)
    )

    result = run_pipeline(intelligence, universe)

    assert result.ranking_status == "RANKED"
    assert result.required_option_type == "PUT"


def test_identity_mismatch_blocks():
    intelligence = make_intelligence(
        underlying_symbol="SENSEX",
        exchange="BSE",
    )

    result = run_pipeline(
        intelligence,
        make_universe(),
    )

    assert result.ranking_status == "BLOCKED"
    assert (
        "OPTION-CHAIN INTELLIGENCE AND CONTRACT "
        "UNIVERSE IDENTITIES DO NOT MATCH"
        in result.blockers
    )


@pytest.mark.parametrize(
    "status",
    [
        "INSUFFICIENT_METRICS",
        "MALFORMED",
        "UNSUPPORTED",
        "FAILED",
    ],
)
def test_blocking_intelligence_statuses_fail_closed(status):
    metric = make_metric(
        signal="UNAVAILABLE",
        status="UNAVAILABLE",
        blockers=("metric unavailable",),
    )
    intelligence = make_intelligence(
        metric=metric,
        intelligence_status=status,
        aggregate_bias="UNAVAILABLE",
        aggregate_strength=0.0,
        bullish_metrics=(),
        unavailable_metrics=("PCR_OPEN_INTEREST",),
        valid_metric_count=0,
        unavailable_metric_count=1,
        blockers=("intelligence blocked",),
    )

    result = run_pipeline(intelligence)

    assert result.ranking_status == "INSUFFICIENT_DATA"
    assert result.selected_candidate is None
    assert (
        "OPTION-CHAIN INTELLIGENCE DOES NOT "
        "PERMIT CONTRACT RANKING"
        in result.blockers
    )


def test_conflicting_intelligence_blocks():
    metric = make_metric(signal="NEUTRAL")
    intelligence = make_intelligence(
        metric=metric,
        intelligence_status="CONFLICTING",
        aggregate_bias="NEUTRAL",
        aggregate_strength=0.5,
        bullish_metrics=(),
        neutral_metrics=("PCR_OPEN_INTEREST",),
        blockers=("conflicting evidence",),
    )

    result = run_pipeline(intelligence)

    assert result.ranking_status == "BLOCKED"
    assert (
        "CONFLICTING OPTION-CHAIN INTELLIGENCE "
        "DOES NOT PERMIT CONTRACT RANKING"
        in result.blockers
    )


@pytest.mark.parametrize(
    "bias,signal,classification",
    [
        ("NEUTRAL", "NEUTRAL", "neutral_metrics"),
        ("MIXED", "BULLISH", "bullish_metrics"),
    ],
)
def test_non_directional_ready_bias_blocks(
    bias,
    signal,
    classification,
):
    metric = make_metric(signal=signal)

    changes = dict(
        metric=metric,
        aggregate_bias=bias,
        bullish_metrics=(),
        bearish_metrics=(),
        neutral_metrics=(),
    )

    changes[classification] = ("PCR_OPEN_INTEREST",)

    if bias == "MIXED":
        second = OptionChainMetricV1(
            metric_name="PCR_VOLUME",
            value=0.8,
            signal="BEARISH",
            status="VALID",
            sample_size=10,
        )
        changes.update(
            metrics=(metric, second),
            bullish_metrics=("PCR_OPEN_INTEREST",),
            bearish_metrics=("PCR_VOLUME",),
            valid_metric_count=2,
        )
        changes.pop("metric")

    intelligence = make_intelligence(**changes)

    result = run_pipeline(intelligence)

    assert result.ranking_status == "BLOCKED"
    assert (
        "DIRECTIONAL OPTION-CHAIN INTELLIGENCE "
        "IS REQUIRED FOR CONTRACT RANKING"
        in result.blockers
    )


def test_expiry_missing_from_universe_blocks():
    intelligence = make_intelligence(
        expiry=date(2026, 8, 6)
    )

    result = run_pipeline(intelligence)

    assert result.ranking_status == "BLOCKED"
    assert (
        "INTELLIGENCE EXPIRY IS NOT PRESENT IN "
        "THE OPTION CONTRACT UNIVERSE"
        in result.blockers
    )


def test_intelligence_expiry_is_applied():
    later = date(2026, 8, 6)
    universe = make_universe(
        (
            make_contract(
                contract_id="wanted",
                expiry_date=EXPIRY,
            ),
            make_contract(
                contract_id="later",
                expiry_date=later,
            ),
        )
    )

    result = run_pipeline(
        make_intelligence(),
        universe,
    )

    assert result.selected_candidate.contract.contract_id == "wanted"
    assert all(
        candidate.contract.expiry_date == EXPIRY
        for candidate in result.ranked_candidates
    )


def test_ready_with_warnings_propagates_warnings():
    intelligence = make_intelligence(
        intelligence_status="READY_WITH_WARNINGS",
        warnings=("partial intelligence",),
    )

    result = run_pipeline(intelligence)

    assert result.ranking_status == "RANKED_WITH_WARNINGS"
    assert "PARTIAL INTELLIGENCE" in result.warnings


def test_intelligence_strength_affects_score():
    strong = run_pipeline(
        make_intelligence(
            option_chain_intelligence_result_id="strong",
            aggregate_strength=1.0,
        )
    )
    weak = run_pipeline(
        make_intelligence(
            option_chain_intelligence_result_id="weak",
            aggregate_strength=0.0,
        )
    )

    assert (
        strong.selected_candidate.total_score
        > weak.selected_candidate.total_score
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("intelligence_result", object()),
        ("universe", object()),
        ("now", datetime(2026, 7, 27)),
        ("policy", object()),
    ],
)
def test_invalid_inputs(field, value):
    kwargs = dict(
        intelligence_result=make_intelligence(),
        universe=make_universe(),
        now=NOW,
    )
    kwargs[field] = value

    with pytest.raises((TypeError, ValueError)):
        build_canonical_option_contract_ranking(**kwargs)