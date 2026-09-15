from pathlib import Path

import pytest

from tests.support.task9_evidence_rehydration import (
    rehydrate_option_ranking,
    rehydrate_task9_evaluation_snapshot,
)


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "data" / "task9" / "live-decision-audit.json"


@pytest.mark.parametrize(
    ("observation_id", "expected"),
    (
        ("task9-nifty-2026-08-24T14:16:19+05:30", "61646"),
        ("task9-sensex-2026-08-26T12:05:02+05:30", "827549"),
    ),
)
def test_selected_contract_is_derived_from_first_ranked_candidate(
    observation_id,
    expected,
):
    import json

    payload = json.loads(AUDIT.read_text(encoding="utf-8"))
    record = next(
        value
        for value in payload["records"].values()
        if value["observation_id"] == observation_id
    )
    identity = rehydrate_option_ranking(
        record["evaluation_snapshot"]["candidate"][
            "option_contract_eligibility"
        ],
        observation_id=observation_id,
    )
    assert identity.selected_contract_id == expected


@pytest.mark.parametrize(
    "observation_id",
    (
        "task9-nifty-2026-08-24T14:16:19+05:30",
        "task9-sensex-2026-08-26T12:05:02+05:30",
    ),
)
def test_full_rehydration_reconstructs_composition_graph(
    observation_id,
):
    composition = rehydrate_task9_evaluation_snapshot(
        audit_path=AUDIT,
        observation_id=observation_id,
    )
    assert type(composition).__name__ == "MarketAnalysisCandidateCompositionInputV1"
