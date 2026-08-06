from datetime import datetime
from zoneinfo import ZoneInfo

from services.analysis.live_market_candidate_evaluator import (
    LiveMarketCandidateEvaluationResultV1,
)
from services.certification.task8_live_candidate_adapter import (
    build_task8_retaining_candidate_reader,
)
from services.paper_orchestration.certified_live_provider_readers import (
    CertifiedLiveProviderReaders,
)
from services.paper_orchestration.certified_two_market_parent_runtime import (
    run_certified_two_market_parent_runtime,
)
from services.contracts.two_market_decision_policy_v1 import (
    TwoMarketDecisionPolicyV1,
)
from services.contracts.two_market_parent_cycle_input_v1 import (
    TwoMarketParentCycleInputV1,
)

from test_task8_parent_typed_candidate_certification import (
    Analysis,
    Options,
    captured,
    cycle,
)


IST = ZoneInfo("Asia/Kolkata")
NOW = datetime(2026, 8, 3, 10, 0, tzinfo=IST)


def test_retaining_reader_keeps_both_exact_evaluations_once():
    nifty_capture = captured(
        "NIFTY",
        "NSE",
        25000.0,
    )
    sensex_capture = captured(
        "SENSEX",
        "BSE",
        80000.0,
    )
    nifty_cycle = cycle(
        "NIFTY",
        "NSE",
        nifty_capture,
    )
    sensex_cycle = cycle(
        "SENSEX",
        "BSE",
        sensex_capture,
    )

    captures = {
        nifty_cycle.observation_id: nifty_capture,
        sensex_cycle.observation_id: sensex_capture,
    }
    retained = {}
    sink_calls = []

    def sink(observation_id, evaluation):
        sink_calls.append(observation_id)
        if observation_id in retained:
            raise AssertionError(
                "evaluation retained more than once"
            )
        retained[observation_id] = evaluation

    reader = build_task8_retaining_candidate_reader(
        evaluation_sink=sink,
    )
    readers = CertifiedLiveProviderReaders(
        quote_reader=lambda *_: (_ for _ in ()).throw(
            AssertionError("provider reread")
        ),
        analysis_pipeline=Analysis(),
        option_decision_pipeline=Options(),
        available_capital=10000.0,
        candidate_reader=reader,
        capture_reader=lambda item: captures[
            item.observation_id
        ],
    )

    parent = TwoMarketParentCycleInputV1(
        parent_cycle_id="retention-parent",
        decision_result_id="retention-decision",
        nifty_child_result_id="retention-nifty-child",
        sensex_child_result_id="retention-sensex-child",
        nifty_observation_id=nifty_cycle.observation_id,
        sensex_observation_id=sensex_cycle.observation_id,
        requested_at=NOW,
        completed_at=NOW,
        decision_policy=TwoMarketDecisionPolicyV1(
            180.0,
            5.0,
        ),
    )

    run_certified_two_market_parent_runtime(
        parent,
        nifty_cycle=nifty_cycle,
        sensex_cycle=sensex_cycle,
        readers=readers,
    )

    assert sink_calls == [
        nifty_cycle.observation_id,
        sensex_cycle.observation_id,
    ]
    assert set(retained) == {
        nifty_cycle.observation_id,
        sensex_cycle.observation_id,
    }
    assert all(
        type(value)
        is LiveMarketCandidateEvaluationResultV1
        for value in retained.values()
    )
    assert (
        retained[nifty_cycle.observation_id]
        .candidate.observation_id
        == nifty_cycle.observation_id
    )
    assert (
        retained[sensex_cycle.observation_id]
        .candidate.observation_id
        == sensex_cycle.observation_id
    )
