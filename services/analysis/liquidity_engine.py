"""
Liquidity Engine

Evaluates market liquidity using bid/ask spread,
market depth and traded volume.
"""


def analyze_liquidity(snapshot):

    """
    Expected snapshot:

    snapshot["liquidity"] = {

        "bid": float,

        "ask": float,

        "bid_qty": int,

        "ask_qty": int,

        "volume": int,

        "avg_volume": int,

    }
    """

    liquidity = snapshot.get(
        "liquidity",
        {},
    )

    bid = float(
        liquidity.get(
            "bid",
            0,
        )
    )

    ask = float(
        liquidity.get(
            "ask",
            0,
        )
    )

    bid_qty = int(
        liquidity.get(
            "bid_qty",
            0,
        )
    )

    ask_qty = int(
        liquidity.get(
            "ask_qty",
            0,
        )
    )

    volume = int(
        liquidity.get(
            "volume",
            0,
        )
    )

    avg_volume = int(
        liquidity.get(
            "avg_volume",
            1,
        )
    )

    if bid <= 0 or ask <= 0:

        return {

            "signal": "UNKNOWN",

            "bull_score": 0,

            "bear_score": 0,

            "confidence": 0,

            "reason": "Liquidity unavailable",

            "metrics": {},

        }

    spread = ask - bid

    spread_pct = (spread / ask) * 100

    rvol = volume / max(
        avg_volume,
        1,
    )

    bull = 0
    bear = 0

    reasons = []

    # -------------------------
    # Spread Analysis
    # -------------------------

    if spread_pct <= 0.05:

        bull += 3

        reasons.append(
            "Very Tight Spread"
        )

    elif spread_pct <= 0.15:

        bull += 2

        reasons.append(
            "Healthy Spread"
        )

    else:

        bear += 2

        reasons.append(
            "Wide Spread"
        )

    # -------------------------
    # Market Depth
    # -------------------------

    if bid_qty > ask_qty * 1.5:

        bull += 2

        reasons.append(
            "Strong Bid Depth"
        )

    elif ask_qty > bid_qty * 1.5:

        bear += 2

        reasons.append(
            "Strong Ask Depth"
        )

    # -------------------------
    # Relative Volume
    # -------------------------

    if rvol >= 2:

        bull += 2

        reasons.append(
            "High Relative Volume"
        )

    elif rvol <= 0.7:

        bear += 1

        reasons.append(
            "Low Relative Volume"
        )

    # -------------------------

    if bull >= bear + 2:

        signal = "BULLISH"

    elif bear >= bull + 2:

        signal = "BEARISH"

    else:

        signal = "NEUTRAL"

    confidence = min(
        100,
        55 + abs(bull - bear) * 8,
    )

    return {

        "signal": signal,

        "bull_score": bull,

        "bear_score": bear,

        "confidence": round(
            confidence,
            2,
        ),

        "reason": ", ".join(reasons),

        "metrics": {

            "Spread": round(
                spread,
                2,
            ),

            "SpreadPercent": round(
                spread_pct,
                4,
            ),

            "RelativeVolume": round(
                rvol,
                2,
            ),

            "BidQuantity": bid_qty,

            "AskQuantity": ask_qty,

            "Volume": volume,

        },

    }