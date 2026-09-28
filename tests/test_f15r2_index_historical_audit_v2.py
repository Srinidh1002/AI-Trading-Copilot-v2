"""F15-R2 Phase R2-16 — index historical integrity audit.

Fixtures mirror the 2026-09-28 NIFTY/SENSEX ledger shape exactly.
The specific row TRD_20260928_145859 predates the R2-2 fix, so its
outcome row still carries certification_countable=True even though
the counter did not accept it. R2-16 classifies this read-only.

No live data touched. No counter mutation. No ledger rewrite.
"""
from __future__ import annotations

import json
from datetime import date

from services.paper_orchestration.campaign_analysis_v2 import (
    analyze_market_day,
)

DAY = date(2026, 9, 28)
DAY_ISO = "2026-09-28"


def _seed(tmp_path, market, pred_rows, out_rows, state):
    d = tmp_path / "data" / "paper_trades"
    d.mkdir(parents=True, exist_ok=True)
    prefix = "mcx_" if market in ("CRUDEOILM", "GOLDM", "NATGASMINI") else ""
    lower = market.lower()
    (d / f"{prefix}{lower}_predictions.jsonl").write_text(
        "\n".join(json.dumps(r) for r in pred_rows) + "\n", encoding="utf-8"
    )
    (d / f"{prefix}{lower}_outcomes.jsonl").write_text(
        "\n".join(json.dumps(r) for r in out_rows) + "\n", encoding="utf-8"
    )
    (d / f"{prefix}{lower}_experimental.json").write_text(
        json.dumps(state), encoding="utf-8"
    )


# --- NIFTY fixture: 5 raw closes, 2 candidate rows, 1 authoritative ---
NIFTY_OUT = [
    # non-candidate, counted (accepted pre-fix: SL_FIRST)
    {"trade_id": "TRD_20260928_113315", "timestamp": f"{DAY_ISO}T11:33:15",
     "net_pnl": 0.0, "first_touch_result": "SL_FIRST",
     "certification_countable": True, "certification_win": False,
     "certification_loss": True, "certification_trade_date": DAY_ISO},
    # non-candidate, not counted
    {"trade_id": "TRD_20260928_124043", "timestamp": f"{DAY_ISO}T14:21:10",
     "net_pnl": 1395.64, "first_touch_result": "T1_FIRST",
     "certification_countable": False, "certification_win": True,
     "certification_loss": False, "certification_trade_date": DAY_ISO},
    # non-candidate, not counted (AMBIGUOUS)
    {"trade_id": "TRD_20260928_142613", "timestamp": f"{DAY_ISO}T14:53:54",
     "net_pnl": -620.58, "first_touch_result": "AMBIGUOUS",
     "certification_countable": False, "certification_win": False,
     "certification_loss": False, "evidence_ambiguous": True,
     "certification_trade_date": DAY_ISO},
    # THE F1 row: candidate=True in row, NOT in counted_ids (pre-fix)
    {"trade_id": "TRD_20260928_145859", "timestamp": f"{DAY_ISO}T15:28:02",
     "net_pnl": -194.52, "first_touch_result": "NONE",
     "certification_countable": True, "certification_win": False,
     "certification_loss": False, "certification_trade_date": DAY_ISO},
    # non-candidate, not counted
    {"trade_id": "TRD_20260928_150000", "timestamp": f"{DAY_ISO}T15:00:00",
     "net_pnl": 300.0, "first_touch_result": "NONE",
     "certification_countable": False, "certification_win": False,
     "certification_loss": False, "certification_trade_date": DAY_ISO},
]

NIFTY_STATE = {
    "market": "NIFTY",
    "certification_counter": 4,
    "certification_wins": 0,
    "certification_losses": 4,
    "counted_trade_ids": [
        "TRD_20260923_130132",
        "TRD_20260923_143054",
        "TRD_20260923_144243",
        "TRD_20260928_113315",
    ],
    "active_trades": [],
    "orphaned_trades": [],
}


def test_nifty_discrepancy_is_visible_and_preserved(tmp_path):
    _seed(tmp_path, "NIFTY", [], NIFTY_OUT, NIFTY_STATE)
    s = analyze_market_day(
        market="NIFTY", day=DAY, repo_root=str(tmp_path)
    )
    # 5 raw closed
    assert s["outcomes_today"] == 5
    # row candidate count (from R2-5 summary): 2 rows with countable=True
    assert s["certification_countable"] == 2
    # counter unchanged, still 4
    assert s["counter"] == 4


