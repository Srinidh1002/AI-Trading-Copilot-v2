"""Task 9 selected-market PAPER lifecycle and durable persistence runtime.

This module begins only after authoritative two-market selection and exact P6
planning have completed. It performs no market-provider reads and exposes no
broker-submission authority.

Execution order:

1. Preserve the exact selected-market P6 result.
2. Build the canonical typed P8/P7 new-entry input.
3. Execute P8 admission.
4. Execute P7 PAPER entry lifecycle.
5. Apply the P8 portfolio update when an entry opens.
6. Persist the complete cycle result in the atomic orchestration journal.
7. Return explicit PERSISTENCE-stage evidence.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path

from services.contracts.paper_orchestration_cycle_input_v1 import (
    PaperOrchestrationCycleInputV1,
)
from services.contracts.paper_orchestration_cycle_result_v1 import (
    PaperOrchestrationCycleResultV1,
)
from services.contracts.paper_orchestration_journal_record_v1 import (
    PaperOrchestrationJournalRecordV1,
)
from services.contracts.paper_orchestration_stage_result_v1 import (
    PaperOrchestrationStageResultV1,
)
from services.paper_orchestration.certified_runtime_composition import (
    build_default_automated_paper_authorities,
)
from services.paper_orchestration.new_entry_paper_lifecycle_executor import (
    NewEntryPaperLifecycleExecutor,
    NewEntryPaperLifecycleResultV1,
)
from services.paper_orchestration.paper_orchestration_journal import (
    PaperOrchestrationJournal,
)
from services.paper_orchestration.selected_market_p6_planning_runtime import (
    SelectedMarketP6PlanningResultV1,
    adapt_selected_market_p6_to_cycle_result,
)
from services.paper_portfolio.paper_portfolio_persistence_service import (
    PaperPortfolioPersistenceService,
)
from services.paper_portfolio_repository import (
    PaperPortfolioRepository,
)
from services.paper_trade_repository import (
    PaperTradeRepository,
)
from services.paper_trading.paper_trade_persistence_service import (
    PaperTradePersistenceService,
)


def _aware(
    value: object,
    name: str,
) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(
            f"{name} must be timezone-aware"
        )
    return value


def _messages(
    *groups: tuple[str, ...],
) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            str(item)
            for group in groups
            for item in group
            if str(item).strip()
        )
    )


def _lifecycle_stage_status(
    lifecycle_status: str,
) -> str:
    if lifecycle_status == "ENTRY_BLOCKED":
        return "BLOCKED"
    if lifecycle_status in {
        "WAITING_FOR_ENTRY",
        "ENTRY_CLOSED",
    }:
        return "NO_ACTION"
    if lifecycle_status == "OPEN":
        return "COMPLETED"
    raise ValueError(
        "lifecycle status does not produce a P7 stage"
    )


def _cycle_status(
    lifecycle_status: str,
) -> str:
    if lifecycle_status in {
        "ADMISSION_BLOCKED",
        "ENTRY_BLOCKED",
    }:
        return "BLOCKED"
    if lifecycle_status in {
        "NO_CAPACITY",
        "WAITING_FOR_ENTRY",
        "ENTRY_CLOSED",
    }:
        return "COMPLETED_NO_ACTION"
    if lifecycle_status == "OPEN":
        return "COMPLETED"
    raise ValueError(
        "unsupported lifecycle status"
    )


def execute_task9_selected_market_lifecycle(
    *,
    selected_cycle: PaperOrchestrationCycleInputV1,
    selected_planning: SelectedMarketP6PlanningResultV1,
    available_capital: float,
    evaluated_at: datetime,
    persistence_root: str | Path = (
        "data/paper_trading/certified_runtime/task9"
    ),
    portfolio_id: str = "task9-certified-paper-portfolio",
    prediction_id: str | None = None,
    task9_binding_persistor=None,
    task9_observation_sink=None,
    task9_pending_entry_persistor=None,
) -> PaperOrchestrationCycleResultV1:
    """Execute selected-only P7/P8 and persist exact PAPER state.

    The function accepts only an already-completed selected P6 result. It does
    not evaluate another market, invoke P6 again, or reread a provider.
    """

    if type(selected_cycle) is not (
        PaperOrchestrationCycleInputV1
    ):
        raise TypeError(
            "selected_cycle must be exact "
            "PaperOrchestrationCycleInputV1"
        )
    if type(selected_planning) is not (
        SelectedMarketP6PlanningResultV1
    ):
        raise TypeError(
            "selected_planning must be exact "
            "SelectedMarketP6PlanningResultV1"
        )
    if (
        isinstance(available_capital, bool)
        or type(available_capital) not in (int, float)
        or available_capital <= 0
    ):
        raise ValueError(
            "available_capital must be positive"
        )
    if type(portfolio_id) is not str or not portfolio_id.strip():
        raise ValueError(
            "portfolio_id must be non-empty"
        )
    if prediction_id is not None and (
        type(prediction_id) is not str or not prediction_id.strip()
    ):
        raise ValueError("prediction_id")
    if task9_binding_persistor is not None and not callable(task9_binding_persistor):
        raise TypeError("task9_binding_persistor")
    if task9_observation_sink is not None and not callable(task9_observation_sink):
        raise TypeError("task9_observation_sink")
    if task9_pending_entry_persistor is not None and not callable(task9_pending_entry_persistor):
        raise TypeError("task9_pending_entry_persistor")

    now = _aware(
        evaluated_at,
        "evaluated_at",
    )

    if selected_planning.status != "READY":
        return adapt_selected_market_p6_to_cycle_result(
            selected_cycle=selected_cycle,
            selected_planning=selected_planning,
        )

    planning_result = selected_planning.planning_result
    if planning_result is None:
        raise ValueError(
            "READY selected planning requires planning_result"
        )
    if planning_result.status != "READY":
        raise ValueError(
            "selected P6 planning result must be READY"
        )
    if planning_result.execution_mode != "PAPER":
        raise ValueError(
            "selected P6 result must remain PAPER-only"
        )
    if planning_result.live_execution_eligible is not False:
        raise ValueError(
            "selected P6 result cannot be live eligible"
        )

    p6_cycle_result = adapt_selected_market_p6_to_cycle_result(
        selected_cycle=selected_cycle,
        selected_planning=selected_planning,
    )
    p6_stage = p6_cycle_result.stage_results[0]

    root = Path(persistence_root)
    root.mkdir(
        parents=True,
        exist_ok=True,
    )

    trade_service = PaperTradePersistenceService(
        PaperTradeRepository(
            root / "p7_trades.json"
        )
    )
    portfolio_service = (
        PaperPortfolioPersistenceService(
            PaperPortfolioRepository(
                root / "p8_portfolios.json"
            )
        )
    )
    journal = PaperOrchestrationJournal(
        root / "selected_cycle_journal.json"
    )

    authorities = (
        build_default_automated_paper_authorities(
            portfolio_id=portfolio_id,
            available_capital=float(
                available_capital
            ),
        )
    )

    new_entry_input = (
        authorities.new_entry_input_factory(
            selected_cycle,
            planning_result,
        )
    )
    if prediction_id is not None:
        new_entry_input = replace(
            new_entry_input,
            prediction_id=prediction_id,
        )

    if task9_observation_sink is not None:
        task9_observation_sink(new_entry_input.observation)

    lifecycle_executor = NewEntryPaperLifecycleExecutor(
        portfolio_persistence_service=(
            portfolio_service
        ),
        trade_persistence_service=trade_service,
        broker_order_submission=False,
    )

    lifecycle_result = lifecycle_executor.execute(
        new_entry_input
    )
    if lifecycle_result.status == "OPEN" and task9_binding_persistor is not None:
        task9_binding_persistor(new_entry_input, lifecycle_result)
    if lifecycle_result.status == "WAITING_FOR_ENTRY" and task9_pending_entry_persistor is not None:
        task9_pending_entry_persistor(new_entry_input, lifecycle_result)
    if type(lifecycle_result) is not (
        NewEntryPaperLifecycleResultV1
    ):
        raise TypeError(
            "new-entry authority must return exact "
            "NewEntryPaperLifecycleResultV1"
        )

    stages: list[
        PaperOrchestrationStageResultV1
    ] = [p6_stage]

    admission_status = (
        "BLOCKED"
        if lifecycle_result.status
        == "ADMISSION_BLOCKED"
        else "NO_ACTION"
        if lifecycle_result.status
        == "NO_CAPACITY"
        else "COMPLETED"
    )

    stages.append(
        PaperOrchestrationStageResultV1(
            stage_result_id=(
                f"{selected_cycle.cycle_id}:"
                "task9:p8-admission"
            ),
            cycle_id=selected_cycle.cycle_id,
            stage="P8_ADMISSION",
            status=admission_status,
            started_at=now,
            completed_at=now,
            source_result_type=(
                type(
                    lifecycle_result.admission_result
                ).__name__
            ),
            source_result_id=getattr(
                lifecycle_result.admission_result,
                "admission_result_id",
                getattr(
                    lifecycle_result.admission_result,
                    "result_id",
                    None,
                ),
            ),
            blockers=lifecycle_result.blockers,
            warnings=lifecycle_result.warnings,
            metadata={
                "scope": (
                    "TASK9_SELECTED_MARKET"
                ),
                "portfolio_id": portfolio_id,
                "broker_order_submission": False,
            },
        )
    )

    if lifecycle_result.status not in {
        "ADMISSION_BLOCKED",
        "NO_CAPACITY",
    }:
        stages.append(
            PaperOrchestrationStageResultV1(
                stage_result_id=(
                    f"{selected_cycle.cycle_id}:"
                    "task9:p7-lifecycle"
                ),
                cycle_id=selected_cycle.cycle_id,
                stage="P7_LIFECYCLE",
                status=_lifecycle_stage_status(
                    lifecycle_result.status
                ),
                started_at=now,
                completed_at=now,
                source_result_type=(
                    None
                    if lifecycle_result.entry_result
                    is None
                    else type(
                        lifecycle_result.entry_result
                    ).__name__
                ),
                source_result_id=getattr(
                    lifecycle_result.entry_result,
                    "evaluation_result_id",
                    getattr(
                        lifecycle_result.entry_result,
                        "result_id",
                        None,
                    ),
                ),
                paper_action_occurred=(
                    lifecycle_result.status == "OPEN"
                ),
                blockers=lifecycle_result.blockers,
                warnings=lifecycle_result.warnings,
                metadata={
                    "paper_trade_id": (
                        None
                        if lifecycle_result.p7_snapshot
                        is None
                        else lifecycle_result
                        .p7_snapshot
                        .paper_trade_id
                    ),
                    "broker_order_submission": False,
                },
            )
        )

    if lifecycle_result.status == "OPEN":
        if (
            lifecycle_result.p7_snapshot is None
            or lifecycle_result.p8_snapshot is None
        ):
            raise ValueError(
                "OPEN lifecycle requires durable "
                "P7 and P8 snapshots"
            )

        persisted_trade = trade_service.get(
            lifecycle_result.p7_snapshot.paper_trade_id
        )
        persisted_portfolio = portfolio_service.get(
            lifecycle_result.p8_snapshot.portfolio_id
        )

        if persisted_trade is None:
            raise RuntimeError(
                "P7 durable snapshot was not recovered"
            )
        if persisted_portfolio is None:
            raise RuntimeError(
                "P8 durable snapshot was not recovered"
            )
        if (
            persisted_trade.integrity_hash
            != lifecycle_result.p7_snapshot.integrity_hash
        ):
            raise RuntimeError(
                "P7 durable snapshot integrity mismatch"
            )
        if (
            persisted_portfolio.integrity_hash
            != lifecycle_result.p8_snapshot.integrity_hash
        ):
            raise RuntimeError(
                "P8 durable snapshot integrity mismatch"
            )

        stages.append(
            PaperOrchestrationStageResultV1(
                stage_result_id=(
                    f"{selected_cycle.cycle_id}:"
                    "task9:p8-portfolio-update"
                ),
                cycle_id=selected_cycle.cycle_id,
                stage="P8_PORTFOLIO_UPDATE",
                status="COMPLETED",
                started_at=now,
                completed_at=now,
                source_result_type=(
                    type(
                        lifecycle_result.p8_snapshot
                    ).__name__
                ),
                source_result_id=(
                    lifecycle_result
                    .p8_snapshot
                    .portfolio_id
                ),
                paper_action_occurred=True,
                warnings=lifecycle_result.warnings,
                metadata={
                    "portfolio_integrity_hash": (
                        lifecycle_result
                        .p8_snapshot
                        .integrity_hash
                    ),
                    "trade_integrity_hash": (
                        lifecycle_result
                        .p7_snapshot
                        .integrity_hash
                    ),
                    "broker_order_submission": False,
                },
            )
        )

    warnings = _messages(
        p6_cycle_result.warnings,
        lifecycle_result.warnings,
    )
    blockers = _messages(
        p6_cycle_result.blockers,
        lifecycle_result.blockers,
    )

    persistence_stage = (
        PaperOrchestrationStageResultV1(
            stage_result_id=(
                f"{selected_cycle.cycle_id}:"
                "task9:persistence"
            ),
            cycle_id=selected_cycle.cycle_id,
            stage="PERSISTENCE",
            status="COMPLETED",
            started_at=now,
            completed_at=now,
            source_result_type=(
                "PaperOrchestrationJournalRecordV1"
            ),
            source_result_id=(
                f"{selected_cycle.cycle_id}:"
                "task9:journal-record"
            ),
            source_semantic_hash=(
                selected_cycle.semantic_hash()
            ),
            paper_action_occurred=(
                lifecycle_result.status == "OPEN"
            ),
            warnings=warnings,
            metadata={
                "journal_path": str(
                    journal.file_path
                ),
                "p7_repository_path": str(
                    trade_service.repository.file_path
                ),
                "p8_repository_path": str(
                    portfolio_service
                    .repository
                    .file_path
                ),
                "lifecycle_status": (
                    lifecycle_result.status
                ),
                "broker_order_submission": False,
                "execution_mode": "PAPER",
                "live_execution_eligible": False,
            },
        )
    )
    stages.append(persistence_stage)

    cycle_result = PaperOrchestrationCycleResultV1(
        cycle_result_id=(
            f"{selected_cycle.cycle_id}:"
            "task9:selected-lifecycle-result"
        ),
        cycle_id=selected_cycle.cycle_id,
        cycle_idempotency_key=(
            selected_cycle.cycle_idempotency_key
        ),
        cycle_input_semantic_hash=(
            selected_cycle.semantic_hash()
        ),
        cycle_status=_cycle_status(
            lifecycle_result.status
        ),
        terminal_stage="PERSISTENCE",
        started_at=p6_cycle_result.started_at,
        completed_at=now,
        stage_results=tuple(stages),
        paper_actions=(
            ("OPEN_POSITION",)
            if lifecycle_result.status == "OPEN"
            else ()
        ),
        blockers=blockers,
        warnings=warnings,
        metadata={
            "scope": (
                "TASK9_SELECTED_MARKET_P6_P7_P8"
            ),
            "parent_cycle_id": (
                selected_planning
                .bridge
                .parent_cycle_id
            ),
            "parent_decision_id": (
                selected_planning
                .bridge
                .parent_decision_id
            ),
            "selected_market": (
                selected_planning
                .bridge
                .selected_market
            ),
            "selected_candidate_id": (
                selected_planning
                .bridge
                .candidate_id
            ),
            "p6_integration_id": (
                planning_result.integration_id
            ),
            "lifecycle_status": (
                lifecycle_result.status
            ),
            "portfolio_id": portfolio_id,
            "broker_order_submission": False,
        },
    )

    record = PaperOrchestrationJournalRecordV1(
        journal_record_id=(
            f"{selected_cycle.cycle_id}:"
            "task9:journal-record"
        ),
        cycle_idempotency_key=(
            selected_cycle.cycle_idempotency_key
        ),
        cycle_input_semantic_hash=(
            selected_cycle.semantic_hash()
        ),
        cycle_result=cycle_result,
        persisted_at=now,
    )

    journal.save(record)

    recovered = journal.get_raw(
        selected_cycle.cycle_idempotency_key
    )
    if recovered is None:
        raise RuntimeError(
            "Task 9 cycle journal record "
            "was not recovered"
        )
    if (
        recovered.get("integrity_hash")
        != record.integrity_hash
    ):
        raise RuntimeError(
            "Task 9 cycle journal integrity mismatch"
        )

    return cycle_result
