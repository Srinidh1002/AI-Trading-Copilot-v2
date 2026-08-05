from dataclasses import replace
from datetime import timedelta

from services.contracts.paper_certification_reporting_v1 import (
    CertificationDuplicateAttemptV1,
    CertificationIncidentV1,
    PredictionCertificationAnalyticsContextV1,
)
from services.contracts.prediction_certification_counting_decision_v1 import (
    PredictionCertificationCountingDecisionV1,
)
from services.contracts.prediction_lifecycle_outcome_record_v1 import (
    PredictionLifecycleOutcomeRecordV1,
)
from services.contracts.prediction_lifecycle_reconciliation_result_v1 import (
    PredictionLifecycleReconciliationResultV1,
)
from services.contracts.paper_trade_fill_v1 import (
    PaperTradeFillV1,
)
from services.contracts.paper_trade_position_v1 import (
    PaperTradePositionV1,
)
from services.contracts.prediction_record_v1 import (
    PredictionRecordV1,
)
from services.reports.paper_certification_daily_report import (
    build_paper_certification_daily_report,
)
NOW = __import__("datetime").datetime(
    2026, 8, 5, 9, 30,
    tzinfo=__import__("datetime").timezone.utc,
)


def call_prediction():
    return PredictionRecordV1(
        prediction_id="prediction:parent-call:NIFTY:NSE",
        parent_cycle_id="parent-call",
        decision_result_id="decision-call",
        child_result_id="child-call",
        observation_id="observation-call",
        underlying_symbol="NIFTY",
        exchange="NSE",
        requested_at=NOW - timedelta(minutes=2),
        completed_at=NOW - timedelta(minutes=1),
        market_timestamp=NOW - timedelta(minutes=1),
        received_at=NOW - timedelta(minutes=1),
        start_underlying_price=24000.0,
        terminal_status="COMPLETED",
        candidate_id="candidate-call",
        predicted_direction="BULLISH",
        predicted_action="CALL",
        eligibility="ELIGIBLE",
        confidence=80.0,
        score=80.0,
        rank_value=80.0,
        eligible_for_comparison=True,
        outcome_reason="SELECTED",
        parent_decision="SELECTED",
        parent_selected=True,
    )


def wait_prediction():
    return PredictionRecordV1(
        prediction_id="prediction:parent-wait:NIFTY:NSE",
        parent_cycle_id="parent-wait",
        decision_result_id="decision-wait",
        child_result_id="child-wait",
        observation_id="observation-wait",
        underlying_symbol="NIFTY",
        exchange="NSE",
        requested_at=NOW - timedelta(minutes=2),
        completed_at=NOW - timedelta(minutes=1),
        market_timestamp=NOW - timedelta(minutes=1),
        received_at=NOW - timedelta(minutes=1),
        start_underlying_price=24000.0,
        terminal_status="COMPLETED",
        candidate_id=None,
        predicted_direction="NEUTRAL",
        predicted_action="WAIT",
        eligibility="INELIGIBLE",
        confidence=0.0,
        score=0.0,
        rank_value=0.0,
        eligible_for_comparison=False,
        outcome_reason="INELIGIBLE",
        parent_decision="NO_TRADE",
        parent_selected=False,
    )


def excluded_prediction():
    return PredictionRecordV1(
        prediction_id="prediction:parent-replay:SENSEX:BSE",
        parent_cycle_id="parent-replay",
        decision_result_id="decision-replay",
        child_result_id="child-replay",
        observation_id="observation-replay",
        underlying_symbol="SENSEX",
        exchange="BSE",
        requested_at=NOW - timedelta(minutes=2),
        completed_at=NOW - timedelta(minutes=1),
        market_timestamp=NOW - timedelta(minutes=1),
        received_at=NOW - timedelta(minutes=1),
        start_underlying_price=80000.0,
        terminal_status="COMPLETED",
        candidate_id=None,
        predicted_direction="NEUTRAL",
        predicted_action="WAIT",
        eligibility="INELIGIBLE",
        confidence=0.0,
        score=0.0,
        rank_value=0.0,
        eligible_for_comparison=False,
        outcome_reason="INELIGIBLE",
        parent_decision="NO_TRADE",
        parent_selected=False,
    )


