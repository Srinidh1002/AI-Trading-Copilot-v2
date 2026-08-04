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
from services.contracts.timeframe_technical_evidence_v1 import (
    TimeframeTechnicalEvidenceV1,
)
import services.contracts.timeframe_technical_evidence_v1 as technical_evidence_contract
from services.trade_opportunity.integration import (
    build_canonical_trade_opportunity,
)


NOW = datetime(2026, 7, 27, 10, 0, tzinfo=timezone.utc)
EXPIRY = date(2026, 7, 30)


def make_evidence(symbol, exchange, bias):
    categories = tuple(
        sorted(technical_evidence_contract._CATEGORIES)
    )

    return TimeframeTechnicalEvidenceV1(
        timeframe_technical_evidence_id=(
            f"technical-evidence-{symbol}"
        ),
        created_at=NOW,
        underlying_symbol=symbol,
        exchange=exchange,
        timeframe="5m",
        timeframe_evidence_id=(
            f"timeframe-evidence-{symbol}"
        ),
        indicators=(),
        category_biases=tuple(
            (
                category,
                (
                    bias
                    if (
                        "TREND" in category.upper()
                        or "MOMENTUM" in category.upper()
                    )
                    else "NEUTRAL"
                ),
            )
            for category in categories
        ),
        category_strengths=tuple(
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
        ),
        trend_bias=bias,
        momentum_bias=bias,
        trend_strength=0.8,
        momentum_strength=0.8,
    )


@pytest.mark.parametrize(
    "symbol,exchange,action,bias,option_type,strike",
    [
        ("NIFTY", "NSE", "BUY", "BULLISH", "CALL", 25000),
        ("NIFTY", "NSE", "SELL", "BEARISH", "PUT", 25000),
        ("BANKNIFTY", "NSE", "BUY", "BULLISH", "CALL", 52000),
        ("BANKNIFTY", "NSE", "SELL", "BEARISH", "PUT", 52000),
        ("FINNIFTY", "NSE", "BUY", "BULLISH", "CALL", 24000),
        ("FINNIFTY", "NSE", "SELL", "BEARISH", "PUT", 24000),
        ("SENSEX", "BSE", "BUY", "BULLISH", "CALL", 82000),
        ("SENSEX", "BSE", "SELL", "BEARISH", "PUT", 82000),
    ],
)
def test_four_index_trade_opportunity(
    symbol,
    exchange,
    action,
    bias,
    option_type,
    strike,
):
    decision = FinalDecisionV1(
        snapshot_id=f"snapshot-{symbol}",
        decision_id=f"decision-{symbol}-{action}",
        symbol=symbol,
        exchange=exchange,
        instrument_type="INDEX_OPTION",
        created_at=NOW,
        market_timestamp=NOW,
        action=action,
        authorization_status="ANALYSIS_ONLY",
        execution_status="NOT_REQUESTED",
        direction=bias,
        confidence=80,
    )

    technical = TechnicalIntelligenceResultV1(
        technical_intelligence_result_id=f"technical-{symbol}",
        created_at=NOW,
        multi_timeframe_snapshot_id=f"mtf-{symbol}",
        multi_timeframe_quality_result_id=f"mtfq-{symbol}",
        underlying_symbol=symbol,
        exchange=exchange,
        timeframe_evidence=(
            make_evidence(symbol, exchange, bias),
        ),
        status="READY",
        aggregate_bias=bias,
        aggregate_strength=0.8,
        required_timeframes=("5m",),
        bullish_timeframes=(
            ("5m",)
            if bias == "BULLISH"
            else ()
        ),
        bearish_timeframes=(
            ("5m",)
            if bias == "BEARISH"
            else ()
        ),
        neutral_timeframes=(),
        unavailable_timeframes=(),
        aligned_timeframes=("5m",),
        conflicting_timeframes=(),
    )

    metric = OptionChainMetricV1(
        metric_name="PCR_OPEN_INTEREST",
        value=1.2,
        signal=bias,
        status="VALID",
        sample_size=10,
    )

    option_chain = OptionChainIntelligenceResultV1(
        option_chain_intelligence_result_id=(
            f"chain-intelligence-{symbol}"
        ),
        created_at=NOW,
        option_chain_snapshot_id=f"chain-{symbol}",
        option_chain_quality_result_id=(
            f"chain-quality-{symbol}"
        ),
        underlying_symbol=symbol,
        exchange=exchange,
        expiry=EXPIRY,
        metrics=(metric,),
        intelligence_status="READY",
        aggregate_bias=bias,
        aggregate_strength=0.75,
        bullish_metrics=(
            ("PCR_OPEN_INTEREST",)
            if bias == "BULLISH"
            else ()
        ),
        bearish_metrics=(
            ("PCR_OPEN_INTEREST",)
            if bias == "BEARISH"
            else ()
        ),
        neutral_metrics=(),
        unavailable_metrics=(),
        valid_metric_count=1,
        unavailable_metric_count=0,
    )

    contract = OptionContractV1(
        contract_id=f"{symbol}-{option_type}",
        underlying_symbol=symbol,
        exchange=exchange,
        trading_symbol=f"{symbol}-{strike}-{option_type}",
        option_type=option_type,
        strike=strike,
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

    candidate = OptionContractCandidateV1(
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

    ranking = OptionContractRankingResultV1(
        ranking_id=f"ranking-{symbol}-{action}",
        ranked_at=NOW,
        universe_id=f"universe-{symbol}",
        intelligence_result_id=(
            option_chain.option_chain_intelligence_result_id
        ),
        underlying_symbol=symbol,
        exchange=exchange,
        directional_bias=bias,
        required_option_type=option_type,
        ranking_status="RANKED",
        ranked_candidates=(candidate,),
    )

    session = MarketSessionValidationV1(
        validation_id=f"session-{symbol}",
        evaluated_at=NOW,
        market_timestamp=NOW,
        symbol=symbol,
        exchange=exchange,
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

    result = build_canonical_trade_opportunity(
        decision=decision,
        technical_intelligence=technical,
        option_chain_intelligence=option_chain,
        contract_ranking=ranking,
        session_validation=session,
        clock=lambda: NOW,
        opportunity_id_factory=(
            lambda: f"opportunity-{symbol}-{action}"
        ),
    )

    assert result.opportunity_status == "READY"
    assert result.underlying_symbol == symbol
    assert result.exchange == exchange
    assert result.action == action
    assert result.directional_bias == bias
    assert result.option_type == option_type
    assert result.contract_id == f"{symbol}-{option_type}"
    assert result.opportunity_ready is True