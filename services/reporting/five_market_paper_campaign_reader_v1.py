"""Read-only builder for the active five-market PAPER campaign view."""
from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path

from services.dashboard_read_models.five_market_paper_campaign_view_v1 import (
    FiveMarketPaperCampaignViewV1,
    FiveMarketPaperMarketViewV1,
)
from src.mcx.mcx_version import get_product_epochs


_MARKETS = ("NIFTY", "SENSEX", "CRUDEOILM", "GOLDM", "NATGASMINI")


class FiveMarketPaperCampaignReadError(RuntimeError):
    """Campaign state cannot be read safely."""


def _load(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise FiveMarketPaperCampaignReadError(
            f"STATE_READ_FAILED:{path.name}:{type(exc).__name__}"
        ) from exc
    if not isinstance(value, dict):
        raise FiveMarketPaperCampaignReadError(
            f"STATE_SCHEMA_INVALID:{path.name}"
        )
    return value


def _trade_sequence(value: object) -> tuple[Mapping[str, object], ...]:
    if value is None:
        return ()
    if isinstance(value, Mapping):
        raw = value.values()
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        raw = value
    else:
        return ()
    return tuple(item for item in raw if isinstance(item, Mapping))


def _trade_pnl(trade: Mapping[str, object]) -> float:
    for key in ("net_pnl", "pnl"):
        value = trade.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return 0.0


def _first_touch_counts(
    trades: tuple[Mapping[str, object], ...],
) -> tuple[int, int]:
    ambiguous = 0
    unresolved = 0
    for trade in trades:
        value = str(
            trade.get("first_touch_result") or ""
        ).strip().upper()
        if value == "AMBIGUOUS":
            ambiguous += 1
        elif value in {"", "NONE"}:
            unresolved += 1
    return ambiguous, unresolved


def _active_details(
    trades: tuple[Mapping[str, object], ...],
) -> tuple[int, str | None, str | None]:
    if not trades:
        return 0, None, None
    first = trades[0]
    return (
        len(trades),
        str(first.get("trade_id") or "").strip() or None,
        str(first.get("first_touch_result") or "").strip().upper() or None,
    )


def _safety_warnings(
    trades: tuple[Mapping[str, object], ...],
) -> tuple[str, ...]:
    warnings: list[str] = []
    for trade in trades:
        tid = str(trade.get("trade_id") or "UNKNOWN")
        mode = trade.get("execution_mode")
        broker = trade.get("broker_submission")
        live = trade.get("live_execution")
        if mode not in (None, "PAPER"):
            warnings.append(f"NON_PAPER_TRADE:{tid}")
        if broker not in (None, False):
            warnings.append(f"BROKER_SUBMISSION_TRUE:{tid}")
        if live not in (None, False):
            warnings.append(f"LIVE_EXECUTION_TRUE:{tid}")
    return tuple(dict.fromkeys(warnings))


def _index_view(root: Path, market: str) -> FiveMarketPaperMarketViewV1:
    state = _load(
        root
        / "data"
        / "paper_trades"
        / f"{market.lower()}_experimental.json"
    )
    completed = _trade_sequence(state.get("completed_trades"))
    active = _trade_sequence(state.get("active_trades"))
    counted_ids = tuple(
        str(item)
        for item in (state.get("counted_trade_ids") or ())
        if str(item)
    )
    counter = int(state.get("certification_counter", 0) or 0)
    wins = int(state.get("certification_wins", 0) or 0)
    losses = int(state.get("certification_losses", 0) or 0)

    if counter != wins + losses or counter != len(counted_ids):
        raise FiveMarketPaperCampaignReadError(
            f"INDEX_COUNTER_INCOHERENT:{market}"
        )
    if len(set(counted_ids)) != len(counted_ids):
        raise FiveMarketPaperCampaignReadError(
            f"INDEX_COUNTED_ID_DUPLICATE:{market}"
        )

    completed_by_id = {
        str(item.get("trade_id")): item
        for item in completed
        if item.get("trade_id")
    }
    if any(tid not in completed_by_id for tid in counted_ids):
        raise FiveMarketPaperCampaignReadError(
            f"INDEX_COUNTED_ID_NOT_COMPLETED:{market}"
        )

    operational_wins = sum(_trade_pnl(item) > 0 for item in completed)
    operational_losses = sum(_trade_pnl(item) < 0 for item in completed)
    operational_pnl = sum(_trade_pnl(item) for item in completed)
    noncountable = sum(
        1
        for item in completed
        if str(item.get("trade_id") or "") not in set(counted_ids)
    )
    ambiguous, unresolved = _first_touch_counts(completed)
    active_count, active_id, first_touch = _active_details(active)
    warnings = list(_safety_warnings(completed + active))

    if state.get("certification_eligible") is None:
        warnings.append("STATE_CERTIFICATION_ELIGIBILITY_NOT_EXPLICIT")

    return FiveMarketPaperMarketViewV1(
        market=market,
        strategy_version=str(state.get("strategy_version") or ""),
        certification_epoch=str(state.get("certification_epoch") or ""),
        certification_eligible=bool(
            state.get("certification_eligible", True)
        ),
        certification_counter=counter,
        certification_wins=wins,
        certification_losses=losses,
        target_trade_count=100,
        operational_completed_trades=len(completed),
        operational_wins=operational_wins,
        operational_losses=operational_losses,
        operational_net_pnl=operational_pnl,
        noncountable_completed_trades=noncountable,
        ambiguous_completed_trades=ambiguous,
        unresolved_first_touch_completed_trades=unresolved,
        active_position_count=active_count,
        active_trade_id=active_id,
        active_first_touch=first_touch,
        source_schema="INDEX_EXPERIMENTAL_V3",
        warnings=tuple(warnings),
    )


def _mcx_view(root: Path, market: str) -> FiveMarketPaperMarketViewV1:
    state = _load(
        root
        / "data"
        / "paper_trades"
        / f"mcx_{market.lower()}_experimental.json"
    )
    registry = get_product_epochs(market) or {}
    if not registry:
        raise FiveMarketPaperCampaignReadError(
            f"MCX_REGISTRY_MISSING:{market}"
        )
    if state.get("epoch") != registry.get("epoch"):
        raise FiveMarketPaperCampaignReadError(
            f"MCX_EPOCH_MISMATCH:{market}"
        )
    if state.get("strategy_version") != registry.get("strategy_version"):
        raise FiveMarketPaperCampaignReadError(
            f"MCX_VERSION_MISMATCH:{market}"
        )

    wins = int(state.get("t1_hit_wins", 0) or 0)
    losses = int(state.get("sl_losses", 0) or 0)
    counter = wins + losses
    counted_ids = tuple(
        str(item)
        for item in (state.get("_counted_trade_ids") or ())
        if str(item)
    )
    if counter != len(counted_ids):
        raise FiveMarketPaperCampaignReadError(
            f"MCX_COUNTER_INCOHERENT:{market}"
        )
    if len(set(counted_ids)) != len(counted_ids):
        raise FiveMarketPaperCampaignReadError(
            f"MCX_COUNTED_ID_DUPLICATE:{market}"
        )

    completed = _trade_sequence(state.get("completed_trades"))
    active = _trade_sequence(
        (state.get("active_position"),)
        if state.get("active_position") is not None
        else ()
    )
    completed_ids = {
        str(item.get("trade_id"))
        for item in completed
        if item.get("trade_id")
    }
    if any(tid not in completed_ids for tid in counted_ids):
        raise FiveMarketPaperCampaignReadError(
            f"MCX_COUNTED_ID_NOT_COMPLETED:{market}"
        )

    operational_total = int(state.get("total_trades", len(completed)) or 0)
    operational_wins = int(state.get("winning_trades", 0) or 0)
    operational_losses = int(state.get("losing_trades", 0) or 0)
    operational_pnl = float(state.get("total_pnl", 0.0) or 0.0)
    if operational_total != len(completed):
        # State may preserve a historical operational aggregate separately.
        # Retain the aggregate but surface the distinction instead of rewriting.
        aggregate_warning = (
            f"OPERATIONAL_TOTAL_DIFFERS_FROM_COMPLETED:"
            f"{operational_total}!={len(completed)}"
        )
    else:
        aggregate_warning = None

    noncountable = max(0, len(completed) - counter)
    ambiguous, unresolved = _first_touch_counts(completed)
    active_count, active_id, first_touch = _active_details(active)
    warnings = list(_safety_warnings(completed + active))
    if aggregate_warning:
        warnings.append(aggregate_warning)

    registry_eligible = bool(registry.get("certification_eligible", False))
    state_eligible = state.get("certification_eligible")
    if state_eligible is not None and bool(state_eligible) != registry_eligible:
        warnings.append(
            "STATE_CERTIFICATION_ELIGIBILITY_STALE_NONAUTHORITATIVE"
        )

    return FiveMarketPaperMarketViewV1(
        market=market,
        strategy_version=str(registry.get("strategy_version") or ""),
        certification_epoch=str(registry.get("epoch") or ""),
        certification_eligible=registry_eligible,
        certification_counter=counter,
        certification_wins=wins,
        certification_losses=losses,
        target_trade_count=100,
        operational_completed_trades=operational_total,
        operational_wins=operational_wins,
        operational_losses=operational_losses,
        operational_net_pnl=operational_pnl,
        noncountable_completed_trades=noncountable,
        active_position_count=active_count,
        active_trade_id=active_id,
        active_first_touch=first_touch,
        source_schema="MCX_EXPERIMENTAL_V4",
        warnings=tuple(warnings),
    )


def _release_commit(root: Path) -> str:
    try:
        value = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except Exception as exc:
        raise FiveMarketPaperCampaignReadError(
            "RELEASE_COMMIT_UNAVAILABLE"
        ) from exc
    if not value:
        raise FiveMarketPaperCampaignReadError(
            "RELEASE_COMMIT_UNAVAILABLE"
        )
    return value


def build_five_market_paper_campaign_view_v1(
    repo_root: str | Path,
    *,
    generated_at: datetime | None = None,
    release_commit: str | None = None,
) -> FiveMarketPaperCampaignViewV1:
    """Read all five current campaign states without mutating any file."""
    root = Path(repo_root).resolve()
    now = generated_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("generated_at must be timezone-aware")

    markets = (
        _index_view(root, "NIFTY"),
        _index_view(root, "SENSEX"),
        _mcx_view(root, "CRUDEOILM"),
        _mcx_view(root, "GOLDM"),
        _mcx_view(root, "NATGASMINI"),
    )

    return FiveMarketPaperCampaignViewV1(
        generated_at=now,
        release_commit=release_commit or _release_commit(root),
        markets=markets,
    )
