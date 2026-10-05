"""Read-only final/in-progress five-market PAPER certification report builder."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from services.contracts.five_market_certification_report_v1 import (
    FiveMarketCertificationMarketReportV1,
    FiveMarketCertificationReportV1,
)
from services.reporting.five_market_paper_campaign_reader_v1 import (
    build_five_market_paper_campaign_view_v1,
)
from src.diversity_tracker import (
    DIVERSITY_MAX_PER_DAY,
    DIVERSITY_MIN_DAYS,
    DIVERSITY_MIN_PHASES,
    DIVERSITY_MIN_REGIMES,
)
from src.mcx.mcx_version import get_product_epochs


class FiveMarketCertificationReportError(RuntimeError):
    """Certification report authority could not be reconciled."""


def _state(root: Path, filename: str) -> dict[str, object]:
    path = root / "data" / "paper_trades" / filename
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise FiveMarketCertificationReportError(
            f"STATE_READ_FAILED:{filename}:{type(exc).__name__}"
        ) from exc
    if not isinstance(value, dict):
        raise FiveMarketCertificationReportError(
            f"STATE_SCHEMA_INVALID:{filename}"
        )
    return value


def _ledger_rows(root: Path, filename: str) -> tuple[dict[str, object], ...]:
    path = root / "data" / "paper_trades" / filename
    if not path.is_file():
        return ()
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except Exception as exc:
            raise FiveMarketCertificationReportError(
                f"LEDGER_JSON_INVALID:{filename}"
            ) from exc
        if not isinstance(item, dict):
            raise FiveMarketCertificationReportError(
                f"LEDGER_ROW_INVALID:{filename}"
            )
        rows.append(item)
    return tuple(rows)


def _diversity(
    trades: tuple[dict[str, object], ...],
    *,
    index_market: bool,
) -> tuple[int, int, int, int, bool]:
    days: set[str] = set()
    regimes: set[str] = set()
    phases: set[str] = set()
    per_day: Counter[str] = Counter()

    for trade in trades:
        if index_market:
            day = str(trade.get("certification_trade_date") or "").strip()
            regime = str(trade.get("certification_regime") or "").strip()
            phase = str(
                trade.get("certification_session_phase") or ""
            ).strip()
        else:
            entry_time = str(trade.get("entry_time") or "").strip()
            day = entry_time[:10]
            regime = str(trade.get("regime_at_entry") or "").strip()
            hour = entry_time[11:13]
            phase = ""
            if len(hour) == 2 and hour.isdigit():
                phase = "MORNING" if int(hour) < 17 else "EVENING"

        if day:
            days.add(day)
            per_day[day] += 1
        if regime and regime != "UNKNOWN":
            regimes.add(regime)
        if phase and phase != "UNKNOWN":
            phases.add(phase)

    max_per_day = max(per_day.values(), default=0)
    passed = (
        len(days) >= DIVERSITY_MIN_DAYS
        and len(regimes) >= DIVERSITY_MIN_REGIMES
        and len(phases) >= DIVERSITY_MIN_PHASES
        and max_per_day <= DIVERSITY_MAX_PER_DAY
    )
    return (
        len(days),
        len(regimes),
        len(phases),
        max_per_day,
        passed,
    )


def _status(
    *,
    accepted: int,
    wins: int,
    diversity_pass: bool,
    integrity: bool,
    ledger_ok: bool,
) -> tuple[str, bool]:
    accuracy = accepted == 100 and wins >= 80
    if accepted < 100:
        return "IN_PROGRESS", False
    if not integrity or not ledger_ok or not diversity_pass:
        return "DIVERSITY_FAIL", accuracy
    if not accuracy:
        return "FAIL_ACCURACY", False
    return "PASS", True


def _index_report(
    root: Path,
    market: str,
    operational,
) -> FiveMarketCertificationMarketReportV1:
    state = _state(root, f"{market.lower()}_experimental.json")
    accepted_ids = tuple(
        str(item)
        for item in (state.get("counted_trade_ids") or ())
        if str(item)
    )
    accepted = int(state.get("certification_counter", 0) or 0)
    wins = int(state.get("certification_wins", 0) or 0)
    losses = int(state.get("certification_losses", 0) or 0)
    completed = tuple(
        item
        for item in (state.get("completed_trades") or ())
        if isinstance(item, dict)
    )
    completed_by_id = {
        str(item.get("trade_id")): item
        for item in completed
        if item.get("trade_id")
    }
    accepted_trades = tuple(
        completed_by_id[tid]
        for tid in accepted_ids
        if tid in completed_by_id
    )

    state_integrity = (
        accepted == wins + losses == len(accepted_ids)
        and len(set(accepted_ids)) == len(accepted_ids)
        and len(accepted_trades) == len(accepted_ids)
        and all(
            item.get("first_touch_result") in {"T1_FIRST", "SL_FIRST"}
            and item.get("certification_countable") is True
            and item.get("execution_mode") == "PAPER"
            and item.get("broker_submission") is False
            and item.get("live_execution") is False
            and item.get("strategy_version") == state.get("strategy_version")
            and item.get("certification_epoch") == state.get("certification_epoch")
            for item in accepted_trades
        )
    )

    ledger = _ledger_rows(root, f"{market.lower()}_outcomes.jsonl")
    ledger_by_id: dict[str, list[dict[str, object]]] = {}
    for row in ledger:
        tid = str(row.get("trade_id") or "")
        if tid:
            ledger_by_id.setdefault(tid, []).append(row)
    ledger_ok = all(
        len(ledger_by_id.get(tid, ())) == 1
        and ledger_by_id[tid][0].get("certification_countable") is True
        and ledger_by_id[tid][0].get("first_touch_result")
        == completed_by_id[tid].get("first_touch_result")
        and ledger_by_id[tid][0].get("strategy_version")
        == state.get("strategy_version")
        and ledger_by_id[tid][0].get("certification_epoch")
        == state.get("certification_epoch")
        and ledger_by_id[tid][0].get("execution_mode") == "PAPER"
        and ledger_by_id[tid][0].get("broker_submission") is False
        and ledger_by_id[tid][0].get("live_execution") is False
        for tid in accepted_ids
        if tid in completed_by_id
    ) and len(accepted_trades) == len(accepted_ids)

    days, regimes, phases, max_day, diversity_pass = _diversity(
        accepted_trades,
        index_market=True,
    )

    persisted = state.get("diversity_state") or {}
    warnings: list[str] = []
    if isinstance(persisted, dict):
        persisted_days = set(persisted.get("trading_dates") or ())
        persisted_regimes = set(persisted.get("regimes") or ())
        persisted_phases = set(persisted.get("session_phases") or ())
        persisted_counts = {
            str(key): int(value or 0)
            for key, value in dict(
                persisted.get("countable_by_day") or {}
            ).items()
        }
        recomputed_counts = Counter(
            str(item.get("certification_trade_date") or "").strip()
            for item in accepted_trades
            if str(item.get("certification_trade_date") or "").strip()
        )
        if (
            persisted_days != set(recomputed_counts)
            or persisted_regimes
            != {
                str(item.get("certification_regime") or "").strip()
                for item in accepted_trades
                if str(item.get("certification_regime") or "").strip()
                not in {"", "UNKNOWN"}
            }
            or persisted_phases
            != {
                str(item.get("certification_session_phase") or "").strip()
                for item in accepted_trades
                if str(item.get("certification_session_phase") or "").strip()
                not in {"", "UNKNOWN"}
            }
            or persisted_counts != dict(recomputed_counts)
        ):
            state_integrity = False
            warnings.append("PERSISTED_DIVERSITY_MISMATCH")
    elif accepted:
        state_integrity = False
        warnings.append("PERSISTED_DIVERSITY_MISSING")

    status, accuracy = _status(
        accepted=accepted,
        wins=wins,
        diversity_pass=diversity_pass,
        integrity=state_integrity,
        ledger_ok=ledger_ok,
    )

    return FiveMarketCertificationMarketReportV1(
        market=market,
        strategy_version=str(state.get("strategy_version") or ""),
        certification_epoch=str(state.get("certification_epoch") or ""),
        target_trade_count=100,
        accepted_trade_count=accepted,
        t1_first_wins=wins,
        sl_first_losses=losses,
        operational_completed_trades=operational.operational_completed_trades,
        operational_net_pnl=operational.operational_net_pnl,
        noncountable_completed_trades=operational.noncountable_completed_trades,
        ambiguous_completed_trades=operational.ambiguous_completed_trades,
        distinct_trading_days=days,
        distinct_regimes=regimes,
        distinct_session_phases=phases,
        max_countable_per_day=max_day,
        diversity_pass=diversity_pass,
        accuracy_threshold_pass=accuracy,
        state_counter_integrity=state_integrity,
        ledger_reconciliation_pass=ledger_ok,
        final_status=status,
        accepted_trade_ids=accepted_ids,
        warnings=tuple(warnings),
    )


def _mcx_report(
    root: Path,
    market: str,
    operational,
) -> FiveMarketCertificationMarketReportV1:
    state = _state(root, f"mcx_{market.lower()}_experimental.json")
    registry = get_product_epochs(market) or {}
    accepted_ids = tuple(
        str(item)
        for item in (state.get("_counted_trade_ids") or ())
        if str(item)
    )
    wins = int(state.get("t1_hit_wins", 0) or 0)
    losses = int(state.get("sl_losses", 0) or 0)
    accepted = wins + losses
    completed = tuple(
        item
        for item in (state.get("completed_trades") or ())
        if isinstance(item, dict)
    )
    completed_by_id = {
        str(item.get("trade_id")): item
        for item in completed
        if item.get("trade_id")
    }
    accepted_trades = tuple(
        completed_by_id[tid]
        for tid in accepted_ids
        if tid in completed_by_id
    )

    state_integrity = (
        bool(registry)
        and state.get("epoch") == registry.get("epoch")
        and state.get("strategy_version") == registry.get("strategy_version")
        and accepted == len(accepted_ids)
        and len(set(accepted_ids)) == len(accepted_ids)
        and len(accepted_trades) == len(accepted_ids)
        and all(
            item.get("certification_accepted") is True
            and item.get("first_touch_result") in {"T1_FIRST", "SL_FIRST"}
            and item.get("certification_eligible") is True
            and item.get("epoch_id") == registry.get("epoch")
            and item.get("strategy_version") == registry.get("strategy_version")
            for item in accepted_trades
        )
    )

    ledger = _ledger_rows(root, f"mcx_{market.lower()}_outcomes.jsonl")
    ledger_by_id: dict[str, list[dict[str, object]]] = {}
    for row in ledger:
        tid = str(row.get("trade_id") or "")
        if tid:
            ledger_by_id.setdefault(tid, []).append(row)
    ledger_ok = all(
        len(ledger_by_id.get(tid, ())) == 1
        and ledger_by_id[tid][0].get("certification_accepted") is True
        and ledger_by_id[tid][0].get("epoch_id") == registry.get("epoch")
        and ledger_by_id[tid][0].get("strategy_version")
        == registry.get("strategy_version")
        for tid in accepted_ids
    ) and len(accepted_trades) == len(accepted_ids)

    days, regimes, phases, max_day, diversity_pass = _diversity(
        accepted_trades,
        index_market=False,
    )
    status, accuracy = _status(
        accepted=accepted,
        wins=wins,
        diversity_pass=diversity_pass,
        integrity=state_integrity,
        ledger_ok=ledger_ok,
    )
    warnings: list[str] = []
    if (
        state.get("certification_eligible") is not None
        and bool(state.get("certification_eligible"))
        != bool(registry.get("certification_eligible", False))
    ):
        warnings.append(
            "STATE_CERTIFICATION_ELIGIBILITY_STALE_NONAUTHORITATIVE"
        )

    return FiveMarketCertificationMarketReportV1(
        market=market,
        strategy_version=str(registry.get("strategy_version") or ""),
        certification_epoch=str(registry.get("epoch") or ""),
        target_trade_count=100,
        accepted_trade_count=accepted,
        t1_first_wins=wins,
        sl_first_losses=losses,
        operational_completed_trades=operational.operational_completed_trades,
        operational_net_pnl=operational.operational_net_pnl,
        noncountable_completed_trades=operational.noncountable_completed_trades,
        ambiguous_completed_trades=operational.ambiguous_completed_trades,
        distinct_trading_days=days,
        distinct_regimes=regimes,
        distinct_session_phases=phases,
        max_countable_per_day=max_day,
        diversity_pass=diversity_pass,
        accuracy_threshold_pass=accuracy,
        state_counter_integrity=state_integrity,
        ledger_reconciliation_pass=ledger_ok,
        final_status=status,
        accepted_trade_ids=accepted_ids,
        warnings=tuple(warnings),
    )


def build_five_market_certification_report_v1(
    repo_root: str | Path,
    *,
    generated_at: datetime | None = None,
    release_commit: str | None = None,
) -> FiveMarketCertificationReportV1:
    root = Path(repo_root).resolve()
    now = generated_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("generated_at must be timezone-aware")

    campaign = build_five_market_paper_campaign_view_v1(
        root,
        generated_at=now,
        release_commit=release_commit,
    )
    operational = campaign.by_market()

    reports = (
        _index_report(root, "NIFTY", operational["NIFTY"]),
        _index_report(root, "SENSEX", operational["SENSEX"]),
        _mcx_report(root, "CRUDEOILM", operational["CRUDEOILM"]),
        _mcx_report(root, "GOLDM", operational["GOLDM"]),
        _mcx_report(root, "NATGASMINI", operational["NATGASMINI"]),
    )

    return FiveMarketCertificationReportV1(
        generated_at=now,
        release_commit=campaign.release_commit,
        markets=reports,
    )
