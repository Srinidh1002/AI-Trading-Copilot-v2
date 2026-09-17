"""Deterministic typed fixtures for Task 7A replay scenarios."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import ClassVar

from services.certification.replay_scenario_catalogue import (
    build_replay_scenario_catalogue,
)
from services.contracts.active_paper_position_v1 import (
    ActivePaperPositionV1,
)
from services.contracts.paper_monitoring_lifecycle_v1 import (
    PaperMonitoringEvidenceV1,
)
from services.contracts.replay_certification_v1 import (
    ReplayScenarioV1,
)


@dataclass(frozen=True, slots=True)
class ReplayLifecycleFixtureV1:
    """Typed position and monitoring sequence for one replay scenario."""

    SCHEMA_VERSION: ClassVar[str] = "replay_lifecycle_fixture.v1"

    fixture_id: str
    scenario: ReplayScenarioV1
    initial_position: ActivePaperPositionV1 | None
    monitoring_evidence: tuple[PaperMonitoringEvidenceV1, ...]
    expected_outcome: str
    execution_mode: str = "PAPER"
    network_access_used: bool = False
    broker_submission_enabled: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if (
            type(self.fixture_id) is not str
            or not self.fixture_id.strip()
        ):
            raise ValueError("fixture_id")
        if type(self.scenario) is not ReplayScenarioV1:
            raise TypeError("scenario")
        if self.fixture_id != self.scenario.fixture_id:
            raise ValueError("fixture identity")
        if not isinstance(self.monitoring_evidence, tuple):
            raise TypeError("monitoring_evidence")
        if any(
            type(item) is not PaperMonitoringEvidenceV1
            for item in self.monitoring_evidence
        ):
            raise TypeError("monitoring_evidence")
        if self.initial_position is not None and type(
            self.initial_position
        ) is not ActivePaperPositionV1:
            raise TypeError("initial_position")
        if self.expected_outcome != self.scenario.expected_outcome:
            raise ValueError("expected_outcome")

        if self.expected_outcome == "CLOSED_TRADE":
            if self.initial_position is None:
                raise ValueError("closed replay requires position")
            if not self.monitoring_evidence:
                raise ValueError("closed replay requires evidence")
            if any(
                item.position_id
                != self.initial_position.position_id
                for item in self.monitoring_evidence
            ):
                raise ValueError("position identity")
        else:
            if self.initial_position is not None:
                raise ValueError("non-trade fixture cannot contain position")
            if self.monitoring_evidence:
                raise ValueError("non-trade fixture cannot contain evidence")

        if (
            self.execution_mode != "PAPER"
            or self.network_access_used is not False
            or self.broker_submission_enabled is not False
            or self.live_execution_eligible is not False
        ):
            raise ValueError("offline PAPER-only replay fixture")


def _contract_for(scenario: ReplayScenarioV1) -> str:
    symbol = scenario.market[0]
    right = (
        "CALL"
        if scenario.scenario_type
        not in {"TRENDING_DOWN", "FALSE_BREAKOUT"}
        else "PUT"
    )
    suffix = "C" if right == "CALL" else "P"
    strike = 25000 if symbol == "NIFTY" else 82000
    return f"{symbol}06AUG26{suffix}{strike}"


def _initial_position(
    scenario: ReplayScenarioV1,
) -> ActivePaperPositionV1:
    symbol, exchange = scenario.market
    right = (
        "PUT"
        if scenario.scenario_type
        in {"TRENDING_DOWN", "FALSE_BREAKOUT"}
        else "CALL"
    )
    strike = 25000.0 if symbol == "NIFTY" else 82000.0
    position_id = f"position-{scenario.scenario_id}"
    opened_at = scenario.replay_started_at
    updated_at = opened_at + timedelta(seconds=1)

    return ActivePaperPositionV1(
        position_id=position_id,
        recommendation_id=f"recommendation-{scenario.scenario_id}",
        reservation_result_id=f"reservation-{scenario.scenario_id}",
        fill_result_id=f"fill-{scenario.scenario_id}",
        opened_at=opened_at,
        updated_at=updated_at,
        underlying_symbol=symbol,
        exchange=exchange,
        option_right=right,
        contract=_contract_for(scenario),
        expiry="2026-08-06",
        strike=strike,
        entry_price=100.0,
        stop_loss=90.0,
        target_1=110.0,
        target_2=120.0,
        target_3=130.0,
        initial_lots=3,
        remaining_lots=3,
        lot_size=25,
        initial_quantity=75,
        remaining_quantity=75,
        reserved_capital=7600.0,
        maximum_loss=1000.0,
    )


def _evidence(
    scenario: ReplayScenarioV1,
    *,
    sequence: int,
    bid: float,
    confidence: float = 0.80,
    setup_valid: bool = True,
) -> PaperMonitoringEvidenceV1:
    observed_at = (
        scenario.replay_started_at
        + timedelta(seconds=sequence + 1)
    )
    return PaperMonitoringEvidenceV1(
        evidence_id=(
            f"evidence-{scenario.scenario_id}-{sequence}"
        ),
        position_id=f"position-{scenario.scenario_id}",
        observed_at=observed_at,
        current_bid=bid,
        current_ask=bid + 1.0,
        current_last=bid + 0.5,
        confidence=confidence,
        setup_valid=setup_valid,
    )


def _target_sequence(
    scenario: ReplayScenarioV1,
) -> tuple[PaperMonitoringEvidenceV1, ...]:
    return (
        _evidence(scenario, sequence=1, bid=105.0),
        _evidence(scenario, sequence=2, bid=110.0),
        _evidence(scenario, sequence=3, bid=120.0),
        _evidence(scenario, sequence=4, bid=130.0),
    )


def _stop_sequence(
    scenario: ReplayScenarioV1,
) -> tuple[PaperMonitoringEvidenceV1, ...]:
    return (
        _evidence(scenario, sequence=1, bid=103.0),
        _evidence(scenario, sequence=2, bid=89.0),
    )


def _early_exit_sequence(
    scenario: ReplayScenarioV1,
) -> tuple[PaperMonitoringEvidenceV1, ...]:
    return (
        _evidence(scenario, sequence=1, bid=104.0),
        _evidence(
            scenario,
            sequence=2,
            bid=101.0,
            confidence=0.35,
            setup_valid=False,
        ),
    )


def _partial_then_stop_sequence(
    scenario: ReplayScenarioV1,
) -> tuple[PaperMonitoringEvidenceV1, ...]:
    return (
        _evidence(scenario, sequence=1, bid=110.0),
        _evidence(scenario, sequence=2, bid=120.0),
        _evidence(scenario, sequence=3, bid=89.0),
    )


def _monitoring_sequence(
    scenario: ReplayScenarioV1,
) -> tuple[PaperMonitoringEvidenceV1, ...]:
    scenario_type = scenario.scenario_type

    if scenario_type in {
        "TRENDING_UP",
        "TRENDING_DOWN",
        "PARTIAL_EXITS",
        "ALL_TARGETS",
        "DUPLICATE_ENTRY",
        "RESTART_RECOVERY",
    }:
        return _target_sequence(scenario)

    if scenario_type in {
        "RANGE",
        "LOW_VOLATILITY",
        "FALSE_BREAKOUT",
        "STOP_HIT",
    }:
        return _stop_sequence(scenario)

    if scenario_type in {
        "HIGH_VOLATILITY",
        "GAP",
        "EARLY_SAFETY_EXIT",
    }:
        return _early_exit_sequence(scenario)

    if scenario_type == "REVERSAL":
        return _partial_then_stop_sequence(scenario)

    raise ValueError(
        f"unsupported closed-trade scenario: {scenario_type}"
    )


def build_replay_lifecycle_fixture(
    scenario: ReplayScenarioV1,
) -> ReplayLifecycleFixtureV1:
    """Build one deterministic fixture without network or broker access."""
    if type(scenario) is not ReplayScenarioV1:
        raise TypeError("scenario")

    if scenario.expected_outcome != "CLOSED_TRADE":
        return ReplayLifecycleFixtureV1(
            fixture_id=scenario.fixture_id,
            scenario=scenario,
            initial_position=None,
            monitoring_evidence=(),
            expected_outcome=scenario.expected_outcome,
        )

    return ReplayLifecycleFixtureV1(
        fixture_id=scenario.fixture_id,
        scenario=scenario,
        initial_position=_initial_position(scenario),
        monitoring_evidence=_monitoring_sequence(scenario),
        expected_outcome=scenario.expected_outcome,
    )


def build_replay_fixture_catalogue(
) -> tuple[ReplayLifecycleFixtureV1, ...]:
    return tuple(
        build_replay_lifecycle_fixture(scenario)
        for scenario in build_replay_scenario_catalogue()
    )
