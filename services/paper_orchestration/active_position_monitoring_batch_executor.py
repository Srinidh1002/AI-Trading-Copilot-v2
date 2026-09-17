from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from services.contracts.paper_orchestration_cycle_input_v1 import (
    PaperOrchestrationCycleInputV1,
)
from services.contracts.paper_orchestration_cycle_result_v1 import (
    PaperOrchestrationCycleResultV1,
)
from services.contracts.paper_orchestration_stage_result_v1 import (
    PaperOrchestrationStageResultV1,
)
from services.contracts.paper_portfolio_policy_v1 import (
    PaperPortfolioPolicyV1,
)
from services.paper_orchestration.certified_live_option_quote_reader import (
    CertifiedLiveOptionQuoteReader,
)
from services.paper_orchestration.certified_position_evaluation_input_factory import (
    CertifiedPositionEvaluationInputFactory,
)
from services.paper_orchestration.existing_position_monitoring_executor import (
    ExistingPositionMonitoringExecutor,
    ExistingPositionMonitoringInputV1,
    ExistingPositionMonitoringResultV1,
)
from services.paper_trading.paper_trade_recovery_service import (
    PaperTradeRecoveryService,
)


class Clock(Protocol):
    def __call__(self) -> datetime: ...


PortfolioPolicyProvider = Callable[
    [PaperOrchestrationCycleInputV1],
    PaperPortfolioPolicyV1,
]


def _aware(
    value: object,
    name: str,
) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")

    return value


def _identity(
    namespace: str,
    *parts: object,
) -> str:
    payload = "|".join(
        (
            namespace,
            *(str(part).strip() for part in parts),
        )
    )

    digest = hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()[:24]

    return f"{namespace}-{digest}"


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


