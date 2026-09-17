"""Versioned rules for deterministic prediction lifecycle outcomes."""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from typing import ClassVar


_SAME_OBSERVATION_PRECEDENCE = {
    "STOP_FIRST",
    "TARGET_FIRST",
    "CONSERVATIVE_STOP_FIRST",
}
_MULTIPLE_TARGET_MODES = {"HIGHEST_CROSSED_TARGET"}
_PARTIAL_TARGET_MODES = {"HIGHEST_TARGET_BEFORE_TERMINAL"}
_EARLY_EXIT_MODES = {"TARGET_BEFORE_EARLY_EXIT"}


def _text(value: object, name: str) -> str:
    if type(value) is not str:
        raise TypeError(name)
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(name)
    return cleaned


def _nonnegative(value: object, name: str) -> float:
    if (
        type(value) not in (int, float)
        or isinstance(value, bool)
        or not math.isfinite(value)
        or value < 0.0
    ):
        raise ValueError(name)
    return float(value)


@dataclass(frozen=True, slots=True)
class PredictionLifecycleOutcomePolicyV1:
    """Immutable precedence and missed-move rules."""

    SCHEMA_VERSION: ClassVar[str] = (
        "prediction_lifecycle_outcome_policy.v1"
    )

    policy_id: str
    policy_version: str
    same_observation_precedence: str = "CONSERVATIVE_STOP_FIRST"
    multiple_target_crossing_mode: str = "HIGHEST_CROSSED_TARGET"
    partial_target_outcome_mode: str = "HIGHEST_TARGET_BEFORE_TERMINAL"
    early_exit_precedence: str = "TARGET_BEFORE_EARLY_EXIT"
    no_trade_move_threshold_percent: float = 0.20
    any_data_gap_is_unavailable: bool = True
    break_even_early_exit_is_loss: bool = True
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("policy_id", "policy_version"):
            object.__setattr__(self, name, _text(getattr(self, name), name))

        controlled = (
            (
                "same_observation_precedence",
                _SAME_OBSERVATION_PRECEDENCE,
            ),
            (
                "multiple_target_crossing_mode",
                _MULTIPLE_TARGET_MODES,
            ),
            (
                "partial_target_outcome_mode",
                _PARTIAL_TARGET_MODES,
            ),
            ("early_exit_precedence", _EARLY_EXIT_MODES),
        )
        for name, allowed in controlled:
            normalized = _text(getattr(self, name), name).upper()
            if normalized not in allowed:
                raise ValueError(name)
            object.__setattr__(self, name, normalized)

        object.__setattr__(
            self,
            "no_trade_move_threshold_percent",
            _nonnegative(
                self.no_trade_move_threshold_percent,
                "no_trade_move_threshold_percent",
            ),
        )

        for name in (
            "any_data_gap_is_unavailable",
            "break_even_early_exit_is_loss",
            "live_execution_eligible",
            "broker_order_submission",
        ):
            if type(getattr(self, name)) is not bool:
                raise TypeError(name)

        if self.any_data_gap_is_unavailable is not True:
            raise ValueError("certified outcomes require fail-closed data gaps")
        if self.break_even_early_exit_is_loss is not True:
            raise ValueError("break-even early exits remain conservative")
        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
            or self.schema_version != self.SCHEMA_VERSION
        ):
            raise ValueError("PAPER-only lifecycle outcome policy")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    @property
    def semantic_hash(self) -> str:
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()
