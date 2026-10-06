"""R19-B unresolved index reconciliation tests."""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TOOL = REPO / "tools" / "r19b_reconcile_unterminated_index_trade.py"


def _load_tool():
    spec = importlib.util.spec_from_file_location("r19b_reconcile", TOOL)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _state():
    return {
        "market": "SENSEX",
        "total_pnl": 1456.39,
        "certification_counter": 2,
        "certification_wins": 0,
        "certification_losses": 2,
        "counted_trade_ids": ["A", "B"],
        "completed_trades": [{"trade_id": "A"}, {"trade_id": "B"}],
        "active_trades": [
            {
                "trade_id": "TRD_SENSEX_20261006_143550700934",
                "status": "OPEN",
                "entry": 321.95,
                "entry_time": "2026-10-06 14:35:50.787836",
                "peak_bid": 360.1,
                "t1_price": 370.2425,
                "sl_price": 305.8525,
                "first_touch_result": "NONE",
                "first_touch_state": {"last_valid_bid": 348.05},
                "certification_countable": True,
            }
        ],
        "orphaned_trades": [],
    }


def test_reconcile_archives_without_inventing_exit_or_accounting():
    mod = _load_tool()
    before = _state()
    before_copy = copy.deepcopy(before)

    after, incident = mod.reconcile_state(
        before,
        "TRD_SENSEX_20261006_143550700934",
        reconciled_at="2026-10-06T17:00:00+00:00",
    )

    assert before == before_copy
    assert after["active_trades"] == []
    assert len(after["orphaned_trades"]) == 1

    archived = after["orphaned_trades"][0]
    assert archived["status"] == "UNRESOLVED_PRIOR_SESSION"
    assert archived["reconciliation_status"] == "UNRESOLVED_EXCLUDED"
    assert archived["terminal_exit_invented"] is False
    assert archived["operational_pnl_included"] is False
    assert archived["certification_countable"] is False

    assert after["total_pnl"] == before["total_pnl"]
    assert after["certification_counter"] == before["certification_counter"]
    assert after["certification_wins"] == before["certification_wins"]
    assert after["certification_losses"] == before["certification_losses"]
    assert after["counted_trade_ids"] == before["counted_trade_ids"]
    assert after["completed_trades"] == before["completed_trades"]

    assert incident["economic_pnl_added"] == 0
    assert incident["certification_count_added"] == 0
    assert incident["terminal_exit_invented"] is False
    assert incident["last_valid_bid"] == 348.05


def test_reconcile_refuses_trade_already_in_completed():
    mod = _load_tool()
    state = _state()
    state["completed_trades"].append(
        {"trade_id": "TRD_SENSEX_20261006_143550700934"}
    )

    try:
        mod.reconcile_state(
            state,
            "TRD_SENSEX_20261006_143550700934",
            reconciled_at="2026-10-06T17:00:00+00:00",
        )
    except ValueError as exc:
        assert str(exc) == "TERMINAL_COMPLETED_RECORD_EXISTS"
    else:
        raise AssertionError("expected refusal")


def test_reconcile_refuses_certification_counted_trade():
    mod = _load_tool()
    state = _state()
    state["counted_trade_ids"].append(
        "TRD_SENSEX_20261006_143550700934"
    )

    try:
        mod.reconcile_state(
            state,
            "TRD_SENSEX_20261006_143550700934",
            reconciled_at="2026-10-06T17:00:00+00:00",
        )
    except ValueError as exc:
        assert str(exc) == "TRADE_ALREADY_CERTIFICATION_COUNTED"
    else:
        raise AssertionError("expected refusal")
