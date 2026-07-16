class DecisionExplanation:

    def build(
        self,
        pipeline_result,
    ):

        if not isinstance(
            pipeline_result,
            dict,
        ):
            return {}

        explanation = {
            "decision": pipeline_result.get("decision"),
            "confidence": pipeline_result.get("confidence"),
            "direction": pipeline_result.get("direction"),
            "strategy": pipeline_result.get("strategy"),
            "setup_status": pipeline_result.get("setup_status"),
            "risk_flags": pipeline_result.get("risk_flags", []),
            "signals": pipeline_result.get("relevant_signals", []),
            "reasons": pipeline_result.get("reasons", []),
        }

        pipeline_result[
            "decision_explanation"
        ] = explanation

        return explanation