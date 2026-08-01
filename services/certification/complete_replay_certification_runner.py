"""Complete Task 7A replay certification with replacement trades."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from services.certification.base_replay_certification_runner import (
    run_base_replay_certification,
)
from services.certification.replay_fixture_executor import (
    execute_replay_fixture,
)
from services.certification.replay_fixture_factory import (
    build_replay_lifecycle_fixture,
)
from services.certification.replacement_replay_scenarios import (
    build_replacement_trade_scenarios,
)
from services.contracts.replay_certification_v1 import (
    ReplayCertificationLedgerV1,
)


def run_complete_replay_certification(
    *,
    work_root: str | Path,
    ledger_id: str,
    generated_at: datetime,
) -> ReplayCertificationLedgerV1:
    root = Path(work_root)

    base = run_base_replay_certification(
        work_root=root / "base",
        ledger_id=f"{ledger_id}:base",
        generated_at=generated_at,
    )

    replacement_results = tuple(
        execute_replay_fixture(
            build_replay_lifecycle_fixture(scenario),
            work_root=root / "replacements",
        )
        for scenario in build_replacement_trade_scenarios()
    )

    return ReplayCertificationLedgerV1(
        ledger_id=ledger_id,
        generated_at=generated_at,
        results=base.results + replacement_results,
        required_closed_trades_per_market=60,
    )