def excluded_counting_decision(prediction):
    return PredictionCertificationCountingDecisionV1(
        decision_id="counting-decision-replay",
        counting_key="c" * 64,
        prediction_id=prediction.prediction_id,
        outcome_id=None,
        official_run_id="official-run",
        underlying_symbol=prediction.underlying_symbol,
        exchange=prediction.exchange,
        predicted_action=prediction.predicted_action,
        parent_decision=prediction.parent_decision,
        status="EXCLUDED_REPLAY",
        countable=False,
        pending=False,
        reason_codes=("RECORD_SOURCE_REPLAY",),
        policy_id="counting-policy",
        policy_version="1.0",
        system_version="system-1",
        provider_version="provider-1",
        evaluated_at=NOW,
    )


def counting_decision(prediction, token):
    return PredictionCertificationCountingDecisionV1(
        decision_id=f"counting-decision-{token}",
        counting_key=(token * 64)[:64],
        prediction_id=prediction.prediction_id,
        outcome_id=f"basic-outcome-{token}",
        official_run_id="official-run",
        underlying_symbol=prediction.underlying_symbol,
        exchange=prediction.exchange,
        predicted_action=prediction.predicted_action,
        parent_decision=prediction.parent_decision,
        status="INCLUDED",
        countable=True,
        pending=False,
        reason_codes=(),
        policy_id="counting-policy",
        policy_version="1.0",
        system_version="system-1",
        provider_version="provider-1",
        evaluated_at=NOW,
    )


def stopped_position():
    entry = PaperTradeFillV1(
        fill_id="entry-r79",
        trade_plan_id="plan-r79",
        integrated_trade_plan_result_id="integrated-r79",
        position_id="position-r79",
        observation_id="observation-entry-r79",
        selected_option_contract_id="contract-r79",
        fill_type="ENTRY",
        fill_reason="ENTRY_ACTIVATED",
        side="BUY",
        filled_lot_count=2,
        lot_size=25,
        filled_quantity=50,
        fill_price=100.0,
        gross_notional=5000.0,
        estimated_trading_cost=5.0,
        net_cash_effect=-5005.0,
        filled_at=NOW,
        source="R79_TEST",
    )
    exit_fill = PaperTradeFillV1(
        fill_id="exit-r79",
        trade_plan_id="plan-r79",
        integrated_trade_plan_result_id="integrated-r79",
        position_id="position-r79",
        observation_id="observation-exit-r79",
        selected_option_contract_id="contract-r79",
        fill_type="EXIT",
        fill_reason="STOP",
        side="SELL",
        filled_lot_count=2,
        lot_size=25,
        filled_quantity=50,
        fill_price=90.0,
        gross_notional=4500.0,
        estimated_trading_cost=5.0,
        net_cash_effect=4495.0,
        filled_at=NOW + timedelta(minutes=5),
        source="R79_TEST",
    )
    return PaperTradePositionV1(
        position_id="position-r79",
        trade_plan_id="plan-r79",
        integrated_trade_plan_result_id="integrated-r79",
        lifecycle_policy_id="lifecycle-policy-r79",
        lifecycle_state_id="lifecycle-state-r79",
        selected_option_contract_id="contract-r79",
        market="NIFTY",
        underlying_symbol="NIFTY",
        option_symbol="NIFTY26AUG24000CE",
        direction="BULLISH",
        option_type="CALL",
        strike=24000.0,
        expiry="2026-08-27",
        entry_fill=entry,
        entry_price=100.0,
        opened_at=NOW,
        initial_lot_count=2,
        lot_size=25,
        initial_quantity=50,
        remaining_lot_count=0,
        remaining_quantity=0,
        target_1_lot_count=1,
        target_2_lot_count=1,
        target_3_lot_count=0,
        runner_lot_count=0,
        stop_loss=90.0,
        target_1=110.0,
        target_2=120.0,
        target_3=130.0,
        estimated_premium_outlay=5000.0,
        estimated_risk_amount=500.0,
        estimated_total_trading_cost=10.0,
        estimated_total_capital_requirement=5010.0,
        lifecycle_state="CLOSED_STOP",
        exit_fills=(exit_fill,),
        realized_gross_pnl=-500.0,
        realized_net_pnl=-510.0,
        unrealized_pnl=0.0,
        total_pnl=-510.0,
        exchange="NSE",
    )


