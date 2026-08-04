"""Project certified normalized runtime states into an operator snapshot."""
from __future__ import annotations

from datetime import datetime

from services.contracts.operator_application_snapshot_v1 import (
    OperatorActiveTradeStateV1,
    OperatorApplicationSnapshotV1,
    OperatorCapitalStateV1,
    OperatorMarketStateV1,
    OperatorRecommendationStateV1,
    OperatorSystemHealthV1,
)


def project_operator_application_snapshot(
    *,
    snapshot_id: str,
    generated_at: datetime,
    nifty: OperatorMarketStateV1,
    sensex: OperatorMarketStateV1,
    recommendation: OperatorRecommendationStateV1,
    capital: OperatorCapitalStateV1,
    active_trade: OperatorActiveTradeStateV1,
    system_health: OperatorSystemHealthV1,
) -> OperatorApplicationSnapshotV1:
    """Build one read-only operator snapshot from certified normalized states."""

    expected = {
        "nifty": (nifty, OperatorMarketStateV1),
        "sensex": (sensex, OperatorMarketStateV1),
        "recommendation": (
            recommendation,
            OperatorRecommendationStateV1,
        ),
        "capital": (capital, OperatorCapitalStateV1),
        "active_trade": (
            active_trade,
            OperatorActiveTradeStateV1,
        ),
        "system_health": (
            system_health,
            OperatorSystemHealthV1,
        ),
    }
    for name, (value, expected_type) in expected.items():
        if type(value) is not expected_type:
            raise TypeError(name)

    if nifty.market != "NIFTY" or nifty.exchange != "NSE":
        raise ValueError("nifty identity")
    if sensex.market != "SENSEX" or sensex.exchange != "BSE":
        raise ValueError("sensex identity")

    selected_market = recommendation.selected_market
    losing_market: str | None = None
    losing_reasons: tuple[str, ...] = ()

    if selected_market == "NIFTY":
        if not nifty.eligible:
            raise ValueError("selected NIFTY is ineligible")
        losing_market = "SENSEX"
        losing_reasons = _losing_reasons(
            winner=nifty,
            loser=sensex,
        )
    elif selected_market == "SENSEX":
        if not sensex.eligible:
            raise ValueError("selected SENSEX is ineligible")
        losing_market = "NIFTY"
        losing_reasons = _losing_reasons(
            winner=sensex,
            loser=nifty,
        )
    else:
        if recommendation.action in {"CALL", "PUT"}:
            raise ValueError(
                "executable recommendation requires selected market"
            )

    if active_trade.active and recommendation.action in {
        "CALL",
        "PUT",
    }:
        if active_trade.contract != recommendation.contract:
            raise ValueError(
                "active trade/recommendation contract mismatch"
            )

    health = system_health
    if (
        not nifty.data_fresh
        or not sensex.data_fresh
        or not health.data_fresh
    ):
        if health.status == "HEALTHY":
            raise ValueError("healthy snapshot contains stale data")

    return OperatorApplicationSnapshotV1(
        snapshot_id=snapshot_id,
        generated_at=generated_at,
        nifty=nifty,
        sensex=sensex,
        selected_market=selected_market,
        losing_market=losing_market,
        losing_market_reasons=losing_reasons,
        recommendation=recommendation,
        capital=capital,
        active_trade=active_trade,
        system_health=health,
    )


def _losing_reasons(
    *,
    winner: OperatorMarketStateV1,
    loser: OperatorMarketStateV1,
) -> tuple[str, ...]:
    reasons: list[str] = []

    if not loser.eligible:
        reasons.extend(loser.rejection_reasons)
        if not loser.rejection_reasons:
            reasons.append("LOSING_MARKET_INELIGIBLE")

    if loser.score < winner.score:
        reasons.append("LOWER_SCORE")
    if loser.confidence < winner.confidence:
        reasons.append("LOWER_CONFIDENCE")
    if not loser.data_fresh:
        reasons.append("STALE_DATA")

    if not reasons:
        reasons.append("LOWER_CERTIFIED_RANK")

    return tuple(dict.fromkeys(reasons))
