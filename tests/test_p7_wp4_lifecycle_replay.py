"""WP4 lifecycle and cross-instrument persistence/replay certification."""

import pytest

from tests.p7_replay_harness import ReplayHarness, ReplayStepIds
from tests.test_paper_trading_engine_adapter_v1 import (
    test_adapter_persists_typed_cancellation_without_legacy_close,
)


def test_cancellation_replay_is_durable(tmp_path):
    test_adapter_persists_typed_cancellation_without_legacy_close(tmp_path)


def _assert_position_copies_p6_plan(profile, snapshot, *, option_type, exchange):
    plan = profile.integrated_trade_plan_result
    selected = plan.option_contract_selection_result.selected_contract.contract
    capital = plan.capital_quantity_result
    targets = plan.three_target_result
    position = snapshot.position

    assert position is not None
    assert (
        position.integrated_trade_plan_result_id,
        position.selected_option_contract_id,
        position.underlying_symbol,
        position.option_type,
        position.option_symbol,
        position.exchange,
        position.strike,
        position.expiry,
    ) == (
        plan.integration_id,
        selected.contract_id,
        selected.underlying_symbol,
        option_type,
        selected.trading_symbol,
        exchange,
        selected.strike,
        selected.expiry_date.isoformat(),
    )
    assert (
        position.initial_lot_count,
        position.lot_size,
        position.initial_quantity,
        position.target_1_lot_count,
        position.target_2_lot_count,
        position.target_3_lot_count,
        position.runner_lot_count,
    ) == (
        capital.planned_lot_count,
        capital.lot_size,
        capital.planned_quantity,
        capital.target_1_lot_count,
        capital.target_2_lot_count,
        capital.target_3_lot_count,
        capital.runner_lot_count,
    )
    assert (
        position.stop_loss,
        position.target_1,
        position.target_2,
        position.target_3,
    ) == (
        plan.stop_loss_result.stop_loss_price,
        targets.target_1.target_price,
        targets.target_2.target_price,
        targets.target_3.target_price,
    )
    assert position.estimated_premium_outlay == capital.estimated_premium_outlay
    assert position.estimated_risk_amount == capital.estimated_risk_amount
    assert position.estimated_total_trading_cost == capital.estimated_total_trading_cost
    assert (
        position.estimated_total_capital_requirement
        == capital.estimated_total_capital_requirement
    )
    assert snapshot.latest_observation.underlying_symbol == selected.underlying_symbol
    assert snapshot.latest_observation.option_symbol == selected.trading_symbol
    assert snapshot.execution_mode == position.execution_mode == "PAPER"
    assert snapshot.live_execution_eligible is position.live_execution_eligible is False


def test_nifty_call_entry_persistence_recovery_and_t1_replay(tmp_path):
    harness = ReplayHarness(tmp_path, "nifty_call")
    persisted = harness.persist()
    recovered = harness.fresh_recover()
    harness.assert_snapshot_exact(persisted, recovered)
    _assert_position_copies_p6_plan(
        harness.profile,
        recovered,
        option_type="CALL",
        exchange="NSE",
    )

    updated, result = harness.evaluate(
        recovered,
        ReplayStepIds.at("nifty-call-t1", 1, fill_count=1),
        option_price=110.0,
    )
    after_restart = harness.fresh_recover()
    harness.assert_snapshot_exact(updated, after_restart)
    assert result.status == "PARTIALLY_EXITED"
    assert updated.position.option_type == "CALL"
    assert updated.position.remaining_quantity == 25
    assert [fill.fill_reason for fill in updated.position.exit_fills] == ["TARGET_1"]
    assert updated.pnl_evidence.realized_gross_pnl_after == 250.0
    assert updated.pnl_evidence.allocated_entry_cost_after == 25.0
    assert updated.pnl_evidence.unrealized_pnl_after == 250.0
    assert updated.pnl_evidence.total_pnl_after == 475.0


def test_nifty_put_entry_persistence_recovery_and_stop_replay(tmp_path):
    harness = ReplayHarness(tmp_path, "nifty_put")
    harness.persist()
    recovered = harness.fresh_recover()
    _assert_position_copies_p6_plan(
        harness.profile,
        recovered,
        option_type="PUT",
        exchange="NSE",
    )

    updated, result = harness.evaluate(
        recovered,
        ReplayStepIds.at("nifty-put-stop", 1, fill_count=1),
        option_price=90.0,
    )
    history = harness.recover_history()
    assert len(history) == 1
    harness.assert_snapshot_exact(updated, history[0])
    assert result.status == "CLOSED_STOP"
    assert updated.position.option_type == "PUT"
    assert updated.position.option_symbol == "NIFTY26JAN24000PE"
    assert updated.position.remaining_quantity == 0
    assert [fill.fill_reason for fill in updated.position.exit_fills] == ["STOP"]
    assert updated.pnl_evidence.realized_gross_pnl_after == -500.0
    assert updated.pnl_evidence.allocated_entry_cost_after == 50.0
    assert updated.pnl_evidence.unrealized_pnl_after == 0.0
    assert updated.pnl_evidence.total_pnl_after == -550.0


