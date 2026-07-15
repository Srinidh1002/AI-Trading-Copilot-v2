"""Granular public-contract tests for the read-only daily research report."""

from copy import deepcopy
from pathlib import Path
import re

import pytest

from services.daily_research_report import DailyResearchReport


class FakeEntryEngine:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def analyze(self, entries, *, session_date=None):
        self.calls.append((entries, session_date))
        if self.error is not None:
            raise self.error
        return self.result


class FakeSummaryEngine(FakeEntryEngine):
    def summarize(self, entries, *, session_date=None):
        return self.analyze(entries, session_date=session_date)


class FakeHistoricalEngine:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.analyse_calls = []

    def analyse(self, trades):
        self.analyse_calls.append(trades)
        if self.error is not None:
            raise self.error
        return self.result


class FakeRegimeEngine:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def analyze(self, trades):
        self.calls.append(trades)
        if self.error is not None:
            raise self.error
        return self.result


def make_service(
    *,
    summary=None,
    journal=None,
    decision=None,
    readiness=None,
    blocker=None,
    historical=None,
    regime=None,
):
    components = {
        "summary": summary or FakeSummaryEngine({}),
        "journal": journal or FakeEntryEngine({}),
        "decision": decision or FakeEntryEngine({}),
        "readiness": readiness or FakeEntryEngine({}),
        "blocker": blocker or FakeEntryEngine({}),
        "historical": historical or FakeHistoricalEngine({}),
        "regime": regime or FakeRegimeEngine({}),
    }
    return DailyResearchReport(
        market_session_summary=components["summary"],
        session_journal_analytics=components["journal"],
        decision_evolution_analyzer=components["decision"],
        trade_readiness_momentum=components["readiness"],
        blocker_intelligence=components["blocker"],
        historical_trade_performance=components["historical"],
        strategy_regime_performance=components["regime"],
    ), components


def build(**kwargs):
    service, components = make_service(**kwargs)
    return service.build_report([{"cycle": 1}], trades=[{"trade": 1}], session_date="2026-07-14"), components


def test_empty_entries_and_trades_are_safe():
    service, _ = make_service()
    report = service.build_report([], trades=[])
    assert report["cycles_observed"] == 0 and report["trades_observed"] == 0


def test_status_is_completed_when_components_succeed():
    assert build()[0]["status"] == "COMPLETED"


def test_report_is_read_only():
    assert build()[0]["read_only"] is True


def test_report_is_research_only():
    assert build()[0]["research_only"] is True


def test_session_date_is_preserved():
    assert build()[0]["session_date"] == "2026-07-14"


def test_cycles_observed_is_correct():
    assert build()[0]["cycles_observed"] == 1


def test_trades_observed_is_correct():
    assert build()[0]["trades_observed"] == 1


def test_required_top_level_keys_exist():
    report = build()[0]
    assert {"status", "read_only", "research_only", "session_date", "cycles_observed", "trades_observed", "session_intelligence", "decision_intelligence", "readiness_intelligence", "blocker_intelligence", "historical_performance", "strategy_regime_performance", "research_observations", "research_snapshot"} <= set(report)


def test_none_inputs_do_not_raise():
    service, _ = make_service()
    assert service.build_report(None, trades=None)["status"] == "COMPLETED"


def test_repeated_calls_return_fresh_dictionaries():
    service, _ = make_service()
    first, second = service.build_report([]), service.build_report([])
    assert first is not second and first["research_snapshot"] is not second["research_snapshot"]


@pytest.mark.parametrize(
    ("argument", "report_key", "result"),
    [
        ("summary", "market_session_summary", {"component": "summary"}),
        ("journal", "journal_analytics", {"component": "journal"}),
    ],
)
def test_session_component_outputs_are_preserved(argument, report_key, result):
    engine = FakeSummaryEngine(result) if argument == "summary" else FakeEntryEngine(result)
    report = build(**{argument: engine})[0]
    assert report["session_intelligence"][report_key] == result


