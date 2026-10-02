"""X9 five-market *research* comparison ledger, never opportunity ranking."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import datetime

from services.x7.contracts_v1 import MARKETS, _aware, _sha, _text, canonical_sha256
from services.x8.contracts_v1 import zero_authority


@dataclass(frozen=True, slots=True)
class X9MarketSlotV1:
    market: str
    x8_readiness_sha256: str
    source_as_of: datetime
    regime_readiness: str
    regime_label: str = "UNASSESSED"
    eligibility: str = "UNASSESSED"
    schema_version: str = "X9_MARKET_SLOT_V1"
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
            or not _sha(self.x8_readiness_sha256)
            or not _aware(self.source_as_of)
            or self.regime_readiness not in {"READY", "PARTIAL", "UNAVAILABLE"}
            or self.regime_label != "UNASSESSED"
            or self.eligibility != "UNASSESSED"
        ):
            raise ValueError("Invalid unranked five-market slot")
        zero_authority(self, "X9_MARKET_SLOT_V1")


@dataclass(frozen=True, slots=True)
class X9FiveMarketLedgerV1:
    parent_cycle_id: str
    as_of: datetime
    slots: tuple[X9MarketSlotV1, ...]
    status: str
    timing_skew_seconds: float
    selected_market: None = None
    rankings: tuple[()] = ()
    blockers: tuple[str, ...] = ()
    schema_version: str = "X9_FIVE_MARKET_LEDGER_V1"
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
            or type(self.slots) is not tuple
            or len(self.slots) != len(MARKETS)
            or any(type(slot) is not X9MarketSlotV1 for slot in self.slots)
            or tuple(slot.market for slot in self.slots) != MARKETS
            or self.status not in {"COMPLETE_RESEARCH", "INCOMPLETE_RESEARCH"}
            or type(self.timing_skew_seconds) is not float
            or self.timing_skew_seconds < 0
            or self.selected_market is not None
            or self.rankings != ()
            or type(self.blockers) is not tuple
        ):
            raise ValueError("X9 is a complete unranked five-market ledger")
        if any(slot.source_as_of > self.as_of for slot in self.slots):
            raise ValueError("X9 cannot incorporate future captures")
        blockers = tuple(
            f"{slot.market}_REGIME_READINESS_{slot.regime_readiness}"
            for slot in self.slots
            if slot.regime_readiness != "READY"
        )
        status = "INCOMPLETE_RESEARCH" if blockers else "COMPLETE_RESEARCH"
        true_skew = max((self.as_of - slot.source_as_of).total_seconds() for slot in self.slots)
        if (
            self.blockers != blockers
            or self.status != status
            or not math.isfinite(self.timing_skew_seconds)
            or not math.isclose(true_skew, self.timing_skew_seconds, abs_tol=1e-9)
        ):
            raise ValueError("X9 cannot misreport comparison completeness or timing skew")
        zero_authority(self, "X9_FIVE_MARKET_LEDGER_V1")

    def sha256(self) -> str:
        return canonical_sha256(asdict(self))
