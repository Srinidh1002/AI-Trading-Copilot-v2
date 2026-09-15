"""Immutable Task 9 live PAPER 100+100 certification progress."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import ClassVar


def _count(value: object, name: str) -> int:
    if type(value) is not int or isinstance(value, bool) or value < 0:
        raise ValueError(name)
    return value


@dataclass(frozen=True, slots=True)
class Task9MarketProgressV1:
    market: str
    target_trade_count: int
    completed_live_paper_trades: int
    pending_entered_trades: int
    no_trade_completed: int
    no_trade_passed: int
    no_trade_failed: int
    wait_completed: int = 0
    wait_passed: int = 0
    wait_failed: int = 0

    def __post_init__(self) -> None:
        market = self.market.strip().upper()
        if market not in {"NIFTY", "SENSEX"}:
            raise ValueError("market")
        object.__setattr__(self, "market", market)

        for name in (
            "target_trade_count",
            "completed_live_paper_trades",
            "pending_entered_trades",
            "no_trade_completed",
            "no_trade_passed",
            "no_trade_failed",
            "wait_completed",
            "wait_passed",
            "wait_failed",
        ):
            object.__setattr__(
                self,
                name,
                _count(getattr(self, name), name),
            )

        if self.target_trade_count != 100:
            raise ValueError(
                "Task 9 requires exactly 100 trades per market"
            )

        if (
            self.no_trade_passed
            + self.no_trade_failed
            != self.no_trade_completed
        ):
            raise ValueError("NO_TRADE reconciliation")

        if (
            self.wait_passed
            + self.wait_failed
            != self.wait_completed
        ):
            raise ValueError("WAIT reconciliation")

    @property
    def target_reached(self) -> bool:
        return (
            self.completed_live_paper_trades
            >= self.target_trade_count
        )

    @property
    def remaining_trade_count(self) -> int:
        return max(
            0,
            self.target_trade_count
            - self.completed_live_paper_trades,
        )


@dataclass(frozen=True, slots=True)
class Task9LivePaperCertificationProgressV1:
    SCHEMA_VERSION: ClassVar[str] = (
        "task9_live_paper_certification_progress.v1"
    )

    nifty: Task9MarketProgressV1
    sensex: Task9MarketProgressV1
    replay_excluded: int
    duplicate_excluded: int
    invalid_excluded: int
    unresolved: int
    certification_complete: bool
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False
    read_only: bool = True
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if type(self.nifty) is not Task9MarketProgressV1:
            raise TypeError("nifty")
        if type(self.sensex) is not Task9MarketProgressV1:
            raise TypeError("sensex")
        if self.nifty.market != "NIFTY":
            raise ValueError("nifty market")
        if self.sensex.market != "SENSEX":
            raise ValueError("sensex market")

        for name in (
            "replay_excluded",
            "duplicate_excluded",
            "invalid_excluded",
            "unresolved",
        ):
            object.__setattr__(
                self,
                name,
                _count(getattr(self, name), name),
            )

        if type(self.certification_complete) is not bool:
            raise TypeError("certification_complete")

        expected_complete = (
            self.nifty.target_reached
            and self.sensex.target_reached
        )
        if self.certification_complete != expected_complete:
            raise ValueError(
                "certification completion coherence"
            )

        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
            or self.read_only is not True
            or self.schema_version != self.SCHEMA_VERSION
        ):
            raise ValueError(
                "Task 9 progress must remain PAPER-only read-only"
            )

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["nifty"]["target_reached"] = (
            self.nifty.target_reached
        )
        value["nifty"]["remaining_trade_count"] = (
            self.nifty.remaining_trade_count
        )
        value["sensex"]["target_reached"] = (
            self.sensex.target_reached
        )
        value["sensex"]["remaining_trade_count"] = (
            self.sensex.remaining_trade_count
        )
        return value
