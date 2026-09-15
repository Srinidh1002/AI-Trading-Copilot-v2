"""Read-only Task 9 decision observability projection."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(name)
    return value.strip()


def _optional_text(
    value: object,
    name: str,
) -> str | None:
    if value is None:
        return None
    return _text(value, name)


def _texts(
    values: object,
    name: str,
) -> tuple[str, ...]:
    if not isinstance(values, (tuple, list)):
        raise TypeError(name)

    result = tuple(
        _text(item, f"{name} item")
        for item in values
    )

    if len(result) != len(set(result)):
        raise ValueError(name)

    return result


def _optional_number(
    value: object,
    name: str,
) -> float | None:
    if value is None:
        return None

    if (
        type(value) not in (int, float)
        or isinstance(value, bool)
        or not isfinite(float(value))
    ):
        raise ValueError(name)

    return float(value)


def _optional_int(
    value: object,
    name: str,
) -> int | None:
    if value is None:
        return None

    if type(value) is not int or isinstance(value, bool):
        raise ValueError(name)

    return value


@dataclass(frozen=True, slots=True)
class Task9ProviderParticipationV1:
    capability: str
    selected: bool
    called: bool
    used: bool
    available: bool | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "capability",
            _text(self.capability, "capability"),
        )

        for name in ("selected", "called", "used"):
            if type(getattr(self, name)) is not bool:
                raise TypeError(name)

        if (
            self.available is not None
            and type(self.available) is not bool
        ):
            raise TypeError("available")

        object.__setattr__(
            self,
            "reason",
            _optional_text(self.reason, "reason"),
        )

        if self.called and not self.selected:
            raise ValueError(
                "called provider must have been selected"
            )

        if self.used and not self.called:
            raise ValueError(
                "used provider must have been called"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "capability": self.capability,
            "selected": self.selected,
            "called": self.called,
            "used": self.used,
            "available": self.available,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class Task9DecisionObservabilityV1:
    audit_id: str
    parent_cycle_id: str
    prediction_id: str
    market: str
    exchange: str

    action: str | None
    direction: str | None
    eligibility: str | None

    first_causal_blocker: str | None
    concurrent_blockers: tuple[str, ...]
    decision_reasons: tuple[str, ...]

    actual_confidence: float | None
    required_confidence: float | None
    confidence_margin: float | None

    supporting_family_count: int | None
    required_family_count: int | None
    family_margin: int | None
    supporting_families: tuple[str, ...]
    opposing_families: tuple[str, ...]

    candidate_reached: bool
    ranking_reached: bool
    planning_reached: bool
    capital_authority_reached: bool
    paper_entry_reached: bool

    capital_status: str | None = None
    available_capital: float | None = None
    estimated_one_lot_premium_cost: float | None = None
    estimated_total_capital_requirement: float | None = None
    planned_lot_count: int | None = None
    planned_quantity: int | None = None
    capital_blockers: tuple[str, ...] = ()
    capital_reasons: tuple[str, ...] = ()

    provider_participation: tuple[
        Task9ProviderParticipationV1,
        ...
    ] = ()

    execution_mode: str = "PAPER"
    broker_order_submission: bool = False
    live_execution_eligible: bool = False

    schema_version: str = (
        "task9_decision_observability.v1"
    )

    def __post_init__(self) -> None:
        for name in (
            "audit_id",
            "parent_cycle_id",
            "prediction_id",
            "market",
            "exchange",
        ):
            object.__setattr__(
                self,
                name,
                _text(getattr(self, name), name),
            )

        if (
            self.market,
            self.exchange,
        ) not in {
            ("NIFTY", "NSE"),
            ("SENSEX", "BSE"),
        }:
            raise ValueError("market identity")

        for name in (
            "action",
            "direction",
            "eligibility",
            "first_causal_blocker",
            "capital_status",
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
            "concurrent_blockers",
            "decision_reasons",
            "supporting_families",
            "opposing_families",
            "capital_blockers",
            "capital_reasons",
        ):
            object.__setattr__(
                self,
                name,
                _texts(
                    getattr(self, name),
                    name,
                ),
            )

        for name in (
            "actual_confidence",
            "required_confidence",
            "confidence_margin",
            "available_capital",
            "estimated_one_lot_premium_cost",
            "estimated_total_capital_requirement",
        ):
            object.__setattr__(
                self,
                name,
                _optional_number(
                    getattr(self, name),
                    name,
                ),
            )

        for name in (
            "supporting_family_count",
            "required_family_count",
            "family_margin",
            "planned_lot_count",
            "planned_quantity",
        ):
            object.__setattr__(
                self,
                name,
                _optional_int(
                    getattr(self, name),
                    name,
                ),
            )

        for name in (
            "candidate_reached",
            "ranking_reached",
            "planning_reached",
            "capital_authority_reached",
            "paper_entry_reached",
        ):
            if type(getattr(self, name)) is not bool:
                raise TypeError(name)

        if not isinstance(
            self.provider_participation,
            tuple,
        ):
            raise TypeError("provider_participation")

        if any(
            type(item)
            is not Task9ProviderParticipationV1
            for item in self.provider_participation
        ):
            raise TypeError("provider_participation item")

        if (
            self.actual_confidence is None
        ) != (
            self.required_confidence is None
        ):
            raise ValueError(
                "confidence threshold pair"
            )

        expected_confidence_margin = (
            None
            if self.actual_confidence is None
            else (
                self.actual_confidence
                - self.required_confidence
            )
        )

        if (
            expected_confidence_margin is None
            and self.confidence_margin is not None
        ):
            raise ValueError("confidence_margin")

        if (
            expected_confidence_margin is not None
            and (
                self.confidence_margin is None
                or abs(
                    self.confidence_margin
                    - expected_confidence_margin
                ) > 1e-9
            )
        ):
            raise ValueError("confidence_margin")

        if (
            self.supporting_family_count is None
        ) != (
            self.required_family_count is None
        ):
            raise ValueError("family threshold pair")

        expected_family_margin = (
            None
            if self.supporting_family_count is None
            else (
                self.supporting_family_count
                - self.required_family_count
            )
        )

        if self.family_margin != expected_family_margin:
            raise ValueError("family_margin")

        if (
            self.supporting_family_count is not None
            and self.supporting_family_count
            != len(self.supporting_families)
        ):
            raise ValueError(
                "supporting_family_count"
            )

        if (
            not self.planning_reached
            and self.capital_authority_reached
        ):
            raise ValueError(
                "capital cannot precede planning"
            )

        if (
            not self.capital_authority_reached
            and (
                self.capital_status is not None
                or self.available_capital is not None
                or self.estimated_one_lot_premium_cost
                is not None
                or self.estimated_total_capital_requirement
                is not None
                or self.planned_lot_count is not None
                or self.planned_quantity is not None
                or self.capital_blockers
                or self.capital_reasons
            )
        ):
            raise ValueError(
                "capital diagnostics without authority reach"
            )

        if (
            self.execution_mode != "PAPER"
            or self.broker_order_submission is not False
            or self.live_execution_eligible is not False
        ):
            raise ValueError(
                "observability must remain PAPER-only"
            )

        if (
            self.schema_version
            != "task9_decision_observability.v1"
        ):
            raise ValueError("schema_version")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "audit_id": self.audit_id,
            "parent_cycle_id": self.parent_cycle_id,
            "prediction_id": self.prediction_id,
            "market": self.market,
            "exchange": self.exchange,
            "action": self.action,
            "direction": self.direction,
            "eligibility": self.eligibility,
            "first_causal_blocker":
                self.first_causal_blocker,
            "concurrent_blockers":
                list(self.concurrent_blockers),
            "decision_reasons":
                list(self.decision_reasons),
            "thresholds": {
                "actual_confidence":
                    self.actual_confidence,
                "required_confidence":
                    self.required_confidence,
                "confidence_margin":
                    self.confidence_margin,
                "supporting_family_count":
                    self.supporting_family_count,
                "required_family_count":
                    self.required_family_count,
                "family_margin":
                    self.family_margin,
                "supporting_families":
                    list(self.supporting_families),
                "opposing_families":
                    list(self.opposing_families),
            },
            "stage_reach": {
                "candidate_reached":
                    self.candidate_reached,
                "ranking_reached":
                    self.ranking_reached,
                "planning_reached":
                    self.planning_reached,
                "capital_authority_reached":
                    self.capital_authority_reached,
                "paper_entry_reached":
                    self.paper_entry_reached,
            },
            "capital": {
                "status": self.capital_status,
                "available_capital":
                    self.available_capital,
                "estimated_one_lot_premium_cost":
                    self.estimated_one_lot_premium_cost,
                "estimated_total_capital_requirement":
                    self.estimated_total_capital_requirement,
                "planned_lot_count":
                    self.planned_lot_count,
                "planned_quantity":
                    self.planned_quantity,
                "blockers":
                    list(self.capital_blockers),
                "reasons":
                    list(self.capital_reasons),
            },
            "provider_participation": [
                item.to_dict()
                for item in self.provider_participation
            ],
            "execution_mode": self.execution_mode,
            "broker_order_submission":
                self.broker_order_submission,
            "live_execution_eligible":
                self.live_execution_eligible,
        }


__all__ = (
    "Task9DecisionObservabilityV1",
    "Task9ProviderParticipationV1",
)
