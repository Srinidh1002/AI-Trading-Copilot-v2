"""X10-B4 anchored read-only X9/X10 linkage; never a financial authority."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime

from services.x7.contracts_v1 import MARKETS, _sha, canonical_sha256
from services.x8.contracts_v1 import zero_authority
from services.x9.contracts_v1 import X9FiveMarketLedgerV1
from services.x9.provenance_replay_v1 import X9ProvenanceReplayV1
from services.x10.reconciliation_audit_v1 import (
    X10ReconciliationAuditV1,
    audit_x10_reconciliation_v1,
)
from services.x10.typed_projection_v1 import X10TypedPortfolioProjectionV1


@dataclass(frozen=True, slots=True)
class X10CrossModuleReplayV1:
    parent_cycle_id: str
    x9_replay_sha256: str
    x10_projection_sha256: str
    x10_reconciliation_sha256: str
    p8_persistence_sha256: str | None
    market_statuses: tuple[tuple[str, str], ...]
    status: str
    deployable_capital: None = None
    capital_admission_allowed: bool = False
    schema_version: str = "X10_CROSS_MODULE_REPLAY_V1"
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
            or any(
                not _sha(x)
                for x in (
                    self.x9_replay_sha256,
                    self.x10_projection_sha256,
                    self.x10_reconciliation_sha256,
                )
            )
            or (self.p8_persistence_sha256 is not None and not _sha(self.p8_persistence_sha256))
            or tuple(row[0] for row in self.market_statuses) != MARKETS
            or any(row[1] != "MCX_UNVERIFIED" for row in self.market_statuses[2:])
            or self.status not in {"INDEX_REPLAY_RECONCILED", "PARTIAL_RESEARCH_ONLY"}
            or self.deployable_capital is not None
            or self.capital_admission_allowed is not False
        ):
            raise ValueError("X10 replay cannot confer trading or financial authority")
        zero_authority(self, "X10_CROSS_MODULE_REPLAY_V1")

    def sha256(self) -> str:
        return canonical_sha256(asdict(self))


def replay_x10_cross_module_v1(
    *,
    ledger: X9FiveMarketLedgerV1,
    x9_replay: X9ProvenanceReplayV1,
    expected_x9_replay_sha256: str,
    projection: X10TypedPortfolioProjectionV1,
    expected_projection_sha256: str,
    reconciliation: X10ReconciliationAuditV1,
    expected_reconciliation_sha256: str,
    p8_snapshot: object | None,
    expected_p8_sha256: str | None,
    p8_available_at: datetime | None,
    p7_snapshots: tuple[object, ...] = (),
    expected_p7_hashes: tuple[tuple[str, str], ...] = (),
) -> X10CrossModuleReplayV1:
    if (
        type(ledger) is not X9FiveMarketLedgerV1
        or type(x9_replay) is not X9ProvenanceReplayV1
        or type(projection) is not X10TypedPortfolioProjectionV1
        or type(reconciliation) is not X10ReconciliationAuditV1
    ):
        raise TypeError("Exact immutable original X9/X10 inputs required")
    checks = (
        (x9_replay, expected_x9_replay_sha256),
        (projection, expected_projection_sha256),
        (reconciliation, expected_reconciliation_sha256),
    )
    if any(not _sha(digest) or obj.sha256() != digest for obj, digest in checks):
        raise ValueError("Detached X9/X10 anchored digest mismatch")
    if (
        x9_replay.parent_cycle_id != ledger.parent_cycle_id
        or x9_replay.ledger_sha256 != ledger.sha256()
        or projection.parent_cycle_id != ledger.parent_cycle_id
        or reconciliation.parent_cycle_id != ledger.parent_cycle_id
        or projection.x9_ledger_sha256 != ledger.sha256()
        or reconciliation.ledger_sha256 != ledger.sha256()
        or reconciliation.projection_sha256 != projection.sha256()
    ):
        raise ValueError("X9/X10 cross-cycle identity mismatch")
    reproduced = audit_x10_reconciliation_v1(
        ledger=ledger,
        projection=projection,
        expected_projection_sha256=projection.sha256(),
        p8_snapshot=p8_snapshot,
        expected_p8_sha256=expected_p8_sha256,
        p8_available_at=p8_available_at,
        p7_snapshots=p7_snapshots,
        expected_p7_hashes=expected_p7_hashes,
    )
    if reproduced != reconciliation:
        raise ValueError("X10 reconciliation is not reproducible from original P7/P8 records")
    status = (
        "INDEX_REPLAY_RECONCILED"
        if reconciliation.position_reconciliation == "P7_P8_MATCHED"
        and x9_replay.status == "REPLAYED_DESCRIPTIVE"
        else "PARTIAL_RESEARCH_ONLY"
    )
    return X10CrossModuleReplayV1(
        ledger.parent_cycle_id,
        x9_replay.sha256(),
        projection.sha256(),
        reconciliation.sha256(),
        projection.p8_persistence_sha256,
        reconciliation.market_statuses,
        status,
    )
