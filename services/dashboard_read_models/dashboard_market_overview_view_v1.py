from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{name} must be a nonblank string")
    return value.strip()


def _aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


def _optional_number(value: object, name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or type(value) not in (int, float):
        raise TypeError(f"{name} must be numeric or None")
    return float(value)


def _diag(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise TypeError(f"{name} must be a tuple")
    result: list[str] = []
    for item in value:
        normalized = _text(item, f"{name} item")
        if normalized not in result:
            result.append(normalized)
    return tuple(result)


@dataclass(frozen=True, slots=True)
class DashboardMarketOverviewViewV1:
    source_id: str
    underlying_symbol: str
    exchange: str
    market_status: str
    source_updated_at: datetime
    last_traded_price: float | None = None
    rsi: float | None = None
    bull_score: float | None = None
    bear_score: float | None = None
    neutral_score: float | None = None
    momentum: str | None = None
    trend_strength: str | None = None
    trend_score: float | None = None
    candlestick_pattern: str | None = None
    candlestick_signal: str | None = None
    support: float | None = None
    resistance: float | None = None
    decision: str | None = None
    decision_confidence: float | None = None
    institutional_score: float | None = None
    trade_grade: str | None = None
    execution_display: str | None = None
    risk_level: str | None = None
    decision_reason: str | None = None
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    execution_mode: ClassVar[str] = "PAPER"
    live_execution_eligible: ClassVar[bool] = False
    schema_version: ClassVar[str] = "dashboard_market_overview_view.v1"

    def __post_init__(self) -> None:
        for name in (
            "source_id",
            "underlying_symbol",
            "exchange",
            "market_status",
        ):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        object.__setattr__(
            self,
            "source_updated_at",
            _aware(self.source_updated_at, "source_updated_at"),
        )
        for name in (
            "last_traded_price",
            "rsi",
            "bull_score",
            "bear_score",
            "neutral_score",
            "trend_score",
            "support",
            "resistance",
            "decision_confidence",
            "institutional_score",
        ):
            object.__setattr__(
                self,
                name,
                _optional_number(getattr(self, name), name),
            )
        for name in (
            "momentum",
            "trend_strength",
            "candlestick_pattern",
            "candlestick_signal",
            "decision",
            "trade_grade",
            "execution_display",
            "risk_level",
            "decision_reason",
        ):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _text(value, name))
        if (
            self.support is not None
            and self.resistance is not None
            and self.support > self.resistance
        ):
            raise ValueError("support cannot exceed resistance")
        for name in ("blockers", "warnings"):
            object.__setattr__(
                self,
                name,
                _diag(getattr(self, name), name),
            )

    def to_dict(self) -> dict[str, object]:
        result = {
            name: getattr(self, name)
            for name in self.__dataclass_fields__
        }
        result["source_updated_at"] = self.source_updated_at.isoformat()
        result["blockers"] = list(self.blockers)
        result["warnings"] = list(self.warnings)
        result["execution_mode"] = self.execution_mode
        result["live_execution_eligible"] = self.live_execution_eligible
        result["schema_version"] = self.schema_version
        return result
