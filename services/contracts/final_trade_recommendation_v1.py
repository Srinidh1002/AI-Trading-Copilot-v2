"""Final PAPER-only capital-safe recommendation projection for Task 4."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from math import isfinite
from typing import ClassVar


_ACTIONS = {"CALL", "PUT", "WAIT", "NO_TRADE"}
_MARKETS = {("NIFTY", "NSE"), ("SENSEX", "BSE")}


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


def _optional_number(
    value: object,
    name: str,
    *,
    positive: bool = False,
) -> float | None:
    if value is None:
        return None
    if (
        type(value) not in (int, float)
        or isinstance(value, bool)
        or not isfinite(value)
        or (positive and value <= 0.0)
        or (not positive and value < 0.0)
    ):
        raise ValueError(name)
    return float(value)


def _messages(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise TypeError(name)
    return tuple(dict.fromkeys(_text(item, name) for item in value))


@dataclass(frozen=True, slots=True)
class FinalTradeRecommendationV1:
    """One final recommendation with complete geometry or no trade plan."""

    SCHEMA_VERSION: ClassVar[str] = "final_trade_recommendation.v1"

    recommendation_id: str
    parent_cycle_id: str
    evaluated_at: datetime
    action: str
    selected_market: tuple[str, str] | None
    expiry: date | None
    strike: float | None
    contract: str | None
    entry_zone_lower: float | None
    entry_zone_upper: float | None
    stop_loss: float | None
    target_1: float | None
    target_2: float | None
    target_3: float | None
    lots: int
    quantity: int
    capital_required: float
    maximum_loss: float
    risk_reward: float | None
    confidence: float | None
    losing_market: tuple[str, str] | None
    losing_outcome_reason: str | None
    reasons: tuple[str, ...] = ()
    invalidation_conditions: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False

    def __post_init__(self) -> None:
        for name in ("recommendation_id", "parent_cycle_id"):
            object.__setattr__(
                self,
                name,
                _text(getattr(self, name), name),
            )
        object.__setattr__(
            self,
            "evaluated_at",
            _aware(self.evaluated_at, "evaluated_at"),
        )

        action = _text(self.action, "action").upper()
        if action not in _ACTIONS:
            raise ValueError("action")
        object.__setattr__(self, "action", action)

        for name in ("selected_market", "losing_market"):
            market = getattr(self, name)
            if market is not None:
                if not isinstance(market, tuple) or len(market) != 2:
                    raise TypeError(name)
                normalized = tuple(
                    _text(item, name).upper() for item in market
                )
                if normalized not in _MARKETS:
                    raise ValueError(name)
                object.__setattr__(self, name, normalized)

        if self.contract is not None:
            object.__setattr__(
                self,
                "contract",
                _text(self.contract, "contract"),
            )
        if self.expiry is not None and type(self.expiry) is not date:
            raise TypeError("expiry")

        for name in (
            "strike",
            "entry_zone_lower",
            "entry_zone_upper",
            "stop_loss",
            "target_1",
            "target_2",
            "target_3",
            "capital_required",
            "maximum_loss",
            "risk_reward",
            "confidence",
        ):
            object.__setattr__(
                self,
                name,
                _optional_number(
                    getattr(self, name),
                    name,
                    positive=name
                    not in {
                        "capital_required",
                        "maximum_loss",
                        "confidence",
                    },
                ),
            )

        if type(self.lots) is not int or self.lots < 0:
            raise ValueError("lots")
        if type(self.quantity) is not int or self.quantity < 0:
            raise ValueError("quantity")
        if self.confidence is not None and not 0.0 <= self.confidence <= 100.0:
            raise ValueError("confidence")

        for name in (
            "reasons",
            "invalidation_conditions",
            "blockers",
            "warnings",
        ):
            object.__setattr__(
                self,
                name,
                _messages(getattr(self, name), name),
            )

        plan = (
            self.expiry,
            self.strike,
            self.contract,
            self.entry_zone_lower,
            self.entry_zone_upper,
            self.stop_loss,
            self.target_1,
            self.target_2,
            self.target_3,
            self.risk_reward,
            self.confidence,
        )

        if action in {"CALL", "PUT"}:
            if self.selected_market is None:
                raise ValueError("action requires selected_market")
            if any(item is None for item in plan):
                raise ValueError("action requires complete plan")
            if self.lots < 1 or self.quantity < 1:
                raise ValueError("action requires positive size")
            if self.capital_required <= 0.0 or self.maximum_loss <= 0.0:
                raise ValueError("action requires known capital and loss")
            if self.blockers:
                raise ValueError("action cannot contain blockers")
            if not (
                self.entry_zone_lower
                < self.entry_zone_upper
                and self.stop_loss < self.entry_zone_lower
                and self.entry_zone_upper
                < self.target_1
                < self.target_2
                < self.target_3
            ):
                raise ValueError("invalid trade geometry")
        else:
            if any(item is not None for item in plan[:-1]):
                raise ValueError(
                    "WAIT/NO_TRADE cannot expose executable geometry"
                )
            if (
                self.lots != 0
                or self.quantity != 0
                or self.capital_required != 0.0
                or self.maximum_loss != 0.0
            ):
                raise ValueError("WAIT/NO_TRADE must use zero size")
            if not self.blockers:
                raise ValueError("WAIT/NO_TRADE requires blockers")
            if action == "NO_TRADE" and self.selected_market is not None:
                raise ValueError(
                    "NO_TRADE cannot identify selected market"
                )

        if self.losing_market is None:
            if self.losing_outcome_reason is not None:
                raise ValueError("losing reason without losing market")
        elif self.losing_outcome_reason is None:
            raise ValueError("losing market requires reason")
        else:
            object.__setattr__(
                self,
                "losing_outcome_reason",
                _text(
                    self.losing_outcome_reason,
                    "losing_outcome_reason",
                ).upper(),
            )

        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
        ):
            raise ValueError("PAPER-only final recommendation")
