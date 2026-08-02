from services.analysis.live_canonical_engine_adapters import build_default_live_canonical_evidence_engines
def test_bundle_requires_named_engine_callables():
 try: build_default_live_canonical_evidence_engines()
 except TypeError: pass
 else: raise AssertionError("engine callables are required")
