"""Task 7A machine-readable replay certification report."""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from math import isfinite
from typing import ClassVar

from services.contracts.replay_certification_v1 import (
    ReplayCertificationLedgerV1,
)


def _text(value: object, name: str) -> str:
    if type(value) is not str or not (cleaned := value.strip()):
        raise ValueError(name)
    return cleaned


def _aware(value: object, name: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(name)
    return value


@dataclass(frozen=True, slots=True)
class ReplayCertificationReportV1:
    """Stable summary artifact for Task 7A and Monday preflight."""

    SCHEMA_VERSION: ClassVar[str] = "replay_certification_report.v1"

    report_id: str
    generated_at: datetime
    branch_name: str
    commit_sha: str
    overall_status: str
    task_8_ready: bool
    total_results: int
    total_closed_trades: int
    nifty_closed_trades: int
    sensex_closed_trades: int
    no_trade_count: int
    blocked_count: int
    failed_count: int
    scenario_coverage: dict[str, int]
    closure_distribution: dict[str, int]
    market_realized_pnl: dict[str, float]
    total_realized_pnl: float
    execution_mode: str = "PAPER"
    network_access_used: bool = False
    broker_submission_enabled: bool = False
    live_execution_eligible: bool = False
    schema_version: str = "replay_certification_report.v1"

    def __post_init__(self) -> None:
        for name in ("report_id", "branch_name", "commit_sha"):
            object.__setattr__(
                self,
                name,
                _text(getattr(self, name), name),
            )
        object.__setattr__(
            self,
            "generated_at",
            _aware(self.generated_at, "generated_at"),
        )

        if self.overall_status not in {"PASSED", "FAILED"}:
            raise ValueError("overall_status")
        if type(self.task_8_ready) is not bool:
            raise TypeError("task_8_ready")

        for name in (
            "total_results",
            "total_closed_trades",
            "nifty_closed_trades",
            "sensex_closed_trades",
            "no_trade_count",
            "blocked_count",
            "failed_count",
        ):
            value = getattr(self, name)
            if (
                type(value) is not int
                or isinstance(value, bool)
                or value < 0
            ):
                raise ValueError(name)

        if not isinstance(self.scenario_coverage, dict):
            raise TypeError("scenario_coverage")
        if not isinstance(self.closure_distribution, dict):
            raise TypeError("closure_distribution")
        if not isinstance(self.market_realized_pnl, dict):
            raise TypeError("market_realized_pnl")

        for mapping_name in (
            "scenario_coverage",
            "closure_distribution",
        ):
            mapping = getattr(self, mapping_name)
            if any(
                type(key) is not str
                or type(value) is not int
                or value < 0
                for key, value in mapping.items()
            ):
                raise ValueError(mapping_name)

        if set(self.market_realized_pnl) != {"NIFTY", "SENSEX"}:
            raise ValueError("market_realized_pnl")
        if any(
            type(value) not in (int, float)
            or isinstance(value, bool)
            or not isfinite(value)
            for value in self.market_realized_pnl.values()
        ):
            raise ValueError("market_realized_pnl")
        if (
            type(self.total_realized_pnl) not in (int, float)
            or isinstance(self.total_realized_pnl, bool)
            or not isfinite(self.total_realized_pnl)
        ):
            raise ValueError("total_realized_pnl")

        coherent_total = (
            self.total_closed_trades
            + self.no_trade_count
            + self.blocked_count
            + self.failed_count
        )
        if coherent_total != self.total_results:
            raise ValueError("result counts are incoherent")
        if (
            self.nifty_closed_trades
            + self.sensex_closed_trades
            != self.total_closed_trades
        ):
            raise ValueError("closed trade counts are incoherent")

        passed = (
            self.nifty_closed_trades == 60
            and self.sensex_closed_trades == 60
            and self.failed_count == 0
            and self.execution_mode == "PAPER"
            and self.network_access_used is False
            and self.broker_submission_enabled is False
            and self.live_execution_eligible is False
        )
        if (self.overall_status == "PASSED") is not passed:
            raise ValueError("overall_status")
        if self.task_8_ready is not passed:
            raise ValueError("task_8_ready")

        if (
            self.execution_mode != "PAPER"
            or self.network_access_used is not False
            or self.broker_submission_enabled is not False
            or self.live_execution_eligible is not False
        ):
            raise ValueError("offline PAPER-only report")
        if self.schema_version != self.SCHEMA_VERSION:
            raise ValueError("schema_version")

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["generated_at"] = self.generated_at.isoformat()
        return value


def build_replay_certification_report(
    *,
    ledger: ReplayCertificationLedgerV1,
    report_id: str,
    branch_name: str,
    commit_sha: str,
) -> ReplayCertificationReportV1:
    if type(ledger) is not ReplayCertificationLedgerV1:
        raise TypeError("ledger")

    closed = tuple(
        result
        for result in ledger.results
        if result.status == "CLOSED_TRADE"
    )
    scenario_coverage = Counter(
        result.scenario_type
        for result in ledger.results
    )
    closure_distribution = Counter(
        result.closure_reason
        for result in closed
        if result.closure_reason is not None
    )
    market_pnl = {
        "NIFTY": sum(
            result.realized_pnl
            for result in closed
            if result.market == ("NIFTY", "NSE")
        ),
        "SENSEX": sum(
            result.realized_pnl
            for result in closed
            if result.market == ("SENSEX", "BSE")
        ),
    }
    passed = ledger.is_complete and ledger.failed_count == 0

    return ReplayCertificationReportV1(
        report_id=report_id,
        generated_at=ledger.generated_at,
        branch_name=branch_name,
        commit_sha=commit_sha,
        overall_status="PASSED" if passed else "FAILED",
        task_8_ready=passed,
        total_results=len(ledger.results),
        total_closed_trades=len(closed),
        nifty_closed_trades=ledger.nifty_closed_trade_count,
        sensex_closed_trades=ledger.sensex_closed_trade_count,
        no_trade_count=ledger.no_trade_count,
        blocked_count=ledger.blocked_count,
        failed_count=ledger.failed_count,
        scenario_coverage=dict(sorted(scenario_coverage.items())),
        closure_distribution=dict(
            sorted(closure_distribution.items())
        ),
        market_realized_pnl={
            key: float(value)
            for key, value in market_pnl.items()
        },
        total_realized_pnl=float(sum(market_pnl.values())),
    )
