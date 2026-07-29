from __future__ import annotations

from datetime import datetime, timezone

from services.contracts.paper_portfolio_persistence_snapshot_v1 import (
    PaperPortfolioPersistenceSnapshotV1,
)
from services.contracts.paper_portfolio_policy_v1 import PaperPortfolioPolicyV1
from services.paper_portfolio import aggregate_paper_portfolio
from services.paper_portfolio.paper_portfolio_persistence_service import (
    PaperPortfolioPersistenceService,
)
from services.paper_portfolio.paper_portfolio_recovery_service import (
    PaperPortfolioRecoveryService,
)
from services.paper_portfolio_repository import PaperPortfolioRepository


NOW = datetime(2026, 7, 30, 1, 0, tzinfo=timezone.utc)


def make_policy():
    return PaperPortfolioPolicyV1(
        portfolio_policy_id="policy-1",
        policy_timestamp=NOW,
        maximum_concurrent_trades=3,
        maximum_total_deployed_capital=100_000.0,
        maximum_total_portfolio_risk_amount=10_000.0,
        maximum_daily_loss_amount=2_000.0,
        maximum_daily_drawdown_amount=3_000.0,
        maximum_instrument_risk_fraction=0.75,
        maximum_direction_risk_fraction=0.75,
        maximum_correlated_index_risk_fraction=0.60,
        maximum_expiry_risk_fraction=0.60,
        minimum_available_cash_reserve=10_000.0,
    )


def make_persistence_snapshot():
    portfolio_snapshot = aggregate_paper_portfolio(
        portfolio_snapshot_id="snapshot-1",
        portfolio_id="portfolio-1",
        policy=make_policy(),
        trading_day_id="2026-07-30",
        starting_capital=100_000.0,
        reservations=(),
        position_references=(),
        event_sequence=0,
        created_at=NOW,
        updated_at=NOW,
    )
    return PaperPortfolioPersistenceSnapshotV1(
        portfolio_id="portfolio-1",
        portfolio_snapshot=portfolio_snapshot,
        admission_idempotency_records={},
        update_idempotency_records={},
        processed_portfolio_event_hashes={},
        processed_p7_transition_hashes={},
        processed_p7_fill_hashes={},
        created_at=NOW,
        updated_at=NOW,
        event_sequence=0,
    )


def test_repository_round_trip(tmp_path):
    repository = PaperPortfolioRepository(tmp_path / "portfolio.json")
    service = PaperPortfolioPersistenceService(repository)
    original = make_persistence_snapshot()
    service.save(original)
    recovered = service.get("portfolio-1")
    assert recovered is not None
    assert recovered.to_json() == original.to_json()
    assert recovered.integrity_hash == original.integrity_hash


def test_recovery_service_recovers_valid_snapshot(tmp_path):
    repository = PaperPortfolioRepository(tmp_path / "portfolio.json")
    service = PaperPortfolioPersistenceService(repository)
    service.save(make_persistence_snapshot())
    result = PaperPortfolioRecoveryService(service).recover("portfolio-1", NOW)
    assert result.status == "RECOVERED"
    assert result.persistence_snapshot is not None


def test_recovery_service_blocks_missing_snapshot(tmp_path):
    service = PaperPortfolioPersistenceService(
        PaperPortfolioRepository(tmp_path / "portfolio.json")
    )
    result = PaperPortfolioRecoveryService(service).recover("missing", NOW)
    assert result.status == "BLOCKED"
    assert result.blockers == ("PORTFOLIO_NOT_FOUND",)