def call_outcome(prediction, position):
    fill = position.exit_fills[-1]
    return PredictionLifecycleOutcomeRecordV1(
        outcome_id="lifecycle-outcome-call",
        prediction_id=prediction.prediction_id,
        parent_cycle_id=prediction.parent_cycle_id,
        decision_result_id=prediction.decision_result_id,
        window_id="window-call",
        underlying_symbol=prediction.underlying_symbol,
        exchange=prediction.exchange,
        predicted_action=prediction.predicted_action,
        policy_id="lifecycle-policy",
        policy_version="1.0",
        evaluated_at=NOW,
        evaluation_status="RESOLVED",
        outcome="STOP_HIT",
        entry_occurred=True,
        entry_at=position.opened_at,
        entry_premium=position.entry_price,
        highest_target_reached=0,
        terminal_event_type="STOP",
        terminal_event_at=fill.filled_at,
        terminal_option_premium=fill.fill_price,
        maximum_up_move_percent=0.0,
        maximum_down_move_percent=0.5,
        maximum_absolute_move_percent=0.5,
        evidence_observation_ids=("obs-call",),
    )


def wait_outcome(prediction):
    return PredictionLifecycleOutcomeRecordV1(
        outcome_id="lifecycle-outcome-wait",
        prediction_id=prediction.prediction_id,
        parent_cycle_id=prediction.parent_cycle_id,
        decision_result_id=prediction.decision_result_id,
        window_id="window-wait",
        underlying_symbol=prediction.underlying_symbol,
        exchange=prediction.exchange,
        predicted_action=prediction.predicted_action,
        policy_id="lifecycle-policy",
        policy_version="1.0",
        evaluated_at=NOW,
        evaluation_status="RESOLVED",
        outcome="NO_TRADE_CORRECT",
        entry_occurred=False,
        entry_at=None,
        entry_premium=None,
        highest_target_reached=0,
        terminal_event_type="VALIDITY_WINDOW_END",
        terminal_event_at=NOW,
        terminal_option_premium=None,
        maximum_up_move_percent=0.05,
        maximum_down_move_percent=0.05,
        maximum_absolute_move_percent=0.05,
        evidence_observation_ids=("obs-wait",),
    )


def reconciliation(prediction, outcome, position=None):
    return PredictionLifecycleReconciliationResultV1(
        reconciliation_id=(
            f"reconciliation:{prediction.prediction_id}"
        ),
        prediction_id=prediction.prediction_id,
        lifecycle_outcome_id=outcome.outcome_id,
        position_id=(
            position.position_id
            if position is not None
            else None
        ),
        underlying_symbol=prediction.underlying_symbol,
        exchange=prediction.exchange,
        predicted_action=prediction.predicted_action,
        lifecycle_outcome=outcome.outcome,
        position_lifecycle_state=(
            position.lifecycle_state
            if position is not None
            else None
        ),
        reconciled_at=NOW,
        status="RECONCILED",
        reconciliation_complete=True,
        counting_eligible=True,
        identity_matches=True,
        entry_matches=(
            True if position is not None else None
        ),
        terminal_matches=(
            True if position is not None else None
        ),
        fill_sequence_matches=(
            True if position is not None else None
        ),
        quantity_matches=(
            True if position is not None else None
        ),
        pnl_matches=(
            True if position is not None else None
        ),
    )


