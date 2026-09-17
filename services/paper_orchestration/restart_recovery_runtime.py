"""R4.5 restart recovery and duplicate-protection runtime."""

from __future__ import annotations

from dataclasses import dataclass

from services.contracts.paper_portfolio_persistence_snapshot_v1 import (
    PaperPortfolioPersistenceSnapshotV1,
)
from services.contracts.paper_portfolio_policy_v1 import (
    PaperPortfolioPolicyV1,
)
from services.contracts.paper_trade_persistence_snapshot_v1 import (
    PaperTradePersistenceSnapshotV1,
)
from services.paper_portfolio.paper_portfolio_persistence_service import (
    PaperPortfolioPersistenceService,
)
from services.paper_portfolio.paper_portfolio_reconciliation import (
    validate_paper_portfolio_reconciliation,
)
from services.paper_trading.paper_trade_persistence_service import (
    PaperTradePersistenceService,
)
from services.paper_trading.paper_trade_recovery_service import (
    PaperTradeRecoveryService,
)


_ALLOWED_ACTIVE_STATES = frozenset(
    {
        "OPEN",
        "PARTIALLY_EXITED",
    }
)


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{name} must be a nonblank string")
    return value.strip()


@dataclass(frozen=True, slots=True)
class RestartRecoveryResultV1:
    status: str
    portfolio_snapshot: PaperPortfolioPersistenceSnapshotV1
    recovered_trades: tuple[
        PaperTradePersistenceSnapshotV1,
        ...,
    ]
    active_trade_count: int
    terminal_trade_count: int
    duplicate_protection_verified: bool
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False

    def __post_init__(self) -> None:
        if self.status != "RECOVERED":
            raise ValueError(
                "restart recovery status must be RECOVERED"
            )

        if (
            type(self.portfolio_snapshot)
            is not PaperPortfolioPersistenceSnapshotV1
        ):
            raise TypeError(
                "portfolio_snapshot must be exact "
                "PaperPortfolioPersistenceSnapshotV1"
            )

        if type(self.recovered_trades) is not tuple:
            raise TypeError(
                "recovered_trades must be an exact tuple"
            )

        if any(
            type(item) is not PaperTradePersistenceSnapshotV1
            for item in self.recovered_trades
        ):
            raise TypeError(
                "recovered_trades must contain exact "
                "PaperTradePersistenceSnapshotV1 values"
            )

        for name in (
            "active_trade_count",
            "terminal_trade_count",
        ):
            value = getattr(self, name)
            if (
                type(value) is not int
                or isinstance(value, bool)
                or value < 0
            ):
                raise ValueError(
                    f"{name} must be a nonnegative exact int"
                )

        if (
            self.active_trade_count
            + self.terminal_trade_count
            != len(self.recovered_trades)
        ):
            raise ValueError(
                "recovered trade counts are incoherent"
            )

        if type(self.duplicate_protection_verified) is not bool:
            raise TypeError(
                "duplicate_protection_verified must be bool"
            )

        if not self.duplicate_protection_verified:
            raise ValueError(
                "restart recovery requires duplicate protection"
            )

        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
        ):
            raise ValueError("R4.5 must remain PAPER-only")


def _validate_trade_snapshot(
    snapshot: PaperTradePersistenceSnapshotV1,
) -> None:
    if type(snapshot) is not PaperTradePersistenceSnapshotV1:
        raise TypeError(
            "recovered trade must be exact "
            "PaperTradePersistenceSnapshotV1"
        )

    if snapshot.execution_mode != "PAPER":
        raise ValueError("recovered trade must remain PAPER")

    if snapshot.live_execution_eligible is not False:
        raise ValueError(
            "recovered trade cannot be live eligible"
        )

    if snapshot.position is None:
        raise ValueError(
            "recovered persisted trade must contain a position"
        )

    position = snapshot.position
    state = snapshot.lifecycle_state

    if position.lifecycle_state != state.current_state:
        raise ValueError(
            "recovered P7 lifecycle/position mismatch"
        )

    if (
        position.trade_plan_id
        != state.trade_plan_id
        or position.integrated_trade_plan_result_id
        != state.integrated_trade_plan_result_id
    ):
        raise ValueError(
            "recovered P7 trade lineage mismatch"
        )

    if snapshot.event_sequence != state.transition_sequence:
        raise ValueError(
            "recovered P7 transition sequence mismatch"
        )

    if state.is_terminal:
        if state.current_state in _ALLOWED_ACTIVE_STATES:
            raise ValueError(
                "terminal P7 snapshot has active lifecycle state"
            )
    elif state.current_state not in _ALLOWED_ACTIVE_STATES:
        raise ValueError(
            "nonterminal P7 snapshot is not resumable"
        )

    exit_fill_ids = tuple(
        fill.fill_id for fill in position.exit_fills
    )

    if len(exit_fill_ids) != len(set(exit_fill_ids)):
        raise ValueError(
            "duplicate exit fill IDs in recovered trade"
        )

    all_fill_ids = (
        position.entry_fill.fill_id,
        *exit_fill_ids,
    )

    if len(all_fill_ids) != len(set(all_fill_ids)):
        raise ValueError(
            "duplicate entry/exit fill IDs in recovered trade"
        )

    if snapshot.latest_observation is not None:
        observation = snapshot.latest_observation

        if (
            observation.trade_plan_id
            != position.trade_plan_id
            or observation.integrated_trade_plan_result_id
            != position.integrated_trade_plan_result_id
            or observation.selected_option_contract_id
            != position.selected_option_contract_id
            or observation.option_symbol
            != position.option_symbol
        ):
            raise ValueError(
                "recovered observation/position lineage mismatch"
            )

    if snapshot.pnl_evidence is not None:
        evidence = snapshot.pnl_evidence

        if evidence.position_id != position.position_id:
            raise ValueError(
                "recovered P&L evidence position mismatch"
            )

        if (
            evidence.remaining_quantity
            != position.remaining_quantity
        ):
            raise ValueError(
                "recovered P&L evidence quantity mismatch"
            )


