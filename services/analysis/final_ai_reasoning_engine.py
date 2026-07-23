"""
Final AI Reasoning Engine

Generates a human-readable institutional explanation
for the final trade decision.
"""


class FinalAIReasoningEngine:

    @staticmethod
    def generate(decision: dict):

        reasons = []

        signal = decision.get("signal", "UNKNOWN")
        confidence = decision.get("confidence", 0)

        # -----------------------------
        # Trend
        # -----------------------------

        trend = decision.get(
            "trend_signal",
            "",
        )

        if trend:
            reasons.append(
                f"Trend: {trend}"
            )

        # -----------------------------
        # Multi Timeframe
        # -----------------------------

        mtf = decision.get(
            "multi_timeframe_bias",
            "",
        )

        if mtf:
            reasons.append(
                f"MTF: {mtf}"
            )

        # -----------------------------
        # Market Regime
        # -----------------------------

        regime = decision.get(
            "market_regime_signal",
            "",
        )

        if regime:
            reasons.append(
                f"Regime: {regime}"
            )

        # -----------------------------
        # Volume
        # -----------------------------

        volume = decision.get(
            "volume_signal",
            "",
        )

        if volume:
            reasons.append(
                f"Volume: {volume}"
            )

        # -----------------------------
        # Breadth
        # -----------------------------

        breadth = decision.get(
            "market_breadth_signal",
            "",
        )

        if breadth:
            reasons.append(
                f"Breadth: {breadth}"
            )

        # -----------------------------
        # Institutional Money
        # -----------------------------

        fii = decision.get(
            "fii_dii_signal",
            "",
        )

        if fii:
            reasons.append(
                f"FII/DII: {fii}"
            )

        # -----------------------------
        # VIX
        # -----------------------------

        vix = decision.get(
            "vix_signal",
            "",
        )

        if vix:
            reasons.append(
                f"VIX: {vix}"
            )

        # -----------------------------
        # Liquidity
        # -----------------------------

        liquidity = decision.get(
            "liquidity_signal",
            "",
        )

        if liquidity:
            reasons.append(
                f"Liquidity: {liquidity}"
            )

        # -----------------------------
        # Options
        # -----------------------------

        option_bias = decision.get(
            "option_bias",
            "",
        )

        if option_bias:
            reasons.append(
                f"Options: {option_bias}"
            )

        option_flow = decision.get(
            "option_flow",
            "",
        )

        if option_flow:
            reasons.append(
                f"Flow: {option_flow}"
            )

        pcr = decision.get(
            "pcr",
            None,
        )

        if pcr is not None:
            reasons.append(
                f"PCR: {pcr}"
            )

        max_pain = decision.get(
            "max_pain",
            None,
        )

        if max_pain is not None:
            reasons.append(
                f"Max Pain: {max_pain}"
            )

        # -----------------------------
        # Greeks
        # -----------------------------

        greeks = decision.get(
            "greeks_bias",
            "",
        )

        if greeks:
            reasons.append(
                f"Greeks: {greeks}"
            )

        # -----------------------------
        # News
        # -----------------------------

        news = decision.get(
            "news_signal",
            "",
        )

        if news:
            reasons.append(
                f"News: {news}"
            )

        # -----------------------------
        # Economic
        # -----------------------------

        economic = decision.get(
            "economic_signal",
            "",
        )

        if economic:
            reasons.append(
                f"Macro: {economic}"
            )

        # -----------------------------
        # Market Strength
        # -----------------------------

        strength = decision.get(
            "market_strength_signal",
            "",
        )

        if strength:
            reasons.append(
                f"Strength: {strength}"
            )

        # -----------------------------
        # Confluence
        # -----------------------------

        confluence = decision.get(
            "confluence_signal",
            "",
        )

        if confluence:
            reasons.append(
                f"Confluence: {confluence}"
            )

        # -----------------------------
        # Self Validation
        # -----------------------------

        validation = decision.get(
            "validation_status",
            "",
        )

        if validation:
            reasons.append(
                f"Validation: {validation}"
            )

        # -----------------------------
        # Final Summary
        # -----------------------------

        summary = (

            f"{signal} "

            f"({confidence:.1f}% Confidence)"

        )

        if reasons:

            summary += "\n\n"

            summary += "\n".join(

                f"• {reason}"

                for reason in reasons

            )

        return {

            "summary": summary,

            "signal": signal,

            "confidence": confidence,

            "reasons": reasons,

        }