from models.final_decision_state import (
    FinalDecisionState,
)

from services.unified_decision_engine import (
    make_final_decision,
)


class FinalDecisionAgent:

    def analyse(
        self,
        strategy,
        core_risk,
        options_risk=None,
    ):

        result = make_final_decision(
            strategy=strategy,
            core_risk=core_risk,
            options_risk=options_risk,
        )

        return FinalDecisionState(
            decision=result["decision"],
            action=result["action"],
            direction=result["direction"],
            strategy=result["strategy"],
            confidence=result["confidence"],
            approved=result["approved"],
            reasons=result["reasons"],
            risk_flags=result["risk_flags"],
        )