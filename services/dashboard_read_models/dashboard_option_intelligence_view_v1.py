from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from .dashboard_market_overview_view_v1 import (
    _aware,
    _diag,
    _optional_number,
    _text,
)


@dataclass(frozen=True, slots=True)
class DashboardOptionIntelligenceViewV1:
    source_id: str
    underlying_symbol: str
    exchange: str
    status: str
    source_updated_at: datetime
    pcr: float | None = None
    directional_bias: str | None = None
    flow: str | None = None
    confidence: float | None = None
    support: float | None = None
    resistance: float | None = None
    max_pain: float | None = None
    call_open_interest: float | None = None
    put_open_interest: float | None = None
    atm_delta: float | None = None
    atm_gamma: float | None = None
    atm_theta: float | None = None
    atm_vega: float | None = None
    aggregate_greeks_summary: str | None = None
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    execution_mode: ClassVar[str] = "PAPER"
    live_execution_eligible: ClassVar[bool] = False
    schema_version: ClassVar[str] = (
        "dashboard_option_intelligence_view.v1"
    )

    def __post_init__(self) -> None:
        for name in (
            "source_id",
            "underlying_symbol",
            "exchange",
            "status",
        ):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        object.__setattr__(
            self,
            "source_updated_at",
            _aware(self.source_updated_at, "source_updated_at"),
        )
        for name in (
            "pcr",
            "confidence",
            "support",
            "resistance",
            "max_pain",
            "call_open_interest",
            "put_open_interest",
            "atm_delta",
            "atm_gamma",
            "atm_theta",
            "atm_vega",
        ):
            object.__setattr__(
                self,
                name,
                _optional_number(getattr(self, name), name),
            )
        for name in (
            "directional_bias",
            "flow",
            "aggregate_greeks_summary",
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
