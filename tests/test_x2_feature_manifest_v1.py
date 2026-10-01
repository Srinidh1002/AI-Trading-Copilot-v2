from __future__ import annotations

import pytest

from services.x2.feature_manifest_v1 import (
    DEFAULT_X2_FEATURE_MANIFEST_V1,
    FAMILIES_V1,
    NOT_APPLICABLE_MARKETS_V1,
    SOURCE_FAMILIES_V1,
    SUPPORTED_MARKETS_V1,
    X2_FEATURE_MANIFEST_SCHEMA_V1,
    X2FeatureDescriptorV1,
    X2FeatureManifestError,
    X2FeatureManifestV1,
)


def descriptor(**overrides):
    defaults = dict(
        feature_id="x2.test.v1",
        feature_version="1.0",
        family="CONSTITUENT_INFLUENCE",
        subject="INDEX",
        markets=("NIFTY",),
        source_families=("X2_CONSTITUENT_RETURNS",),
        dependency_ids=(),
        output_contract="TestResultV1",
    )
    defaults.update(overrides)
    return X2FeatureDescriptorV1(**defaults)


def test_default_manifest_shape():
    m = DEFAULT_X2_FEATURE_MANIFEST_V1
    assert m.schema_version == X2_FEATURE_MANIFEST_SCHEMA_V1
    ids = [d.feature_id for d in m.descriptors]
    assert len(ids) == len(set(ids))
    assert "x2.constituent_influence.v1" in ids
    assert "x2.weighted_breadth.v1" in ids
    assert "x2.heatmap.v1" in ids
    assert "x2.sector_strength.v1" in ids
    assert "x2.relative_strength.v1" in ids


def test_default_manifest_covers_all_families():
    m = DEFAULT_X2_FEATURE_MANIFEST_V1
    for family in FAMILIES_V1:
        assert m.by_family(family), family


def test_default_manifest_only_supports_nifty_sensex():
    for d in DEFAULT_X2_FEATURE_MANIFEST_V1.descriptors:
        for mkt in d.markets:
            assert mkt in SUPPORTED_MARKETS_V1
            assert mkt not in NOT_APPLICABLE_MARKETS_V1


def test_dependency_groups_expose_shared_sources():
    m = DEFAULT_X2_FEATURE_MANIFEST_V1
    groups = m.dependency_groups()
    key = "|".join(
        sorted(("X2_CONSTITUENT_RETURNS", "X2_CONSTITUENT_WEIGHTS"))
    )
    assert key in groups
    members = groups[key]
    assert "x2.constituent_influence.v1" in members
    assert "x2.weighted_breadth.v1" in members
    assert "x2.heatmap.v1" in members


def test_descriptor_rejects_bad_family():
    with pytest.raises(X2FeatureManifestError):
        descriptor(family="NOT_A_FAMILY")


def test_descriptor_rejects_unsupported_market():
    with pytest.raises(X2FeatureManifestError):
        descriptor(markets=("CRUDEOILM",))


def test_descriptor_rejects_unsupported_source_family():
    with pytest.raises(X2FeatureManifestError):
        descriptor(source_families=("NOT_A_SOURCE",))


def test_descriptor_rejects_authority_overrides():
    with pytest.raises(X2FeatureManifestError):
        descriptor(execution_authority=True)
    with pytest.raises(X2FeatureManifestError):
        descriptor(risk_authority=True)
    with pytest.raises(X2FeatureManifestError):
        descriptor(position_authority=True)
    with pytest.raises(X2FeatureManifestError):
        descriptor(certification_authority=True)


def test_descriptor_rejects_authority_provider_overrides():
    with pytest.raises(X2FeatureManifestError):
        descriptor(order_capability_allowed=True)
    with pytest.raises(X2FeatureManifestError):
        descriptor(automatic_fallback_allowed=True)
    with pytest.raises(X2FeatureManifestError):
        descriptor(data_only=False)


def test_manifest_rejects_duplicate_ids():
    d = descriptor(feature_id="dup")
    with pytest.raises(X2FeatureManifestError):
        X2FeatureManifestV1(descriptors=(d, d))


def test_manifest_canonical_json_is_stable():
    m = DEFAULT_X2_FEATURE_MANIFEST_V1
    first = m.canonical_json()
    second = m.canonical_json()
    assert first == second
    assert m.manifest_sha256 == m.manifest_sha256


def test_manifest_serialisation_contains_only_data_only_flags():
    payload = DEFAULT_X2_FEATURE_MANIFEST_V1.to_dict()
    for d in payload["descriptors"]:
        assert d["execution_authority"] is False
        assert d["risk_authority"] is False
        assert d["position_authority"] is False
        assert d["certification_authority"] is False
        assert d["data_only"] is True
        assert d["order_capability_allowed"] is False
        assert d["automatic_fallback_allowed"] is False


def test_manifest_does_not_register_in_v1_registry():
    # Sanity check: importing the manifest must not alter the frozen
    # V1 analyzer registry.
    from services.brain.analyzer_registry_v1 import (
        DEFAULT_ANALYZER_REGISTRY_V1,
    )

    ids = {d.analyzer_id for d in DEFAULT_ANALYZER_REGISTRY_V1.descriptors}
    for d in DEFAULT_X2_FEATURE_MANIFEST_V1.descriptors:
        assert d.feature_id not in ids


def test_source_families_set_matches_expected():
    assert SOURCE_FAMILIES_V1 == frozenset(
        {
            "X2_CONSTITUENT_RETURNS",
            "X2_CONSTITUENT_WEIGHTS",
            "X2_SECTOR_MAPPING",
            "X2_INDEX_RETURNS",
        }
    )
