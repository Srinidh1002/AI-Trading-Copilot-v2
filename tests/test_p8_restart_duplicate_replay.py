from __future__ import annotations

from services.paper_portfolio.paper_portfolio_lifecycle_coordinator import (
    PaperPortfolioLifecycleCoordinator,
)
from services.paper_portfolio.paper_portfolio_persistence_service import (
    PaperPortfolioPersistenceService,
)
from services.paper_portfolio.paper_portfolio_recovery_service import (
    PaperPortfolioRecoveryService,
)
from services.paper_portfolio_repository import PaperPortfolioRepository
from tests.p8_portfolio_harness import (
    PORTFOLIO_ID,
    NOW,
    make_open_p7_snapshot,
    make_p8_policy,
    make_persistence_service,
)


def test_restart_recovers_active_position_and_duplicate_stays_noop(tmp_path):
    service = make_persistence_service(tmp_path)
    coordinator = PaperPortfolioLifecycleCoordinator(service)
    p7 = make_open_p7_snapshot()

    first = coordinator.apply_p7_snapshot(
        portfolio_id=PORTFOLIO_ID,
        policy=make_p8_policy(),
        p7_snapshot=p7,
        result_snapshot_id="p8-snapshot-open",
        portfolio_event_id="p8-event-open",
        update_idempotency_key="p8-update-open",
        updated_at=NOW,
    )

    restarted_service = PaperPortfolioPersistenceService(
        PaperPortfolioRepository(tmp_path / "p8-portfolio.json")
    )
    recovered = PaperPortfolioRecoveryService(restarted_service).recover(
        PORTFOLIO_ID,
        NOW,
    )
    assert recovered.status == "RECOVERED"
    assert recovered.persistence_snapshot.to_json() == first.to_json()

    restarted_coordinator = PaperPortfolioLifecycleCoordinator(restarted_service)
    duplicate = restarted_coordinator.apply_p7_snapshot(
        portfolio_id=PORTFOLIO_ID,
        policy=make_p8_policy(),
        p7_snapshot=p7,
        result_snapshot_id="ignored",
        portfolio_event_id="different-event-is-ignored-by-key",
        update_idempotency_key="p8-update-open",
        updated_at=NOW,
    )
    assert duplicate.to_json() == first.to_json()
