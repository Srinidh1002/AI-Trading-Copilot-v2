from datetime import date, datetime, timezone

import pytest

from services.contracts.final_decision_v1 import (
    FinalDecisionV1,
)
from services.contracts.market_session_validation_v1 import (
    MarketSessionValidationV1,
)
from services.contracts.option_chain_intelligence_result_v1 import (
    OptionChainIntelligenceResultV1,
)
from services.contracts.option_chain_metric_v1 import (
    OptionChainMetricV1,
)
from services.contracts.option_contract_candidate_v1 import (
    OptionContractCandidateV1,
)
from services.contracts.option_contract_ranking_result_v1 import (
    OptionContractRankingResultV1,
)
from services.contracts.option_contract_v1 import (
    OptionContractV1,
)
from services.contracts.technical_intelligence_result_v1 import (
    TechnicalIntelligenceResultV1,
)
import services.contracts.timeframe_technical_evidence_v1 as timeframe_technical_evidence_contract
from services.contracts.timeframe_technical_evidence_v1 import (
    TimeframeTechnicalEvidenceV1,
)
from services.trade_opportunity.integration import (
    build_canonical_trade_opportunity,
)


NOW = datetime(2026, 7, 27, 10, 0, tzinfo=timezone.utc)
EXPIRY = date(2026, 7, 30)


def make_decision(**changes):
    values = dict(
        snapshot_id="snapshot-1",
        decision_id="decision-1",
        symbol="NIFTY",
        exchange="NSE",
        instrument_type="INDEX_OPTION",
        created_at=NOW,
        market_timestamp=NOW,
        action="BUY",
        authorization_status="ANALYSIS_ONLY",
        execution_status="NOT_REQUESTED",
        direction="BULLISH",
        confidence=80,
    )
    values.update(changes)
    return FinalDecisionV1(**values)


def make_evidence(
    *,
    timeframe="5m",
    trend_bias="BULLISH",
    momentum_bias="BULLISH",
):
    categories = tuple(
        sorted(
            timeframe_technical_evidence_contract._CATEGORIES
        )
    )

    category_biases = tuple(
        (
            category,
            (
                trend_bias
                if "TREND" in category.upper()
                else momentum_bias
                if "MOMENTUM" in category.upper()
                else "NEUTRAL"
            ),
        )
        for category in categories
    )

    category_strengths = tuple(
        (
            category,
            (
                0.8
                if (
                    "TREND" in category.upper()
                    or "MOMENTUM" in category.upper()
                )
                else 0.0
            ),
        )
        for category in categories
    )


    return TimeframeTechnicalEvidenceV1(
        timeframe_technical_evidence_id=(
            f"technical-evidence-{timeframe}"
        ),
        created_at=NOW,
        underlying_symbol="NIFTY",
        exchange="NSE",
        timeframe=timeframe,
        timeframe_evidence_id=(
            f"timeframe-evidence-{timeframe}"
        ),
        indicators=(),
        category_biases=category_biases,
        category_strengths=category_strengths,
        trend_bias=trend_bias,
        momentum_bias=momentum_bias,
        trend_strength=0.8,
        momentum_strength=0.8,
        bullish_evidence_count=0,
        bearish_evidence_count=0,
        neutral_evidence_count=0,
        valid_indicator_count=0,
        unavailable_indicator_count=0,
    )


def make_technical(**changes):
    evidence = changes.pop(
        "timeframe_evidence",
        (make_evidence(),),
    )

    values = dict(
        technical_intelligence_result_id="technical-1",
        created_at=NOW,
        multi_timeframe_snapshot_id="mtf-1",
        multi_timeframe_quality_result_id="mtfq-1",
        underlying_symbol="NIFTY",
        exchange="NSE",
        timeframe_evidence=evidence,
        status="READY",
        aggregate_bias="BULLISH",
        aggregate_strength=0.8,
        required_timeframes=("5m",),
        bullish_timeframes=("5m",),
        bearish_timeframes=(),
        neutral_timeframes=(),
        unavailable_timeframes=(),
        aligned_timeframes=("5m",),
        conflicting_timeframes=(),
    )
    values.update(changes)

    return TechnicalIntelligenceResultV1(**values)


def make_metric(
    *,
    signal="BULLISH",
    status="VALID",
):
    return OptionChainMetricV1(
        metric_name="PCR_OPEN_INTEREST",
        value=(
            1.2
            if status.startswith("VALID")
            else None
        ),
        signal=signal,
        status=status,
        sample_size=10,
        blockers=(
            ()
            if status.startswith("VALID")
            else ("metric unavailable",)
        ),
    )


