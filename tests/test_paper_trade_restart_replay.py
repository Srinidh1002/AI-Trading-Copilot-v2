"""Real repository/recovery/replay certification using the shared P7 harness."""
from dataclasses import replace
from datetime import timedelta

import pytest

from tests.p7_fixture_helpers import NOW
from tests.p7_replay_harness import ReplayHarness, ReplayStepIds, make_replay_profile


def _runner_harness(tmp_path, close_mode):
    profile = make_replay_profile("runner")
    policy = replace(profile.initial_snapshot.lifecycle_policy, runner_close_mode=close_mode)
    snapshot = replace(profile.initial_snapshot, lifecycle_policy=policy)
    return ReplayHarness(tmp_path, replace(profile, initial_snapshot=snapshot))


def _recover_runner_after_three_targets(harness):
    harness.persist()
    current = harness.fresh_recover()
    for index, price in enumerate((110.0, 120.0, 130.0), start=1):
        current, _ = harness.evaluate(
            current,
            ReplayStepIds.at(f"deferred-runner-t{index}", index),
            option_price=price,
        )
        current = harness.fresh_recover()
    assert current.lifecycle_state.current_state == "PARTIALLY_EXITED"
    assert current.position.remaining_lot_count == 1
    assert [fill.fill_reason for fill in current.position.exit_fills] == [
        "TARGET_1",
        "TARGET_2",
        "TARGET_3",
    ]
    return current


@pytest.mark.parametrize(
    "name,underlying,option_type,allocations",
    (
        ("three_target", "NIFTY", "CALL", (1, 1, 1, 0)),
        ("t2_terminal", "NIFTY", "CALL", (1, 1, 0, 0)),
        ("runner", "NIFTY", "CALL", (1, 1, 1, 1)),
        ("simple_terminal", "NIFTY", "CALL", (1, 0, 0, 0)),
        ("nifty_call", "NIFTY", "CALL", (1, 1, 0, 0)),
        ("nifty_put", "NIFTY", "PUT", (1, 1, 0, 0)),
        ("sensex", "SENSEX", "CALL", (1, 1, 0, 0)),
    ),
)
def test_replay_profiles_are_real_entry_activated_snapshots(
    name, underlying, option_type, allocations
):
    profile = make_replay_profile(name)
    snapshot = profile.initial_snapshot
    position = snapshot.position

    assert position is not None
    assert snapshot.lifecycle_state.current_state == "OPEN"
    assert position.lifecycle_state == "OPEN"
    assert position.underlying_symbol == underlying
    assert position.option_type == option_type
    assert (
        position.target_1_lot_count,
        position.target_2_lot_count,
        position.target_3_lot_count,
        position.runner_lot_count,
    ) == allocations
    assert position.initial_lot_count == sum(allocations)
    assert position.initial_quantity == sum(allocations) * position.lot_size
    assert position.entry_fill.observation_id == profile.entry_observation.observation_id
    assert snapshot.lifecycle_policy.runner_enabled is (allocations[3] > 0)


def test_harness_recovers_exact_snapshot_by_all_supported_identities(tmp_path):
    harness = ReplayHarness(tmp_path, "three_target")
    source = harness.persist()

    recovered_by_snapshot = harness.recover(paper_trade_id=source.paper_trade_id)
    recovered_by_position = harness.recover(position_id=source.position.position_id)
    recovered_by_plan = harness.recover(trade_plan_id=source.position.trade_plan_id)
    fresh = harness.fresh_recover(source.paper_trade_id)

    for recovered in (
        recovered_by_snapshot,
        recovered_by_position,
        recovered_by_plan,
        fresh,
    ):
        harness.assert_snapshot_exact(source, recovered)
    assert harness.repository_path == tmp_path / "three_target-replay.json"


