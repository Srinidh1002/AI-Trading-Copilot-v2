from __future__ import annotations

import json

import pytest

from services.brain.analyzer_registry_v1 import (
    AnalyzerDescriptorV1,
    AnalyzerRegistryV1,
    DEFAULT_ANALYZER_REGISTRY_V1,
    SUPPORTED_MARKETS,
)


EXPECTED_ANALYZER_IDS = {
    "index.previous_session.legacy_v1",
    "index.gap.legacy_v1",
    "index.global_risk.legacy_v1",
    "index.india_vix.legacy_v1",
    "index.institutional_flow.legacy_v1",
    "index.news.legacy_v1",
    "index.event_calendar.legacy_v1",
    "index.breadth.legacy_v1",
    "index.mtf.legacy_v1",
    "index.regime.legacy_v1",
    "index.option_chain.legacy_v1",

    "mcx.mtf.native_v1",
    "mcx.regime.native_v1",
    "mcx.structure.native_v1",
    "mcx.price_oi.native_v1",
    "mcx.pcr.native_v1",
    "mcx.event_risk.native_v1",

    "canonical.technical_intelligence.v1",
}


def make_descriptor(
    **overrides,
):
    values = {
        "analyzer_id":
            "test.analyzer.v1",

        "analyzer_version":
            "1.0",

        "category":
            "TECHNICAL",

        "markets":
            (
                "NIFTY",
            ),

        "source_family":
            "INDEX_LEGACY",

        "runtime_role":
            "PRODUCTION_INPUT",

        "currently_consumed_by_production":
            True,
    }

    values.update(
        overrides
    )

    return AnalyzerDescriptorV1(
        **values
    )


def test_default_registry_contains_exact_b1_analyzers():
    actual = {
        item.analyzer_id
        for item
        in DEFAULT_ANALYZER_REGISTRY_V1.descriptors
    }

    assert actual == EXPECTED_ANALYZER_IDS


def test_default_registry_has_expected_descriptor_count():
    assert len(
        DEFAULT_ANALYZER_REGISTRY_V1.descriptors
    ) == 18


def test_every_supported_market_has_registered_analyzers():
    for market in SUPPORTED_MARKETS:
        assert DEFAULT_ANALYZER_REGISTRY_V1.for_market(
            market
        )


def test_current_production_routes_are_described_correctly():
    index_mtf = DEFAULT_ANALYZER_REGISTRY_V1.get(
        "index.mtf.legacy_v1"
    )

    mcx_mtf = DEFAULT_ANALYZER_REGISTRY_V1.get(
        "mcx.mtf.native_v1"
    )

    canonical = DEFAULT_ANALYZER_REGISTRY_V1.get(
        "canonical.technical_intelligence.v1"
    )

    assert index_mtf.currently_consumed_by_production is True
    assert index_mtf.runtime_role == "PRODUCTION_INPUT"

    assert mcx_mtf.currently_consumed_by_production is True
    assert mcx_mtf.runtime_role == "PRODUCTION_INPUT"

    assert canonical.currently_consumed_by_production is False
    assert canonical.runtime_role == "SHADOW_AVAILABLE"


def test_every_descriptor_has_zero_authority():
    for item in DEFAULT_ANALYZER_REGISTRY_V1.descriptors:
        assert item.execution_authority is False
        assert item.risk_authority is False
        assert item.position_authority is False
        assert item.certification_authority is False


def test_shadow_analyzer_cannot_claim_current_production_consumption():
    with pytest.raises(
        ValueError,
        match="SHADOW_AVAILABLE",
    ):
        make_descriptor(
            runtime_role="SHADOW_AVAILABLE",
            currently_consumed_by_production=True,
        )


def test_execution_authority_can_never_be_enabled():
    with pytest.raises(
        ValueError,
        match="permanently False",
    ):
        make_descriptor(
            execution_authority=True
        )


def test_risk_authority_can_never_be_enabled():
    with pytest.raises(
        ValueError,
        match="permanently False",
    ):
        make_descriptor(
            risk_authority=True
        )


