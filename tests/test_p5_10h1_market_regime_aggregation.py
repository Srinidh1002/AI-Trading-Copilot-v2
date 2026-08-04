"""Focused deterministic aggregation coverage for P5-10H1."""
from datetime import datetime, timezone

from services.contracts.market_regime_input_v1 import MarketRegimeInputV1
from services.contracts.market_regime_policy_v1 import MarketRegimePolicyV1
from services.contracts.market_session_validation_v1 import MarketSessionValidationV1
from services.contracts.technical_regime_component_result_v1 import TechnicalRegimeComponentResultV1
from services.market_regime.aggregate import aggregate_market_regime


TS = datetime(2026, 1, 1, 9, 15, tzinfo=timezone.utc)


def _session(analysis_allowed=True, entries_allowed=True):
    return MarketSessionValidationV1(
        validation_id="session", evaluated_at=TS, market_timestamp=TS, symbol="NIFTY", exchange="NSE",
        timezone="UTC", trading_date=TS.date(), session_state="REGULAR", session_phase="REGULAR_TRADING",
        trading_day_status="TRADING_DAY", analysis_allowed=analysis_allowed,
        paper_execution_allowed=entries_allowed,
    )


def _technical(direction="POSITIVE", strength=0.9, confidence=0.9):
    return TechnicalRegimeComponentResultV1(
        "technical", TS, "NIFTY", "NSE", None, "READY", direction, "UPTREND", "NORMAL",
        strength, confidence, "CONFIRMING", 1, 0,
    )


def _input(technical="DEFAULT", session=None):
    return MarketRegimeInputV1(
        "input-1", TS, "NIFTY", "NSE", market_session_validation=session or _session(),
        technical_regime_component=_technical() if technical == "DEFAULT" else technical,
    )


def test_strong_bullish_is_deterministic_and_preserves_provenance():
    result = aggregate_market_regime(_input())
    assert result.primary_regime == "STRONG_BULLISH"
    assert result.market_regime_result_id == "market-regime:input-1"
    assert result.created_at == TS
    assert result.to_dict() == aggregate_market_regime(_input()).to_dict()
    assert result.technical_regime_component is not None
    assert result.execution_mode == "PAPER" and result.live_execution_eligible is False


def test_required_failure_and_analysis_disallowed_fail_closed():
    failed = aggregate_market_regime(_input(technical=None))
    blocked = aggregate_market_regime(_input(session=_session(False, False)))
    assert failed.primary_regime == blocked.primary_regime == "BLOCKED"
    assert failed.entry_suitability == blocked.entry_suitability == "BLOCKED"


def test_non_unit_outer_weights_remain_supported():
    policy = MarketRegimePolicyV1(technical_weight=2, broader_market_weight=1, external_context_weight=1)
    result = aggregate_market_regime(_input(), policy)
    assert result.primary_regime == "STRONG_BULLISH"
    assert result.regime_strength == 0.9
