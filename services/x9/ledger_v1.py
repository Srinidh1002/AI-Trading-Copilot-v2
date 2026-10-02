"""Cross-market completeness and point-in-time identity; no market selection."""

from __future__ import annotations

import math
from datetime import datetime

from services.x7.contracts_v1 import MARKETS, _aware, _text
from services.x8.contracts_v1 import X8RegimeReadinessV1
from services.x9.contracts_v1 import X9FiveMarketLedgerV1, X9MarketSlotV1


def build_x9_five_market_ledger_v1(
    *,
    parent_cycle_id: str,
    as_of: datetime,
    readiness: tuple[X8RegimeReadinessV1, ...],
    max_skew_seconds: float,
) -> X9FiveMarketLedgerV1:
    if not _text(parent_cycle_id) or not _aware(as_of):
        raise ValueError("Caller must provide an exact parent cycle and aware time")
    if (
        type(max_skew_seconds) not in (int, float)
        or not math.isfinite(max_skew_seconds)
        or max_skew_seconds < 0
    ):
        raise ValueError("Explicit non-negative finite skew budget is required")
    if (
        type(readiness) is not tuple
        or len(readiness) != len(MARKETS)
        or any(type(row) is not X8RegimeReadinessV1 for row in readiness)
    ):
        raise ValueError("All five typed X8 readiness results are required")
    by_market = {row.market: row for row in readiness}
    if len(by_market) != len(MARKETS) or set(by_market) != set(MARKETS):
        raise ValueError("Duplicate or missing market; do not silently select a subset")
    if len({(row.market, row.session_id, row.capture_id) for row in readiness}) != 5:
        raise ValueError("Duplicate capture identities")
    if any(row.as_of > as_of for row in readiness):
        raise ValueError("Future capture cannot enter the parent cycle")
    skew = max((as_of - row.as_of).total_seconds() for row in readiness)
    if skew > max_skew_seconds:
        raise ValueError("Five-market capture skew exceeds the caller budget")
    slots = tuple(
        X9MarketSlotV1(
            market,
            by_market[market].sha256(),
            by_market[market].as_of,
            by_market[market].status,
        )
        for market in MARKETS
    )
    blockers = tuple(
        f"{slot.market}_REGIME_READINESS_{slot.regime_readiness}"
        for slot in slots
        if slot.regime_readiness != "READY"
    )
    return X9FiveMarketLedgerV1(
        parent_cycle_id,
        as_of,
        slots,
        "INCOMPLETE_RESEARCH" if blockers else "COMPLETE_RESEARCH",
        float(skew),
        None,
        (),
        blockers,
    )
