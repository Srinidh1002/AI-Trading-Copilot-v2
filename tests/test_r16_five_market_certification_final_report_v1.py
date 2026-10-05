from __future__ import annotations

import json
from pathlib import Path

from services.reporting.five_market_certification_final_report_v1 import (
    build_five_market_certification_final_report,
)


INDEX_VERSION = "NS_DESIGN_B_BID_AUTH_V3"
INDEX_EPOCH = "NS_CERT_20260916_V3"


def _write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )


def _index_state(market, completed, counted, wins, losses):
    return {
        "market": market,
        "strategy_version": INDEX_VERSION,
        "certification_epoch": INDEX_EPOCH,
        "certification_counter": len(counted),
        "certification_wins": wins,
        "certification_losses": losses,
        "counted_trade_ids": counted,
        "active_trades": [],
        "completed_trades": completed,
        "total_trades": len(completed),
        "winning_trades": sum((t.get("net_pnl") or 0) > 0 for t in completed),
        "losing_trades": sum((t.get("net_pnl") or 0) < 0 for t in completed),
        "total_pnl": sum(float(t.get("net_pnl") or 0) for t in completed),
    }


def _mcx_state(product, epoch, version, *, eligible, completed=(), counted=(), wins=0, losses=0):
    payload = {
        "product": product,
        "epoch": epoch,
        "strategy_version": version,
        "certification_eligible": eligible,
        "t1_hit_wins": wins,
        "sl_losses": losses,
        "_counted_trade_ids": list(counted),
        "active_position": None,
        "completed_trades": list(completed),
        "total_trades": len(completed),
        "winning_trades": sum((t.get("net_pnl") or 0) > 0 for t in completed),
        "losing_trades": sum((t.get("net_pnl") or 0) < 0 for t in completed),
        "total_pnl": sum(float(t.get("net_pnl") or 0) for t in completed),
    }
    return payload


def _base_repo(root: Path):
    base = root / "data/paper_trades"
    _write_json(base / "nifty_experimental.json", _index_state("NIFTY", [], [], 0, 0))
    _write_json(base / "sensex_experimental.json", _index_state("SENSEX", [], [], 0, 0))
    _write_json(
        base / "mcx_crudeoilm_experimental.json",
        _mcx_state("CRUDEOILM", "POST_PRECISION_V4", "MCX_POST_PRECISION_V4", eligible=True),
    )
    _write_json(
        base / "mcx_goldm_experimental.json",
        _mcx_state("GOLDM", "GOLDM_PRECERT_V2", "MCX_GOLDM_PRECERT_V2", eligible=True),
    )
    _write_json(
        base / "mcx_natgasmini_experimental.json",
        _mcx_state(
            "NATGASMINI",
            "NATGASMINI_PRECERT_V1",
            "MCX_NATGASMINI_PRECERT_V1",
            eligible=False,
        ),
    )


def test_report_keeps_ambiguous_operational_trade_outside_certification(tmp_path):
    _base_repo(tmp_path)
    base = tmp_path / "data/paper_trades"

    accepted = {
        "trade_id": "N1",
        "first_touch_result": "T1_FIRST",
        "certification_countable": True,
        "certification_trade_date": "2026-10-05",
        "certification_regime": "TRENDING_UP",
        "certification_session_phase": "MORNING",
        "net_pnl": 653.43,
    }
    ambiguous = {
        "trade_id": "N2",
        "first_touch_result": "AMBIGUOUS",
        "certification_countable": False,
        "net_pnl": -461.76,
    }
    _write_json(
        base / "nifty_experimental.json",
        _index_state("NIFTY", [accepted, ambiguous], ["N1"], 1, 0),
    )
    _write_jsonl(
        base / "nifty_outcomes.jsonl",
        [
            {
                "trade_id": "N1",
                "first_touch_result": "T1_FIRST",
                "certification_countable": True,
                "strategy_version": INDEX_VERSION,
                "certification_epoch": INDEX_EPOCH,
            },
            {
                "trade_id": "N2",
                "first_touch_result": "AMBIGUOUS",
                "certification_countable": False,
                "strategy_version": INDEX_VERSION,
                "certification_epoch": INDEX_EPOCH,
            },
        ],
    )

    report = build_five_market_certification_final_report(tmp_path)
    nifty = {item.market: item for item in report.markets}["NIFTY"]

    assert nifty.accepted_count == 1
    assert nifty.operational_total_trades == 2
    assert nifty.noncountable_completed_count == 1
    assert nifty.ambiguous_completed_count == 1
    assert nifty.ambiguity_percent_of_completed == 50.0
    assert nifty.accepted_ledger_match_count == 1
    assert nifty.accounting_integrity_pass is True
    assert nifty.ledger_integrity_pass is True
    assert nifty.final_verdict == "IN_PROGRESS"