def test_recovery_is_byte_deterministic_across_fresh_service_instances(tmp_path):
    harness = ReplayHarness(tmp_path, "t2_terminal")
    source = harness.persist()
    recovered = tuple(harness.fresh_recover() for _ in range(10))

    assert {snapshot.to_json() for snapshot in recovered} == {source.to_json()}
    assert {snapshot.integrity_hash for snapshot in recovered} == {source.integrity_hash}
    assert harness.repository_bytes() == harness.repository_bytes()


def test_replay_input_uses_exact_recovered_nested_authorities(tmp_path):
    harness = ReplayHarness(tmp_path, "three_target")
    harness.persist()
    recovered = harness.fresh_recover()
    step = ReplayStepIds.at("exact-authorities", 1)
    evaluation_input = harness.build_input(recovered, step, option_price=110.0)

    assert evaluation_input.position is recovered.position
    assert evaluation_input.lifecycle_policy is recovered.lifecycle_policy
    assert evaluation_input.lifecycle_state is recovered.lifecycle_state
    assert evaluation_input.observation.trade_plan_id == recovered.position.trade_plan_id
    assert (
        evaluation_input.observation.selected_option_contract_id
        == recovered.position.selected_option_contract_id
    )
    assert evaluation_input.observation.option_symbol == recovered.position.option_symbol
    assert evaluation_input.observation.observed_at == step.observed_at
    assert evaluation_input.evaluation_timestamp == step.evaluation_timestamp


def test_recovered_open_snapshot_continues_with_real_t1_and_persists(tmp_path):
    harness = ReplayHarness(tmp_path, "t2_terminal")
    harness.persist()
    recovered = harness.fresh_recover()
    step = ReplayStepIds.at("restart-t1", 1)

    updated, result = harness.evaluate(recovered, step, option_price=110.0)
    persisted = harness.fresh_recover()

    assert result.status == "PARTIALLY_EXITED"
    assert updated.lifecycle_state.current_state == "PARTIALLY_EXITED"
    assert updated.position.remaining_lot_count == 1
    assert updated.position.remaining_quantity == updated.position.lot_size
    assert [fill.fill_reason for fill in updated.position.exit_fills] == ["TARGET_1"]
    assert updated.event_sequence == recovered.event_sequence + 1
    harness.assert_snapshot_exact(updated, persisted)


def test_recovered_t1_snapshot_continues_once_to_terminal_t2(tmp_path):
    harness = ReplayHarness(tmp_path, "t2_terminal")
    harness.persist()
    opened = harness.fresh_recover()
    after_t1, _ = harness.evaluate(
        opened, ReplayStepIds.at("t1", 1), option_price=110.0
    )
    recovered_t1 = harness.fresh_recover()
    harness.assert_snapshot_exact(after_t1, recovered_t1)

    after_t2, result = harness.evaluate(
        recovered_t1, ReplayStepIds.at("t2", 2), option_price=120.0
    )
    terminal = harness.fresh_recover()

    assert result.status == "CLOSED_TARGET_2"
    assert [fill.fill_id for fill in after_t2.position.exit_fills] == [
        "t1-fill-1",
        "t2-fill-1",
    ]
    assert [fill.fill_reason for fill in after_t2.position.exit_fills] == [
        "TARGET_1",
        "TARGET_2",
    ]
    assert after_t2.position.remaining_quantity == 0
    assert after_t2.pnl_evidence.exited_quantity == after_t2.position.initial_quantity
    assert after_t2.pnl_evidence.realized_gross_pnl_after == 750.0
    assert after_t2.event_sequence == opened.event_sequence + 2
    harness.assert_snapshot_exact(after_t2, terminal)
    assert harness.recover_active() == ()
    assert harness.recover_history() == (terminal,)


