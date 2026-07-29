from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping

from .integrated_three_target_trade_plan_result_v1 import (
    IntegratedThreeTargetTradePlanResultV1,
)
from .paper_market_observation_v1 import (
    PaperMarketObservationV1,
    _aware_datetime,
    _freeze_json_value,
    _nonblank_text,
    _plain_json_value,
)
from .paper_trade_lifecycle_policy_v1 import PaperTradeLifecyclePolicyV1
from .paper_trade_lifecycle_state_v1 import PaperTradeLifecycleStateV1


def _nested_attr(value: object, *path: str) -> Any:
    current = value
    for name in path:
        current = getattr(current, name)
    return current


@dataclass(frozen=True, slots=True)
class PaperTradeEntryEvaluationInputV1:
    integrated_trade_plan_result: IntegratedThreeTargetTradePlanResultV1
    lifecycle_policy: PaperTradeLifecyclePolicyV1
    lifecycle_state: PaperTradeLifecycleStateV1
    observation: PaperMarketObservationV1
    evaluation_timestamp: datetime
    requested_transition_id: str
    position_id: str
    entry_fill_id: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        exact_types = (
            (
                self.integrated_trade_plan_result,
                IntegratedThreeTargetTradePlanResultV1,
                "integrated_trade_plan_result",
            ),
            (self.lifecycle_policy, PaperTradeLifecyclePolicyV1, "lifecycle_policy"),
            (self.lifecycle_state, PaperTradeLifecycleStateV1, "lifecycle_state"),
            (self.observation, PaperMarketObservationV1, "observation"),
        )
        for value, expected_type, field_name in exact_types:
            if type(value) is not expected_type:
                raise TypeError(f"{field_name} must be an exact {expected_type.__name__}")

        plan = self.integrated_trade_plan_result
        policy = self.lifecycle_policy
        state = self.lifecycle_state
        observation = self.observation

        if plan.status != "READY":
            raise ValueError("integrated trade plan must be READY")
        if state.current_state not in {"PLANNED", "WAITING_FOR_ENTRY"}:
            raise ValueError("lifecycle source state is not entry-eligible")
        if state.is_terminal:
            raise ValueError("terminal lifecycle state is not entry-eligible")

        object.__setattr__(
            self,
            "evaluation_timestamp",
            _aware_datetime(self.evaluation_timestamp, "evaluation_timestamp"),
        )
        for field_name in (
            "requested_transition_id",
            "position_id",
            "entry_fill_id",
        ):
            object.__setattr__(
                self,
                field_name,
                _nonblank_text(getattr(self, field_name), field_name),
            )

        if getattr(plan, "execution_mode", "PAPER") != "PAPER":
            raise ValueError("integrated trade plan must be PAPER-only")
        if getattr(plan, "live_execution_eligible", False) is not False:
            raise ValueError("integrated trade plan must not be live eligible")
        if policy.execution_mode != "PAPER" or policy.live_execution_eligible is not False:
            raise ValueError("lifecycle policy must be PAPER-only")
        if state.execution_mode != "PAPER" or state.live_execution_eligible is not False:
            raise ValueError("lifecycle state must be PAPER-only")
        if (
            observation.execution_mode != "PAPER"
            or observation.live_execution_eligible is not False
        ):
            raise ValueError("observation must be PAPER-only")

        integration_id = _nonblank_text(plan.integration_id, "plan.integration_id")
        trade_plan_id = _nonblank_text(
            _nested_attr(plan, "capital_quantity_result", "trade_plan_id"),
            "plan.trade_plan_id",
        )
        selected_contract = _nested_attr(
            plan,
            "option_contract_selection_result",
            "selected_contract",
            "contract",
        )
        selected_contract_id = _nonblank_text(
            selected_contract.contract_id,
            "selected_contract.contract_id",
        )

        coherence_checks = (
            (
                "state.trade_plan_id",
                state.trade_plan_id,
                trade_plan_id,
            ),
            (
                "state.integrated_trade_plan_result_id",
                state.integrated_trade_plan_result_id,
                integration_id,
            ),
            (
                "state.lifecycle_policy_id",
                state.lifecycle_policy_id,
                policy.lifecycle_policy_id,
            ),
            (
                "observation.trade_plan_id",
                observation.trade_plan_id,
                trade_plan_id,
            ),
            (
                "observation.integrated_trade_plan_result_id",
                observation.integrated_trade_plan_result_id,
                integration_id,
            ),
            (
                "observation.selected_option_contract_id",
                observation.selected_option_contract_id,
                selected_contract_id,
            ),
        )
        for label, actual, expected in coherence_checks:
            if actual != expected:
                raise ValueError(f"{label} identity mismatch")

        # P6H OptionContractV1 is the exact authority for the selected trading
        # symbol and underlying identity; P6J itself deliberately has no
        # guessed market/underlying aliases.
        if observation.option_symbol != selected_contract.trading_symbol:
            raise ValueError("observation option_symbol mismatch")
        if observation.underlying_symbol != selected_contract.underlying_symbol:
            raise ValueError("observation underlying_symbol mismatch")

        object.__setattr__(
            self,
            "metadata",
            _freeze_json_value(self.metadata),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "integrated_trade_plan_result": self.integrated_trade_plan_result.to_dict(),
            "lifecycle_policy": self.lifecycle_policy.to_dict(),
            "lifecycle_state": self.lifecycle_state.to_dict(),
            "observation": self.observation.to_dict(),
            "evaluation_timestamp": self.evaluation_timestamp.isoformat(),
            "requested_transition_id": self.requested_transition_id,
            "position_id": self.position_id,
            "entry_fill_id": self.entry_fill_id,
            "metadata": _plain_json_value(self.metadata),
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "integrated_trade_plan_result": (
                self.integrated_trade_plan_result.semantic_dict()
            ),
            "lifecycle_policy": self.lifecycle_policy.semantic_dict(),
            "lifecycle_state": self.lifecycle_state.semantic_dict(),
            "observation": self.observation.semantic_dict(),
            "position_id": self.position_id,
            "metadata": _plain_json_value(self.metadata),
        }
