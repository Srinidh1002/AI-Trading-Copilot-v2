from services.analysis.live_canonical_engine_adapters import build_default_live_canonical_evidence_engines


def test_default_canonical_bundle_is_provider_free():
    bundle = build_default_live_canonical_evidence_engines()
    assert not hasattr(bundle, "place_order")
    assert not hasattr(bundle, "submit_order")
