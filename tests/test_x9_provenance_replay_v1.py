"""B4 replays five original X8/X9 records and independently anchored digests."""

from dataclasses import replace
from datetime import timedelta

import pytest
from test_x9_ledger_v1 import NOW, ledger, result

from services.x7.contracts_v1 import MARKETS
from services.x8.regime_description_v1 import describe_x8_regime_evidence_v1
from services.x9.comparison_safeguards_v1 import audit_x9_comparison_safeguards_v1
from services.x9.provenance_replay_v1 import replay_x9_provenance_v1
from services.x9.research_eligibility_v1 import evaluate_x9_research_eligibility_v1
from services.x9.session_prerequisites_v1 import build_x9_session_matrix_v1


def original(*, blocked_market=None):
    refs = tuple(
        result(m, NOW - timedelta(seconds=3) if m == blocked_market else NOW) for m in MARKETS
    )
    base = ledger(refs, skew=100)
    matrix = build_x9_session_matrix_v1(
        ledger=base,
        readiness=refs,
        reported_states=tuple((m, "REPORTED_OPEN") for m in MARKETS),
    )
    descriptions = tuple(
        describe_x8_regime_evidence_v1(
            readiness=r,
            max_age_seconds=1 if r.market == blocked_market else 60,
        )
        for r in refs
    )
    eligibility = evaluate_x9_research_eligibility_v1(
        ledger=base,
        session_matrix=matrix,
        readiness=refs,
        descriptions=descriptions,
    )
    guards = audit_x9_comparison_safeguards_v1(
        ledger=base,
        eligibility=eligibility,
        max_capture_skew_seconds=15,
    )
    args = dict(
        ledger=base,
        expected_ledger_sha256=base.sha256(),
        matrix=matrix,
        expected_matrix_sha256=matrix.sha256(),
        readiness=refs,
        descriptions=descriptions,
        eligibility=eligibility,
        expected_eligibility_sha256=eligibility.sha256(),
        safeguards=guards,
        expected_safeguards_sha256=guards.sha256(),
    )
    return args


def test_complete_descriptive_replay_is_never_ranking():
    out = replay_x9_provenance_v1(**original())
    assert out.status == "REPLAYED_DESCRIPTIVE"
    assert out.selected_market is None and out.rankings == ()
    assert not out.execution_authority
    assert tuple(m for m, _ in out.market_readiness_hashes) == MARKETS


@pytest.mark.parametrize("market", MARKETS)
def test_incomplete_input_is_not_upgraded(market):
    out = replay_x9_provenance_v1(**original(blocked_market=market))
    assert out.status == "INCOMPLETE_DESCRIPTIVE"


@pytest.mark.parametrize(
    "name",
    (
        "expected_ledger_sha256",
        "expected_matrix_sha256",
        "expected_eligibility_sha256",
        "expected_safeguards_sha256",
    ),
)
def test_external_hash_mismatch_fails_closed(name):
    a = original()
    a[name] = "f" * 64
    with pytest.raises(ValueError, match="digest"):
        replay_x9_provenance_v1(**a)


def test_missing_market_rejected():
    a = original()
    a["readiness"] = a["readiness"][:-1]
    with pytest.raises(ValueError, match="five"):
        replay_x9_provenance_v1(**a)


def test_changed_reported_state_rejects_original_proof():
    a = original()
    m = a["matrix"]
    from services.x9.session_prerequisites_v1 import X9SessionMatrixV1

    a["matrix"] = X9SessionMatrixV1(
        m.parent_cycle_id,
        m.as_of,
        m.x9_ledger_sha256,
        m.prerequisites[:-1]
        + (
            replace(
                m.prerequisites[-1],
                reported_state="UNKNOWN",
                session_source_sha256=None,
                observed_at=None,
            ),
        ),
        "INCOMPLETE_DESCRIPTIVE",
        m.reported_index_overlap,
    )
    a["expected_matrix_sha256"] = a["matrix"].sha256()
    with pytest.raises(ValueError):
        replay_x9_provenance_v1(**a)


def test_no_authority_escalation():
    with pytest.raises(ValueError):
        replace(replay_x9_provenance_v1(**original()), independent_vote=True)
