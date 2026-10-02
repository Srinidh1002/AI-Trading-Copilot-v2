"""X5 B3 offline registry and research projection: no SDK, orders or PAPER writes."""

from dataclasses import FrozenInstanceError, asdict, replace
from datetime import timedelta

import pytest
from test_x5_analytics_v1 import pair
from test_x5_chain_contracts_v1 import MARKETS, capture, observation

from services.x5.analytics_v1 import analyze_x5_chain_v1
from services.x5.chain_validation_v1 import METRICS, validate_x5_chain_v1
from services.x5.contracts_v1 import X5ChainCaptureV1, canonical_sha256
from services.x5.feature_manifest_v1 import (
    build_x5_feature_manifest_v1,
)
from services.x5.research_view_v1 import build_x5_research_view_v1


def view(c=None, *, v=None, a=None, manifest=None):
    c = c if c is not None else capture()
    v = v if v is not None else validate_x5_chain_v1(c, max_age_seconds=60)
    a = a if a is not None else analyze_x5_chain_v1(capture=c, max_age_seconds=60)
    return build_x5_research_view_v1(capture=c, validation=v, analytics=a, manifest=manifest)


def feature(v, name):
    return next(x for x in v.features if x.metric_name == name)


@pytest.mark.parametrize("market", tuple(MARKETS))
def test_all_five_markets_project_without_trading_authority(market):
    v = view(capture(market))
    assert v.market == market
    assert v.status == "AVAILABLE"
    assert v.data_only is True and v.independent_vote is False
    assert not any(
        (
            v.execution_authority,
            v.risk_authority,
            v.position_authority,
            v.certification_authority,
            v.live_execution_eligible,
        )
    )
    assert v.option_exchange == (
        "MCX" if market not in {"NIFTY", "SENSEX"} else "NFO" if market == "NIFTY" else "BFO"
    )


@pytest.mark.parametrize("name", METRICS)
def test_manifest_carries_exact_b2_identity_and_unit(name):
    m = build_x5_feature_manifest_v1()
    spec = next(x for x in m.features if x.metric_name == name)
    metric = next(
        x
        for x in analyze_x5_chain_v1(capture=capture(), max_age_seconds=60).metrics
        if x.metric_name == name
    )
    assert spec.unit == metric.unit
    assert spec.dependency_group == metric.dependency_group
    assert spec.independent_vote is False and spec.data_only is True
    assert spec.scope == "CAPTURED_STRIKE_WINDOW"


@pytest.mark.parametrize("name", METRICS)
def test_available_projection_preserves_value_unit_detail_and_strikes(name):
    c = capture()
    a = analyze_x5_chain_v1(capture=c, max_age_seconds=60)
    v = view(c, a=a)
    source = next(x for x in a.metrics if x.metric_name == name)
    projected = feature(v, name)
    assert projected.status == source.status
    assert projected.value == source.value
    assert projected.unit == source.unit
    assert projected.supporting_strikes == source.supporting_strikes
    assert projected.detail == source.detail
    assert projected.source_metric_sha256 == canonical_sha256(asdict(source))


@pytest.mark.parametrize("name", METRICS)
def test_unverified_capture_never_promotes_unavailable_metric(name):
    c = capture(capture_verified=False, point_in_time_verified=False)
    v = view(c)
    x = feature(v, name)
    assert x.status == "UNAVAILABLE" and x.value is None and x.blockers
    assert x.independent_vote is False and x.live_execution_eligible is False
    assert v.status == "UNAVAILABLE"


@pytest.mark.parametrize("name", METRICS)
def test_retroactive_capture_has_no_available_metrics(name):
    c = capture(
        historical_retrieval=True,
        point_in_time_verified=False,
        captured_at=capture().captured_at + timedelta(hours=1),
    )
    v = view(c)
    assert feature(v, name).status == "UNAVAILABLE"
    assert v.historical_retrieval is True and v.point_in_time_verified is False
    assert not v.available_metrics


@pytest.mark.parametrize(
    "field",
    [
        "independent_vote",
        "execution_authority",
        "risk_authority",
        "position_authority",
        "certification_authority",
        "live_execution_eligible",
    ],
)
def test_manifest_feature_cannot_acquire_authority(field):
    x = build_x5_feature_manifest_v1().features[0]
    with pytest.raises(ValueError):
        replace(x, **{field: True})


@pytest.mark.parametrize(
    "field",
    [
        "independent_vote",
        "execution_authority",
        "risk_authority",
        "position_authority",
        "certification_authority",
        "live_execution_eligible",
    ],
)
def test_manifest_cannot_acquire_authority(field):
    with pytest.raises(ValueError):
        replace(build_x5_feature_manifest_v1(), **{field: True})


