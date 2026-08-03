"""R4.3 continuous PAPER position monitoring certification."""

from dataclasses import replace
from datetime import timedelta

import pytest

from services.paper_orchestration.continuous_position_monitoring_runtime import (
    ContinuousPositionMonitoringResultV1,
    execute_continuous_position_monitoring,
)
from tests.test_r42_admitted_plan_simulated_entry_runtime import (
    _admitted_runtime_args,
)


def _open_runtime(tmp_path):
    from services.paper_orchestration.admitted_plan_simulated_entry_runtime import (
        execute_admitted_plan_simulated_entry,
    )

    entry_args, portfolio_service, trade_service = (
        _admitted_runtime_args(tmp_path)
    )

    entry_result = execute_admitted_plan_simulated_entry(
        **entry_args
    )

    assert entry_result.status == "OPEN"

    persisted_trade = trade_service.get(
        entry_args["paper_trade_id"]
    )
    assert persisted_trade is not None
    assert persisted_trade.position is not None

    return (
        entry_args,
        persisted_trade,
        portfolio_service,
        trade_service,
    )


def _monitoring_args(
    *,
    entry_args,
    persisted_trade,
    portfolio_service,
    trade_service,
    observation,
    evaluation_timestamp,
    suffix,
):
    return {
        "portfolio_id": entry_args["portfolio_id"],
        "paper_trade_id": entry_args["paper_trade_id"],
        "portfolio_policy": entry_args["portfolio_policy"],
        "observation": observation,
        "evaluation_timestamp": evaluation_timestamp,
        "requested_transition_id": (
            f"r43-transition-{suffix}"
        ),
        "resulting_lifecycle_state_id": (
            f"r43-state-{suffix}"
        ),
        "evaluation_result_id": (
            f"r43-evaluation-{suffix}"
        ),
        "exit_fill_ids": (
            f"r43-exit-{suffix}-1",
            f"r43-exit-{suffix}-2",
            f"r43-exit-{suffix}-3",
            f"r43-exit-{suffix}-4",
        ),
        "pnl_evidence_id": f"r43-pnl-{suffix}",
        "result_snapshot_id": (
            f"r43-portfolio-{suffix}"
        ),
        "portfolio_event_id": (
            f"r43-portfolio-event-{suffix}"
        ),
        "update_idempotency_key": (
            f"r43-update-{suffix}"
        ),
        "portfolio_persistence_service": (
            portfolio_service
        ),
        "trade_persistence_service": trade_service,
    }


def _next_observation(
    persisted_trade,
    *,
    suffix,
    price,
    seconds=1,
):
    prior = persisted_trade.latest_observation
    assert prior is not None

    observed_at = prior.observed_at + timedelta(
        seconds=seconds
    )

    return replace(
        prior,
        observation_id=f"r43-observation-{suffix}",
        observed_at=observed_at,
        received_at=observed_at,
        option_last_price=price,
        option_open=price,
        option_low=price,
        option_high=price,
        option_close=price,
    )


def test_hold_updates_p7_and_p8_without_paper_action(tmp_path):
    (
        entry_args,
        persisted_trade,
        portfolio_service,
        trade_service,
    ) = _open_runtime(tmp_path)

    position = persisted_trade.position
    assert position is not None

    observation = _next_observation(
        persisted_trade,
        suffix="hold",
        price=position.entry_price + 1.0,
    )

    args = _monitoring_args(
        entry_args=entry_args,
        persisted_trade=persisted_trade,
        portfolio_service=portfolio_service,
        trade_service=trade_service,
        observation=observation,
        evaluation_timestamp=observation.observed_at,
        suffix="hold",
    )

    result = execute_continuous_position_monitoring(
        **args
    )

    assert type(result) is ContinuousPositionMonitoringResultV1
    assert result.status == "HOLD_UPDATED"
    assert result.p7_state_changed is True
    assert result.p8_state_changed is True
    assert result.paper_action_occurred is False

    updated_trade = trade_service.get(
        entry_args["paper_trade_id"]
    )
    assert updated_trade is not None
    assert (
        updated_trade.latest_observation.observation_id
        == observation.observation_id
    )
    assert updated_trade.position is not None
    assert (
        updated_trade.position.lifecycle_state
        == "OPEN"
    )

    updated_portfolio = portfolio_service.get(
        entry_args["portfolio_id"]
    )
    assert updated_portfolio is not None
    reference = (
        updated_portfolio.portfolio_snapshot
        .position_references[0]
    )
    assert (
        reference.last_observation_id
        == observation.observation_id
    )