def make_option_chain(**changes):
    metric = changes.pop(
        "metric",
        make_metric(),
    )

    values = dict(
        option_chain_intelligence_result_id="option-chain-1",
        created_at=NOW,
        option_chain_snapshot_id="chain-1",
        option_chain_quality_result_id="chain-quality-1",
        underlying_symbol="NIFTY",
        exchange="NSE",
        expiry=EXPIRY,
        metrics=(metric,),
        intelligence_status="READY",
        aggregate_bias="BULLISH",
        aggregate_strength=0.75,
        bullish_metrics=("PCR_OPEN_INTEREST",),
        bearish_metrics=(),
        neutral_metrics=(),
        unavailable_metrics=(),
        valid_metric_count=1,
        unavailable_metric_count=0,
    )
    values.update(changes)

    return OptionChainIntelligenceResultV1(**values)


def make_contract(**changes):
    values = dict(
        contract_id="contract-1",
        underlying_symbol="NIFTY",
        exchange="NSE",
        trading_symbol="NIFTY-25000-CALL",
        option_type="CALL",
        strike=25000,
        expiry_date=EXPIRY,
        lot_size=25,
        market_timestamp=NOW,
        last_price=100,
        bid_price=99,
        ask_price=101,
        open_interest=2000,
        volume=1000,
        implied_volatility=18,
    )
    values.update(changes)

    return OptionContractV1(**values)


def make_candidate(**changes):
    contract = changes.pop(
        "contract",
        make_contract(),
    )

    values = dict(
        contract=contract,
        candidate_status="ELIGIBLE",
        moneyness="ATM",
        strike_distance_percent=0,
        spread_percent=2,
        liquidity_score=0.8,
        proximity_score=1.0,
        open_interest_score=0.8,
        volume_score=0.8,
        spread_score=0.6,
        implied_volatility_score=0.5,
        intelligence_alignment_score=0.75,
        total_score=0.82,
    )
    values.update(changes)

    return OptionContractCandidateV1(**values)


def make_ranking(**changes):
    candidate = changes.pop(
        "candidate",
        make_candidate(),
    )

    values = dict(
        ranking_id="ranking-1",
        ranked_at=NOW,
        universe_id="universe-1",
        intelligence_result_id="option-chain-1",
        underlying_symbol="NIFTY",
        exchange="NSE",
        directional_bias="BULLISH",
        required_option_type="CALL",
        ranking_status="RANKED",
        ranked_candidates=(candidate,),
    )
    values.update(changes)

    return OptionContractRankingResultV1(**values)


def make_session(**changes):
    values = dict(
        validation_id="session-1",
        evaluated_at=NOW,
        market_timestamp=NOW,
        symbol="NIFTY",
        exchange="NSE",
        timezone="Asia/Kolkata",
        trading_date=NOW.date(),
        session_state="REGULAR",
        session_phase="REGULAR_TRADING",
        trading_day_status="TRADING_DAY",
        is_trading_day=True,
        regular_session_open=True,
        analysis_allowed=True,
        paper_preparation_allowed=True,
        paper_execution_allowed=False,
    )
    values.update(changes)

    return MarketSessionValidationV1(**values)


def run_integration(**changes):
    return build_canonical_trade_opportunity(
        decision=changes.pop(
            "decision",
            make_decision(),
        ),
        technical_intelligence=changes.pop(
            "technical_intelligence",
            make_technical(),
        ),
        option_chain_intelligence=changes.pop(
            "option_chain_intelligence",
            make_option_chain(),
        ),
        contract_ranking=changes.pop(
            "contract_ranking",
            make_ranking(),
        ),
        session_validation=changes.pop(
            "session_validation",
            make_session(),
        ),
        clock=changes.pop(
            "clock",
            lambda: NOW,
        ),
        opportunity_id_factory=changes.pop(
            "opportunity_id_factory",
            lambda: "opportunity-1",
        ),
        **changes,
    )


def test_aligned_buy_opportunity_is_ready():
    result = run_integration()

    assert result.opportunity_status == "READY"
    assert result.opportunity_ready is True
    assert result.action == "BUY"
    assert result.directional_bias == "BULLISH"
    assert result.option_type == "CALL"
    assert result.contract_id == "contract-1"
    assert result.reference_option_price == 100
    assert result.opportunity_score > 0.6