def _validate_portfolio_lineage(
    *,
    portfolio_id: str,
    portfolio_policy: PaperPortfolioPolicyV1,
    portfolio_snapshot: PaperPortfolioPersistenceSnapshotV1,
    trades: tuple[
        PaperTradePersistenceSnapshotV1,
        ...,
    ],
) -> None:
    if portfolio_snapshot.portfolio_id != portfolio_id:
        raise ValueError(
            "recovered portfolio identity mismatch"
        )

    if (
        portfolio_snapshot.portfolio_snapshot.portfolio_policy_id
        != portfolio_policy.portfolio_policy_id
    ):
        raise ValueError(
            "recovered portfolio policy mismatch"
        )

    if portfolio_snapshot.execution_mode != "PAPER":
        raise ValueError(
            "recovered portfolio must remain PAPER"
        )

    if portfolio_snapshot.live_execution_eligible is not False:
        raise ValueError(
            "recovered portfolio cannot be live eligible"
        )

    reconciliation_codes = (
        validate_paper_portfolio_reconciliation(
            portfolio_snapshot=(
                portfolio_snapshot.portfolio_snapshot
            ),
            paper_trade_snapshots=trades,
        )
    )

    if reconciliation_codes:
        raise ValueError(
            "restart reconciliation failed: "
            + ",".join(reconciliation_codes)
        )

    positions = {
        snapshot.position.position_id: snapshot.position
        for snapshot in trades
        if snapshot.position is not None
    }

    for reference in (
        portfolio_snapshot.portfolio_snapshot
        .position_references
    ):
        position = positions.get(reference.position_id)

        if position is None:
            raise ValueError(
                "recovered portfolio references unknown position"
            )

        if (
            reference.lifecycle_state
            != position.lifecycle_state
            or reference.remaining_quantity
            != position.remaining_quantity
            or reference.realized_net_pnl
            != position.realized_net_pnl
            or reference.unrealized_pnl
            != position.unrealized_pnl
            or reference.total_pnl
            != position.total_pnl
        ):
            raise ValueError(
                "recovered P7/P8 position projection mismatch"
            )