def test_full_t1_t2_t3_chain_uses_each_freshly_recovered_snapshot(tmp_path):
    harness = ReplayHarness(tmp_path, "three_target")
    harness.persist()
    current = harness.fresh_recover()
    expected_states = ("PARTIALLY_EXITED", "PARTIALLY_EXITED", "CLOSED_TARGET_3")

    for index, (label, price, expected_state) in enumerate(
        zip(("chain-t1", "chain-t2", "chain-t3"), (110.0, 120.0, 130.0), expected_states),
        start=1,
    ):
        updated, result = harness.evaluate(
            current, ReplayStepIds.at(label, index), option_price=price
        )
        recovered = harness.fresh_recover()
        harness.assert_snapshot_exact(updated, recovered)
        assert result.status == expected_state
        assert updated.event_sequence == index + 1
        assert updated.position.remaining_lot_count == 3 - index
        current = recovered

    assert [fill.fill_reason for fill in current.position.exit_fills] == [
        "TARGET_1",
        "TARGET_2",
        "TARGET_3",
    ]
    assert len({fill.fill_id for fill in current.position.exit_fills}) == 3
    assert current.pnl_evidence.exited_quantity == current.position.initial_quantity
    assert current.pnl_evidence.realized_gross_pnl_after == 1500.0
    assert current.position.realized_gross_pnl == 1500.0
    assert current.position.unrealized_pnl == 0.0
    assert current.position.total_pnl == current.position.realized_net_pnl
    # T2 preserves PARTIALLY_EXITED, so it advances the durable event sequence
    # without fabricating a second lifecycle-state transition.
    assert current.lifecycle_state.transition_sequence == 4
    assert len({current.to_json() for _ in range(10)}) == 1


def test_runner_target3_chain_closes_target_and_runner_without_oversell(tmp_path):
    harness = ReplayHarness(tmp_path, "runner")
    harness.persist()
    current = harness.fresh_recover()

    for index, (label, price) in enumerate(
        (("runner-t1", 110.0), ("runner-t2", 120.0)), start=1
    ):
        current, result = harness.evaluate(
            current, ReplayStepIds.at(label, index), option_price=price
        )
        assert result.status == "PARTIALLY_EXITED"
        current = harness.fresh_recover()

    before_t3 = current
    terminal, result = harness.evaluate(
        before_t3,
        ReplayStepIds.at("runner-t3", 3, fill_count=2),
        option_price=130.0,
    )
    terminal = harness.fresh_recover()

    assert result.status == "CLOSED_TARGET_3"
    assert [fill.fill_reason for fill in terminal.position.exit_fills] == [
        "TARGET_1",
        "TARGET_2",
        "TARGET_3",
        "RUNNER_CLOSE",
    ]
    assert [fill.fill_id for fill in result.generated_exit_fills] == [
        "runner-t3-fill-1",
        "runner-t3-fill-2",
    ]
    assert sum(fill.filled_quantity for fill in terminal.position.exit_fills) == (
        terminal.position.initial_quantity
    )
    assert terminal.position.remaining_quantity == 0
    assert terminal.event_sequence == before_t3.event_sequence + 1


def test_stop_after_fresh_recovery_persists_exact_terminal_history(tmp_path):
    harness = ReplayHarness(tmp_path, "simple_terminal")
    harness.persist()
    opened = harness.fresh_recover()
    terminal, result = harness.evaluate(
        opened, ReplayStepIds.at("restart-stop", 1), option_price=90.0
    )
    recovered = harness.fresh_recover()

    assert result.status == "CLOSED_STOP"
    assert [fill.fill_reason for fill in terminal.position.exit_fills] == ["STOP"]
    assert terminal.position.remaining_quantity == 0
    harness.assert_snapshot_exact(terminal, recovered)
    assert harness.recover_active() == ()
    assert harness.recover_history() == (recovered,)


