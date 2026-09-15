"""Immutable PAPER-only Task 9 live decision audit authority."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType


_MARKETS = {
    ("NIFTY", "NSE"),
    ("SENSEX", "BSE"),
}

_DISPOSITIONS = {
    "EVIDENCE_UNAVAILABLE",
    "POLICY_ABSTENTION",
    "ENTRY_ELIGIBLE",
    "OTHER_INELIGIBLE",
}


def _text(
    value: object,
    name: str,
) -> str:
    if (
        type(value) is not str
        or not value.strip()
    ):
        raise ValueError(name)

    return value.strip()


def _optional_text(
    value: object,
    name: str,
) -> str | None:
    if value is None:
        return None

    return _text(
        value,
        name,
    )


def _aware(
    value: object,
    name: str,
) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(name)

    return value


def _freeze(
    value: object,
) -> object:
    if isinstance(value, Mapping):
        result = {}

        for key, child in sorted(
            value.items(),
            key=lambda item: str(item[0]),
        ):
            normalized_key = str(key)

            if normalized_key in result:
                raise ValueError(
                    "snapshot key collision"
                )

            result[normalized_key] = (
                _freeze(child)
            )

        return MappingProxyType(
            result
        )

    if isinstance(
        value,
        (list, tuple),
    ):
        return tuple(
            _freeze(item)
            for item in value
        )

    if isinstance(
        value,
        (set, frozenset),
    ):
        return tuple(
            sorted(
                (
                    _freeze(item)
                    for item in value
                ),
                key=repr,
            )
        )

    if (
        value is None
        or type(value)
        in {
            str,
            bool,
            int,
            float,
        }
    ):
        return value

    raise TypeError(
        "unsupported persisted audit snapshot value: "
        f"{type(value).__name__}"
    )


def _freeze_mapping(
    value: object,
    name: str,
) -> Mapping[str, object]:
    if not isinstance(
        value,
        Mapping,
    ):
        raise TypeError(name)

    frozen = _freeze(value)

    if not isinstance(
        frozen,
        Mapping,
    ):
        raise TypeError(name)

    return frozen


def _thaw(
    value: object,
) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): _thaw(child)
            for key, child
            in value.items()
        }

    if isinstance(value, tuple):
        return [
            _thaw(item)
            for item in value
        ]

    return value


def _texts(
    value: object,
    name: str,
) -> tuple[str, ...]:
    if not isinstance(
        value,
        (tuple, list),
    ):
        raise TypeError(name)

    result = tuple(
        _text(
            item,
            f"{name} item",
        )
        for item in value
    )

    if len(result) != len(
        set(result)
    ):
        raise ValueError(name)

    return result


@dataclass(frozen=True, slots=True)
class Task9LiveDecisionAuditV1:
    audit_id: str
    official_run_id: str
    parent_cycle_id: str
    prediction_id: str
    observation_id: str

    underlying_symbol: str
    exchange: str
    evaluated_at: datetime

    disposition: str
    first_causal_blocker: str | None

    prediction_action: str | None
    prediction_direction: str | None
    prediction_eligibility: str | None

    evaluation_present: bool
    trade_planner_reached: bool
    entry_observation_present: bool

    prediction_blockers: tuple[str, ...] = ()
    provider_incident_ids: tuple[str, ...] = ()
    failure_diagnostic: Mapping[str, object] | None = None

    evaluation_snapshot: Mapping[
        str,
        object,
    ] = field(
        default_factory=dict
    )

    selected_planning_snapshot: (
        Mapping[str, object] | None
    ) = None

    execution_mode: str = "PAPER"
    broker_order_submission: bool = False
    live_execution_eligible: bool = False

    schema_version: str = (
        "task9_live_decision_audit.v1"
    )

    def __post_init__(
        self,
    ) -> None:
        for name in (
            "audit_id",
            "official_run_id",
            "parent_cycle_id",
            "prediction_id",
            "observation_id",
            "underlying_symbol",
            "exchange",
        ):
            object.__setattr__(
                self,
                name,
                _text(
                    getattr(self, name),
                    name,
                ),
            )

        if (
            self.underlying_symbol,
            self.exchange,
        ) not in _MARKETS:
            raise ValueError(
                "market identity"
            )

        _aware(
            self.evaluated_at,
            "evaluated_at",
        )

        disposition = _text(
            self.disposition,
            "disposition",
        ).upper()

        if disposition not in _DISPOSITIONS:
            raise ValueError(
                "disposition"
            )

        object.__setattr__(
            self,
            "disposition",
            disposition,
        )

        object.__setattr__(
            self,
            "first_causal_blocker",
            _optional_text(
                self.first_causal_blocker,
                "first_causal_blocker",
            ),
        )

        for name in (
            "prediction_action",
            "prediction_direction",
            "prediction_eligibility",
        ):
            object.__setattr__(
                self,
                name,
                _optional_text(
                    getattr(self, name),
                    name,
                ),
            )

        for name in (
            "evaluation_present",
            "trade_planner_reached",
            "entry_observation_present",
        ):
            if (
                type(
                    getattr(self, name)
                )
                is not bool
            ):
                raise TypeError(name)

        object.__setattr__(
            self,
            "prediction_blockers",
            _texts(
                self.prediction_blockers,
                "prediction_blockers",
            ),
        )

        object.__setattr__(
            self,
            "provider_incident_ids",
            _texts(
                self.provider_incident_ids,
                "provider_incident_ids",
            ),
        )
        if self.failure_diagnostic is not None:
            diagnostic = _freeze_mapping(self.failure_diagnostic, "failure_diagnostic")
            if set(diagnostic) != {"failure_stage", "exception_class", "stable_failure_code"} or any(type(value) is not str or not value for value in diagnostic.values()):
                raise ValueError("failure_diagnostic")
            object.__setattr__(self, "failure_diagnostic", diagnostic)

        snapshot = _freeze_mapping(
            self.evaluation_snapshot,
            "evaluation_snapshot",
        )

        object.__setattr__(
            self,
            "evaluation_snapshot",
            snapshot,
        )

        if (
            self.evaluation_present
            and not snapshot
        ):
            raise ValueError(
                "evaluation_present requires snapshot"
            )

        if (
            not self.evaluation_present
            and snapshot
        ):
            raise ValueError(
                "missing evaluation cannot have snapshot"
            )

        planning = (
            self.selected_planning_snapshot
        )

        if planning is not None:
            planning = _freeze_mapping(
                planning,
                "selected_planning_snapshot",
            )

        object.__setattr__(
            self,
            "selected_planning_snapshot",
            planning,
        )

        if (
            self.trade_planner_reached
            != (planning is not None)
        ):
            raise ValueError(
                "trade planner snapshot state"
            )

        if (
            self.execution_mode != "PAPER"
            or self.broker_order_submission
            is not False
            or self.live_execution_eligible
            is not False
        ):
            raise ValueError(
                "Task 9 decision audit must remain PAPER-only"
            )

        if (
            self.schema_version
            != "task9_live_decision_audit.v1"
        ):
            raise ValueError(
                "schema_version"
            )

    def to_dict(
        self,
    ) -> dict[str, object]:
        return {
            "schema_version":
                self.schema_version,
            "audit_id":
                self.audit_id,
            "official_run_id":
                self.official_run_id,
            "parent_cycle_id":
                self.parent_cycle_id,
            "prediction_id":
                self.prediction_id,
            "observation_id":
                self.observation_id,
            "underlying_symbol":
                self.underlying_symbol,
            "exchange":
                self.exchange,
            "evaluated_at":
                self.evaluated_at.isoformat(),
            "disposition":
                self.disposition,
            "first_causal_blocker":
                self.first_causal_blocker,
            "prediction_action":
                self.prediction_action,
            "prediction_direction":
                self.prediction_direction,
            "prediction_eligibility":
                self.prediction_eligibility,
            "evaluation_present":
                self.evaluation_present,
            "trade_planner_reached":
                self.trade_planner_reached,
            "entry_observation_present":
                self.entry_observation_present,
            "prediction_blockers":
                list(
                    self.prediction_blockers
                ),
            "provider_incident_ids":
                list(
                    self.provider_incident_ids
            ),
            "failure_diagnostic": None if self.failure_diagnostic is None else _thaw(self.failure_diagnostic),
            "evaluation_snapshot":
                _thaw(
                    self.evaluation_snapshot
                ),
            "selected_planning_snapshot":
                (
                    None
                    if self.selected_planning_snapshot
                    is None
                    else _thaw(
                        self.selected_planning_snapshot
                    )
                ),
            "execution_mode":
                self.execution_mode,
            "broker_order_submission":
                self.broker_order_submission,
            "live_execution_eligible":
                self.live_execution_eligible,
        }


def task9_live_decision_audit_from_dict(
    value: Mapping[str, object],
) -> Task9LiveDecisionAuditV1:
    if not isinstance(
        value,
        Mapping,
    ):
        raise TypeError(
            "Task 9 live decision audit"
        )

    evaluated_at = datetime.fromisoformat(
        str(
            value.get(
                "evaluated_at"
            )
        )
    )

    evaluation_snapshot = value.get(
        "evaluation_snapshot"
    )

    if not isinstance(
        evaluation_snapshot,
        Mapping,
    ):
        raise ValueError(
            "evaluation_snapshot"
        )

    selected_planning = value.get(
        "selected_planning_snapshot"
    )

    if (
        selected_planning is not None
        and not isinstance(
            selected_planning,
            Mapping,
        )
    ):
        raise ValueError(
            "selected_planning_snapshot"
        )

    prediction_blockers = value.get(
        "prediction_blockers"
    )

    provider_incident_ids = value.get(
        "provider_incident_ids"
    )
    failure_diagnostic = value.get("failure_diagnostic")

    if not isinstance(
        prediction_blockers,
        list,
    ):
        raise ValueError(
            "prediction_blockers"
        )

    if not isinstance(
        provider_incident_ids,
        list,
    ):
        raise ValueError(
            "provider_incident_ids"
        )
    if failure_diagnostic is not None and not isinstance(failure_diagnostic, Mapping):
        raise ValueError("failure_diagnostic")

    return Task9LiveDecisionAuditV1(
        audit_id=value.get(
            "audit_id"
        ),
        official_run_id=value.get(
            "official_run_id"
        ),
        parent_cycle_id=value.get(
            "parent_cycle_id"
        ),
        prediction_id=value.get(
            "prediction_id"
        ),
        observation_id=value.get(
            "observation_id"
        ),
        underlying_symbol=value.get(
            "underlying_symbol"
        ),
        exchange=value.get(
            "exchange"
        ),
        evaluated_at=evaluated_at,
        disposition=value.get(
            "disposition"
        ),
        first_causal_blocker=value.get(
            "first_causal_blocker"
        ),
        prediction_action=value.get(
            "prediction_action"
        ),
        prediction_direction=value.get(
            "prediction_direction"
        ),
        prediction_eligibility=value.get(
            "prediction_eligibility"
        ),
        evaluation_present=value.get(
            "evaluation_present"
        ),
        trade_planner_reached=value.get(
            "trade_planner_reached"
        ),
        entry_observation_present=value.get(
            "entry_observation_present"
        ),
        prediction_blockers=tuple(
            prediction_blockers
        ),
        provider_incident_ids=tuple(
            provider_incident_ids
        ),
        failure_diagnostic=failure_diagnostic,
        evaluation_snapshot=(
            evaluation_snapshot
        ),
        selected_planning_snapshot=(
            selected_planning
        ),
        execution_mode=value.get(
            "execution_mode"
        ),
        broker_order_submission=value.get(
            "broker_order_submission"
        ),
        live_execution_eligible=value.get(
            "live_execution_eligible"
        ),
        schema_version=value.get(
            "schema_version"
        ),
    )


__all__ = (
    "Task9LiveDecisionAuditV1",
    "task9_live_decision_audit_from_dict",
)
