from dataclasses import replace
from datetime import datetime, timezone

from services.certification.task2_decision_certification_scenarios import (
    get_task2_decision_certification_scenarios,
)
from services.certification.task2_decision_fixture_factory import (
    PILLAR_ORDER,
    foundation_fixtures,
)
from services.certification.task2_end_to_end_decision_certification import (
    compose_task2_decision_certification,
)
import services.certification.task2_end_to_end_decision_certification as composer

NOW=datetime(2026,8,3,tzinfo=timezone.utc)
def test_foundation_fixtures_are_deterministic_and_parent_cycle_coherent():
 results=tuple(compose_task2_decision_certification(value) for value in foundation_fixtures(NOW))
 assert len(results)==5
 for result in results:
  assert result.nifty.parent_cycle_id==result.sensex.parent_cycle_id==result.parent_cycle_id
  assert result.nifty.observation_id!=result.sensex.observation_id
  if result.nifty.candidate_id is not None and result.sensex.candidate_id is not None: assert result.nifty.candidate_id!=result.sensex.candidate_id
  assert result.safety_counters and all(value==0 for _,value in result.safety_counters)
 assert results[0].nifty.pre_entry_action=="CALL"
 assert results[1].sensex.pre_entry_action=="PUT"
 assert results[0].nifty.ordered_pillar_names==PILLAR_ORDER

def test_fully_reached_scenario_invokes_each_production_builder_exactly_once_per_stage(monkeypatch):
 fixture=foundation_fixtures(NOW)[0];counts={};values={}
 for name in ("build_market_analysis_pillar_contributions","build_market_analysis_confidence_ledger","resolve_pre_entry_market_action","build_market_decision_explanation","rank_two_market_candidates","project_parent_pre_entry_action","build_two_market_decision_explanation"):
  original=getattr(composer,name)
  def wrapper(*args,_original=original,_name=name,**kwargs):counts[_name]=counts.get(_name,0)+1;return _original(*args,**kwargs)
  values[{"build_market_analysis_pillar_contributions":"build_pillar_contributions","build_market_analysis_confidence_ledger":"build_confidence_ledger","resolve_pre_entry_market_action":"resolve_child_action","build_market_decision_explanation":"build_child_explanation","rank_two_market_candidates":"rank_two_markets","project_parent_pre_entry_action":"project_parent_action","build_two_market_decision_explanation":"build_parent_explanation"}[name]]=wrapper
 from dataclasses import replace
 compose_task2_decision_certification(fixture,dependencies=replace(composer.DEFAULT_DEPENDENCIES,**values))
 assert counts=={"build_market_analysis_pillar_contributions":2,"build_market_analysis_confidence_ledger":2,"resolve_pre_entry_market_action":2,"build_market_decision_explanation":2,"rank_two_market_candidates":1,"project_parent_pre_entry_action":1,"build_two_market_decision_explanation":1}

def test_fixture_expectations_do_not_control_production_selected_market_or_parent_output():
 fixture=foundation_fixtures(NOW)[0]
 changed=replace(fixture,expected_selected_market="SENSEX",expected_parent_action="PUT",expected_parent_status="NO_TRADE")
 actual=compose_task2_decision_certification(changed)
 assert (actual.selected_market,actual.parent_action,actual.parent_decision_status)==("NIFTY","CALL","SELECTED")
 assert set(actual.certification_failure_codes)=={"EXPECTED_SELECTED_MARKET_MISMATCH","EXPECTED_PARENT_ACTION_MISMATCH","EXPECTED_PARENT_STATUS_MISMATCH"}
def _catalog_fixture(scenario_id):
    for fixture in get_task2_decision_certification_scenarios():
        if fixture.scenario_id == scenario_id:
            return fixture
    raise AssertionError(f"missing scenario: {scenario_id}")


