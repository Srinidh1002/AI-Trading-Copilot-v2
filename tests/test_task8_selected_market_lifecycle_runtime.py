from services.certification.task8_selected_market_lifecycle_runtime import (
    execute_task8_selected_market_lifecycle,
)
from services.certification.task8_selected_market_p6_bundle import (
    build_task8_selected_market_p6_bundle,
)
from services.paper_orchestration.certified_p6_input_factory import (
    CertifiedP6InputFactory,
)
from services.paper_orchestration.p6_planning_stage_executor import (
    execute_p6_planning_stage,
)
from services.paper_orchestration.selected_market_p6_planning_runtime import (
    SelectedMarketP6PlanningResultV1,
)
from tests.test_task8_selected_market_p6_bundle import (
    NOW,
    _real_selected_bundle_inputs,
)


def _ready_selected_planning():
    (
        bridge,
        selected_cycle,
        evaluation,
    ) = _real_selected_bundle_inputs()

    bundle = build_task8_selected_market_p6_bundle(
        bridge=bridge,
        cycle=selected_cycle,
        evaluation=evaluation,
        available_capital=300000.0,
        evaluated_at=NOW,
    )

    factory = CertifiedP6InputFactory(
        typed_input_builder=lambda *_: bundle,
    )

    stage_input = factory(
        selected_cycle,
        bridge.selected_candidate,
        bridge.selected_candidate.option_contract_eligibility,
    )

    integrated_result = execute_p6_planning_stage(
        stage_input
    )

    assert integrated_result.status == "READY"

    planning = SelectedMarketP6PlanningResultV1(
        bridge=bridge,
        planning_result=integrated_result,
        status="READY",
    )

    return (
        bridge,
        selected_cycle,
        evaluation,
        bundle,
        planning,
    )


def test_selected_lifecycle_requires_no_provider_reread(
    tmp_path,
):
    (
        bridge,
        selected_cycle,
        evaluation,
        bundle,
        planning,
    ) = _ready_selected_planning()

    result = execute_task8_selected_market_lifecycle(
        selected_cycle=selected_cycle,
        selected_planning=planning,
        available_capital=300000.0,
        evaluated_at=NOW,
        persistence_root=tmp_path,
    )

    stages = tuple(
        stage.stage
        for stage in result.stage_results
    )

    assert stages[0] == "P6_PLAN"
    assert "P8_ADMISSION" in stages
    assert "P7_LIFECYCLE" in stages
    assert stages[-1] == "PERSISTENCE"

    assert result.execution_mode == "PAPER"
    assert result.live_execution_eligible is False
    assert result.metadata["selected_market"] == (
        "NIFTY",
        "NSE",
    )
    assert (
        result.metadata["selected_candidate_id"]
        == bridge.candidate_id
    )

    assert all(
        action == "OPEN_POSITION"
        for action in result.paper_actions
    )

    assert (
        tmp_path / "selected_cycle_journal.json"
    ).exists()
    assert (
        tmp_path / "p8_portfolios.json"
    ).exists()


def test_selected_lifecycle_persistence_is_durable(
    tmp_path,
):
    (
        bridge,
        selected_cycle,
        evaluation,
        bundle,
        planning,
    ) = _ready_selected_planning()

    result = execute_task8_selected_market_lifecycle(
        selected_cycle=selected_cycle,
        selected_planning=planning,
        available_capital=300000.0,
        evaluated_at=NOW,
        persistence_root=tmp_path,
    )

    persistence = result.stage_results[-1]

    assert persistence.stage == "PERSISTENCE"
    assert persistence.status == "COMPLETED"
    assert (
        persistence.metadata[
            "broker_order_submission"
        ]
        is False
    )
    assert (
        persistence.metadata[
            "live_execution_eligible"
        ]
        is False
    )

    journal_text = (
        tmp_path / "selected_cycle_journal.json"
    ).read_text(encoding="utf-8")

    assert result.cycle_result_id in journal_text
    assert '"execution_mode": "PAPER"' in journal_text
    assert (
        '"live_execution_eligible": false'
        in journal_text
    )


def test_only_open_lifecycle_emits_open_position(
    tmp_path,
):
    (
        bridge,
        selected_cycle,
        evaluation,
        bundle,
        planning,
    ) = _ready_selected_planning()

    result = execute_task8_selected_market_lifecycle(
        selected_cycle=selected_cycle,
        selected_planning=planning,
        available_capital=300000.0,
        evaluated_at=NOW,
        persistence_root=tmp_path,
    )

    lifecycle = next(
        stage
        for stage in result.stage_results
        if stage.stage == "P7_LIFECYCLE"
    )

    if lifecycle.paper_action_occurred:
        assert result.paper_actions == (
            "OPEN_POSITION",
        )
        assert (
            "P8_PORTFOLIO_UPDATE"
            in tuple(
                stage.stage
                for stage in result.stage_results
            )
        )
        assert (
            tmp_path / "p7_trades.json"
        ).exists()
    else:
        assert result.paper_actions == ()
