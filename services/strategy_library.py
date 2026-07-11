"""
Strategy library for the AI Trading Copilot.

Defines which strategies are suitable for each market regime.
"""

STRATEGIES = {
    "TREND_CONTINUATION": {
        "regimes": [
            "TRENDING_BULLISH",
            "TRENDING_BEARISH",
        ],
        "description": "Trade in the direction of an established trend.",
    },

    "PULLBACK": {
        "regimes": [
            "TRENDING_BULLISH",
            "TRENDING_BEARISH",
        ],
        "description": "Enter after a retracement within a strong trend.",
    },

    "BREAKOUT": {
        "regimes": [
            "COMPRESSION",
            "RANGING",
            "HIGH_VOLATILITY",
        ],
        "description": "Trade a confirmed break above resistance.",
    },

    "BREAKDOWN": {
        "regimes": [
            "COMPRESSION",
            "RANGING",
            "HIGH_VOLATILITY",
        ],
        "description": "Trade a confirmed break below support.",
    },

    "MEAN_REVERSION": {
        "regimes": [
            "RANGING",
            "LOW_VOLATILITY",
        ],
        "description": "Trade price movement back toward its mean.",
    },

    "RANGE_TRADING": {
        "regimes": [
            "RANGING",
            "LOW_VOLATILITY",
        ],
        "description": "Trade between established support and resistance.",
    },

    "MOMENTUM": {
        "regimes": [
            "TRENDING_BULLISH",
            "TRENDING_BEARISH",
            "HIGH_VOLATILITY",
        ],
        "description": "Trade strong directional price momentum.",
    },

    "REVERSAL": {
        "regimes": [
            "TRENDING_BULLISH",
            "TRENDING_BEARISH",
            "HIGH_VOLATILITY",
        ],
        "description": "Trade a confirmed reversal of the existing trend.",
    },

    "VOLATILITY_EXPANSION": {
        "regimes": [
            "COMPRESSION",
            "LOW_VOLATILITY",
        ],
        "description": "Trade expansion following volatility compression.",
    },

    "NO_TRADE": {
        "regimes": [
            "UNCERTAIN",
        ],
        "description": "Reject low-quality or conflicting setups.",
    },
}


def get_strategies_for_regime(regime):
    """
    Return strategies suitable for a market regime.
    """

    suitable = []

    for name, details in STRATEGIES.items():
        if regime in details["regimes"]:
            suitable.append(name)

    if not suitable:
        return ["NO_TRADE"]

    return suitable