def test_invalidation_after_partial_restart_closes_remaining_quantity(tmp_path):
    harness = ReplayHarness(tmp_path, "t2_terminal")
    harness.persist()
    opened = harness.fresh_recover()
    after_t1, _ = harness.evaluate(
        opened, ReplayStepIds.at("invalidate-t1", 1), option_price=110.0
    )
    partial = harness.fresh_recover()
    harness.assert_snapshot_exact(after_t1, partial)

    terminal, result = harness.evaluate(
        partial,
        ReplayStepIds.at("invalidate", 2),
        option_price=105.0,
        input_changes={
            "invalidation_status": "TRIGGERED",
            "invalidation_reason_code": "RISK_AUTHORITY_INVALIDATED",
        },
    )

    assert result.status == "CLOSED_INVALIDATED"
    assert [fill.fill_reason for fill in terminal.position.exit_fills] == [
        "TARGET_1",
        "INVALIDATION",
    ]
    assert result.decision_reasons == ("RISK_AUTHORITY_INVALIDATED",)
    assert harness.fresh_recover().to_json() == terminal.to_json()


@pytest.mark.parametrize("partial_first", (False, True), ids=("open", "partial"))
def test_cancellation_after_restart_is_terminal_history(tmp_path, partial_first):
    harness = ReplayHarness(tmp_path, "t2_terminal")
    harness.persist()
    source = harness.fresh_recover()
    if partial_first:
        source, _ = harness.evaluate(
            source, ReplayStepIds.at("cancel-t1", 1), option_price=110.0
        )
        source = harness.fresh_recover()

    seconds = 2 if partial_first else 1
    terminal, result = harness.evaluate(
        source,
        ReplayStepIds.at("cancel", seconds),
        option_price=105.0,
        input_changes={
            "cancellation_status": "REQUESTED",
            "cancellation_reason_code": "USER_REQUEST",
        },
    )
    recovered = harness.fresh_recover()

    assert result.status == "CANCELLED"
    assert result.cancellation_triggered is True
    assert terminal.position.exit_fills[-1].fill_reason == "CANCELLED"
    assert sum(fill.fill_reason == "CANCELLED" for fill in terminal.position.exit_fills) == 1
    assert terminal.position.remaining_quantity == 0
    harness.assert_snapshot_exact(terminal, recovered)
    assert harness.recover_active() == ()
    assert harness.recover_history() == (recovered,)


def test_session_close_after_partial_restart_closes_once(tmp_path):
    harness = ReplayHarness(tmp_path, "three_target")
    harness.persist()
    opened = harness.fresh_recover()
    after_t1, _ = harness.evaluate(
        opened, ReplayStepIds.at("session-t1", 1), option_price=110.0
    )
    partial = harness.fresh_recover()
    harness.assert_snapshot_exact(after_t1, partial)

    terminal, result = harness.evaluate(
        partial,
        ReplayStepIds.at("session-close", 2),
        option_price=105.0,
        observation_changes={"session_state": "CLOSED", "is_market_open": False},
    )

    assert result.status == "CLOSED_SESSION"
    assert result.session_close_triggered is True
    assert terminal.position.exit_fills[-1].fill_reason == "SESSION_CLOSE"
    assert terminal.position.exit_fills[-1].filled_lot_count == 2
    assert harness.fresh_recover().to_json() == terminal.to_json()


def test_expiry_close_after_partial_restart_closes_once(tmp_path):
    harness = ReplayHarness(tmp_path, "three_target")
    harness.persist()
    opened = harness.fresh_recover()
    after_t1, _ = harness.evaluate(
        opened, ReplayStepIds.at("expiry-t1", 1), option_price=110.0
    )
    partial = harness.fresh_recover()
    harness.assert_snapshot_exact(after_t1, partial)
    expiry_moment = NOW.replace(day=29) + timedelta(seconds=2)

    terminal, result = harness.evaluate(
        partial,
        ReplayStepIds.at("expiry-close", timestamp=expiry_moment),
        option_price=105.0,
    )

    assert result.status == "CLOSED_EXPIRY"
    assert result.expiry_close_triggered is True
    assert terminal.position.exit_fills[-1].fill_reason == "EXPIRY_CLOSE"
    assert terminal.position.exit_fills[-1].filled_lot_count == 2
    assert harness.fresh_recover().to_json() == terminal.to_json()


