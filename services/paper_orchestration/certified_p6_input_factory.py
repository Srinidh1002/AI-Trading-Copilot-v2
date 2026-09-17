from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from services.contracts.capital_quantity_planning_input_v1 import (
    CapitalQuantityPlanningInputV1,
)
from services.contracts.entry_zone_evaluation_input_v1 import (
    EntryZoneEvaluationInputV1,
)
from services.contracts.option_contract_selection_input_v1 import (
    OptionContractSelectionInputV1,
)
from services.contracts.paper_orchestration_cycle_input_v1 import (
    PaperOrchestrationCycleInputV1,
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
from services.paper_orchestration.p6_planning_stage_executor import (
    P6PlanningStageInputV1,
)


@dataclass(frozen=True, slots=True)
class CertifiedP6InputBundleV1:
    planning_policy: TradePlanningPolicyV1
    option_selection_input: OptionContractSelectionInputV1
    entry_zone_input: EntryZoneEvaluationInputV1
    stop_loss_input: StopLossEvaluationInputV1
    three_target_input: ThreeTargetEvaluationInputV1
    capital_quantity_input: CapitalQuantityPlanningInputV1
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "certified_p6_input_bundle.v1"

    def __post_init__(self) -> None:
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
                raise TypeError(f"{name} must be exact {expected.__name__}")

        if self.execution_mode != "PAPER":
            raise ValueError("execution_mode must be PAPER")
        if self.live_execution_eligible:
            raise ValueError("live execution is not eligible")
        if self.schema_version != "certified_p6_input_bundle.v1":
            raise ValueError("unsupported schema_version")


TypedP6Builder = Callable[
    [PaperOrchestrationCycleInputV1, object, object],
    CertifiedP6InputBundleV1,
]


class CertifiedP6InputFactory:
    """Attach caller-built exact P5/P6 contracts to the P9 cycle identity.

    Legacy dictionaries are not converted here. The injected builder must
    produce exact certified P5/P6 contracts, preserving each domain authority.
    """

    def __init__(self, *, typed_input_builder: TypedP6Builder) -> None:
        if not callable(typed_input_builder):
            raise TypeError("typed_input_builder must be callable")
        self.typed_input_builder = typed_input_builder

    def __call__(
        self,
        cycle_input: PaperOrchestrationCycleInputV1,
        analysis_result: object,
        opportunity_result: object,
    ) -> P6PlanningStageInputV1:
        if type(cycle_input) is not PaperOrchestrationCycleInputV1:
            raise TypeError(
                "cycle_input must be exact PaperOrchestrationCycleInputV1"
            )

        bundle = self.typed_input_builder(
            cycle_input,
            analysis_result,
            opportunity_result,
        )
        if type(bundle) is not CertifiedP6InputBundleV1:
            raise TypeError(
                "typed_input_builder must return exact "
                "CertifiedP6InputBundleV1"
            )

        stage_input = P6PlanningStageInputV1(
            integration_id=cycle_input.p6_integration_id,
            planning_policy=bundle.planning_policy,
            option_selection_input=bundle.option_selection_input,
            entry_zone_input=bundle.entry_zone_input,
            stop_loss_input=bundle.stop_loss_input,
            three_target_input=bundle.three_target_input,
            capital_quantity_input=bundle.capital_quantity_input,
        )

        canonical = (
            stage_input.capital_quantity_input.canonical_trade_plan_input
        )
        expected_identity = (
            cycle_input.underlying_symbol,
            cycle_input.exchange,
        )
        actual_identity = (
            canonical.underlying_symbol,
            canonical.exchange,
        )
        if actual_identity != expected_identity:
            raise ValueError("P6 canonical/cycle market identity mismatch")
        if stage_input.integration_id != cycle_input.p6_integration_id:
            raise ValueError("P6 integration identity mismatch")

        return stage_input
