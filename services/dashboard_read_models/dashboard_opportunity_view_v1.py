from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from ._shared import (
    aware,
    diagnostics,
    optional_number,
    paper_only,
    plain,
    text,
)


@dataclass(frozen=True, slots=True)
class DashboardOpportunityViewV1:
    opportunity_id: str
    created_at: datetime
    snapshot_id: str
    decision_id: str
    underlying_symbol: str
    exchange: str
    opportunity_status: str
    action: str
    directional_bias: str
    option_type: str | None
    contract_id: str | None
    trading_symbol: str | None
    instrument_token: str | None
    strike: float | None
    expiry: date | None
    lot_size: int | None
    reference_option_price: float | None
    technical_strength: float
    option_chain_strength: float
    contract_ranking_score: float
    decision_confidence: float
    opportunity_score: float
    supporting_evidence: tuple[str, ...] = ()
    contradictions: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "dashboard_opportunity_view.v1"

    def __post_init__(self) -> None:
        for name in (
            "opportunity_id",
            "snapshot_id",
            "decision_id",
            "underlying_symbol",
            "exchange",
            "opportunity_status",
            "action",
            "directional_bias",
        ):
            object.__setattr__(self, name, text(getattr(self, name), name))
        object.__setattr__(self, "created_at", aware(self.created_at, "created_at"))
        for name in (
            "option_type",
            "contract_id",
            "trading_symbol",
            "instrument_token",
        ):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, text(value, name))
        if self.expiry is not None:
            if isinstance(self.expiry, datetime) or not isinstance(self.expiry, date):
                raise TypeError("expiry must be a date or None")
        if self.lot_size is not None:
            if type(self.lot_size) is not int or isinstance(self.lot_size, bool):
                raise TypeError("lot_size must be an exact int or None")
            if self.lot_size <= 0:
                raise ValueError("lot_size must be positive")
        for name in (
            "strike",
            "reference_option_price",
            "technical_strength",
            "option_chain_strength",
            "contract_ranking_score",
            "decision_confidence",
            "opportunity_score",
        ):
            value = optional_number(getattr(self, name), name)
            if value is None:
                raise ValueError(f"{name} is required")
            object.__setattr__(self, name, value)
        for name in ("supporting_evidence", "contradictions", "blockers", "warnings"):
            object.__setattr__(self, name, diagnostics(getattr(self, name), name))
        paper_only(self.execution_mode, self.live_execution_eligible)
        if self.schema_version != "dashboard_opportunity_view.v1":
            raise ValueError("unsupported schema_version")

    def to_dict(self) -> dict[str, Any]:
        return {name: plain(getattr(self, name)) for name in self.__dataclass_fields__}