def test_duplicate_observation_after_restart_is_an_exact_economic_noop(tmp_path):
    harness = ReplayHarness(tmp_path, "t2_terminal")
    harness.persist()
    opened = harness.fresh_recover()
    after_t1, _ = harness.evaluate(
        opened, ReplayStepIds.at("duplicate-t1", 1), option_price=110.0
    )
    recovered = harness.fresh_recover()
    harness.assert_snapshot_exact(after_t1, recovered)
    authoritative_bytes = harness.repository_bytes()

    duplicate_step = ReplayStepIds.at("duplicate-retry", 2)
    duplicate_input = harness.build_input(
        recovered,
        duplicate_step,
        observation=recovered.latest_observation,
    )
    unchanged, result = harness.evaluate_input(
        recovered, duplicate_input, label="duplicate-retry"
    )

    assert result.position_decision == "HOLD"
    assert result.observation_order_valid is False
    assert result.decision_reasons == ("DUPLICATE_OBSERVATION_IGNORED",)
    harness.assert_economic_no_change(recovered, unchanged, result)
    assert harness.repository_bytes() == authoritative_bytes
    harness.assert_snapshot_exact(recovered, harness.fresh_recover())


def test_harness_trace_records_deterministic_persist_recover_evaluate_steps(tmp_path):
    harness = ReplayHarness(tmp_path, "simple_terminal")
    harness.persist()
    opened = harness.fresh_recover()
    terminal, _ = harness.evaluate(
        opened, ReplayStepIds.at("trace-stop", 1), option_price=90.0
    )
    harness.fresh_recover()

    assert [step.action for step in harness.trace] == [
        "PERSIST",
        "FRESH_RECOVER",
        "EVALUATE",
        "FRESH_RECOVER",
    ]
    assert harness.trace[-1].canonical_json == terminal.to_json()
    assert [step.event_sequence for step in harness.trace] == [1, 1, 2, 2]


def test_session_end_runner_survives_targets_then_closes_once_after_restart(tmp_path):
    harness = _runner_harness(tmp_path, "SESSION_END")
    runner = _recover_runner_after_three_targets(harness)

    ordinary, result = harness.evaluate(
        runner,
        ReplayStepIds.at("session-runner-hold", 4),
        option_price=105.0,
    )
    ordinary = harness.fresh_recover()
    assert result.status == "PARTIALLY_EXITED"
    assert result.generated_exit_fills == ()
    assert ordinary.position.remaining_lot_count == 1
    assert all(fill.fill_reason != "RUNNER_CLOSE" for fill in ordinary.position.exit_fills)

    terminal, result = harness.evaluate(
        ordinary,
        ReplayStepIds.at("session-runner-close", 5),
        option_price=105.0,
        observation_changes={"session_state": "CLOSED", "is_market_open": False},
    )
    recovered = harness.fresh_recover()

    assert result.status == "CLOSED_SESSION"
    assert result.session_close_triggered is True
    assert terminal.position.exit_fills[-1].fill_reason == "SESSION_CLOSE"
    assert terminal.position.exit_fills[-1].filled_lot_count == 1
    assert sum(fill.fill_reason == "SESSION_CLOSE" for fill in terminal.position.exit_fills) == 1
    harness.assert_snapshot_exact(terminal, recovered)
    assert harness.recover_active() == ()


