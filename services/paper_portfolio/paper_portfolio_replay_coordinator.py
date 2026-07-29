"""Deterministic replay coordinator for recovered P8 portfolio state."""
from __future__ import annotations

from services.contracts.paper_portfolio_policy_v1 import PaperPortfolioPolicyV1
from services.contracts.paper_trade_persistence_snapshot_v1 import PaperTradePersistenceSnapshotV1

from .paper_portfolio_lifecycle_coordinator import PaperPortfolioLifecycleCoordinator
from .paper_portfolio_persistence_service import PaperPortfolioPersistenceService
from .paper_portfolio_recovery_service import PaperPortfolioRecoveryService


class PaperPortfolioReplayCoordinator:
    def __init__(self, persistence_service):
        if type(persistence_service) is not PaperPortfolioPersistenceService:
            raise TypeError("persistence_service")
        self.persistence_service = persistence_service
        self.recovery_service = PaperPortfolioRecoveryService(persistence_service)
        self.lifecycle_coordinator = PaperPortfolioLifecycleCoordinator(persistence_service)

    def replay_p7_snapshot(
        self,
        *,
        portfolio_id,
        policy,
        p7_snapshot,
        result_snapshot_id,
        portfolio_event_id,
        update_idempotency_key,
        updated_at,
    ):
        if type(policy) is not PaperPortfolioPolicyV1:
            raise TypeError("policy")
        if type(p7_snapshot) is not PaperTradePersistenceSnapshotV1:
            raise TypeError("p7_snapshot")

        recovery = self.recovery_service.recover(portfolio_id, updated_at)
        if recovery.status != "RECOVERED":
            return recovery, None

        before = recovery.persistence_snapshot
        after = self.lifecycle_coordinator.apply_p7_snapshot(
            portfolio_id=portfolio_id,
            policy=policy,
            p7_snapshot=p7_snapshot,
            result_snapshot_id=result_snapshot_id,
            portfolio_event_id=portfolio_event_id,
            update_idempotency_key=update_idempotency_key,
            updated_at=updated_at,
        )
        return before, after
