from __future__ import annotations

from datetime import datetime

import mcx.mcx_paper_bot as bot
from mcx.mcx_exec_countability import is_countable


def _recovery_quote():
    return {
        "provider": "FYERS",
        "source_mode": "REST_FULL",
        "provider_received_at": datetime.now().astimezone().isoformat(),
        "validation_status": "INVALID",
        "rejection_reasons": ["MISSING_FEED_TIME"],
        "best_bid": 99.5,
        "bids": [
            {
                "price": 99.5,
                "quantity": 1,
            }
        ],
        "asks": [
            {
                "price": 100.0,
                "quantity": 1,
            }
        ],
        "raw_payload_hash": "RECOVERY_Q1",
        "token": "MCX:TEST",
    }


def test_operational_mark_uses_best_bid_price_without_depth_quantity(
    monkeypatch,
):
    monkeypatch.setattr(
        bot,
        "is_entry_execution_calibrated",
        lambda *args, **kwargs: False,
    )

    monkeypatch.setattr(
        bot,
        "fetch_execution_quote_or_none",
        lambda *args, **kwargs: _recovery_quote(),
    )

    def forbidden_depth(*args, **kwargs):
        raise AssertionError("operational recovery must not consume depth quantity")

    monkeypatch.setattr(
        bot,
        "depth_vwap_for_sell",
        forbidden_depth,
    )

    position = {
        "product": "CRUDEOILM",
        "token": "MCX:TEST",
        "symbol": "MCX:TEST",
        "type": "CE",
        "strike": 100.0,
        "lots": 1,
        "certification_eligible": True,
    }

    mark, quote = bot.get_bid_mark_for_position(
        object(),
        position,
    )

    assert mark == 99.5
    assert quote["operational_recovery_only"] is True
    assert quote["operational_recovery_status"] == "VALID"
    assert quote["operational_recovery_mark_method"] == "BEST_BID_OPERATIONAL_RECOVERY"
    assert quote["certification_freshness_calibrated"] is False
    assert quote["depth_quantity_semantics_verified"] is False
    assert position["operational_recovery_used"] is True
    assert position["certification_eligible"] is False
    assert position["last_mark_mode"] == "OPERATIONAL_RECOVERY_BEST_BID"


def test_certified_mark_keeps_depth_vwap_when_calibrated(
    monkeypatch,
):
    quote = _recovery_quote()
    quote["validation_status"] = "VALID"

    monkeypatch.setattr(
        bot,
        "is_entry_execution_calibrated",
        lambda *args, **kwargs: True,
    )

    monkeypatch.setattr(
        bot,
        "fetch_execution_quote_or_none",
        lambda *args, **kwargs: quote,
    )

    monkeypatch.setattr(
        bot,
        "depth_vwap_for_sell",
        lambda *args, **kwargs: (
            99.25,
            10,
            1,
            99.25,
            "OK",
        ),
    )

    position = {
        "product": "CRUDEOILM",
        "token": "MCX:TEST",
        "symbol": "MCX:TEST",
        "type": "CE",
        "strike": 100.0,
        "lots": 1,
        "certification_eligible": True,
    }

    mark, returned_quote = bot.get_bid_mark_for_position(
        object(),
        position,
    )

    assert mark == 99.25
    assert returned_quote is quote
    assert position["last_mark_mode"] == "CERTIFIED_DEPTH_VWAP"
    assert not position.get(
        "operational_recovery_used",
        False,
    )


def test_countability_explicitly_rejects_operational_recovery():
    trade = {
        "trade_id": "RECOVERY-T1",
        "execution_mode": "PAPER",
        "market_origin": "REAL_MARKET",
        "quote_origin": "REAL_PROVIDER",
        "entry_fill_method": "DEPTH_VWAP",
        "exit_fill_method": "DEPTH_VWAP",
        "entry_quote_id": "Q1",
        "exit_quote_id": "Q2",
        "certification_eligible": True,
        "product": "CRUDEOILM",
        "terminal": True,
        "reconciled": True,
        "first_touch_result": "T1_FIRST",
        "operational_recovery_used": True,
    }

    ok, reasons = is_countable(
        trade,
        "CRUDEOILM",
        _allow_evidence_bypass=True,
    )

    assert ok is False
    assert "OPERATIONAL_RECOVERY_EVIDENCE_USED" in reasons


