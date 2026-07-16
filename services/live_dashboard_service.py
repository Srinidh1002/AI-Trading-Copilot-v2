from copy import deepcopy


class LiveDashboardService:

    def build(
        self,
        pipeline_result,
    ):

        if not isinstance(
            pipeline_result,
            dict,
        ):
            return {}

        return deepcopy(
            {
                "decision": pipeline_result.get(
                    "decision"
                ),
                "direction": pipeline_result.get(
                    "direction"
                ),
                "market_analysis": pipeline_result.get(
                    "market_analysis"
                ),
                "setup_trigger": pipeline_result.get(
                    "setup_trigger"
                ),
                "contract": pipeline_result.get(
                    "contract"
                ),
                "completed_candle": pipeline_result.get(
                    "completed_candle"
                ),
                "session_status": pipeline_result.get(
                    "session_status"
                ),
                "decision_explanation": pipeline_result.get(
                     "decision_explanation"
                ),
            }
        )