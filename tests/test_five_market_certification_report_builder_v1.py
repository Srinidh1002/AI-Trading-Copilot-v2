from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from services.certification.five_market_certification_report_builder_v1 import (
    build_five_market_certification_report_v1,
)


NOW = datetime(2026, 10, 5, 11, 0, tzinfo=timezone.utc)


def _write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )


def _index_state(market: str, accepted_trades=()):
    wins = sum(
        item["first_touch_result"] == "T1_FIRST"
        for item in accepted_trades
    )
    losses = sum(
        item["first_touch_result"] == "SL_FIRST"
        for item in accepted_trades
    )
    dates = sorted(
        {item["certification_trade_date"] for item in accepted_trades}
    )
    regimes = sorted(
        {item["certification_regime"] for item in accepted_trades}
    )
    phases = sorted(
        {item["certification_session_phase"] for item in accepted_trades}
    )
    per_day = {}
    for item in accepted_trades:
        day = item["certification_trade_date"]
        per_day[day] = per_day.get(day, 0) + 1

    return {
        "market": market,
        "strategy_version": "NS_DESIGN_B_BID_AUTH_V3",
        "certification_epoch": "NS_CERT_20260916_V3",
        "certification_counter": len(accepted_trades),
        "certification_wins": wins,
        "certification_losses": losses,
        "counted_trade_ids": [
            item["trade_id"] for item in accepted_trades
        ],
        "completed_trades": list(accepted_trades),
        "active_trades": [],
        "total_trades": len(accepted_trades),
        "winning_trades": wins,
        "losing_trades": losses,
        "total_pnl": sum(item["net_pnl"] for item in accepted_trades),
        "diversity_state": {
            "trading_dates": dates,
            "regimes": regimes,
            "session_phases": phases,
            "countable_by_day": per_day,
        },
    }


def _index_trade(number: int, *, win=True):
    day = 1 + number // 20
    regime = "TRENDING_UP" if number % 2 else "RANGE_BOUND"
    phase = "MORNING" if number % 3 else "AFTERNOON"
    first_touch = "T1_FIRST" if win else "SL_FIRST"
    return {
        "trade_id": f"IDX-{number:03d}",
        "status": "CLOSED",
        "first_touch_result": first_touch,
        "certification_countable": True,
        "certification_trade_date": f"2026-10-{day:02d}",
        "certification_regime": regime,
        "certification_session_phase": phase,
        "strategy_version": "NS_DESIGN_B_BID_AUTH_V3",
        "certification_epoch": "NS_CERT_20260916_V3",
        "execution_mode": "PAPER",
        "broker_submission": False,
        "live_execution": False,
        "net_pnl": 100.0 if win else -100.0,
    }


def _mcx_state(market: str):
    version = {
        "CRUDEOILM": ("MCX_POST_PRECISION_V4", "POST_PRECISION_V4"),
        "GOLDM": ("MCX_GOLDM_PRECERT_V2", "GOLDM_PRECERT_V2"),
        "NATGASMINI": (
            "MCX_NATGASMINI_PRECERT_V1",
            "NATGASMINI_PRECERT_V1",
        ),
    }[market]
    return {
        "product": market,
        "strategy_version": version[0],
        "epoch": version[1],
        "certification_eligible": (
            False if market == "NATGASMINI" else True
        ),
        "t1_hit_wins": 0,
        "sl_losses": 0,
        "_counted_trade_ids": [],
        "total_trades": 0,
        "winning_trades": 0,
        "losing_trades": 0,
        "total_pnl": 0.0,
        "active_position": None,
        "completed_trades": [],
    }


def _build_root(tmp_path: Path, nifty_trades=()):
    base = tmp_path / "data" / "paper_trades"
    nifty_state = _index_state("NIFTY", nifty_trades)
    sensex_state = _index_state("SENSEX", ())
    _write_json(base / "nifty_experimental.json", nifty_state)
    _write_json(base / "sensex_experimental.json", sensex_state)

    _write_jsonl(
        base / "nifty_outcomes.jsonl",
        [
            {
                **trade,
                "market": "NIFTY",
            }
            for trade in nifty_trades
        ],
    )
    _write_jsonl(base / "sensex_outcomes.jsonl", [])

    for market in ("CRUDEOILM", "GOLDM", "NATGASMINI"):
        _write_json(
            base / f"mcx_{market.lower()}_experimental.json",
            _mcx_state(market),
        )
        _write_jsonl(
            base / f"mcx_{market.lower()}_outcomes.jsonl",
            [],
        )
    return tmp_path


def test_in_progress_report_reconciles_one_index_trade(tmp_path):
    trade = _index_trade(0, win=True)
    report = build_five_market_certification_report_v1(
        _build_root(tmp_path, (trade,)),
        generated_at=NOW,
        release_commit="99cf",
    )

    nifty = report.markets[0]
    assert nifty.accepted_trade_count == 1
    assert nifty.t1_first_wins == 1
    assert nifty.ledger_reconciliation_pass is True
    assert nifty.state_counter_integrity is True
    assert nifty.final_status == "IN_PROGRESS"
    assert report.all_markets_complete is False
    assert report.all_markets_pass is False


def test_100_diversified_with_80_wins_passes_market(tmp_path):
    trades = tuple(
        _index_trade(i, win=(i < 80))
        for i in range(100)
    )
    report = build_five_market_certification_report_v1(
        _build_root(tmp_path, trades),
        generated_at=NOW,
        release_commit="99cf",
    )

    nifty = report.markets[0]
    assert nifty.accepted_trade_count == 100
    assert nifty.t1_first_wins == 80
    assert nifty.sl_first_losses == 20
    assert nifty.distinct_trading_days == 5
    assert nifty.distinct_regimes == 2
    assert nifty.distinct_session_phases == 2
    assert nifty.max_countable_per_day == 20
    assert nifty.diversity_pass is True
    assert nifty.accuracy_threshold_pass is True
    assert nifty.final_status == "PASS"


def test_100_diversified_with_79_wins_fails_accuracy(tmp_path):
    trades = tuple(
        _index_trade(i, win=(i < 79))
        for i in range(100)
    )
    report = build_five_market_certification_report_v1(
        _build_root(tmp_path, trades),
        generated_at=NOW,
        release_commit="99cf",
    )

    nifty = report.markets[0]
    assert nifty.diversity_pass is True
    assert nifty.accuracy_threshold_pass is False
    assert nifty.final_status == "FAIL_ACCURACY"


def test_missing_counted_ledger_row_prevents_pass(tmp_path):
    trades = tuple(
        _index_trade(i, win=(i < 80))
        for i in range(100)
    )
    root = _build_root(tmp_path, trades)
    ledger = (
        root / "data" / "paper_trades" / "nifty_outcomes.jsonl"
    )
    rows = ledger.read_text(encoding="utf-8").splitlines()
    ledger.write_text(
        "\n".join(rows[:-1]) + "\n",
        encoding="utf-8",
    )

    report = build_five_market_certification_report_v1(
        root,
        generated_at=NOW,
        release_commit="99cf",
    )
    nifty = report.markets[0]
    assert nifty.ledger_reconciliation_pass is False
    assert nifty.final_status != "PASS"


def test_report_remains_paper_only(tmp_path):
    report = build_five_market_certification_report_v1(
        _build_root(tmp_path),
        generated_at=NOW,
        release_commit="99cf",
    )
    assert report.execution_mode == "PAPER"
    assert report.live_broker_orders_prohibited is True
    assert report.live_capital_prohibited is True
    assert report.read_only is True
