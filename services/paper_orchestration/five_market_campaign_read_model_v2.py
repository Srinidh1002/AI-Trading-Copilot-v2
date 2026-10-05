"""Read-only five-market PAPER campaign projection for operator/dashboard use.

The projection deliberately separates operational accounting from certification
accounting. It performs no provider calls, no trading decisions, no state
mutation and no broker operations.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from services.paper_orchestration.state_authority_readonly_v2 import (
    validate_market,
)

MARKETS_V2 = ("NIFTY", "SENSEX", "CRUDEOILM", "GOLDM", "NATGASMINI")

_STATE_FILE = {
    "NIFTY": "nifty_experimental.json",
    "SENSEX": "sensex_experimental.json",
    "CRUDEOILM": "mcx_crudeoilm_experimental.json",
    "GOLDM": "mcx_goldm_experimental.json",
    "NATGASMINI": "mcx_natgasmini_experimental.json",
}


@dataclass(frozen=True, slots=True)
class MarketCampaignViewV2:
    market: str
    authority_status: str
    authority_reason: str
    strategy_version: str | None
    certification_epoch: str | None
    certification_eligible: bool | None
    certification_count: int | None
    certification_wins: int | None
    certification_losses: int | None
    counted_id_count: int | None
    operational_total_trades: int | None
    operational_wins: int | None
    operational_losses: int | None
    operational_total_pnl: float | None
    active_position_count: int | None
    completed_trade_count: int | None
    noncountable_completed_count: int | None
    ambiguous_completed_count: int | None
    latest_completed_trade_id: str | None
    latest_completed_first_touch: str | None
    latest_completed_net_pnl: float | None


@dataclass(frozen=True, slots=True)
class FiveMarketCampaignViewV2:
    generated_at: str
    execution_mode: str
    broker_submission: bool
    live_execution: bool
    markets: tuple[MarketCampaignViewV2, ...]


def _read_state(root: Path, market: str) -> dict:
    path = root / "data" / "paper_trades" / _STATE_FILE[market]
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("STATE_SCHEMA_INVALID")
    return payload


def _completed_metrics(completed) -> tuple[int, int, str | None, str | None, float | None]:
    if not isinstance(completed, list):
        completed = []

    noncountable = 0
    ambiguous = 0
    for trade in completed:
        if not isinstance(trade, dict):
            continue
        if trade.get("certification_countable") is False:
            noncountable += 1
        if str(trade.get("first_touch_result") or "").upper() == "AMBIGUOUS":
            ambiguous += 1

    latest = completed[-1] if completed and isinstance(completed[-1], dict) else {}
    net = latest.get("net_pnl") if latest else None
    try:
        net_value = float(net) if net is not None else None
    except (TypeError, ValueError):
        net_value = None

    return (
        noncountable,
        ambiguous,
        latest.get("trade_id") if latest else None,
        latest.get("first_touch_result") if latest else None,
        net_value,
    )


def _index_view(market: str, state: dict, authority) -> MarketCampaignViewV2:
    completed = state.get("completed_trades")
    if not isinstance(completed, list):
        completed = []

    active = state.get("active_trades")
    if not isinstance(active, list):
        active = []

    noncountable, ambiguous, latest_id, latest_ft, latest_pnl = _completed_metrics(
        completed
    )

    ids = state.get("counted_trade_ids")
    ids = ids if isinstance(ids, list) else []

    counter = int(state.get("certification_counter", 0) or 0)
    wins = int(state.get("certification_wins", 0) or 0)
    losses = int(state.get("certification_losses", 0) or 0)

    op_trades = state.get("total_trades")
    if not isinstance(op_trades, int):
        op_trades = len(completed)

    op_wins = state.get("winning_trades")
    op_losses = state.get("losing_trades")
    op_pnl = state.get("total_pnl")

    return MarketCampaignViewV2(
        market=market,
        authority_status="PASS",
        authority_reason=authority.reason,
        strategy_version=state.get("strategy_version"),
        certification_epoch=state.get("certification_epoch"),
        certification_eligible=True,
        certification_count=counter,
        certification_wins=wins,
        certification_losses=losses,
        counted_id_count=len(ids),
        operational_total_trades=int(op_trades or 0),
        operational_wins=int(op_wins or 0) if op_wins is not None else None,
        operational_losses=int(op_losses or 0) if op_losses is not None else None,
        operational_total_pnl=float(op_pnl or 0.0) if op_pnl is not None else None,
        active_position_count=len(active),
        completed_trade_count=len(completed),
        noncountable_completed_count=noncountable,
        ambiguous_completed_count=ambiguous,
        latest_completed_trade_id=latest_id,
        latest_completed_first_touch=latest_ft,
        latest_completed_net_pnl=latest_pnl,
    )


def _mcx_view(market: str, state: dict, authority) -> MarketCampaignViewV2:
    from mcx.mcx_version import get_product_epochs

    completed = state.get("completed_trades")
    if not isinstance(completed, list):
        completed = []

    noncountable, ambiguous, latest_id, latest_ft, latest_pnl = _completed_metrics(
        completed
    )

    ids = state.get("_counted_trade_ids")
    ids = ids if isinstance(ids, list) else []
    wins = int(state.get("t1_hit_wins", 0) or 0)
    losses = int(state.get("sl_losses", 0) or 0)
    cfg = get_product_epochs(market) or {}

    return MarketCampaignViewV2(
        market=market,
        authority_status="PASS",
        authority_reason=authority.reason,
        strategy_version=state.get("strategy_version"),
        certification_epoch=state.get("epoch"),
        certification_eligible=bool(cfg.get("certification_eligible", False)),
        certification_count=wins + losses,
        certification_wins=wins,
        certification_losses=losses,
        counted_id_count=len(ids),
        operational_total_trades=int(state.get("total_trades", 0) or 0),
        operational_wins=int(state.get("winning_trades", 0) or 0),
        operational_losses=int(state.get("losing_trades", 0) or 0),
        operational_total_pnl=float(state.get("total_pnl", 0.0) or 0.0),
        active_position_count=1 if state.get("active_position") is not None else 0,
        completed_trade_count=len(completed),
        noncountable_completed_count=noncountable,
        ambiguous_completed_count=ambiguous,
        latest_completed_trade_id=latest_id,
        latest_completed_first_touch=latest_ft,
        latest_completed_net_pnl=latest_pnl,
    )


def _hold_view(market: str, reason: str) -> MarketCampaignViewV2:
    return MarketCampaignViewV2(
        market=market,
        authority_status="HOLD",
        authority_reason=reason,
        strategy_version=None,
        certification_epoch=None,
        certification_eligible=None,
        certification_count=None,
        certification_wins=None,
        certification_losses=None,
        counted_id_count=None,
        operational_total_trades=None,
        operational_wins=None,
        operational_losses=None,
        operational_total_pnl=None,
        active_position_count=None,
        completed_trade_count=None,
        noncountable_completed_count=None,
        ambiguous_completed_count=None,
        latest_completed_trade_id=None,
        latest_completed_first_touch=None,
        latest_completed_net_pnl=None,
    )


def build_five_market_campaign_view_v2(
    repo_root: str | Path,
) -> FiveMarketCampaignViewV2:
    root = Path(repo_root).resolve()
    views: list[MarketCampaignViewV2] = []

    for market in MARKETS_V2:
        authority = validate_market(root, market)
        if not authority.ok:
            views.append(_hold_view(market, authority.reason))
            continue
        try:
            state = _read_state(root, market)
            if market in {"NIFTY", "SENSEX"}:
                view = _index_view(market, state, authority)
            else:
                view = _mcx_view(market, state, authority)
        except Exception as exc:
            views.append(_hold_view(market, f"READ_MODEL_ERROR:{type(exc).__name__}"))
            continue
        views.append(view)

    return FiveMarketCampaignViewV2(
        generated_at=datetime.now(UTC).isoformat(),
        execution_mode="PAPER",
        broker_submission=False,
        live_execution=False,
        markets=tuple(views),
    )