def test_target_one_creates_partial_exit_and_persists_p7_p8(
    tmp_path,
):
    (
        entry_args,
        persisted_trade,
        portfolio_service,
        trade_service,
    ) = _open_runtime(tmp_path)

    position = persisted_trade.position
    assert position is not None

    observation = _next_observation(
        persisted_trade,
        suffix="target-one",
        price=position.target_1,
    )

    args = _monitoring_args(
        entry_args=entry_args,
        persisted_trade=persisted_trade,
        portfolio_service=portfolio_service,
        trade_service=trade_service,
        observation=observation,
        evaluation_timestamp=observation.observed_at,
        suffix="target-one",
    )

    result = execute_continuous_position_monitoring(
        **args
    )

    assert result.status == "PARTIAL_EXIT"
    assert result.paper_action_occurred is True
    assert result.p7_state_changed is True
    assert result.p8_state_changed is True

    updated_trade = trade_service.get(
        entry_args["paper_trade_id"]
    )
    assert updated_trade is not None
    assert updated_trade.position is not None
    assert (
        updated_trade.position.lifecycle_state
        == "PARTIALLY_EXITED"
    )
    assert len(updated_trade.position.exit_fills) == 1
    assert (
        updated_trade.position.exit_fills[0].fill_reason
        == "TARGET_1"
    )

    updated_portfolio = portfolio_service.get(
        entry_args["portfolio_id"]
    )
    assert updated_portfolio is not None
    reference = (
        updated_portfolio.portfolio_snapshot
        .position_references[0]
    )
    assert reference.lifecycle_state == "PARTIALLY_EXITED"
    assert len(reference.exit_fill_ids) == 1


def test_stop_closes_position_and_releases_reservation(
    tmp_path,
):
    (
        entry_args,
        persisted_trade,
        portfolio_service,
        trade_service,
    ) = _open_runtime(tmp_path)

    position = persisted_trade.position
    assert position is not None

    observation = _next_observation(
        persisted_trade,
        suffix="stop",
        price=position.stop_loss,
    )

    args = _monitoring_args(
        entry_args=entry_args,
        persisted_trade=persisted_trade,
        portfolio_service=portfolio_service,
        trade_service=trade_service,
        observation=observation,
        evaluation_timestamp=observation.observed_at,
        suffix="stop",
    )

    result = execute_continuous_position_monitoring(
        **args
    )

    assert result.status == "CLOSED"
    assert result.paper_action_occurred is True

    updated_trade = trade_service.get(
        entry_args["paper_trade_id"]
    )
    assert updated_trade is not None
    assert updated_trade.position is not None
    assert (
        updated_trade.position.lifecycle_state
        == "CLOSED_STOP"
    )
    assert updated_trade.position.remaining_quantity == 0
    assert (
        updated_trade.position.exit_fills[-1].fill_reason
        == "STOP"
    )

    updated_portfolio = portfolio_service.get(
        entry_args["portfolio_id"]
    )
    assert updated_portfolio is not None

    reservation = (
        updated_portfolio.portfolio_snapshot
        .reservations[0]
    )
    reference = (
        updated_portfolio.portfolio_snapshot
        .position_references[0]
    )

    assert reservation.reservation_status == "RELEASED"
    assert reservation.remaining_quantity == 0
    assert reference.lifecycle_state == "CLOSED_STOP"
    assert reference.remaining_quantity == 0


def test_duplicate_observation_is_no_change(tmp_path):
    (
        entry_args,
        persisted_trade,
        portfolio_service,
        trade_service,
    ) = _open_runtime(tmp_path)

    prior = persisted_trade.latest_observation
    assert prior is not None

    args = _monitoring_args(
        entry_args=entry_args,
        persisted_trade=persisted_trade,
        portfolio_service=portfolio_service,
        trade_service=trade_service,
        observation=prior,
        evaluation_timestamp=prior.observed_at,
        suffix="duplicate",
    )

    trade_before = trade_service.get(
        entry_args["paper_trade_id"]
    )
    portfolio_before = portfolio_service.get(
        entry_args["portfolio_id"]
    )

    result = execute_continuous_position_monitoring(
        **args
    )

    assert result.status == "HOLD_NO_CHANGE"
    assert result.p7_state_changed is False
    assert result.p8_state_changed is False
    assert result.paper_action_occurred is False

    assert (
        trade_service.get(entry_args["paper_trade_id"])
        == trade_before
    )
    assert (
        portfolio_service.get(entry_args["portfolio_id"])
        == portfolio_before
    )


