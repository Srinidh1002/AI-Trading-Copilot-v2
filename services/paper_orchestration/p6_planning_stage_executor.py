from __future__ import annotations

from dataclasses import dataclass

from services.contracts.capital_quantity_planning_input_v1 import (
    CapitalQuantityPlanningInputV1,
)
from services.contracts.entry_zone_evaluation_input_v1 import (
    EntryZoneEvaluationInputV1,
)
from services.contracts.integrated_three_target_trade_plan_input_v1 import (
    IntegratedThreeTargetTradePlanInputV1,
)
from services.contracts.integrated_three_target_trade_plan_result_v1 import (
    IntegratedThreeTargetTradePlanResultV1,
)
from services.contracts.option_contract_selection_input_v1 import (
    OptionContractSelectionInputV1,
)
from services.contracts.stop_loss_evaluation_input_v1 import (
    StopLossEvaluationInputV1,
)
from services.contracts.three_target_evaluation_input_v1 import (
    ThreeTargetEvaluationInputV1,
)
from services.contracts.trade_planning_policy_v1 import (
    TradePlanningPolicyV1,
)
from services.trade_planning.capital_quantity_planner import (
    plan_capital_quantity,
)
from services.trade_planning.entry_zone_evaluator import (
    evaluate_entry_zone,
)
from services.trade_planning.option_contract_selector import (
    select_option_contract,
)
from services.trade_planning.stop_loss_evaluator import (
    evaluate_stop_loss,
)
from services.trade_planning.three_target_evaluator import (
    evaluate_three_targets,
)
from services.trade_planning.three_target_trade_plan_integrator import (
    integrate_three_target_trade_plan,
)


@dataclass(frozen=True, slots=True)
class P6PlanningStageInputV1:
    integration_id: str
    planning_policy: TradePlanningPolicyV1
    option_selection_input: OptionContractSelectionInputV1
    entry_zone_input: EntryZoneEvaluationInputV1
    stop_loss_input: StopLossEvaluationInputV1
    three_target_input: ThreeTargetEvaluationInputV1
    capital_quantity_input: CapitalQuantityPlanningInputV1
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "p6_planning_stage_input.v1"

    def __post_init__(self) -> None:
        if type(self.integration_id) is not str or not self.integration_id.strip():
            raise ValueError("integration_id must be a non-empty string")
        object.__setattr__(self, "integration_id", self.integration_id.strip())

        exact = (
            (self.planning_policy, TradePlanningPolicyV1, "planning_policy"),
            (
                self.option_selection_input,
                OptionContractSelectionInputV1,
                "option_selection_input",
            ),
            (
                self.entry_zone_input,
                EntryZoneEvaluationInputV1,
                "entry_zone_input",
            ),
            (
                self.stop_loss_input,
                StopLossEvaluationInputV1,
                "stop_loss_input",
            ),
            (
                self.three_target_input,
                ThreeTargetEvaluationInputV1,
                "three_target_input",
            ),
            (
                self.capital_quantity_input,
                CapitalQuantityPlanningInputV1,
                "capital_quantity_input",
            ),
        )
        for value, expected, name in exact:
            if type(value) is not expected:
                raise TypeError(f"{name} must be an exact {expected.__name__}")

        policy_id = self.planning_policy.policy_id
        for value, name in (
            (self.option_selection_input.policy_id, "option_selection_input"),
            (self.entry_zone_input.policy_id, "entry_zone_input"),
            (self.stop_loss_input.policy_id, "stop_loss_input"),
            (self.three_target_input.policy_id, "three_target_input"),
        ):
            if value != policy_id:
                raise ValueError(f"{name} policy identity mismatch")

        canonical = self.capital_quantity_input.canonical_trade_plan_input
        identity = (
            canonical.underlying_symbol,
            canonical.exchange,
            canonical.direction,
        )
        for value, name in (
            (self.option_selection_input, "option_selection_input"),
            (self.entry_zone_input, "entry_zone_input"),
            (self.stop_loss_input, "stop_loss_input"),
            (self.three_target_input, "three_target_input"),
        ):
            candidate = (
                value.underlying_symbol,
                value.exchange,
                value.direction,
            )
            if candidate != identity:
                raise ValueError(f"{name} market identity mismatch")

        if self.execution_mode != "PAPER":
            raise ValueError("execution_mode must be PAPER")
        if self.live_execution_eligible:
            raise ValueError("live execution is not eligible")
        if self.schema_version != "p6_planning_stage_input.v1":
            raise ValueError("unsupported schema_version")


def execute_p6_planning_stage(
    stage_input: P6PlanningStageInputV1,
) -> IntegratedThreeTargetTradePlanResultV1:
    """Run the certified P6 planning authorities in deterministic order."""

    if type(stage_input) is not P6PlanningStageInputV1:
        raise TypeError(
            "stage_input must be an exact P6PlanningStageInputV1"
        )

    policy = stage_input.planning_policy
    canonical = (
        stage_input.capital_quantity_input.canonical_trade_plan_input
    )

    option_result = select_option_contract(
        stage_input.option_selection_input,
        policy,
    )
    entry_result = evaluate_entry_zone(
        stage_input.entry_zone_input,
        policy,
    )
    stop_result = evaluate_stop_loss(
        canonical,
        policy,
        entry_result,
        stage_input.stop_loss_input,
    )
    target_result = evaluate_three_targets(
        stage_input.three_target_input,
        policy,
    )

    capital_template = stage_input.capital_quantity_input
    capital_input = CapitalQuantityPlanningInputV1(
        planning_input_id=capital_template.planning_input_id,
        trade_plan_id=capital_template.trade_plan_id,
        policy_id=capital_template.policy_id,
        canonical_trade_plan_input=canonical,
        capital_quantity_policy=capital_template.capital_quantity_policy,
        entry_zone_result=entry_result,
        stop_loss_result=stop_result,
        three_target_result=target_result,
        option_contract_selection_result=option_result,
        trading_cost_policy=capital_template.trading_cost_policy,
        trading_cost_evidence=capital_template.trading_cost_evidence,
        caller_supplied_per_lot_risk_amount=(
            capital_template.caller_supplied_per_lot_risk_amount
        ),
        evaluated_at=capital_template.evaluated_at,
        input_source=capital_template.input_source,
        blockers=capital_template.blockers,
        warnings=capital_template.warnings,
        source_timestamps=capital_template.source_timestamps,
        metadata=capital_template.metadata,
    )
    capital_result = plan_capital_quantity(capital_input)

    integration_input = IntegratedThreeTargetTradePlanInputV1(
        integration_id=stage_input.integration_id,
        canonical_trade_plan_input=canonical,
        entry_zone_result=entry_result,
        stop_loss_result=stop_result,
        three_target_result=target_result,
        option_contract_selection_result=option_result,
        capital_quantity_result=capital_result,
    )
    return integrate_three_target_trade_plan(integration_input)
