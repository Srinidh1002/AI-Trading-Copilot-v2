from __future__ import annotations

from datetime import datetime, timezone

from services.contracts.paper_portfolio_persistence_snapshot_v1 import (
    PaperPortfolioPersistenceSnapshotV1,
)
from services.contracts.paper_trade_persistence_snapshot_v1 import (
    PaperTradePersistenceSnapshotV1,
)
from services.paper_orchestration.certified_startup_recovery import (
    CertifiedStartupRecovery,
    CertifiedStartupRecoveryResultV1,
)
from services.paper_portfolio.paper_portfolio_recovery_service import (
    PaperPortfolioRecoveryService,
)
from services.paper_trading.paper_trade_recovery_service import (
    PaperTradeRecoveryService,
)


NOW = datetime(
    2026,
    8,
    5,
    9,
    30,
    tzinfo=timezone.utc,
)


def exact(contract, **fields):
    value = object.__new__(contract)

    for name, item in fields.items():
        object.__setattr__(
            value,
            name,
            item,
        )

    return value


def trade(
    trade_id,
    position_id,
    *,
    lifecycle_state="OPEN",
    terminal=False,
    with_position=True,
):
    state = type(
        "LifecycleState",
        (),
        {
            "is_terminal": terminal,
            "trade_plan_id": f"plan-{trade_id}",
            "integrated_trade_plan_result_id": (
                f"result-{trade_id}"
            ),
            "transition_sequence": 1,
        },
    )()

    position = None

    if with_position:
        position = type(
            "Position",
            (),
            {
                "position_id": position_id,
                "trade_plan_id": f"plan-{trade_id}",
                "integrated_trade_plan_result_id": (
                    f"result-{trade_id}"
                ),
                "selected_option_contract_id": (
                    f"contract-{trade_id}"
                ),
                "underlying_symbol": "NIFTY",
                "option_symbol": f"NIFTY-{trade_id}-CE",
                "lifecycle_state": lifecycle_state,
                "remaining_lot_count": 1,
                "remaining_quantity": 50,
                "realized_net_pnl": 0.0,
                "unrealized_pnl": 25.0,
                "total_pnl": 25.0,
                "exit_fills": (),
            },
        )()

    return exact(
        PaperTradePersistenceSnapshotV1,
        paper_trade_id=trade_id,
        adapter_idempotency_key=(
            f"adapter-{trade_id}"
        ),
        lifecycle_state=state,
        position=position,
        created_at=NOW,
    )


def position_reference(trade_value):
    position = trade_value.position
    assert position is not None

    return type(
        "PositionReference",
        (),
        {
            "position_id": position.position_id,
            "trade_plan_id": position.trade_plan_id,
            "integrated_trade_plan_result_id": (
                position.integrated_trade_plan_result_id
            ),
            "selected_option_contract_id": (
                position.selected_option_contract_id
            ),
            "underlying_symbol": (
                position.underlying_symbol
            ),
            "option_symbol": position.option_symbol,
            "lifecycle_state": (
                position.lifecycle_state
            ),
            "transition_sequence": 1,
            "remaining_lot_count": 1,
            "remaining_quantity": 50,
            "realized_net_pnl": 0.0,
            "unrealized_pnl": 25.0,
            "total_pnl": 25.0,
            "exit_fill_ids": (),
        },
    )()


def portfolio(
    *,
    references=(),
    reservations=(),
):
    snapshot = type(
        "PortfolioSnapshot",
        (),
        {
            "position_references": tuple(references),
            "reservations": tuple(reservations),
        },
    )()

    return exact(
        PaperPortfolioPersistenceSnapshotV1,
        portfolio_id="certified-paper-portfolio",
        portfolio_snapshot=snapshot,
    )


def recovery_result(portfolio_value):
    return type(
        "RecoveryResult",
        (),
        {
            "status": "RECOVERED",
            "persistence_snapshot": portfolio_value,
        },
    )()


def operation(
    *,
    trades=(),
    portfolios=(),
    trade_error=None,
    portfolio_error=None,
):
    trade_service = object.__new__(
        PaperTradeRecoveryService
    )

    portfolio_service = object.__new__(
        PaperPortfolioRecoveryService
    )

    def recover(*, include_terminal=True):
        if trade_error is not None:
            raise trade_error
        return tuple(trades)

    def recover_all(recovered_at):
        if portfolio_error is not None:
            raise portfolio_error
        return tuple(
            recovery_result(value)
            for value in portfolios
        )

    trade_service.recover = recover
    portfolio_service.recover_all = recover_all

    return CertifiedStartupRecovery(
        portfolio_id="certified-paper-portfolio",
        trade_recovery_service=trade_service,
        portfolio_recovery_service=portfolio_service,
        clock=lambda: NOW,
    )


