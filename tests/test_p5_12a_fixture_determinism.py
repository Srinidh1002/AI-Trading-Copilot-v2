from tests.fixtures.p5_12 import *
def test_fixture_ids_timestamps_and_serialization_are_deterministic():
 identity=CANONICAL_MARKET_IDENTITIES[0]; first=build_technical_intelligence(identity,STRONG_BULLISH); second=build_technical_intelligence(identity,STRONG_BULLISH)
 assert first.to_dict()==second.to_dict() and first.created_at==REPLAY_EVALUATED_AT
 timestamps=build_source_timestamps();assert timestamps==build_source_timestamps()
 profile=build_freshness_timestamp_profile('MIXED');assert profile==build_freshness_timestamp_profile('MIXED')
 classified=classify_fixture_freshness_profile(profile);assert classified==classify_fixture_freshness_profile(profile)
 assert classified.freshness_state in {'FRESH','STALE','FUTURE','MIXED','UNAVAILABLE'}
 assert tuple(profile)==('broader_market','external_context','market_regime','option_chain','technical','trade_opportunity')
 assert tuple(to_candidate_source_timestamps(profile))==('BROADER_MARKET','EXTERNAL_CONTEXT','MARKET_REGIME','OPTION_CHAIN','TECHNICAL','TRADE_OPPORTUNITY')
 try:profile['technical']=REPLAY_EVALUATED_AT
 except TypeError:pass
 else:raise AssertionError('timestamp profile must be immutable')
 scenarios={market:STRONG_BULLISH for market in CANONICAL_MARKET_IDENTITIES}; candidates=build_four_market_candidate_set(scenarios)
 assert candidates==build_four_market_candidate_set(scenarios)
