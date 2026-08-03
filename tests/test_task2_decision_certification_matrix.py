import pytest
from dataclasses import replace
from services.certification.task2_decision_certification_matrix import (
    build_task2_decision_certification_aggregate,
    run_all_task2_decision_certification_scenarios,
    run_task2_decision_certification_scenario,
)
from services.certification.task2_decision_certification_scenarios import (
    get_task2_decision_certification_scenarios,
)


def _scenario_ids(scenarios):
    return tuple(scenario.scenario_id for scenario in scenarios)


def _result_scenario_ids(aggregate):
    return tuple(result.scenario_id for result in aggregate.scenario_results)


def test_matrix_passes_deterministically_with_required_coverage():
    first = run_all_task2_decision_certification_scenarios()
    second = run_all_task2_decision_certification_scenarios()

    assert (
        first.total_scenarios,
        first.passed_scenarios,
        first.failed_scenarios,
        first.overall_status,
    ) == (19, 19, 0, "PASS")

    assert first.coverage_failure_codes == ()
    assert first.deterministic_checksum == second.deterministic_checksum
    assert _result_scenario_ids(first) == _result_scenario_ids(second)

    coverage = dict(first.coverage_summary)

    required_positive_coverage = (
        "NIFTY_SELECTED",
        "SENSEX_SELECTED",
        "NONE_SELECTED",
        "PARENT_CALL",
        "PARENT_PUT",
        "PARENT_NO_TRADE",
        "CHILD_CALL",
        "CHILD_PUT",
        "CHILD_WAIT",
        "CHILD_UNAVAILABLE",
        "TIE_BREAK_SCENARIOS",
        "CONFIDENCE_TIE_BREAK_SCENARIOS",
        "CONFLICT_SCENARIOS",
        "REQUIRED_FAILURE_SCENARIOS",
        "OPTIONAL_WARNING_SCENARIOS",
        "GROUPED_PROVENANCE_SCENARIOS",
        "DUPLICATE_LEDGER_SCENARIOS",
        "INVARIANT_FAILURE_SCENARIOS",
    )

    for key in required_positive_coverage:
        assert coverage[key] > 0


def test_selected_scenarios_follow_production_composer_outputs():
    nifty_call = run_task2_decision_certification_scenario(
        "NIFTY_CALL_WINS"
    )
    sensex_put = run_task2_decision_certification_scenario(
        "SENSEX_PUT_WINS"
    )

    assert nifty_call.parent_action == "CALL"
    assert nifty_call.selected_market == "NIFTY"

    assert sensex_put.parent_action == "PUT"
    assert sensex_put.selected_market == "SENSEX"


def test_subset_coverage_failures_are_stable_and_catalog_is_unchanged():
    catalog = get_task2_decision_certification_scenarios()
    original_ids = _scenario_ids(catalog)

    subset = tuple(
        scenario
        for scenario in catalog
        if scenario.scenario_id != "REQUIRED_EVIDENCE_MISSING"
    )

    result = run_all_task2_decision_certification_scenarios(
        scenarios=subset
    )

    assert result.overall_status == "FAILED"
    assert result.coverage_failure_codes == (
        "COVERAGE_REQUIRED_FAILURE_MISSING",
    )

    assert _scenario_ids(
        get_task2_decision_certification_scenarios()
    ) == original_ids


def test_required_selection_and_child_action_coverage_codes_are_stable():
    catalog = get_task2_decision_certification_scenarios()

    cases = (
        (
            tuple(
                scenario
                for scenario in catalog
                if scenario.expected_selected_market != "NIFTY"
            ),
            "COVERAGE_NIFTY_SELECTION_MISSING",
        ),
        (
            tuple(
                scenario
                for scenario in catalog
                if scenario.expected_selected_market != "SENSEX"
            ),
            "COVERAGE_SENSEX_SELECTION_MISSING",
        ),
        (
            tuple(
                scenario
                for scenario in catalog
                if scenario.expected_selected_market != "NONE"
            ),
            "COVERAGE_NO_TRADE_MISSING",
        ),
        (
            tuple(
                scenario
                for scenario in catalog
                if (
                    scenario.nifty.expected_action != "WAIT"
                    and scenario.sensex.expected_action != "WAIT"
                )
            ),
            "COVERAGE_WAIT_MISSING",
        ),
        (
            tuple(
                scenario
                for scenario in catalog
                if scenario.scenario_id
                not in {
                    "WAIT_AND_UNAVAILABLE",
                    "BOTH_UNAVAILABLE",
                    "ONE_UNAVAILABLE_OTHER_CALL",
                    "ONE_UNAVAILABLE_OTHER_PUT",
                    "CONFLICTING_CHILD",
                    "REQUIRED_EVIDENCE_MISSING",
                    "REGIME_BLOCKED",
                }
            ),
            "COVERAGE_UNAVAILABLE_MISSING",
        ),
    )

    for subset, expected_code in cases:
        result = run_all_task2_decision_certification_scenarios(
            scenarios=subset
        )

        assert result.overall_status == "FAILED"
        assert expected_code in result.coverage_failure_codes