def test_aligned_sell_opportunity_is_ready():
    decision = make_decision(
        action="SELL",
        direction="BEARISH",
    )

    technical = make_technical(
        aggregate_bias="BEARISH",
        bullish_timeframes=(),
        bearish_timeframes=("5m",),
    )

    option_chain = make_option_chain(
        metric=make_metric(signal="BEARISH"),
        aggregate_bias="BEARISH",
        bullish_metrics=(),
        bearish_metrics=("PCR_OPEN_INTEREST",),
    )

    candidate = make_candidate(
        contract=make_contract(
            option_type="PUT",
            trading_symbol="NIFTY-25000-PUT",
        )
    )

    ranking = make_ranking(
        candidate=candidate,
        directional_bias="BEARISH",
        required_option_type="PUT",
    )

    result = run_integration(
        decision=decision,
        technical_intelligence=technical,
        option_chain_intelligence=option_chain,
        contract_ranking=ranking,
    )

    assert result.opportunity_status == "READY"
    assert result.action == "SELL"
    assert result.option_type == "PUT"


@pytest.mark.parametrize(
    "action",
    ["WAIT", "HOLD"],
)
def test_non_directional_decision_returns_no_action(action):
    result = run_integration(
        decision=make_decision(
            action=action,
            direction="NEUTRAL",
        )
    )

    assert result.opportunity_status == "NO_ACTION"
    assert result.opportunity_ready is False
    assert result.action == action
    assert result.contract_id is None


def test_identity_mismatch_blocks():
    session = make_session(
        symbol="SENSEX",
        exchange="BSE",
    )

    result = run_integration(
        session_validation=session,
    )

    assert result.opportunity_status == "BLOCKED"
    assert (
        "SOURCE MARKET IDENTITIES DO NOT MATCH"
        in result.blockers
    )


def test_blocked_decision_blocks():
    result = run_integration(
        decision=make_decision(
            authorization_status="BLOCKED",
        )
    )

    assert result.opportunity_status == "BLOCKED"
    assert "FINAL DECISION IS BLOCKED" in result.blockers


def test_closed_session_blocks():
    result = run_integration(
        session_validation=make_session(
            paper_preparation_allowed=False,
        )
    )

    assert result.opportunity_status == "BLOCKED"
    assert (
        "MARKET SESSION DOES NOT ALLOW PAPER PREPARATION"
        in result.blockers
    )


def test_non_ready_technical_intelligence_blocks():
    technical = make_technical(
        status="STALE",
        aggregate_bias="UNAVAILABLE",
        aggregate_strength=0,
        blockers=("technical stale",),
        bullish_timeframes=(),
        unavailable_timeframes=("5m",),
        aligned_timeframes=(),
    )

    result = run_integration(
        technical_intelligence=technical,
    )

    assert result.opportunity_status == "CONFLICTING"
    assert (
        "TECHNICAL INTELLIGENCE IS NOT READY"
        in result.blockers
    )


def test_non_ready_option_chain_intelligence_blocks():
    metric = make_metric(
        signal="UNAVAILABLE",
        status="UNAVAILABLE",
    )

    option_chain = make_option_chain(
        metric=metric,
        intelligence_status="INSUFFICIENT_METRICS",
        aggregate_bias="UNAVAILABLE",
        aggregate_strength=0,
        bullish_metrics=(),
        unavailable_metrics=("PCR_OPEN_INTEREST",),
        valid_metric_count=0,
        unavailable_metric_count=1,
        blockers=("chain unavailable",),
    )

    result = run_integration(
        option_chain_intelligence=option_chain,
    )

    assert result.opportunity_status == "CONFLICTING"
    assert (
        "OPTION-CHAIN INTELLIGENCE IS NOT READY"
        in result.blockers
    )


def test_non_ready_ranking_blocks():
    ranking = make_ranking(
        ranking_status="BLOCKED",
        ranked_candidates=(),
        blockers=("ranking blocked",),
    )

    result = run_integration(
        contract_ranking=ranking,
    )

    assert result.opportunity_status == "BLOCKED"
    assert (
        "OPTION CONTRACT RANKING IS NOT READY"
        in result.blockers
    )
    assert (
        "RANKED OPTION CONTRACT IS REQUIRED"
        in result.blockers
    )


def test_directional_conflict_returns_conflicting():
    technical = make_technical(
        aggregate_bias="BEARISH",
        bullish_timeframes=(),
        bearish_timeframes=("5m",),
    )

    result = run_integration(
        technical_intelligence=technical,
    )

    assert result.opportunity_status == "CONFLICTING"
    assert (
        "TECHNICAL INTELLIGENCE DOES NOT MATCH DECISION"
        in result.contradictions
    )
    assert (
        "DIRECTIONAL EVIDENCE IS CONFLICTING"
        in result.blockers
    )


