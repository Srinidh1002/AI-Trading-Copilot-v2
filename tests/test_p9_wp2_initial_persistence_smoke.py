from datetime import datetime, timezone

from services.contracts.paper_portfolio_persistence_snapshot_v1 import (
    PaperPortfolioPersistenceSnapshotV1,
)
from services.contracts.paper_portfolio_policy_v1 import (
    PaperPortfolioPolicyV1,
)
from services.paper_orchestration.paper_state_factories import (
    build_initial_paper_portfolio_snapshot,
)
from services.paper_portfolio.paper_portfolio_persistence_service import (
    PaperPortfolioPersistenceService,
)
from services.paper_portfolio_repository import (
    PaperPortfolioRepository,
)


NOW = datetime(2026, 1, 8, 9, 30, tzinfo=timezone.utc)


def policy():
    return PaperPortfolioPolicyV1(
        portfolio_policy_id="portfolio-policy-1",
        policy_timestamp=NOW,
        maximum_concurrent_trades=3,
        maximum_total_deployed_capital=100000.0,
        maximum_total_portfolio_risk_amount=10000.0,
        maximum_daily_loss_amount=5000.0,
        maximum_daily_drawdown_amount=5000.0,
        maximum_instrument_risk_fraction=1.0,
        maximum_direction_risk_fraction=1.0,
        maximum_correlated_index_risk_fraction=1.0,
        maximum_expiry_risk_fraction=1.0,
    )


def test_initial_p8_envelope_round_trips_through_real_repository(tmp_path):
    snapshot = build_initial_paper_portfolio_snapshot(
        portfolio_snapshot_id="snapshot-1",
        portfolio_id="portfolio-1",
        policy=policy(),
        trading_day_id=NOW.date().isoformat(),
        starting_capital=100000.0,
        created_at=NOW,
    )
    envelope = PaperPortfolioPersistenceSnapshotV1(
        portfolio_id="portfolio-1",
        portfolio_snapshot=snapshot,
        admission_idempotency_records={},
        update_idempotency_records={},
        processed_portfolio_event_hashes={},
        processed_p7_transition_hashes={},
        processed_p7_fill_hashes={},
        created_at=NOW,
        updated_at=NOW,
        event_sequence=0,
    )
    service = PaperPortfolioPersistenceService(
        PaperPortfolioRepository(
            tmp_path / "portfolio.json"
        )
    )
    service.save(envelope)
    restored = service.get("portfolio-1")

    assert restored is not None
    assert restored.integrity_hash == envelope.integrity_hash
    assert restored.portfolio_snapshot.available_cash == 100000.0
