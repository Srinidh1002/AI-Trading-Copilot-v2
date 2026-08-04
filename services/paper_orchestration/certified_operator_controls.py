from __future__ import annotations

import threading
from dataclasses import dataclass, replace

from services.contracts.paper_orchestration_cycle_input_v1 import (
    PaperOrchestrationCycleInputV1,
)
from services.contracts.paper_orchestration_policy_v1 import (
    PaperOrchestrationPolicyV1,
)


@dataclass(frozen=True, slots=True)
class CertifiedOperatorControlSnapshotV1:
    observe_only: bool
    emergency_halt: bool
    new_entries_allowed: bool
    position_monitoring_allowed: bool
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "certified_operator_control_snapshot.v1"

    def __post_init__(self) -> None:
        for name in (
            "observe_only",
            "emergency_halt",
            "new_entries_allowed",
            "position_monitoring_allowed",
        ):
            if type(getattr(self, name)) is not bool:
                raise TypeError(name)
        if self.new_entries_allowed and (
            self.observe_only or self.emergency_halt
        ):
            raise ValueError(
                "new entries cannot be allowed during observe-only or halt"
            )
        if not self.position_monitoring_allowed:
            raise ValueError(
                "certified controls must keep position monitoring allowed"
            )
        if self.execution_mode != "PAPER":
            raise ValueError("execution_mode must be PAPER")
        if self.live_execution_eligible:
            raise ValueError("live execution is not eligible")
        if self.schema_version != (
            "certified_operator_control_snapshot.v1"
        ):
            raise ValueError("unsupported schema_version")


class CertifiedOperatorControls:
    """Thread-safe PAPER-only operator controls.

    Observe-only and emergency halt both suppress new entries while keeping
    existing-position monitoring enabled.
    """

    def __init__(
        self,
        *,
        observe_only: bool = True,
        emergency_halt: bool = False,
    ) -> None:
        if type(observe_only) is not bool:
            raise TypeError("observe_only")
        if type(emergency_halt) is not bool:
            raise TypeError("emergency_halt")
        self._lock = threading.RLock()
        self._observe_only = observe_only
        self._emergency_halt = emergency_halt

    def snapshot(self) -> CertifiedOperatorControlSnapshotV1:
        with self._lock:
            observe_only = self._observe_only
            emergency_halt = self._emergency_halt
        return CertifiedOperatorControlSnapshotV1(
            observe_only=observe_only,
            emergency_halt=emergency_halt,
            new_entries_allowed=not (
                observe_only or emergency_halt
            ),
            position_monitoring_allowed=True,
        )

    def set_observe_only(self, enabled: bool) -> None:
        if type(enabled) is not bool:
            raise TypeError("enabled")
        with self._lock:
            self._observe_only = enabled

    def set_emergency_halt(self, enabled: bool) -> None:
        if type(enabled) is not bool:
            raise TypeError("enabled")
        with self._lock:
            self._emergency_halt = enabled


class ControlledOpportunityInputFactory:
    """Apply operator controls to exact cycle inputs without mutating them."""

    def __init__(
        self,
        *,
        delegate,
        controls: CertifiedOperatorControls,
    ) -> None:
        if not callable(delegate):
            raise TypeError("delegate must be callable")
        if type(controls) is not CertifiedOperatorControls:
            raise TypeError("controls")
        self.delegate = delegate
        self.controls = controls

    def __call__(self) -> PaperOrchestrationCycleInputV1:
        value = self.delegate()
        if type(value) is not PaperOrchestrationCycleInputV1:
            raise TypeError(
                "delegate must return exact PaperOrchestrationCycleInputV1"
            )

        control = self.controls.snapshot()
        if control.new_entries_allowed:
            return value

        policy = value.orchestration_policy
        if type(policy) is not PaperOrchestrationPolicyV1:
            raise TypeError(
                "orchestration_policy must be exact "
                "PaperOrchestrationPolicyV1"
            )

        halted_policy = replace(
            policy,
            emergency_paper_halt=True,
        )
        metadata = dict(value.metadata)
        metadata.update(
            {
                "operator_observe_only": control.observe_only,
                "operator_emergency_halt": control.emergency_halt,
                "operator_new_entries_allowed": False,
                "operator_position_monitoring_allowed": True,
            }
        )
        return replace(
            value,
            orchestration_policy=halted_policy,
            metadata=metadata,
        )