@pytest.mark.parametrize(
    ("argument", "report_key", "engine_class", "result"),
    [
        ("decision", "decision_intelligence", FakeEntryEngine, {"component": "decision"}),
        ("readiness", "readiness_intelligence", FakeEntryEngine, {"component": "readiness"}),
        ("blocker", "blocker_intelligence", FakeEntryEngine, {"component": "blocker"}),
        ("historical", "historical_performance", FakeHistoricalEngine, {"component": "historical"}),
        ("regime", "strategy_regime_performance", FakeRegimeEngine, {"component": "regime"}),
    ],
)
def test_research_component_outputs_are_preserved(argument, report_key, engine_class, result):
    assert build(**{argument: engine_class(result)})[0][report_key] == result


def test_historical_engine_uses_analyse():
    historical = FakeHistoricalEngine({})
    build(historical=historical)
    assert len(historical.analyse_calls) == 1


def test_entries_are_passed_as_independent_lists_to_session_engines():
    entries = [{"nested": {"value": 1}}]
    _, components = build(summary=FakeSummaryEngine({}), journal=FakeEntryEngine({}))
    # The helper uses a separate input, so use a direct invocation for identity checks.
    service = DailyResearchReport(market_session_summary=components["summary"], session_journal_analytics=components["journal"], decision_evolution_analyzer=FakeEntryEngine({}), trade_readiness_momentum=FakeEntryEngine({}), blocker_intelligence=FakeEntryEngine({}), historical_trade_performance=FakeHistoricalEngine({}), strategy_regime_performance=FakeRegimeEngine({}))
    service.build_report(entries)
    assert components["summary"].calls[-1][0] == entries and components["summary"].calls[-1][0] is not entries
    assert components["journal"].calls[-1][0] is not entries


def test_trades_are_passed_as_independent_lists_to_historical_engines():
    trades = [{"nested": {"value": 1}}]
    historical, regime = FakeHistoricalEngine({}), FakeRegimeEngine({})
    service, _ = make_service(historical=historical, regime=regime)
    service.build_report([], trades=trades)
    assert historical.analyse_calls[0] == trades and historical.analyse_calls[0] is not trades
    assert regime.calls[0] is not trades


@pytest.mark.parametrize(
    ("argument", "engine_class", "report_path"),
    [
        ("summary", FakeSummaryEngine, ("session_intelligence", "market_session_summary")),
        ("journal", FakeEntryEngine, ("session_intelligence", "journal_analytics")),
        ("decision", FakeEntryEngine, ("decision_intelligence",)),
        ("readiness", FakeEntryEngine, ("readiness_intelligence",)),
        ("blocker", FakeEntryEngine, ("blocker_intelligence",)),
        ("historical", FakeHistoricalEngine, ("historical_performance",)),
        ("regime", FakeRegimeEngine, ("strategy_regime_performance",)),
    ],
)
def test_each_component_failure_is_isolated(argument, engine_class, report_path):
    report = build(**{argument: engine_class(error=RuntimeError(argument))})[0]
    component = report
    for key in report_path:
        component = component[key]
    assert report["status"] == "COMPLETED_WITH_ERRORS" and component["status"] == "ERROR"


def test_multiple_component_failures_are_isolated():
    report = build(decision=FakeEntryEngine(error=ValueError("decision")), regime=FakeRegimeEngine(error=ValueError("regime")))[0]
    assert report["status"] == "COMPLETED_WITH_ERRORS"


def test_successful_outputs_survive_another_component_failure():
    report = build(decision=FakeEntryEngine({"kept": True}), blocker=FakeEntryEngine(error=ValueError("failed")))[0]
    assert report["decision_intelligence"] == {"kept": True}


def test_component_error_result_is_read_only_with_type_and_message():
    report = build(decision=FakeEntryEngine(error=ValueError("bad data")))[0]
    error = report["decision_intelligence"]
    assert error["read_only"] is True and error["error"] == "ValueError: bad data"


