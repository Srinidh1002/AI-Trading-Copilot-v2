"""R4.5 restart recovery and duplicate-protection certification."""

from dataclasses import replace
from datetime import timedelta

import pytest

from services.paper_orchestration.restart_recovery_runtime import (
    RestartRecoveryResultV1,
    execute_restart_recovery,
)
from services.paper_orchestration.continuous_position_monitoring_runtime import (
    execute_continuous_position_monitoring,
)
from services.paper_portfolio.paper_portfolio_persistence_service import (
    PaperPortfolioPersistenceService,
)
from services.paper_trading.paper_trade_persistence_service import (
    PaperTradePersistenceService,
)
from tests.test_r42_admitted_plan_simulated_entry_runtime import (
    _admitted_runtime_args,
)


def _fresh_services(entry_args):
    return (
        PaperPortfolioPersistenceService(
            entry_args[
                "portfolio_persistence_service"
            ].repository
        ),
        PaperTradePersistenceService(
            entry_args[
                "trade_persistence_service"
            ].repository
        ),
    )


def _open_runtime(tmp_path):
    from services.paper_orchestration.admitted_plan_simulated_entry_runtime import (
        execute_admitted_plan_simulated_entry,
    )

    entry_args, portfolio_service, trade_service = (
        _admitted_runtime_args(tmp_path)
    )

    result = execute_admitted_plan_simulated_entry(
        **entry_args
    )

    assert result.status == "OPEN"

    entry_args = (
        entry_args
        | {
            "portfolio_persistence_service": (
                portfolio_service
            ),
            "trade_persistence_service": trade_service,
        }
    )

    return (
        entry_args,
        portfolio_service,
        trade_service,
    )


def _recovery_args(
    *,
    entry_args,
    portfolio_service,
    trade_service,
    include_terminal=True,
):
    return {
        "portfolio_id": entry_args["portfolio_id"],
        "portfolio_policy": entry_args[
            "portfolio_policy"
        ],
        "portfolio_persistence_service": (
            portfolio_service
        ),
        "trade_persistence_service": trade_service,
        "include_terminal": include_terminal,
    }


def _next_observation(snapshot, *, suffix, price):
    prior = snapshot.latest_observation
    assert prior is not None

    observed_at = prior.observed_at + timedelta(seconds=1)

    return replace(
        prior,
        observation_id=f"r45-observation-{suffix}",
        observed_at=observed_at,
        received_at=observed_at,
        option_last_price=price,
        option_open=price,
        option_low=price,
        option_high=price,
        option_close=price,
    )


def test_restart_rehydrates_open_trade_from_fresh_services(
    tmp_path,
):
    (
        entry_args,
        _,
        _,
    ) = _open_runtime(tmp_path)

    fresh_portfolio, fresh_trade = _fresh_services(
        entry_args
    )

    result = execute_restart_recovery(
        **_recovery_args(
            entry_args=entry_args,
            portfolio_service=fresh_portfolio,
            trade_service=fresh_trade,
        )
    )

    assert type(result) is RestartRecoveryResultV1
    assert result.status == "RECOVERED"
    assert result.active_trade_count == 1
    assert result.terminal_trade_count == 0
    assert len(result.recovered_trades) == 1
    assert (
        result.recovered_trades[0]
        .lifecycle_state.current_state
        == "OPEN"
    )
    assert result.duplicate_protection_verified is True


