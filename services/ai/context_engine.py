"""
Context Engine V1
"""


def build_context(snapshot, decision):

    return {
        "market": {
            "price": snapshot["ltp"],
            "status": snapshot["market_status"],
        },

        "trend": decision["trend"],

        "support": decision["support_resistance"]["Support"],

        "resistance": decision["support_resistance"]["Resistance"],

        "confidence": decision["confidence"],

        "risk": decision["risk"],

        "trade": decision["trade"],
    }