def test_operational_exit_uses_best_bid_and_never_depth_quantity(
    monkeypatch,
):
    monkeypatch.setattr(
        bot,
        "is_entry_execution_calibrated",
        lambda *args, **kwargs: False,
    )

    monkeypatch.setattr(
        bot,
        "fetch_execution_quote_or_none",
        lambda *args, **kwargs: _recovery_quote(),
    )

    def forbidden_fill(*args, **kwargs):
        raise AssertionError("operational recovery exit must not run DEPTH_VWAP")

    monkeypatch.setattr(
        bot,
        "compute_paper_fill_v2",
        forbidden_fill,
    )

    monkeypatch.setattr(
        bot,
        "record_quote_hash_addressed",
        lambda *args, **kwargs: None,
    )

    def fake_reconcile(pos, product=None):
        record = dict(pos)

        record.update(
            {
                "reconciled": True,
                "is_win": False,
                "gross_pnl": -1.0,
                "costs_total": 0.0,
                "net_pnl": -1.0,
                "profit_giveback_pct": None,
            }
        )

        return record

    monkeypatch.setattr(
        bot,
        "reconcile_trade",
        fake_reconcile,
    )

    def fake_countable(
        record,
        product=None,
        known_trade_ids=None,
    ):
        assert record["exit_fill_method"] == "BEST_BID_OPERATIONAL_RECOVERY"
        assert record["operational_recovery_used"] is True

        return (
            False,
            [
                "OPERATIONAL_RECOVERY_EVIDENCE_USED",
            ],
        )

    monkeypatch.setattr(
        bot,
        "exec_is_countable",
        fake_countable,
    )

    monkeypatch.setattr(
        bot,
        "append_outcome",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError(
                "non-countable recovery must not append certification outcome"
            )
        ),
    )

    monkeypatch.setattr(
        bot,
        "cert_update",
        lambda state, record: state,
    )

    monkeypatch.setattr(
        bot,
        "learn_collect",
        lambda *args, **kwargs: None,
    )

    monkeypatch.setattr(
        bot,
        "cert_status",
        lambda state: {
            "total_countable_trades": 0,
        },
    )

    pos = {
        "trade_id": "RECOVERY-CLOSE",
        "product": "CRUDEOILM",
        "token": "MCX:TEST",
        "symbol": "MCX:TEST",
        "type": "CE",
        "strike": 100.0,
        "entry": 100.0,
        "lots": 1,
        "certification_eligible": True,
        "max_profit_pct": 0.0,
        "min_profit_pct": -1.0,
    }

    state = {
        "active_position": pos,
        "total_trades": 0,
        "winning_trades": 0,
        "losing_trades": 0,
        "total_pnl": 0.0,
        "completed_trades": [],
        "_counted_trade_ids": [],
    }

    bot.close_and_reconcile(
        object(),
        pos,
        "STOP_LOSS",
        99.5,
        -0.5,
        state,
    )

    assert state["active_position"] is None
    assert state["total_trades"] == 1
    assert len(state["completed_trades"]) == 1

    record = state["completed_trades"][0]

    assert record["exit_fill_method"] == "BEST_BID_OPERATIONAL_RECOVERY"

    assert record["exit_operational_recovery"] is True

    assert record["operational_recovery_used"] is True

    assert record["certification_eligible"] is False
    assert record["countable"] is False


def test_operational_recovery_rejects_structurally_invalid_book(
    monkeypatch,
):
    quote = _recovery_quote()

    quote["rejection_reasons"] = [
        "MISSING_FEED_TIME",
        "CROSSED_BOOK_INVALID",
    ]

    quote["best_bid"] = 101.0

    quote["bids"] = [
        {
            "price": 101.0,
            "quantity": 1,
        }
    ]

    quote["asks"] = [
        {
            "price": 100.0,
            "quantity": 1,
        }
    ]

    monkeypatch.setattr(
        bot,
        "is_entry_execution_calibrated",
        lambda *args, **kwargs: False,
    )

    monkeypatch.setattr(
        bot,
        "fetch_execution_quote_or_none",
        lambda *args, **kwargs: quote,
    )

    position = {
        "product": "CRUDEOILM",
        "token": "MCX:TEST",
        "symbol": "MCX:TEST",
        "type": "CE",
        "strike": 100.0,
        "lots": 1,
        "certification_eligible": True,
    }

    mark, returned_quote = bot.get_bid_mark_for_position(
        object(),
        position,
    )

    assert mark is None
    assert returned_quote is quote

    assert not position.get(
        "operational_recovery_used",
        False,
    )

    assert position["certification_eligible"] is True