def test_restart_rehydrates_partially_exited_trade(
    tmp_path,
):
    (
        entry_args,
        portfolio_service,
        trade_service,
    ) = _open_runtime(tmp_path)

    snapshot = trade_service.get(
        entry_args["paper_trade_id"]
    )
    assert snapshot is not None
    assert snapshot.position is not None

    observation = _next_observation(
        snapshot,
        suffix="partial",
        price=snapshot.position.target_1,
    )

    monitor_result = execute_continuous_position_monitoring(
        portfolio_id=entry_args["portfolio_id"],
        paper_trade_id=entry_args["paper_trade_id"],
        portfolio_policy=entry_args["portfolio_policy"],
        observation=observation,
        evaluation_timestamp=observation.observed_at,
        requested_transition_id="r45-partial-transition",
        resulting_lifecycle_state_id="r45-partial-state",
        evaluation_result_id="r45-partial-result",
        exit_fill_ids=(
            "r45-partial-exit-1",
            "r45-partial-exit-2",
            "r45-partial-exit-3",
            "r45-partial-exit-4",
        ),
        pnl_evidence_id="r45-partial-pnl",
        result_snapshot_id="r45-partial-portfolio",
        portfolio_event_id="r45-partial-event",
        update_idempotency_key="r45-partial-update",
        portfolio_persistence_service=portfolio_service,
        trade_persistence_service=trade_service,
    )

    assert monitor_result.status == "PARTIAL_EXIT"

    fresh_portfolio, fresh_trade = _fresh_services(
        entry_args
    )

    result = execute_restart_recovery(
        **_recovery_args(
            entry_args=entry_args,
            portfolio_service=fresh_portfolio,
            trade_service=fresh_trade,
        )
    )

    assert result.active_trade_count == 1
    assert (
        result.recovered_trades[0]
        .lifecycle_state.current_state
        == "PARTIALLY_EXITED"
    )


def test_terminal_trade_is_excluded_when_requested(
    tmp_path,
):
    (
        entry_args,
        portfolio_service,
        trade_service,
    ) = _open_runtime(tmp_path)

    snapshot = trade_service.get(
        entry_args["paper_trade_id"]
    )
    assert snapshot is not None
    assert snapshot.position is not None

    observation = _next_observation(
        snapshot,
        suffix="terminal",
        price=snapshot.position.stop_loss,
    )

    monitor_result = execute_continuous_position_monitoring(
        portfolio_id=entry_args["portfolio_id"],
        paper_trade_id=entry_args["paper_trade_id"],
        portfolio_policy=entry_args["portfolio_policy"],
        observation=observation,
        evaluation_timestamp=observation.observed_at,
        requested_transition_id="r45-terminal-transition",
        resulting_lifecycle_state_id="r45-terminal-state",
        evaluation_result_id="r45-terminal-result",
        exit_fill_ids=("r45-terminal-exit-1",),
        pnl_evidence_id="r45-terminal-pnl",
        result_snapshot_id="r45-terminal-portfolio",
        portfolio_event_id="r45-terminal-event",
        update_idempotency_key="r45-terminal-update",
        portfolio_persistence_service=portfolio_service,
        trade_persistence_service=trade_service,
    )

    assert monitor_result.status == "CLOSED"

    fresh_portfolio, fresh_trade = _fresh_services(
        entry_args
    )

    result = execute_restart_recovery(
        **_recovery_args(
            entry_args=entry_args,
            portfolio_service=fresh_portfolio,
            trade_service=fresh_trade,
            include_terminal=False,
        )
    )

    assert result.active_trade_count == 0
    assert result.terminal_trade_count == 0
    assert result.recovered_trades == ()


def test_corrupted_p7_integrity_is_rejected(tmp_path):
    (
        entry_args,
        _,
        trade_service,
    ) = _open_runtime(tmp_path)

    state = trade_service.repository.get_trade(
        entry_args["paper_trade_id"]
    )
    assert state is not None

    state["typed_p7_integrity_hash"] = "corrupted"
    trade_service.repository.save_trade(state)

    fresh_portfolio, fresh_trade = _fresh_services(
        entry_args
    )

    with pytest.raises(
        ValueError,
        match="typed snapshot integrity mismatch",
    ):
        execute_restart_recovery(
            **_recovery_args(
                entry_args=entry_args,
                portfolio_service=fresh_portfolio,
                trade_service=fresh_trade,
            )
        )


