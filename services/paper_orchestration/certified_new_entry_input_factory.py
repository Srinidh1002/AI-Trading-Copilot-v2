from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import datetime

from services.contracts.integrated_three_target_trade_plan_result_v1 import (
    IntegratedThreeTargetTradePlanResultV1,
)
from services.contracts.paper_market_observation_v1 import (
    PaperMarketObservationV1,
)
from services.contracts.paper_orchestration_cycle_input_v1 import (
    PaperOrchestrationCycleInputV1,
)
from services.contracts.paper_portfolio_policy_v1 import (
    PaperPortfolioPolicyV1,
)
from services.contracts.paper_trade_lifecycle_policy_v1 import (
    PaperTradeLifecyclePolicyV1,
)
from services.paper_orchestration.new_entry_paper_lifecycle_executor import (
    NewEntryPaperLifecycleInputV1,
)


PortfolioPolicyProvider = Callable[
    [PaperOrchestrationCycleInputV1, IntegratedThreeTargetTradePlanResultV1],
    PaperPortfolioPolicyV1,
]
LifecyclePolicyProvider = Callable[
    [PaperOrchestrationCycleInputV1, IntegratedThreeTargetTradePlanResultV1],
    PaperTradeLifecyclePolicyV1,
]
ObservationProvider = Callable[
    [PaperOrchestrationCycleInputV1, IntegratedThreeTargetTradePlanResultV1],
    PaperMarketObservationV1,
]


def _identity(namespace: str, *parts: object) -> str:
    payload = "|".join((namespace, *(str(part).strip() for part in parts)))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"{namespace}-{digest}"


def _positive(value: object, name: str) -> float:
    if isinstance(value, bool) or type(value) not in (int, float):
        raise TypeError(f"{name} must be numeric")
    result = float(value)
    if result <= 0:
        raise ValueError(f"{name} must be positive")
    return result


