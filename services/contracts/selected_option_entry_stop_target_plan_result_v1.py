"""Typed Task 4 entry, stop-loss, and target planning result."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from services.contracts.entry_zone_evaluation_result_v1 import (
    EntryZoneEvaluationResultV1,
)
from services.contracts.stop_loss_evaluation_result_v1 import (
    StopLossEvaluationResultV1,
)
from services.contracts.three_target_evaluation_result_v1 import (
    ThreeTargetEvaluationResultV1,
)


_STATUSES = {"READY", "BLOCKED", "UNAVAILABLE"}


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not (cleaned := value.strip()):
        raise ValueError(name)
    return cleaned


def _optional_text(value: object, name: str) -> str | None:
    if value is None:
        return None
    return _text(value, name)


def _aware(value: object, name: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(name)
    return value


def _messages(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise TypeError(name)
    return tuple(dict.fromkeys(_text(item, name) for item in value))


@dataclass(frozen=True, slots=True)
class SelectedOptionEntryStopTargetPlanResultV1:
    """Task 4 deterministic planning output for one Task 3C contract."""

    SCHEMA_VERSION: ClassVar[str] = (
        "selected_option_entry_stop_target_plan_result.v1"
    )

    planning_result_id: str
    affordability_result_id: str
    certification_result_id: str
    parent_cycle_id: str
    parent_decision_id: str
    bridge_result_id: str
    candidate_id: str | None
    observation_id: str | None
    ranking_result_id: str | None
    contract_id: str | None
    trade_plan_input_id: str | None
    policy_id: str | None
    evaluated_at: datetime
    status: str
    planning_allowed: bool
    entry_result: EntryZoneEvaluationResultV1 | None
    stop_loss_result: StopLossEvaluationResultV1 | None
    target_result: ThreeTargetEvaluationResultV1 | None
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False

    def __post_init__(self) -> None:
        for name in (
            "planning_result_id",
            "affordability_result_id",
            "certification_result_id",
            "parent_cycle_id",
            "parent_decision_id",
            "bridge_result_id",
        ):
            object.__setattr__(self, name, _text(getattr(self, name), name))

        for name in (
            "candidate_id",
            "observation_id",
            "ranking_result_id",
            "contract_id",
            "trade_plan_input_id",
            "policy_id",
        ):
            object.__setattr__(
                self,
                name,
                _optional_text(getattr(self, name), name),
            )

        object.__setattr__(
            self,
            "evaluated_at",
            _aware(self.evaluated_at, "evaluated_at"),
        )

        status = _text(self.status, "status").upper()
        if status not in _STATUSES:
            raise ValueError("status")
        object.__setattr__(self, "status", status)

        if type(self.planning_allowed) is not bool:
            raise TypeError("planning_allowed")

        for name, expected in (
            ("entry_result", EntryZoneEvaluationResultV1),
            ("stop_loss_result", StopLossEvaluationResultV1),
            ("target_result", ThreeTargetEvaluationResultV1),
        ):
            value = getattr(self, name)
            if value is not None and type(value) is not expected:
                raise TypeError(name)

        for name in ("blockers", "warnings"):
            object.__setattr__(
                self,
                name,
                _messages(getattr(self, name), name),
            )

        if status == "READY":
            if (
                not self.planning_allowed
                or self.blockers
                or self.trade_plan_input_id is None
                or self.policy_id is None
                or self.entry_result is None
                or self.stop_loss_result is None
                or self.target_result is None
                or self.entry_result.status != "READY"
                or self.stop_loss_result.status != "READY"
                or self.target_result.status != "READY"
            ):
                raise ValueError("READY coherence")
        elif status == "BLOCKED":
            if self.planning_allowed or not self.blockers:
                raise ValueError("BLOCKED coherence")
            if self.entry_result is None:
                raise ValueError("BLOCKED requires entry result")
        else:
            if (
                self.planning_allowed
                or not self.blockers
                or self.entry_result is not None
                or self.stop_loss_result is not None
                or self.target_result is not None
                or self.trade_plan_input_id is not None
                or self.policy_id is not None
            ):
                raise ValueError("UNAVAILABLE coherence")

        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
        ):
            raise ValueError("PAPER-only Task 4 result")

    def to_dict(self) -> dict[str, object]:
        values: dict[str, object] = {}
        for name in self.__dataclass_fields__:
            value = getattr(self, name)
            if isinstance(value, datetime):
                values[name] = value.isoformat()
            elif isinstance(value, tuple):
                values[name] = list(value)
            elif name in {"entry_result", "stop_loss_result", "target_result"}:
                values[name] = None if value is None else value.to_dict()
            else:
                values[name] = value
        values["schema_version"] = self.SCHEMA_VERSION
        return values

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