class ActivePositionMonitoringBatchExecutor:
    """Monitor every active persisted P7 position in one certified cycle."""

    def __init__(
        self,
        *,
        portfolio_id: str,
        trade_recovery_service: PaperTradeRecoveryService,
        quote_reader: CertifiedLiveOptionQuoteReader,
        evaluation_input_factory: CertifiedPositionEvaluationInputFactory,
        monitoring_executor: ExistingPositionMonitoringExecutor,
        portfolio_policy_provider: PortfolioPolicyProvider,
        clock: Clock,
    ) -> None:
        if type(portfolio_id) is not str or not portfolio_id.strip():
            raise ValueError(
                "portfolio_id must be a non-empty string"
            )

        if type(trade_recovery_service) is not PaperTradeRecoveryService:
            raise TypeError("trade_recovery_service")

        if type(quote_reader) is not CertifiedLiveOptionQuoteReader:
            raise TypeError("quote_reader")

        if (
            type(evaluation_input_factory)
            is not CertifiedPositionEvaluationInputFactory
        ):
            raise TypeError("evaluation_input_factory")

        if type(monitoring_executor) is not ExistingPositionMonitoringExecutor:
            raise TypeError("monitoring_executor")

        if not callable(portfolio_policy_provider):
            raise TypeError("portfolio_policy_provider")

        if not callable(clock):
            raise TypeError("clock")

        self.portfolio_id = portfolio_id.strip()
        self.trade_recovery_service = trade_recovery_service
        self.quote_reader = quote_reader
        self.evaluation_input_factory = (
            evaluation_input_factory
        )
        self.monitoring_executor = monitoring_executor
        self.portfolio_policy_provider = (
            portfolio_policy_provider
        )
        self.clock = clock

    @staticmethod
    def _validate_active_snapshots(
        snapshots: object,
    ) -> tuple:
        if type(snapshots) is not tuple:
            raise TypeError(
                "recover_active() must return an exact tuple"
            )

        seen_trade_ids: set[str] = set()
        seen_idempotency_keys: set[str] = set()
        seen_position_ids: set[str] = set()
        seen_option_identities: set[tuple[str, str, str]] = set()

        ordered = sorted(
            snapshots,
            key=lambda item: (
                item.created_at,
                item.paper_trade_id,
            ),
        )

        for snapshot in ordered:
            position = snapshot.position

            if position is None:
                raise ValueError(
                    "active P7 snapshot must contain a position"
                )

            if snapshot.lifecycle_state.is_terminal:
                raise ValueError(
                    "recover_active returned a terminal trade"
                )

            if position.lifecycle_state not in {
                "OPEN",
                "PARTIALLY_EXITED",
            }:
                raise ValueError(
                    "active trade has unsupported lifecycle state"
                )

            if snapshot.paper_trade_id in seen_trade_ids:
                raise ValueError("duplicate paper_trade_id")

            if (
                snapshot.adapter_idempotency_key
                in seen_idempotency_keys
            ):
                raise ValueError(
                    "duplicate adapter idempotency key"
                )

            if position.position_id in seen_position_ids:
                raise ValueError("duplicate position_id")

            option_identity = (
                position.underlying_symbol,
                position.option_symbol,
                position.position_id,
            )

            if option_identity in seen_option_identities:
                raise ValueError(
                    "duplicate active option identity"
                )

            seen_trade_ids.add(snapshot.paper_trade_id)
            seen_idempotency_keys.add(
                snapshot.adapter_idempotency_key
            )
            seen_position_ids.add(position.position_id)
            seen_option_identities.add(option_identity)

        return tuple(ordered)

    def __call__(
        self,
        cycle_input: PaperOrchestrationCycleInputV1,
    ) -> PaperOrchestrationCycleResultV1:
        if type(cycle_input) is not PaperOrchestrationCycleInputV1:
            raise TypeError(
                "cycle_input must be exact "
                "PaperOrchestrationCycleInputV1"
            )

        started_at = _aware(
            self.clock(),
            "clock result",
        )

        policy = self.portfolio_policy_provider(
            cycle_input
        )

        if type(policy) is not PaperPortfolioPolicyV1:
            raise TypeError(
                "portfolio_policy_provider must return exact "
                "PaperPortfolioPolicyV1"
            )

        snapshots = self._validate_active_snapshots(
            self.trade_recovery_service.recover_active()
        )

        if not snapshots:
            completed_at = _aware(
                self.clock(),
                "clock result",
            )

            stage = PaperOrchestrationStageResultV1(
                stage_result_id=(
                    f"{cycle_input.cycle_id}:"
                    "p7-active-batch-empty"
                ),
                cycle_id=cycle_input.cycle_id,
                stage="P7_LIFECYCLE",
                status="NO_ACTION",
                started_at=started_at,
                completed_at=completed_at,
                source_result_type=(
                    "PaperTradeRecoveryService"
                ),
                paper_action_occurred=False,
                metadata={
                    "active_trade_count": 0,
                    "processed_trade_count": 0,
                    "execution_mode": "PAPER",
                    "broker_order_submission": False,
                },
            )

            return PaperOrchestrationCycleResultV1(
                cycle_result_id=(
                    f"{cycle_input.cycle_id}:"
                    "active-monitoring-empty-result"
                ),
                cycle_id=cycle_input.cycle_id,
                cycle_idempotency_key=(
                    cycle_input.cycle_idempotency_key
                ),
                cycle_input_semantic_hash=(
                    cycle_input.semantic_hash()
                ),
                cycle_status="COMPLETED_NO_ACTION",
                terminal_stage="P7_LIFECYCLE",
                started_at=started_at,
                completed_at=completed_at,
                stage_results=(stage,),
                metadata={
                    "active_trade_count": 0,
                    "processed_trade_count": 0,
                    "trade_outcomes": (),
                    "execution_mode": "PAPER",
                    "broker_order_submission": False,
                },
            )

        trade_outcomes: list[dict[str, object]] = []
        blockers: list[str] = []
        warnings: list[str] = []
        errors: list[str] = []
        paper_actions: list[str] = []

        p7_state_changed = False
        p8_state_changed = False
        any_success = False

        for index, snapshot in enumerate(
            snapshots,
            start=1,
        ):
            position = snapshot.position
            assert position is not None

            outcome: dict[str, object] = {
                "sequence": index,
                "paper_trade_id": snapshot.paper_trade_id,
                "position_id": position.position_id,
                "underlying_symbol": (
                    position.underlying_symbol
                ),
                "option_symbol": position.option_symbol,
                "status": "FAILED",
                "p7_state_changed": False,
                "p8_state_changed": False,
                "paper_action_occurred": False,
                "blockers": (),
                "warnings": (),
                "errors": (),
            }

            try:
                quote = self.quote_reader(snapshot)

                evaluation_input = (
                    self.evaluation_input_factory(
                        cycle_input=cycle_input,
                        snapshot=snapshot,
                        quote=quote,
                    )
                )

                basis = (
                    cycle_input.cycle_id,
                    cycle_input.cycle_idempotency_key,
                    snapshot.paper_trade_id,
                    position.position_id,
                )

                monitoring_input = (
                    ExistingPositionMonitoringInputV1(
                        portfolio_id=self.portfolio_id,
                        result_snapshot_id=_identity(
                            "monitoring-p8-snapshot",
                            *basis,
                        ),
                        portfolio_event_id=_identity(
                            "monitoring-p8-event",
                            *basis,
                        ),
                        update_idempotency_key=_identity(
                            "monitoring-p8-update-key",
                            *basis,
                        ),
                        updated_at=(
                            cycle_input.cycle_requested_at
                        ),
                        portfolio_policy=policy,
                        p7_snapshot=snapshot,
                        evaluation_input=evaluation_input,
                    )
                )

                result = self.monitoring_executor.execute(
                    monitoring_input
                )

                if type(result) is not ExistingPositionMonitoringResultV1:
                    raise TypeError(
                        "monitoring executor must return exact "
                        "ExistingPositionMonitoringResultV1"
                    )

                result_blockers = _text_tuple(
                    result.blockers
                )
                result_warnings = _text_tuple(
                    result.warnings
                )

                outcome.update(
                    {
                        "status": result.status,
                        "p7_state_changed": (
                            result.p7_state_changed
                        ),
                        "p8_state_changed": (
                            result.p8_state_changed
                        ),
                        "paper_action_occurred": (
                            result.paper_action_occurred
                        ),
                        "blockers": result_blockers,
                        "warnings": result_warnings,
                        "errors": (),
                    }
                )

                blockers.extend(result_blockers)
                warnings.extend(result_warnings)

                p7_state_changed = (
                    p7_state_changed
                    or result.p7_state_changed
                )
                p8_state_changed = (
                    p8_state_changed
                    or result.p8_state_changed
                )

                if result.status != "BLOCKED":
                    any_success = True

                if result.status == "PARTIAL_EXIT":
                    paper_actions.append(
                        "PARTIAL_EXIT_POSITION"
                    )

                elif result.status == "CLOSED":
                    paper_actions.append(
                        "CLOSE_POSITION"
                    )

            except Exception as exc:
                error_code = (
                    "ACTIVE_POSITION_MONITORING_"
                    f"{type(exc).__name__.upper()}"
                )

                errors.append(error_code)

                outcome.update(
                    {
                        "status": "FAILED",
                        "errors": (error_code,),
                        "error_type": type(exc).__name__,
                        "error_message": (
                            str(exc) or type(exc).__name__
                        ),
                    }
                )

            trade_outcomes.append(outcome)

        completed_at = _aware(
            self.clock(),
            "clock result",
        )

        unique_blockers = tuple(
            dict.fromkeys(blockers)
        )
        unique_warnings = tuple(
            dict.fromkeys(warnings)
        )
        unique_errors = tuple(
            dict.fromkeys(errors)
        )
        unique_actions = tuple(
            dict.fromkeys(paper_actions)
        )

        if unique_errors and not any_success:
            stage_status = "FAILED"
            cycle_status = "FAILED"

            from services.contracts.paper_orchestration_failure_v1 import (
                PaperOrchestrationFailureV1,
            )

            failure = PaperOrchestrationFailureV1(
                failure_code=(
                    "ACTIVE_POSITION_BATCH_FAILURE"
                ),
                stage="P7_LIFECYCLE",
                message=(
                    "all active PAPER position monitoring "
                    "operations failed closed"
                ),
                retryable=True,
                source_component=type(self).__name__,
                metadata={
                    "active_trade_count": len(snapshots),
                    "failed_trade_count": len(
                        unique_errors
                    ),
                },
            )

        elif unique_blockers and not any_success:
            stage_status = "BLOCKED"
            cycle_status = "BLOCKED"
            failure = None

        else:
            stage_status = "COMPLETED"
            cycle_status = (
                "COMPLETED"
                if unique_actions
                else "COMPLETED_NO_ACTION"
            )
            failure = None

        p7_stage = PaperOrchestrationStageResultV1(
            stage_result_id=(
                f"{cycle_input.cycle_id}:"
                "p7-active-position-batch"
            ),
            cycle_id=cycle_input.cycle_id,
            stage="P7_LIFECYCLE",
            status=stage_status,
            started_at=started_at,
            completed_at=completed_at,
            source_result_type=(
                "ExistingPositionMonitoringResultV1"
            ),
            paper_action_occurred=bool(
                unique_actions
            ),
            blockers=unique_blockers,
            warnings=unique_warnings,
            errors=unique_errors,
            failure=failure,
            metadata={
                "active_trade_count": len(snapshots),
                "processed_trade_count": len(
                    trade_outcomes
                ),
                "p7_state_changed": p7_state_changed,
                "p8_state_changed": p8_state_changed,
                "trade_outcomes": tuple(
                    trade_outcomes
                ),
                "execution_mode": "PAPER",
                "broker_order_submission": False,
            },
        )

        stage_results = [p7_stage]
        terminal_stage = "P7_LIFECYCLE"

        if p8_state_changed:
            p8_stage = PaperOrchestrationStageResultV1(
                stage_result_id=(
                    f"{cycle_input.cycle_id}:"
                    "p8-active-position-batch"
                ),
                cycle_id=cycle_input.cycle_id,
                stage="P8_PORTFOLIO_UPDATE",
                status="COMPLETED",
                started_at=started_at,
                completed_at=completed_at,
                source_result_type=(
                    "PaperPortfolioPersistenceSnapshotV1"
                ),
                paper_action_occurred=bool(
                    unique_actions
                ),
                warnings=unique_warnings,
                metadata={
                    "updated_trade_count": sum(
                        bool(
                            item[
                                "p8_state_changed"
                            ]
                        )
                        for item in trade_outcomes
                    ),
                    "execution_mode": "PAPER",
                    "broker_order_submission": False,
                },
            )

            stage_results.append(p8_stage)
            terminal_stage = "P8_PORTFOLIO_UPDATE"

        return PaperOrchestrationCycleResultV1(
            cycle_result_id=(
                f"{cycle_input.cycle_id}:"
                "active-monitoring-batch-result"
            ),
            cycle_id=cycle_input.cycle_id,
            cycle_idempotency_key=(
                cycle_input.cycle_idempotency_key
            ),
            cycle_input_semantic_hash=(
                cycle_input.semantic_hash()
            ),
            cycle_status=cycle_status,
            terminal_stage=terminal_stage,
            started_at=started_at,
            completed_at=completed_at,
            stage_results=tuple(stage_results),
            paper_actions=unique_actions,
            blockers=unique_blockers,
            warnings=unique_warnings,
            errors=unique_errors,
            metadata={
                "active_trade_count": len(snapshots),
                "processed_trade_count": len(
                    trade_outcomes
                ),
                "trade_outcomes": tuple(
                    trade_outcomes
                ),
                "p7_state_changed": p7_state_changed,
                "p8_state_changed": p8_state_changed,
                "execution_mode": "PAPER",
                "live_execution_eligible": False,
                "broker_order_submission": False,
            },
        )