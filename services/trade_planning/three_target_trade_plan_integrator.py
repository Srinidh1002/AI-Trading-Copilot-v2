from services.contracts.integrated_three_target_trade_plan_input_v1 import (
    IntegratedThreeTargetTradePlanInputV1,
)
from services.contracts.integrated_three_target_trade_plan_result_v1 import (
    IntegratedThreeTargetTradePlanResultV1,
)


def integrate_three_target_trade_plan(
    integration_input,
):
    if (
        type(integration_input)
        is not IntegratedThreeTargetTradePlanInputV1
    ):
        raise TypeError("integration_input")

    values = (
        integration_input.entry_zone_result,
        integration_input.stop_loss_result,
        integration_input.three_target_result,
        integration_input.option_contract_selection_result,
        integration_input.capital_quantity_result,
    )

    blockers = tuple(
        dict.fromkeys(
            blocker
            for value in values
            if value.status == "BLOCKED"
            for blocker in (
                value.blockers
                or (f"{type(value).__name__}_BLOCKED",)
            )
        )
    )

    if blockers:
        return IntegratedThreeTargetTradePlanResultV1(
            integration_input.integration_id,
            "BLOCKED",
            integration_input.canonical_trade_plan_input,
            *values,
            blockers=blockers,
            warnings=tuple(
                dict.fromkeys(
                    warning
                    for value in values
                    for warning in value.warnings
                )
            ),
            metadata={
                "integration_stage": "ASSEMBLY",
            },
        )

    non_ready = tuple(
        value.status
        for value in values[:-1]
        if value.status != "READY"
    )
    if non_ready:
        return IntegratedThreeTargetTradePlanResultV1(
            integration_input.integration_id,
            "BLOCKED",
            integration_input.canonical_trade_plan_input,
            *values,
            blockers=non_ready,
            metadata={
                "integration_stage": "ASSEMBLY",
            },
        )

    capital = integration_input.capital_quantity_result

    if capital.status == "NO_SIZE":
        return IntegratedThreeTargetTradePlanResultV1(
            integration_input.integration_id,
            "NO_SIZE",
            integration_input.canonical_trade_plan_input,
            *values,
            decision_reasons=capital.decision_reasons,
            warnings=capital.warnings,
            metadata={
                "integration_stage": "ASSEMBLY",
            },
        )

    if capital.status != "READY":
        raise ValueError(
            "capital quantity result must be "
            "READY, BLOCKED, or NO_SIZE"
        )

    return IntegratedThreeTargetTradePlanResultV1(
        integration_input.integration_id,
        "READY",
        integration_input.canonical_trade_plan_input,
        *values,
        warnings=tuple(
            dict.fromkeys(
                warning
                for value in values
                for warning in value.warnings
            )
        ),
        metadata={
            "integration_stage": "ASSEMBLY",
        },
    )
