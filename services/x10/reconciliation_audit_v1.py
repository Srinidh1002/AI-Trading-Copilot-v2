"""X10-B3 independent replay of supplied P7/P8 projection, read-only.

Only the canonical B2 projection can bind genuine typed persistence records.
This evaluator calls that original function again and compares the detached
result; it neither reads stores nor claims completeness of external P7 records.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime

from services.x7.contracts_v1 import MARKETS, _sha, canonical_sha256
from services.x8.contracts_v1 import zero_authority
from services.x9.contracts_v1 import X9FiveMarketLedgerV1
from services.x10.typed_projection_v1 import (
    X10TypedPortfolioProjectionV1,
    project_x10_typed_portfolio_v1,
)


@dataclass(frozen=True, slots=True)
class X10ReconciliationAuditV1:
    parent_cycle_id: str
    ledger_sha256: str
    projection_sha256: str
    p8_persistence_sha256: str | None
    verified_p7_record_count: int
    position_reconciliation: str
    market_statuses: tuple[tuple[str, str], ...]
    unresolved_capital_allocation: bool
    findings: tuple[str, ...]
    deployable_capital: None = None
    capital_admission_allowed: bool = False
    schema_version: str = "X10_RECONCILIATION_AUDIT_V1"
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
            or not _sha(self.ledger_sha256)
            or not _sha(self.projection_sha256)
            or (self.p8_persistence_sha256 is not None and not _sha(self.p8_persistence_sha256))
            or type(self.verified_p7_record_count) is not int
            or self.verified_p7_record_count < 0
            or self.position_reconciliation
            not in {"UNAVAILABLE", "P8_ONLY_UNRECONCILED", "P7_P8_MATCHED"}
            or type(self.market_statuses) is not tuple
            or tuple(row[0] for row in self.market_statuses) != MARKETS
            or type(self.unresolved_capital_allocation) is not bool
            or type(self.findings) is not tuple
            or self.deployable_capital is not None
            or self.capital_admission_allowed is not False
        ):
            raise ValueError("Invalid X10 zero-authority reconciliation result")
        if self.p8_persistence_sha256 is None and (
            self.verified_p7_record_count or self.position_reconciliation != "UNAVAILABLE"
        ):
            raise ValueError("Missing P8 cannot be claimed as reconciled")
        if any(row[1] != "MCX_UNVERIFIED" for row in self.market_statuses[2:]):
            raise ValueError("Original P8 does not establish MCX portfolio authority")
        zero_authority(self, "X10_RECONCILIATION_AUDIT_V1")

    def sha256(self) -> str:
        return canonical_sha256(asdict(self))


def audit_x10_reconciliation_v1(
    *,
    ledger: X9FiveMarketLedgerV1,
    projection: X10TypedPortfolioProjectionV1,
    expected_projection_sha256: str,
    p8_snapshot: object | None,
    expected_p8_sha256: str | None,
    p8_available_at: datetime | None,
    p7_snapshots: tuple[object, ...] = (),
    expected_p7_hashes: tuple[tuple[str, str], ...] = (),
) -> X10ReconciliationAuditV1:
    if (
        type(ledger) is not X9FiveMarketLedgerV1
        or type(projection) is not X10TypedPortfolioProjectionV1
    ):
        raise TypeError("Exact frozen B2 ledger and projection required")
    if (
        not _sha(expected_projection_sha256)
        or projection.sha256() != expected_projection_sha256
        or projection.x9_ledger_sha256 != ledger.sha256()
        or projection.parent_cycle_id != ledger.parent_cycle_id
        or projection.as_of != ledger.as_of
    ):
        raise ValueError("Projection does not match the separately anchored X9 cycle")
    reconstructed = project_x10_typed_portfolio_v1(
        ledger=ledger,
        p8_snapshot=p8_snapshot,
        expected_p8_sha256=expected_p8_sha256,
        p8_available_at=p8_available_at,
        p7_snapshots=p7_snapshots,
        expected_p7_hashes=expected_p7_hashes,
    )
    if reconstructed != projection or reconstructed.sha256() != expected_projection_sha256:
        raise ValueError("X10 projected state is not reproducible from supplied P7/P8")
    pending = projection.shared_pending_reservation_count
    findings = []
    if projection.p8_persistence_sha256 is None:
        findings.append("P8_STATE_UNAVAILABLE_NOT_ZERO")
    if projection.position_reconciliation == "P8_ONLY_UNRECONCILED":
        findings.append("P7_P8_RECONCILIATION_NOT_PROVEN")
    if pending is None or pending > 0:
        findings.append("MARKET_ALLOCATION_OF_PENDING_CAPITAL_UNVERIFIED")
    findings.append("MCX_ACCOUNT_AUTHORITY_UNVERIFIED")
    return X10ReconciliationAuditV1(
        ledger.parent_cycle_id,
        ledger.sha256(),
        projection.sha256(),
        projection.p8_persistence_sha256,
        len(projection.p7_snapshots),
        projection.position_reconciliation,
        tuple((row.market, row.source_status) for row in projection.slots),
        pending is None or pending > 0,
        tuple(findings),
    )