def test_empty_repositories_succeed():
    result = operation()()

    assert type(result) is CertifiedStartupRecoveryResultV1
    assert result.success is True
    assert result.recovered_trade_count == 0
    assert result.recovered_portfolio_count == 0
    assert result.reconciliation_codes == (
        "EMPTY_REPOSITORIES",
    )
    assert result.execution_mode == "PAPER"
    assert result.live_execution_eligible is False
    assert result.broker_order_submission is False


def test_open_trade_and_portfolio_reconcile():
    active = trade(
        "trade-a",
        "position-a",
    )

    result = operation(
        trades=(active,),
        portfolios=(
            portfolio(
                references=(
                    position_reference(active),
                ),
            ),
        ),
    )()

    assert result.success is True
    assert result.recovered_trade_count == 1
    assert result.active_trade_count == 1
    assert result.pending_trade_count == 0
    assert result.recovered_portfolio_count == 1
    assert result.reconciliation_codes == (
        "P7_P8_RECONCILED",
    )


def test_partially_exited_trade_reconciles():
    active = trade(
        "trade-a",
        "position-a",
        lifecycle_state="PARTIALLY_EXITED",
    )

    result = operation(
        trades=(active,),
        portfolios=(
            portfolio(
                references=(
                    position_reference(active),
                ),
            ),
        ),
    )()

    assert result.success is True
    assert result.active_trade_count == 1


def test_pending_trade_reconciles_with_pending_reservation():
    pending = trade(
        "trade-pending",
        "unused",
        lifecycle_state="WAITING_FOR_ENTRY",
        with_position=False,
    )

    reservation = type(
        "Reservation",
        (),
        {
            "trade_plan_id": "plan-trade-pending",
            "integrated_trade_plan_result_id": (
                "result-trade-pending"
            ),
            "reservation_status": "PENDING_HOLD",
        },
    )()

    result = operation(
        trades=(pending,),
        portfolios=(
            portfolio(
                reservations=(reservation,),
            ),
        ),
    )()

    assert result.success is True
    assert result.pending_trade_count == 1


def test_existing_trade_without_portfolio_fails_closed():
    active = trade(
        "trade-a",
        "position-a",
    )

    result = operation(
        trades=(active,),
    )()

    assert result.success is False
    assert result.blockers == (
        "P8_PORTFOLIO_MISSING",
    )


def test_p7_position_missing_from_p8_fails_closed():
    active = trade(
        "trade-a",
        "position-a",
    )

    result = operation(
        trades=(active,),
        portfolios=(portfolio(),),
    )()

    assert result.success is False
    assert "P7_POSITION_MISSING_FROM_P8" in (
        result.blockers
    )


def test_p8_position_missing_from_p7_fails_closed():
    active = trade(
        "trade-a",
        "position-a",
    )

    result = operation(
        trades=(),
        portfolios=(
            portfolio(
                references=(
                    position_reference(active),
                ),
            ),
        ),
    )()

    assert result.success is False
    assert "P8_POSITION_MISSING_FROM_P7" in (
        result.blockers
    )


def test_reconciliation_drift_fails_closed():
    active = trade(
        "trade-a",
        "position-a",
    )

    reference = position_reference(active)
    reference.remaining_quantity = 25

    result = operation(
        trades=(active,),
        portfolios=(
            portfolio(
                references=(reference,),
            ),
        ),
    )()

    assert result.success is False
    assert (
        "P7_P8_REMAINING_QUANTITY_MISMATCH"
        in result.blockers
    )


def test_corrupt_trade_recovery_fails_closed():
    result = operation(
        trade_error=ValueError(
            "corrupt P7 persistence"
        ),
    )()

    assert result.success is False
    assert result.blockers == (
        "STARTUP_RECOVERY_VALUEERROR",
    )


def test_corrupt_portfolio_recovery_fails_closed():
    result = operation(
        portfolio_error=ValueError(
            "corrupt P8 persistence"
        ),
    )()

    assert result.success is False
    assert result.blockers == (
        "STARTUP_RECOVERY_VALUEERROR",
    )


def test_duplicate_trade_identity_fails_closed():
    first = trade(
        "trade-a",
        "position-a",
    )
    second = trade(
        "trade-a",
        "position-b",
    )

    result = operation(
        trades=(first, second),
    )()

    assert result.success is False
    assert result.blockers == (
        "STARTUP_RECOVERY_VALUEERROR",
    )