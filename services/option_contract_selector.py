"""
Option contract selection engine.

Selects the best option contract from an already-normalized
option chain.

This module does not place orders.
"""


def select_option_contract(
    contracts,
    direction,
    spot_price,
    maximum_spread_percent=2.0,
    minimum_volume=100,
    minimum_open_interest=500,
    minimum_delta=0.30,
    maximum_delta=0.75,
):
    if not contracts:
        return {
            "selected": False,
            "decision": "NO_CONTRACT",
            "symbol": None,
            "strike": None,
            "option_type": None,
            "expiry": None,
            "premium": None,
            "score": 0,
            "reasons": [
                "No option contracts provided."
            ],
        }

    if spot_price <= 0:
        raise ValueError(
            "Spot price must be greater than zero."
        )

    direction = direction.upper()

    if direction == "BULLISH":
        required_type = "CE"

    elif direction == "BEARISH":
        required_type = "PE"

    else:
        return {
            "selected": False,
            "decision": "NO_CONTRACT",
            "symbol": None,
            "strike": None,
            "option_type": None,
            "expiry": None,
            "premium": None,
            "score": 0,
            "reasons": [
                "No valid directional bias."
            ],
        }

    candidates = []

    for contract in contracts:

        option_type = str(
            contract.get(
                "option_type",
                ""
            )
        ).upper()

        if option_type != required_type:
            continue

        premium = float(
            contract.get(
                "premium",
                0
            )
            or 0
        )

        bid = float(
            contract.get(
                "bid",
                0
            )
            or 0
        )

        ask = float(
            contract.get(
                "ask",
                0
            )
            or 0
        )

        volume = int(
            contract.get(
                "volume",
                0
            )
            or 0
        )

        open_interest = int(
            contract.get(
                "open_interest",
                0
            )
            or 0
        )

        delta = abs(
            float(
                contract.get(
                    "delta",
                    0
                )
                or 0
            )
        )

        strike = float(
            contract.get(
                "strike",
                0
            )
            or 0
        )

        if (
            premium <= 0
            or strike <= 0
            or bid <= 0
            or ask <= 0
            or ask < bid
        ):
            continue

        midpoint = (
            bid + ask
        ) / 2

        spread_percent = (
            (ask - bid)
            / midpoint
        ) * 100

        if (
            spread_percent
            > maximum_spread_percent
        ):
            continue

        if volume < minimum_volume:
            continue

        if (
            open_interest
            < minimum_open_interest
        ):
            continue

        if not (
            minimum_delta
            <= delta
            <= maximum_delta
        ):
            continue

        score = 0
        reasons = []

        # -------------------------
        # ATM PROXIMITY
        # -------------------------

        strike_distance_percent = (
            abs(
                strike - spot_price
            )
            / spot_price
        ) * 100

        if strike_distance_percent <= 0.5:
            score += 4
            reasons.append(
                "Strike is close to ATM."
            )

        elif strike_distance_percent <= 1.0:
            score += 2
            reasons.append(
                "Strike is near ATM."
            )

        # -------------------------
        # SPREAD QUALITY
        # -------------------------

        if spread_percent <= 0.5:
            score += 3
            reasons.append(
                "Excellent bid-ask spread."
            )

        elif spread_percent <= 1.0:
            score += 2
            reasons.append(
                "Good bid-ask spread."
            )

        else:
            score += 1

        # -------------------------
        # LIQUIDITY
        # -------------------------

        if volume >= 10000:
            score += 3

        elif volume >= 1000:
            score += 2

        else:
            score += 1

        if open_interest >= 10000:
            score += 3

        elif open_interest >= 2000:
            score += 2

        else:
            score += 1

        # -------------------------
        # DELTA QUALITY
        # -------------------------

        if 0.45 <= delta <= 0.65:
            score += 3
            reasons.append(
                "Delta is in preferred range."
            )

        elif 0.35 <= delta <= 0.70:
            score += 2

        else:
            score += 1

        candidate = dict(
            contract
        )

        candidate[
            "_selection_score"
        ] = score

        candidate[
            "_spread_percent"
        ] = spread_percent

        candidate[
            "_strike_distance_percent"
        ] = strike_distance_percent

        candidate[
            "_selection_reasons"
        ] = reasons

        candidates.append(
            candidate
        )

    if not candidates:
        return {
            "selected": False,
            "decision": "NO_CONTRACT",
            "symbol": None,
            "strike": None,
            "option_type": required_type,
            "expiry": None,
            "premium": None,
            "score": 0,
            "reasons": [
                "No contract passed liquidity and risk filters."
            ],
        }

    candidates.sort(
        key=lambda item: (
            item["_selection_score"],
            -item[
                "_strike_distance_percent"
            ],
            -item[
                "_spread_percent"
            ],
        ),
        reverse=True,
    )

    best = candidates[0]

    return {
        "selected": True,
        "decision": "CONTRACT_SELECTED",
        "symbol": best.get("symbol"),
        "strike": best.get("strike"),
        "option_type": best.get(
            "option_type"
        ),
        "expiry": best.get("expiry"),
        "premium": best.get("premium"),
        "score": best[
            "_selection_score"
        ],
        "reasons": best[
            "_selection_reasons"
        ],
    }