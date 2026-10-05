from __future__ import annotations

import json
from pathlib import Path

from dashboard.five_market_campaign_sync_v2 import (
    FIVE_MARKET_CAMPAIGN_VIEW_STATE_KEY,
    get_five_market_campaign_view,
    synchronize_five_market_campaign_projection,
)
from services.paper_orchestration.five_market_campaign_read_model_v2 import (
    FiveMarketCampaignViewV2,
    build_five_market_campaign_view_v2,
)


def _write(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _index_state(market: str, *, counter=0, wins=0, losses=0, completed=None):
    completed = list(completed or [])
    counted = [
        t["trade_id"]
        for t in completed
        if t.get("certification_countable") is True
    ][:counter]
    return {
        "market": market,
        "strategy_version": "NS_DESIGN_B_BID_AUTH_V3",
        "certification_epoch": "NS_CERT_20260916_V3",
        "certification_counter": counter,
        "certification_wins": wins,
        "certification_losses": losses,
        "counted_trade_ids": counted,
        "active_trades": [],
        "completed_trades": completed,
        "total_trades": len(completed),
        "winning_trades": sum(1 for t in completed if (t.get("net_pnl") or 0) > 0),
        "losing_trades": sum(1 for t in completed if (t.get("net_pnl") or 0) < 0),
        "total_pnl": sum(float(t.get("net_pnl") or 0) for t in completed),
    }


def _mcx_state(
    product: str,
    epoch: str,
    strategy: str,
    *,
    eligible: bool,
    wins=0,
    losses=0,
    completed=None,
):
    completed = list(completed or [])
    counted = [
        t["trade_id"]
        for t in completed
        if t.get("certification_accepted") is True
    ]
    payload = {
        "product": product,
        "epoch": epoch,
        "strategy_version": strategy,
        "certification_eligible": eligible,
        "t1_hit_wins": wins,
        "sl_losses": losses,
        "total_trades": len(completed),
        "winning_trades": sum(1 for t in completed if (t.get("net_pnl") or 0) > 0),
        "losing_trades": sum(1 for t in completed if (t.get("net_pnl") or 0) < 0),
        "total_pnl": sum(float(t.get("net_pnl") or 0) for t in completed),
        "active_position": None,
        "completed_trades": completed,
    }
    if counted:
        payload["_counted_trade_ids"] = counted
    return payload


def _build_repo(root: Path):
    base = root / "data/paper_trades"

    nifty_completed = [
        {
            "trade_id": "N1",
            "first_touch_result": "T1_FIRST",
            "certification_countable": True,
            "net_pnl": 653.43,
        },
        {
            "trade_id": "N2",
            "first_touch_result": "AMBIGUOUS",
            "certification_countable": False,
            "net_pnl": -461.76,
        },
    ]
    _write(
        base / "nifty_experimental.json",
        _index_state(
            "NIFTY",
            counter=1,
            wins=1,
            losses=0,
            completed=nifty_completed,
        ),
    )
    _write(base / "sensex_experimental.json", _index_state("SENSEX"))

    crude_completed = [
        {
            "trade_id": "C1",
            "first_touch_result": "SL_FIRST",
            "certification_countable": True,
            "certification_accepted": True,
            "net_pnl": -100.0,
        }
    ]
    _write(
        base / "mcx_crudeoilm_experimental.json",
        _mcx_state(
            "CRUDEOILM",
            "POST_PRECISION_V4",
            "MCX_POST_PRECISION_V4",
            eligible=True,
            wins=0,
            losses=1,
            completed=crude_completed,
        ),
    )
    _write(
        base / "mcx_goldm_experimental.json",
        _mcx_state(
            "GOLDM",
            "GOLDM_PRECERT_V2",
            "MCX_GOLDM_PRECERT_V2",
            eligible=True,
        ),
    )
    # State metadata is intentionally stale; product registry is authoritative.
    _write(
        base / "mcx_natgasmini_experimental.json",
        _mcx_state(
            "NATGASMINI",
            "NATGASMINI_PRECERT_V1",
            "MCX_NATGASMINI_PRECERT_V1",
            eligible=False,
        ),
    )


def test_five_market_view_separates_operational_and_certification(tmp_path):
    _build_repo(tmp_path)

    view = build_five_market_campaign_view_v2(tmp_path)
    by_market = {m.market: m for m in view.markets}

    nifty = by_market["NIFTY"]
    assert nifty.authority_status == "PASS"
    assert nifty.certification_count == 1
    assert nifty.certification_wins == 1
    assert nifty.counted_id_count == 1
    assert nifty.operational_total_trades == 2
    assert nifty.completed_trade_count == 2
    assert nifty.noncountable_completed_count == 1
    assert nifty.ambiguous_completed_count == 1
    assert nifty.operational_total_pnl == 191.67

    crude = by_market["CRUDEOILM"]
    assert crude.certification_count == 1
    assert crude.certification_losses == 1
    assert crude.operational_total_trades == 1
    assert crude.operational_total_pnl == -100.0

    natgas = by_market["NATGASMINI"]
    assert natgas.certification_eligible is True


def test_projection_sync_is_read_only_and_typed(tmp_path):
    _build_repo(tmp_path)
    state_path = tmp_path / "data/paper_trades/nifty_experimental.json"
    before = state_path.read_bytes()

    session_state = {}
    projected = synchronize_five_market_campaign_projection(
        session_state,
        repo_root=tmp_path,
    )

    assert type(projected) is FiveMarketCampaignViewV2
    assert session_state[FIVE_MARKET_CAMPAIGN_VIEW_STATE_KEY] is projected
    assert get_five_market_campaign_view(session_state) is projected
    assert state_path.read_bytes() == before


def test_invalid_authority_is_exposed_as_hold_not_zero(tmp_path):
    _build_repo(tmp_path)
    state_path = tmp_path / "data/paper_trades/sensex_experimental.json"
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    payload["certification_counter"] = 2
    payload["counted_trade_ids"] = []
    _write(state_path, payload)

    view = build_five_market_campaign_view_v2(tmp_path)
    sensex = {m.market: m for m in view.markets}["SENSEX"]

    assert sensex.authority_status == "HOLD"
    assert sensex.certification_count is None
    assert sensex.authority_reason == "STATE_COUNTER_INCOHERENT"
