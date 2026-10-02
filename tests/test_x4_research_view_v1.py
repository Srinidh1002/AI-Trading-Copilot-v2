"""Offline X4 B3 manifest, projection, provenance and zero-authority gates."""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from services.x4.contracts_v1 import (
    X4BasisReferenceV1,
    X4ContractV1,
    X4SampleV1,
)
from services.x4.feature_manifest_v1 import (
    X4_FEATURE_IDS_V1,
    X4_FEATURE_MANIFEST_V1,
    X4FeatureSpecV1,
    get_x4_feature_spec_v1,
    x4_manifest_sha256_v1,
)
from services.x4.fyers_adapter_v1 import X4AdaptedCandlesV1
from services.x4.multi_timeframe_v1 import compose_x4_multi_timeframe_v1
from services.x4.research_view_v1 import (
    build_x4_research_view_v1,
)

NOW = datetime(2026, 10, 1, 10, 20, tzinfo=UTC)
PRICE_UNITS = {
    "NIFTY": "INDEX_POINTS",
    "SENSEX": "INDEX_POINTS",
    "CRUDEOILM": "INR_PER_BARREL",
    "GOLDM": "INR_PER_10G",
    "NATGASMINI": "INR_PER_MMBTU",
}


def contract(market="NIFTY"):
    return X4ContractV1(
        market=market,
        canonical_instrument_id=f"FYERS:{market}:20261030:FUT",
        provider="FYERS",
        provider_symbol=f"FYERS:{market}:FUT",
        expiry=date(2026, 10, 30),
        price_unit=PRICE_UNITS[market],
        metadata_status="VERIFIED",
        metadata_source="TEST_VERIFIED_MASTER",
    )


def capture(c, tf, *, oi_verified=True, volume_verified=True, now=NOW):
    capture_id = f"CAPTURE:{c.market}:{tf}"
    samples = tuple(
        X4SampleV1(
            contract_id=c.canonical_instrument_id,
            session_id="2026-10-01:S1",
            timeframe=tf,
            observed_at=now - timedelta(minutes=10 - 5 * i),
            source_id=f"{capture_id}:{i}",
            close=100.0 + i,
            high=101.0 + i,
            low=99.0 + i,
            volume=10.0 * (i + 1),
            open_interest=1000.0 + i * 10,
            volume_verified=volume_verified,
            oi_verified=oi_verified,
            is_closed=True,
            quality="VALID",
        )
        for i in range(3)
    )
    return X4AdaptedCandlesV1(c, samples, NOW, capture_id)


def composed(
    market="NIFTY",
    *,
    include=("5m", "15m"),
    oi_verified=True,
    volume_verified=True,
    basis=None,
    stale_frame=None,
):
    c = contract(market)
    captures = {
        tf: capture(
            c,
            tf,
            oi_verified=oi_verified,
            volume_verified=volume_verified,
            now=NOW - timedelta(minutes=10) if tf == stale_frame else NOW,
        )
        for tf in include
    }
    return compose_x4_multi_timeframe_v1(
        contract=c,
        captures=captures,
        required_timeframes=("5m", "15m"),
        max_age_seconds_by_timeframe={"5m": 300, "15m": 1200},
        as_of=NOW,
        basis_reference=basis,
    )


@pytest.mark.parametrize("market", tuple(PRICE_UNITS))
def test_five_market_projection_remains_research_only(market):
    source = composed(market)
    result = build_x4_research_view_v1(source)
    assert (result.market, result.instrument_id, result.provider_symbol) == (
        source.market,
        source.instrument_id,
        source.provider_symbol,
    )
    assert result.source_result_sha256 == source.sha256()
    assert result.manifest_sha256 == x4_manifest_sha256_v1()
    assert result.alignment == "CONSISTENT_UP"
    assert len(result.features) == 16
    assert result.required_timeframes == ("5m", "15m")
    assert result.data_only and not result.independent_vote
    assert not result.live_execution_eligible
    assert all(not f.independent_vote and f.data_only for f in result.features)