def test_stale_observation_is_blocked_without_mutation(
    tmp_path,
):
    (
        entry_args,
        persisted_trade,
        portfolio_service,
        trade_service,
    ) = _open_runtime(tmp_path)

    position = persisted_trade.position
    prior = persisted_trade.latest_observation
    assert position is not None
    assert prior is not None

    observation = replace(
        prior,
        observation_id="r43-observation-stale",
        option_last_price=position.entry_price + 1.0,
        option_open=position.entry_price + 1.0,
        option_low=position.entry_price + 1.0,
        option_high=position.entry_price + 1.0,
        option_close=position.entry_price + 1.0,
    )

    evaluation_timestamp = (
        observation.observed_at
        + timedelta(
            seconds=(
                persisted_trade.lifecycle_policy
                .maximum_observation_age_seconds
                + 1
            )
        )
    )

    args = _monitoring_args(
        entry_args=entry_args,
        persisted_trade=persisted_trade,
        portfolio_service=portfolio_service,
        trade_service=trade_service,
        observation=observation,
        evaluation_timestamp=evaluation_timestamp,
        suffix="stale",
    )

    trade_before = trade_service.get(
        entry_args["paper_trade_id"]
    )
    portfolio_before = portfolio_service.get(
        entry_args["portfolio_id"]
    )

    result = execute_continuous_position_monitoring(
        **args
    )

    assert result.status == "BLOCKED"
    assert result.evaluation_result.blockers == (
        "STALE_OBSERVATION",
    )
    assert result.p7_state_changed is False
    assert result.p8_state_changed is False

    assert (
        trade_service.get(entry_args["paper_trade_id"])
        == trade_before
    )
    assert (
        portfolio_service.get(entry_args["portfolio_id"])
        == portfolio_before
    )


def test_out_of_order_observation_is_blocked_without_mutation(
    tmp_path,
):
    (
        entry_args,
        persisted_trade,
        portfolio_service,
        trade_service,
    ) = _open_runtime(tmp_path)

    prior = persisted_trade.latest_observation
    position = persisted_trade.position
    assert prior is not None
    assert position is not None

    observed_at = prior.observed_at - timedelta(seconds=1)

    observation = replace(
        prior,
        observation_id="r43-observation-out-of-order",
        observed_at=observed_at,
        received_at=observed_at,
        option_last_price=position.entry_price + 1.0,
        option_open=position.entry_price + 1.0,
        option_low=position.entry_price + 1.0,
        option_high=position.entry_price + 1.0,
        option_close=position.entry_price + 1.0,
    )

    args = _monitoring_args(
        entry_args=entry_args,
        persisted_trade=persisted_trade,
        portfolio_service=portfolio_service,
        trade_service=trade_service,
        observation=observation,
        evaluation_timestamp=prior.observed_at,
        suffix="out-of-order",
    )

    trade_before = trade_service.get(
        entry_args["paper_trade_id"]
    )
    portfolio_before = portfolio_service.get(
        entry_args["portfolio_id"]
    )

    result = execute_continuous_position_monitoring(
        **args
    )

    assert result.status == "BLOCKED"
    assert result.evaluation_result.blockers == (
        "OUT_OF_ORDER_OBSERVATION",
    )

    assert (
        trade_service.get(entry_args["paper_trade_id"])
        == trade_before
    )
    assert (
        portfolio_service.get(entry_args["portfolio_id"])
        == portfolio_before
    )


def test_mismatched_observation_is_rejected_before_mutation(
    tmp_path,
):
    (
        entry_args,
        persisted_trade,
        portfolio_service,
        trade_service,
    ) = _open_runtime(tmp_path)

    prior = persisted_trade.latest_observation
    assert prior is not None

    observation = replace(
        prior,
        observation_id="r43-observation-mismatch",
        option_symbol="WRONG-SYMBOL",
    )

    trade_before = trade_service.get(
        entry_args["paper_trade_id"]
    )
    portfolio_before = portfolio_service.get(
        entry_args["portfolio_id"]
    )

    with pytest.raises(
        ValueError,
        match="observation/position identity mismatch",
    ):
        execute_continuous_position_monitoring(
            **_monitoring_args(
                entry_args=entry_args,
                persisted_trade=persisted_trade,
                portfolio_service=portfolio_service,
                trade_service=trade_service,
                observation=observation,
                evaluation_timestamp=prior.observed_at,
                suffix="mismatch",
            )
        )

    assert (
        trade_service.get(entry_args["paper_trade_id"])
        == trade_before
    )
    assert (
        portfolio_service.get(entry_args["portfolio_id"])
        == portfolio_before
    )


def test_submission_guard_rejects_before_monitoring(
    tmp_path,
):
    (
        entry_args,
        persisted_trade,
        portfolio_service,
        trade_service,
    ) = _open_runtime(tmp_path)

    position = persisted_trade.position
    assert position is not None

    observation = _next_observation(
        persisted_trade,
        suffix="submission",
        price=position.entry_price + 1.0,
    )

    args = _monitoring_args(
        entry_args=entry_args,
        persisted_trade=persisted_trade,
        portfolio_service=portfolio_service,
        trade_service=trade_service,
        observation=observation,
        evaluation_timestamp=observation.observed_at,
        suffix="submission",
    )

    trade_before = trade_service.get(
        entry_args["paper_trade_id"]
    )
    portfolio_before = portfolio_service.get(
        entry_args["portfolio_id"]
    )

    with pytest.raises(
        ValueError,
        match="order submission must remain disabled",
    ):
        execute_continuous_position_monitoring(
            **args,
            broker_order_submission=True,
        )

    assert (
        trade_service.get(entry_args["paper_trade_id"])
        == trade_before
    )
    assert (
        portfolio_service.get(entry_args["portfolio_id"])
        == portfolio_before
    )