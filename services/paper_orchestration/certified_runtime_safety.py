from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


SUPPORTED_INSTRUMENTS = ("NIFTY", "SENSEX")
FORBIDDEN_BROKER_ORDER_METHODS = (
    "place_order",
    "submit_order",
    "modify_order",
    "cancel_order",
)


@dataclass(frozen=True, slots=True)
class CertifiedPaperRuntimeSafetyConfigV1:
    instruments: tuple[str, ...]
    interval_seconds: float = 60.0
    observe_only: bool = True
    emergency_halt: bool = False
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False
    schema_version: str = "certified_paper_runtime_safety_config.v1"

    def __post_init__(self) -> None:
        instruments = tuple(
            str(item).strip().upper()
            for item in self.instruments
            if str(item).strip()
        )
        if not instruments:
            raise ValueError("at least one instrument is required")
        if len(set(instruments)) != len(instruments):
            raise ValueError("duplicate instruments are not allowed")
        unsupported = tuple(
            item for item in instruments
            if item not in SUPPORTED_INSTRUMENTS
        )
        if unsupported:
            raise ValueError(
                "unsupported instruments: " + ", ".join(unsupported)
            )
        object.__setattr__(self, "instruments", instruments)

        value = float(self.interval_seconds)
        if value <= 0:
            raise ValueError("interval_seconds must be greater than zero")
        object.__setattr__(self, "interval_seconds", value)

        if self.execution_mode != "PAPER":
            raise ValueError("execution_mode must be PAPER")
        if self.live_execution_eligible:
            raise ValueError("live execution is not eligible")
        if self.broker_order_submission:
            raise ValueError("broker order submission must remain disabled")
        if self.schema_version != (
            "certified_paper_runtime_safety_config.v1"
        ):
            raise ValueError("unsupported schema_version")

    @property
    def new_entries_enabled(self) -> bool:
        return not self.observe_only and not self.emergency_halt

    @property
    def monitoring_enabled(self) -> bool:
        return True


def validate_repository_paper_safety(
    *,
    broker: object,
    enable_paper_trading: object,
    enable_live_trading: object,
) -> None:
    if broker != "PAPER":
        raise RuntimeError("config.BROKER must equal PAPER")
    if enable_paper_trading is not True:
        raise RuntimeError("ENABLE_PAPER_TRADING must be True")
    if enable_live_trading is not False:
        raise RuntimeError("ENABLE_LIVE_TRADING must be False")


def validate_no_broker_submission_guard(
    *,
    broker_order_submission: object,
) -> None:
    """Explicit automated-PAPER barrier: order APIs are outside this runtime."""
    if broker_order_submission is not False:
        raise RuntimeError(
            "automated PAPER mode cannot enable broker order submission "
            f"({', '.join(FORBIDDEN_BROKER_ORDER_METHODS)})"
        )


def validate_required_angel_credentials(
    environment: Mapping[str, str],
) -> None:
    required = (
        "ANGEL_API_KEY",
        "ANGEL_CLIENT_ID",
        "ANGEL_PIN",
        "ANGEL_TOTP_SECRET",
    )
    missing = tuple(
        name
        for name in required
        if not str(environment.get(name, "")).strip()
    )
    if missing:
        raise RuntimeError(
            "missing required Angel credentials: "
            + ", ".join(missing)
        )


def validate_runtime_paths(
    *,
    journal_directory: Path,
    log_directory: Path,
) -> None:
    for path, name in (
        (journal_directory, "journal_directory"),
        (log_directory, "log_directory"),
    ):
        if not isinstance(path, Path):
            raise TypeError(f"{name} must be a Path")
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".certified_paper_write_probe"
        try:
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
        except OSError as exc:
            raise RuntimeError(f"{name} is not writable") from exc


def safety_banner(
    config: CertifiedPaperRuntimeSafetyConfigV1,
) -> dict[str, object]:
    if type(config) is not CertifiedPaperRuntimeSafetyConfigV1:
        raise TypeError(
            "config must be exact CertifiedPaperRuntimeSafetyConfigV1"
        )
    return {
        "execution_mode": config.execution_mode,
        "live_execution_eligible": config.live_execution_eligible,
        "broker_order_submission": config.broker_order_submission,
        "observe_only": config.observe_only,
        "emergency_halt": config.emergency_halt,
        "new_entries_enabled": config.new_entries_enabled,
        "monitoring_enabled": config.monitoring_enabled,
        "instruments": list(config.instruments),
        "interval_seconds": config.interval_seconds,
    }
