from services.analysis.live_canonical_engine_adapters import build_default_live_canonical_evidence_engines


def test_default_bundle_binds_concrete_repository_callables():
 bundle = build_default_live_canonical_evidence_engines()
 assert bundle.data_quality.__name__ == "_data_quality"
 assert bundle.multi_timeframe.__name__ == "_multi_timeframe"
 assert bundle.technical.__name__ == "_technical"
 assert bundle.regime.__name__ == "_regime"
 assert bundle.option_chain.__name__ == "_option_chain"
 assert bundle.contract_ranking.__name__ == "_contract_ranking"