def test_authoritative_accepted_uses_counted_ids_not_row_flag(tmp_path):
    _seed(tmp_path, "NIFTY", [], NIFTY_OUT, NIFTY_STATE)
    st = json.loads(
        (tmp_path / "data" / "paper_trades" / "nifty_experimental.json")
        .read_text(encoding="utf-8")
    )
    counted = set(st["counted_trade_ids"])
    today_rows = [r for r in NIFTY_OUT
                  if r.get("certification_trade_date") == DAY_ISO]
    accepted_today = [r for r in today_rows if r["trade_id"] in counted]
    assert len(accepted_today) == 1
    assert accepted_today[0]["trade_id"] == "TRD_20260928_113315"


def test_f1_row_is_exactly_the_one_discrepancy(tmp_path):
    _seed(tmp_path, "NIFTY", [], NIFTY_OUT, NIFTY_STATE)
    counted = set(NIFTY_STATE["counted_trade_ids"])
    today = [r for r in NIFTY_OUT
             if r.get("certification_trade_date") == DAY_ISO]
    discrepancy = [
        r for r in today
        if r.get("certification_countable") is True
        and r["trade_id"] not in counted
    ]
    assert len(discrepancy) == 1
    d = discrepancy[0]
    assert d["trade_id"] == "TRD_20260928_145859"
    assert d["first_touch_result"] == "NONE"


def test_no_reverse_discrepancy(tmp_path):
    """Every counted row is also marked candidate=True in the fixture."""
    counted = set(NIFTY_STATE["counted_trade_ids"])
    reverse = [
        r for r in NIFTY_OUT
        if r["trade_id"] in counted
        and r.get("certification_countable") is not True
    ]
    assert reverse == []


# --- SENSEX fixture: 5 raw closes, 3 candidate rows, 3 authoritative ---
SENSEX_OUT = [
    {"trade_id": "TRD_20260928_095648", "timestamp": f"{DAY_ISO}T09:56:48",
     "net_pnl": -462.83, "first_touch_result": "SL_FIRST",
     "certification_countable": True, "certification_win": False,
     "certification_loss": True, "certification_trade_date": DAY_ISO},
    {"trade_id": "TRD_20260928_105204", "timestamp": f"{DAY_ISO}T10:55:46",
     "net_pnl": -474.47, "first_touch_result": "SL_FIRST",
     "certification_countable": True, "certification_win": False,
     "certification_loss": True, "certification_trade_date": DAY_ISO},
    {"trade_id": "TRD_20260928_110121", "timestamp": f"{DAY_ISO}T11:30:25",
     "net_pnl": -474.47, "first_touch_result": "SL_FIRST",
     "certification_countable": True, "certification_win": False,
     "certification_loss": True, "certification_trade_date": DAY_ISO},
    {"trade_id": "TRD_20260928_114558", "timestamp": f"{DAY_ISO}T12:30:01",
     "net_pnl": -493.0, "first_touch_result": "AMBIGUOUS",
     "certification_countable": False, "evidence_ambiguous": True,
     "certification_trade_date": DAY_ISO},
    {"trade_id": "TRD_20260928_140000", "timestamp": f"{DAY_ISO}T14:00:00",
     "net_pnl": 200.0, "first_touch_result": "NONE",
     "certification_countable": False,
     "certification_trade_date": DAY_ISO},
]

SENSEX_STATE = {
    "market": "SENSEX",
    "certification_counter": 5,
    "certification_wins": 0,
    "certification_losses": 5,
    "counted_trade_ids": [
        "TRD_20260923_133405",
        "TRD_20260923_134130",
        "TRD_20260928_095648",
        "TRD_20260928_105204",
        "TRD_20260928_110121",
    ],
    "active_trades": [],
    "orphaned_trades": [],
}


def test_sensex_has_no_discrepancy(tmp_path):
    _seed(tmp_path, "SENSEX", [], SENSEX_OUT, SENSEX_STATE)
    counted = set(SENSEX_STATE["counted_trade_ids"])
    today = [r for r in SENSEX_OUT
             if r.get("certification_trade_date") == DAY_ISO]
    discrepancy = [
        r for r in today
        if r.get("certification_countable") is True
        and r["trade_id"] not in counted
    ]
    assert discrepancy == []
    s = analyze_market_day(
        market="SENSEX", day=DAY, repo_root=str(tmp_path)
    )
    assert s["outcomes_today"] == 5
    assert s["certification_countable"] == 3
    assert s["counter"] == 5


def test_counter_matches_counted_ids_for_both_markets(tmp_path):
    _seed(tmp_path, "NIFTY", [], NIFTY_OUT, NIFTY_STATE)
    _seed(tmp_path, "SENSEX", [], SENSEX_OUT, SENSEX_STATE)
    for mk, expected in (("NIFTY", 4), ("SENSEX", 5)):
        st = json.loads(
            (tmp_path / "data" / "paper_trades" / f"{mk.lower()}_experimental.json")
            .read_text(encoding="utf-8")
        )
        assert st["certification_counter"] == expected
        assert len(st["counted_trade_ids"]) == expected
