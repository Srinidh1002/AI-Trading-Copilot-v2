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


def test_task91043_snapshot_uses_evidence_contracts_but_universe_stays_strict():
    strict_call = row(
        token="STRICT_CE",
        symbol="NIFTY14JUL202624200CE",
        strike=24200,
        option_type="CE",
        premium=100.0,
        bid=99.5,
        ask=100.5,
        open_interest=1000,
        volume=100,
    )

    evidence_call = dict(strict_call)

    evidence_put = row(
        token="EVIDENCE_PE",
        symbol="NIFTY14JUL202624200PE",
        strike=24200,
        option_type="PE",
        premium=0.0,
        bid=0.0,
        ask=0.05,
        open_interest=800,
        volume=0,
    )

    result = normalize_angel_option_chain(
        contracts=(strict_call,),
        snapshot_contracts=(
            evidence_call,
            evidence_put,
        ),
        market_spec=NIFTY_MARKET_SPEC,
        spot_price=24206,
        provider_timestamp=NOW,
        evaluated_at=NOW,
    )

    assert len(result.universe.contracts) == 1
    assert result.universe.contracts[0].instrument_token == "STRICT_CE"

    assert result.snapshot.complete_pair_count == 1
    assert result.snapshot.call_only_count == 0
    assert result.snapshot.put_only_count == 0
