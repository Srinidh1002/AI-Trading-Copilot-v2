"""Task 7A full base-catalogue replay runner and ledger assembly."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from services.certification.replay_fixture_executor import (
    execute_replay_fixture,
)
from services.certification.replay_fixture_factory import (
    build_replay_fixture_catalogue,
)
from services.contracts.replay_certification_v1 import (
    ReplayCertificationLedgerV1,
)


def run_base_replay_certification(
    *,
    work_root: str | Path,
    ledger_id: str,
    generated_at: datetime,
) -> ReplayCertificationLedgerV1:
    """Execute all 120 deterministic base scenarios.

    Safety scenarios remain NO_TRADE or BLOCKED and are never promoted
    into trades. The returned ledger is therefore expected to remain
    incomplete until deterministic replacement trade scenarios are added.
    """
    root = Path(work_root)
    results = tuple(
        execute_replay_fixture(
            fixture,
            work_root=root,
        )
        for fixture in build_replay_fixture_catalogue()
    )

    return ReplayCertificationLedgerV1(
        ledger_id=ledger_id,
        generated_at=generated_at,
        results=results,
        required_closed_trades_per_market=60,
    )