def test_expiry_runner_survives_preexpiry_then_closes_once_at_expiry_after_restart(tmp_path):
    harness = _runner_harness(tmp_path, "EXPIRY")
    runner = _recover_runner_after_three_targets(harness)

    preexpiry, result = harness.evaluate(
        runner,
        ReplayStepIds.at("expiry-runner-hold", 4),
        option_price=105.0,
    )
    preexpiry = harness.fresh_recover()
    assert result.status == "PARTIALLY_EXITED"
    assert result.generated_exit_fills == ()
    assert preexpiry.position.remaining_lot_count == 1

    expiry_moment = NOW.replace(day=29) + timedelta(seconds=5)
    terminal, result = harness.evaluate(
        preexpiry,
        ReplayStepIds.at("expiry-runner-close", timestamp=expiry_moment),
        option_price=105.0,
    )
    recovered = harness.fresh_recover()

    assert result.status == "CLOSED_EXPIRY"
    assert result.expiry_close_triggered is True
    assert terminal.position.exit_fills[-1].fill_reason == "EXPIRY_CLOSE"
    assert terminal.position.exit_fills[-1].filled_lot_count == 1
    assert sum(fill.fill_reason == "EXPIRY_CLOSE" for fill in terminal.position.exit_fills) == 1
    harness.assert_snapshot_exact(terminal, recovered)
    assert harness.recover_active() == ()


def test_explicit_signal_runner_has_no_implicit_close_without_typed_authority(tmp_path):
    harness = _runner_harness(tmp_path, "EXPLICIT_SIGNAL")
    runner = _recover_runner_after_three_targets(harness)

    first_hold, first_result = harness.evaluate(
        runner,
        ReplayStepIds.at("explicit-runner-hold-1", 4),
        option_price=105.0,
    )
    first_hold = harness.fresh_recover()
    second_hold, second_result = harness.evaluate(
        first_hold,
        ReplayStepIds.at("explicit-runner-hold-2", 5),
        option_price=130.0,
    )
    recovered = harness.fresh_recover()

    for result in (first_result, second_result):
        assert result.status == "PARTIALLY_EXITED"
        assert result.generated_exit_fills == ()
    assert recovered.position.remaining_lot_count == 1
    assert recovered.position.remaining_quantity == recovered.position.lot_size
    assert [fill.fill_reason for fill in recovered.position.exit_fills] == [
        "TARGET_1",
        "TARGET_2",
        "TARGET_3",
    ]
    assert all(fill.fill_reason != "RUNNER_CLOSE" for fill in recovered.position.exit_fills)
    assert recovered.lifecycle_policy.runner_close_mode == "EXPLICIT_SIGNAL"
    harness.assert_snapshot_exact(second_hold, recovered)


def test_recovered_stale_and_out_of_order_blocked_inputs_are_economic_noops(tmp_path):
    cases = (
        (
            "stale",
            ReplayStepIds.at("blocked-stale", 121),
            NOW + timedelta(seconds=1),
            ("STALE_OBSERVATION",),
        ),
        (
            "out-of-order",
            ReplayStepIds.at("blocked-out-of-order", 2),
            NOW - timedelta(seconds=1),
            ("OUT_OF_ORDER_OBSERVATION",),
        ),
    )
    for directory, step, observation_timestamp, expected_blockers in cases:
        harness = ReplayHarness(tmp_path / directory, "t2_terminal")
        harness.persist()
        recovered = harness.fresh_recover()
        authoritative_bytes = harness.repository_bytes()
        observation = harness.build_observation(
            recovered,
            step,
            option_price=105.0,
            observed_at=observation_timestamp,
            received_at=observation_timestamp,
            market_session_date=observation_timestamp.date(),
        )
        evaluation_input = harness.build_input(recovered, step, observation=observation)

        unchanged, result = harness.evaluate_input(
            recovered, evaluation_input, label=f"blocked-{directory}"
        )

        assert result.status == "BLOCKED"
        assert result.position_decision == "BLOCK"
        assert result.blockers == expected_blockers
        assert result.generated_exit_fills == ()
        assert result.pnl_evidence is None
        harness.assert_snapshot_exact(recovered, unchanged)
        assert harness.economic_fingerprint(unchanged) == harness.economic_fingerprint(recovered)
        assert harness.repository_bytes() == authoritative_bytes
        harness.assert_snapshot_exact(recovered, harness.fresh_recover())