class CertifiedNewEntryInputFactory:
    """Build the exact P6→P8→P7 new-entry lifecycle input.

    Policies and observations are injected as exact typed authorities. No
    arbitrary dictionaries, broker methods, or live execution switches are
    accepted.
    """

    def __init__(
        self,
        *,
        portfolio_id: str,
        starting_capital: float,
        portfolio_policy_provider: PortfolioPolicyProvider,
        lifecycle_policy_provider: LifecyclePolicyProvider,
        observation_provider: ObservationProvider,
    ) -> None:
        if type(portfolio_id) is not str or not portfolio_id.strip():
            raise ValueError("portfolio_id must be non-empty")
        if not callable(portfolio_policy_provider):
            raise TypeError("portfolio_policy_provider must be callable")
        if not callable(lifecycle_policy_provider):
            raise TypeError("lifecycle_policy_provider must be callable")
        if not callable(observation_provider):
            raise TypeError("observation_provider must be callable")

        self.portfolio_id = portfolio_id.strip()
        self.starting_capital = _positive(starting_capital, "starting_capital")
        self.portfolio_policy_provider = portfolio_policy_provider
        self.lifecycle_policy_provider = lifecycle_policy_provider
        self.observation_provider = observation_provider

    def __call__(
        self,
        cycle_input: PaperOrchestrationCycleInputV1,
        integrated_trade_plan_result: IntegratedThreeTargetTradePlanResultV1,
    ) -> NewEntryPaperLifecycleInputV1:
        if type(cycle_input) is not PaperOrchestrationCycleInputV1:
            raise TypeError(
                "cycle_input must be exact PaperOrchestrationCycleInputV1"
            )
        if type(integrated_trade_plan_result) is not IntegratedThreeTargetTradePlanResultV1:
            raise TypeError(
                "integrated_trade_plan_result must be exact "
                "IntegratedThreeTargetTradePlanResultV1"
            )
        if integrated_trade_plan_result.status != "READY":
            raise ValueError("integrated trade plan must be READY")
        if integrated_trade_plan_result.execution_mode != "PAPER":
            raise ValueError("integrated trade plan must be PAPER-only")
        if integrated_trade_plan_result.live_execution_eligible is not False:
            raise ValueError("integrated trade plan cannot be live eligible")
        if integrated_trade_plan_result.integration_id != cycle_input.p6_integration_id:
            raise ValueError("P6 integration identity mismatch")

        canonical = integrated_trade_plan_result.canonical_trade_plan_input
        expected_identity = (
            cycle_input.underlying_symbol,
            cycle_input.exchange,
        )
        actual_identity = (
            canonical.underlying_symbol,
            canonical.exchange,
        )
        if actual_identity != expected_identity:
            raise ValueError("integrated plan/cycle market identity mismatch")

        portfolio_policy = self.portfolio_policy_provider(
            cycle_input,
            integrated_trade_plan_result,
        )
        lifecycle_policy = self.lifecycle_policy_provider(
            cycle_input,
            integrated_trade_plan_result,
        )
        observation = self.observation_provider(
            cycle_input,
            integrated_trade_plan_result,
        )

        if type(portfolio_policy) is not PaperPortfolioPolicyV1:
            raise TypeError(
                "portfolio_policy_provider must return exact PaperPortfolioPolicyV1"
            )
        if type(lifecycle_policy) is not PaperTradeLifecyclePolicyV1:
            raise TypeError(
                "lifecycle_policy_provider must return exact "
                "PaperTradeLifecyclePolicyV1"
            )
        if type(observation) is not PaperMarketObservationV1:
            raise TypeError(
                "observation_provider must return exact PaperMarketObservationV1"
            )

        observation_identity = (
            getattr(observation, "underlying_symbol", None),
            getattr(observation, "exchange", None),
        )
        if observation_identity != expected_identity:
            raise ValueError("observation/cycle market identity mismatch")

        evaluated_at: datetime = cycle_input.cycle_requested_at
        basis = (
            cycle_input.cycle_id,
            cycle_input.cycle_idempotency_key,
            integrated_trade_plan_result.integration_id,
            self.portfolio_id,
            cycle_input.trading_day_id,
        )

        return NewEntryPaperLifecycleInputV1(
            portfolio_id=self.portfolio_id,
            initial_portfolio_snapshot_id=_identity(
                "portfolio-snapshot-initial",
                *basis,
            ),
            admission_result_id=_identity("admission-result", *basis),
            admission_request_id=cycle_input.p8_admission_request_id,
            admission_idempotency_key=(
                cycle_input.p8_admission_idempotency_key
            ),
            admission_portfolio_event_id=cycle_input.p8_portfolio_event_id,
            requested_reservation_id=_identity("reservation", *basis),
            paper_trade_id=_identity("paper-trade", *basis),
            paper_trade_adapter_idempotency_key=_identity(
                "paper-trade-key",
                *basis,
            ),
            initial_lifecycle_state_id=_identity(
                "lifecycle-state-initial",
                *basis,
            ),
            resulting_lifecycle_state_id=_identity(
                "lifecycle-state-result",
                *basis,
            ),
            requested_transition_id=cycle_input.p7_requested_transition_id,
            position_id=cycle_input.p7_position_id,
            entry_fill_id=cycle_input.p7_entry_fill_id,
            activation_result_snapshot_id=_identity(
                "portfolio-snapshot-activation",
                *basis,
            ),
            activation_portfolio_event_id=cycle_input.p8_update_event_id,
            activation_update_idempotency_key=(
                cycle_input.p8_update_idempotency_key
            ),
            trading_day_id=cycle_input.trading_day_id,
            starting_capital=self.starting_capital,
            evaluated_at=evaluated_at,
            integrated_trade_plan_result=integrated_trade_plan_result,
            portfolio_policy=portfolio_policy,
            lifecycle_policy=lifecycle_policy,
            observation=observation,
        )