@pytest.mark.parametrize("result", [None, ["unexpected"], "unexpected", 5])
def test_non_mapping_component_results_are_normalized_safely(result):
    report = build(decision=FakeEntryEngine(result))[0]
    assert report["decision_intelligence"] == {} and report["status"] == "COMPLETED"


def test_missing_nested_snapshot_fields_are_safe():
    snapshot = build(decision=FakeEntryEngine({}), readiness=FakeEntryEngine({}), blocker=FakeEntryEngine({}), regime=FakeRegimeEngine({}))[0]["research_snapshot"]
    assert snapshot["final_confidence"] is None and snapshot["trade_ready_observed"] is False and snapshot["positive_strategy_regime_combinations"] == 0


@pytest.mark.parametrize(
    ("decision", "readiness", "blocker", "regime", "key", "expected"),
    [
        ({"final_state": {"decision": "WAIT"}}, {}, {}, {}, "final_decision", "WAIT"),
        ({"final_state": {"direction": "UP"}}, {}, {}, {}, "final_direction", "UP"),
        ({"final_state": {"regime": "RANGE"}}, {}, {}, {}, "final_regime", "RANGE"),
        ({"final_state": {"confidence": 81}}, {}, {}, {}, "final_confidence", 81),
        ({"confidence": {"trend": "RISING"}}, {}, {}, {}, "confidence_trend", "RISING"),
        ({}, {"momentum": "BUILDING"}, {}, {}, "readiness_momentum", "BUILDING"),
        ({}, {"readiness": {"final": 60}}, {}, {}, "final_readiness", 60),
        ({}, {"risk_flags": {"final_count": 2}}, {}, {}, "final_risk_flag_count", 2),
        ({}, {"setup": {"final_score": 80}}, {}, {}, "final_setup_score", 80),
        ({}, {"trade_ready": {"observed": True}}, {}, {}, "trade_ready_observed", True),
        ({}, {}, {"final_blocker_state": {"blocked": True}}, {}, "final_blocked", True),
        ({}, {}, {"final_blocker_state": {"state": "ACTIVE"}}, {}, "final_blocker_state", {"state": "ACTIVE"}),
        ({}, {}, {}, {"positive_combinations": [1, 2]}, "positive_strategy_regime_combinations", 2),
        ({}, {}, {}, {"negative_combinations": [1]}, "negative_strategy_regime_combinations", 1),
        ({}, {}, {}, {"best_observed_combination": {"strategy": "A"}}, "best_observed_combination", {"strategy": "A"}),
        ({}, {}, {}, {"worst_observed_combination": {"strategy": "B"}}, "worst_observed_combination", {"strategy": "B"}),
    ],
)
def test_snapshot_fields_are_extracted(decision, readiness, blocker, regime, key, expected):
    report = build(decision=FakeEntryEngine(decision), readiness=FakeEntryEngine(readiness), blocker=FakeEntryEngine(blocker), regime=FakeRegimeEngine(regime))[0]
    assert report["research_snapshot"][key] == expected


@pytest.mark.parametrize(
    ("decision", "readiness", "blocker", "historical", "regime", "expected"),
    [
        ({"confidence": {"trend": "RISING"}}, {}, {}, {}, {}, "Confidence increased during the observed session."),
        ({"confidence": {"trend": "FALLING"}}, {}, {}, {}, {}, "Confidence decreased during the observed session."),
        ({"decision_stability": {"stable": True}}, {}, {}, {}, {}, "Decision state remained stable across most observed cycles."),
        ({}, {"momentum": "BUILDING"}, {}, {}, {}, "Trade-readiness momentum improved during the observed session."),
        ({}, {"momentum": "DETERIORATING"}, {}, {}, {}, "Trade-readiness momentum weakened during the observed session."),
        ({}, {}, {"final_blocker_state": {"blocked": True}}, {}, {}, "One or more blockers remained active at the final observed cycle."),
        ({}, {}, {"cleared_before_trade_ready": [{"blocker": "X"}]}, {}, {}, "Observed blockers cleared before the first TRADE_READY state."),
        ({}, {"trade_ready": {"observed": False}}, {}, {}, {}, "No TRADE_READY state was observed."),
        ({}, {}, {}, {}, {"positive_combinations": [1]}, "A historically positive strategy-regime combination was observed."),
        ({}, {}, {}, {}, {"negative_combinations": [1]}, "A historically negative strategy-regime combination was observed."),
        ({}, {}, {}, {"overall": {"sufficient_sample": False}}, {}, "Historical closed-trade sample is insufficient for a strong research observation."),
    ],
)
def test_research_observations_are_produced(decision, readiness, blocker, historical, regime, expected):
    report = build(decision=FakeEntryEngine(decision), readiness=FakeEntryEngine(readiness), blocker=FakeEntryEngine(blocker), historical=FakeHistoricalEngine(historical), regime=FakeRegimeEngine(regime))[0]
    assert expected in report["research_observations"]