@pytest.mark.parametrize("feature_id", X4_FEATURE_IDS_V1)
def test_manifest_maps_existing_engine_features_exactly(feature_id):
    spec = get_x4_feature_spec_v1(feature_id)
    view = build_x4_research_view_v1(composed())
    matches = [f for f in view.features if f.feature_id == feature_id]
    assert len(matches) == 2
    assert all(
        f.family == spec.family and f.dependency_group == spec.dependency_group for f in matches
    )
    assert spec.independent_vote is False
    assert spec.interpretation == "DESCRIPTIVE_RESEARCH_ONLY"


@pytest.mark.parametrize("value", ("", "FUTURES_UNKNOWN", "FUTURES_PRICE_CHANGE", None, 123))
def test_manifest_unknown_feature_fail_closed(value):
    with pytest.raises(ValueError):
        get_x4_feature_spec_v1(value)


def test_manifest_is_eight_unique_metrics_and_deterministic():
    assert len(X4_FEATURE_MANIFEST_V1) == len(set(X4_FEATURE_IDS_V1)) == 8
    assert X4_FEATURE_IDS_V1 == tuple(s.feature_id for s in X4_FEATURE_MANIFEST_V1)
    assert x4_manifest_sha256_v1() == x4_manifest_sha256_v1()
    assert len(x4_manifest_sha256_v1()) == 64


def test_reused_measurements_share_dependency_groups():
    manifest = {s.feature_id: s for s in X4_FEATURE_MANIFEST_V1}
    assert {
        manifest[f].dependency_group
        for f in (
            "FUTURES_PRICE_CHANGE_PCT",
            "FUTURES_OI_DELTA",
            "FUTURES_OI_CHANGE_PCT",
            "FUTURES_OI_ACCELERATION",
        )
    } == {"PRICE_OI"}
    assert {
        manifest[f].dependency_group
        for f in (
            "FUTURES_VOLUME_CHANGE_PCT",
            "FUTURES_CANDLE_VWAP_ESTIMATE",
            "FUTURES_VWAP_ESTIMATE_DISTANCE_PCT",
        )
    } == {"VOLUME_DERIVED"}
    assert manifest["FUTURES_BASIS"].dependency_group == "BASIS_REFERENCE"
    assert not any(s.independent_vote for s in X4_FEATURE_MANIFEST_V1)


def test_canonical_order_and_repeatable_replay_hash():
    first = composed()
    second = composed(include=("15m", "5m"))
    assert first.sha256() == second.sha256()
    one = build_x4_research_view_v1(first)
    two = build_x4_research_view_v1(second)
    assert one.to_dict() == two.to_dict()
    assert one.sha256() == two.sha256()
    assert tuple((f.timeframe, f.feature_id) for f in one.features) == tuple(
        (tf, feature) for tf in ("5m", "15m") for feature in X4_FEATURE_IDS_V1
    )
    assert one.dependency_groups == ("PRICE_OI", "VOLUME_DERIVED", "BASIS_REFERENCE")


def test_every_feature_has_capture_and_contract_provenance():
    result = build_x4_research_view_v1(composed())
    for f in result.features:
        assert f.dependency_ids[:3] == (result.instrument_id, result.session_id, f.timeframe)
        assert any(id.startswith(f.capture_id + ":") for id in f.dependency_ids[3:])
        assert f.capture_id == f"CAPTURE:NIFTY:{f.timeframe}"
        assert f.as_of == NOW


def test_basis_without_reference_is_absent_not_zero():
    result = build_x4_research_view_v1(composed())
    basis = [f for f in result.features if f.feature_id == "FUTURES_BASIS"]
    assert all(f.status == "UNAVAILABLE" and f.value is None for f in basis)
    assert all("BENCHMARK_UNAVAILABLE" in f.blockers for f in basis)


