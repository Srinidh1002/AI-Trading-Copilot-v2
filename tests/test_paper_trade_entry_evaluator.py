from dataclasses import replace
from datetime import timedelta
import pytest
from services.paper_trading import evaluate_paper_trade_entry
from tests.p7_fixture_helpers import NOW, make_entry_input, make_integrated, make_observation, make_policy, make_state

def run(**changes): return evaluate_paper_trade_entry(make_entry_input(**changes))
def ohlc(last=100., low=99., high=101., open_=100., close=100., **changes): return make_observation(option_last_price=last,option_low=low,option_high=high,option_open=open_,option_close=close,**changes)
def at(timestamp): return replace(ohlc(), observed_at=timestamp, received_at=timestamp)

@pytest.mark.parametrize("case,observation,status", [("inside",ohlc(),"OPEN"),("lower",ohlc(last=99.,low=99.,high=99.,open_=99.,close=99.),"OPEN"),("upper",ohlc(last=101.,low=101.,high=101.,open_=101.,close=101.),"OPEN"),("range-overlap",ohlc(last=102.,low=98.,high=102.,open_=102.,close=102.),"OPEN"),("below",ohlc(last=98.,low=97.,high=98.,open_=98.,close=98.),"WAITING_FOR_ENTRY"),("above",ohlc(last=102.,low=102.,high=103.,open_=102.,close=102.),"WAITING_FOR_ENTRY")])
def test_zone_touch_matrix(case,observation,status): assert run(observation=observation).status==status

@pytest.mark.parametrize("close,status", [(100.,"OPEN"),(99.,"OPEN"),(101.,"OPEN"),(98.,"WAITING_FOR_ENTRY"),(102.,"WAITING_FOR_ENTRY")])
def test_zone_close_matrix(close,status): assert run(lifecycle_policy=make_policy(entry_activation_mode="ZONE_CLOSE"),observation=ohlc(close=close,last=close,low=close,high=close,open_=close)).status==status
def test_zone_close_requires_close_and_gap_does_not_override():
    assert run(lifecycle_policy=make_policy(entry_activation_mode="ZONE_CLOSE",allow_gap_entry=True),observation=make_observation(option_last_price=110.)).status=="BLOCKED"

def test_tolerance_and_original_zone_provenance():
    value=run(lifecycle_policy=make_policy(entry_zone_tolerance_fraction=.01),observation=ohlc(last=98.,low=98.,high=98.,open_=98.,close=98.))
    assert value.status=="OPEN" and (value.effective_entry_zone_lower,value.effective_entry_zone_upper)==(98.,102.) and value.metadata["original_entry_zone_lower"]==99.

@pytest.mark.parametrize("allow,status", [(True,"OPEN"),(False,"WAITING_FOR_ENTRY")])
def test_upward_gap_policy_and_p6_copy_authority(allow,status):
    value=run(lifecycle_policy=make_policy(allow_gap_entry=allow),observation=ohlc(last=110.,low=110.,high=111.,open_=110.,close=110.))
    assert value.status==status
    if allow:
      p=value.position;c=make_integrated().capital_quantity_result; assert value.entry_fill.fill_price==110. and "GAP_ENTRY_ACTIVATED" in value.warnings and (p.initial_lot_count,p.initial_quantity,p.estimated_risk_amount,p.estimated_premium_outlay)==(c.planned_lot_count,c.planned_quantity,c.estimated_risk_amount,c.estimated_premium_outlay)

@pytest.mark.parametrize("age,status", [(0,"OPEN"),(60,"OPEN"),(61,"BLOCKED")])
def test_freshness_boundaries(age,status): assert run(evaluation_timestamp=NOW+timedelta(seconds=age),observation=ohlc()).status==status
def test_future_duplicate_and_ordering_are_fail_closed_or_noop():
    assert run(evaluation_timestamp=NOW-timedelta(seconds=1),observation=ohlc()).blockers==("OBSERVATION_FROM_FUTURE",)
    state=make_state(last_observation_id="obs-1",last_observation_timestamp=NOW); assert run(lifecycle_state=state,observation=ohlc()).decision_reasons==("DUPLICATE_OBSERVATION_IGNORED",)
    state=make_state(last_observation_id="other",last_observation_timestamp=NOW+timedelta(seconds=1)); assert run(lifecycle_state=state,observation=ohlc()).blockers==("OUT_OF_ORDER_OBSERVATION",)

@pytest.mark.parametrize("session,close,status", [("PRE_OPEN",False,"WAITING_FOR_ENTRY"),("ENTRY_CUTOFF",True,"CLOSED_SESSION"),("POSITION_MANAGEMENT",True,"CLOSED_SESSION"),("CLOSED",False,"WAITING_FOR_ENTRY"),("HOLIDAY",True,"CLOSED_SESSION"),("UNKNOWN",True,"BLOCKED")])
def test_session_matrix(session,close,status):
    value=run(lifecycle_policy=make_policy(close_at_session_end=close),observation=ohlc(session_state=session,is_market_open=False)); assert value.status==status and (value.position is None)

@pytest.mark.parametrize("days,close,status", [(-1,True,"OPEN"),(0,True,"CLOSED_EXPIRY"),(1,True,"CLOSED_EXPIRY"),(0,False,"WAITING_FOR_ENTRY")])
def test_expiry_matrix(days,close,status):
    timestamp=NOW.replace(day=29)+timedelta(days=days); value=run(lifecycle_policy=make_policy(close_at_expiry=close),lifecycle_state=make_state(lifecycle_created_at=timestamp),evaluation_timestamp=timestamp,observation=at(timestamp)); assert value.status==status and (value.position is None if status!="OPEN" else value.position is not None)

@pytest.mark.parametrize("seconds,status", [(59,"OPEN"),(60,"OPEN"),(61,"CLOSED_INVALIDATED")])
def test_timeout_strict_boundary(seconds,status): assert run(lifecycle_policy=make_policy(require_fresh_observation=False),evaluation_timestamp=NOW+timedelta(seconds=seconds),observation=ohlc()).status==status

@pytest.mark.parametrize("kind", ("BLOCKED","WAITING","OPEN","EXPIRY"))
def test_ten_run_determinism(kind):
    if kind=="BLOCKED": value=make_entry_input(observation=make_observation(data_quality_status="INVALID"))
    elif kind=="WAITING": value=make_entry_input(observation=ohlc(last=110.,low=110.,high=111.,open_=110.,close=110.))
    elif kind=="EXPIRY": value=make_entry_input(evaluation_timestamp=NOW.replace(day=29))
    else: value=make_entry_input(observation=ohlc())
    results=[evaluate_paper_trade_entry(value) for _ in range(10)]; assert all(x==results[0] and x.to_json()==results[0].to_json() and x.to_dict()==results[0].to_dict() for x in results)

def test_evaluator_export(): assert callable(evaluate_paper_trade_entry)
