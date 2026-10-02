"""Bind supplied exposure records to X9; no reservation or capital changes."""

from __future__ import annotations

from collections import defaultdict

from services.x7.contracts_v1 import MARKETS
from services.x9.contracts_v1 import X9FiveMarketLedgerV1
from services.x10.contracts_v1 import (
    X10MarketExposureReferenceV1,
    X10PortfolioReadinessV1,
)


def build_x10_portfolio_readiness_v1(
    *,
    ledger: X9FiveMarketLedgerV1,
    references: tuple[X10MarketExposureReferenceV1, ...],
) -> X10PortfolioReadinessV1:
    if type(ledger) is not X9FiveMarketLedgerV1:
        raise TypeError("X10 requires an immutable X9 parent ledger")
    if (
        type(references) is not tuple
        or len(references) != len(MARKETS)
        or any(type(row) is not X10MarketExposureReferenceV1 for row in references)
    ):
        raise ValueError("X10 requires five explicit exposure references")
    by_market = {row.market: row for row in references}
    if len(by_market) != len(MARKETS) or set(by_market) != set(MARKETS):
        raise ValueError("Missing or duplicate exposure market")
    for row in references:
        if (row.observed_at is not None and row.observed_at > ledger.as_of) or (
            row.available_at is not None and row.available_at > ledger.as_of
        ):
            raise ValueError("Exposure record was not known at cycle time")
    ordered = tuple(by_market[market] for market in MARKETS)
    shared = defaultdict(list)
    for row in ordered:
        if row.source_kind != "NONE":
            shared[(row.source_id, row.source_record_id)].append(row.market)
    shared_groups = tuple(
        tuple(markets) for _, markets in sorted(shared.items()) if len(markets) > 1
    )
    blockers = tuple(
        f"{row.market}_EXPOSURE_{row.state}" for row in ordered if row.state != "REPORTED"
    )
    warnings = tuple(f"SHARED_SOURCE_{'_'.join(group)}" for group in shared_groups) + tuple(
        f"{row.market}_EXTERNAL_RESEARCH_NOT_P8_AUTHORITY"
        for row in ordered
        if row.state == "REPORTED" and row.source_kind == "EXTERNAL_RESEARCH"
    )
    total_open = (
        sum(row.open_position_count for row in ordered)
        if not blockers and not shared_groups
        else None
    )
    total_pending = (
        sum(row.pending_reservation_count for row in ordered)
        if not blockers and not shared_groups
        else None
    )
    return X10PortfolioReadinessV1(
        ledger.parent_cycle_id,
        ledger.as_of,
        ledger.sha256(),
        ordered,
        "INCOMPLETE_RESEARCH" if blockers or shared_groups else "COMPLETE_RESEARCH",
        total_open,
        total_pending,
        shared_groups,
        None,
        None,
        False,
        blockers,
        warnings,
    )
