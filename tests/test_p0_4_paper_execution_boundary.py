"""P0-4 fail-closed contract tests for explicit paper execution."""

import math
from unittest.mock import Mock

import pytest

from test_p0_3_entry_point_fail_safe_matrix import _load_trade_engine


def _approved_result(action="BUY CE"):
    direction = "SELL" if action in {"SELL", "BUY PE"} else "BUY"
    return {
        "decision": action,
        "master_decision": direction,
        "approval_status": "APPROVED",
        "entry_allowed": True,
        "trade_action": "EXECUTE",
        "entry": 25_000.0,
        "stop_loss": 24_900.0,
        "target1": 25_100.0,
        "target2": 25_150.0,
        "confidence": 80.0,
        "reason": "validated setup",
        "risk_level": "LOW",
        "snapshot": {
            "timestamp": "2026-07-25T09:15:00+05:30",
            "ltp": 25_000.0,
        },
    }


@pytest.mark.parametrize(
    "change",
    [
        {"decision": "WAIT"},
        {"decision": "HOLD"},
        {"decision": "NO_TRADE"},
        {"decision": "TRADE_REJECTED"},
        {"decision": "BLOCKED"},
        {"decision": "ERROR"},
        {"decision": None},
        {"decision": "UNSUPPORTED"},
        {"entry": None},
        {"stop_loss": None},
        {"target1": None},
        {"target2": None},
        {"entry": math.nan},
        {"snapshot": {"timestamp": "x", "ltp": math.inf}},
        {"quantity": 0},
        {"trade_action": "WAIT"},
        {"approval_status": "CAUTION"},
        {"master_decision": "SELL"},
        {"error": "analysis failed"},
        {"risk_level": "REJECTED"},
    ],
)
def test_rejected_inputs_never_reach_paper_engine(monkeypatch, change):
    trade_engine = _load_trade_engine()
    process_trade = Mock()
    monkeypatch.setattr(trade_engine, "process_trade", process_trade)
    result = _approved_result()
    result.update(change)

    rejection = trade_engine.execute_paper_trade(result)

    assert rejection["status"] == "REJECTED"
    assert rejection["executed"] is False
    assert rejection["reason"]
    assert rejection["paper_trade"] is None
    process_trade.assert_not_called()


@pytest.mark.parametrize("action", ["BUY CE", "BUY", "BUY PE", "SELL"])
def test_valid_approved_directional_result_submits_once(monkeypatch, action):
    trade_engine = _load_trade_engine()
    process_trade = Mock()
    monkeypatch.setattr(trade_engine, "process_trade", process_trade)

    result = trade_engine.execute_paper_trade(_approved_result(action))

    assert result["status"] == "SUBMITTED"
    assert result["executed"] is True
    assert result["paper_trade"]["decision"] in {"BUY", "SELL"}
    process_trade.assert_called_once()


def test_paper_engine_exception_fails_closed(monkeypatch):
    trade_engine = _load_trade_engine()
    process_trade = Mock(side_effect=RuntimeError("storage unavailable"))
    monkeypatch.setattr(trade_engine, "process_trade", process_trade)

    result = trade_engine.execute_paper_trade(_approved_result())

    assert result == {
        "status": "REJECTED",
        "executed": False,
        "reason": "Paper trade execution failed.",
        "paper_trade": None,
    }
    process_trade.assert_called_once()


def test_repeated_rejected_calls_remain_side_effect_free(monkeypatch):
    trade_engine = _load_trade_engine()
    process_trade = Mock()
    monkeypatch.setattr(trade_engine, "process_trade", process_trade)

    first = trade_engine.execute_paper_trade({})
    second = trade_engine.execute_paper_trade({})

    assert first == second
    process_trade.assert_not_called()