@pytest.mark.parametrize(
    ("removed_scenario_id", "expected_failure_code"),
    (
        (
            "EQUAL_SCORE_CONFIDENCE_TIE",
            "COVERAGE_TIE_BREAK_MISSING",
        ),
        (
            "SCORE_TIE_HIGHER_CONFIDENCE_WINS",
            "COVERAGE_CONFIDENCE_TIE_BREAK_MISSING",
        ),
        (
            "OPTIONAL_EXTERNAL_UNAVAILABLE",
            "COVERAGE_OPTIONAL_WARNING_MISSING",
        ),
        (
            "GROUPED_PILLAR_PROVENANCE",
            "COVERAGE_GROUPED_PROVENANCE_MISSING",
        ),
        (
            "CONFIDENCE_LEDGER_DUPLICATE_INPUT",
            "COVERAGE_DUPLICATE_LEDGER_MISSING",
        ),
        (
            "SELECTED_ACTION_INVARIANT_FAILURE",
            "COVERAGE_INVARIANT_FAILURE_MISSING",
        ),
    ),
)
def test_specialized_coverage_removal_produces_exact_failure(
    removed_scenario_id,
    expected_failure_code,
):
    catalog = get_task2_decision_certification_scenarios()

    subset = tuple(
        scenario
        for scenario in catalog
        if scenario.scenario_id != removed_scenario_id
    )

    result = run_all_task2_decision_certification_scenarios(
        scenarios=subset
    )

    assert result.overall_status == "FAILED"
    assert result.coverage_failure_codes == (expected_failure_code,)


def test_multiple_missing_coverage_codes_follow_policy_order():
    catalog = get_task2_decision_certification_scenarios()

    removed_ids = {
        "EQUAL_SCORE_CONFIDENCE_TIE",
        "SCORE_TIE_HIGHER_CONFIDENCE_WINS",
        "OPTIONAL_EXTERNAL_UNAVAILABLE",
        "GROUPED_PILLAR_PROVENANCE",
        "CONFIDENCE_LEDGER_DUPLICATE_INPUT",
        "SELECTED_ACTION_INVARIANT_FAILURE",
    }

    subset = tuple(
        scenario
        for scenario in catalog
        if scenario.scenario_id not in removed_ids
    )

    result = run_all_task2_decision_certification_scenarios(
        scenarios=subset
    )

    assert result.overall_status == "FAILED"
    assert result.coverage_failure_codes == (
        "COVERAGE_TIE_BREAK_MISSING",
        "COVERAGE_CONFIDENCE_TIE_BREAK_MISSING",
        "COVERAGE_OPTIONAL_WARNING_MISSING",
        "COVERAGE_GROUPED_PROVENANCE_MISSING",
        "COVERAGE_DUPLICATE_LEDGER_MISSING",
        "COVERAGE_INVARIANT_FAILURE_MISSING",
    )


def test_supplied_scenario_order_is_preserved():
    catalog = get_task2_decision_certification_scenarios()

    subset = (
        catalog[3],
        catalog[0],
        catalog[10],
        catalog[9],
    )

    result = run_all_task2_decision_certification_scenarios(
        scenarios=subset
    )

    assert _result_scenario_ids(result) == _scenario_ids(subset)


def test_reversed_subset_changes_aggregate_order_but_not_individual_results():
    catalog = get_task2_decision_certification_scenarios()

    subset = tuple(catalog[:5])
    reversed_subset = tuple(reversed(subset))

    forward = run_all_task2_decision_certification_scenarios(
        scenarios=subset
    )
    backward = run_all_task2_decision_certification_scenarios(
        scenarios=reversed_subset
    )

    assert _result_scenario_ids(forward) == _scenario_ids(subset)
    assert _result_scenario_ids(backward) == _scenario_ids(
        reversed_subset
    )

    assert forward.deterministic_checksum != backward.deterministic_checksum

    forward_checksums = {
        result.scenario_id: result.deterministic_checksum
        for result in forward.scenario_results
    }
    backward_checksums = {
        result.scenario_id: result.deterministic_checksum
        for result in backward.scenario_results
    }

    assert forward_checksums == backward_checksums


def test_duplicate_scenario_ids_are_rejected():
    catalog = get_task2_decision_certification_scenarios()
    duplicate_subset = (catalog[0], catalog[0])

    with pytest.raises(
        ValueError,
        match="DUPLICATE_SCENARIO_ID",
    ):
        run_all_task2_decision_certification_scenarios(
            scenarios=duplicate_subset
        )