def _validate_duplicate_protection(
    *,
    portfolio_snapshot: PaperPortfolioPersistenceSnapshotV1,
    trades: tuple[
        PaperTradePersistenceSnapshotV1,
        ...,
    ],
) -> None:
    trade_ids = tuple(
        snapshot.paper_trade_id
        for snapshot in trades
    )
    if len(trade_ids) != len(set(trade_ids)):
        raise ValueError("duplicate recovered paper trade ID")

    adapter_keys = tuple(
        snapshot.adapter_idempotency_key
        for snapshot in trades
    )
    if len(adapter_keys) != len(set(adapter_keys)):
        raise ValueError(
            "duplicate recovered adapter idempotency key"
        )

    position_ids = tuple(
        snapshot.position.position_id
        for snapshot in trades
        if snapshot.position is not None
    )
    if len(position_ids) != len(set(position_ids)):
        raise ValueError("duplicate recovered position ID")

    transition_keys = tuple(
        key
        for key, _ in (
            portfolio_snapshot
            .processed_p7_transition_hashes
        )
    )
    if len(transition_keys) != len(set(transition_keys)):
        raise ValueError(
            "duplicate persisted P7 transition record"
        )

    fill_keys = tuple(
        key
        for key, _ in (
            portfolio_snapshot.processed_p7_fill_hashes
        )
    )
    if len(fill_keys) != len(set(fill_keys)):
        raise ValueError(
            "duplicate persisted P7 fill record"
        )

    event_keys = tuple(
        key
        for key, _ in (
            portfolio_snapshot
            .processed_portfolio_event_hashes
        )
    )
    if len(event_keys) != len(set(event_keys)):
        raise ValueError(
            "duplicate persisted portfolio event record"
        )

    admission_keys = tuple(
        key
        for key, _ in (
            portfolio_snapshot
            .admission_idempotency_records
        )
    )
    if len(admission_keys) != len(set(admission_keys)):
        raise ValueError(
            "duplicate persisted admission idempotency record"
        )

    update_keys = tuple(
        key
        for key, _ in (
            portfolio_snapshot
            .update_idempotency_records
        )
    )
    if len(update_keys) != len(set(update_keys)):
        raise ValueError(
            "duplicate persisted update idempotency record"
        )

    exit_fill_ids: list[str] = []

    for snapshot in trades:
        if snapshot.position is None:
            continue

        exit_fill_ids.extend(
            fill.fill_id
            for fill in snapshot.position.exit_fills
        )

    if len(exit_fill_ids) != len(set(exit_fill_ids)):
        raise ValueError(
            "duplicate recovered exit fill across trades"
        )


def execute_restart_recovery(
    *,
    portfolio_id: str,
    portfolio_policy: PaperPortfolioPolicyV1,
    portfolio_persistence_service: PaperPortfolioPersistenceService,
    trade_persistence_service: PaperTradePersistenceService,
    include_terminal: bool = True,
    broker_order_submission: bool = False,
) -> RestartRecoveryResultV1:
    """Rehydrate and validate exact persisted R4 PAPER state."""

    if type(portfolio_policy) is not PaperPortfolioPolicyV1:
        raise TypeError(
            "portfolio_policy must be exact "
            "PaperPortfolioPolicyV1"
        )

    if (
        type(portfolio_persistence_service)
        is not PaperPortfolioPersistenceService
    ):
        raise TypeError(
            "portfolio_persistence_service must be exact "
            "PaperPortfolioPersistenceService"
        )

    if (
        type(trade_persistence_service)
        is not PaperTradePersistenceService
    ):
        raise TypeError(
            "trade_persistence_service must be exact "
            "PaperTradePersistenceService"
        )

    if type(include_terminal) is not bool:
        raise TypeError("include_terminal must be bool")

    portfolio_id = _text(portfolio_id, "portfolio_id")

    if broker_order_submission is not False:
        raise ValueError(
            "order submission must remain disabled"
        )

    portfolio_snapshot = (
        portfolio_persistence_service.get(portfolio_id)
    )

    if portfolio_snapshot is None:
        raise ValueError(
            "persisted portfolio not found during restart"
        )

    recovery_service = PaperTradeRecoveryService(
        trade_persistence_service
    )

    all_trades = recovery_service.recover(
        include_terminal=True
    )

    if not all_trades:
        raise ValueError(
            "no persisted paper trades found during restart"
        )

    for snapshot in all_trades:
        _validate_trade_snapshot(snapshot)

    _validate_portfolio_lineage(
        portfolio_id=portfolio_id,
        portfolio_policy=portfolio_policy,
        portfolio_snapshot=portfolio_snapshot,
        trades=all_trades,
    )

    _validate_duplicate_protection(
        portfolio_snapshot=portfolio_snapshot,
        trades=all_trades,
    )

    active_trades = tuple(
        snapshot
        for snapshot in all_trades
        if not snapshot.lifecycle_state.is_terminal
    )

    terminal_trades = tuple(
        snapshot
        for snapshot in all_trades
        if snapshot.lifecycle_state.is_terminal
    )

    for snapshot in active_trades:
        if (
            snapshot.lifecycle_state.current_state
            not in _ALLOWED_ACTIVE_STATES
        ):
            raise ValueError(
                "restart recovered unsupported active state"
            )

    recovered = (
        all_trades
        if include_terminal
        else active_trades
    )

    return RestartRecoveryResultV1(
        status="RECOVERED",
        portfolio_snapshot=portfolio_snapshot,
        recovered_trades=recovered,
        active_trade_count=len(active_trades),
        terminal_trade_count=(
            len(terminal_trades)
            if include_terminal
            else 0
        ),
        duplicate_protection_verified=True,
    )