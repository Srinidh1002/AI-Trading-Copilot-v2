"""
Portfolio Risk Engine

Evaluates overall portfolio risk using
exposure, diversification, sector concentration,
drawdown and leverage.
"""


def analyze_portfolio_risk(snapshot):

    """
    Expected snapshot

    snapshot["portfolio"] = {

        "capital": float,

        "cash": float,

        "positions": [

            {
                "symbol": "...",
                "value": float,
                "sector": "...",
                "pnl": float,
                "leverage": float
            }

        ]

    }
    """

    portfolio = snapshot.get(
        "portfolio",
        {},
    )

    capital = float(
        portfolio.get(
            "capital",
            0,
        )
    )

    cash = float(
        portfolio.get(
            "cash",
            0,
        )
    )

    positions = portfolio.get(
        "positions",
        [],
    )

    if capital <= 0:

        return {

            "signal": "UNKNOWN",

            "bull_score": 0,

            "bear_score": 0,

            "confidence": 0,

            "reason": "Portfolio unavailable",

            "metrics": {},

        }

    invested = sum(

        float(
            p.get(
                "value",
                0,
            )
        )

        for p in positions

    )

    exposure = invested / capital

    sector_map = {}

    total_drawdown = 0

    leverage_sum = 0

    for position in positions:

        sector = position.get(
            "sector",
            "UNKNOWN",
        )

        sector_map.setdefault(
            sector,
            0,
        )

        sector_map[sector] += float(

            position.get(
                "value",
                0,
            )

        )

        pnl = float(
            position.get(
                "pnl",
                0,
            )
        )

        if pnl < 0:

            total_drawdown += abs(pnl)

        leverage_sum += float(

            position.get(
                "leverage",
                1,
            )

        )

    sectors = len(
        sector_map
    )

    largest_sector = 0

    if invested > 0 and sector_map:

        largest_sector = max(

            sector_map.values()

        ) / invested

    avg_leverage = 1

    if positions:

        avg_leverage = (

            leverage_sum

            / len(positions)

        )

    bull = 0
    bear = 0

    reasons = []

    # ------------------------
    # Exposure
    # ------------------------

    if exposure <= 0.40:

        bull += 3

        reasons.append(
            "Healthy Exposure"
        )

    elif exposure <= 0.70:

        bull += 1

    else:

        bear += 3

        reasons.append(
            "High Portfolio Exposure"
        )

    # ------------------------
    # Diversification
    # ------------------------

    if sectors >= 5:

        bull += 2

        reasons.append(
            "Well Diversified"
        )

    elif sectors <= 2:

        bear += 2

        reasons.append(
            "Low Diversification"
        )

    # ------------------------
    # Sector Concentration
    # ------------------------

    if largest_sector >= 0.50:

        bear += 2

        reasons.append(
            "Sector Concentration Risk"
        )

    else:

        bull += 1

    # ------------------------
    # Drawdown
    # ------------------------

    drawdown_pct = (

        total_drawdown

        / capital

    ) * 100

    if drawdown_pct >= 10:

        bear += 3

        reasons.append(
            "Large Drawdown"
        )

    elif drawdown_pct <= 2:

        bull += 2

    # ------------------------
    # Leverage
    # ------------------------

    if avg_leverage > 2:

        bear += 2

        reasons.append(
            "High Leverage"
        )

    else:

        bull += 1

    # ------------------------

    if bull >= bear + 2:

        signal = "LOW_RISK"

    elif bear >= bull + 2:

        signal = "HIGH_RISK"

    else:

        signal = "MODERATE_RISK"

    confidence = min(

        100,

        round(

            60

            + abs(
                bull - bear
            ) * 6,

            2,

        ),

    )

    return {

        "signal": signal,

        "bull_score": bull,

        "bear_score": bear,

        "confidence": confidence,

        "reason": ", ".join(reasons),

        "metrics": {

            "Capital": capital,

            "Cash": cash,

            "Invested": invested,

            "ExposurePercent": round(
                exposure * 100,
                2,
            ),

            "SectorCount": sectors,

            "LargestSectorPercent": round(
                largest_sector * 100,
                2,
            ),

            "DrawdownPercent": round(
                drawdown_pct,
                2,
            ),

            "AverageLeverage": round(
                avg_leverage,
                2,
            ),

        },

    }