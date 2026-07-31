from __future__ import annotations

import argparse
import importlib
import signal
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from services.paper_orchestration.continuous_runtime_adapter import (
    ContinuousPaperOrchestrationRuntimeAdapter,
)
from services.paper_orchestration.certified_operator_controls import (
    CertifiedOperatorControls,
)
from services.paper_orchestration.certified_runtime_logging import (
    CertifiedJsonLineLogger,
)


Clock = Callable[[], datetime]


@dataclass(frozen=True, slots=True)
class CertifiedLauncherCompositionV1:
    runtime_adapter: ContinuousPaperOrchestrationRuntimeAdapter
    controls: CertifiedOperatorControls
    logger: CertifiedJsonLineLogger
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "certified_launcher_composition.v1"

    def __post_init__(self) -> None:
        if (
            type(self.runtime_adapter)
            is not ContinuousPaperOrchestrationRuntimeAdapter
        ):
            raise TypeError("runtime_adapter")
        if type(self.controls) is not CertifiedOperatorControls:
            raise TypeError("controls")
        if type(self.logger) is not CertifiedJsonLineLogger:
            raise TypeError("logger")
        if self.execution_mode != "PAPER":
            raise ValueError("execution_mode must be PAPER")
        if self.live_execution_eligible:
            raise ValueError("live execution is not eligible")
        if self.schema_version != "certified_launcher_composition.v1":
            raise ValueError("unsupported schema_version")


class CertifiedPaperRuntimeLauncher:
    def __init__(
        self,
        *,
        composition: CertifiedLauncherCompositionV1,
        clock: Clock,
    ) -> None:
        if type(composition) is not CertifiedLauncherCompositionV1:
            raise TypeError("composition")
        if not callable(clock):
            raise TypeError("clock")
        self.composition = composition
        self.clock = clock
        self._previous_handlers: dict[int, Any] = {}

    def _now(self) -> datetime:
        value = self.clock()
        if not isinstance(value, datetime):
            raise TypeError("clock must return datetime")
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("clock must return timezone-aware datetime")
        return value

    def _handle_stop_signal(self, signum, frame) -> None:
        self.composition.logger.emit(
            event="STOP_REQUESTED",
            occurred_at=self._now(),
            fields={"signal": signum},
        )
        self.composition.runtime_adapter.request_stop()

    def _install_signal_handlers(self) -> None:
        for signum in (signal.SIGINT, signal.SIGTERM):
            try:
                self._previous_handlers[signum] = signal.getsignal(signum)
                signal.signal(signum, self._handle_stop_signal)
            except (ValueError, OSError):
                continue

    def _restore_signal_handlers(self) -> None:
        for signum, handler in self._previous_handlers.items():
            try:
                signal.signal(signum, handler)
            except (ValueError, OSError):
                pass
        self._previous_handlers.clear()

    def run(
        self,
        *,
        max_cycles: int | None = None,
    ) -> dict[str, object]:
        snapshot = self.composition.controls.snapshot()
        self.composition.logger.emit(
            event="RUNTIME_STARTING",
            occurred_at=self._now(),
            fields={
                "observe_only": snapshot.observe_only,
                "emergency_halt": snapshot.emergency_halt,
                "new_entries_allowed": snapshot.new_entries_allowed,
                "position_monitoring_allowed": (
                    snapshot.position_monitoring_allowed
                ),
                "max_cycles": max_cycles,
            },
        )

        self._install_signal_handlers()
        try:
            result = self.composition.runtime_adapter.run(
                max_cycles=max_cycles
            )
            self.composition.logger.emit(
                event="RUNTIME_STOPPED",
                occurred_at=self._now(),
                fields={
                    "stats": result,
                    "graceful_shutdown": True,
                },
            )
            return result
        except KeyboardInterrupt:
            self.composition.runtime_adapter.request_stop()
            result = self.composition.runtime_adapter.get_stats()
            self.composition.logger.emit(
                event="RUNTIME_INTERRUPTED",
                occurred_at=self._now(),
                fields={
                    "stats": result,
                    "graceful_shutdown": True,
                },
            )
            return result
        except BaseException as exc:
            self.composition.runtime_adapter.request_stop()
            self.composition.logger.emit(
                event="RUNTIME_FAILED",
                occurred_at=self._now(),
                fields={
                    "error_type": type(exc).__name__,
                    "error": str(exc) or type(exc).__name__,
                    "graceful_shutdown": False,
                },
            )
            raise
        finally:
            self._restore_signal_handlers()
            self.composition.logger.close()


def _load_factory(path: str):
    if ":" not in path:
        raise ValueError("factory must use module:function syntax")
    module_name, function_name = path.split(":", 1)
    factory = getattr(importlib.import_module(module_name), function_name)
    if not callable(factory):
        raise TypeError("launcher composition factory must be callable")
    return factory


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Certified PAPER orchestration launcher",
    )
    parser.add_argument(
        "--factory",
        required=True,
        help=(
            "Composition factory in module:function form. It must return "
            "CertifiedLauncherCompositionV1."
        ),
    )
    parser.add_argument(
        "--max-cycles",
        type=int,
        default=None,
    )
    parser.add_argument(
        "--observe-only",
        action="store_true",
    )
    parser.add_argument(
        "--emergency-halt",
        action="store_true",
    )
    args = parser.parse_args(argv)

    factory = _load_factory(args.factory)
    composition = factory()
    if type(composition) is not CertifiedLauncherCompositionV1:
        raise TypeError(
            "factory must return exact CertifiedLauncherCompositionV1"
        )

    if args.observe_only:
        composition.controls.set_observe_only(True)
    if args.emergency_halt:
        composition.controls.set_emergency_halt(True)

    launcher = CertifiedPaperRuntimeLauncher(
        composition=composition,
        clock=lambda: datetime.now(timezone.utc),
    )
    launcher.run(max_cycles=args.max_cycles)
    return 0


if __name__ == "__main__":
    canonical_module = importlib.import_module(
        "services.paper_orchestration.certified_runtime_launcher"
    )
    raise SystemExit(canonical_module.main())