def test_verified_same_unit_basis_passes_through_descriptively():
    ref = X4BasisReferenceV1(
        market="NIFTY",
        benchmark_type="INDEX_SPOT",
        price=101,
        price_unit="INDEX_POINTS",
        source_id="TEST_SPOT_PROOF",
        observed_at=NOW,
        verified=True,
    )
    result = build_x4_research_view_v1(composed(basis=ref))
    assert result.status == "AVAILABLE"
    assert all(
        f.value == 1.0 and f.status == "AVAILABLE" and not f.independent_vote
        for f in result.features
        if f.feature_id == "FUTURES_BASIS"
    )


def test_missing_timeframe_remains_missing():
    source = composed(include=("5m",))
    view = build_x4_research_view_v1(source)
    assert view.missing_timeframes == ("15m",)
    assert view.alignment == "INSUFFICIENT_DATA"
    assert len(view.features) == 8
    assert all(f.timeframe == "5m" for f in view.features)
    assert "MISSING_TIMEFRAME:15m" in view.blockers


def test_all_missing_returns_empty_view_without_fabrication():
    view = build_x4_research_view_v1(composed(include=()))
    assert view.status == "UNAVAILABLE"
    assert view.alignment == "INSUFFICIENT_DATA"
    assert view.features == ()
    assert view.dependency_groups == ()
    assert view.missing_timeframes == ("5m", "15m")


def test_unverified_oi_cannot_be_promoted_to_directional_evidence():
    view = build_x4_research_view_v1(composed(oi_verified=False))
    assert view.alignment == "INSUFFICIENT_DATA"
    for f in view.features:
        if f.feature_id in {"FUTURES_OI_DELTA", "FUTURES_OI_CHANGE_PCT", "FUTURES_OI_ACCELERATION"}:
            assert f.status == "UNAVAILABLE" and f.value is None
            assert f.metric_direction == "UNKNOWN"


def test_unverified_volume_cannot_create_session_vwap():
    view = build_x4_research_view_v1(composed(volume_verified=False))
    for f in view.features:
        if f.dependency_group == "VOLUME_DERIVED":
            assert f.status == "UNAVAILABLE" and f.value is None


def test_stale_timeframe_cannot_emit_available_features():
    view = build_x4_research_view_v1(composed(stale_frame="5m"))
    assert view.alignment == "INSUFFICIENT_DATA"
    assert all(f.timeframe != "5m" for f in view.features)
    assert "5m:STALE_FUTURES_SAMPLE" in view.blockers


@pytest.mark.parametrize(
    "field",
    (
        "execution_authority",
        "risk_authority",
        "position_authority",
        "certification_authority",
        "live_execution_eligible",
        "independent_vote",
    ),
)
def test_view_authority_cannot_be_enabled(field):
    view = build_x4_research_view_v1(composed())
    with pytest.raises(ValueError):
        replace(view, **{field: True})
    with pytest.raises(ValueError):
        replace(view.features[0], **{field: True})
    with pytest.raises(FrozenInstanceError):
        view.status = "AVAILABLE"


@pytest.mark.parametrize(
    "field",
    (
        "execution_authority",
        "risk_authority",
        "position_authority",
        "certification_authority",
        "live_execution_eligible",
        "independent_vote",
    ),
)
def test_manifest_cannot_gain_authority(field):
    with pytest.raises(ValueError):
        replace(X4_FEATURE_MANIFEST_V1[0], **{field: True})
    with pytest.raises(ValueError):
        replace(
            X4FeatureSpecV1("FUTURES_EXTRA", "FUTURES_POSITIONING", "PRICE_OI", "PERCENT", 1),
            **{field: True},
        )


def test_unknown_injected_feature_fails_closed():
    source = composed()
    frame = source.timeframe_results[0]
    injection = replace(frame.features[0], feature_id="FUTURES_EXTRA")
    fake = replace(frame, features=(injection, *frame.features[1:]))
    corrupted = replace(source, timeframe_results=(fake, *source.timeframe_results[1:]))
    with pytest.raises(ValueError):
        build_x4_research_view_v1(corrupted)


