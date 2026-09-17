from copy import deepcopy
import json
from pathlib import Path

import pytest

from tests.support.task9_evidence_rehydration import (
    RehydrationIncomplete,
    RehydrationInvalid,
    RehydrationTypeTagMismatch,
    rehydrate_task9_evaluation_snapshot,
    rehydrate_typed_option_ranking,
)


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "data" / "task9" / "live-decision-audit.json"
OBSERVATIONS = (
    "task9-nifty-2026-08-24T14:16:19+05:30",
    "task9-sensex-2026-08-26T12:05:02+05:30",
)


def _ranking(observation_id):
    payload = json.loads(AUDIT.read_text(encoding="utf-8"))
    record = next(
        value for value in payload["records"].values()
        if value["observation_id"] == observation_id
    )
    return record["evaluation_snapshot"]["candidate"]["option_contract_eligibility"]


@pytest.mark.parametrize("observation_id", OBSERVATIONS)
def test_typed_ranking_preserves_tuple_shape_and_selected_derivation(observation_id):
    ranking = rehydrate_typed_option_ranking(
        _ranking(observation_id), observation_id=observation_id,
        path="$.candidate.option_contract_eligibility",
    )
    assert type(ranking.ranked_candidates) is tuple
    assert ranking.selected_candidate is ranking.ranked_candidates[0]
    assert ranking.selected_candidate.contract.contract_id in {"61646", "827549"}


def test_type_tag_mismatch_is_path_precise():
    ranking = deepcopy(_ranking(OBSERVATIONS[0]))
    ranking["__type__"] = "WrongType"
    with pytest.raises(RehydrationTypeTagMismatch, match=r"\$\.candidate\.option_contract_eligibility"):
        rehydrate_typed_option_ranking(
            ranking, observation_id=OBSERVATIONS[0],
            path="$.candidate.option_contract_eligibility",
        )


def test_malformed_datetime_is_rejected_with_exact_path():
    ranking = deepcopy(_ranking(OBSERVATIONS[0]))
    ranking["ranked_at"] = "not-a-datetime"
    ranking["ranked_candidates"] = []
    ranking["rejected_candidates"] = []
    with pytest.raises(RehydrationInvalid, match=r"ranked_at.*malformed datetime"):
        rehydrate_typed_option_ranking(
            ranking, observation_id=OBSERVATIONS[0],
            path="$.candidate.option_contract_eligibility",
        )


def test_nested_type_tag_mismatch_is_path_precise():
    payload = json.loads(AUDIT.read_text(encoding="utf-8"))
    record = next(
        value
        for value in payload["records"].values()
        if value["observation_id"] == OBSERVATIONS[0]
    )

    composition = deepcopy(
        record["evaluation_snapshot"]["composition"]
    )
    composition["freshness"]["__type__"] = "WrongType"

    with pytest.raises(
        RehydrationTypeTagMismatch,
        match=r"\$\.composition\.freshness",
    ):
        from tests.support.task9_evidence_rehydration import (
            rehydrate_market_analysis_composition,
        )

        rehydrate_market_analysis_composition(
            composition,
            observation_id=OBSERVATIONS[0],
        )
def test_composition_mapping_fidelity_is_preserved():
    observation_id = OBSERVATIONS[0]

    payload = json.loads(AUDIT.read_text(encoding="utf-8"))
    record = next(
        value
        for value in payload["records"].values()
        if value["observation_id"] == observation_id
    )

    persisted = record["evaluation_snapshot"]["composition"]

    composition = rehydrate_task9_evaluation_snapshot(
        audit_path=AUDIT,
        observation_id=observation_id,
    )

    assert dict(composition.evidence_references) == persisted["evidence_references"]
    assert dict(composition.provenance) == persisted["provenance"]

    assert type(composition.evidence_references).__name__ == "mappingproxy"
    assert type(composition.provenance).__name__ == "mappingproxy"