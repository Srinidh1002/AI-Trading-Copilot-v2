"""Immutable five-market P7/P8 ownership inventory; NO financial-state adapter."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime

from services.x7.contracts_v1 import MARKETS, _aware, _sha, canonical_sha256
from services.x8.contracts_v1 import zero_authority
from services.x9.contracts_v1 import X9FiveMarketLedgerV1
from services.x10.contracts_v1 import X10PortfolioReadinessV1


@dataclass(frozen=True, slots=True)
class X10InterfaceCoverageV1:
    market: str
    p7_position_interface: str
    p7_recovery_interface: str
    p8_portfolio_interface: str
    verified_runtime_adapter: bool = False
    schema_version: str = "X10_INTERFACE_COVERAGE_V1"
    data_only: bool = True
    independent_vote: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if self.market not in MARKETS or (
            self.p7_position_interface != "CONTRACT_REFERENCE_ONLY"
            or self.p7_recovery_interface != "CONTRACT_REFERENCE_ONLY"
            or self.p8_portfolio_interface
            != (
                "INDEX_CONTRACT_REFERENCE_ONLY"
                if self.market in ("NIFTY", "SENSEX")
                else "MCX_UNVERIFIED"
            )
            or self.verified_runtime_adapter is not False
        ):
            raise ValueError("X10 B1 is an interface audit, not a verified P7/P8 adapter")
        zero_authority(self, "X10_INTERFACE_COVERAGE_V1")


@dataclass(frozen=True, slots=True)
class X10InterfaceAuditV1:
    parent_cycle_id: str
    as_of: datetime
    x9_ledger_sha256: str
    x10_readiness_sha256: str
    coverage: tuple[X10InterfaceCoverageV1, ...]
    verified_adapters: int = 0
    portfolio_authority: bool = False
    capital_admission_allowed: bool = False
    schema_version: str = "X10_INTERFACE_AUDIT_V1"
    data_only: bool = True
    independent_vote: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if (
            not self.parent_cycle_id
            or not _aware(self.as_of)
            or not _sha(self.x9_ledger_sha256)
            or not _sha(self.x10_readiness_sha256)
            or type(self.coverage) is not tuple
            or tuple(row.market for row in self.coverage) != MARKETS
            or self.verified_adapters != 0
            or self.portfolio_authority is not False
            or self.capital_admission_allowed is not False
        ):
            raise ValueError("Interface audit cannot grant capital or portfolio authority")
        zero_authority(self, "X10_INTERFACE_AUDIT_V1")

    def sha256(self) -> str:
        return canonical_sha256(asdict(self))


def audit_x10_interfaces_v1(
    *,
    ledger: X9FiveMarketLedgerV1,
    readiness: X10PortfolioReadinessV1,
) -> X10InterfaceAuditV1:
    if type(ledger) is not X9FiveMarketLedgerV1 or type(readiness) is not X10PortfolioReadinessV1:
        raise TypeError("Exactly typed immutable X9 and X10 results are required")
    if (
        readiness.x9_ledger_sha256 != ledger.sha256()
        or readiness.parent_cycle_id != ledger.parent_cycle_id
        or readiness.as_of != ledger.as_of
    ):
        raise ValueError("X10 result is not bound to this X9 parent cycle")
    rows = tuple(
        X10InterfaceCoverageV1(
            market,
            "CONTRACT_REFERENCE_ONLY",
            "CONTRACT_REFERENCE_ONLY",
            "INDEX_CONTRACT_REFERENCE_ONLY" if market in ("NIFTY", "SENSEX") else "MCX_UNVERIFIED",
        )
        for market in MARKETS
    )
    return X10InterfaceAuditV1(
        ledger.parent_cycle_id,
        ledger.as_of,
        ledger.sha256(),
        readiness.sha256(),
        rows,
    )
