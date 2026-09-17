from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from services.contracts.paper_portfolio_persistence_snapshot_v1 import (
    PaperPortfolioPersistenceSnapshotV1,
)
from services.contracts.paper_trade_persistence_snapshot_v1 import (
    PaperTradePersistenceSnapshotV1,
)
from services.paper_portfolio.paper_portfolio_recovery_service import (
    PaperPortfolioRecoveryService,
)
from services.paper_trading.paper_trade_recovery_service import (
    PaperTradeRecoveryService,
)


class Clock(Protocol):
    def __call__(self) -> datetime: ...


def _aware(
    value: object,
    name: str,
) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")

    return value


def _text_tuple(
    values: object,
) -> tuple[str, ...]:
    if values is None:
        return ()

    return tuple(
        dict.fromkeys(
            str(value).strip()
            for value in values
            if str(value).strip()
        )
    )


@dataclass(frozen=True, slots=True)
class CertifiedStartupRecoveryResultV1:
    success: bool
    recovered_at: datetime
    portfolio_id: str
    recovered_trade_count: int
    active_trade_count: int
    pending_trade_count: int
    terminal_trade_count: int
    recovered_portfolio_count: int
    reconciliation_codes: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False
    schema_version: str = "certified_startup_recovery_result.v1"

    def __post_init__(self) -> None:
        if type(self.success) is not bool:
            raise TypeError("success must be a bool")

        object.__setattr__(
            self,
            "recovered_at",
            _aware(
                self.recovered_at,
                "recovered_at",
            ),
        )

        if type(self.portfolio_id) is not str or not self.portfolio_id.strip():
            raise ValueError(
                "portfolio_id must be a non-empty string"
            )

        object.__setattr__(
            self,
            "portfolio_id",
            self.portfolio_id.strip(),
        )

        for name in (
            "recovered_trade_count",
            "active_trade_count",
            "pending_trade_count",
            "terminal_trade_count",
            "recovered_portfolio_count",
        ):
            value = getattr(self, name)

            if type(value) is not int or isinstance(value, bool):
                raise TypeError(f"{name} must be an exact int")

            if value < 0:
                raise ValueError(f"{name} must be nonnegative")

        codes = _text_tuple(
            self.reconciliation_codes
        )
        blockers = _text_tuple(self.blockers)
        warnings = _text_tuple(self.warnings)

        object.__setattr__(
            self,
            "reconciliation_codes",
            codes,
        )
        object.__setattr__(
            self,
            "blockers",
            blockers,
        )
        object.__setattr__(
            self,
            "warnings",
            warnings,
        )

        if self.success and blockers:
            raise ValueError(
                "successful recovery cannot contain blockers"
            )

        if not self.success and not blockers:
            raise ValueError(
                "failed recovery requires blockers"
            )

        if self.execution_mode != "PAPER":
            raise ValueError("execution_mode must be PAPER")

        if self.live_execution_eligible:
            raise ValueError(
                "live execution must remain disabled"
            )

        if self.broker_order_submission:
            raise ValueError(
                "broker order submission must remain disabled"
            )

        if (
            self.schema_version
            != "certified_startup_recovery_result.v1"
        ):
            raise ValueError("unsupported schema_version")


