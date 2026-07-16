class IndicatorSnapshot:

    def build(self, pipeline_result):

        market = pipeline_result.get("market_analysis", {})

        technical = market.get("technical", {})
        regime = market.get("regime", {})
        volume = market.get("volume", {})

        return {
            "ema20": technical.get("ema20"),
            "ema50": technical.get("ema50"),
            "ema200": technical.get("ema200"),
            "rsi": technical.get("rsi"),
            "macd": technical.get("macd"),
            "trend": technical.get("trend"),

            "primary_regime": regime.get("primary_regime"),
            "regime_trend": regime.get("trend"),
            "regime_confidence": regime.get("confidence"),

            "relative_volume": volume.get("relative_volume"),
            "volume_spike": volume.get("volume_spike"),
        }