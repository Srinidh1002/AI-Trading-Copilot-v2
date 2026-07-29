"""Fail-closed recovery of typed P8 PAPER portfolio snapshots."""
from __future__ import annotations

from datetime import datetime

from services.contracts.paper_portfolio_recovery_result_v1 import (
    PaperPortfolioRecoveryResultV1,
)
from .paper_portfolio_persistence_service import PaperPortfolioPersistenceService


class PaperPortfolioRecoveryService:
    def __init__(self, persistence_service):
        if type(persistence_service) is not PaperPortfolioPersistenceService:
            raise TypeError("persistence_service")
        self.persistence_service = persistence_service

    def recover(self, portfolio_id, recovered_at):
        if not isinstance(recovered_at, datetime) or recovered_at.tzinfo is None:
            raise ValueError("recovered_at must be timezone-aware")
        try:
            snapshot = self.persistence_service.get(portfolio_id)
        except (TypeError, ValueError) as exc:
            return PaperPortfolioRecoveryResultV1(
                portfolio_id=str(portfolio_id).strip(),
                status="CORRUPT",
                recovered_at=recovered_at,
                reconciliation_codes=("PERSISTENCE_DECODE_FAILED",),
                blockers=(type(exc).__name__,),
            )

        if snapshot is None:
            return PaperPortfolioRecoveryResultV1(
                portfolio_id=str(portfolio_id).strip(),
                status="BLOCKED",
                recovered_at=recovered_at,
                blockers=("PORTFOLIO_NOT_FOUND",),
            )

        return PaperPortfolioRecoveryResultV1(
            portfolio_id=snapshot.portfolio_id,
            status="RECOVERED",
            recovered_at=recovered_at,
            persistence_snapshot=snapshot,
        )

    def recover_all(self, recovered_at):
        results = []
        seen = set()
        for snapshot in self.persistence_service.list_all():
            if snapshot.portfolio_id in seen:
                raise ValueError("duplicate portfolio")
            seen.add(snapshot.portfolio_id)
            results.append(
                PaperPortfolioRecoveryResultV1(
                    portfolio_id=snapshot.portfolio_id,
                    status="RECOVERED",
                    recovered_at=recovered_at,
                    persistence_snapshot=snapshot,
                )
            )
        return tuple(results)