def test_injected_action_output_is_used_in_certification():
    fixture = _catalog_fixture("NIFTY_CALL_WINS")
    original_resolver = composer.DEFAULT_DEPENDENCIES.resolve_child_action

    def changed_action(*args, **kwargs):
        action = original_resolver(*args, **kwargs)

        if action.underlying_symbol != "NIFTY":
            return action

        return replace(
            action,
            action_id=f"{action.action_id}:injected",
            warnings=action.warnings + ("CERTIFICATION_ACTION_OVERRIDE",),
        )

    dependencies = replace(
        composer.DEFAULT_DEPENDENCIES,
        resolve_child_action=changed_action,
    )

    baseline = compose_task2_decision_certification(fixture)
    actual = compose_task2_decision_certification(
        fixture,
        dependencies=dependencies,
    )

    assert baseline.nifty.pre_entry_action == "CALL"
    assert actual.nifty.pre_entry_action == "CALL"

    assert actual.nifty.pre_entry_action_id == (
        f"{baseline.nifty.pre_entry_action_id}:injected"
    )
    assert "CERTIFICATION_ACTION_OVERRIDE" in actual.nifty.warnings

    assert actual.nifty.legacy_confidence == baseline.nifty.legacy_confidence
    assert actual.nifty.legacy_score == baseline.nifty.legacy_score
    assert actual.selected_market == baseline.selected_market
    assert actual.parent_action == baseline.parent_action


def test_injected_shadow_ledger_values_are_used_without_replacing_candidate_values():
    fixture = _catalog_fixture("NIFTY_CALL_WINS")
    original_builder = composer.DEFAULT_DEPENDENCIES.build_confidence_ledger

    def changed_ledger(*args, **kwargs):
        ledger = original_builder(*args, **kwargs)

        if ledger.underlying_symbol != "NIFTY":
            return ledger

        changed_confidence = min(100.0, ledger.final_confidence + 3.0)
        changed_score = min(100.0, ledger.final_score + 2.0)

        return replace(
            ledger,
            final_confidence=changed_confidence,
            final_score=changed_score,
        )

    dependencies = replace(
        composer.DEFAULT_DEPENDENCIES,
        build_confidence_ledger=changed_ledger,
    )

    baseline = compose_task2_decision_certification(fixture)
    actual = compose_task2_decision_certification(
        fixture,
        dependencies=dependencies,
    )

    assert actual.nifty.ledger_confidence == min(
        100.0,
        baseline.nifty.ledger_confidence + 3.0,
    )
    assert actual.nifty.ledger_score == min(
        100.0,
        baseline.nifty.ledger_score + 2.0,
    )

    assert actual.nifty.confidence_delta == (
        actual.nifty.ledger_confidence
        - actual.nifty.legacy_confidence
    )
    assert actual.nifty.score_delta == (
        actual.nifty.ledger_score
        - actual.nifty.legacy_score
    )

    assert actual.nifty.legacy_confidence == baseline.nifty.legacy_confidence
    assert actual.nifty.legacy_score == baseline.nifty.legacy_score
    assert actual.nifty.pre_entry_action == baseline.nifty.pre_entry_action
    assert actual.selected_market == baseline.selected_market


def test_injected_valid_contribution_provenance_is_used():
    fixture = _catalog_fixture("NIFTY_CALL_WINS")
    original_builder = composer.DEFAULT_DEPENDENCIES.build_pillar_contributions

    changed_value = {}

    def changed_contributions(*args, **kwargs):
        collection = original_builder(*args, **kwargs)

        if collection.underlying_symbol != "NIFTY":
            return collection

        first = collection.contributions[0]

        replacement_provenance = (
            "DERIVED"
            if first.provenance_classification != "DERIVED"
            else "DIRECT"
        )

        changed_value["before"] = first.provenance_classification
        changed_value["after"] = replacement_provenance

        changed_first = replace(
            first,
            provenance_classification=replacement_provenance,
        )

        return replace(
            collection,
            contributions=(
                changed_first,
                *collection.contributions[1:],
            ),
        )

    dependencies = replace(
        composer.DEFAULT_DEPENDENCIES,
        build_pillar_contributions=changed_contributions,
    )

    baseline = compose_task2_decision_certification(fixture)
    actual = compose_task2_decision_certification(
        fixture,
        dependencies=dependencies,
    )

    assert actual.nifty.pillar_contribution_count == 14
    assert actual.nifty.ordered_pillar_names == PILLAR_ORDER

    assert baseline.nifty.pillar_provenance_summary[0] == changed_value["before"]
    assert actual.nifty.pillar_provenance_summary[0] == changed_value["after"]

    assert actual.nifty.pillar_provenance_summary[0] != (
        baseline.nifty.pillar_provenance_summary[0]
    )

    assert actual.nifty.legacy_confidence == baseline.nifty.legacy_confidence
    assert actual.nifty.legacy_score == baseline.nifty.legacy_score