def test_observations_are_deduplicated_and_ordered():
    report = build(decision=FakeEntryEngine({"confidence": {"trend": "RISING"}}), readiness=FakeEntryEngine({"momentum": "BUILDING"}), regime=FakeRegimeEngine({"positive_combinations": [1, 2]}))[0]
    observations = report["research_observations"]
    assert observations == ["Confidence increased during the observed session.", "Trade-readiness momentum improved during the observed session.", "A historically positive strategy-regime combination was observed."]


def test_empty_outputs_have_deterministic_observations():
    service, _ = make_service()
    assert service.build_report([])["research_observations"] == service.build_report([])["research_observations"]


def test_identical_input_has_identical_research_observations():
    service, _ = make_service(readiness=FakeEntryEngine({"trade_ready": {"observed": False}}))
    assert service.build_report([])["research_observations"] == service.build_report([])["research_observations"]


@pytest.mark.parametrize("component_name", ["decision", "readiness", "blocker", "historical", "regime"])
def test_injected_component_outputs_are_not_mutated(component_name):
    output = {"nested": {"value": 1}}
    engine_types = {"decision": FakeEntryEngine, "readiness": FakeEntryEngine, "blocker": FakeEntryEngine, "historical": FakeHistoricalEngine, "regime": FakeRegimeEngine}
    build(**{component_name: engine_types[component_name](output)})
    assert output == {"nested": {"value": 1}}


def test_input_entries_and_trades_are_not_mutated():
    entries, trades = [{"nested": {"value": 1}}], [{"nested": {"value": 2}}]
    before_entries, before_trades = deepcopy(entries), deepcopy(trades)
    service, _ = make_service()
    service.build_report(entries, trades=trades)
    assert entries == before_entries and trades == before_trades


def test_mutating_report_does_not_mutate_injected_output_or_next_result():
    output = {"final_state": {"decision": "WAIT"}}
    service, _ = make_service(decision=FakeEntryEngine(output))
    first = service.build_report([])
    first["decision_intelligence"]["final_state"]["decision"] = "CHANGED"
    assert output["final_state"]["decision"] == "WAIT"
    assert service.build_report([])["decision_intelligence"]["final_state"]["decision"] == "WAIT"


def test_production_module_has_no_execution_imports_or_calls():
    source = Path("services/daily_research_report.py").read_text(encoding="utf-8").lower()
    forbidden = ("place_order", "placeorder", "open_paper", "close_paper", "broker", "paper_trading_engine")
    assert not any(token in source for token in forbidden)


def test_generated_observations_have_no_execution_instruction_language():
    report = build(decision=FakeEntryEngine({"confidence": {"trend": "RISING"}}), readiness=FakeEntryEngine({"momentum": "BUILDING"}))[0]
    forbidden = re.compile(r"\\b(?:BUY|SELL|ENTER|EXIT\\s+NOW|TAKE\\s+CE|TAKE\\s+PE|TRADE\\s+NOW|EXECUTE)\\b", re.IGNORECASE)
    assert not any(forbidden.search(observation) for observation in report["research_observations"])