class CertifiedStartupRecovery:
    """Read-only startup recovery and exact P7/P8 reconciliation."""

    def __init__(
        self,
        *,
        portfolio_id: str,
        trade_recovery_service: PaperTradeRecoveryService,
        portfolio_recovery_service: PaperPortfolioRecoveryService,
        clock: Clock,
    ) -> None:
        if type(portfolio_id) is not str or not portfolio_id.strip():
            raise ValueError(
                "portfolio_id must be a non-empty string"
            )

        if type(trade_recovery_service) is not PaperTradeRecoveryService:
            raise TypeError("trade_recovery_service")

        if (
            type(portfolio_recovery_service)
            is not PaperPortfolioRecoveryService
        ):
            raise TypeError("portfolio_recovery_service")

        if not callable(clock):
            raise TypeError("clock")

        self.portfolio_id = portfolio_id.strip()
        self.trade_recovery_service = (
            trade_recovery_service
        )
        self.portfolio_recovery_service = (
            portfolio_recovery_service
        )
        self.clock = clock

    @staticmethod
    def _validate_trades(
        snapshots: object,
    ) -> tuple[PaperTradePersistenceSnapshotV1, ...]:
        if type(snapshots) is not tuple:
            raise TypeError(
                "trade recovery must return an exact tuple"
            )

        seen_trade_ids: set[str] = set()
        seen_keys: set[str] = set()
        seen_positions: set[str] = set()

        ordered = sorted(
            snapshots,
            key=lambda item: (
                item.created_at,
                item.paper_trade_id,
            ),
        )

        for snapshot in ordered:
            if type(snapshot) is not PaperTradePersistenceSnapshotV1:
                raise TypeError(
                    "trade recovery must return exact "
                    "PaperTradePersistenceSnapshotV1 values"
                )

            if snapshot.paper_trade_id in seen_trade_ids:
                raise ValueError("duplicate paper_trade_id")

            if snapshot.adapter_idempotency_key in seen_keys:
                raise ValueError(
                    "duplicate adapter idempotency key"
                )

            seen_trade_ids.add(snapshot.paper_trade_id)
            seen_keys.add(
                snapshot.adapter_idempotency_key
            )

            if snapshot.position is not None:
                position_id = snapshot.position.position_id

                if position_id in seen_positions:
                    raise ValueError("duplicate position_id")

                seen_positions.add(position_id)

        return tuple(ordered)

    @staticmethod
    def _validate_portfolios(
        recovery_results: object,
        portfolio_id: str,
    ) -> PaperPortfolioPersistenceSnapshotV1 | None:
        if type(recovery_results) is not tuple:
            raise TypeError(
                "portfolio recovery must return an exact tuple"
            )

        recovered: list[
            PaperPortfolioPersistenceSnapshotV1
        ] = []

        seen_ids: set[str] = set()

        for result in recovery_results:
            status = str(
                getattr(result, "status", "")
            ).strip().upper()

            if status != "RECOVERED":
                raise ValueError(
                    "portfolio recovery did not return RECOVERED"
                )

            snapshot = getattr(
                result,
                "persistence_snapshot",
                None,
            )

            if (
                type(snapshot)
                is not PaperPortfolioPersistenceSnapshotV1
            ):
                raise TypeError(
                    "portfolio recovery result must contain exact "
                    "PaperPortfolioPersistenceSnapshotV1"
                )

            if snapshot.portfolio_id in seen_ids:
                raise ValueError("duplicate portfolio_id")

            seen_ids.add(snapshot.portfolio_id)
            recovered.append(snapshot)

        matching = tuple(
            item
            for item in recovered
            if item.portfolio_id == portfolio_id
        )

        foreign = tuple(
            item
            for item in recovered
            if item.portfolio_id != portfolio_id
        )

        if foreign:
            raise ValueError(
                "unexpected persisted portfolio identity"
            )

        if len(matching) > 1:
            raise ValueError(
                "configured portfolio recovered more than once"
            )

        return matching[0] if matching else None

    @staticmethod
    def _reconcile_position(
        *,
        trade_snapshot: PaperTradePersistenceSnapshotV1,
        reference: object,
    ) -> tuple[str, ...]:
        position = trade_snapshot.position
        assert position is not None

        codes: list[str] = []

        expected = {
            "position_id": position.position_id,
            "trade_plan_id": position.trade_plan_id,
            "integrated_trade_plan_result_id": (
                position.integrated_trade_plan_result_id
            ),
            "selected_option_contract_id": (
                position.selected_option_contract_id
            ),
            "underlying_symbol": position.underlying_symbol,
            "option_symbol": position.option_symbol,
            "lifecycle_state": position.lifecycle_state,
            "remaining_lot_count": (
                position.remaining_lot_count
            ),
            "remaining_quantity": position.remaining_quantity,
        }

        for name, expected_value in expected.items():
            if getattr(reference, name, None) != expected_value:
                codes.append(
                    f"P7_P8_{name.upper()}_MISMATCH"
                )

        if (
            getattr(reference, "transition_sequence", None)
            != trade_snapshot.lifecycle_state.transition_sequence
        ):
            codes.append(
                "P7_P8_TRANSITION_SEQUENCE_MISMATCH"
            )

        if (
            getattr(reference, "realized_net_pnl", None)
            != position.realized_net_pnl
        ):
            codes.append(
                "P7_P8_REALIZED_PNL_MISMATCH"
            )

        if (
            getattr(reference, "unrealized_pnl", None)
            != position.unrealized_pnl
        ):
            codes.append(
                "P7_P8_UNREALIZED_PNL_MISMATCH"
            )

        if (
            getattr(reference, "total_pnl", None)
            != position.total_pnl
        ):
            codes.append(
                "P7_P8_TOTAL_PNL_MISMATCH"
            )

        expected_exit_ids = tuple(
            fill.fill_id
            for fill in position.exit_fills
        )

        if (
            tuple(
                getattr(
                    reference,
                    "exit_fill_ids",
                    (),
                )
            )
            != expected_exit_ids
        ):
            codes.append(
                "P7_P8_EXIT_FILL_IDS_MISMATCH"
            )

        return tuple(codes)

    def __call__(
        self,
    ) -> CertifiedStartupRecoveryResultV1:
        recovered_at = _aware(
            self.clock(),
            "clock result",
        )

        try:
            trades = self._validate_trades(
                self.trade_recovery_service.recover(
                    include_terminal=True
                )
            )

            portfolio = self._validate_portfolios(
                self.portfolio_recovery_service.recover_all(
                    recovered_at
                ),
                self.portfolio_id,
            )

            active_trades = tuple(
                item
                for item in trades
                if (
                    item.position is not None
                    and not item.lifecycle_state.is_terminal
                )
            )

            pending_trades = tuple(
                item
                for item in trades
                if (
                    item.position is None
                    and not item.lifecycle_state.is_terminal
                )
            )

            terminal_trades = tuple(
                item
                for item in trades
                if item.lifecycle_state.is_terminal
            )

            if not trades and portfolio is None:
                return CertifiedStartupRecoveryResultV1(
                    success=True,
                    recovered_at=recovered_at,
                    portfolio_id=self.portfolio_id,
                    recovered_trade_count=0,
                    active_trade_count=0,
                    pending_trade_count=0,
                    terminal_trade_count=0,
                    recovered_portfolio_count=0,
                    reconciliation_codes=(
                        "EMPTY_REPOSITORIES",
                    ),
                )

            if trades and portfolio is None:
                return CertifiedStartupRecoveryResultV1(
                    success=False,
                    recovered_at=recovered_at,
                    portfolio_id=self.portfolio_id,
                    recovered_trade_count=len(trades),
                    active_trade_count=len(active_trades),
                    pending_trade_count=len(pending_trades),
                    terminal_trade_count=len(
                        terminal_trades
                    ),
                    recovered_portfolio_count=0,
                    reconciliation_codes=(
                        "P8_PORTFOLIO_MISSING",
                    ),
                    blockers=(
                        "P8_PORTFOLIO_MISSING",
                    ),
                )

            assert portfolio is not None

            portfolio_snapshot = (
                portfolio.portfolio_snapshot
            )

            references = tuple(
                portfolio_snapshot.position_references
            )
            reservations = tuple(
                portfolio_snapshot.reservations
            )

            reference_by_position = {
                item.position_id: item
                for item in references
            }

            pending_reservation_by_plan = {
                item.trade_plan_id: item
                for item in reservations
                if item.reservation_status == "PENDING_HOLD"
            }

            codes: list[str] = []
            matched_positions: set[str] = set()
            matched_pending_plans: set[str] = set()

            for trade in trades:
                position = trade.position

                if position is not None:
                    reference = reference_by_position.get(
                        position.position_id
                    )

                    if reference is None:
                        codes.append(
                            "P7_POSITION_MISSING_FROM_P8"
                        )
                        continue

                    matched_positions.add(
                        position.position_id
                    )

                    codes.extend(
                        self._reconcile_position(
                            trade_snapshot=trade,
                            reference=reference,
                        )
                    )

                    continue

                if trade.lifecycle_state.is_terminal:
                    continue

                plan_id = (
                    trade.lifecycle_state.trade_plan_id
                )

                reservation = (
                    pending_reservation_by_plan.get(
                        plan_id
                    )
                )

                if reservation is None:
                    codes.append(
                        "P7_PENDING_TRADE_MISSING_FROM_P8"
                    )
                    continue

                matched_pending_plans.add(plan_id)

                if (
                    reservation.integrated_trade_plan_result_id
                    != trade.lifecycle_state.integrated_trade_plan_result_id
                ):
                    codes.append(
                        "P7_P8_PENDING_PLAN_RESULT_MISMATCH"
                    )

            unmatched_references = (
                set(reference_by_position)
                - matched_positions
            )

            if unmatched_references:
                codes.append(
                    "P8_POSITION_MISSING_FROM_P7"
                )

            unmatched_pending = (
                set(pending_reservation_by_plan)
                - matched_pending_plans
            )

            if unmatched_pending:
                codes.append(
                    "P8_PENDING_RESERVATION_MISSING_FROM_P7"
                )

            unique_codes = tuple(
                dict.fromkeys(codes)
            )

            if unique_codes:
                return CertifiedStartupRecoveryResultV1(
                    success=False,
                    recovered_at=recovered_at,
                    portfolio_id=self.portfolio_id,
                    recovered_trade_count=len(trades),
                    active_trade_count=len(active_trades),
                    pending_trade_count=len(pending_trades),
                    terminal_trade_count=len(
                        terminal_trades
                    ),
                    recovered_portfolio_count=1,
                    reconciliation_codes=unique_codes,
                    blockers=unique_codes,
                )

            return CertifiedStartupRecoveryResultV1(
                success=True,
                recovered_at=recovered_at,
                portfolio_id=self.portfolio_id,
                recovered_trade_count=len(trades),
                active_trade_count=len(active_trades),
                pending_trade_count=len(pending_trades),
                terminal_trade_count=len(
                    terminal_trades
                ),
                recovered_portfolio_count=1,
                reconciliation_codes=(
                    "P7_P8_RECONCILED",
                ),
            )

        except Exception as exc:
            code = (
                "STARTUP_RECOVERY_"
                f"{type(exc).__name__.upper()}"
            )

            return CertifiedStartupRecoveryResultV1(
                success=False,
                recovered_at=recovered_at,
                portfolio_id=self.portfolio_id,
                recovered_trade_count=0,
                active_trade_count=0,
                pending_trade_count=0,
                terminal_trade_count=0,
                recovered_portfolio_count=0,
                reconciliation_codes=(code,),
                blockers=(code,),
                warnings=(
                    str(exc) or type(exc).__name__,
                ),
            )