def test_sensex_entry_persistence_recovery_and_target_replay(tmp_path):
    harness = ReplayHarness(tmp_path, "sensex")
    harness.persist()
    recovered = harness.fresh_recover()
    _assert_position_copies_p6_plan(
        harness.profile,
        recovered,
        option_type="CALL",
        exchange="BSE",
    )
    assert recovered.latest_observation.exchange == "BFO"

    updated, result = harness.evaluate(
        recovered,
        ReplayStepIds.at("sensex-t2", 1, fill_count=2),
        option_price=120.0,
    )
    history = harness.recover_history()
    assert len(history) == 1
    harness.assert_snapshot_exact(updated, history[0])
    assert result.status == "CLOSED_TARGET_2"
    assert updated.position.underlying_symbol == updated.position.market == "SENSEX"
    assert updated.position.exchange == "BSE"
    assert updated.position.option_symbol == "SENSEX26JAN24000CE"
    assert [fill.fill_reason for fill in updated.position.exit_fills] == [
        "TARGET_1",
        "TARGET_2",
    ]
    assert updated.position.remaining_quantity == 0
    assert updated.pnl_evidence.realized_gross_pnl_after == 750.0
    assert updated.pnl_evidence.allocated_entry_cost_after == 50.0
    assert updated.pnl_evidence.total_pnl_after == 700.0


@pytest.mark.parametrize(
    "profile_name,price,expected_state",
    (
        ("nifty_call", 110.0, "PARTIALLY_EXITED"),
        ("nifty_put", 90.0, "CLOSED_STOP"),
        ("sensex", 120.0, "CLOSED_TARGET_2"),
    ),
)
def test_instrument_replay_is_byte_identical_across_ten_runs(
    tmp_path,
    profile_name,
    price,
    expected_state,
):
    canonical_results = []
    for index in range(10):
        harness = ReplayHarness(tmp_path / str(index), profile_name)
        harness.persist()
        recovered = harness.fresh_recover()
        updated, result = harness.evaluate(
            recovered,
            ReplayStepIds.at(f"{profile_name}-deterministic", 1),
            option_price=price,
        )
        assert result.status == expected_state
        persisted = harness.fresh_recover()
        harness.assert_snapshot_exact(updated, persisted)
        canonical_results.append(persisted.to_json())
    assert len(set(canonical_results)) == 1


@pytest.mark.parametrize(
    "source_profile,foreign_profile",
    (
        ("nifty_call", "nifty_put"),
        ("nifty_put", "nifty_call"),
        ("sensex", "nifty_call"),
    ),
)
def test_recovered_instrument_rejects_cross_instrument_observation_without_write(
    tmp_path,
    source_profile,
    foreign_profile,
):
    harness = ReplayHarness(tmp_path / "source", source_profile)
    persisted = harness.persist()
    recovered = harness.fresh_recover()
    repository_bytes = harness.repository_bytes()
    foreign = ReplayHarness(tmp_path / "foreign", foreign_profile).profile.entry_observation

    with pytest.raises(ValueError, match="observation"):
        harness.build_input(
            recovered,
            ReplayStepIds.at(f"{source_profile}-foreign", 1),
            observation=foreign,
        )

    assert harness.repository_bytes() == repository_bytes
    harness.assert_snapshot_exact(persisted, harness.fresh_recover())


@pytest.mark.parametrize("profile_name", ("nifty_call", "nifty_put", "sensex"))
def test_recovered_instrument_nested_metadata_is_detached_from_exported_payload(
    tmp_path,
    profile_name,
):
    harness = ReplayHarness(tmp_path, profile_name)
    persisted = harness.persist()
    recovered = harness.fresh_recover()
    repository_bytes = harness.repository_bytes()
    exported = recovered.to_dict()

    exported["position"]["metadata"]["replay_profile"] = "foreign"
    exported["latest_observation"]["metadata"]["replay_profile"] = "foreign"

    harness.assert_snapshot_exact(persisted, recovered)
    assert dict(recovered.position.metadata) == {}
    assert recovered.latest_observation.metadata["replay_profile"] == profile_name
    assert harness.repository_bytes() == repository_bytes


@pytest.mark.parametrize(
    "profile_name,exchange",
    (("nifty_call", "NSE"), ("nifty_put", "NSE"), ("sensex", "BSE")),
)
def test_opt_in_adapter_entry_persists_selected_contract_exchange(
    tmp_path,
    profile_name,
    exchange,
):
    from services.paper_trade_repository import PaperTradeRepository
    from services.paper_trading import (
        PaperTradePersistenceService,
        PaperTradingEngineAdapterInputV1,
        PaperTradingEngineAdapterV1,
    )
    from services.paper_trading_engine import PaperTradingEngine
    from tests.p7_fixture_helpers import NOW, make_entry_input, make_state

    profile = ReplayHarness(tmp_path / "profile", profile_name).profile
    service = PaperTradePersistenceService(PaperTradeRepository(tmp_path / "adapter.json"))
    entry_input = make_entry_input(
        integrated_trade_plan_result=profile.integrated_trade_plan_result,
        lifecycle_policy=profile.initial_snapshot.lifecycle_policy,
        lifecycle_state=make_state(current_state="WAITING_FOR_ENTRY"),
        observation=profile.entry_observation,
        requested_transition_id=f"{profile_name}-adapter-entry-transition",
        position_id=f"{profile_name}-adapter-position",
        entry_fill_id=f"{profile_name}-adapter-entry-fill",
    )
    request = PaperTradingEngineAdapterInputV1(
        f"{profile_name}-adapter-result",
        f"{profile_name}-adapter-trade",
        f"{profile_name}-adapter-key",
        "EVALUATE_ENTRY",
        NOW,
        entry_input=entry_input,
    )
    engine = PaperTradingEngine()
    result = PaperTradingEngineAdapterV1(engine, service).execute(request)
    recovered = service.get(request.paper_trade_id)

    assert result.status == "OPEN"
    assert engine.count_trades() == 1
    assert result.position.exchange == exchange
    assert recovered.position.exchange == exchange
    assert recovered.to_json() == service.get(request.paper_trade_id).to_json()
