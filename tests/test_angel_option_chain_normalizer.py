from datetime import datetime, timezone
import pytest
from services.options.angel_option_chain_normalizer import normalize_angel_option_chain
from services.paper_orchestration.certified_live_provider_readers import NIFTY_MARKET_SPEC, SENSEX_MARKET_SPEC
NOW=datetime(2026,8,3,tzinfo=timezone.utc)
def row(kind="CE", **changes):
 v={"token":"1"+kind,"symbol":"NIFTY26AUG25000"+kind,"option_type":kind,"expiry":"2026-08-27","strike":25000,"lotsize":25,"tick_size":0.05,"premium":100,"bid":99,"ask":101,"volume":5,"open_interest":10};v.update(changes);return v
@pytest.mark.parametrize("spec",(NIFTY_MARKET_SPEC,SENSEX_MARKET_SPEC))
def test_normalizes_exact_market(spec):
 r=row();r["symbol"]=spec.underlying_symbol+"26AUG25000CE"; out=normalize_angel_option_chain(contracts=(r,),market_spec=spec,spot_price=25000,provider_timestamp=NOW,evaluated_at=NOW);assert (out.snapshot.underlying_symbol,out.snapshot.exchange)==(spec.underlying_symbol,spec.exchange) and out.universe.contracts[0].metadata["derivative_segment"]==spec.option_exchange
def test_missing_chain_is_blocked():assert "OPTION_CHAIN_UNAVAILABLE" in normalize_angel_option_chain(contracts=(),market_spec=NIFTY_MARKET_SPEC,spot_price=1,provider_timestamp=NOW,evaluated_at=NOW).blockers
@pytest.mark.parametrize("changes",({"lotsize":0},{"tick_size":0},{"ask":98},{"option_type":"XX"},{"expiry":"2020-01-01"}))
def test_invalid_metadata_rejected(changes):
 with pytest.raises(ValueError):normalize_angel_option_chain(contracts=(row(**changes),),market_spec=NIFTY_MARKET_SPEC,spot_price=1,provider_timestamp=NOW,evaluated_at=NOW)
def test_greeks_and_depth_are_not_fabricated():
 out=normalize_angel_option_chain(contracts=(row(bid=None,ask=None),),market_spec=NIFTY_MARKET_SPEC,spot_price=1,provider_timestamp=NOW,evaluated_at=NOW);c=out.universe.contracts[0];assert c.bid_price is None and c.ask_price is None and "delta" not in c.metadata
