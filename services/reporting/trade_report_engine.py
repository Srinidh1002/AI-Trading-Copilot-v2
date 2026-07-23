"""
Trade Report Engine

Generates a standardized report from the
Master Decision Engine output.
"""

from datetime import datetime


class TradeReportEngine:

    @staticmethod
    def generate(decision: dict):

        report = {

            "generated_at": datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),

            "decision": decision.get(
                "signal",
                "UNKNOWN",
            ),

            "confidence": decision.get(
                "confidence",
                0,
            ),

            "bull_score": decision.get(
                "bull_score",
                0,
            ),

            "bear_score": decision.get(
                "bear_score",
                0,
            ),

            "trade_grade": decision.get(
                "trade_grade",
                "N/A",
            ),

            "execution": decision.get(
                "trade_action",
                "WAIT",
            ),

            "risk_level": decision.get(
                "risk_level",
                "UNKNOWN",
            ),

            "institutional_score": decision.get(
                "institutional_score",
                0,
            ),

            "support": decision.get(
                "support",
                "-",
            ),

            "resistance": decision.get(
                "resistance",
                "-",
            ),

            "stop_loss": decision.get(
                "stop_loss",
                "-",
            ),

            "target": decision.get(
                "target",
                "-",
            ),

            "option_bias": decision.get(
                "option_bias",
                "-",
            ),

            "option_flow": decision.get(
                "option_flow",
                "-",
            ),

            "greeks_bias": decision.get(
                "greeks_bias",
                "-",
            ),

            "pcr": decision.get(
                "pcr",
                "-",
            ),

            "max_pain": decision.get(
                "max_pain",
                "-",
            ),

            "volume_signal": decision.get(
                "volume_signal",
                "-",
            ),

            "market_breadth": decision.get(
                "market_breadth_signal",
                "-",
            ),

            "news_sentiment": decision.get(
                "news_signal",
                "-",
            ),

            "economic_signal": decision.get(
                "economic_signal",
                "-",
            ),

            "fii_dii_signal": decision.get(
                "fii_dii_signal",
                "-",
            ),

            "vix_signal": decision.get(
                "vix_signal",
                "-",
            ),

            "multi_timeframe": decision.get(
                "multi_timeframe_bias",
                "-",
            ),

            "reason": decision.get(
                "reason",
                "",
            ),

        }

        return report