"""Certification matrix for deterministic PAPER position evaluation."""
from datetime import timedelta
from dataclasses import replace

import pytest

from services.contracts import PaperTradePositionEvaluationInputV1
from services.paper_trading import evaluate_open_paper_trade_position
from tests.p7_fixture_helpers import NOW, make_observation, make_open_position, make_open_state, make_policy


def evaluate(*, observation=None, policy=None, state=None, ids=('exit-a', 'exit-b', 'exit-c'), pnl_id='pnl-matrix', **changes):
    values = dict(
        position=make_open_position(), lifecycle_policy=policy or make_policy(allow_partial_exits=True),
        lifecycle_state=state or make_open_state(), observation=observation or make_observation(),
        evaluation_timestamp=NOW, requested_transition_id='transition-matrix',
        resulting_lifecycle_state_id='state-matrix', evaluation_result_id='result-matrix',
        exit_fill_ids=ids, pnl_evidence_id=pnl_id,
    )
    values.update(changes)
    return evaluate_open_paper_trade_position(PaperTradePositionEvaluationInputV1(**values))


@pytest.mark.parametrize('stop_mode,target_mode', [
    ('TOUCH', 'TOUCH'), ('CLOSE', 'CLOSE'), ('TOUCH', 'CLOSE'), ('CLOSE', 'TOUCH'),
])
@pytest.mark.parametrize('price,low,high,expected', [
    (100., 99., 101., 'OPEN'),
    (110., 109., 111., 'PARTIALLY_EXITED'),
    (120., 119., 121., 'CLOSED_TARGET_2'),
    (90., 89., 91., 'CLOSED_STOP'),
    (90., 89., 111., 'CLOSED_STOP'),
])
def test_trigger_modes_use_deterministic_price_boundaries(stop_mode, target_mode, price, low, high, expected):
    policy = make_policy(allow_partial_exits=True, stop_trigger_mode=stop_mode, target_trigger_mode=target_mode)
    result = evaluate(policy=policy, observation=make_observation(option_last_price=price, option_open=price, option_low=low, option_high=high, option_close=price))
    assert result.status == expected
    assert result.resulting_position.lifecycle_state == expected


@pytest.mark.parametrize('cost_name,reason,price', [
    ('target_1_exit_cost', 'TARGET_1', 110.), ('target_2_exit_cost', 'TARGET_2', 120.),
    ('target_3_exit_cost', None, 130.), ('stop_exit_cost', 'STOP', 90.),
    ('session_exit_cost', 'SESSION_CLOSE', 100.), ('expiry_exit_cost', 'EXPIRY_CLOSE', 100.),
    ('invalidation_exit_cost', 'INVALIDATION', 100.), ('runner_exit_cost', None, 130.),
])
def test_exit_costs_are_reflected_in_generated_fills(cost_name, reason, price):
    cost = 3.25
    kwargs = {cost_name: cost}
    observation = make_observation(option_last_price=price, option_open=price, option_low=price - 1, option_high=max(price + 1, 131.), option_close=price)
    policy = make_policy(allow_partial_exits=True)
    if cost_name == 'session_exit_cost':
        observation = make_observation(session_state='CLOSED', is_market_open=False)
    elif cost_name == 'expiry_exit_cost':
        expiry = NOW.replace(day=29)
        observation = make_observation(observed_at=expiry, received_at=expiry)
        kwargs['evaluation_timestamp'] = expiry
    elif cost_name == 'invalidation_exit_cost':
        kwargs.update(invalidation_status='TRIGGERED', invalidation_reason_code='RISK_INVALID')
    result = evaluate(policy=policy, observation=observation, pnl_id='pnl-' + cost_name, **kwargs)
    matching = [fill for fill in result.generated_exit_fills if fill.fill_reason == reason]
    if reason is None:
        assert result.pnl_evidence.exit_trading_cost_delta == 0.
    else:
        assert matching and matching[-1].estimated_trading_cost == cost
        assert result.pnl_evidence.exit_trading_cost_delta >= cost


