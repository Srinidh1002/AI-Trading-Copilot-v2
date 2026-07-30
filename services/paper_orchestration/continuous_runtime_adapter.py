from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from services.continuous_paper_trading_runtime import (
    ContinuousPaperTradingRuntime,
)
from services.contracts.paper_orchestration_cycle_input_v1 import (
    PaperOrchestrationCycleInputV1,
)
from services.contracts.paper_orchestration_cycle_result_v1 import (
    PaperOrchestrationCycleResultV1,
)
from services.paper_orchestration.deterministic_cycle_coordinator import (
    DeterministicPaperOrchestrationCycleCoordinator,
)


CycleInputFactory = Callable[[], PaperOrchestrationCycleInputV1]
StartupOperation = Callable[[], object]


@dataclass(frozen=True, slots=True)
class ContinuousPaperOrchestrationRuntimeConfigV1:
    interval_seconds: float = 60.0
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = (
        "continuous_paper_orchestration_runtime_config.v1"
    )

    def __post_init__(self) -> None:
        value = float(self.interval_seconds)
        if value < 0:
            raise ValueError("interval_seconds cannot be negative")
        object.__setattr__(self, "interval_seconds", value)

        if self.execution_mode != "PAPER":
            raise ValueError("execution_mode must be PAPER")
        if self.live_execution_eligible:
            raise ValueError("live execution is not eligible")
        if self.schema_version != (
            "continuous_paper_orchestration_runtime_config.v1"
        ):
            raise ValueError("unsupported schema_version")


class ContinuousPaperOrchestrationRuntimeAdapter:
    """Bind deterministic P9 cycle coordinators to the legacy-safe outer loop.

    The wrapped ContinuousPaperTradingRuntime controls only scheduling,
    non-overlap, stop handling, and per-operation isolation.
    """

    def __init__(
        self,
        *,
        opportunity_coordinator: (
            DeterministicPaperOrchestrationCycleCoordinator
        ),
        opportunity_input_factory: CycleInputFactory,
        monitoring_coordinator: (
            DeterministicPaperOrchestrationCycleCoordinator
        ),
        monitoring_input_factory: CycleInputFactory,
        config: ContinuousPaperOrchestrationRuntimeConfigV1,
        startup_operation: StartupOperation | None = None,
        sleep_function: Callable[[float], Any] | None = None,
        monotonic_function: Callable[[], float] | None = None,
    ) -> None:
        if (
            type(opportunity_coordinator)
            is not DeterministicPaperOrchestrationCycleCoordinator
        ):
            raise TypeError("opportunity_coordinator")
        if (
            type(monitoring_coordinator)
            is not DeterministicPaperOrchestrationCycleCoordinator
        ):
            raise TypeError("monitoring_coordinator")
        if not callable(opportunity_input_factory):
            raise TypeError("opportunity_input_factory")
        if not callable(monitoring_input_factory):
            raise TypeError("monitoring_input_factory")
        if type(config) is not ContinuousPaperOrchestrationRuntimeConfigV1:
            raise TypeError("config")
        if startup_operation is not None and not callable(
            startup_operation
        ):
            raise TypeError("startup_operation")

        self.opportunity_coordinator = opportunity_coordinator
        self.opportunity_input_factory = opportunity_input_factory
        self.monitoring_coordinator = monitoring_coordinator
        self.monitoring_input_factory = monitoring_input_factory
        self.config = config
        self.startup_operation = startup_operation

        runtime_kwargs = {
            "startup_operation": startup_operation,
            "interval_seconds": config.interval_seconds,
        }
        if sleep_function is not None:
            if not callable(sleep_function):
                raise TypeError("sleep_function")
            runtime_kwargs["sleep_function"] = sleep_function
        if monotonic_function is not None:
            if not callable(monotonic_function):
                raise TypeError("monotonic_function")
            runtime_kwargs["monotonic_function"] = monotonic_function

        self.runtime = ContinuousPaperTradingRuntime(
            opportunity_cycle=self._run_opportunity_cycle,
            monitoring_cycle=self._run_monitoring_cycle,
            **runtime_kwargs,
        )

    @staticmethod
    def _require_cycle_input(
        value: object,
        source: str,
    ) -> PaperOrchestrationCycleInputV1:
        if type(value) is not PaperOrchestrationCycleInputV1:
            raise TypeError(
                f"{source} must return exact "
                "PaperOrchestrationCycleInputV1"
            )
        return value

    @staticmethod
    def _require_cycle_result(
        value: object,
        source: str,
    ) -> PaperOrchestrationCycleResultV1:
        if type(value) is not PaperOrchestrationCycleResultV1:
            raise TypeError(
                f"{source} must return exact "
                "PaperOrchestrationCycleResultV1"
            )
        return value

    def _run_opportunity_cycle(
        self,
    ) -> PaperOrchestrationCycleResultV1:
        cycle_input = self._require_cycle_input(
            self.opportunity_input_factory(),
            "opportunity_input_factory",
        )
        result = self.opportunity_coordinator.run(cycle_input)
        return self._require_cycle_result(
            result,
            "opportunity_coordinator",
        )

    def _run_monitoring_cycle(
        self,
    ) -> PaperOrchestrationCycleResultV1:
        cycle_input = self._require_cycle_input(
            self.monitoring_input_factory(),
            "monitoring_input_factory",
        )
        result = self.monitoring_coordinator.run(cycle_input)
        return self._require_cycle_result(
            result,
            "monitoring_coordinator",
        )

    def run_cycle(self) -> dict[str, object]:
        return self.runtime.run_cycle()

    def run(self, *, max_cycles: int | None = None) -> dict[str, object]:
        return self.runtime.run(max_cycles=max_cycles)

    def run_forever(self) -> dict[str, object]:
        return self.runtime.run_forever()

    def request_stop(self) -> None:
        self.runtime.request_stop()

    def clear_stop_request(self) -> None:
        self.runtime.clear_stop_request()

    def is_running(self) -> bool:
        return self.runtime.is_running()

    def get_stats(self) -> dict[str, object]:
        return self.runtime.get_stats()
