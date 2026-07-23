"""
Market Ranking Engine

Ranks all supported indices and returns the best trading opportunity.
"""

from typing import Dict, List


SUPPORTED_MARKETS = (
    "NIFTY",
    "BANKNIFTY",
    "FINNIFTY",
    "MIDCPNIFTY",
    "SENSEX",
    "BANKEX",
)

MIN_CONFIDENCE = 60
MIN_SCORE_GAP = 15


class MarketRankingEngine:

    def __init__(self):

        self.supported_markets = SUPPORTED_MARKETS

    def rank(self, market_results: Dict[str, Dict]) -> List[Dict]:

        rankings = []

        for market in self.supported_markets:

            result = market_results.get(market)

            if not result:
                continue

            rankings.append(
                {
                    "market": market,
                    "signal": result.get("signal", "HOLD"),
                    "trend": result.get("trend", "NEUTRAL"),
                    "confidence": result.get("confidence", 0),
                    "bull_score": result.get("bull_score", 0),
                    "bear_score": result.get("bear_score", 0),
                    "reasons": result.get("reasons", []),
                    "metadata": result.get("metadata", {}),
                }
            )

        for item in rankings:

            score = item["confidence"]

            if item["signal"] == "BUY":
                score += 5

            elif item["signal"] == "SELL":
                score += 3

            else:
                score -= 10

            score_gap = abs(
                item["bull_score"] - item["bear_score"]
            )

            score += score_gap * 0.20

            if item["confidence"] >= 90:
                score += 10

            elif item["confidence"] >= 80:
                score += 6

            elif item["confidence"] >= 70:
                score += 3

            if score_gap >= 40:
                score += 5

            elif score_gap >= 25:
                score += 2

            item["ranking_score"] = round(score, 2)

        rankings.sort(
            key=lambda x: x["ranking_score"],
            reverse=True,
        )

        return rankings

    def best_trade(self, market_results: Dict[str, Dict]) -> Dict:

        rankings = self.rank(market_results)

        if not rankings:

            return {
                "market": None,
                "signal": "NO_TRADE",
                "reason": "No market data available.",
            }

        best = rankings[0]

        score_gap = abs(
            best["bull_score"] - best["bear_score"]
        )

        if (
            best["signal"] == "HOLD"
            or best["confidence"] < MIN_CONFIDENCE
            or score_gap < MIN_SCORE_GAP
        ):

            return {
                "market": best["market"],
                "signal": "NO_TRADE",
                "reason": (
                    "No market satisfies minimum "
                    "confidence and score-gap requirements."
                ),
                "ranking": best,
            }

        return {
            "market": best["market"],
            "signal": best["signal"],
            "ranking": best,
        }


def rank_markets(market_results: Dict[str, Dict]) -> List[Dict]:

    return MarketRankingEngine().rank(market_results)


def best_market(market_results: Dict[str, Dict]) -> Dict:

    return MarketRankingEngine().best_trade(market_results)