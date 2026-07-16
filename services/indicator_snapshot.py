class IndicatorSnapshot:

    def build(
        self,
        pipeline_result,
    ):
        """
        Build a read-only indicator snapshot.

        Never modify pipeline_result.
        Never calculate indicators.
        Never fetch broker data.
        """
        return {
    "ema20": pipeline_result["technical"]["ema20"],
    "ema50": pipeline_result["technical"]["ema50"],
    "ema200": pipeline_result["technical"]["ema200"],
    "rsi": pipeline_result["technical"]["rsi"],
    "macd": pipeline_result["technical"]["macd"],
    "trend": pipeline_result["technical"]["trend"],
    "primary_regime": pipeline_result["regime"]["primary_regime"],
    "regime_trend": pipeline_result["regime"]["trend"],
    "regime_confidence": pipeline_result["regime"]["confidence"],
    "relative_volume": pipeline_result["volume"]["relative_volume"],
    "volume_spike": pipeline_result["volume"]["volume_spike"],
}