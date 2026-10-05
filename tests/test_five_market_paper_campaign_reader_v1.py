from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from services.reporting.five_market_paper_campaign_reader_v1 import (
    FiveMarketPaperCampaignReadError,
    build_five_market_paper_campaign_view_v1,
)


NOW = datetime(2026, 10, 5, 10, 30, tzinfo=timezone.utc)


def _write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _index_state(market: str):
    return {
        "strategy_version": "NS_DESIGN_B_BID_AUTH_V3",
        "certification_epoch": "NS_CERT_20260916_V3",
        "certification_counter": 1 if market == "NIFTY" else 0,
        "certification_wins": 1 if market == "NIFTY" else 0,
        "certification_losses": 0,
        "counted_trade_ids": (
            ["nifty-counted"] if market == "NIFTY" else []
        ),
        "active_trades": (
            []
            if market == "NIFTY"
            else [
                {
                    "trade_id": "sensex-active",
                    "first_touch_result": "AMBIGUOUS",
                    "execution_mode": "PAPER",
                    "broker_submission": False,
                    "live_execution": False,
                }
            ]
        ),
        "completed_trades": (
            [
                {
                    "trade_id": "nifty-ambiguous",
                    "first_touch_result": "AMBIGUOUS",
                    "certification_countable": False,
                    "net_pnl": -100.0,
                    "execution_mode": "PAPER",
                    "broker_submission": False,
                    "live_execution": False,
                },
                {
                    "trade_id": "nifty-counted",
                    "first_touch_result": "T1_FIRST",
                    "certification_countable": True,
                    "net_pnl": 200.0,
                    "execution_mode": "PAPER",
                    "broker_submission": False,
                    "live_execution": False,
                },
            ]
            if market == "NIFTY"
            else []
        ),
    }


def _mcx_state(market: str, *, state_eligible=True):
    versions = {
        "CRUDEOILM": ("MCX_POST_PRECISION_V4", "POST_PRECISION_V4"),
        "GOLDM": ("MCX_GOLDM_PRECERT_V2", "GOLDM_PRECERT_V2"),
        "NATGASMINI": (
            "MCX_NATGASMINI_PRECERT_V1",
            "NATGASMINI_PRECERT_V1",
        ),
    }
    strategy, epoch = versions[market]
    return {
        "product": market,
        "epoch": epoch,
        "strategy_version": strategy,
        "certification_eligible": state_eligible,
        "total_trades": 0,
        "winning_trades": 0,
        "losing_trades": 0,
        "t1_hit_wins": 0,
        "sl_losses": 0,
        "total_pnl": 0.0,
        "active_position": None,
        "completed_trades": [],
    }


def _repo(tmp_path: Path):
    base = tmp_path / "data" / "paper_trades"
    _write(base / "nifty_experimental.json", _index_state("NIFTY"))
    _write(base / "sensex_experimental.json", _index_state("SENSEX"))
    _write(
        base / "mcx_crudeoilm_experimental.json",
        _mcx_state("CRUDEOILM"),
    )
    _write(
        base / "mcx_goldm_experimental.json",
        _mcx_state("GOLDM"),
    )
    _write(
        base / "mcx_natgasmini_experimental.json",
        _mcx_state("NATGASMINI", state_eligible=False),
    )
    return tmp_path


def test_five_market_view_separates_operational_and_certification(tmp_path):
    root = _repo(tmp_path)

    view = build_five_market_paper_campaign_view_v1(
        root,
        generated_at=NOW,
        release_commit="99cf",
    )
    by_market = view.by_market()

    nifty = by_market["NIFTY"]
    assert nifty.certification_counter == 1
    assert nifty.operational_completed_trades == 2
    assert nifty.noncountable_completed_trades == 1
    assert nifty.ambiguous_completed_trades == 1
    assert nifty.unresolved_first_touch_completed_trades == 0
    assert nifty.ambiguity_rate_percent == 50.0
    assert nifty.operational_net_pnl == 100.0

    sensex = by_market["SENSEX"]
    assert sensex.active_position_count == 1
    assert sensex.active_first_touch == "AMBIGUOUS"
    assert sensex.certification_counter == 0


def test_natgas_registry_authority_overrides_stale_state_flag(tmp_path):
    root = _repo(tmp_path)

    view = build_five_market_paper_campaign_view_v1(
        root,
        generated_at=NOW,
        release_commit="99cf",
    )
    natgas = view.by_market()["NATGASMINI"]

    assert natgas.certification_eligible is True
    assert (
        "STATE_CERTIFICATION_ELIGIBILITY_STALE_NONAUTHORITATIVE"
        in natgas.warnings
    )


def test_index_counter_mismatch_fails_closed(tmp_path):
    root = _repo(tmp_path)
    path = (
        root
        / "data"
        / "paper_trades"
        / "nifty_experimental.json"
    )
    value = json.loads(path.read_text(encoding="utf-8"))
    value["certification_counter"] = 2
    _write(path, value)

    with pytest.raises(
        FiveMarketPaperCampaignReadError,
        match="INDEX_COUNTER_INCOHERENT",
    ):
        build_five_market_paper_campaign_view_v1(
            root,
            generated_at=NOW,
            release_commit="99cf",
        )


def test_mcx_counter_id_mismatch_fails_closed(tmp_path):
    root = _repo(tmp_path)
    path = (
        root
        / "data"
        / "paper_trades"
        / "mcx_goldm_experimental.json"
    )
    value = json.loads(path.read_text(encoding="utf-8"))
    value["t1_hit_wins"] = 1
    _write(path, value)

    with pytest.raises(
        FiveMarketPaperCampaignReadError,
        match="MCX_COUNTER_INCOHERENT",
    ):
        build_five_market_paper_campaign_view_v1(
            root,
            generated_at=NOW,
            release_commit="99cf",
        )


def test_view_is_paper_only_and_read_only(tmp_path):
    view = build_five_market_paper_campaign_view_v1(
        _repo(tmp_path),
        generated_at=NOW,
        release_commit="99cf",
    )
    assert view.execution_mode == "PAPER"
    assert view.live_broker_orders_prohibited is True
    assert view.live_capital_prohibited is True
    assert view.read_only is True