def test_empty_session_reports_no_market_cycles():
    report = DailyResearchReport().build_report(
        [],
        trades=[],
        session_date="2026-07-14",
    )

    assert (
        "No market cycles were observed "
        "for the requested session."
        in report[
            "research_observations"
        ]
    )


def test_empty_session_does_not_claim_decision_stability():
    report = DailyResearchReport().build_report(
        [],
        trades=[],
        session_date="2026-07-14",
    )

    assert (
        "Decision state remained stable "
        "across most observed cycles."
        not in report[
            "research_observations"
        ]
    )


def test_empty_session_does_not_claim_no_trade_ready_observation():
    report = DailyResearchReport().build_report(
        [],
        trades=[],
        session_date="2026-07-14",
    )

    assert (
        "No TRADE_READY state was observed."
        not in report[
            "research_observations"
        ]
    )


def test_daily_report_exposes_strong_trade_readiness_convergence():
    entries = [
        {
            "timestamp": (
                "2026-07-16T09:20:00+05:30"
            ),
            "decision": "WAIT",
            "direction": "BULLISH",
            "confidence": 60.0,
            "trade_candidate_score": 60.0,
            "distance_to_trigger_percent": 1.0,
        },
        {
            "timestamp": (
                "2026-07-16T09:25:00+05:30"
            ),
            "decision": "WAIT",
            "direction": "BULLISH",
            "confidence": 70.0,
            "trade_candidate_score": 70.0,
            "distance_to_trigger_percent": 0.8,
        },
        {
            "timestamp": (
                "2026-07-16T09:30:00+05:30"
            ),
            "decision": "WAIT",
            "direction": "BULLISH",
            "confidence": 85.0,
            "trade_candidate_score": 85.0,
            "distance_to_trigger_percent": 0.5,
        },
        {
            "timestamp": (
                "2026-07-16T09:35:00+05:30"
            ),
            "decision": "TRADE_READY",
            "direction": "BULLISH",
            "confidence": 95.0,
            "trade_candidate_score": 95.0,
            "distance_to_trigger_percent": 0.05,
        },
    ]

    report = DailyResearchReport().build_report(
        entries,
        trades=[],
        session_date="2026-07-16",
    )

    assert report["status"] == "COMPLETED"

    decision = report[
        "decision_intelligence"
    ]

    assert (
        decision[
            "candidate_momentum"
        ][
            "trend"
        ]
        == "RISING"
    )

    assert (
        decision[
            "candidate_momentum"
        ][
            "change"
        ]
        == 35.0
    )

    assert (
        decision[
            "trigger_approach"
        ][
            "approach_trend"
        ]
        == "CLOSING"
    )

    assert (
        decision[
            "trigger_approach"
        ][
            "approach_speed"
        ]
        == "ACCELERATING"
    )

    convergence = report[
        "trade_readiness_convergence"
    ]

    assert (
        convergence[
            "convergence"
        ]
        == "STRONG"
    )

    assert (
        convergence[
            "candidate_signal"
        ][
            "persistent_rise"
        ]
        is True
    )

    assert (
        convergence[
            "trigger_signal"
        ][
            "closing"
        ]
        is True
    )

    assert (
        convergence[
            "trigger_signal"
        ][
            "accelerating"
        ]
        is True
    )


def test_daily_report_marks_convergence_engine_error():
    class FailingConvergence:
        def analyze(
            self,
            evolution_analysis,
            *,
            session_date=None,
        ):
            raise RuntimeError(
                "convergence failure"
            )

    report = DailyResearchReport(
        trade_readiness_convergence=(
            FailingConvergence()
        ),
    ).build_report(
        [],
        trades=[],
        session_date="2026-07-16",
    )

    assert (
        report["status"]
        == "COMPLETED_WITH_ERRORS"
    )

    assert (
        report[
            "trade_readiness_convergence"
        ][
            "status"
        ]
        == "ERROR"
    )
