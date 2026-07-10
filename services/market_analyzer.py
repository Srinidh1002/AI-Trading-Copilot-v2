from services.market_indices import market_indices


def analyse_market():

    data = market_indices()

    score = {
        "trend": "NEUTRAL",
        "strength": 0,
        "momentum": 0,
        "volatility": 0,
        "confidence": 0,
        "reasons": []
    }

    if not data:
        score["reasons"].append("No market data")
        return score

    return score