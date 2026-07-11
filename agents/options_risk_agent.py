from models.options_risk_state import (
    OptionsRiskState,
)

from services.options_risk_engine import (
    evaluate_options_risk,
)


class OptionsRiskAgent:

    def analyse(self, **kwargs):

        result = evaluate_options_risk(
            **kwargs
        )

        return OptionsRiskState(
            approved=result["approved"],
            decision=result["decision"],
            lots=result["lots"],
            quantity=result["quantity"],
            premium_exposure=result[
                "premium_exposure"
            ],
            spread_percent=result[
                "spread_percent"
            ],
            reasons=result["reasons"],
            warnings=result["warnings"],
        )