def test_report_validates_mcx_accepted_trade_against_ledger(tmp_path):
    _base_repo(tmp_path)
    base = tmp_path / "data/paper_trades"

    trade = {
        "trade_id": "C1",
        "entry_time": "2026-10-05T18:00:00+05:30",
        "first_touch_result": "SL_FIRST",
        "certification_countable": True,
        "certification_accepted": True,
        "regime_at_entry": "TRENDING_DOWN",
        "net_pnl": -100.0,
    }
    _write_json(
        base / "mcx_crudeoilm_experimental.json",
        _mcx_state(
            "CRUDEOILM",
            "POST_PRECISION_V4",
            "MCX_POST_PRECISION_V4",
            eligible=True,
            completed=[trade],
            counted=["C1"],
            wins=0,
            losses=1,
        ),
    )
    _write_jsonl(
        base / "mcx_crudeoilm_outcomes.jsonl",
        [
            {
                **trade,
                "epoch_id": "POST_PRECISION_V4",
                "strategy_version": "MCX_POST_PRECISION_V4",
                "certification_accepted": True,
            }
        ],
    )

    report = build_five_market_certification_final_report(tmp_path)
    crude = {item.market: item for item in report.markets}["CRUDEOILM"]

    assert crude.accepted_count == 1
    assert crude.sl_first_losses == 1
    assert crude.counted_id_count == 1
    assert crude.accepted_ledger_match_count == 1
    assert crude.accounting_integrity_pass is True
    assert crude.ledger_integrity_pass is True
    assert crude.final_verdict == "IN_PROGRESS"


def test_report_fails_closed_when_counted_trade_is_missing_from_ledger(tmp_path):
    _base_repo(tmp_path)
    base = tmp_path / "data/paper_trades"

    trade = {
        "trade_id": "N1",
        "first_touch_result": "T1_FIRST",
        "certification_countable": True,
        "certification_trade_date": "2026-10-05",
        "certification_regime": "TRENDING_UP",
        "certification_session_phase": "MORNING",
        "net_pnl": 100.0,
    }
    _write_json(
        base / "nifty_experimental.json",
        _index_state("NIFTY", [trade], ["N1"], 1, 0),
    )

    report = build_five_market_certification_final_report(tmp_path)
    nifty = {item.market: item for item in report.markets}["NIFTY"]

    assert nifty.accounting_integrity_pass is True
    assert nifty.ledger_integrity_pass is False
    assert nifty.final_verdict == "HOLD"


def test_exact_100_with_80_wins_and_diversity_is_pass(tmp_path):
    _base_repo(tmp_path)
    base = tmp_path / "data/paper_trades"

    trades = []
    ledger = []
    counted = []

    for i in range(100):
        tid = f"N{i:03d}"
        win = i < 80
        day = f"2026-10-{5 + (i % 5):02d}"
        regime = "TRENDING_UP" if i % 2 == 0 else "TRENDING_DOWN"
        phase = "MORNING" if i % 2 == 0 else "AFTERNOON"
        trade = {
            "trade_id": tid,
            "first_touch_result": "T1_FIRST" if win else "SL_FIRST",
            "certification_countable": True,
            "certification_trade_date": day,
            "certification_regime": regime,
            "certification_session_phase": phase,
            "net_pnl": 100.0 if win else -50.0,
        }
        trades.append(trade)
        counted.append(tid)
        ledger.append(
            {
                "trade_id": tid,
                "first_touch_result": trade["first_touch_result"],
                "certification_countable": True,
                "strategy_version": INDEX_VERSION,
                "certification_epoch": INDEX_EPOCH,
            }
        )

    _write_json(
        base / "nifty_experimental.json",
        _index_state("NIFTY", trades, counted, 80, 20),
    )
    _write_jsonl(base / "nifty_outcomes.jsonl", ledger)

    report = build_five_market_certification_final_report(tmp_path)
    nifty = {item.market: item for item in report.markets}["NIFTY"]

    assert nifty.accepted_count == 100
    assert nifty.t1_first_wins == 80
    assert nifty.sl_first_losses == 20
    assert nifty.distinct_certification_days == 5
    assert nifty.distinct_certification_regimes == 2
    assert nifty.distinct_certification_phases == 2
    assert nifty.maximum_accepted_per_day == 20
    assert nifty.diversity_pass is True
    assert nifty.final_verdict == "PASS"


def test_report_is_deterministic_and_paper_only(tmp_path):
    _base_repo(tmp_path)
    first = build_five_market_certification_final_report(tmp_path)
    second = build_five_market_certification_final_report(tmp_path)

    assert first.to_json() == second.to_json()
    assert first.semantic_hash == second.semantic_hash
    assert first.execution_mode == "PAPER"
    assert first.live_execution_eligible is False
    assert first.broker_order_submission is False
    assert first.read_only is True