def test_corrupted_p8_integrity_is_rejected(tmp_path):
    (
        entry_args,
        portfolio_service,
        _,
    ) = _open_runtime(tmp_path)

    state = portfolio_service.repository.get_portfolio(
        entry_args["portfolio_id"]
    )
    assert state is not None

    state["typed_p8_integrity_hash"] = "corrupted"
    portfolio_service.repository.save_portfolio(state)

    fresh_portfolio, fresh_trade = _fresh_services(
        entry_args
    )

    with pytest.raises(
        ValueError,
        match="typed P8 snapshot integrity mismatch",
    ):
        execute_restart_recovery(
            **_recovery_args(
                entry_args=entry_args,
                portfolio_service=fresh_portfolio,
                trade_service=fresh_trade,
            )
        )


def test_duplicate_entry_replay_remains_idempotent_after_restart(
    tmp_path,
):
    from services.paper_orchestration.admitted_plan_simulated_entry_runtime import (
        execute_admitted_plan_simulated_entry,
    )

    (
        entry_args,
        _,
        _,
    ) = _open_runtime(tmp_path)

    fresh_portfolio, fresh_trade = _fresh_services(
        entry_args
    )

    replay_args = (
        entry_args
        | {
            "portfolio_persistence_service": (
                fresh_portfolio
            ),
            "trade_persistence_service": fresh_trade,
        }
    )

    before_p7 = fresh_trade.get(
        entry_args["paper_trade_id"]
    )
    before_p8 = fresh_portfolio.get(
        entry_args["portfolio_id"]
    )

    result = execute_admitted_plan_simulated_entry(
        **replay_args
    )

    assert result.status == "OPEN"
    assert result.idempotent_replay is True

    assert (
        fresh_trade.get(entry_args["paper_trade_id"])
        == before_p7
    )
    assert (
        fresh_portfolio.get(entry_args["portfolio_id"])
        == before_p8
    )


def test_duplicate_observation_remains_noop_after_restart(
    tmp_path,
):
    (
        entry_args,
        _,
        _,
    ) = _open_runtime(tmp_path)

    fresh_portfolio, fresh_trade = _fresh_services(
        entry_args
    )

    snapshot = fresh_trade.get(
        entry_args["paper_trade_id"]
    )
    assert snapshot is not None
    assert snapshot.latest_observation is not None

    before_p7 = snapshot
    before_p8 = fresh_portfolio.get(
        entry_args["portfolio_id"]
    )

    result = execute_continuous_position_monitoring(
        portfolio_id=entry_args["portfolio_id"],
        paper_trade_id=entry_args["paper_trade_id"],
        portfolio_policy=entry_args["portfolio_policy"],
        observation=snapshot.latest_observation,
        evaluation_timestamp=(
            snapshot.latest_observation.observed_at
        ),
        requested_transition_id="r45-duplicate-transition",
        resulting_lifecycle_state_id="r45-duplicate-state",
        evaluation_result_id="r45-duplicate-result",
        exit_fill_ids=("r45-duplicate-exit",),
        pnl_evidence_id="r45-duplicate-pnl",
        result_snapshot_id="r45-duplicate-portfolio",
        portfolio_event_id="r45-duplicate-event",
        update_idempotency_key="r45-duplicate-update",
        portfolio_persistence_service=fresh_portfolio,
        trade_persistence_service=fresh_trade,
    )

    assert result.status == "HOLD_NO_CHANGE"

    assert (
        fresh_trade.get(entry_args["paper_trade_id"])
        == before_p7
    )
    assert (
        fresh_portfolio.get(entry_args["portfolio_id"])
        == before_p8
    )


def test_submission_guard_rejects_restart_recovery(
    tmp_path,
):
    (
        entry_args,
        _,
        _,
    ) = _open_runtime(tmp_path)

    fresh_portfolio, fresh_trade = _fresh_services(
        entry_args
    )

    with pytest.raises(
        ValueError,
        match="order submission must remain disabled",
    ):
        execute_restart_recovery(
            **_recovery_args(
                entry_args=entry_args,
                portfolio_service=fresh_portfolio,
                trade_service=fresh_trade,
            ),
            broker_order_submission=True,
        )