from services.contracts.capital_quantity_planning_input_v1 import (
    CapitalQuantityPlanningInputV1,
)
from services.contracts.entry_zone_evaluation_input_v1 import (
    EntryZoneEvaluationInputV1,
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
from services.paper_orchestration.certified_p6_input_factory import (
    CertifiedP6InputBundleV1,
)


def exact_uninitialised(contract):
    return object.__new__(contract)


def test_bundle_requires_exact_certified_contract_types():
    value = CertifiedP6InputBundleV1(
        planning_policy=exact_uninitialised(TradePlanningPolicyV1),
        option_selection_input=exact_uninitialised(
            OptionContractSelectionInputV1
        ),
        entry_zone_input=exact_uninitialised(EntryZoneEvaluationInputV1),
        stop_loss_input=exact_uninitialised(StopLossEvaluationInputV1),
        three_target_input=exact_uninitialised(
            ThreeTargetEvaluationInputV1
        ),
        capital_quantity_input=exact_uninitialised(
            CapitalQuantityPlanningInputV1
        ),
    )

    assert type(value) is CertifiedP6InputBundleV1
    assert value.execution_mode == "PAPER"
    assert value.live_execution_eligible is False


def test_bundle_rejects_legacy_mapping():
    try:
        CertifiedP6InputBundleV1(
            planning_policy={},
            option_selection_input=exact_uninitialised(
                OptionContractSelectionInputV1
            ),
            entry_zone_input=exact_uninitialised(
                EntryZoneEvaluationInputV1
            ),
            stop_loss_input=exact_uninitialised(
                StopLossEvaluationInputV1
            ),
            three_target_input=exact_uninitialised(
                ThreeTargetEvaluationInputV1
            ),
            capital_quantity_input=exact_uninitialised(
                CapitalQuantityPlanningInputV1
            ),
        )
    except TypeError as exc:
        assert "planning_policy" in str(exc)
    else:
        raise AssertionError("legacy mapping must be rejected")
