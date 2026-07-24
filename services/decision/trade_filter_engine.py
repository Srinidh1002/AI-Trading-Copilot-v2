"""
Institutional Trade Filter Engine

Final gate before a trade is approved.

Every filter either:
- APPROVES
- REJECTS
- WARNS

No market analysis is performed here.
This engine only validates whether a trade should
be allowed under institutional trading rules.
"""

from datetime import datetime, time


def _session_filter(snapshot):
    """
    Reject trades outside regular trading session.
    """

    current_time = snapshot.get("timestamp")

    if isinstance(current_time, str):
        current_time = datetime.fromisoformat(current_time)

    if current_time is None:
        return {
            "approved": False,
            "reason": "Market time unavailable",
        }

    now = current_time.time()

    market_open = time(9, 15)
    market_close = time(15, 30)

    if now < market_open:
        return {
            "approved": False,
            "reason": "Market not opened",
        }

    if now > market_close:
        return {
            "approved": False,
            "reason": "Market closed",
        }

    return {
        "approved": True,
        "reason": "",
    }


def _market_regime_filter(snapshot):
    """
    Reject trades during unfavorable market regimes.
    """

    regime = str(
        snapshot.get(
            "market_regime",
            "UNKNOWN",
        )
    ).upper()

    if regime == "SIDEWAYS":
        return {
            "approved": False,
            "reason": "Sideways market",
        }

    if regime == "HIGH_VOLATILITY":
        return {
            "approved": False,
            "reason": "High volatility regime",
        }

    if regime == "UNKNOWN":
        return {
            "approved": False,
            "reason": "Unknown market regime",
        }

    return {
        "approved": True,
        "reason": "",
    }


def _volatility_filter(snapshot):
    """
    Reject trades during extreme volatility.
    """

    indicators = snapshot.get(
        "indicators",
        {},
    )

    vix = indicators.get("INDIA_VIX")

    if vix is None:
        return {
            "approved": True,
            "reason": "",
        }

    if vix >= 28:
        return {
            "approved": False,
            "reason": "Extreme India VIX",
        }

    return {
        "approved": True,
        "reason": "",
    }


def _liquidity_filter(snapshot):
    """
    Reject trades when liquidity is poor.
    """

    option_analysis = snapshot.get(
        "option_analysis",
        {},
    )

    flow = option_analysis.get(
        "Flow",
        {},
    )

    liquidity = flow.get(
        "Liquidity",
    )

    if liquidity is None:
        return {
            "approved": True,
            "reason": "",
        }

    if str(liquidity).upper() == "LOW":
        return {
            "approved": False,
            "reason": "Low market liquidity",
        }

    return {
        "approved": True,
        "reason": "",
    }


def _news_event_filter(snapshot):
    """
    Reject trades during major scheduled or breaking events.
    """

    news = snapshot.get(
        "news",
        {},
    )

    high_impact = news.get(
        "high_impact_event",
        False,
    )

    market_halt = news.get(
        "market_halt",
        False,
    )

    if market_halt:
        return {
            "approved": False,
            "reason": "Market halted",
        }

    if high_impact:
        return {
            "approved": False,
            "reason": "High-impact news event",
        }

    return {
        "approved": True,
        "reason": "",
    }


def _consecutive_loss_filter(snapshot):
    """
    Pause trading after too many consecutive losses.
    """

    trade_stats = snapshot.get(
        "trade_stats",
        {},
    )

    consecutive_losses = trade_stats.get(
        "consecutive_losses",
        0,
    )

    max_losses = trade_stats.get(
        "max_consecutive_losses",
        3,
    )

    if consecutive_losses >= max_losses:
        return {
            "approved": False,
            "reason": "Consecutive loss cooldown active",
        }

    return {
        "approved": True,
        "reason": "",
    }

def _duplicate_signal_filter(snapshot):
    """
    Reject duplicate trade signals that are already active.
    """

    trade_state = snapshot.get(
        "trade_state",
        {},
    )

    active_signal = trade_state.get(
        "active_signal",
        False,
    )

    if active_signal:
        return {
            "approved": False,
            "reason": "Duplicate active trade signal",
        }

    return {
        "approved": True,
        "reason": "",
    }

def _minimum_confirmation_filter(
    decision,
    confidence,
    risk,
):
    """
    Require minimum agreement across the
    decision engines before approving a trade.
    """

    confirmations = 0

    if decision.get("approved", False):
        confirmations += 1

    if confidence.get("confidence", 0) >= 70:
        confirmations += 1

    if risk.get("approved", False):
        confirmations += 1

    minimum_confirmations = 3

    if confirmations < minimum_confirmations:
        return {
            "approved": False,
            "reason": (
                f"Only {confirmations}/"
                f"{minimum_confirmations} confirmations"
            ),
        }

    return {
        "approved": True,
        "reason": "",
    }
def evaluate_trade_filters(
    *,
    snapshot,
    decision,
    confidence,
    risk,
):
    """
    Returns:
    {
        "approved": True,
        "filters": [],
        "warnings": [],
        "reasons": [],
    }
    """

    filters = []
    warnings = []
    reasons = []

    session = _session_filter(snapshot)

    filters.append(
        {
            "name": "Session Filter",
            **session,
        }
    )

    if not session["approved"]:
        reasons.append(session["reason"])

    market_regime = _market_regime_filter(
        snapshot,
    )

    filters.append(
        {
            "name": "Market Regime Filter",
            **market_regime,
        }
    )

    if not market_regime["approved"]:
        reasons.append(
            market_regime["reason"]
        )

    volatility = _volatility_filter(
        snapshot,
    )

    filters.append(
        {
            "name": "Volatility Filter",
            **volatility,
        }
    )

    if not volatility["approved"]:
        reasons.append(
            volatility["reason"]
        )

    liquidity = _liquidity_filter(
        snapshot,
    )

    filters.append(
        {
            "name": "Liquidity Filter",
            **liquidity,
        }
    )

    if not liquidity["approved"]:
        reasons.append(
            liquidity["reason"]
        )

    news_event = _news_event_filter(
        snapshot,
    )

    filters.append(
        {
            "name": "News/Event Filter",
            **news_event,
        }
    )

    if not news_event["approved"]:
        reasons.append(
            news_event["reason"]
        )

    loss_filter = _consecutive_loss_filter(
        snapshot,
    )

    filters.append(
        {
            "name": "Consecutive Loss Filter",
            **loss_filter,
        }
    )

    if not loss_filter["approved"]:
        reasons.append(
            loss_filter["reason"]
        )
    duplicate_signal = _duplicate_signal_filter(
        snapshot,
    )

    filters.append(
        {
            "name": "Duplicate Signal Filter",
            **duplicate_signal,
        }
    )

    if not duplicate_signal["approved"]:
        reasons.append(
            duplicate_signal["reason"]
        )

    confirmation = _minimum_confirmation_filter(
        decision,
        confidence,
        risk,
    )

    filters.append(
        {
            "name": "Minimum Confirmation Filter",
            **confirmation,
        }
    )

    if not confirmation["approved"]:
        reasons.append(
            confirmation["reason"]
        )
    approved = all(
        f["approved"]
        for f in filters
    )
    
    return {
        "approved": approved,
        "filters": filters,
        "warnings": warnings,
        "reasons": reasons,
    }