def build_daily(
    report_id="daily-1",
    starting_capital=100000.0,
    include_excluded=False,
):
    call = call_prediction()
    wait = wait_prediction()
    replay = excluded_prediction() if include_excluded else None
    position = stopped_position()
    call_result = call_outcome(call, position)
    wait_result = wait_outcome(wait)

    contexts = (
        PredictionCertificationAnalyticsContextV1(
            prediction_id=call.prediction_id,
            confidence_band="HIGH",
            regime="TRENDING",
            time_of_day="OPENING",
            contract_quality="GOOD",
            spread_quality="TIGHT",
            liquidity_quality="GOOD",
            engine_contributions=(
                ("TECHNICAL", 60.0),
                ("OPTION_CHAIN", 40.0),
            ),
            pillar_contributions=(
                ("MOMENTUM", 55.0),
                ("LIQUIDITY", 45.0),
            ),
        ),
        PredictionCertificationAnalyticsContextV1(
            prediction_id=wait.prediction_id,
            confidence_band="LOW",
            regime="RANGE",
            time_of_day="OPENING",
            contract_quality="UNAVAILABLE",
            spread_quality="UNAVAILABLE",
            liquidity_quality="UNAVAILABLE",
        ),
    )

    return build_paper_certification_daily_report(
        report_id=report_id,
        session_date=NOW.date(),
        generated_at=NOW + timedelta(hours=1),
        starting_capital=starting_capital,
        predictions=(
            (call, wait, replay)
            if replay is not None
            else (call, wait)
        ),
        counting_decisions=(
            (
                counting_decision(call, "a"),
                counting_decision(wait, "b"),
                excluded_counting_decision(replay),
            )
            if replay is not None
            else (
                counting_decision(call, "a"),
                counting_decision(wait, "b"),
            )
        ),
        lifecycle_outcomes=(call_result, wait_result),
        reconciliations=(
            reconciliation(call, call_result, position),
            reconciliation(wait, wait_result),
        ),
        positions=(position,),
        analytics_contexts=contexts,
        incidents=(
            CertificationIncidentV1(
                incident_id="incident-1",
                occurred_at=NOW,
                incident_type="DATA_PROVIDER",
                severity="WARNING",
                code="THROTTLED",
                resolved=True,
                market="NIFTY",
            ),
        ),
        duplicate_attempts=(
            CertificationDuplicateAttemptV1(
                attempt_id="duplicate-1",
                occurred_at=NOW,
                duplicate_type="PREDICTION",
                blocked=True,
                reference_id=call.prediction_id,
                market="NIFTY",
                reason_codes=("IDEMPOTENCY_HIT",),
            ),
        ),
    )


def clone_daily(report, *, report_id, day_offset):
    session_date = report.session_date + timedelta(
        days=day_offset
    )
    facts = tuple(
        replace(
            item,
            prediction_id=(
                f"{item.prediction_id}:day-{day_offset}"
            ),
            parent_cycle_id=(
                f"{item.parent_cycle_id}:day-{day_offset}"
            ),
        )
        for item in report.prediction_facts
    )
    incidents = tuple(
        replace(
            item,
            incident_id=f"{item.incident_id}:day-{day_offset}",
            occurred_at=item.occurred_at
            + timedelta(days=day_offset),
        )
        for item in report.incidents
    )
    duplicates = tuple(
        replace(
            item,
            attempt_id=f"{item.attempt_id}:day-{day_offset}",
            occurred_at=item.occurred_at
            + timedelta(days=day_offset),
            reference_id=(
                f"{item.reference_id}:day-{day_offset}"
            ),
        )
        for item in report.duplicate_attempts
    )
    return replace(
        report,
        report_id=report_id,
        session_date=session_date,
        generated_at=report.generated_at
        + timedelta(days=day_offset),
        starting_capital=report.ending_capital,
        ending_capital=report.ending_capital + report.net_pnl,
        prediction_facts=facts,
        incidents=incidents,
        duplicate_attempts=duplicates,
    )
