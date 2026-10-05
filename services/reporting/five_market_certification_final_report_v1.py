"""Canonical read-only final report for the five-market PAPER campaigns.

The report derives certification only from authoritative counted-trade IDs.
Operational P&L/trade counts are reported separately and can never inflate the
/100 denominator. No state mutation, provider call or broker action occurs.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from services.paper_orchestration.state_authority_readonly_v2 import validate_market

MARKETS = ("NIFTY", "SENSEX", "CRUDEOILM", "GOLDM", "NATGASMINI")
INDEX_MARKETS = frozenset(("NIFTY", "SENSEX"))
PASS_WINS = 80
TARGET_COUNT = 100

_STATE_FILE = {
    "NIFTY": "nifty_experimental.json",
    "SENSEX": "sensex_experimental.json",
    "CRUDEOILM": "mcx_crudeoilm_experimental.json",
    "GOLDM": "mcx_goldm_experimental.json",
    "NATGASMINI": "mcx_natgasmini_experimental.json",
}


@dataclass(frozen=True, slots=True)
class MarketCertificationFinalReportV1:
    market: str
    authority_status: str
    authority_reason: str
    strategy_version: str | None
    certification_epoch: str | None
    certification_eligible: bool | None
    accepted_count: int | None
    t1_first_wins: int | None
    sl_first_losses: int | None
    counted_id_count: int | None
    accepted_ledger_match_count: int | None
    operational_total_trades: int | None
    operational_wins: int | None
    operational_losses: int | None
    operational_total_pnl: float | None
    completed_trade_count: int | None
    noncountable_completed_count: int | None
    ambiguous_completed_count: int | None
    ambiguity_percent_of_completed: float | None
    distinct_certification_days: int | None
    distinct_certification_regimes: int | None
    distinct_certification_phases: int | None
    maximum_accepted_per_day: int | None
    diversity_pass: bool | None
    accounting_integrity_pass: bool | None
    ledger_integrity_pass: bool | None
    final_verdict: str
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False
    read_only: bool = True


@dataclass(frozen=True, slots=True)
class FiveMarketCertificationFinalReportV1:
    markets: tuple[MarketCertificationFinalReportV1, ...]
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False
    read_only: bool = True
    schema_version: str = "five_market_certification_final_report.v1"

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "execution_mode": self.execution_mode,
            "live_execution_eligible": self.live_execution_eligible,
            "broker_order_submission": self.broker_order_submission,
            "read_only": self.read_only,
            "markets": [asdict(item) for item in self.markets],
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    @property
    def semantic_hash(self) -> str:
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()


def _read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("STATE_SCHEMA_INVALID")
    return value


def _read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except Exception:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _ambiguity(completed: list[dict]) -> tuple[int, int, float]:
    valid = [t for t in completed if isinstance(t, dict)]
    ambiguous = sum(
        str(t.get("first_touch_result") or "").upper() == "AMBIGUOUS"
        for t in valid
    )
    noncountable = sum(t.get("certification_countable") is False for t in valid)
    pct = (ambiguous / len(valid) * 100.0) if valid else 0.0
    return noncountable, ambiguous, round(pct, 4)


def _accepted_diversity(trades: list[dict], *, index_market: bool):
    days: set[str] = set()
    regimes: set[str] = set()
    phases: set[str] = set()
    per_day: dict[str, int] = {}

    for trade in trades:
        if index_market:
            day = str(
                trade.get("certification_trade_date")
                or trade.get("entry_time")
                or ""
            )[:10]
            regime = str(trade.get("certification_regime") or "").strip()
            phase = str(trade.get("certification_session_phase") or "").strip()
        else:
            entry = str(trade.get("entry_time") or "")
            day = entry[:10]
            regime = str(trade.get("regime_at_entry") or "").strip()
            phase = ""
            hour_text = entry[11:13]
            if hour_text.isdigit():
                phase = "MORNING" if int(hour_text) < 17 else "EVENING"

        if day:
            days.add(day)
            per_day[day] = per_day.get(day, 0) + 1
        if regime and regime != "UNKNOWN":
            regimes.add(regime)
        if phase and phase != "UNKNOWN":
            phases.add(phase)

    maximum = max(per_day.values()) if per_day else 0
    passed = (
        len(days) >= 5
        and len(regimes) >= 2
        and len(phases) >= 2
        and maximum <= 40
    )
    return len(days), len(regimes), len(phases), maximum, passed


def _hold(market: str, reason: str) -> MarketCertificationFinalReportV1:
    return MarketCertificationFinalReportV1(
        market=market,
        authority_status="HOLD",
        authority_reason=reason,
        strategy_version=None,
        certification_epoch=None,
        certification_eligible=None,
        accepted_count=None,
        t1_first_wins=None,
        sl_first_losses=None,
        counted_id_count=None,
        accepted_ledger_match_count=None,
        operational_total_trades=None,
        operational_wins=None,
        operational_losses=None,
        operational_total_pnl=None,
        completed_trade_count=None,
        noncountable_completed_count=None,
        ambiguous_completed_count=None,
        ambiguity_percent_of_completed=None,
        distinct_certification_days=None,
        distinct_certification_regimes=None,
        distinct_certification_phases=None,
        maximum_accepted_per_day=None,
        diversity_pass=None,
        accounting_integrity_pass=None,
        ledger_integrity_pass=None,
        final_verdict="HOLD",
    )


def _index_report(root: Path, market: str, state: dict, authority):
    counted_ids = state.get("counted_trade_ids")
    if not isinstance(counted_ids, list):
        counted_ids = []
    completed = state.get("completed_trades")
    completed = completed if isinstance(completed, list) else []

    wins = int(state.get("certification_wins", 0) or 0)
    losses = int(state.get("certification_losses", 0) or 0)
    counter = int(state.get("certification_counter", 0) or 0)

    completed_by_id = {
        t.get("trade_id"): t
        for t in completed
        if isinstance(t, dict) and t.get("trade_id")
    }
    accepted = [completed_by_id[tid] for tid in counted_ids if tid in completed_by_id]

    ledger = _read_jsonl(
        root / "data" / "paper_trades" / f"{market.lower()}_outcomes.jsonl"
    )
    ledger_matches = 0
    ledger_ok = True
    for tid in counted_ids:
        matches = [
            row
            for row in ledger
            if row.get("trade_id") == tid
            and row.get("certification_countable") is True
            and row.get("strategy_version") == state.get("strategy_version")
            and row.get("certification_epoch") == state.get("certification_epoch")
        ]
        if len(matches) != 1:
            ledger_ok = False
        else:
            ledger_matches += 1

    accounting_ok = (
        counter == wins + losses
        and counter == len(counted_ids)
        and len(counted_ids) == len(set(counted_ids))
        and len(accepted) == counter
        and sum(t.get("first_touch_result") == "T1_FIRST" for t in accepted) == wins
        and sum(t.get("first_touch_result") == "SL_FIRST" for t in accepted) == losses
    )

    days, regimes, phases, maximum, diversity = _accepted_diversity(
        accepted, index_market=True
    )
    noncountable, ambiguous, ambiguity_pct = _ambiguity(completed)

    if not accounting_ok or not ledger_ok:
        verdict = "HOLD"
    elif counter < TARGET_COUNT:
        verdict = "IN_PROGRESS"
    elif counter != TARGET_COUNT:
        verdict = "HOLD"
    elif not diversity:
        verdict = "DIVERSITY_FAIL"
    elif wins >= PASS_WINS:
        verdict = "PASS"
    else:
        verdict = "FAIL_ACCURACY"

    return MarketCertificationFinalReportV1(
        market=market,
        authority_status="PASS",
        authority_reason=authority.reason,
        strategy_version=state.get("strategy_version"),
        certification_epoch=state.get("certification_epoch"),
        certification_eligible=True,
        accepted_count=counter,
        t1_first_wins=wins,
        sl_first_losses=losses,
        counted_id_count=len(counted_ids),
        accepted_ledger_match_count=ledger_matches,
        operational_total_trades=int(state.get("total_trades", len(completed)) or 0),
        operational_wins=int(state.get("winning_trades", 0) or 0),
        operational_losses=int(state.get("losing_trades", 0) or 0),
        operational_total_pnl=float(state.get("total_pnl", 0.0) or 0.0),
        completed_trade_count=len(completed),
        noncountable_completed_count=noncountable,
        ambiguous_completed_count=ambiguous,
        ambiguity_percent_of_completed=ambiguity_pct,
        distinct_certification_days=days,
        distinct_certification_regimes=regimes,
        distinct_certification_phases=phases,
        maximum_accepted_per_day=maximum,
        diversity_pass=diversity,
        accounting_integrity_pass=accounting_ok,
        ledger_integrity_pass=ledger_ok,
        final_verdict=verdict,
    )


def _mcx_report(root: Path, market: str, state: dict, authority):
    from mcx.mcx_version import get_product_epochs

    cfg = get_product_epochs(market) or {}
    counted_ids = state.get("_counted_trade_ids")
    counted_ids = counted_ids if isinstance(counted_ids, list) else []
    completed = state.get("completed_trades")
    completed = completed if isinstance(completed, list) else []

    wins = int(state.get("t1_hit_wins", 0) or 0)
    losses = int(state.get("sl_losses", 0) or 0)
    counter = wins + losses
    completed_by_id = {
        t.get("trade_id"): t
        for t in completed
        if isinstance(t, dict) and t.get("trade_id")
    }
    accepted = [completed_by_id[tid] for tid in counted_ids if tid in completed_by_id]

    ledger = _read_jsonl(
        root / "data" / "paper_trades" / f"mcx_{market.lower()}_outcomes.jsonl"
    )
    ledger_matches = 0
    ledger_ok = True
    for tid in counted_ids:
        matches = [
            row
            for row in ledger
            if row.get("trade_id") == tid
            and row.get("certification_accepted") is True
            and row.get("strategy_version") == state.get("strategy_version")
            and row.get("epoch_id") == state.get("epoch")
        ]
        if len(matches) != 1:
            ledger_ok = False
        else:
            ledger_matches += 1

    accounting_ok = (
        counter == len(counted_ids)
        and len(counted_ids) == len(set(counted_ids))
        and len(accepted) == counter
        and sum(t.get("first_touch_result") == "T1_FIRST" for t in accepted) == wins
        and sum(t.get("first_touch_result") == "SL_FIRST" for t in accepted) == losses
    )

    days, regimes, phases, maximum, diversity = _accepted_diversity(
        accepted, index_market=False
    )
    noncountable, ambiguous, ambiguity_pct = _ambiguity(completed)
    eligible = bool(cfg.get("certification_eligible", False))

    if not eligible or not accounting_ok or not ledger_ok:
        verdict = "HOLD"
    elif counter < TARGET_COUNT:
        verdict = "IN_PROGRESS"
    elif counter != TARGET_COUNT:
        verdict = "HOLD"
    elif not diversity:
        verdict = "DIVERSITY_FAIL"
    elif wins >= PASS_WINS:
        verdict = "PASS"
    else:
        verdict = "FAIL_ACCURACY"

    return MarketCertificationFinalReportV1(
        market=market,
        authority_status="PASS",
        authority_reason=authority.reason,
        strategy_version=state.get("strategy_version"),
        certification_epoch=state.get("epoch"),
        certification_eligible=eligible,
        accepted_count=counter,
        t1_first_wins=wins,
        sl_first_losses=losses,
        counted_id_count=len(counted_ids),
        accepted_ledger_match_count=ledger_matches,
        operational_total_trades=int(state.get("total_trades", 0) or 0),
        operational_wins=int(state.get("winning_trades", 0) or 0),
        operational_losses=int(state.get("losing_trades", 0) or 0),
        operational_total_pnl=float(state.get("total_pnl", 0.0) or 0.0),
        completed_trade_count=len(completed),
        noncountable_completed_count=noncountable,
        ambiguous_completed_count=ambiguous,
        ambiguity_percent_of_completed=ambiguity_pct,
        distinct_certification_days=days,
        distinct_certification_regimes=regimes,
        distinct_certification_phases=phases,
        maximum_accepted_per_day=maximum,
        diversity_pass=diversity,
        accounting_integrity_pass=accounting_ok,
        ledger_integrity_pass=ledger_ok,
        final_verdict=verdict,
    )


def build_five_market_certification_final_report(
    repo_root: str | Path,
) -> FiveMarketCertificationFinalReportV1:
    root = Path(repo_root).resolve()
    reports: list[MarketCertificationFinalReportV1] = []

    for market in MARKETS:
        authority = validate_market(root, market)
        if not authority.ok:
            reports.append(_hold(market, authority.reason))
            continue

        try:
            state = _read_json(
                root / "data" / "paper_trades" / _STATE_FILE[market]
            )
            report = (
                _index_report(root, market, state, authority)
                if market in INDEX_MARKETS
                else _mcx_report(root, market, state, authority)
            )
        except Exception as exc:
            report = _hold(market, f"REPORT_ERROR:{type(exc).__name__}")
        reports.append(report)

    return FiveMarketCertificationFinalReportV1(tuple(reports))
