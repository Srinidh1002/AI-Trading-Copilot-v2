"""
Option contract selection engine.

Selects the best option contract from an already-normalized
option chain.

Greeks such as delta are optional unless explicitly required.

Preserves the actual exchange lot size when available.

This module does not place orders.
"""


def _no_contract_result(
    option_type=None,
    reason="No option contracts provided.",
):
    """
    Return a consistent NO_CONTRACT result.
    """

    return {
        "selected": False,
        "decision": "NO_CONTRACT",
        "symbol": None,
        "strike": None,
        "option_type": option_type,
        "expiry": None,
        "premium": None,
        "lot_size": 0,
        "score": 0,
        "reasons": [
            reason
        ],
    }


def _normalize_lot_size(
    raw_lot_size,
):
    """
    Convert lot size to an integer.

    Invalid or unavailable values return zero.
    """

    try:
        return int(
            float(
                raw_lot_size
                or 0
            )
        )

    except (
        TypeError,
        ValueError,
    ):
        return 0


def select_option_contract(
    contracts,
    direction,
    spot_price,
    maximum_spread_percent=2.0,
    minimum_volume=100,
    minimum_open_interest=500,
    minimum_delta=0.30,
    maximum_delta=0.75,
    require_delta=False,
):
    """
    Select the best option contract for a directional market view.

    Parameters
    ----------
    contracts : list
        Normalized option contracts.

    direction : str
        BULLISH selects CE contracts.
        BEARISH selects PE contracts.

    spot_price : float
        Current underlying spot price.

    require_delta : bool
        If True, contracts without valid delta are rejected.
        If False, contracts may be evaluated without Greeks.

    Returns
    -------
    dict
        Selected contract or NO_CONTRACT result.
    """

    # ---------------------------------
    # INPUT VALIDATION
    # ---------------------------------

    if not contracts:
        return _no_contract_result()

    if spot_price <= 0:
        raise ValueError(
            "Spot price must be greater than zero."
        )

    direction = str(
        direction
    ).upper()

    if direction == "BULLISH":
        required_type = "CE"

    elif direction == "BEARISH":
        required_type = "PE"

    else:
        return _no_contract_result(
            reason=(
                "No valid directional bias."
            )
        )

    candidates = []

    # ---------------------------------
    # EVALUATE CONTRACTS
    # ---------------------------------

    for contract in contracts:

        option_type = str(
            contract.get(
                "option_type",
                "",
            )
        ).upper()

        if (
            option_type
            != required_type
        ):
            continue

        premium = float(
            contract.get(
                "premium",
                0,
            )
            or 0
        )

        bid = float(
            contract.get(
                "bid",
                0,
            )
            or 0
        )

        ask = float(
            contract.get(
                "ask",
                0,
            )
            or 0
        )

        volume = int(
            contract.get(
                "volume",
                0,
            )
            or 0
        )

        open_interest = int(
            contract.get(
                "open_interest",
                0,
            )
            or 0
        )

        strike = float(
            contract.get(
                "strike",
                0,
            )
            or 0
        )

        # ---------------------------------
        # OPTIONAL DELTA
        # ---------------------------------

        raw_delta = contract.get(
            "delta"
        )

        try:
            delta = (
                abs(
                    float(
                        raw_delta
                    )
                )
                if raw_delta
                is not None
                else None
            )

        except (
            TypeError,
            ValueError,
        ):
            delta = None

        # ---------------------------------
        # BASIC DATA QUALITY
        # ---------------------------------

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

        if midpoint <= 0:
            continue

        spread_percent = (
            (ask - bid)
            / midpoint
        ) * 100

        # ---------------------------------
        # HARD FILTERS
        # ---------------------------------

        if (
            spread_percent
            > maximum_spread_percent
        ):
            continue

        if (
            volume
            < minimum_volume
        ):
            continue

        if (
            open_interest
            < minimum_open_interest
        ):
            continue

        if require_delta:

            if delta is None:
                continue

            if not (
                minimum_delta
                <= delta
                <= maximum_delta
            ):
                continue

        # ---------------------------------
        # SCORING
        # ---------------------------------

        score = 0
        reasons = []

        # -------------------------
        # ATM PROXIMITY
        # -------------------------

        strike_distance_percent = (
            abs(
                strike
                - spot_price
            )
            / spot_price
        ) * 100

        if (
            strike_distance_percent
            <= 0.5
        ):
            score += 4

            reasons.append(
                "Strike is close to ATM."
            )

        elif (
            strike_distance_percent
            <= 1.0
        ):
            score += 2

            reasons.append(
                "Strike is near ATM."
            )

        # -------------------------
        # SPREAD QUALITY
        # -------------------------

        if (
            spread_percent
            <= 0.5
        ):
            score += 3

            reasons.append(
                "Excellent bid-ask spread."
            )

        elif (
            spread_percent
            <= 1.0
        ):
            score += 2

            reasons.append(
                "Good bid-ask spread."
            )

        else:
            score += 1

        # -------------------------
        # VOLUME QUALITY
        # -------------------------

        if volume >= 10000:
            score += 3

            reasons.append(
                "Strong trading volume."
            )

        elif volume >= 1000:
            score += 2

        else:
            score += 1

        # -------------------------
        # OPEN INTEREST QUALITY
        # -------------------------

        if (
            open_interest
            >= 10000
        ):
            score += 3

            reasons.append(
                "Strong open interest."
            )

        elif (
            open_interest
            >= 2000
        ):
            score += 2

        else:
            score += 1

        # -------------------------
        # DELTA QUALITY
        # -------------------------

        if delta is not None:

            if (
                0.45
                <= delta
                <= 0.65
            ):
                score += 3

                reasons.append(
                    "Delta is in preferred range."
                )

            elif (
                0.35
                <= delta
                <= 0.70
            ):
                score += 2

                reasons.append(
                    "Delta is in acceptable range."
                )

            else:
                score += 1

        else:
            reasons.append(
                "Delta unavailable; "
                "contract evaluated without Greeks."
            )

        # ---------------------------------
        # STORE CANDIDATE
        # ---------------------------------

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

    # ---------------------------------
    # NO VALID CONTRACT
    # ---------------------------------

    if not candidates:
        return _no_contract_result(
            option_type=required_type,
            reason=(
                "No contract passed "
                "liquidity and risk filters."
            ),
        )

    # ---------------------------------
    # RANK CONTRACTS
    # ---------------------------------

    candidates.sort(
        key=lambda item: (
            item[
                "_selection_score"
            ],
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

    lot_size = (
        _normalize_lot_size(
            best.get(
                "lot_size",
                0,
            )
        )
    )

    # ---------------------------------
    # RETURN BEST CONTRACT
    # ---------------------------------

    return {
        "selected": True,
        "decision": "CONTRACT_SELECTED",
        "symbol": best.get(
            "symbol"
        ),
        "strike": best.get(
            "strike"
        ),
        "option_type": best.get(
            "option_type"
        ),
        "expiry": best.get(
            "expiry"
        ),
        "premium": best.get(
            "premium"
        ),
        "lot_size": lot_size,
        "score": best[
            "_selection_score"
        ],
        "reasons": best[
            "_selection_reasons"
        ],
    }