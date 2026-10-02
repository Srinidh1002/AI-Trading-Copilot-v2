"""Read-only portfolio/exposure provenance, NOT P8 capital or risk authority."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime

from services.x7.contracts_v1 import MARKETS, _aware, _sha, _text, canonical_sha256
from services.x8.contracts_v1 import zero_authority

SOURCES = frozenset({"P8_PAPER_REFERENCE", "EXTERNAL_RESEARCH", "NONE"})
STATES = frozenset({"REPORTED", "UNVERIFIED", "STALE", "UNAVAILABLE"})


@dataclass(frozen=True, slots=True)
class X10MarketExposureReferenceV1:
    market: str
    source_kind: str
    source_id: str
    source_record_id: str
    source_sha256: str | None
    observed_at: datetime | None
    available_at: datetime | None
    state: str
    source_verified: bool
    open_position_count: int | None
    pending_reservation_count: int | None
    schema_version: str = "X10_MARKET_EXPOSURE_REFERENCE_V1"
    data_only: bool = True
    independent_vote: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if (
            self.market not in MARKETS
            or self.source_kind not in SOURCES
            or not all(_text(s) for s in (self.source_id, self.source_record_id))
            or self.state not in STATES
            or type(self.source_verified) is not bool
        ):
            raise ValueError("Invalid portfolio research reference")
        if self.source_kind == "P8_PAPER_REFERENCE" and self.market not in ("NIFTY", "SENSEX"):
            raise ValueError(
                "Existing four-index P8 cannot assert certified MCX portfolio evidence"
            )
        if self.source_kind == "NONE" and (
            self.state != "UNAVAILABLE"
            or self.source_verified
            or self.source_sha256 is not None
            or self.observed_at is not None
            or self.available_at is not None
        ):
            raise ValueError("Missing source must remain explicitly unavailable")
        if self.source_sha256 is not None and not _sha(self.source_sha256):
            raise ValueError("Invalid source hash")
        if self.observed_at is not None and not _aware(self.observed_at):
            raise ValueError("Observation time must be aware")
        if self.available_at is not None and (
            not _aware(self.available_at)
            or self.observed_at is None
            or self.available_at < self.observed_at
        ):
            raise ValueError("Availability cannot precede observation")
        for name in ("open_position_count", "pending_reservation_count"):
            value = getattr(self, name)
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError("Exposure counts must be non-negative integers or unknown")
        if self.state == "REPORTED" and (
            self.source_kind == "NONE"
            or not self.source_verified
            or self.source_sha256 is None
            or self.available_at is None
            or self.open_position_count is None
            or self.pending_reservation_count is None
        ):
            raise ValueError("Reported exposure needs traceable supplied counts")
        if self.state == "UNAVAILABLE" and (
            self.open_position_count is not None or self.pending_reservation_count is not None
        ):
            raise ValueError("Unavailable is not zero exposure")
        zero_authority(self, "X10_MARKET_EXPOSURE_REFERENCE_V1")


@dataclass(frozen=True, slots=True)
class X10PortfolioReadinessV1:
    parent_cycle_id: str
    as_of: datetime
    x9_ledger_sha256: str
    references: tuple[X10MarketExposureReferenceV1, ...]
    status: str
    total_open_positions: int | None
    total_pending_reservations: int | None
    shared_source_groups: tuple[tuple[str, ...], ...]
    deployable_capital: None = None
    risk_budget: None = None
    capital_admission_allowed: bool = False
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    schema_version: str = "X10_PORTFOLIO_READINESS_V1"
    data_only: bool = True
    independent_vote: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if (
            not _text(self.parent_cycle_id)
            or not _aware(self.as_of)
            or not _sha(self.x9_ledger_sha256)
            or type(self.references) is not tuple
            or len(self.references) != len(MARKETS)
            or any(type(item) is not X10MarketExposureReferenceV1 for item in self.references)
            or tuple(item.market for item in self.references) != MARKETS
            or self.status not in {"COMPLETE_RESEARCH", "INCOMPLETE_RESEARCH"}
            or self.deployable_capital is not None
            or self.risk_budget is not None
            or self.capital_admission_allowed is not False
            or type(self.shared_source_groups) is not tuple
            or type(self.blockers) is not tuple
            or type(self.warnings) is not tuple
        ):
            raise ValueError("X10 cannot grant portfolio/risk/capital permission")
        for count in (self.total_open_positions, self.total_pending_reservations):
            if count is not None and (type(count) is not int or count < 0):
                raise ValueError("Invalid read-only reported total")
        blockers = tuple(
            f"{row.market}_EXPOSURE_{row.state}"
            for row in self.references
            if row.state != "REPORTED"
        )
        from collections import defaultdict

        shared = defaultdict(list)
        for row in self.references:
            if row.source_kind != "NONE":
                shared[(row.source_id, row.source_record_id)].append(row.market)
        groups = tuple(tuple(markets) for _, markets in sorted(shared.items()) if len(markets) > 1)
        warnings = tuple(f"SHARED_SOURCE_{'_'.join(group)}" for group in groups) + tuple(
            f"{row.market}_EXTERNAL_RESEARCH_NOT_P8_AUTHORITY"
            for row in self.references
            if row.state == "REPORTED" and row.source_kind == "EXTERNAL_RESEARCH"
        )
        count_open = (
            sum(row.open_position_count for row in self.references)
            if not blockers and not groups
            else None
        )
        count_pending = (
            sum(row.pending_reservation_count for row in self.references)
            if not blockers and not groups
            else None
        )
        if (
            self.blockers != blockers
            or self.warnings != warnings
            or self.shared_source_groups != groups
            or self.status != ("INCOMPLETE_RESEARCH" if blockers or groups else "COMPLETE_RESEARCH")
            or self.total_open_positions != count_open
            or self.total_pending_reservations != count_pending
        ):
            raise ValueError("X10 cannot fabricate a verified portfolio total or readiness")
        zero_authority(self, "X10_PORTFOLIO_READINESS_V1")

    def sha256(self) -> str:
        return canonical_sha256(asdict(self))
