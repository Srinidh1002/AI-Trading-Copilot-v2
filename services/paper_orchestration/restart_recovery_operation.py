from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    def __call__(self) -> datetime: ...


RecoveryCallable = Callable[[str, datetime], object]


@dataclass(frozen=True, slots=True)
class RestartRecoveryTargetV1:
    target_type: str
    target_id: str
    recovery_authority: RecoveryCallable

    def __post_init__(self) -> None:
        target_type = str(self.target_type).strip().upper()
        if target_type not in {"P7_TRADE", "P8_PORTFOLIO"}:
            raise ValueError("target_type is unsupported")
        if type(self.target_id) is not str or not self.target_id.strip():
            raise ValueError("target_id must be a non-empty string")
        if not callable(self.recovery_authority):
            raise TypeError("recovery_authority must be callable")
        object.__setattr__(self, "target_type", target_type)
        object.__setattr__(self, "target_id", self.target_id.strip())


class RestartRecoveryOperation:
    """Fail-closed startup recovery for caller-supplied P7/P8 identities."""

    def __init__(
        self,
        *,
        targets: Iterable[RestartRecoveryTargetV1],
        clock: Clock,
    ) -> None:
        values = tuple(targets)
        if any(
            type(item) is not RestartRecoveryTargetV1
            for item in values
        ):
            raise TypeError(
                "targets must contain exact RestartRecoveryTargetV1 values"
            )
        if not callable(clock):
            raise TypeError("clock must be callable")

        identities = tuple(
            (item.target_type, item.target_id)
            for item in values
        )
        if len(set(identities)) != len(identities):
            raise ValueError("duplicate recovery target")

        self.targets = values
        self.clock = clock

    def __call__(self) -> dict[str, object]:
        recovered_at = self.clock()
        if not isinstance(recovered_at, datetime):
            raise TypeError("clock must return a datetime")
        if (
            recovered_at.tzinfo is None
            or recovered_at.utcoffset() is None
        ):
            raise ValueError(
                "clock must return a timezone-aware datetime"
            )

        results: list[dict[str, object]] = []
        success = True

        for target in self.targets:
            try:
                recovery = target.recovery_authority(
                    target.target_id,
                    recovered_at,
                )
                status = str(
                    getattr(recovery, "status", "UNKNOWN")
                ).strip().upper()
                item_success = status == "RECOVERED"
                results.append(
                    {
                        "target_type": target.target_type,
                        "target_id": target.target_id,
                        "status": status,
                        "success": item_success,
                        "error": None,
                    }
                )
                success = success and item_success
            except Exception as exc:
                success = False
                results.append(
                    {
                        "target_type": target.target_type,
                        "target_id": target.target_id,
                        "status": "ERROR",
                        "success": False,
                        "error": str(exc) or type(exc).__name__,
                    }
                )

        return {
            "success": success,
            "recovered_at": recovered_at.isoformat(),
            "target_count": len(self.targets),
            "results": results,
            "execution_mode": "PAPER",
            "live_execution_eligible": False,
        }