def test_injected_ranker_result_controls_actual_parent_selection():
    fixture = _catalog_fixture("EQUAL_SCORE_CONFIDENCE_TIE")
    original_ranker = composer.DEFAULT_DEPENDENCIES.rank_two_markets

    def changed_ranker(*args, **kwargs):
        decision = original_ranker(*args, **kwargs)

        assert decision.decision == "SELECTED"
        assert decision.selected_market == ("NIFTY", "NSE")

        nifty_entry, sensex_entry = decision.entries

        changed_nifty = replace(
            nifty_entry,
            outcome_reason="TIE_BREAK_LOSS",
        )
        changed_sensex = replace(
            sensex_entry,
            outcome_reason="SELECTED",
        )

        return replace(
            decision,
            entries=(changed_nifty, changed_sensex),
            selected_market=("SENSEX", "BSE"),
            selected_candidate_id=(
                changed_sensex.child.candidate.candidate_id
            ),
        )

    dependencies = replace(
        composer.DEFAULT_DEPENDENCIES,
        rank_two_markets=changed_ranker,
    )

    baseline = compose_task2_decision_certification(fixture)
    actual = compose_task2_decision_certification(
        fixture,
        dependencies=dependencies,
    )

    assert baseline.selected_market == "NIFTY"
    assert actual.selected_market == "SENSEX"

    assert "EXPECTED_SELECTED_MARKET_MISMATCH" in (
        actual.certification_failure_codes
    )

    assert actual.nifty.pre_entry_action == baseline.nifty.pre_entry_action
    assert actual.sensex.pre_entry_action == baseline.sensex.pre_entry_action

    selected_child_action = actual.sensex.pre_entry_action
    assert actual.parent_action == selected_child_action


def test_injected_child_explanation_output_is_used():
    fixture = _catalog_fixture("NIFTY_CALL_WINS")
    original_builder = composer.DEFAULT_DEPENDENCIES.build_child_explanation

    def changed_explanation(*args, **kwargs):
        explanation = original_builder(*args, **kwargs)

        if explanation.underlying_symbol != "NIFTY":
            return explanation

        return replace(
            explanation,
            explanation_id=f"{explanation.explanation_id}:injected",
        )

    dependencies = replace(
        composer.DEFAULT_DEPENDENCIES,
        build_child_explanation=changed_explanation,
    )

    baseline = compose_task2_decision_certification(fixture)
    actual = compose_task2_decision_certification(
        fixture,
        dependencies=dependencies,
    )

    assert actual.nifty.child_explanation_id == (
        f"{baseline.nifty.child_explanation_id}:injected"
    )
    assert actual.sensex.child_explanation_id == (
        baseline.sensex.child_explanation_id
    )


def test_injected_parent_explanation_output_is_used():
    fixture = _catalog_fixture("NIFTY_CALL_WINS")
    original_builder = composer.DEFAULT_DEPENDENCIES.build_parent_explanation

    def changed_parent_explanation(*args, **kwargs):
        explanation = original_builder(*args, **kwargs)

        return replace(
            explanation,
            explanation_id=f"{explanation.explanation_id}:injected",
        )

    dependencies = replace(
        composer.DEFAULT_DEPENDENCIES,
        build_parent_explanation=changed_parent_explanation,
    )

    baseline = compose_task2_decision_certification(fixture)
    actual = compose_task2_decision_certification(
        fixture,
        dependencies=dependencies,
    )

    assert actual.parent_explanation_id == (
        f"{baseline.parent_explanation_id}:injected"
    )

    assert actual.selected_market == baseline.selected_market
    assert actual.parent_action == baseline.parent_action
    assert actual.parent_decision_status == baseline.parent_decision_status

def test_explicit_default_dependencies_are_identical_to_omitted_defaults():
 fixture=foundation_fixtures(NOW)[0]
 implicit=compose_task2_decision_certification(fixture)
 explicit=compose_task2_decision_certification(fixture,dependencies=composer.DEFAULT_DEPENDENCIES)
 assert implicit.to_json()==explicit.to_json()
