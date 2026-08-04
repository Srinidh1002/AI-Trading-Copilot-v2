"""P0-2 contract: dashboard analysis must not mutate paper-trading state."""

import inspect
import sys
from types import ModuleType
from unittest.mock import Mock

from services.decision import master_decision_engine


def _test_master_decision(**_):
    return {"final_decision": "HOLD"}


# `services.trade.trade_engine` currently imports a missing production symbol.
# Install this test-only shim solely long enough to import the analysis module;
# individual tests replace its bound dependency with controlled values.
_missing_master_decision = not hasattr(
    master_decision_engine,
    "make_master_decision",
)
if _missing_master_decision:
    master_decision_engine.make_master_decision = _test_master_decision

_response_builder_name = "services.trade.trade_response_builder"
_response_builder = ModuleType(_response_builder_name)
_response_builder.build_trade_response = lambda **_: None
sys.modules[_response_builder_name] = _response_builder

try:
    import dashboard.dashboard_v2 as dashboard
    import services.trade.trade_engine as trade_engine
finally:
    del sys.modules[_response_builder_name]
    if _missing_master_decision:
        del master_decision_engine.make_master_decision


def _snapshot():
    return {
        "timestamp": "2026-07-25T09:15:00+05:30",
        "ltp": 25_000.0,
        "low": 24_900.0,
        "high": 25_100.0,
        "indicators": {},
    }


def _configure_analysis(monkeypatch):
    decision = {
        "bull_score": 8,
        "bear_score": 1,
        "signal": "BUY",
        "confidence": 80,
    }
    risk = {
        "entry": 25_000.0,
        "stop_loss": 24_900.0,
        "risk_reward": 2.0,
    }
    score = {
        "Action": "EXECUTE",
        "Score": 80,
        "Grade": "A",
        "RiskLevel": "LOW",
        "Reasons": [],
    }
    confidence = {"confidence": 80, "grade": "A"}
    master = {"final_decision": "BUY"}

    monkeypatch.setattr(trade_engine, "make_decision", lambda _: decision)
    monkeypatch.setattr(trade_engine, "calculate_risk", lambda *_: risk)
    monkeypatch.setattr(
        trade_engine.trade_score_engine,
        "evaluate",
        lambda *_: score,
    )
    monkeypatch.setattr(
        trade_engine,
        "calculate_confidence",
        lambda **_: confidence,
    )
    monkeypatch.setattr(
        trade_engine,
        "make_master_decision",
        lambda **_: master,
    )
    monkeypatch.setattr(
        trade_engine,
        "build_trade_response",
        lambda **kwargs: {
            "decision": kwargs["display_signal"],
            "trade_action": score["Action"],
            "entry": kwargs["entry"],
            "stop_loss": kwargs["stop_loss"],
            "target1": kwargs["target1"],
            "target2": kwargs["target2"],
            "confidence": kwargs["confidence"],
            "reason": kwargs["reason"],
            "snapshot": kwargs["snapshot"],
        },
    )
    monkeypatch.setattr(trade_engine.performance_monitor, "start", lambda _: None)
    monkeypatch.setattr(trade_engine.performance_monitor, "stop", lambda _: None)
    monkeypatch.setattr(trade_engine.refresh_state, "decision", None)


def test_analyze_trade_never_calls_paper_engine(monkeypatch):
    _configure_analysis(monkeypatch)
    process_trade = Mock()
    monkeypatch.setattr(trade_engine, "process_trade", process_trade)

    result = trade_engine.analyze_trade(_snapshot())

    assert result["decision"] == "BUY CE"
    process_trade.assert_not_called()


def test_repeated_analysis_and_paper_engine_failures_are_side_effect_free(
    monkeypatch,
):
    _configure_analysis(monkeypatch)
    monkeypatch.setattr(
        trade_engine,
        "process_trade",
        Mock(side_effect=RuntimeError("paper engine must not run")),
    )

    first = trade_engine.analyze_trade(_snapshot())
    second = trade_engine.analyze_trade(_snapshot())

    assert first["decision"] == second["decision"] == "BUY CE"
    trade_engine.process_trade.assert_not_called()


def test_explicit_paper_execution_boundary_invokes_paper_engine(monkeypatch):
    process_trade = Mock(return_value="submitted")
    monkeypatch.setattr(trade_engine, "process_trade", process_trade)

    result = trade_engine.execute_paper_trade(
        {
            "decision": "BUY CE",
            "master_decision": "BUY",
            "approval_status": "APPROVED",
            "entry_allowed": True,
            "trade_action": "EXECUTE",
            "entry": 25_000.0,
            "stop_loss": 24_900.0,
            "target1": 25_100.0,
            "target2": 25_150.0,
            "confidence": 80,
            "reason": "test",
            "snapshot": _snapshot(),
        }
    )

    assert result["status"] == "SUBMITTED"
    assert result["executed"] is True
    process_trade.assert_called_once_with(
        {
            "timestamp": "2026-07-25T09:15:00+05:30",
            "decision": "BUY",
            "trade_action": "EXECUTE",
            "entry": 25_000.0,
            "stop_loss": 24_900.0,
            "target1": 25_100.0,
            "target2": 25_150.0,
            "confidence": 80,
            "reason": "test",
            "current_price": 25_000.0,
        }
    )


def test_dashboard_has_no_paper_execution_boundary_call():
    source = inspect.getsource(dashboard)

    assert "execute_paper_trade" not in source
    assert "process_trade" not in source
