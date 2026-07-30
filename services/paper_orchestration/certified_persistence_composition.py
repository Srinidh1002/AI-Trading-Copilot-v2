from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from services.paper_orchestration.deterministic_cycle_coordinator import (
    DeterministicPaperOrchestrationCycleCoordinator,
)
from services.paper_orchestration.paper_orchestration_journal import (
    PaperOrchestrationJournal,
)
from services.paper_orchestration.restart_recovery_operation import (
    RestartRecoveryOperation,
    RestartRecoveryTargetV1,
)


Clock = Callable[[], datetime]


@dataclass(frozen=True, slots=True)
class CertifiedPersistencePathsV1:
    root_directory: Path
    opportunity_journal_path: Path
    monitoring_journal_path: Path
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "certified_persistence_paths.v1"

    def __post_init__(self) -> None:
        root = Path(self.root_directory)
        opportunity = Path(self.opportunity_journal_path)
        monitoring = Path(self.monitoring_journal_path)

        if opportunity == monitoring:
            raise ValueError(
                "opportunity and monitoring journals must be separate"
            )
        for path in (opportunity, monitoring):
            try:
                path.relative_to(root)
            except ValueError as exc:
                raise ValueError(
                    "journal paths must remain under root_directory"
                ) from exc

        object.__setattr__(self, "root_directory", root)
        object.__setattr__(self, "opportunity_journal_path", opportunity)
        object.__setattr__(self, "monitoring_journal_path", monitoring)

        if self.execution_mode != "PAPER":
            raise ValueError("execution_mode must be PAPER")
        if self.live_execution_eligible:
            raise ValueError("live execution is not eligible")
        if self.schema_version != "certified_persistence_paths.v1":
            raise ValueError("unsupported schema_version")


def build_certified_persistence_paths(
    root_directory: str | Path = "data/paper_trading/certified_runtime",
) -> CertifiedPersistencePathsV1:
    root = Path(root_directory)
    return CertifiedPersistencePathsV1(
        root_directory=root,
        opportunity_journal_path=(
            root / "opportunity_orchestration_journal.json"
        ),
        monitoring_journal_path=(
            root / "monitoring_orchestration_journal.json"
        ),
    )


@dataclass(frozen=True, slots=True)
class CertifiedCoordinatorPairV1:
    opportunity_journal: PaperOrchestrationJournal
    monitoring_journal: PaperOrchestrationJournal
    opportunity_coordinator: DeterministicPaperOrchestrationCycleCoordinator
    monitoring_coordinator: DeterministicPaperOrchestrationCycleCoordinator
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "certified_coordinator_pair.v1"

    def __post_init__(self) -> None:
        if type(self.opportunity_journal) is not PaperOrchestrationJournal:
            raise TypeError("opportunity_journal")
        if type(self.monitoring_journal) is not PaperOrchestrationJournal:
            raise TypeError("monitoring_journal")
        if (
            type(self.opportunity_coordinator)
            is not DeterministicPaperOrchestrationCycleCoordinator
        ):
            raise TypeError("opportunity_coordinator")
        if (
            type(self.monitoring_coordinator)
            is not DeterministicPaperOrchestrationCycleCoordinator
        ):
            raise TypeError("monitoring_coordinator")
        if self.opportunity_journal.file_path == self.monitoring_journal.file_path:
            raise ValueError("coordinators must not share one journal file")
        if self.execution_mode != "PAPER":
            raise ValueError("execution_mode must be PAPER")
        if self.live_execution_eligible:
            raise ValueError("live execution is not eligible")
        if self.schema_version != "certified_coordinator_pair.v1":
            raise ValueError("unsupported schema_version")


def build_certified_coordinators(
    *,
    opportunity_cycle_executor: Callable,
    monitoring_cycle_executor: Callable,
    clock: Clock,
    paths: CertifiedPersistencePathsV1 | None = None,
) -> CertifiedCoordinatorPairV1:
    if not callable(opportunity_cycle_executor):
        raise TypeError("opportunity_cycle_executor must be callable")
    if not callable(monitoring_cycle_executor):
        raise TypeError("monitoring_cycle_executor must be callable")
    if not callable(clock):
        raise TypeError("clock must be callable")
    paths = paths or build_certified_persistence_paths()
    if type(paths) is not CertifiedPersistencePathsV1:
        raise TypeError("paths must be exact CertifiedPersistencePathsV1")

    opportunity_journal = PaperOrchestrationJournal(
        paths.opportunity_journal_path
    )
    monitoring_journal = PaperOrchestrationJournal(
        paths.monitoring_journal_path
    )

    return CertifiedCoordinatorPairV1(
        opportunity_journal=opportunity_journal,
        monitoring_journal=monitoring_journal,
        opportunity_coordinator=(
            DeterministicPaperOrchestrationCycleCoordinator(
                journal=opportunity_journal,
                cycle_executor=opportunity_cycle_executor,
                clock=clock,
            )
        ),
        monitoring_coordinator=(
            DeterministicPaperOrchestrationCycleCoordinator(
                journal=monitoring_journal,
                cycle_executor=monitoring_cycle_executor,
                clock=clock,
            )
        ),
    )


def build_certified_restart_recovery(
    *,
    p7_trade_ids: Iterable[str],
    p8_portfolio_ids: Iterable[str],
    p7_recovery_authority: Callable,
    p8_recovery_authority: Callable,
    clock: Clock,
) -> RestartRecoveryOperation:
    if not callable(p7_recovery_authority):
        raise TypeError("p7_recovery_authority must be callable")
    if not callable(p8_recovery_authority):
        raise TypeError("p8_recovery_authority must be callable")

    targets = tuple(
        RestartRecoveryTargetV1(
            target_type="P7_TRADE",
            target_id=target_id,
            recovery_authority=p7_recovery_authority,
        )
        for target_id in p7_trade_ids
    ) + tuple(
        RestartRecoveryTargetV1(
            target_type="P8_PORTFOLIO",
            target_id=target_id,
            recovery_authority=p8_recovery_authority,
        )
        for target_id in p8_portfolio_ids
    )

    return RestartRecoveryOperation(
        targets=targets,
        clock=clock,
    )
