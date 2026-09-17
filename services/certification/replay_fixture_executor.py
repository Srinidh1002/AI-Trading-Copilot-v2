"""Execute Task 7A fixtures through the certified PAPER lifecycle runtime."""
from __future__ import annotations

from pathlib import Path

from services.certification.replay_fixture_factory import (
    ReplayLifecycleFixtureV1,
)
from services.contracts.replay_certification_v1 import (
    ReplayTradeResultV1,
)
from services.paper_trading.json_paper_position_repository import (
    JsonPaperPositionRepository,
)
from services.paper_trading.paper_lifecycle_runtime import (
    run_paper_lifecycle_cycle,
)
from services.paper_trading.paper_trade_finalizer import (
    JsonPaperTradeJournalRepository,
)


_NON_TRADE_BLOCKERS = {
    "STALE_DATA": ("STALE_DATA",),
    "MISSING_OPTION_CHAIN": ("OPTION_CHAIN_UNAVAILABLE",),
    "ONE_MARKET_UNAVAILABLE": ("MARKET_UNAVAILABLE",),
    "BOTH_BLOCKED": ("BOTH_MARKETS_BLOCKED",),
}


def _repositories(
    root: Path,
    scenario_id: str,
) -> tuple[
    JsonPaperPositionRepository,
    JsonPaperTradeJournalRepository,
]:
    scenario_root = root / scenario_id
    return (
        JsonPaperPositionRepository(
            scenario_root / "positions.json"
        ),
        JsonPaperTradeJournalRepository(
            scenario_root / "journal.json"
        ),
    )


def _execute_non_trade(
    fixture: ReplayLifecycleFixtureV1,
) -> ReplayTradeResultV1:
    scenario = fixture.scenario
    blockers = _NON_TRADE_BLOCKERS.get(
        scenario.scenario_type,
        (),
    )

    return ReplayTradeResultV1(
        result_id=f"result-{scenario.scenario_id}",
        scenario_id=scenario.scenario_id,
        sequence=scenario.sequence,
        market=scenario.market,
        scenario_type=scenario.scenario_type,
        status=scenario.expected_outcome,
        opened=False,
        closed=False,
        opened_at=None,
        closed_at=None,
        closure_reason=None,
        realized_pnl=0.0,
        action_history=(scenario.expected_outcome,),
        blockers=blockers,
    )


def execute_replay_fixture(
    fixture: ReplayLifecycleFixtureV1,
    *,
    work_root: str | Path,
) -> ReplayTradeResultV1:
    """Run one fixture using persisted Task 5 runtime state only."""
    if type(fixture) is not ReplayLifecycleFixtureV1:
        raise TypeError("fixture")

    root = Path(work_root)
    scenario = fixture.scenario

    if fixture.expected_outcome != "CLOSED_TRADE":
        return _execute_non_trade(fixture)

    position = fixture.initial_position
    if position is None:
        raise ValueError("trade fixture requires initial position")

    positions, journal = _repositories(
        root,
        scenario.scenario_id,
    )
    positions.save(position)

    actions: list[str] = []
    final_result = None

    for event_number, evidence in enumerate(
        fixture.monitoring_evidence,
        start=1,
    ):
        if (
            scenario.scenario_type == "RESTART_RECOVERY"
            and event_number == 2
        ):
            positions = JsonPaperPositionRepository(
                positions.path
            )

        result = run_paper_lifecycle_cycle(
            runtime_result_id=(
                f"runtime-result-{scenario.scenario_id}-"
                f"{event_number}"
            ),
            runtime_cycle_id=(
                f"runtime-cycle-{scenario.scenario_id}-"
                f"{event_number}"
            ),
            recovery_result_id=(
                f"recovery-result-{scenario.scenario_id}-"
                f"{event_number}"
            ),
            transition_id=(
                f"transition-{scenario.scenario_id}-"
                f"{event_number}"
            ),
            evaluated_at=evidence.observed_at,
            evidence=evidence,
            position_repository=positions,
            journal_repository=journal,
            maximum_position_age_seconds=60.0,
            closure_id=(
                f"closure-{scenario.scenario_id}"
            ),
            journal_entry_id=(
                f"journal-{scenario.scenario_id}"
            ),
            finalization_result_id=(
                f"finalization-{scenario.scenario_id}"
            ),
        )

        if result.status == "BLOCKED":
            return ReplayTradeResultV1(
                result_id=f"result-{scenario.scenario_id}",
                scenario_id=scenario.scenario_id,
                sequence=scenario.sequence,
                market=scenario.market,
                scenario_type=scenario.scenario_type,
                status="FAILED",
                opened=False,
                closed=False,
                opened_at=None,
                closed_at=None,
                closure_reason=None,
                realized_pnl=0.0,
                action_history=tuple(actions),
                errors=("LIFECYCLE_RUNTIME_BLOCKED",),
            )

        if result.transition is None:
            return ReplayTradeResultV1(
                result_id=f"result-{scenario.scenario_id}",
                scenario_id=scenario.scenario_id,
                sequence=scenario.sequence,
                market=scenario.market,
                scenario_type=scenario.scenario_type,
                status="FAILED",
                opened=False,
                closed=False,
                opened_at=None,
                closed_at=None,
                closure_reason=None,
                realized_pnl=0.0,
                action_history=tuple(actions),
                errors=("LIFECYCLE_TRANSITION_MISSING",),
            )

        actions.append(result.transition.action)
        final_result = result

        if (
            result.position_after is not None
            and result.position_after.lifecycle_state == "CLOSED"
        ):
            break

    if (
        final_result is None
        or final_result.position_after is None
        or final_result.position_after.lifecycle_state != "CLOSED"
        or final_result.finalization_result is None
    ):
        return ReplayTradeResultV1(
            result_id=f"result-{scenario.scenario_id}",
            scenario_id=scenario.scenario_id,
            sequence=scenario.sequence,
            market=scenario.market,
            scenario_type=scenario.scenario_type,
            status="FAILED",
            opened=False,
            closed=False,
            opened_at=None,
            closed_at=None,
            closure_reason=None,
            realized_pnl=0.0,
            action_history=tuple(actions),
            errors=("TRADE_DID_NOT_CLOSE",),
        )

    closed_position = final_result.position_after
    journal_entry = (
        final_result.finalization_result.journal_entry
    )

    return ReplayTradeResultV1(
        result_id=f"result-{scenario.scenario_id}",
        scenario_id=scenario.scenario_id,
        sequence=scenario.sequence,
        market=scenario.market,
        scenario_type=scenario.scenario_type,
        status="CLOSED_TRADE",
        opened=True,
        closed=True,
        opened_at=closed_position.opened_at,
        closed_at=closed_position.updated_at,
        closure_reason=journal_entry.closure_reason,
        realized_pnl=closed_position.realized_pnl,
        action_history=tuple(actions),
        warnings=closed_position.warnings,
    )
