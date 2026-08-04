"""Provider-free Task 2E3 aggregate matrix runner."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from typing import Any

from services.certification.task2_decision_certification_scenarios import (
    get_task2_decision_certification_scenarios,
)
from services.certification.task2_end_to_end_decision_certification import (
    compose_task2_decision_certification,
)
from services.contracts.task2_decision_certification_report_v1 import (
    Task2DecisionCertificationAggregateV1,
)


NIFTY_SELECTED = "NIFTY_SELECTED"
SENSEX_SELECTED = "SENSEX_SELECTED"
NONE_SELECTED = "NONE_SELECTED"

PARENT_CALL = "PARENT_CALL"
PARENT_PUT = "PARENT_PUT"
PARENT_NO_TRADE = "PARENT_NO_TRADE"

CHILD_CALL = "CHILD_CALL"
CHILD_PUT = "CHILD_PUT"
CHILD_WAIT = "CHILD_WAIT"
CHILD_UNAVAILABLE = "CHILD_UNAVAILABLE"

TIE_BREAK_SCENARIOS = "TIE_BREAK_SCENARIOS"
CONFIDENCE_TIE_BREAK_SCENARIOS = "CONFIDENCE_TIE_BREAK_SCENARIOS"
CONFLICT_SCENARIOS = "CONFLICT_SCENARIOS"
REQUIRED_FAILURE_SCENARIOS = "REQUIRED_FAILURE_SCENARIOS"
OPTIONAL_WARNING_SCENARIOS = "OPTIONAL_WARNING_SCENARIOS"
GROUPED_PROVENANCE_SCENARIOS = "GROUPED_PROVENANCE_SCENARIOS"
DUPLICATE_LEDGER_SCENARIOS = "DUPLICATE_LEDGER_SCENARIOS"
INVARIANT_FAILURE_SCENARIOS = "INVARIANT_FAILURE_SCENARIOS"


REQUIRED_COVERAGE = (
    (NIFTY_SELECTED, "COVERAGE_NIFTY_SELECTION_MISSING"),
    (SENSEX_SELECTED, "COVERAGE_SENSEX_SELECTION_MISSING"),
    (NONE_SELECTED, "COVERAGE_NO_TRADE_MISSING"),
    (CHILD_WAIT, "COVERAGE_WAIT_MISSING"),
    (CHILD_UNAVAILABLE, "COVERAGE_UNAVAILABLE_MISSING"),
    (TIE_BREAK_SCENARIOS, "COVERAGE_TIE_BREAK_MISSING"),
    (
        CONFIDENCE_TIE_BREAK_SCENARIOS,
        "COVERAGE_CONFIDENCE_TIE_BREAK_MISSING",
    ),
    (
        REQUIRED_FAILURE_SCENARIOS,
        "COVERAGE_REQUIRED_FAILURE_MISSING",
    ),
    (
        OPTIONAL_WARNING_SCENARIOS,
        "COVERAGE_OPTIONAL_WARNING_MISSING",
    ),
    (
        GROUPED_PROVENANCE_SCENARIOS,
        "COVERAGE_GROUPED_PROVENANCE_MISSING",
    ),
    (
        DUPLICATE_LEDGER_SCENARIOS,
        "COVERAGE_DUPLICATE_LEDGER_MISSING",
    ),
    (
        INVARIANT_FAILURE_SCENARIOS,
        "COVERAGE_INVARIANT_FAILURE_MISSING",
    ),
)


def run_task2_decision_certification_scenario(
    scenario_id: str,
    *,
    dependencies: Any = None,
):
    """Run one canonical Task 2 certification scenario."""

    for scenario in get_task2_decision_certification_scenarios():
        if scenario.scenario_id == scenario_id:
            return compose_task2_decision_certification(
                scenario,
                dependencies=dependencies,
            )

    raise ValueError("UNKNOWN_SCENARIO")


def run_all_task2_decision_certification_scenarios(
    *,
    scenarios: Sequence[Any] | None = None,
    dependencies: Any = None,
) -> Task2DecisionCertificationAggregateV1:
    """Run the canonical catalog or a supplied provider-free ordered subset."""

    selected_scenarios = tuple(
        get_task2_decision_certification_scenarios()
        if scenarios is None
        else scenarios
    )

    if not selected_scenarios:
        raise ValueError("EMPTY_SCENARIO_SEQUENCE")

    scenario_ids = tuple(
        scenario.scenario_id for scenario in selected_scenarios
    )

    if len(set(scenario_ids)) != len(scenario_ids):
        raise ValueError("DUPLICATE_SCENARIO_ID")

    results = tuple(
        compose_task2_decision_certification(
            scenario,
            dependencies=dependencies,
        )
        for scenario in selected_scenarios
    )

    return build_task2_decision_certification_aggregate(results)


def build_task2_decision_certification_aggregate(
    results: Sequence[Any],
) -> Task2DecisionCertificationAggregateV1:
    """Build one deterministic aggregate from typed scenario results."""

    ordered_results = tuple(results)

    if not ordered_results:
        raise ValueError("EMPTY_CERTIFICATION_RESULTS")

    result_ids = tuple(
        result.scenario_id for result in ordered_results
    )

    if len(set(result_ids)) != len(result_ids):
        raise ValueError("DUPLICATE_CERTIFICATION_RESULT_ID")

    coverage = _empty_coverage()
    aggregate_call_counts: dict[str, int] = {}
    aggregate_safety_counters: dict[str, int] = {}

    for result in ordered_results:
        _accumulate_result_coverage(coverage, result)
        _accumulate_pairs(
            aggregate_call_counts,
            result.call_counts,
        )
        _accumulate_pairs(
            aggregate_safety_counters,
            result.safety_counters,
        )

    coverage_failure_codes = tuple(
        failure_code
        for coverage_key, failure_code in REQUIRED_COVERAGE
        if coverage[coverage_key] == 0
    )

    has_safety_failure = any(
        value != 0
        for value in aggregate_safety_counters.values()
    )

    aggregate_failure_codes = coverage_failure_codes

    if has_safety_failure:
        aggregate_failure_codes += ("SAFETY_COUNTER_NONZERO",)

    passed_scenarios = sum(
        result.certification_status == "PASS"
        for result in ordered_results
    )
    failed_scenarios = len(ordered_results) - passed_scenarios

    overall_status = (
        "PASS"
        if (
            failed_scenarios == 0
            and not aggregate_failure_codes
        )
        else "FAILED"
    )

    deterministic_checksum = _build_aggregate_checksum(
        ordered_results
    )

    return Task2DecisionCertificationAggregateV1(
        "task2-e3-fixed",
        "TASK_2",
        ordered_results[0].evaluated_at,
        ordered_results[-1].evaluated_at,
        (
            ("contribution", "v1"),
            ("ledger", "v1"),
            ("action", "v1"),
            ("explanation", "v1"),
        ),
        len(ordered_results),
        passed_scenarios,
        failed_scenarios,
        overall_status,
        ordered_results,
        tuple(coverage.items()),
        tuple(sorted(aggregate_call_counts.items())),
        tuple(sorted(aggregate_safety_counters.items())),
        aggregate_failure_codes,
        deterministic_checksum,
    )


def _empty_coverage() -> dict[str, int]:
    """Return coverage counters in stable semantic order."""

    return {
        NIFTY_SELECTED: 0,
        SENSEX_SELECTED: 0,
        NONE_SELECTED: 0,
        PARENT_CALL: 0,
        PARENT_PUT: 0,
        PARENT_NO_TRADE: 0,
        CHILD_CALL: 0,
        CHILD_PUT: 0,
        CHILD_WAIT: 0,
        CHILD_UNAVAILABLE: 0,
        TIE_BREAK_SCENARIOS: 0,
        CONFIDENCE_TIE_BREAK_SCENARIOS: 0,
        CONFLICT_SCENARIOS: 0,
        REQUIRED_FAILURE_SCENARIOS: 0,
        OPTIONAL_WARNING_SCENARIOS: 0,
        GROUPED_PROVENANCE_SCENARIOS: 0,
        DUPLICATE_LEDGER_SCENARIOS: 0,
        INVARIANT_FAILURE_SCENARIOS: 0,
    }


def _accumulate_result_coverage(
    coverage: dict[str, int],
    result: Any,
) -> None:
    """Accumulate truthful coverage from one actual scenario result."""

    selected_market_key = f"{result.selected_market}_SELECTED"
    if selected_market_key not in coverage:
        raise ValueError("UNKNOWN_SELECTED_MARKET")

    parent_action_key = f"PARENT_{result.parent_action}"
    if parent_action_key not in coverage:
        raise ValueError("UNKNOWN_PARENT_ACTION")

    coverage[selected_market_key] += 1
    coverage[parent_action_key] += 1

    for child in (result.nifty, result.sensex):
        child_action_key = f"CHILD_{child.pre_entry_action}"
        if child_action_key not in coverage:
            raise ValueError("UNKNOWN_CHILD_ACTION")
        coverage[child_action_key] += 1

    scenario_id = result.scenario_id

    # Exact scenario IDs are used so one ranking branch cannot accidentally
    # satisfy another branch's coverage requirement.
    if scenario_id == "EQUAL_SCORE_CONFIDENCE_TIE":
        coverage[TIE_BREAK_SCENARIOS] += 1

    if scenario_id == "SCORE_TIE_HIGHER_CONFIDENCE_WINS":
        coverage[CONFIDENCE_TIE_BREAK_SCENARIOS] += 1

    if scenario_id == "CONFLICTING_CHILD":
        coverage[CONFLICT_SCENARIOS] += 1

    if scenario_id == "REQUIRED_EVIDENCE_MISSING":
        coverage[REQUIRED_FAILURE_SCENARIOS] += 1

    if scenario_id == "OPTIONAL_EXTERNAL_UNAVAILABLE":
        coverage[OPTIONAL_WARNING_SCENARIOS] += 1

    if scenario_id == "GROUPED_PILLAR_PROVENANCE":
        coverage[GROUPED_PROVENANCE_SCENARIOS] += 1

    if scenario_id == "CONFIDENCE_LEDGER_DUPLICATE_INPUT":
        coverage[DUPLICATE_LEDGER_SCENARIOS] += 1

    if scenario_id == "SELECTED_ACTION_INVARIANT_FAILURE":
        coverage[INVARIANT_FAILURE_SCENARIOS] += 1


def _accumulate_pairs(
    destination: dict[str, int],
    values: Sequence[tuple[str, int]],
) -> None:
    """Add stable typed counter pairs into an aggregate mapping."""

    for key, value in values:
        destination[key] = destination.get(key, 0) + value


def _build_aggregate_checksum(results: Sequence[Any]) -> str:
    """Build a deterministic checksum from ordered scenario checksums."""

    serialized_checksums = json.dumps(
        tuple(result.deterministic_checksum for result in results),
        separators=(",", ":"),
        ensure_ascii=True,
    )

    return hashlib.sha256(
        serialized_checksums.encode("utf-8")
    ).hexdigest()