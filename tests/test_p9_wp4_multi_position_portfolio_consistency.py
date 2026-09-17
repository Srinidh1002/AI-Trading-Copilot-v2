from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from services.paper_portfolio.paper_portfolio_persistence_service import (
    PaperPortfolioPersistenceService,
)
from services.paper_portfolio.paper_portfolio_recovery_service import (
    PaperPortfolioRecoveryService,
)
from services.paper_trading.paper_trade_persistence_service import (
    PaperTradePersistenceService,
)
from services.paper_trading.paper_trade_recovery_service import (
    PaperTradeRecoveryService,
)
from services.contracts.paper_portfolio_persistence_snapshot_v1 import (
    PaperPortfolioPersistenceSnapshotV1,
)

NOW = datetime(2026, 1, 8, 9, 30, tzinfo=timezone.utc)


def trade_snapshot(
    *,
    trade_id: str,
    idempotency_key: str,
    position_id: str | None,
    terminal: bool = False,
):
    return SimpleNamespace(
        paper_trade_id=trade_id,
        adapter_idempotency_key=idempotency_key,
        position=(
            None
            if position_id is None
            else SimpleNamespace(position_id=position_id)
        ),
        lifecycle_state=SimpleNamespace(
            is_terminal=terminal,
        ),
    )


def portfolio_snapshot(
    *,
    portfolio_id: str,
) -> PaperPortfolioPersistenceSnapshotV1:
    value = object.__new__(
        PaperPortfolioPersistenceSnapshotV1
    )
    object.__setattr__(
        value,
        "portfolio_id",
        portfolio_id,
    )
    return value


def trade_recovery_service():
    persistence = object.__new__(
        PaperTradePersistenceService
    )
    return PaperTradeRecoveryService(persistence)


def portfolio_recovery_service():
    persistence = object.__new__(
        PaperPortfolioPersistenceService
    )
    return PaperPortfolioRecoveryService(persistence)


def test_trade_recovery_accepts_distinct_active_positions():
    service = trade_recovery_service()
    snapshots = (
        trade_snapshot(
            trade_id="trade-1",
            idempotency_key="entry-key-1",
            position_id="position-1",
        ),
        trade_snapshot(
            trade_id="trade-2",
            idempotency_key="entry-key-2",
            position_id="position-2",
        ),
    )

    with patch.object(
        service.persistence_service,
        "list_all",
        return_value=snapshots,
    ):
        recovered = service.recover_active()

    assert recovered == snapshots


def test_trade_recovery_rejects_duplicate_position_identity():
    service = trade_recovery_service()
    snapshots = (
        trade_snapshot(
            trade_id="trade-1",
            idempotency_key="entry-key-1",
            position_id="position-1",
        ),
        trade_snapshot(
            trade_id="trade-2",
            idempotency_key="entry-key-2",
            position_id="position-1",
        ),
    )

    with (
        patch.object(
            service.persistence_service,
            "list_all",
            return_value=snapshots,
        ),
        pytest.raises(
            ValueError,
            match="duplicate position",
        ),
    ):
        service.recover()


def test_trade_recovery_rejects_duplicate_durable_idempotency_key():
    service = trade_recovery_service()
    snapshots = (
        trade_snapshot(
            trade_id="trade-1",
            idempotency_key="entry-key-1",
            position_id="position-1",
        ),
        trade_snapshot(
            trade_id="trade-2",
            idempotency_key="entry-key-1",
            position_id="position-2",
        ),
    )

    with (
        patch.object(
            service.persistence_service,
            "list_all",
            return_value=snapshots,
        ),
        pytest.raises(
            ValueError,
            match="duplicate idempotency key",
        ),
    ):
        service.recover()


def test_active_recovery_excludes_terminal_positions():
    service = trade_recovery_service()
    active = trade_snapshot(
        trade_id="trade-1",
        idempotency_key="entry-key-1",
        position_id="position-1",
    )
    terminal = trade_snapshot(
        trade_id="trade-2",
        idempotency_key="entry-key-2",
        position_id="position-2",
        terminal=True,
    )

    with patch.object(
        service.persistence_service,
        "list_all",
        return_value=(active, terminal),
    ):
        recovered = service.recover_active()

    assert recovered == (active,)


def test_portfolio_recovery_rejects_duplicate_portfolio_identity():
    service = portfolio_recovery_service()
    snapshots = (
        portfolio_snapshot(portfolio_id="portfolio-1"),
        portfolio_snapshot(portfolio_id="portfolio-1"),
    )

    with (
        patch.object(
            service.persistence_service,
            "list_all",
            return_value=snapshots,
        ),
        pytest.raises(
            ValueError,
            match="duplicate portfolio",
        ),
    ):
        service.recover_all(NOW)


def test_portfolio_recovery_preserves_distinct_portfolio_identities():
    service = portfolio_recovery_service()
    snapshots = (
        portfolio_snapshot(portfolio_id="portfolio-1"),
        portfolio_snapshot(portfolio_id="portfolio-2"),
    )

    with patch.object(
        service.persistence_service,
        "list_all",
        return_value=snapshots,
    ):
        recovered = service.recover_all(NOW)

    assert tuple(
        item.portfolio_id
        for item in recovered
    ) == (
        "portfolio-1",
        "portfolio-2",
    )
    assert all(
        item.status == "RECOVERED"
        for item in recovered
    )
    assert all(
        item.execution_mode == "PAPER"
        for item in recovered
    )
    assert all(
        item.live_execution_eligible is False
        for item in recovered
    )
