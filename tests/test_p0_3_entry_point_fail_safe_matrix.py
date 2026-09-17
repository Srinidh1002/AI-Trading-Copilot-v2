"""P0-3 verification of supported entry-point fail-safe boundaries."""

import sys
from types import ModuleType
from unittest.mock import Mock

def _load_trade_engine():
    module_name = "services.trade.trade_engine"
    if module_name in sys.modules:
        return sys.modules[module_name]

    from services.decision import master_decision_engine

    missing_master_decision = not hasattr(
        master_decision_engine,
        "make_master_decision",
    )
    if missing_master_decision:
        master_decision_engine.make_master_decision = lambda **_: {
            "final_decision": "HOLD"
        }

    response_builder_name = "services.trade.trade_response_builder"
    response_builder = ModuleType(response_builder_name)
    response_builder.build_trade_response = lambda **_: None
    sys.modules[response_builder_name] = response_builder

    try:
        from services.trade import trade_engine
        return trade_engine
    finally:
        sys.modules.pop(response_builder_name, None)
        if missing_master_decision:
            del master_decision_engine.make_master_decision


def _unapproved_analysis_result():
    return {
        "decision": "WAIT",
        "trade_action": "EXECUTE",
        "entry": 25_000.0,
        "stop_loss": 24_900.0,
        "target1": 25_100.0,
        "target2": 25_150.0,
        "confidence": 0,
        "reason": "market data unavailable",
        "snapshot": {
            "timestamp": "2026-07-25T09:15:00+05:30",
            "ltp": 25_000.0,
        },
    }


def test_explicit_paper_execution_rejects_unapproved_analysis(monkeypatch):
    trade_engine = _load_trade_engine()
    process_trade = Mock()
    monkeypatch.setattr(trade_engine, "process_trade", process_trade)

    result = trade_engine.execute_paper_trade(
        _unapproved_analysis_result()
    )

    process_trade.assert_not_called()
    assert result == {
        "status": "REJECTED",
        "executed": False,
        "reason": "A directional BUY or SELL decision is required.",
        "paper_trade": None,
    }


def test_explicit_paper_execution_returns_safe_result_for_malformed_input():
    trade_engine = _load_trade_engine()

    result = trade_engine.execute_paper_trade({})

    assert result == {
        "status": "REJECTED",
        "executed": False,
        "reason": "A directional BUY or SELL decision is required.",
        "paper_trade": None,
    }
