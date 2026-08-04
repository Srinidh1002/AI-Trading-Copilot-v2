"""Project operator application snapshot into a UI-safe view model."""
from __future__ import annotations

from services.contracts.operator_application_snapshot_v1 import (
    OperatorApplicationSnapshotV1,
    OperatorMarketStateV1,
)
from services.contracts.operator_application_view_model_v1 import (
    OperatorActiveTradeCardV1,
    OperatorApplicationViewModelV1,
    OperatorCapitalCardV1,
    OperatorHealthCardV1,
    OperatorMarketCardV1,
    OperatorRecommendationCardV1,
)


def project_operator_application_view_model(
    *,
    view_model_id: str,
    snapshot: OperatorApplicationSnapshotV1,
) -> OperatorApplicationViewModelV1:
    if type(snapshot) is not OperatorApplicationSnapshotV1:
        raise TypeError("snapshot")

    selected_banner = (
        f"Selected market: {snapshot.selected_market}"
        if snapshot.selected_market is not None
        else "Selected market: NONE"
    )
    losing_banner = (
        "Losing market: NONE"
        if snapshot.losing_market is None
        else (
            f"Losing market: {snapshot.losing_market} | "
            + ", ".join(snapshot.losing_market_reasons)
        )
    )

    recommendation = snapshot.recommendation
    capital = snapshot.capital
    active = snapshot.active_trade
    health = snapshot.system_health

    return OperatorApplicationViewModelV1(
        view_model_id=view_model_id,
        generated_at=snapshot.generated_at,
        title="AI Trading Copilot",
        subtitle="NIFTY and SENSEX certified operator view",
        selected_market_banner=selected_banner,
        losing_market_banner=losing_banner,
        nifty_card=_market_card(snapshot.nifty),
        sensex_card=_market_card(snapshot.sensex),
        recommendation_card=OperatorRecommendationCardV1(
            action_label=f"Action: {recommendation.action}",
            selected_market_label=(
                "Market: NONE"
                if recommendation.selected_market is None
                else f"Market: {recommendation.selected_market}"
            ),
            contract_label=(
                "Contract: NONE"
                if recommendation.contract is None
                else f"Contract: {recommendation.contract}"
            ),
            entry_label=_price_label(
                "Entry",
                recommendation.entry_price,
            ),
            stop_label=_price_label(
                "Stop",
                recommendation.stop_loss,
            ),
            targets_label=_targets_label(
                recommendation.target_1,
                recommendation.target_2,
                recommendation.target_3,
            ),
            confidence_label=(
                f"Confidence: {recommendation.confidence:.0%}"
            ),
            explanation=recommendation.explanation,
        ),
        capital_card=OperatorCapitalCardV1(
            supplied_capital_label=(
                f"Supplied capital: {_money(capital.supplied_capital)}"
            ),
            usable_capital_label=(
                f"Usable capital: {_money(capital.usable_capital)}"
            ),
            position_size_label=(
                f"Position size: {capital.lots} lots / "
                f"{capital.quantity} quantity"
            ),
            capital_required_label=(
                f"Capital required: {_money(capital.capital_required)}"
            ),
            maximum_loss_label=(
                f"Maximum loss: {_money(capital.maximum_loss)}"
            ),
            daily_risk_used_label=(
                f"Daily risk used: {_money(capital.daily_risk_used)}"
            ),
        ),
        active_trade_card=OperatorActiveTradeCardV1(
            status_label=(
                "Active trade: YES"
                if active.active
                else "Active trade: NO"
            ),
            contract_label=(
                "Contract: NONE"
                if active.contract is None
                else f"Contract: {active.contract}"
            ),
            premium_label=(
                "Current premium: N/A"
                if active.current_premium is None
                else (
                    f"Current premium: "
                    f"{active.current_premium:.2f}"
                )
            ),
            pnl_label=f"Unrealized P&L: {_money(active.unrealized_pnl)}",
            target_status_label=(
                f"Target status: {active.target_status}"
            ),
            stop_status_label=f"Stop status: {active.stop_status}",
            instruction_label=f"Instruction: {active.instruction}",
            confidence_warning_label=(
                "Confidence warning: DETERIORATING"
                if active.confidence_deteriorating
                else "Confidence warning: STABLE"
            ),
        ),
        health_card=OperatorHealthCardV1(
            status_label=f"System status: {health.status}",
            data_freshness_label=(
                "Data freshness: FRESH"
                if health.data_fresh
                else "Data freshness: STALE"
            ),
            data_connection_label=(
                f"Data connection: {health.data_connection}"
            ),
            broker_connection_label=(
                f"Broker connection: {health.broker_connection}"
            ),
            mode_label=f"Mode: {health.mode}",
            broker_submission_label=(
                "Broker submission: ENABLED"
                if health.broker_submission_enabled
                else "Broker submission: DISABLED"
            ),
            emergency_halt_label=(
                "Emergency halt: ACTIVE"
                if health.emergency_halt
                else "Emergency halt: CLEAR"
            ),
            runtime_label=(
                "Runtime: HEALTHY"
                if health.runtime_healthy
                else "Runtime: UNHEALTHY"
            ),
            journal_label=(
                "Journal: HEALTHY"
                if health.journal_healthy
                else "Journal: UNHEALTHY"
            ),
            warnings=health.warnings,
        ),
        read_only_notice=(
            "Read-only operator view. No broker order submission."
        ),
    )


def _market_card(
    market: OperatorMarketStateV1,
) -> OperatorMarketCardV1:
    return OperatorMarketCardV1(
        title=market.market,
        exchange=market.exchange,
        score_label=f"Score: {market.score:.2f}",
        confidence_label=f"Confidence: {market.confidence:.0%}",
        direction_label=f"Direction: {market.direction}",
        eligibility_label=(
            "Eligibility: ELIGIBLE"
            if market.eligible
            else "Eligibility: INELIGIBLE"
        ),
        freshness_label=(
            "Data: FRESH"
            if market.data_fresh
            else "Data: STALE"
        ),
        reasons=market.reasons,
        rejection_reasons=market.rejection_reasons,
    )


def _money(value: float) -> str:
    sign = "-" if value < 0.0 else ""
    return f"{sign}₹{abs(value):,.2f}"


def _price_label(name: str, value: float | None) -> str:
    return f"{name}: N/A" if value is None else f"{name}: {value:.2f}"


def _targets_label(
    target_1: float | None,
    target_2: float | None,
    target_3: float | None,
) -> str:
    if target_1 is None or target_2 is None or target_3 is None:
        return "Targets: N/A"
    return (
        f"Targets: T1 {target_1:.2f} | "
        f"T2 {target_2:.2f} | T3 {target_3:.2f}"
    )
