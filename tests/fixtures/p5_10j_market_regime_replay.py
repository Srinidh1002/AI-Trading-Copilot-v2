"""Fixed, provider-free P5-10J market-regime replay fixtures."""
from datetime import datetime, timedelta, timezone

from services.contracts.broader_market_regime_component_result_v1 import BroaderMarketRegimeComponentResultV1
from services.contracts.external_context_regime_component_result_v1 import ExternalContextRegimeComponentResultV1
from services.contracts.market_regime_input_v1 import MarketRegimeInputV1
from services.contracts.market_session_validation_v1 import MarketSessionValidationV1
from services.contracts.technical_regime_component_result_v1 import TechnicalRegimeComponentResultV1


TS = datetime(2026, 1, 1, 9, 15, tzinfo=timezone.utc)
IDENTITIES = (("NIFTY", "NSE"), ("BANKNIFTY", "NSE"), ("FINNIFTY", "NSE"), ("SENSEX", "BSE"))


def session(identity, *, analysis=True, entries=True, timestamp=TS):
    return MarketSessionValidationV1(
        validation_id=f"session-{identity[0]}", evaluated_at=timestamp, market_timestamp=timestamp,
        symbol=identity[0], exchange=identity[1], timezone="UTC", trading_date=timestamp.date(),
        session_state="REGULAR", session_phase="REGULAR_TRADING", trading_day_status="TRADING_DAY",
        analysis_allowed=analysis, paper_execution_allowed=entries,
    )


def technical(identity, *, direction="POSITIVE", strength=0.9, confidence=0.9, confirmation="CONFIRMING", timestamp=TS):
    return TechnicalRegimeComponentResultV1(
        f"technical-{identity[0]}", timestamp, identity[0], identity[1], None, "READY", direction,
        "UPTREND", "NORMAL", strength, confidence, confirmation, 1, 0,
    )


def broader(identity, *, direction="FLAT", volatility="NORMAL", breadth="FLAT", confirmation="NOT_CONFIRMING", timestamp=TS):
    return BroaderMarketRegimeComponentResultV1(
        f"broader-{identity[0]}", timestamp, identity[0], identity[1], None, "READY", direction,
        breadth, "UNAVAILABLE", volatility, 0.5, 0.5, confirmation, 1, 0,
    )


def external(identity, *, direction="FLAT", event="NONE", restriction="OPEN", timestamp=TS):
    return ExternalContextRegimeComponentResultV1(
        f"external-{identity[0]}", timestamp, identity[0], identity[1], None, "READY", direction,
        "UNAVAILABLE", "UNAVAILABLE", event, restriction, 0.5, 0.5, "NOT_CONFIRMING",
    )


def input_for(identity, *, identifier, technical_component="DEFAULT", broader_component=None, external_component=None, session_component="DEFAULT"):
    return MarketRegimeInputV1(
        identifier, TS, identity[0], identity[1],
        market_session_validation=session(identity) if session_component == "DEFAULT" else session_component,
        technical_regime_component=technical(identity) if technical_component == "DEFAULT" else technical_component,
        broader_market_regime_component=broader_component,
        external_context_regime_component=external_component,
    )


def replay_cases():
    return {
        "nifty_strong_bullish": input_for(IDENTITIES[0], identifier="nifty-strong"),
        "banknifty_event_risk": input_for(IDENTITIES[1], identifier="bank-event", external_component=external(IDENTITIES[1], event="HIGH", restriction="WARNING")),
        "finnifty_high_volatility": input_for(IDENTITIES[2], identifier="fin-vol", broader_component=broader(IDENTITIES[2], volatility="HIGH")),
        "sensex_blocked_session": input_for(IDENTITIES[3], identifier="sensex-block", session_component=session(IDENTITIES[3], analysis=False, entries=False)),
        "nifty_conflicting": input_for(IDENTITIES[0], identifier="nifty-conflict", broader_component=broader(IDENTITIES[0], direction="NEGATIVE", confirmation="CONFIRMING")),
        "banknifty_optional_missing": input_for(IDENTITIES[1], identifier="bank-missing"),
        "finnifty_timestamp_skew": input_for(IDENTITIES[2], identifier="fin-skew", broader_component=broader(IDENTITIES[2], timestamp=TS - timedelta(seconds=901))),
        "sensex_unavailable": input_for(IDENTITIES[3], identifier="sensex-unavailable", technical_component=None),
    }
