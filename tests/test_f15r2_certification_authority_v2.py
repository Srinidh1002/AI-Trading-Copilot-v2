"""F15-R2 Phase R2-2 — certification writer/ledger consistency.

Root cause fixed: close_position used to write the outcome row
BEFORE _try_increment_certification_counter ran, so non-diversity
rejections (NONE/AMBIGUOUS first touch, wrong epoch, non-PAPER, etc.)
left the row saying certification_countable=True even though the
authoritative counter rejected the trade.

This test file proves:
  * the split evaluator is pure and returns the correct reason
  * the applier is idempotent by trade_id
  * close_position writes the row with the authoritative decision
  * ledger-write failure downgrades an otherwise-admitted trade
  * AMBIGUOUS and NONE are never counted
  * accepted trades land in counted_trade_ids exactly once
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

from provider_injected_target_bot_v2 import (  # noqa: E402
    ProviderInjectedUnifiedTradingBotV2,
)
from target_focused_bot import (  # noqa: E402
    CERTIFICATION_EPOCH,
    STRATEGY_VERSION,
)

# ---------------- collaborators ----------------

class _FakeMFE:
    def snapshot(self, tid):
        return {
            "max_favorable": 0.0,
            "max_adverse": 0.0,
            "peak_pnl_pct": 0.0,
            "trough_pnl_pct": 0.0,
        }


class _FakeCapital:
    def compute_net_pnl(self, entry, exit_price, qty, direction):
        return {
            "gross_pnl": 0.0,
            "costs": {"total": 0.0},
            "net_pnl": 0.0,
            "net_pnl_pct": 0.0,
        }


class _FakeLedger:
    def __init__(self, ok=True):
        self.rows = []
        self.ok = ok
    def record(self, trade):
        if not self.ok:
            return False
        # snapshot at write time to catch later mutations
        self.rows.append({
            "trade_id": trade.get("trade_id"),
            "first_touch_result": trade.get("first_touch_result"),
            "certification_countable": trade.get("certification_countable"),
            "certification_countability_reason":
                trade.get("certification_countability_reason"),
            "certification_win": trade.get("certification_win"),
            "certification_loss": trade.get("certification_loss"),
        })
        return True


class _FakeDiversity:
    def __init__(self, allow=True, reason=None):
        self.allow = allow
        self.reason = reason
        self.countable_by_day = {}
        self.records = []
    def would_count(self, trade_date, regime, phase):
        return self.allow, self.reason
    def record(self, trade_date, regime, phase):
        self.records.append((trade_date, regime, phase))
        self.countable_by_day[trade_date] = self.countable_by_day.get(trade_date, 0) + 1


# ---------------- fixtures ----------------

def _make_trade(tid, ftr, *, countable=True,
                epoch=CERTIFICATION_EPOCH, sv=STRATEGY_VERSION,
                execution_mode="PAPER", broker_submission=False,
                live_execution=False, eligible=True):
    return {
        "trade_id": tid,
        "type": "PE",
        "strike": 22800.0,
        "signal": "BUY",
        "symbol": "NIFTY_TEST_SYM",
        "entry": 100.0,
        "quantity": 65,
        "lot_size": 65,
        "entry_time": "2026-09-28 10:00:00",
        # _evaluate_certification_admission is only called from
        # close_position, which sets status='CLOSED' before the call.
        # Fixture therefore defaults to CLOSED.
        "status": "CLOSED",
        "execution_mode": execution_mode,
        "broker_submission": broker_submission,
        "live_execution": live_execution,
        "certification_eligible": eligible,
        "certification_countable": countable,
        "certification_win": None,
        "certification_loss": None,
        "certification_countability_reason": None,
        "strategy_version": sv,
        "certification_epoch": epoch,
        "certification_trade_date": "2026-09-28",
        "certification_regime": "TRENDING_DOWN",
        "certification_session_phase": "EARLY_CONTINUOUS",
        "first_touch_result": ftr,
        "monitoring_gap_count": 0,
        "evidence_ambiguous": False,
    }


def _build_test_bot(*, ledger=None, diversity=None):
    bot = object.__new__(ProviderInjectedUnifiedTradingBotV2)
    bot.market = "NIFTY"
    bot.certification_counter = 0
    bot.certification_wins = 0
    bot.certification_losses = 0
    bot.counted_trade_ids = set()
    bot.active_trades = {}
    bot.completed_trades = []
    bot.total_pnl = 0.0
    bot.winning_trades = 0
    bot.losing_trades = 0
    bot.consecutive_wins = 0
    bot.consecutive_losses = 0
    bot.daily_trade_count = 0
    bot.daily_realized_loss = 0.0
    bot.same_direction_stops = 0
    bot.last_exit_time = None
    bot.last_exit_direction = None
    bot.mfe_mae = _FakeMFE()
    bot.capital_engine = _FakeCapital()
    bot.outcome_ledger = ledger or _FakeLedger()
    bot.certification_diversity = diversity or _FakeDiversity()
    bot.save_state = lambda: None
    return bot


def _close(bot, trade, *, reason="STOP_LOSS", exit_price=95.0, pnl=-5.0, pnl_pct=-5.0):
    bot.active_trades[trade["trade_id"]] = trade
    bot.close_position(
        trade["trade_id"], exit_price, reason, pnl, pnl_pct
    )


# ---------------- evaluate (pure) ----------------

def test_evaluate_accepts_t1_first():
    bot = _build_test_bot()
    t = _make_trade("T1", "T1_FIRST")
    accepted, reason = bot._evaluate_certification_admission(t)
    assert accepted is True
    assert reason is None


def test_evaluate_accepts_sl_first():
    bot = _build_test_bot()
    t = _make_trade("T1", "SL_FIRST")
    accepted, reason = bot._evaluate_certification_admission(t)
    assert accepted is True


def test_evaluate_rejects_none_first_touch():
    bot = _build_test_bot()
    t = _make_trade("T1", "NONE")
    accepted, reason = bot._evaluate_certification_admission(t)
    assert accepted is False
    assert "NO_TERMINAL_FIRST_TOUCH" in reason


def test_evaluate_rejects_ambiguous_first_touch():
    bot = _build_test_bot()
    t = _make_trade("T1", "AMBIGUOUS")
    accepted, reason = bot._evaluate_certification_admission(t)
    assert accepted is False
    assert "NO_TERMINAL_FIRST_TOUCH" in reason


def test_evaluate_rejects_not_paper():
    bot = _build_test_bot()
    t = _make_trade("T1", "SL_FIRST", execution_mode="LIVE")
    accepted, reason = bot._evaluate_certification_admission(t)
    assert accepted is False
    assert "NOT_PAPER" in reason


def test_evaluate_rejects_wrong_epoch():
    bot = _build_test_bot()
    t = _make_trade("T1", "SL_FIRST", epoch="WRONG_EPOCH")
    accepted, reason = bot._evaluate_certification_admission(t)
    assert accepted is False
    assert "WRONG_EPOCH" in reason


def test_evaluate_rejects_wrong_strategy_version():
    bot = _build_test_bot()
    t = _make_trade("T1", "SL_FIRST", sv="OLD_STRATEGY")
    accepted, reason = bot._evaluate_certification_admission(t)
    assert accepted is False
    assert "WRONG_STRATEGY_VERSION" in reason


def test_evaluate_rejects_duplicate_trade_id():
    bot = _build_test_bot()
    bot.counted_trade_ids.add("T1")
    t = _make_trade("T1", "SL_FIRST")
    accepted, reason = bot._evaluate_certification_admission(t)
    assert accepted is False
    assert "DUPLICATE_TRADE_ID" in reason


def test_evaluate_rejects_diversity_gate():
    bot = _build_test_bot(diversity=_FakeDiversity(allow=False, reason="DAY_CAP"))
    t = _make_trade("T1", "SL_FIRST")
    accepted, reason = bot._evaluate_certification_admission(t)
    assert accepted is False
    assert reason == "DAY_CAP"


# ---------------- apply (mutating) ----------------

def test_apply_increments_counter_and_ids():
    bot = _build_test_bot()
    t = _make_trade("T1", "SL_FIRST")
    bot._apply_certification_acceptance(t)
    assert bot.certification_counter == 1
    assert "T1" in bot.counted_trade_ids
    assert bot.certification_losses == 1
    assert bot.certification_wins == 0


def test_apply_t1_first_counts_as_win():
    bot = _build_test_bot()
    t = _make_trade("T1", "T1_FIRST")
    bot._apply_certification_acceptance(t)
    assert bot.certification_wins == 1
    assert bot.certification_losses == 0


def test_apply_is_idempotent():
    bot = _build_test_bot()
    t = _make_trade("T1", "SL_FIRST")
    bot._apply_certification_acceptance(t)
    bot._apply_certification_acceptance(t)
    bot._apply_certification_acceptance(t)
    assert bot.certification_counter == 1
    assert bot.certification_losses == 1


# ---------------- end-to-end via close_position ----------------

def test_close_writes_row_with_false_for_none_ftr():
    ledger = _FakeLedger()
    bot = _build_test_bot(ledger=ledger)
    t = _make_trade("T_NONE", "NONE")
    _close(bot, t)
    assert len(ledger.rows) == 1
    row = ledger.rows[0]
    assert row["certification_countable"] is False
    assert "NO_TERMINAL_FIRST_TOUCH" in (row["certification_countability_reason"] or "")
    assert bot.certification_counter == 0
    assert "T_NONE" not in bot.counted_trade_ids


def test_close_writes_row_with_false_for_ambiguous_ftr():
    ledger = _FakeLedger()
    bot = _build_test_bot(ledger=ledger)
    t = _make_trade("T_AMB", "AMBIGUOUS")
    _close(bot, t)
    row = ledger.rows[0]
    assert row["certification_countable"] is False
    assert bot.certification_counter == 0


def test_close_writes_row_with_true_and_counts_for_sl_first():
    ledger = _FakeLedger()
    bot = _build_test_bot(ledger=ledger)
    t = _make_trade("T_SL", "SL_FIRST")
    _close(bot, t)
    row = ledger.rows[0]
    assert row["certification_countable"] is True
    assert row["certification_countability_reason"] is None
    assert row["certification_loss"] is True
    assert bot.certification_counter == 1
    assert "T_SL" in bot.counted_trade_ids


def test_close_writes_row_with_true_and_counts_for_t1_first():
    ledger = _FakeLedger()
    bot = _build_test_bot(ledger=ledger)
    t = _make_trade("T_T1", "T1_FIRST")
    _close(bot, t)
    row = ledger.rows[0]
    assert row["certification_countable"] is True
    assert row["certification_win"] is True
    assert bot.certification_counter == 1
    assert bot.certification_wins == 1


def test_close_downgrades_admitted_trade_if_ledger_write_fails():
    ledger = _FakeLedger(ok=False)
    bot = _build_test_bot(ledger=ledger)
    t = _make_trade("T_LEDGER_FAIL", "SL_FIRST")
    _close(bot, t)
    # No row written
    assert ledger.rows == []
    # And the trade was NOT counted
    assert bot.certification_counter == 0
    assert "T_LEDGER_FAIL" not in bot.counted_trade_ids
    # And the in-memory trade reflects the downgrade
    assert t["certification_countable"] is False
    assert t["certification_countability_reason"] == "NOT_RECONCILED"


def test_close_duplicate_call_is_not_counted_twice():
    ledger = _FakeLedger()
    bot = _build_test_bot(ledger=ledger)
    t = _make_trade("T_DUP", "SL_FIRST")
    _close(bot, t)
    assert bot.certification_counter == 1
    # Re-inject into active_trades and call close again with same trade dict
    t["status"] = "OPEN"
    t["certification_countable"] = True
    t["certification_countability_reason"] = None
    _close(bot, t)
    # Counter unchanged
    assert bot.certification_counter == 1
    assert bot.counted_trade_ids == {"T_DUP"}


def test_close_accepts_multiple_distinct_trades_in_sequence():
    ledger = _FakeLedger()
    bot = _build_test_bot(ledger=ledger)
    _close(bot, _make_trade("T_A", "T1_FIRST"))
    _close(bot, _make_trade("T_B", "SL_FIRST"))
    _close(bot, _make_trade("T_C", "SL_FIRST"))
    assert bot.certification_counter == 3
    assert bot.certification_wins == 1
    assert bot.certification_losses == 2
    assert bot.counted_trade_ids == {"T_A", "T_B", "T_C"}
    assert len(ledger.rows) == 3
    assert [r["trade_id"] for r in ledger.rows] == ["T_A", "T_B", "T_C"]
