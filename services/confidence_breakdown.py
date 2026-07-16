class ConfidenceBreakdown:

    def build(
        self,
        pipeline_result,
    ):

        return {
            "trend": pipeline_result.get(
                "trend_score",
                0,
            ),
            "volume": pipeline_result.get(
                "volume_score",
                0,
            ),
            "pattern": pipeline_result.get(
                "pattern_score",
                0,
            ),
            "timeframe": pipeline_result.get(
                "timeframe_score",
                0,
            ),
            "risk": pipeline_result.get(
                "risk_score",
                0,
            ),
            "overall": pipeline_result.get(
                "confidence",
                0,
            ),
        }