"""Typed dashboard view for Task 9 decision observability."""

from __future__ import annotations

from dataclasses import dataclass

from services.contracts.task9_decision_observability_v1 import (
    Task9DecisionObservabilityV1,
)


@dataclass(frozen=True, slots=True)
class Task9DecisionObservabilityDashboardViewV1:
    market: str
    action: str
    direction: str
    eligibility: str

    first_blocker: str
    blocker_count: int

    confidence_text: str
    family_text: str

    candidate_reached: bool
    ranking_reached: bool
    planning_reached: bool
    capital_reached: bool
    paper_entry_reached: bool

    capital_status: str
    provider_summary: tuple[str, ...]

    decision_reasons: tuple[str, ...]
    blockers: tuple[str, ...]

    schema_version: str = (
        "task9_decision_observability_dashboard_view.v1"
    )

    def __post_init__(self) -> None:
        if type(self.market) is not str or not self.market:
            raise ValueError("market")

        for name in (
            "action",
            "direction",
            "eligibility",
            "first_blocker",
            "confidence_text",
            "family_text",
            "capital_status",
        ):
            value = getattr(self, name)

            if type(value) is not str or not value:
                raise ValueError(name)

        if type(self.blocker_count) is not int:
            raise TypeError("blocker_count")

        if self.blocker_count < 0:
            raise ValueError("blocker_count")

        for name in (
            "candidate_reached",
            "ranking_reached",
            "planning_reached",
            "capital_reached",
            "paper_entry_reached",
        ):
            if type(getattr(self, name)) is not bool:
                raise TypeError(name)

        for name in (
            "provider_summary",
            "decision_reasons",
            "blockers",
        ):
            value = getattr(self, name)

            if not isinstance(value, tuple):
                raise TypeError(name)

            if any(
                type(item) is not str or not item
                for item in value
            ):
                raise ValueError(name)

        if self.blocker_count != len(self.blockers):
            raise ValueError("blocker_count mismatch")

        if (
            self.schema_version
            != "task9_decision_observability_dashboard_view.v1"
        ):
            raise ValueError("schema_version")


def build_task9_decision_observability_dashboard_view(
    observability: Task9DecisionObservabilityV1,
) -> Task9DecisionObservabilityDashboardViewV1:
    if (
        type(observability)
        is not Task9DecisionObservabilityV1
    ):
        raise TypeError("observability")

    def _display(
        value: object,
    ) -> str:
        if value is None:
            return "Unavailable"

        return str(value)

    if (
        observability.actual_confidence is None
        or observability.required_confidence is None
        or observability.confidence_margin is None
    ):
        confidence_text = "Unavailable"
    else:
        confidence_text = (
            f"{observability.actual_confidence:.1f}"
            f" / {observability.required_confidence:.1f}"
            f" ({observability.confidence_margin:+.1f})"
        )

    if (
        observability.supporting_family_count is None
        or observability.required_family_count is None
        or observability.family_margin is None
    ):
        family_text = "Unavailable"
    else:
        family_text = (
            f"{observability.supporting_family_count}"
            f" / {observability.required_family_count}"
            f" ({observability.family_margin:+d})"
        )

    provider_summary = tuple(
        (
            f"{item.capability}: "
            f"selected={item.selected}, "
            f"called={item.called}, "
            f"used={item.used}, "
            f"available={_display(item.available)}, "
            f"reason={_display(item.reason)}"
        )
        for item in observability.provider_participation
    )

    return Task9DecisionObservabilityDashboardViewV1(
        market=observability.market,
        action=_display(observability.action),
        direction=_display(observability.direction),
        eligibility=_display(observability.eligibility),
        first_blocker=_display(
            observability.first_causal_blocker
        ),
        blocker_count=len(
            observability.concurrent_blockers
        ),
        confidence_text=confidence_text,
        family_text=family_text,
        candidate_reached=(
            observability.candidate_reached
        ),
        ranking_reached=(
            observability.ranking_reached
        ),
        planning_reached=(
            observability.planning_reached
        ),
        capital_reached=(
            observability.capital_authority_reached
        ),
        paper_entry_reached=(
            observability.paper_entry_reached
        ),
        capital_status=_display(
            observability.capital_status
        ),
        provider_summary=provider_summary,
        decision_reasons=(
            observability.decision_reasons
        ),
        blockers=(
            observability.concurrent_blockers
        ),
    )


__all__ = (
    "Task9DecisionObservabilityDashboardViewV1",
    "build_task9_decision_observability_dashboard_view",
)
