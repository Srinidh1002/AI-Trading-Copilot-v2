"""X6-B4 independent witnesses, recomputation, chronology, transitions and authority."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, replace
from datetime import date, timedelta
from pathlib import Path

import pytest
from test_x6_volatility_regime_v1 import MARKETS, prior, sample

from services.x5.contracts_v1 import canonical_sha256
from services.x6.replay_provenance_v1 import (
    X6ReplayReferenceInputV1,
    replay_x6_history_v1,
    seal_x6_replay_frame_v1,
)


def frame(market="NIFTY", *, pit=True, history=(), reference=False):
    x5, cap, _ = sample(market, pit=pit)
    b1 = X6ReplayReferenceInputV1(0.25, "independent-vol-source", True) if reference else None
    return seal_x6_replay_frame_v1(source_x5=x5, capture=cap, history=history, reference_input=b1)


def later(
    origin,
    *,
    hours=1,
    suffix="2",
    more_strike=False,
    changed_id=False,
    new_expiry=False,
    new_session=False,
    new_rate_source=False,
):
    x5, cap = origin.source_x5, origin.capture
    clock = cap.context.as_of + timedelta(hours=hours)
    expiry = (
        cap.context.option_expiry + timedelta(days=7) if new_expiry else cap.context.option_expiry
    )
    session = f"session-{suffix}" if new_session else cap.session_id
    rows5 = []
    rows6 = []
    for row in x5.observations:
        suffix_id = f"-{suffix}" if new_expiry or changed_id else ""
        oid = row.canonical_option_id + suffix_id
        provider = row.provider_symbol + suffix_id
        source = f"{row.source_record_id}-{suffix}"
        rows5.append(
            replace(
                row,
                expiry=expiry,
                canonical_option_id=oid,
                provider_symbol=provider,
                source_record_id=source,
                observed_at=clock,
            )
        )
        old = next(
            r
            for r in cap.observations
            if r.option_type == row.option_type and r.strike == row.strike
        )
        rows6.append(
            replace(old, canonical_option_id=oid, source_record_id=source, observed_at=clock)
        )
    if more_strike:
        x5_base = rows5[0]
        x6_base = rows6[0]
        rows5.append(
            replace(
                x5_base,
                strike=105.0,
                canonical_option_id=f"{x5_base.canonical_option_id}-105",
                provider_symbol=f"{x5_base.provider_symbol}-105",
                source_record_id=f"{x5_base.source_record_id}-105",
            )
        )
        rows6.append(
            replace(
                x6_base,
                strike=105.0,
                canonical_option_id=f"{x6_base.canonical_option_id}-105",
                source_record_id=f"{x6_base.source_record_id}-105",
            )
        )
    x5_next = replace(
        x5,
        contract=replace(x5.contract, expiry=expiry),
        session_id=session,
        capture_id=f"capture-{suffix}",
        source_id=f"source-{suffix}",
        as_of=clock,
        captured_at=clock,
        observations=tuple(rows5),
    )
    ctx = replace(
        cap.context,
        as_of=clock,
        option_expiry=expiry,
        option_expiry_at=cap.context.option_expiry_at + timedelta(days=7)
        if new_expiry
        else cap.context.option_expiry_at,
        rate_source_id=f"rate-{suffix}" if new_rate_source else cap.context.rate_source_id,
    )
    cap_next = replace(
        cap,
        context=ctx,
        session_id=session,
        capture_id=f"capture-{suffix}",
        observations=tuple(rows6),
        source_x5_capture_sha256=x5_next.sha256(),
    )
    return seal_x6_replay_frame_v1(source_x5=x5_next, capture=cap_next)


@pytest.mark.parametrize("market", MARKETS)
def test_all_markets_single_frame_witnesses_and_model(market):
    f = frame(market)
    r = replay_x6_history_v1(frames=(f,))
    record = r.records[0]
    assert r.market == market and record.market == market
    assert record.model == f.capture.context.model
    assert record.transition == "FIRST_FRAME"
    assert record.source_x5_sha256 == f.source_x5.sha256()
    assert record.source_x6_sha256 == f.capture.sha256()
    assert record.validation_sha256 == f.validation.sha256()
    assert record.iv_greeks_sha256 == f.iv_greeks.sha256()
    assert record.regime_sha256 == f.regime.sha256()
    assert record.reference_sha256 is None
    assert record.capture_window_sha256 == canonical_sha256(
        tuple(
            sorted(
                (float(row.strike), row.option_type, row.canonical_option_id)
                for row in f.capture.observations
            )
        )
    )
    assert r.final_record_sha256 == record.sha256()
    assert r.source_frame_count == 1
    assert r.expiry_transition_count == r.window_transition_count == r.retrospective_count == 0
    assert r.sha256() == replay_x6_history_v1(frames=(f,)).sha256()


@pytest.mark.parametrize("market", MARKETS)
def test_optional_reference_b1_is_recomputed(market):
    f = frame(market, reference=True)
    r = replay_x6_history_v1(frames=(f,))
    assert f.reference.status == "AVAILABLE"
    assert r.records[0].reference_status == "AVAILABLE"
    assert r.records[0].reference_sha256 == f.reference.sha256()
    assert f.reference_input.annual_volatility == 0.25


@pytest.mark.parametrize("market", MARKETS)
def test_retrospective_results_cannot_be_promoted(market):
    f = frame(market, pit=False, reference=True)
    r = replay_x6_history_v1(frames=(f,))
    rec = r.records[0]
    assert rec.observation_provenance == "RETROSPECTIVE_UNPROVEN"
    assert rec.iv_greeks_status == rec.regime_status == rec.reference_status == "RETROSPECTIVE"
    assert r.retrospective_count == 1
    assert r.cross_frame_metric_comparison_allowed is False


@pytest.mark.parametrize(
    "tamper",
    (
        "expected_x5_sha256",
        "expected_x6_sha256",
        "expected_validation_sha256",
        "expected_iv_greeks_sha256",
        "expected_regime_sha256",
        "expected_x5_row_seals",
        "expected_x6_row_seals",
    ),
)
def test_independently_retained_witness_detects_tampering(tamper):
    f = frame()
    if "row_seals" in tamper:
        rows = getattr(f, tamper)
        value = ((rows[0][0], "f" * 64),) + rows[1:]
        value = tuple(sorted(value))
    else:
        value = "f" * 64
    altered = replace(f, **{tamper: value})
    with pytest.raises(ValueError, match="MISMATCH"):
        replay_x6_history_v1(frames=(altered,))


def test_external_x5_capture_modification_detected():
    f = frame()
    changed = replace(f.source_x5, source_id="changed-original-source")
    with pytest.raises(ValueError, match="SOURCE_OR_ROW_WITNESS_MISMATCH"):
        replay_x6_history_v1(frames=(replace(f, source_x5=changed),))


def test_external_x6_capture_modification_detected():
    f = frame()
    changed = replace(
        f.capture, context=replace(f.capture.context, reference_source_id="changed-reference")
    )
    with pytest.raises(ValueError, match="SOURCE_OR_ROW_WITNESS_MISMATCH"):
        replay_x6_history_v1(frames=(replace(f, capture=changed),))


@pytest.mark.parametrize(
    "field, extra",
    (
        ("validation", "warnings"),
        ("iv_greeks", "warnings"),
        ("regime", "warnings"),
        ("reference", "warnings"),
    ),
)
def test_stored_outputs_cannot_be_changed_without_witness(field, extra):
    f = frame(reference=True)
    old = getattr(f, field)
    changed = replace(old, **{extra: old.warnings + ("ALTERED",)})
    with pytest.raises(ValueError, match="MISMATCH"):
        replay_x6_history_v1(frames=(replace(f, **{field: changed}),))


def test_changed_b1_recompute_inputs_fail_against_original_witness():
    f = frame(reference=True)
    changed = replace(f.reference_input, annual_volatility=0.45)
    with pytest.raises(ValueError, match="REFERENCE_PRICING_REPLAY_MISMATCH"):
        replay_x6_history_v1(frames=(replace(f, reference_input=changed),))


@pytest.mark.parametrize("market", MARKETS)
def test_current_regime_with_history_has_traceable_hashes(market):
    f = frame(market, history=prior(market))
    result = replay_x6_history_v1(frames=(f,))
    assert f.regime.status == "AVAILABLE"
    assert len(f.expected_history_sha256) == 20
    assert result.records[0].history_witness_sha256 == canonical_sha256(f.expected_history_sha256)
    assert result.records[0].regime_status == "AVAILABLE"


def test_history_row_witness_tampering_is_rejected():
    f = frame(history=prior())
    changed = replace(f, expected_history_sha256=("f" * 64,) + f.expected_history_sha256[1:])
    with pytest.raises(ValueError, match="SOURCE_OR_ROW_WITNESS_MISMATCH"):
        replay_x6_history_v1(frames=(changed,))


def test_history_point_modification_is_rejected():
    f = frame(history=prior())
    h = (replace(f.history[0], atm_iv_decimal=0.7),) + f.history[1:]
    with pytest.raises(ValueError, match="SOURCE_OR_ROW_WITNESS_MISMATCH"):
        replay_x6_history_v1(frames=(replace(f, history=h),))


@pytest.mark.parametrize("market", MARKETS)
def test_two_frame_same_window_has_record_hash_chain(market):
    first = frame(market)
    second = later(first)
    r = replay_x6_history_v1(frames=(first, second))
    assert tuple(x.transition for x in r.records) == ("FIRST_FRAME", "SAME_WINDOW")
    assert r.records[1].previous_record_sha256 == r.records[0].sha256()
    assert r.final_record_sha256 == r.records[1].sha256()
    assert (
        r.sha256()
        == replay_x6_history_v1(frames=(first, second), expected_final_sha256=r.sha256()).sha256()
    )


@pytest.mark.parametrize("market", MARKETS)
def test_coverage_change_is_recorded_and_comparison_disabled(market):
    first = frame(market)
    second = later(first, more_strike=True)
    r = replay_x6_history_v1(frames=(first, second))
    assert r.window_transition_count == 1
    assert r.records[1].transition == "WINDOW_CHANGED"
    assert r.records[1].capture_window_sha256 != r.records[0].capture_window_sha256
    assert r.cross_frame_metric_comparison_allowed is False


@pytest.mark.parametrize("market", MARKETS)
def test_expiry_transition_is_recorded_not_mixed(market):
    first = frame(market)
    second = later(first, new_expiry=True, new_session=True, hours=24)
    r = replay_x6_history_v1(frames=(first, second))
    assert r.expiry_transition_count == 1
    assert r.records[1].transition == "EXPIRY_CHANGED"
    assert r.records[1].option_expiry == date(2026, 10, 15)
    assert r.cross_frame_metric_comparison_allowed is False


def test_new_rate_source_is_flagged_as_assumption_change():
    first = frame()
    second = later(first, new_rate_source=True)
    r = replay_x6_history_v1(frames=(first, second))
    assert r.records[1].model_assumption_changed is True
    assert r.records[1].transition == "SAME_WINDOW"


@pytest.mark.parametrize("bad", (None, [], (), ("invalid",)))
def test_invalid_frame_sequences_fail_closed(bad):
    with pytest.raises(ValueError):
        replay_x6_history_v1(frames=bad)


@pytest.mark.parametrize("digest", ("0" * 63, "G" * 64, "0" * 65, 3))
def test_external_final_witness_must_be_canonical(digest):
    with pytest.raises(ValueError):
        replay_x6_history_v1(frames=(frame(),), expected_final_sha256=digest)


def test_external_final_witness_detects_wrong_sequence():
    f = frame()
    with pytest.raises(ValueError, match="EXTERNALLY_RETAINED_FINAL_DIGEST_MISMATCH"):
        replay_x6_history_v1(frames=(f,), expected_final_sha256="f" * 64)


def test_reverse_chronology_fails():
    first = frame()
    second = later(first)
    with pytest.raises(ValueError, match="NONCHRONOLOGICAL_REPLAY"):
        replay_x6_history_v1(frames=(second, first))


def test_duplicate_capture_fails():
    first = frame()
    with pytest.raises(ValueError, match="DUPLICATE_CAPTURE_ID"):
        replay_x6_history_v1(frames=(first, first))


def test_duplicate_x5_capture_id_fails():
    first = frame()
    second = later(first)
    changed_x5 = replace(second.source_x5, capture_id=first.source_x5.capture_id)
    changed_cap = replace(
        second.capture,
        capture_id=changed_x5.capture_id,
        source_x5_capture_sha256=changed_x5.sha256(),
    )
    forged = seal_x6_replay_frame_v1(source_x5=changed_x5, capture=changed_cap)
    with pytest.raises(ValueError, match="DUPLICATE_CAPTURE_ID"):
        replay_x6_history_v1(frames=(first, forged))


def test_same_expiry_contract_id_drift_fails():
    first = frame()
    second = later(first, changed_id=True)
    with pytest.raises(ValueError, match="SAME_EXPIRY_CANONICAL_OPTION_ID_DRIFT"):
        replay_x6_history_v1(frames=(first, second))


def test_inconsistent_same_day_session_fails():
    first = frame()
    second = later(first, new_session=True)
    with pytest.raises(ValueError, match="INCONSISTENT_SAME_DAY_SESSION"):
        replay_x6_history_v1(frames=(first, second))


def test_reused_session_across_days_fails():
    first = frame()
    second = later(first, hours=24)
    with pytest.raises(ValueError, match="REUSED_SESSION_ACROSS_DAYS"):
        replay_x6_history_v1(frames=(first, second))


def test_same_expiry_expiry_instant_drift_fails():
    first = frame()
    second = later(first)
    new_ctx = replace(
        second.capture.context,
        option_expiry_at=(second.capture.context.option_expiry_at - timedelta(minutes=5)),
    )
    new_cap = replace(second.capture, context=new_ctx)
    changed = seal_x6_replay_frame_v1(source_x5=second.source_x5, capture=new_cap)
    with pytest.raises(ValueError, match="SAME_EXPIRY_CONTRACT_OR_EXPIRY_INSTANT_DRIFT"):
        replay_x6_history_v1(frames=(first, changed))


def test_mixed_markets_are_rejected():
    with pytest.raises(ValueError, match="MIXED_MARKETS_IN_REPLAY"):
        replay_x6_history_v1(frames=(frame("NIFTY"), frame("SENSEX")))


def test_reused_x5_row_id_across_frames_fails():
    first = frame()
    second = later(first)
    # Keep the second capture internally valid, but reuse one historical row ID.
    rows5 = tuple(
        replace(r, source_record_id=first.source_x5.observations[0].source_record_id)
        if r.option_type == first.source_x5.observations[0].option_type
        else r
        for r in second.source_x5.observations
    )
    rows6 = tuple(
        replace(r, source_record_id=first.source_x5.observations[0].source_record_id)
        if r.option_type == first.source_x5.observations[0].option_type
        else r
        for r in second.capture.observations
    )
    x5 = replace(second.source_x5, observations=rows5)
    cap = replace(second.capture, observations=rows6, source_x5_capture_sha256=x5.sha256())
    changed = seal_x6_replay_frame_v1(source_x5=x5, capture=cap)
    with pytest.raises(ValueError, match="REUSED_X5_SOURCE_RECORD_ACROSS_CAPTURES"):
        replay_x6_history_v1(frames=(first, changed))


@pytest.mark.parametrize(
    "attr, value",
    (
        ("execution_authority", True),
        ("risk_authority", True),
        ("position_authority", True),
        ("certification_authority", True),
        ("live_execution_eligible", True),
        ("independent_vote", True),
        ("data_only", False),
    ),
)
@pytest.mark.parametrize("kind", ("frame", "record", "result", "b1_inputs"))
def test_zero_authority_is_immutable_on_all_replay_objects(kind, attr, value):
    f = frame(reference=True)
    r = replay_x6_history_v1(frames=(f,))
    obj = {"frame": f, "record": r.records[0], "result": r, "b1_inputs": f.reference_input}[kind]
    with pytest.raises(ValueError, match="authority"):
        replace(obj, **{attr: value})
    with pytest.raises(FrozenInstanceError):
        setattr(obj, attr, value)


def test_replay_record_hash_chain_cannot_be_forged_directly():
    a = replay_x6_history_v1(frames=(frame(),))
    bad = replace(a.records[0], previous_record_sha256="a" * 64)
    with pytest.raises(ValueError, match="Broken replay record hash chain"):
        replace(a, records=(bad,), final_record_sha256=bad.sha256())


def test_replay_result_count_cannot_be_forged():
    r = replay_x6_history_v1(frames=(frame(),))
    with pytest.raises(ValueError, match="counters"):
        replace(r, window_transition_count=4)


def test_frame_b1_reference_witness_required_when_b1_present():
    f = frame(reference=True)
    with pytest.raises(ValueError, match="witness"):
        replace(f, expected_reference_sha256=None)


def test_frame_rejects_reference_without_recompute_inputs():
    f = frame(reference=True)
    with pytest.raises(ValueError, match="together"):
        replace(f, reference_input=None)


@pytest.mark.parametrize(
    "sigma, source, verified",
    (
        (0.3, None, True),
        (None, "src", True),
        (True, "src", True),
        (-0.1, "src", False),
        (5.1, "src", False),
        (float("nan"), "src", False),
    ),
)
def test_invalid_b1_recompute_inputs_fail_closed(sigma, source, verified):
    with pytest.raises(ValueError):
        X6ReplayReferenceInputV1(sigma, source, verified)


def test_no_provider_or_order_imports_in_x6_b4():
    path = Path("services/x6/replay_provenance_v1.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden = (
        "fyers_apiv3",
        "SmartApi",
        "services.execution",
        "services.paper_orchestration",
        "services.trading",
        "subprocess",
        "socket",
        "requests",
    )
    calls = {"place_order", "placeOrder", "submit_order", "execute_trade", "send_order"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not any(x.name.startswith(forbidden) for x in node.names)
        if isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith(forbidden)
        if isinstance(node, ast.Call):
            name = getattr(node.func, "attr", getattr(node.func, "id", ""))
            assert name not in calls


def test_changed_rate_value_with_same_source_is_disclosed():
    first = frame()
    second = later(first)
    ctx = replace(second.capture.context, annual_risk_free_rate=0.075)
    cap = replace(second.capture, context=ctx)
    changed = seal_x6_replay_frame_v1(source_x5=second.source_x5, capture=cap)
    r = replay_x6_history_v1(frames=(first, changed))
    assert r.records[1].model_assumption_changed is True


def test_changed_dividend_value_with_same_source_is_disclosed():
    first = frame()
    second = later(first)
    ctx = replace(second.capture.context, annual_dividend_yield=0.025)
    cap = replace(second.capture, context=ctx)
    changed = seal_x6_replay_frame_v1(source_x5=second.source_x5, capture=cap)
    assert replay_x6_history_v1(frames=(first, changed)).records[1].model_assumption_changed is True


def test_changed_reference_volatility_inputs_are_disclosed():
    first = frame(reference=True)
    second = later(first)
    newer = seal_x6_replay_frame_v1(
        source_x5=second.source_x5,
        capture=second.capture,
        reference_input=X6ReplayReferenceInputV1(0.4, "new-independent-source", True),
    )
    r = replay_x6_history_v1(frames=(first, newer))
    assert r.records[1].model_assumption_changed is True
    assert r.records[1].reference_sha256 is not None


def test_repeated_x6_witness_has_identical_canonical_json():
    f = frame()
    r = replay_x6_history_v1(frames=(f,))
    assert r.to_dict() == replay_x6_history_v1(frames=(f,)).to_dict()
    assert r.sha256() == canonical_sha256(r.to_dict())
    assert r.records[0].sha256() == canonical_sha256(r.records[0].to_dict())


def test_unverified_reference_is_unavailable_not_invented():
    f = frame()
    params = X6ReplayReferenceInputV1(0.25, "not-verified", False)
    ref = seal_x6_replay_frame_v1(source_x5=f.source_x5, capture=f.capture, reference_input=params)
    r = replay_x6_history_v1(frames=(ref,))
    assert r.records[0].reference_status == "UNAVAILABLE"


def test_cannot_claim_contemporaneous_from_retrospective_record():
    f = frame(pit=False)
    r = replay_x6_history_v1(frames=(f,))
    rec = r.records[0]
    with pytest.raises(ValueError, match="Retrospective replay cannot promote"):
        replace(rec, regime_status="AVAILABLE")


def test_noncanonical_witness_format_is_rejected():
    f = frame()
    with pytest.raises(ValueError, match="Canonical SHA-256"):
        replace(f, expected_x5_sha256="F" * 64)


def test_mixed_replay_expiry_with_strike_change_does_not_count_same_window():
    first = frame()
    second = later(first, new_expiry=True, new_session=True, more_strike=True, hours=24)
    r = replay_x6_history_v1(frames=(first, second))
    assert r.expiry_transition_count == 1
    assert r.window_transition_count == 0
    assert r.records[1].transition == "EXPIRY_CHANGED"