@pytest.mark.parametrize(
    "field",
    [
        "independent_vote",
        "execution_authority",
        "risk_authority",
        "position_authority",
        "certification_authority",
        "live_execution_eligible",
    ],
)
def test_research_feature_cannot_acquire_authority(field):
    with pytest.raises(ValueError):
        replace(view().features[0], **{field: True})


@pytest.mark.parametrize(
    "field",
    [
        "independent_vote",
        "execution_authority",
        "risk_authority",
        "position_authority",
        "certification_authority",
        "live_execution_eligible",
    ],
)
def test_research_view_cannot_acquire_authority(field):
    with pytest.raises(ValueError):
        replace(view(), **{field: True})


def test_oi_metrics_share_one_group_and_are_not_independent_votes():
    v = view()
    expected = {"PCR_OI", "MAX_PAIN", "OI_CONCENTRATION", "OI_BUILDUP", "OI_SUPPORT_RESISTANCE"}
    assert {
        x.metric_name for x in v.features if x.dependency_group == "OPTION_OI_POSITIONING"
    } == expected
    assert ("OPTION_OI_POSITIONING", 5) in v.group_coverage
    assert all(x.independent_vote is False for x in v.features)
    assert not hasattr(v, "aggregate_bias")
    assert not hasattr(v, "trade_action")
    assert not hasattr(v, "independent_vote_count")


def test_groups_count_available_metrics_but_do_not_count_votes():
    c = capture(observations=tuple(replace(x, iv_verified=False) for x in capture().observations))
    v = view(c)
    assert v.status == "PARTIAL"
    assert ("OPTION_VOLATILITY", 0) in v.group_coverage
    assert feature(v, "IV_SKEW").value is None
    assert v.available_metrics == tuple(x for x in METRICS if x != "IV_SKEW")
    assert v.unavailable_metrics == ("IV_SKEW",)
    assert v.independent_vote is False


def test_zero_denominator_is_not_promoted_by_research_view():
    rows = pair(100)
    c = capture(observations=(replace(rows[0], open_interest=0), rows[1]))
    v = view(c)
    assert feature(v, "PCR_OI").value is None
    assert feature(v, "PCR_OI").blockers == ("ZERO_CALL_DENOMINATOR",)
    assert "ZERO_CALL_DENOMINATOR" in v.blockers


def test_incomplete_ce_pe_pair_has_no_fabricated_values():
    c = capture(observations=(observation("NIFTY", "CE"),))
    v = view(c)
    assert v.status == "UNAVAILABLE" and not v.available_metrics
    assert v.total_strike_count == 1
    assert v.call_only_count == 1 and v.put_only_count == 0
    assert v.complete_pair_count == 0
    assert all(x.value is None for x in v.features)
    assert "INCOMPLETE_CE_PE_PAIRS" in v.warnings


def test_analytics_and_source_provenance_hashes_are_linked():
    c = capture()
    val = validate_x5_chain_v1(c, max_age_seconds=60)
    a = analyze_x5_chain_v1(capture=c, max_age_seconds=60)
    v = view(c, v=val, a=a)
    assert v.source_capture_sha256 == c.sha256()
    assert v.source_validation_sha256 == val.sha256()
    assert v.source_analytics_sha256 == a.sha256()
    assert v.manifest_sha256 == build_x5_feature_manifest_v1().sha256()


def test_replay_is_repeatable_and_observation_order_independent():
    c = capture()
    reverse = replace(c, observations=tuple(reversed(c.observations)))
    assert c.sha256() == reverse.sha256()
    assert view(c).to_dict() == view(reverse).to_dict()
    assert view(c).sha256() == view(reverse).sha256()
    assert view(c).sha256() == view(c).sha256()


def test_mutated_value_changes_feature_and_view_hash():
    c = capture()
    changed = replace(
        c, observations=(replace(c.observations[0], open_interest=200), c.observations[1])
    )
    assert c.sha256() != changed.sha256()
    assert view(c).sha256() != view(changed).sha256()
    assert (
        feature(view(c), "PCR_OI").source_metric_sha256
        != feature(view(changed), "PCR_OI").source_metric_sha256
    )


def test_mixed_market_capture_and_results_rejected():
    with pytest.raises(ValueError, match="identit"):
        view(capture(), v=validate_x5_chain_v1(capture("SENSEX"), max_age_seconds=60))


def test_mixed_capture_hash_is_rejected_even_when_market_and_clock_match():
    c = capture()
    changed = replace(c, underlying_value=c.underlying_value + 1)
    v = validate_x5_chain_v1(changed, max_age_seconds=60)
    a = analyze_x5_chain_v1(capture=changed, max_age_seconds=60)
    with pytest.raises(ValueError, match="hash"):
        view(c, v=v, a=a)


