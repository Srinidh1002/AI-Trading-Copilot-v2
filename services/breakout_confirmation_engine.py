"""
Breakout and breakdown confirmation engine.

Confirms directional price triggers using:
- Candle close beyond the trigger level
- Optional confirmation buffer
- Optional volume confirmation
- Optional momentum confirmation

This module does not place orders.
"""


def confirm_breakout(
    direction,
    trigger_price,
    candle_close,
    candle_high=None,
    candle_low=None,
    current_volume=None,
    average_volume=None,
    momentum_signal=None,
    confirmation_buffer_percent=0.0,
    minimum_volume_multiplier=1.2,
    require_volume=False,
    require_momentum=False,
):
    """
    Confirm a bullish breakout or bearish breakdown.

    Returns
    -------
    dict
        Structured confirmation result.
    """

    # ---------------------------------
    # VALIDATION
    # ---------------------------------

    if trigger_price <= 0:
        raise ValueError(
            "trigger_price must be greater than zero."
        )

    if candle_close <= 0:
        raise ValueError(
            "candle_close must be greater than zero."
        )

    if confirmation_buffer_percent < 0:
        raise ValueError(
            "confirmation_buffer_percent cannot be negative."
        )

    if minimum_volume_multiplier <= 0:
        raise ValueError(
            "minimum_volume_multiplier must be greater than zero."
        )

    direction = str(
        direction
    ).upper()

    if direction not in {
        "BULLISH",
        "BEARISH",
    }:
        raise ValueError(
            "direction must be BULLISH or BEARISH."
        )

    # ---------------------------------
    # CONFIRMATION LEVEL
    # ---------------------------------

    if direction == "BULLISH":

        confirmation_price = (
            trigger_price
            * (
                1
                + confirmation_buffer_percent
                / 100
            )
        )

        price_confirmed = (
            candle_close
            > confirmation_price
        )

        trigger_type = "BREAKOUT"

    else:

        confirmation_price = (
            trigger_price
            * (
                1
                - confirmation_buffer_percent
                / 100
            )
        )

        price_confirmed = (
            candle_close
            < confirmation_price
        )

        trigger_type = "BREAKDOWN"

    # ---------------------------------
    # VOLUME CONFIRMATION
    # ---------------------------------

    volume_confirmed = None

    if (
        current_volume is not None
        and average_volume is not None
    ):

        current_volume = float(
            current_volume
        )

        average_volume = float(
            average_volume
        )

        if average_volume > 0:

            volume_confirmed = (
                current_volume
                >= average_volume
                * minimum_volume_multiplier
            )

    # ---------------------------------
    # MOMENTUM CONFIRMATION
    # ---------------------------------

    momentum_confirmed = None

    if momentum_signal is not None:

        normalized_momentum = str(
            momentum_signal
        ).upper()

        if direction == "BULLISH":
            momentum_confirmed = (
                normalized_momentum
                == "BULLISH"
            )

        else:
            momentum_confirmed = (
                normalized_momentum
                == "BEARISH"
            )

    # ---------------------------------
    # REASONS
    # ---------------------------------

    reasons = []
    failed_conditions = []

    if price_confirmed:

        if direction == "BULLISH":
            reasons.append(
                "Candle closed above the breakout confirmation level."
            )

        else:
            reasons.append(
                "Candle closed below the breakdown confirmation level."
            )

    else:

        if direction == "BULLISH":
            failed_conditions.append(
                "Candle did not close above the breakout "
                "confirmation level."
            )

        else:
            failed_conditions.append(
                "Candle did not close below the breakdown "
                "confirmation level."
            )

    # ---------------------------------
    # REQUIRED VOLUME CHECK
    # ---------------------------------

    if require_volume:

        if volume_confirmed is True:
            reasons.append(
                "Volume confirmed the price move."
            )

        elif volume_confirmed is False:
            failed_conditions.append(
                "Volume did not confirm the price move."
            )

        else:
            failed_conditions.append(
                "Volume confirmation was required "
                "but volume data was unavailable."
            )

    elif volume_confirmed is True:

        reasons.append(
            "Volume provided additional confirmation."
        )

    # ---------------------------------
    # REQUIRED MOMENTUM CHECK
    # ---------------------------------

    if require_momentum:

        if momentum_confirmed is True:
            reasons.append(
                "Momentum confirmed the price move."
            )

        elif momentum_confirmed is False:
            failed_conditions.append(
                "Momentum did not confirm the price move."
            )

        else:
            failed_conditions.append(
                "Momentum confirmation was required "
                "but momentum data was unavailable."
            )

    elif momentum_confirmed is True:

        reasons.append(
            "Momentum provided additional confirmation."
        )

    # ---------------------------------
    # FINAL CONFIRMATION
    # ---------------------------------

    confirmed = (
        price_confirmed
        and (
            not require_volume
            or volume_confirmed is True
        )
        and (
            not require_momentum
            or momentum_confirmed is True
        )
    )

    status = (
        "CONFIRMED"
        if confirmed
        else "NOT_CONFIRMED"
    )

    return {
        "confirmed": confirmed,
        "status": status,
        "direction": direction,
        "trigger_type": trigger_type,
        "trigger_price": round(
            float(trigger_price),
            2,
        ),
        "confirmation_price": round(
            float(confirmation_price),
            2,
        ),
        "candle_close": float(
            candle_close
        ),
        "candle_high": (
            float(candle_high)
            if candle_high is not None
            else None
        ),
        "candle_low": (
            float(candle_low)
            if candle_low is not None
            else None
        ),
        "price_confirmed": price_confirmed,
        "volume_confirmed": volume_confirmed,
        "momentum_confirmed": momentum_confirmed,
        "reasons": reasons,
        "failed_conditions": failed_conditions,
    }