def test_unexpected_fixed_unit_rejected():
    source = composed()
    frame = source.timeframe_results[0]
    bad = replace(frame.features[0], unit="RUPEES")
    fake = replace(frame, features=(bad, *frame.features[1:]))
    corrupted = replace(source, timeframe_results=(fake, *source.timeframe_results[1:]))
    with pytest.raises(ValueError):
        build_x4_research_view_v1(corrupted)


@pytest.mark.parametrize(
    "mutation",
    (
        lambda frame: replace(frame, market="SENSEX"),
        lambda frame: replace(frame, instrument_id="OTHER_CONTRACT"),
        lambda frame: replace(frame, session_id="OTHER_SESSION"),
        lambda frame: replace(frame, as_of=NOW + timedelta(minutes=1)),
    ),
)
def test_frame_identity_contamination_rejected(mutation):
    source = composed()
    corrupted = replace(
        source,
        timeframe_results=(mutation(source.timeframe_results[0]), source.timeframe_results[1]),
    )
    with pytest.raises(ValueError):
        build_x4_research_view_v1(corrupted)


def test_capture_id_mismatch_rejected():
    source = composed()
    bad_evidence = replace(source.evidence[0], capture_id="OTHER_CAPTURE")
    corrupted = replace(source, evidence=(bad_evidence, source.evidence[1]))
    with pytest.raises(ValueError):
        build_x4_research_view_v1(corrupted)


def test_feature_dependency_mismatch_rejected():
    source = composed()
    frame = source.timeframe_results[0]
    bad = replace(
        frame.features[0], dependency_ids=("OTHER", *frame.features[0].dependency_ids[1:])
    )
    fake = replace(frame, features=(bad, *frame.features[1:]))
    corrupted = replace(source, timeframe_results=(fake, source.timeframe_results[1]))
    with pytest.raises(ValueError):
        build_x4_research_view_v1(corrupted)


def test_duplicate_dependency_rejected():
    source = composed()
    frame = source.timeframe_results[0]
    previous = frame.features[0].dependency_ids
    bad = replace(frame.features[0], dependency_ids=(*previous, previous[-1]))
    fake = replace(frame, features=(bad, *frame.features[1:]))
    corrupted = replace(source, timeframe_results=(fake, source.timeframe_results[1]))
    with pytest.raises(ValueError):
        build_x4_research_view_v1(corrupted)


def test_available_feature_removed_from_manifest_population_rejected():
    source = composed()
    frame = source.timeframe_results[0]
    fake = replace(frame, features=frame.features[:-1])
    corrupted = replace(source, timeframe_results=(fake, source.timeframe_results[1]))
    with pytest.raises(ValueError):
        build_x4_research_view_v1(corrupted)


def test_view_hash_is_sensitive_to_captured_evidence():
    source = composed()
    original = build_x4_research_view_v1(source)
    change = replace(source.evidence[0], capture_id="CAPTURE:NIFTY:5m:REVISED")
    changed = replace(source, evidence=(change, source.evidence[1]))
    # The revision must be accompanied by a re-derived upstream capture;
    # changing just the presentation provenance must fail closed.
    with pytest.raises(ValueError):
        build_x4_research_view_v1(changed)
    assert original.sha256() == build_x4_research_view_v1(composed()).sha256()


def test_unsupported_input_rejected():
    with pytest.raises(TypeError):
        build_x4_research_view_v1({"market": "NIFTY"})


def test_no_order_sdk_network_or_paper_imports():
    sources = [
        Path("services/x4/feature_manifest_v1.py").read_text(encoding="utf-8"),
        Path("services/x4/research_view_v1.py").read_text(encoding="utf-8"),
    ]
    for source in sources:
        for prohibited in (
            "place_order(",
            "submit_order(",
            "certification_counter(",
            "fyers_apiv3",
            "requests.",
            "services.paper_orchestration",
        ):
            assert prohibited not in source
    view = build_x4_research_view_v1(composed())
    assert not hasattr(view, "trade_action")
    assert not hasattr(view, "risk_limit")
    assert not hasattr(view, "certification_counter")
