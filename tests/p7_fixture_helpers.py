"""Deterministic, constructor-backed P7 fixtures shared by WP2 tests."""
from datetime import date, datetime, timezone

from services.contracts.capital_quantity_planning_result_v1 import CapitalQuantityPlanningResultV1
from services.contracts.entry_zone_evaluation_result_v1 import EntryZoneEvaluationResultV1
from services.contracts.integrated_three_target_trade_plan_result_v1 import IntegratedThreeTargetTradePlanResultV1
from services.contracts.option_contract_candidate_v1 import OptionContractCandidateV1
from services.contracts.option_contract_selection_result_v1 import OptionContractSelectionResultV1
from services.contracts.option_contract_v1 import OptionContractV1
from services.contracts.paper_market_observation_v1 import PaperMarketObservationV1
from services.contracts.paper_trade_lifecycle_policy_v1 import PaperTradeLifecyclePolicyV1
from services.contracts.paper_trade_lifecycle_state_v1 import PaperTradeLifecycleStateV1
from services.contracts.stop_loss_evaluation_result_v1 import StopLossEvaluationResultV1
from services.contracts.three_target_evaluation_result_v1 import ThreeTargetEvaluationResultV1
from services.contracts.trade_plan_target_v1 import TradePlanTargetV1

NOW = datetime(2026, 1, 8, 9, 30, tzinfo=timezone.utc)

def make_integrated(*, status="READY", symbol="NIFTY26JAN24000CE", underlying="NIFTY", exchange="NSE", direction="BULLISH"):
    right = "CALL" if direction == "BULLISH" else "PUT"
    contract = OptionContractV1("contract-1", underlying, exchange, symbol, right, 24000.0, date(2026, 1, 29), 25, NOW, last_price=100.0, bid_price=99.0, ask_price=101.0)
    candidate = OptionContractCandidateV1(contract, "ELIGIBLE", "ATM", 0.0, 2.0, .7, 1., .5, .5, .5, .5, 1., .7)
    selection = OptionContractSelectionResultV1("selection-result-1", "selection-1", NOW, underlying, exchange, direction, right, "READY", candidate, 1, .7, (), *([True] * 10), 120., .05, 2500., 2)
    entry = EntryZoneEvaluationResultV1("entry-result-1", "entry-evaluation-1", NOW, underlying, exchange, direction, right, "OPTION_MID", "OPTION_MID", "READY", 100., 99., 101., .01, 102., 120., .02, .05, True)
    stop = StopLossEvaluationResultV1("stop-result-1", "stop-evaluation-1", NOW, underlying, exchange, direction, right, "PREMIUM_FRACTION", "PREMIUM_FRACTION", "READY", 90., 100., 10., .1, .05, .2, invalidation_rules=("STOP",))
    targets = ThreeTargetEvaluationResultV1("target-result-1", "target-evaluation-1", NOW, underlying, exchange, direction, right, "RISK_MULTIPLE", "RISK_MULTIPLE", "READY", TradePlanTargetV1(1,110.,.3,10.,1.,"RISK_REDUCTION"), TradePlanTargetV1(2,120.,.4,20.,2.,"PRIMARY"), TradePlanTargetV1(3,130.,.3,30.,3.,"EXTENDED"), 100.,90.,10.,.1,1.,2.,3.,1.,2.,3.)
    capital = CapitalQuantityPlanningResultV1("capital-result-1", "capital-input-1", "plan-1", "capital-policy-1", "selection-result-1", "READY", available_capital=100000., maximum_capital_utilization_fraction=.8, minimum_reserve_capital=10000., deployable_capital=90000., reserved_capital=10000., risk_model="PREMIUM_AT_RISK", maximum_risk_fraction=.1, maximum_risk_amount=10000., effective_risk_budget=10000., per_lot_risk_amount=250., risk_based_lot_limit=10, estimated_one_lot_premium_cost=2500., upstream_affordable_lot_limit=2, deployable_capital_affordable_lot_limit=36, planned_lot_count=2, lot_size=25, planned_quantity=50, estimated_premium_outlay=5000., estimated_risk_amount=500., target_allocation_enabled=True, target_1_lot_count=1, target_2_lot_count=1, target_3_lot_count=0, runner_lot_count=0, evaluated_at=NOW)
    extras = {"blockers": ("BLOCKED",)} if status == "BLOCKED" else {"decision_reasons": ("NO_SIZE",)} if status == "NO_SIZE" else {}
    return IntegratedThreeTargetTradePlanResultV1("integrated-1", status, None, entry, stop, targets, selection, capital, **extras)

def make_policy(**changes):
    values = dict(lifecycle_policy_id="policy-1", policy_timestamp=NOW, policy_source="TEST", entry_timeout_seconds=60, maximum_observation_age_seconds=60, maximum_holding_seconds=120)
    values.update(changes); return PaperTradeLifecyclePolicyV1(**values)

def make_state(*, current_state="PLANNED", **changes):
    values = dict(lifecycle_state_id="state-1", trade_plan_id="plan-1", integrated_trade_plan_result_id="integrated-1", lifecycle_policy_id="policy-1", current_state=current_state, lifecycle_created_at=NOW)
    if current_state == "WAITING_FOR_ENTRY": values.update(previous_state="PLANNED", transition_sequence=1, waiting_for_entry_at=NOW)
    values.update(changes); return PaperTradeLifecycleStateV1(**values)

def make_observation(**changes):
    values = dict(observation_id="obs-1", trade_plan_id="plan-1", integrated_trade_plan_result_id="integrated-1", selected_option_contract_id="contract-1", observed_at=NOW, received_at=NOW, market_session_date=NOW.date(), underlying_symbol="NIFTY", underlying_last_price=24000., option_symbol="NIFTY26JAN24000CE", option_last_price=100., market="NIFTY", exchange="NFO", session_state="OPEN", is_market_open=True, is_expiry_session=False, data_quality_status="FRESH", source="TEST")
    values.update(changes); return PaperMarketObservationV1(**values)

def make_entry_input(**changes):
    from services.contracts.paper_trade_entry_evaluation_input_v1 import PaperTradeEntryEvaluationInputV1
    values = dict(integrated_trade_plan_result=make_integrated(), lifecycle_policy=make_policy(), lifecycle_state=make_state(), observation=make_observation(), evaluation_timestamp=NOW, requested_transition_id="transition-1", position_id="position-1", entry_fill_id="fill-1")
    values.update(changes)
    return PaperTradeEntryEvaluationInputV1(**values)

def make_open_position():
    from services.paper_trading import evaluate_paper_trade_entry
    return evaluate_paper_trade_entry(make_entry_input(observation=make_observation(option_open=100.,option_low=99.,option_high=101.,option_close=100.))).position

def make_open_state():
    return PaperTradeLifecycleStateV1("state-open","plan-1","integrated-1","policy-1","OPEN",NOW,previous_state="WAITING_FOR_ENTRY",transition_sequence=2,opened_at=NOW)