@pytest.mark.parametrize(
    "field,value,expected_blocker",
    [
        (
            "technical_intelligence",
            make_technical(
                aggregate_strength=0.2,
            ),
            "TECHNICAL STRENGTH IS BELOW POLICY MINIMUM",
        ),
        (
            "option_chain_intelligence",
            make_option_chain(
                aggregate_strength=0.2,
            ),
            "OPTION-CHAIN STRENGTH IS BELOW POLICY MINIMUM",
        ),
        (
            "contract_ranking",
            make_ranking(
                candidate=make_candidate(
                    total_score=0.2,
                )
            ),
            "CONTRACT RANKING SCORE IS BELOW POLICY MINIMUM",
        ),
        (
            "decision",
            make_decision(
                confidence=20,
            ),
            "DECISION CONFIDENCE IS BELOW POLICY MINIMUM",
        ),
    ],
)
def test_threshold_failures_block(
    field,
    value,
    expected_blocker,
):
    result = run_integration(
        **{field: value}
    )

    assert result.opportunity_status == "BLOCKED"
    assert expected_blocker in result.blockers


def test_decision_confidence_supports_zero_to_one_scale():
    result = run_integration(
        decision=make_decision(
            confidence=0.8,
        )
    )

    assert result.decision_confidence == 0.8


def test_warnings_produce_ready_with_warnings():
    result = run_integration(
        decision=make_decision(
            warnings=("decision warning",),
        )
    )

    assert (
        result.opportunity_status
        == "READY_WITH_WARNINGS"
    )
    assert "DECISION WARNING" in result.warnings


def test_source_staleness_blocks():
    old = datetime(
        2026,
        7,
        27,
        9,
        54,
        tzinfo=timezone.utc,
    )

    technical = make_technical(
        created_at=old,
    )

    result = run_integration(
        technical_intelligence=technical,
    )

    assert result.opportunity_status == "BLOCKED"
    assert (
        "INTEGRATION SOURCE IS STALE"
        in result.blockers
    )


def test_future_source_blocks():
    future = datetime(
        2026,
        7,
        27,
        10,
        0,
        6,
        tzinfo=timezone.utc,
    )

    ranking = make_ranking(
        ranked_at=future,
    )

    result = run_integration(
        contract_ranking=ranking,
    )

    assert result.opportunity_status == "BLOCKED"
    assert (
        "INTEGRATION SOURCE TIMESTAMP IS IN THE FUTURE"
        in result.blockers
    )


def test_mid_price_is_preferred():
    result = run_integration(
        contract_ranking=make_ranking(
            candidate=make_candidate(
                contract=make_contract(
                    bid_price=90,
                    ask_price=110,
                    last_price=99,
                )
            )
        )
    )

    assert result.reference_option_price == 100


def test_ask_then_last_then_bid_price_fallback():
    ask_result = run_integration(
        contract_ranking=make_ranking(
            candidate=make_candidate(
                contract=make_contract(
                    bid_price=None,
                    ask_price=110,
                    last_price=99,
                )
            )
        )
    )

    last_result = run_integration(
        contract_ranking=make_ranking(
            candidate=make_candidate(
                contract=make_contract(
                    bid_price=None,
                    ask_price=None,
                    last_price=99,
                )
            )
        )
    )

    bid_result = run_integration(
        contract_ranking=make_ranking(
            candidate=make_candidate(
                contract=make_contract(
                    bid_price=90,
                    ask_price=None,
                    last_price=None,
                )
            )
        )
    )

    assert ask_result.reference_option_price == 110
    assert last_result.reference_option_price == 99
    assert bid_result.reference_option_price == 90


def test_result_is_deterministic():
    first = run_integration()
    second = run_integration()

    assert (
        first.semantic_dict()
        == second.semantic_dict()
    )


@pytest.mark.parametrize(
    "field",
    [
        "decision",
        "technical_intelligence",
        "option_chain_intelligence",
        "contract_ranking",
        "session_validation",
        "policy",
    ],
)
def test_input_types_are_enforced(field):
    kwargs = dict(
        decision=make_decision(),
        technical_intelligence=make_technical(),
        option_chain_intelligence=make_option_chain(),
        contract_ranking=make_ranking(),
        session_validation=make_session(),
        clock=lambda: NOW,
    )
    kwargs[field] = object()

    with pytest.raises(TypeError):
        build_canonical_trade_opportunity(
            **kwargs
        )


def test_clock_must_return_timezone_aware_datetime():
    with pytest.raises(ValueError):
        run_integration(
            clock=lambda: datetime(
                2026,
                7,
                27,
                10,
                0,
            )
        )