def test_empty_scenario_sequence_is_rejected():
    with pytest.raises(
        ValueError,
        match="EMPTY_SCENARIO_SEQUENCE",
    ):
        run_all_task2_decision_certification_scenarios(
            scenarios=()
        )


def test_subset_runs_do_not_mutate_catalog_or_fixture_objects():
    catalog_before = get_task2_decision_certification_scenarios()
    ids_before = _scenario_ids(catalog_before)

    selected_fixture = catalog_before[0]
    fixture_repr_before = repr(selected_fixture)

    run_all_task2_decision_certification_scenarios(
        scenarios=tuple(catalog_before[:4])
    )

    catalog_after = get_task2_decision_certification_scenarios()

    assert _scenario_ids(catalog_after) == ids_before
    assert repr(selected_fixture) == fixture_repr_before
def test_one_failed_scenario_makes_complete_aggregate_fail():
    catalog = get_task2_decision_certification_scenarios()

    changed_fixture = replace(
        catalog[0],
        expected_selected_market="SENSEX",
    )

    modified_catalog = (
        changed_fixture,
        *catalog[1:],
    )

    result = run_all_task2_decision_certification_scenarios(
        scenarios=modified_catalog
    )

    changed_result = result.scenario_results[0]

    assert changed_result.scenario_id == "NIFTY_CALL_WINS"
    assert changed_result.selected_market == "NIFTY"
    assert changed_result.certification_status != "PASS"
    assert (
        "EXPECTED_SELECTED_MARKET_MISMATCH"
        in changed_result.certification_failure_codes
    )

    assert result.total_scenarios == 19
    assert result.passed_scenarios == 18
    assert result.failed_scenarios == 1
    assert result.overall_status == "FAILED"

    unchanged = run_all_task2_decision_certification_scenarios()

    for actual, baseline in zip(
        result.scenario_results[1:],
        unchanged.scenario_results[1:],
        strict=True,
    ):
        assert actual.to_json() == baseline.to_json()


def test_nonzero_safety_counter_makes_aggregate_fail():
    passing = run_all_task2_decision_certification_scenarios()

    first_result = passing.scenario_results[0]
    original_safety = tuple(first_result.safety_counters)

    assert original_safety
    assert all(value == 0 for _, value in original_safety)

    first_key = original_safety[0][0]

    changed_safety = tuple(
        (
            key,
            1 if key == first_key else value,
        )
        for key, value in original_safety
    )

    unsafe_result = replace(
        first_result,
        safety_counters=changed_safety,
    )

    modified_results = (
        unsafe_result,
        *passing.scenario_results[1:],
    )

    aggregate = build_task2_decision_certification_aggregate(
        modified_results
    )

    safety = dict(aggregate.aggregate_safety_counters)

    assert safety[first_key] == 1

    for key, value in safety.items():
        if key != first_key:
            assert value == 0

    assert aggregate.passed_scenarios == 19
    assert aggregate.failed_scenarios == 0
    assert aggregate.overall_status == "FAILED"
    assert (
        "SAFETY_COUNTER_NONZERO"
        in aggregate.coverage_failure_codes
    )


def test_aggregate_builder_rejects_empty_results():
    with pytest.raises(
        ValueError,
        match="EMPTY_CERTIFICATION_RESULTS",
    ):
        build_task2_decision_certification_aggregate(())


def test_aggregate_builder_rejects_duplicate_result_ids():
    passing = run_all_task2_decision_certification_scenarios()
    duplicate = passing.scenario_results[0]

    with pytest.raises(
        ValueError,
        match="DUPLICATE_CERTIFICATION_RESULT_ID",
    ):
        build_task2_decision_certification_aggregate(
            (duplicate, duplicate)
        )


def test_safety_failure_is_deterministic():
    passing = run_all_task2_decision_certification_scenarios()

    first_result = passing.scenario_results[0]
    key = first_result.safety_counters[0][0]

    changed_safety = tuple(
        (
            current_key,
            1 if current_key == key else value,
        )
        for current_key, value in first_result.safety_counters
    )

    unsafe_result = replace(
        first_result,
        safety_counters=changed_safety,
    )

    modified_results = (
        unsafe_result,
        *passing.scenario_results[1:],
    )

    first = build_task2_decision_certification_aggregate(
        modified_results
    )
    second = build_task2_decision_certification_aggregate(
        modified_results
    )

    assert first.overall_status == "FAILED"
    assert first.coverage_failure_codes == (
        "SAFETY_COUNTER_NONZERO",
    )
    assert (
        first.deterministic_checksum
        == second.deterministic_checksum
    )
    assert (
        first.aggregate_safety_counters
        == second.aggregate_safety_counters
    )