@pytest.mark.parametrize('kind', ['future', 'stale', 'out_of_order', 'duplicate', 'invalid_quality'])
def test_observation_safety_controls_fail_closed_or_hold(kind):
    if kind == 'future':
        later = NOW + timedelta(seconds=1)
        result = evaluate(observation=make_observation(observed_at=later, received_at=later))
        assert result.status == 'BLOCKED' and result.blockers == ('OBSERVATION_FROM_FUTURE',)
    elif kind == 'stale':
        earlier = NOW - timedelta(seconds=61)
        result = evaluate(observation=make_observation(observed_at=earlier, received_at=earlier))
        assert result.status == 'BLOCKED' and result.blockers == ('STALE_OBSERVATION',)
    elif kind == 'out_of_order':
        earlier = NOW - timedelta(seconds=1)
        state = replace(make_open_state(), last_observation_id='newer', last_observation_timestamp=NOW)
        result = evaluate(state=state, observation=make_observation(observed_at=earlier, received_at=earlier))
        assert result.status == 'BLOCKED' and result.blockers == ('OUT_OF_ORDER_OBSERVATION',)
    elif kind == 'duplicate':
        source_position = make_open_position()
        state = replace(make_open_state(), last_observation_id='obs-1', last_observation_timestamp=NOW)
        result = evaluate(position=source_position, state=state)
        assert result.status == 'OPEN' and result.position_decision == 'HOLD' and result.observation_order_valid is False
        assert result.resulting_position is source_position and result.pnl_evidence is None
    else:
        result = evaluate(observation=make_observation(data_quality_status='INVALID'))
        assert result.status == 'BLOCKED' and result.blockers == ('INVALID_DATA_QUALITY',)


@pytest.mark.parametrize('precedence,expected,fill_reasons', [
    ('STOP_FIRST', 'CLOSED_STOP', ('STOP',)),
    ('CONSERVATIVE_STOP_FIRST', 'CLOSED_STOP', ('STOP',)),
    ('TARGET_FIRST', 'CLOSED_STOP', ('TARGET_1', 'STOP')),
    ('TARGET_FIRST', 'CLOSED_STOP', ('TARGET_1', 'STOP')),
    ('SEQUENTIAL_TARGETS', 'CLOSED_TARGET_2', ('TARGET_1', 'TARGET_2')),
])
def test_precedence_and_target_progression(precedence, expected, fill_reasons):
    policy_changes = dict(allow_partial_exits=True)
    price, low, high = 110., 89., 111.
    if precedence == 'SEQUENTIAL_TARGETS':
        policy_changes['multiple_target_crossing_mode'] = precedence
        price, low, high = 120., 119., 121.
    else:
        policy_changes['same_observation_precedence'] = precedence
    result = evaluate(policy=make_policy(**policy_changes), observation=make_observation(option_last_price=price, option_open=price, option_low=low, option_high=high, option_close=price))
    assert result.status == expected
    assert tuple(fill.fill_reason for fill in result.generated_exit_fills) == fill_reasons


@pytest.mark.parametrize('price', [90., 95., 100., 105., 110., 115., 120., 125.])
def test_same_input_replays_to_byte_identical_result(price):
    observation = make_observation(option_last_price=price, option_open=price, option_low=price - 1, option_high=price + 1, option_close=price)
    first = evaluate(observation=observation, pnl_id='pnl-replay-' + str(price))
    second = evaluate(observation=observation, pnl_id='pnl-replay-' + str(price))
    assert first.to_json() == second.to_json()


@pytest.mark.parametrize('first_price,second_price,expected', [
    (110., 120., 'CLOSED_TARGET_2'), (110., 90., 'CLOSED_STOP'),
    (100., 110., 'PARTIALLY_EXITED'), (110., 130., 'CLOSED_TARGET_2'),
])
def test_replay_chains_real_lifecycle_snapshots(first_price, second_price, expected):
    first_observation = make_observation(observation_id='first-' + str(first_price), option_last_price=first_price, option_open=first_price, option_low=first_price - 1, option_high=first_price + 1, option_close=first_price)
    first = evaluate(observation=first_observation, ids=('first-a', 'first-b', 'first-c'), pnl_id='first-pnl-' + str(first_price))
    later = NOW + timedelta(seconds=1)
    second_observation = make_observation(observation_id='second-' + str(second_price), observed_at=later, received_at=later, option_last_price=second_price, option_open=second_price, option_low=second_price - 1, option_high=second_price + 1, option_close=second_price)
    result = evaluate(position=first.resulting_position, state=first.resulting_lifecycle_state, observation=second_observation, ids=('second-a', 'second-b', 'second-c'), pnl_id='second-pnl-' + str(second_price), evaluation_timestamp=later)
    assert result.status == expected
    assert result.resulting_lifecycle_state.previous_state == first.status