def test_stale_validation_digest_rejected():
    c = capture()
    v = validate_x5_chain_v1(c, max_age_seconds=60)
    changed = replace(v, warnings=v.warnings + ("NEW_WARNING",))
    with pytest.raises(ValueError, match="hash"):
        view(c, v=changed)


def test_validation_readiness_cannot_be_bypassed_by_available_metric():
    c = capture()
    v = validate_x5_chain_v1(c, max_age_seconds=60)
    new_readiness = tuple(
        (n, "UNAVAILABLE" if n == "PCR_OI" else status) for n, status in v.readiness
    )
    limited = replace(v, readiness=new_readiness)
    a = analyze_x5_chain_v1(capture=c, max_age_seconds=60)
    aligned_a = replace(a, source_validation_sha256=limited.sha256())
    with pytest.raises(ValueError, match="promoted"):
        view(c, v=limited, a=aligned_a)


def test_unknown_manifest_rejected():
    c = capture()
    with pytest.raises(ValueError, match="manifest"):
        view(c, manifest="legacy")


def test_explicit_identical_manifest_is_accepted():
    m = build_x5_feature_manifest_v1()
    assert view(manifest=m).sha256() == view().sha256()


def test_manifest_missing_feature_fails_closed():
    m = build_x5_feature_manifest_v1()
    with pytest.raises(ValueError, match="nine canonical"):
        replace(m, features=m.features[:-1])


def test_manifest_reordered_feature_fails_closed():
    m = build_x5_feature_manifest_v1()
    with pytest.raises(ValueError, match="nine canonical"):
        replace(m, features=tuple(reversed(m.features)))


def test_manifest_reclassified_feature_fails_closed():
    m = build_x5_feature_manifest_v1()
    with pytest.raises(ValueError, match="reclassified"):
        replace(m.features[0], dependency_group="OPTION_VOLATILITY")


def test_manifest_feature_is_immutable():
    with pytest.raises(FrozenInstanceError):
        build_x5_feature_manifest_v1().features[0].unit = "CONTRACTS"


def test_research_view_is_immutable():
    with pytest.raises(FrozenInstanceError):
        view().status = "AVAILABLE"


def test_research_feature_no_exchange_wide_claim():
    with pytest.raises(ValueError, match="exchange-wide"):
        replace(view().features[0], scope="EXCHANGE_WIDE")


def test_research_view_no_exchange_wide_claim():
    with pytest.raises(ValueError, match="exchange-wide"):
        replace(view(), scope="EXCHANGE_WIDE")


def test_result_status_cannot_be_manually_promoted():
    c = capture(observations=(observation("NIFTY", "CE"),))
    with pytest.raises(ValueError, match="Status"):
        replace(view(c), status="AVAILABLE")


def test_unavailable_feature_cannot_carry_value():
    c = capture(observations=(observation("NIFTY", "CE"),))
    with pytest.raises(ValueError, match="Unavailable"):
        replace(view(c).features[0], value=1.0)


def test_available_feature_requires_finite_value():
    with pytest.raises(ValueError, match="finite"):
        replace(view().features[0], value=float("nan"))


def test_duplicate_feature_inventory_cannot_replace_canonical_tuple():
    v = view()
    with pytest.raises(ValueError, match="nine canonical"):
        replace(v, features=(v.features[0], v.features[0]) + v.features[2:])


def test_invalid_group_coverage_rejected():
    v = view()
    with pytest.raises(ValueError, match="coverage"):
        replace(v, group_coverage=tuple((g, n + 1) for g, n in v.group_coverage))


def test_mutated_provenance_digest_rejected():
    with pytest.raises(ValueError, match="provenance"):
        replace(view(), manifest_sha256="not-a-hash")


def test_metric_status_cannot_mismatch_list():
    v = view()
    with pytest.raises(ValueError, match="availability"):
        replace(v, available_metrics=())


def test_no_provider_or_trade_methods_exposed():
    v = view()
    for action in (
        "place_order",
        "placeOrder",
        "submit_order",
        "select_contract",
        "rank_trade",
        "broker",
    ):
        assert not hasattr(v, action)
        assert not hasattr(v.features[0], action)


def test_five_market_registry_is_exact():
    assert set(MARKETS) == {"NIFTY", "SENSEX", "CRUDEOILM", "GOLDM", "NATGASMINI"}


def test_capture_immutable_contract_class_is_enforced():
    with pytest.raises(ValueError):
        view(X5ChainCaptureV1)


def test_manifest_schema_is_fixed():
    with pytest.raises(ValueError, match="source"):
        replace(build_x5_feature_manifest_v1(), source_analytics_schema="UNKNOWN")


def test_manifest_sha_is_canonical_and_repeatable():
    assert build_x5_feature_manifest_v1().sha256() == build_x5_feature_manifest_v1().sha256()
    assert len(build_x5_feature_manifest_v1().sha256()) == 64