def test_position_authority_can_never_be_enabled():
    with pytest.raises(
        ValueError,
        match="permanently False",
    ):
        make_descriptor(
            position_authority=True
        )


def test_certification_authority_can_never_be_enabled():
    with pytest.raises(
        ValueError,
        match="permanently False",
    ):
        make_descriptor(
            certification_authority=True
        )


def test_invalid_market_is_rejected():
    with pytest.raises(
        ValueError,
        match="unsupported markets",
    ):
        make_descriptor(
            markets=(
                "BANKNIFTY",
            )
        )


def test_duplicate_analyzer_id_is_rejected():
    descriptor = make_descriptor()

    with pytest.raises(
        ValueError,
        match="duplicate analyzer_id",
    ):
        AnalyzerRegistryV1(
            descriptors=(
                descriptor,
                descriptor,
            )
        )


def test_registry_market_filter_is_deterministic():
    nifty = DEFAULT_ANALYZER_REGISTRY_V1.for_market(
        "NIFTY"
    )

    assert nifty
    assert all(
        "NIFTY" in item.markets
        for item in nifty
    )


def test_registry_category_filter_is_deterministic():
    technical = DEFAULT_ANALYZER_REGISTRY_V1.by_category(
        "TECHNICAL"
    )

    assert {
        item.analyzer_id
        for item in technical
    } == {
        "index.mtf.legacy_v1",
        "mcx.mtf.native_v1",
        "canonical.technical_intelligence.v1",
    }


def test_production_inputs_exclude_shadow_canonical_engine():
    values = DEFAULT_ANALYZER_REGISTRY_V1.production_inputs(
        "NIFTY"
    )

    ids = {
        item.analyzer_id
        for item in values
    }

    assert "index.mtf.legacy_v1" in ids

    assert (
        "canonical.technical_intelligence.v1"
        not in ids
    )


def test_shadow_available_contains_canonical_engine():
    values = DEFAULT_ANALYZER_REGISTRY_V1.shadow_available(
        "NIFTY"
    )

    assert [
        item.analyzer_id
        for item in values
    ] == [
        "canonical.technical_intelligence.v1"
    ]


def test_registry_serializes_to_json():
    payload = DEFAULT_ANALYZER_REGISTRY_V1.to_dict()

    encoded = json.dumps(
        payload,
        sort_keys=True,
    )

    assert "BRAIN_ANALYZER_REGISTRY_V1" in encoded
    assert "canonical.technical_intelligence.v1" in encoded


def test_registry_contains_no_callable_analyzer_objects():
    for descriptor in DEFAULT_ANALYZER_REGISTRY_V1.descriptors:
        assert not callable(
            descriptor
        )

        assert not hasattr(
            descriptor,
            "run"
        )

        assert not hasattr(
            descriptor,
            "execute"
        )


def test_event_registry_entries_do_not_receive_authority():
    index_event = DEFAULT_ANALYZER_REGISTRY_V1.get(
        "index.event_calendar.legacy_v1"
    )

    mcx_event = DEFAULT_ANALYZER_REGISTRY_V1.get(
        "mcx.event_risk.native_v1"
    )

    for item in (
        index_event,
        mcx_event,
    ):
        assert item.execution_authority is False
        assert item.risk_authority is False
        assert item.position_authority is False
        assert item.certification_authority is False


def test_b1_known_event_limit_is_documented():
    descriptor = DEFAULT_ANALYZER_REGISTRY_V1.get(
        "index.event_calendar.legacy_v1"
    )

    text = " ".join(
        descriptor.notes
    )

    assert "UNVERIFIED" in text


def test_b1_known_pcr_normalization_need_is_documented():
    descriptor = DEFAULT_ANALYZER_REGISTRY_V1.get(
        "index.option_chain.legacy_v1"
    )

    text = " ".join(
        descriptor.notes
    )

    assert "normalized" in text.lower()


def test_canonical_technical_math_verification_is_documented():
    descriptor = DEFAULT_ANALYZER_REGISTRY_V1.get(
        "canonical.technical_intelligence.v1"
    )

    text = " ".join(
        descriptor.notes
    )

    assert "independently verified" in text
    assert "not production-authoritative" in text