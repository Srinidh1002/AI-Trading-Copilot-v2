"""Terminal retained result for one child in a two-market parent cycle."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from services.contracts.market_analysis_candidate_v1 import (
    MarketAnalysisCandidateV1,
)


_EXACT_MARKETS = {("NIFTY", "NSE"), ("SENSEX", "BSE")}
_STATUSES = {"COMPLETED", "FAILED", "UNAVAILABLE"}


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not (cleaned := value.strip()):
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


def _messages(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise TypeError(name)
    return tuple(dict.fromkeys(_text(item, name) for item in value))


@dataclass(frozen=True, slots=True)
class TwoMarketChildTerminalResultV1:
    """One retained NIFTY or SENSEX child terminal result."""

    SCHEMA_VERSION: ClassVar[str] = "two_market_child_terminal_result.v1"

    child_result_id: str
    parent_cycle_id: str
    observation_id: str
    underlying_symbol: str
    exchange: str
    requested_at: datetime
    received_at: datetime
    terminal_status: str
    candidate: MarketAnalysisCandidateV1 | None = None
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False

    def __post_init__(self) -> None:
        for name in ("child_result_id", "parent_cycle_id", "observation_id"):
            object.__setattr__(self, name, _text(getattr(self, name), name))

        identity = (
            _text(self.underlying_symbol, "underlying_symbol").upper(),
            _text(self.exchange, "exchange").upper(),
        )
        if identity not in _EXACT_MARKETS:
            raise ValueError("unsupported child market identity")
        object.__setattr__(self, "underlying_symbol", identity[0])
        object.__setattr__(self, "exchange", identity[1])

        requested = _aware(self.requested_at, "requested_at")
        received = _aware(self.received_at, "received_at")
        if requested > received:
            raise ValueError("requested_at must not exceed received_at")
        object.__setattr__(self, "requested_at", requested)
        object.__setattr__(self, "received_at", received)

        status = _text(self.terminal_status, "terminal_status").upper()
        if status not in _STATUSES:
            raise ValueError("terminal_status")
        object.__setattr__(self, "terminal_status", status)

        for name in ("blockers", "warnings", "errors"):
            object.__setattr__(
                self,
                name,
                _messages(getattr(self, name), name),
            )

        if status == "COMPLETED":
            if type(self.candidate) is not MarketAnalysisCandidateV1:
                raise ValueError("COMPLETED child requires exact candidate")
            candidate_identity = (
                self.candidate.observation_id,
                self.candidate.underlying_symbol,
                self.candidate.exchange,
                self.candidate.requested_at,
                self.candidate.received_at,
            )
            child_identity = (
                self.observation_id,
                self.underlying_symbol,
                self.exchange,
                self.requested_at,
                self.received_at,
            )
            if candidate_identity != child_identity:
                raise ValueError("candidate identity/timestamps mismatch")
            if self.errors:
                raise ValueError("COMPLETED child cannot contain errors")
        else:
            if self.candidate is not None:
                raise ValueError(
                    "FAILED/UNAVAILABLE child must not contain candidate"
                )
            if not (self.blockers or self.errors):
                raise ValueError(
                    "FAILED/UNAVAILABLE child requires blocker or error"
                )

        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
        ):
            raise ValueError("PAPER-only child result")
