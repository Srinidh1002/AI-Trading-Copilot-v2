"""Read-only index P8/P7 snapshot *projection*; never owns financial state.

Exact P7/P8 types are imported lazily so missing optional legacy modules do not
make an unavailable Shadow view import-unsafe. NO runtime fetch or side effects.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime

from services.x7.contracts_v1 import MARKETS, _aware, _sha, _text, canonical_sha256
from services.x8.contracts_v1 import zero_authority
from services.x9.contracts_v1 import X9FiveMarketLedgerV1


def _p8_cls():
    from services.contracts.paper_portfolio_persistence_snapshot_v1 import (
        PaperPortfolioPersistenceSnapshotV1,
    )

    return PaperPortfolioPersistenceSnapshotV1


def _p7_cls():
    from services.contracts.paper_trade_persistence_snapshot_v1 import (
        PaperTradePersistenceSnapshotV1,
    )

    return PaperTradePersistenceSnapshotV1


@dataclass(frozen=True, slots=True)
class X10TypedMarketProjectionV1:
    market: str
    open_position_count: int | None
    pending_reservation_count: int | None
    source_status: str
    schema_version: str = "X10_TYPED_MARKET_PROJECTION_V1"
    data_only: bool = True
    independent_vote: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if self.market not in MARKETS or self.source_status not in {
            "INDEX_P8_REPORTED",
            "UNAVAILABLE",
            "MCX_UNVERIFIED",
        }:
            raise ValueError("Invalid X10 index-only projection")
        if self.market not in ("NIFTY", "SENSEX") and (
            self.source_status != "MCX_UNVERIFIED"
            or self.open_position_count is not None
            or self.pending_reservation_count is not None
        ):
            raise ValueError("Existing P8 does not certify MCX account state")
        if self.source_status == "UNAVAILABLE" and (
            self.open_position_count is not None or self.pending_reservation_count is not None
        ):
            raise ValueError("Missing P8 is not zero positions")
        if self.source_status == "INDEX_P8_REPORTED" and self.market not in ("NIFTY", "SENSEX"):
            raise ValueError("Only supported index projections may be reported")
        for name in ("open_position_count", "pending_reservation_count"):
            count = getattr(self, name)
            if count is not None and (type(count) is not int or count < 0):
                raise ValueError("Projected counts must be exact nonnegative integers or unknown")
        if self.source_status == "INDEX_P8_REPORTED" and self.open_position_count is None:
            raise ValueError("A reported index requires an actual position count")
        zero_authority(self, "X10_TYPED_MARKET_PROJECTION_V1")


@dataclass(frozen=True, slots=True)
class X10TypedPortfolioProjectionV1:
    parent_cycle_id: str
    as_of: datetime
    x9_ledger_sha256: str
    p8_persistence_sha256: str | None
    p8_event_sequence: int | None
    p7_snapshots: tuple[tuple[str, str, int], ...]
    index_open_position_count: int | None
    shared_pending_reservation_count: int | None
    position_reconciliation: str
    slots: tuple[X10TypedMarketProjectionV1, ...]
    status: str
    deployable_capital: None = None
    capital_admission_allowed: bool = False
    schema_version: str = "X10_TYPED_PORTFOLIO_PROJECTION_V1"
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
            or type(self.slots) is not tuple
            or tuple(row.market for row in self.slots) != MARKETS
            or any(type(row) is not X10TypedMarketProjectionV1 for row in self.slots)
            or type(self.p7_snapshots) is not tuple
            or self.position_reconciliation
            not in {
                "UNAVAILABLE",
                "P8_ONLY_UNRECONCILED",
                "P7_P8_MATCHED",
            }
            or self.status not in {"PARTIAL_DESCRIPTIVE", "UNAVAILABLE"}
            or self.deployable_capital is not None
            or self.capital_admission_allowed is not False
        ):
            raise ValueError("X10 projection cannot obtain account or risk authority")
        if self.p8_persistence_sha256 is None:
            if (
                self.p8_event_sequence is not None
                or self.p7_snapshots
                or self.index_open_position_count is not None
                or self.shared_pending_reservation_count is not None
                or self.position_reconciliation != "UNAVAILABLE"
                or self.status != "UNAVAILABLE"
                or any(row.source_status != "UNAVAILABLE" for row in self.slots[:2])
            ):
                raise ValueError("Absent P8 source cannot imply account evidence")
        else:
            if (
                not _sha(self.p8_persistence_sha256)
                or (type(self.p8_event_sequence) is not int or self.p8_event_sequence < 0)
                or self.status != "PARTIAL_DESCRIPTIVE"
                or any(row.source_status != "INDEX_P8_REPORTED" for row in self.slots[:2])
                or self.position_reconciliation == "UNAVAILABLE"
            ):
                raise ValueError("P8 provenance is inconsistent")
            count = sum(row.open_position_count for row in self.slots[:2])
            if self.index_open_position_count != count or (
                type(self.shared_pending_reservation_count) is not int
                or self.shared_pending_reservation_count < 0
            ):
                raise ValueError("Projected P8 index totals cannot be fabricated")
            for row in self.slots[:2]:
                if row.pending_reservation_count != (
                    0 if self.shared_pending_reservation_count == 0 else None
                ):
                    raise ValueError("Unattributed P8 reservations cannot be allocated to markets")
        if any(row.source_status != "MCX_UNVERIFIED" for row in self.slots[2:]):
            raise ValueError("No MCX P8 authority is established")
        ids = [row[0] for row in self.p7_snapshots]
        if (
            len(ids) != len(set(ids))
            or ids != sorted(ids)
            or any(
                type(row) is not tuple
                or len(row) != 3
                or not _text(row[0])
                or not _sha(row[1])
                or type(row[2]) is not int
                or row[2] < 0
                for row in self.p7_snapshots
            )
        ):
            raise ValueError("P7 records must be unique, ordered and hash-bound")
        if self.position_reconciliation == "P7_P8_MATCHED" and not self.p7_snapshots:
            raise ValueError("No supplied P7 evidence was independently matched")
        zero_authority(self, "X10_TYPED_PORTFOLIO_PROJECTION_V1")

    def sha256(self) -> str:
        return canonical_sha256(asdict(self))


def project_x10_typed_portfolio_v1(
    *,
    ledger: X9FiveMarketLedgerV1,
    p8_snapshot: object | None,
    expected_p8_sha256: str | None,
    p8_available_at: datetime | None,
    p7_snapshots: tuple[object, ...] = (),
    expected_p7_hashes: tuple[tuple[str, str], ...] = (),
) -> X10TypedPortfolioProjectionV1:
    """Consume caller-supplied exact P7/P8 objects, never open repositories.

    A detached SHA confirms supplied byte consistency, not a publisher or the
    existence of every unobserved position. A live P7/P8 store adapter remains
    a separate certification task.
    """
    if type(ledger) is not X9FiveMarketLedgerV1:
        raise TypeError("Exact immutable X9 ledger required")
    if p8_snapshot is None:
        if (
            expected_p8_sha256 is not None
            or p8_available_at is not None
            or p7_snapshots
            or expected_p7_hashes
        ):
            raise ValueError("Unavailable P8 cannot have claimed P7/portfolio facts")
        rows = tuple(
            X10TypedMarketProjectionV1(
                market,
                None,
                None,
                "UNAVAILABLE" if market in ("NIFTY", "SENSEX") else "MCX_UNVERIFIED",
            )
            for market in MARKETS
        )
        return X10TypedPortfolioProjectionV1(
            ledger.parent_cycle_id,
            ledger.as_of,
            ledger.sha256(),
            None,
            None,
            (),
            None,
            None,
            "UNAVAILABLE",
            rows,
            "UNAVAILABLE",
        )
    if type(p8_snapshot) is not _p8_cls():
        raise TypeError("Exact canonical P8 persistence snapshot required")
    if not _sha(expected_p8_sha256) or p8_snapshot.integrity_hash != expected_p8_sha256:
        raise ValueError("Detached P8 persistence digest mismatch")
    if not _aware(p8_available_at) or (
        p8_snapshot.created_at > p8_snapshot.updated_at
        or p8_snapshot.updated_at > p8_available_at
        or p8_available_at > ledger.as_of
        or p8_snapshot.portfolio_snapshot.updated_at > p8_available_at
        or p8_snapshot.portfolio_snapshot.created_at > ledger.as_of
    ):
        raise ValueError("P8 portfolio was not available at the cycle time")
    snap = p8_snapshot.portfolio_snapshot
    if (
        p8_snapshot.portfolio_id != snap.portfolio_id
        or p8_snapshot.event_sequence != snap.event_sequence
        or p8_snapshot.execution_mode != "PAPER"
        or p8_snapshot.live_execution_eligible is not False
    ):
        raise ValueError("P8 persistence/snapshot binding mismatch")
    positions = snap.position_references
    # P8 can contain BANKNIFTY/FINNIFTY, but this exact five-market Shadow
    # scope cannot silently drop their capital use or reassign it to NIFTY.
    for p in positions:
        if p.underlying_symbol not in ("NIFTY", "SENSEX"):
            raise ValueError("Out-of-scope P8 positions need a separate portfolio view")
        if p.updated_at > p8_available_at:
            raise ValueError("Future P8 position must not enter the Shadow capture")
    if snap.open_position_count != sum(not p.is_terminal for p in positions):
        raise ValueError("P8 open-position count contradicts original positions")
    if snap.pending_plan_count != sum(
        r.reservation_status == "PENDING_HOLD" for r in snap.reservations
    ):
        raise ValueError("P8 pending count contradicts reservation states")
    if type(p7_snapshots) is not tuple or type(expected_p7_hashes) is not tuple:
        raise TypeError("P7 snapshots/anchors must be tuples")
    if len(p7_snapshots) != len(expected_p7_hashes):
        raise ValueError("P7 snapshots and detached hashes must correspond")
    p7_by_id = {}
    expected = dict(expected_p7_hashes)
    if len(expected) != len(expected_p7_hashes):
        raise ValueError("Duplicate P7 expected identity")
    for value in p7_snapshots:
        if type(value) is not _p7_cls():
            raise TypeError("Exact canonical P7 persistence snapshot required")
        if value.paper_trade_id in p7_by_id or value.paper_trade_id not in expected:
            raise ValueError("Duplicate or unexpected P7 persistence identity")
        if value.integrity_hash != expected[value.paper_trade_id]:
            raise ValueError("Detached P7 persistence digest mismatch")
        if value.updated_at > ledger.as_of or value.updated_at < value.created_at:
            raise ValueError("P7 persistence unavailable at cycle time")
        if value.execution_mode != "PAPER" or value.live_execution_eligible is not False:
            raise ValueError("P7 must remain PAPER-only")
        p7_by_id[value.paper_trade_id] = value
    p8_by_position = {p.position_id: p for p in positions}
    if len(p8_by_position) != len(positions):
        raise ValueError("Duplicate P8 position ID")
    matched = set()
    for row in p7_by_id.values():
        position = row.position
        if position is None or position.position_id not in p8_by_position:
            raise ValueError("P7 position is absent from exact P8 position inventory")
        corresponding = p8_by_position[position.position_id]
        if (
            position.market != corresponding.underlying_symbol
            or position.remaining_quantity != corresponding.remaining_quantity
            or position.lifecycle_state != corresponding.lifecycle_state
            or row.event_sequence < corresponding.transition_sequence
        ):
            raise ValueError("P7/P8 position identity, state or sequence mismatch")
        matched.add(position.position_id)
    reconciliation = (
        "P7_P8_MATCHED" if matched and matched == set(p8_by_position) else "P8_ONLY_UNRECONCILED"
    )
    market_counts = {
        market: sum(p.underlying_symbol == market and not p.is_terminal for p in positions)
        for market in ("NIFTY", "SENSEX")
    }
    pending = snap.pending_plan_count
    slots = tuple(
        X10TypedMarketProjectionV1(
            market,
            market_counts[market],
            0 if pending == 0 else None,
            "INDEX_P8_REPORTED",
        )
        if market in market_counts
        else X10TypedMarketProjectionV1(
            market,
            None,
            None,
            "MCX_UNVERIFIED",
        )
        for market in MARKETS
    )
    ids = tuple(
        sorted(
            (row.paper_trade_id, row.integrity_hash, row.event_sequence)
            for row in p7_by_id.values()
        )
    )
    return X10TypedPortfolioProjectionV1(
        ledger.parent_cycle_id,
        ledger.as_of,
        ledger.sha256(),
        expected_p8_sha256,
        p8_snapshot.event_sequence,
        ids,
        snap.open_position_count,
        pending,
        reconciliation,
        slots,
        "PARTIAL_DESCRIPTIVE",
    )
