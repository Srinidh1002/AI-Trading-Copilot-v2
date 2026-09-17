from __future__ import annotations

import hashlib
from collections.abc import Callable

from services.contracts.paper_orchestration_cycle_input_v1 import (
    PaperOrchestrationCycleInputV1,
)
from services.contracts.paper_portfolio_policy_v1 import (
    PaperPortfolioPolicyV1,
)
from services.contracts.paper_trade_persistence_snapshot_v1 import (
    PaperTradePersistenceSnapshotV1,
)
from services.contracts.paper_trade_position_evaluation_input_v1 import (
    PaperTradePositionEvaluationInputV1,
)
from services.paper_orchestration.existing_position_monitoring_executor import (
    ExistingPositionMonitoringInputV1,
)


P7SnapshotProvider = Callable[
    [PaperOrchestrationCycleInputV1],
    PaperTradePersistenceSnapshotV1,
]
PortfolioPolicyProvider = Callable[
    [PaperOrchestrationCycleInputV1, PaperTradePersistenceSnapshotV1],
    PaperPortfolioPolicyV1,
]
PositionEvaluationInputBuilder = Callable[
    [
        PaperOrchestrationCycleInputV1,
        PaperTradePersistenceSnapshotV1,
    ],
    PaperTradePositionEvaluationInputV1,
]


def _identity(namespace: str, *parts: object) -> str:
    payload = "|".join((namespace, *(str(part).strip() for part in parts)))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"{namespace}-{digest}"


class CertifiedMonitoringInputFactory:
    """Build one exact existing-position monitoring input.

    The domain-specific P7 evaluation input remains owned by an injected typed
    builder. This boundary supplies cycle identity, exact persisted P7 state,
    exact P8 policy, and deterministic update identifiers.
    """

    def __init__(
        self,
        *,
        portfolio_id: str,
        p7_snapshot_provider: P7SnapshotProvider,
        portfolio_policy_provider: PortfolioPolicyProvider,
        evaluation_input_builder: PositionEvaluationInputBuilder,
    ) -> None:
        if type(portfolio_id) is not str or not portfolio_id.strip():
            raise ValueError("portfolio_id must be non-empty")
        if not callable(p7_snapshot_provider):
            raise TypeError("p7_snapshot_provider must be callable")
        if not callable(portfolio_policy_provider):
            raise TypeError("portfolio_policy_provider must be callable")
        if not callable(evaluation_input_builder):
            raise TypeError("evaluation_input_builder must be callable")

        self.portfolio_id = portfolio_id.strip()
        self.p7_snapshot_provider = p7_snapshot_provider
        self.portfolio_policy_provider = portfolio_policy_provider
        self.evaluation_input_builder = evaluation_input_builder

    def __call__(
        self,
        cycle_input: PaperOrchestrationCycleInputV1,
    ) -> ExistingPositionMonitoringInputV1:
        if type(cycle_input) is not PaperOrchestrationCycleInputV1:
            raise TypeError(
                "cycle_input must be exact PaperOrchestrationCycleInputV1"
            )

        p7_snapshot = self.p7_snapshot_provider(cycle_input)
        if type(p7_snapshot) is not PaperTradePersistenceSnapshotV1:
            raise TypeError(
                "p7_snapshot_provider must return exact "
                "PaperTradePersistenceSnapshotV1"
            )
        if p7_snapshot.position is None:
            raise ValueError("monitoring requires an existing P7 position")

        portfolio_policy = self.portfolio_policy_provider(
            cycle_input,
            p7_snapshot,
        )
        if type(portfolio_policy) is not PaperPortfolioPolicyV1:
            raise TypeError(
                "portfolio_policy_provider must return exact "
                "PaperPortfolioPolicyV1"
            )

        evaluation_input = self.evaluation_input_builder(
            cycle_input,
            p7_snapshot,
        )
        if type(evaluation_input) is not PaperTradePositionEvaluationInputV1:
            raise TypeError(
                "evaluation_input_builder must return exact "
                "PaperTradePositionEvaluationInputV1"
            )

        if (
            evaluation_input.position.position_id
            != p7_snapshot.position.position_id
        ):
            raise ValueError("monitoring P7 position identity mismatch")
        if evaluation_input.evaluation_timestamp != cycle_input.cycle_requested_at:
            raise ValueError(
                "evaluation timestamp must equal cycle_requested_at"
            )

        basis = (
            cycle_input.cycle_id,
            cycle_input.cycle_idempotency_key,
            p7_snapshot.paper_trade_id,
            p7_snapshot.position.position_id,
            self.portfolio_id,
            cycle_input.trading_day_id,
        )

        return ExistingPositionMonitoringInputV1(
            portfolio_id=self.portfolio_id,
            result_snapshot_id=_identity(
                "monitoring-portfolio-snapshot",
                *basis,
            ),
            portfolio_event_id=cycle_input.p8_update_event_id,
            update_idempotency_key=(
                cycle_input.p8_update_idempotency_key
            ),
            updated_at=cycle_input.cycle_requested_at,
            portfolio_policy=portfolio_policy,
            p7_snapshot=p7_snapshot,
            evaluation_input=evaluation_input,
        )
