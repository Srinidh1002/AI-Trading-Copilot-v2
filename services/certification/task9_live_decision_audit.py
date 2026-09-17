"""Projection and durable store for Task 9 live decision diagnostics."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
import json
import math
import os
from pathlib import Path

from services.analysis.live_market_candidate_evaluator import (
    LiveMarketCandidateEvaluationResultV1,
)
from services.contracts.task9_live_decision_audit_v1 import (
    Task9LiveDecisionAuditV1,
    task9_live_decision_audit_from_dict,
)


_DERIVED_PARENT_BLOCKERS = {
    "NO_ELIGIBLE_MARKET",
}


def _unique_texts(
    values,
) -> tuple[str, ...]:
    result = []

    for value in values or ():
        if (
            type(value) is not str
            or not value.strip()
        ):
            continue

        normalized = value.strip()

        if normalized not in result:
            result.append(
                normalized
            )

    return tuple(result)


def _json_snapshot(
    value: object,
) -> object:
    if isinstance(value, Enum):
        return _json_snapshot(
            value.value
        )

    if isinstance(value, datetime):
        if (
            value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError(
                "audit datetime must be aware"
            )

        return value.isoformat()

    if isinstance(value, (date, time)):
        return value.isoformat()

    if isinstance(value, Decimal):
        return str(value)

    if value is None:
        return None

    if type(value) is bool:
        return value

    if type(value) is int:
        return value

    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError(
                "non-finite audit float"
            )

        return value

    if type(value) is str:
        return value

    if isinstance(value, Mapping):
        result = {}

        for key, child in sorted(
            value.items(),
            key=lambda item: str(item[0]),
        ):
            normalized_key = str(key)

            if normalized_key in result:
                raise ValueError(
                    "audit mapping key collision"
                )

            result[normalized_key] = (
                _json_snapshot(child)
            )

        return result

    if isinstance(
        value,
        (tuple, list),
    ):
        return [
            _json_snapshot(item)
            for item in value
        ]

    if isinstance(
        value,
        (set, frozenset),
    ):
        rendered = [
            _json_snapshot(item)
            for item in value
        ]

        return sorted(
            rendered,
            key=lambda item: json.dumps(
                item,
                sort_keys=True,
                separators=(",", ":"),
            ),
        )

    to_dict = getattr(
        value,
        "to_dict",
        None,
    )

    if callable(to_dict):
        return _json_snapshot(
            to_dict()
        )

    if is_dataclass(value):
        result = {
            "__type__":
                type(value).__name__,
        }

        for field in fields(value):
            result[field.name] = (
                _json_snapshot(
                    getattr(
                        value,
                        field.name,
                    )
                )
            )

        return result

    raise TypeError(
        "unsupported typed audit projection value: "
        f"{type(value).__module__}."
        f"{type(value).__name__}"
    )


def _evaluation_snapshot(
    evaluation: (
        LiveMarketCandidateEvaluationResultV1
        | None
    ),
) -> dict[str, object]:
    if evaluation is None:
        return {}

    if type(evaluation) is not (
        LiveMarketCandidateEvaluationResultV1
    ):
        raise TypeError(
            "evaluation"
        )

    if not is_dataclass(
        evaluation
    ):
        raise TypeError(
            "typed evaluation must be dataclass"
        )

    result = {
        "__type__":
            type(evaluation).__name__,
    }

    # Deliberately omit the raw captured observation. The immutable
    # decision/evidence/policy objects remain, avoiding duplicate raw
    # market payload persistence.
    for field in fields(evaluation):
        if field.name == "observation":
            continue

        result[field.name] = (
            _json_snapshot(
                getattr(
                    evaluation,
                    field.name,
                )
            )
        )

    return result


def _optional_snapshot(
    value: object,
) -> (
    dict[str, object] | None
):
    if value is None:
        return None

    rendered = _json_snapshot(
        value
    )

    if not isinstance(
        rendered,
        dict,
    ):
        raise TypeError(
            "selected planning audit snapshot"
        )

    return rendered


def _first_causal_blocker(
    blockers: tuple[str, ...],
) -> str | None:
    for blocker in blockers:
        if blocker.startswith(
            "EVIDENCE_UNAVAILABLE_"
        ):
            return blocker

    if "REGIME_BLOCKED" in blockers:
        return "REGIME_BLOCKED"

    for blocker in blockers:
        if (
            blocker
            not in _DERIVED_PARENT_BLOCKERS
        ):
            return blocker

    if blockers:
        return blockers[0]

    return None


def _disposition(
    *,
    blockers: tuple[str, ...],
    action: str | None,
    eligibility: str | None,
) -> str:
    if any(
        blocker.startswith(
            "EVIDENCE_UNAVAILABLE_"
        )
        for blocker in blockers
    ):
        return "EVIDENCE_UNAVAILABLE"

    if "REGIME_BLOCKED" in blockers:
        return "POLICY_ABSTENTION"

    normalized_action = (
        action.strip().upper()
        if type(action) is str
        and action.strip()
        else None
    )

    normalized_eligibility = (
        eligibility.strip().upper()
        if type(eligibility) is str
        and eligibility.strip()
        else None
    )

    if (
        normalized_action
        in {"CALL", "PUT"}
        and normalized_eligibility
        == "ELIGIBLE"
    ):
        return "ENTRY_ELIGIBLE"

    if normalized_action in {
        "WAIT",
        "NO_TRADE",
    }:
        return "POLICY_ABSTENTION"

    return "OTHER_INELIGIBLE"


def build_task9_live_decision_audit(
    *,
    audit_id: str,
    official_run_id: str,
    parent_cycle_id: str,
    prediction_id: str,
    observation_id: str,
    underlying_symbol: str,
    exchange: str,
    evaluated_at: datetime,
    evaluation: (
        LiveMarketCandidateEvaluationResultV1
        | None
    ),
    prediction_action: str | None,
    prediction_direction: str | None,
    prediction_eligibility: str | None,
    prediction_blockers=(),
    selected_planning=None,
    paper_observation=None,
    provider_incident_ids=(),
    failure_diagnostic=None,
) -> Task9LiveDecisionAuditV1:
    candidate = (
        None
        if evaluation is None
        else evaluation.candidate
    )

    pre_entry = (
        None
        if evaluation is None
        else evaluation.pre_entry_action
    )

    candidate_blockers = (
        ()
        if candidate is None
        else getattr(
            candidate,
            "blockers",
            (),
        )
    )

    pre_entry_blockers = (
        ()
        if pre_entry is None
        else getattr(
            pre_entry,
            "blockers",
            (),
        )
    )

    persisted_blockers = _unique_texts(
        prediction_blockers
    )

    evaluation_blockers = _unique_texts(
        (
            *pre_entry_blockers,
            *candidate_blockers,
        )
    )

    # The persisted PredictionRecord blocker projection is the primary
    # causal authority. Candidate/pre-entry blockers contain richer internal
    # diagnostics, including optional unavailable evidence such as Greeks,
    # and must not automatically become the first causal blocker.
    persisted_has_causal_blocker = any(
        blocker not in _DERIVED_PARENT_BLOCKERS
        for blocker in persisted_blockers
    )

    causal_blockers = (
        persisted_blockers
        if persisted_has_causal_blocker
        else _unique_texts(
            (
                *persisted_blockers,
                *evaluation_blockers,
            )
        )
    )

    action = prediction_action

    if (
        action is None
        and pre_entry is not None
    ):
        action = getattr(
            pre_entry,
            "action",
            None,
        )

    direction = prediction_direction

    if (
        direction is None
        and candidate is not None
    ):
        direction = getattr(
            candidate,
            "direction",
            None,
        )

    eligibility = (
        prediction_eligibility
    )

    if (
        eligibility is None
        and candidate is not None
    ):
        eligibility = getattr(
            candidate,
            "eligibility",
            None,
        )

    if (
        evaluation is None
        and not any(
            blocker.startswith(
                "EVIDENCE_UNAVAILABLE_"
            )
            for blocker in causal_blockers
        )
    ):
        causal_blockers = _unique_texts(
            (
                "EVIDENCE_UNAVAILABLE_EVALUATION",
                *causal_blockers,
            )
        )

    return Task9LiveDecisionAuditV1(
        audit_id=audit_id,
        official_run_id=official_run_id,
        parent_cycle_id=parent_cycle_id,
        prediction_id=prediction_id,
        observation_id=observation_id,
        underlying_symbol=underlying_symbol,
        exchange=exchange,
        evaluated_at=evaluated_at,
        disposition=_disposition(
            blockers=causal_blockers,
            action=action,
            eligibility=eligibility,
        ),
        first_causal_blocker=(
            _first_causal_blocker(
                causal_blockers
            )
        ),
        prediction_action=action,
        prediction_direction=direction,
        prediction_eligibility=eligibility,
        evaluation_present=(
            evaluation is not None
        ),
        trade_planner_reached=(
            selected_planning is not None
        ),
        entry_observation_present=(
            paper_observation is not None
        ),
        prediction_blockers=persisted_blockers,
        provider_incident_ids=(
            _unique_texts(
                provider_incident_ids
            )
        ),
        failure_diagnostic=failure_diagnostic,
        evaluation_snapshot=(
            _evaluation_snapshot(
                evaluation
            )
        ),
        selected_planning_snapshot=(
            _optional_snapshot(
                selected_planning
            )
        ),
    )


class Task9LiveDecisionAuditStore:
    def __init__(
        self,
        file_path: str | Path,
    ):
        self.file_path = Path(
            file_path
        )

    @staticmethod
    def _empty():
        return {
            "version": 1,
            "records": {},
        }

    def _read(
        self,
    ) -> dict[str, object]:
        if not self.file_path.exists():
            return self._empty()

        try:
            value = json.loads(
                self.file_path.read_text(
                    encoding="utf-8"
                )
            )
        except (
            OSError,
            json.JSONDecodeError,
        ) as exc:
            raise ValueError(
                "invalid Task 9 live decision audit store"
            ) from exc

        if (
            type(value) is not dict
            or set(value)
            != {
                "version",
                "records",
            }
            or value.get("version")
            != 1
            or type(
                value.get("records")
            )
            is not dict
        ):
            raise ValueError(
                "invalid Task 9 live decision audit store"
            )

        records = value[
            "records"
        ]

        for prediction_id, raw in records.items():
            if (
                type(prediction_id)
                is not str
                or not prediction_id
                or not isinstance(
                    raw,
                    Mapping,
                )
            ):
                raise ValueError(
                    "invalid Task 9 live decision audit record"
                )

            record = (
                task9_live_decision_audit_from_dict(
                    raw
                )
            )

            if (
                record.prediction_id
                != prediction_id
            ):
                raise ValueError(
                    "Task 9 decision audit identity"
                )

        return value

    def save(
        self,
        audit: Task9LiveDecisionAuditV1,
    ) -> str:
        if type(audit) is not (
            Task9LiveDecisionAuditV1
        ):
            raise TypeError("audit")

        document = self._read()
        records = document[
            "records"
        ]

        raw = audit.to_dict()

        existing = records.get(
            audit.prediction_id
        )

        if existing is not None:
            if existing != raw:
                raise ValueError(
                    "conflicting Task 9 live decision audit"
                )

            return (
                "DUPLICATE_SAME_PAYLOAD"
            )

        records[
            audit.prediction_id
        ] = raw

        self.file_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temp_path = (
            self.file_path.with_suffix(
                self.file_path.suffix
                + ".tmp"
            )
        )

        try:
            temp_path.write_text(
                json.dumps(
                    document,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                encoding="utf-8",
            )

            os.replace(
                temp_path,
                self.file_path,
            )
        finally:
            temp_path.unlink(
                missing_ok=True
            )

        return "SAVED"

    def recover(
        self,
        prediction_id: str,
    ) -> (
        Task9LiveDecisionAuditV1
        | None
    ):
        if (
            type(prediction_id)
            is not str
            or not prediction_id.strip()
        ):
            raise ValueError(
                "prediction_id"
            )

        raw = self._read()[
            "records"
        ].get(
            prediction_id
        )

        if raw is None:
            return None

        return (
            task9_live_decision_audit_from_dict(
                raw
            )
        )

    def list_all(
        self,
    ) -> tuple[
        Task9LiveDecisionAuditV1,
        ...,
    ]:
        return tuple(
            sorted(
                (
                    task9_live_decision_audit_from_dict(
                        raw
                    )
                    for raw
                    in self._read()[
                        "records"
                    ].values()
                ),
                key=lambda item: (
                    item.evaluated_at,
                    item.underlying_symbol,
                    item.prediction_id,
                ),
            )
        )


__all__ = (
    "Task9LiveDecisionAuditStore",
    "build_task9_live_decision_audit",
)
