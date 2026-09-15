"""Task 9 canonical runtime/PAPER safety proof producer."""
from __future__ import annotations

from datetime import datetime

from services.contracts.task9_runtime_config_v1 import (
    Task9RuntimeConfigV1,
)
from services.contracts.task9_runtime_safety_proof_v1 import (
    Task9RuntimeSafetyProofV1,
    Task9RuntimeSafetyStatus,
)
from services.paper_orchestration.certified_runtime_safety import (
    validate_no_broker_submission_guard,
    validate_repository_paper_safety,
)


def produce_task9_runtime_safety_proof(
    *,
    runtime_config: Task9RuntimeConfigV1,
    repository_broker,
    repository_enable_paper_trading,
    repository_enable_live_trading,
    observed_at: datetime,
) -> Task9RuntimeSafetyProofV1:
    if type(runtime_config) is not Task9RuntimeConfigV1:
        raise TypeError(
            "runtime_config"
        )

    if (
        not isinstance(observed_at, datetime)
        or observed_at.tzinfo is None
        or observed_at.utcoffset() is None
    ):
        raise ValueError(
            "observed_at"
        )

    repository_passed = False
    broker_guard_passed = False
    failure_reason = None

    try:
        validate_repository_paper_safety(
            broker=repository_broker,
            enable_paper_trading=(
                repository_enable_paper_trading
            ),
            enable_live_trading=(
                repository_enable_live_trading
            ),
        )

        repository_passed = True

        validate_no_broker_submission_guard(
            broker_order_submission=(
                runtime_config.broker_order_submission
            ),
        )

        broker_guard_passed = True

    except RuntimeError as exc:
        failure_reason = (
            "TASK9_RUNTIME_SAFETY_INVALID:"
            f"{type(exc).__name__}"
        )

    if not (
        repository_passed
        and broker_guard_passed
    ):
        status = (
            Task9RuntimeSafetyStatus.INVALID
        )

        new_entries_permitted = False

        sanitized_reason = (
            failure_reason
            or "TASK9_RUNTIME_SAFETY_INVALID"
        )

    elif runtime_config.emergency_halt_enabled:
        status = (
            Task9RuntimeSafetyStatus.EMERGENCY_HALTED
        )

        new_entries_permitted = False

        sanitized_reason = (
            "TASK9_EMERGENCY_HALT_ACTIVE"
        )

    else:
        status = (
            Task9RuntimeSafetyStatus.READY
        )

        new_entries_permitted = True
        sanitized_reason = None

    return Task9RuntimeSafetyProofV1(
        proof_id=(
            "task9-runtime-safety:"
            f"{runtime_config.runtime_config_id}:"
            f"{observed_at.isoformat()}"
        ),
        observed_at=observed_at,
        status=status,
        runtime_config_id=(
            runtime_config.runtime_config_id
        ),
        execution_mode=(
            runtime_config.execution_mode
        ),
        broker_order_submission=(
            runtime_config.broker_order_submission
        ),
        live_execution_eligible=(
            runtime_config.live_execution_eligible
        ),
        repository_broker=str(
            repository_broker
        ),
        repository_paper_trading_enabled=(
            repository_enable_paper_trading is True
        ),
        repository_live_trading_enabled=(
            repository_enable_live_trading is True
        ),
        repository_paper_safety_passed=(
            repository_passed
        ),
        no_broker_submission_guard_passed=(
            broker_guard_passed
        ),
        emergency_halt_enabled=(
            runtime_config.emergency_halt_enabled
        ),
        emergency_halt_reason=(
            runtime_config.emergency_halt_reason
        ),
        new_entries_permitted=(
            new_entries_permitted
        ),
        monitoring_permitted=True,
        sanitized_reason=(
            sanitized_reason
        ),
    )


__all__ = (
    "produce_task9_runtime_safety_proof",
)
