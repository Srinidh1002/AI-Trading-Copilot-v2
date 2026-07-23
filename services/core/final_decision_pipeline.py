"""
Final Decision Pipeline

Runs every analysis engine in the correct order and
returns a single institutional-grade decision snapshot.
"""

from services.analysis.trend_engine import analyze_trend
from archive.market_structure_engine import (
    analyze_market_structure as analyze_structure,
)
from services.analysis.candlestick_engine import detect_pattern
from services.analysis.volume_engine import analyze_volume
from services.analysis.market_breadth_engine import analyze_market_breadth
from services.analysis.market_regime_engine import analyze_market_regime
from services.analysis.liquidity_engine import analyze_liquidity
from services.analysis.correlation_engine import analyze_correlation
from services.analysis.fii_dii_engine import analyze_fii_dii
from services.analysis.vix_engine import analyze_vix
from services.analysis.news_sentiment_engine import analyze_news_sentiment
from services.analysis.economic_calendar_engine import analyze_economic_calendar
from services.analysis.market_strength_engine import analyze_market_strength
from services.analysis.execution_quality_engine import (
    analyze_execution_quality,
)
from services.analysis.portfolio_risk_engine import (
    analyze_portfolio_risk,
)
from services.analysis.confluence_engine import analyze_confluence
from services.analysis.self_validation_engine import (
    analyze_self_validation,
)
from services.analysis.decision_quality_engine import (
    analyze_decision_quality,
)
from services.analysis.final_ai_reasoning_engine import (
    FinalAIReasoningEngine,
)


class FinalDecisionPipeline:

    @staticmethod
    def run(snapshot: dict):

        # ---------------------------------
        # Core Analysis
        # ---------------------------------

        snapshot["trend_analysis"] = analyze_trend(snapshot)

        snapshot["structure_analysis"] = analyze_structure(snapshot)

        snapshot["candlestick_analysis"] = detect_pattern(snapshot)

        snapshot["volume_analysis"] = analyze_volume(snapshot)

        snapshot["market_breadth_analysis"] = (
            analyze_market_breadth(snapshot)
        )

        snapshot["market_regime_analysis"] = (
            analyze_market_regime(snapshot)
        )

        snapshot["liquidity_analysis"] = (
            analyze_liquidity(snapshot)
        )

        snapshot["correlation_analysis"] = (
            analyze_correlation(snapshot)
        )

        snapshot["fii_dii_analysis"] = (
            analyze_fii_dii(snapshot)
        )

        snapshot["vix_analysis"] = (
            analyze_vix(snapshot)
        )

        snapshot["news_analysis"] = (
            analyze_news_sentiment(snapshot)
        )

        snapshot["economic_analysis"] = (
            analyze_economic_calendar(snapshot)
        )

        # ---------------------------------
        # Aggregate Analysis
        # ---------------------------------

        snapshot["market_strength_analysis"] = (
            analyze_market_strength(snapshot)
        )

        snapshot["execution_quality_analysis"] = (
            analyze_execution_quality(snapshot)
        )

        snapshot["portfolio_risk_analysis"] = (
            analyze_portfolio_risk(snapshot)
        )

        snapshot["confluence_analysis"] = (
            analyze_confluence(snapshot)
        )

        snapshot["self_validation_analysis"] = (
            analyze_self_validation(snapshot)
        )

        snapshot["decision_quality_analysis"] = (
            analyze_decision_quality(snapshot)
        )

        # ---------------------------------
        # Final Decision
        # ---------------------------------

        confluence = snapshot["confluence_analysis"]

        validation = snapshot["self_validation_analysis"]

        quality = snapshot["decision_quality_analysis"]

        final_decision = {

            "signal": confluence.get(
                "signal",
                "NEUTRAL",
            ),

            "confidence": confluence.get(
                "confidence",
                0,
            ),

            "bull_score": confluence.get(
                "bull_score",
                0,
            ),

            "bear_score": confluence.get(
                "bear_score",
                0,
            ),

            "confluence_score": confluence.get(
                "confluence_score",
                0,
            ),

            "validation_status": validation.get(
                "status",
                "UNKNOWN",
            ),

            "validation_agreement": validation.get(
                "agreement",
                0,
            ),

            "decision_quality": quality.get(
                "quality",
                0,
            ),

            "decision_quality_signal": quality.get(
                "signal",
                "UNKNOWN",
            ),

        }

        final_decision.update({

            "trend_signal":
                snapshot["trend_analysis"].get("signal"),

            "volume_signal":
                snapshot["volume_analysis"].get("signal"),

            "market_breadth_signal":
                snapshot["market_breadth_analysis"].get("signal"),

            "market_regime_signal":
                snapshot["market_regime_analysis"].get("signal"),

            "liquidity_signal":
                snapshot["liquidity_analysis"].get("signal"),

            "fii_dii_signal":
                snapshot["fii_dii_analysis"].get("signal"),

            "vix_signal":
                snapshot["vix_analysis"].get("signal"),

            "news_signal":
                snapshot["news_analysis"].get("signal"),

            "economic_signal":
                snapshot["economic_analysis"].get("signal"),

            "market_strength_signal":
                snapshot["market_strength_analysis"].get("signal"),

            "confluence_signal":
                confluence.get("signal"),

        })

        final_decision["ai_reasoning"] = (

            FinalAIReasoningEngine.generate(
                final_decision
            )

        )

        snapshot["final_decision"] = final_decision

        return snapshot