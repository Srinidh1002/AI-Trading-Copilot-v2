import pytest
from tests.fixtures.external_context import external_observation,institutional_snapshot,replay_inputs,run_external_context_replay,scheduled_event
@pytest.mark.parametrize("symbol,exchange",(("NIFTY","NSE"),("BANKNIFTY","NSE"),("FINNIFTY","NSE"),("SENSEX","BSE")))
def test_positive_replay_is_deterministic_across_four_markets(symbol,exchange):
 result=run_external_context_replay(symbol=symbol,exchange=exchange,observations=(external_observation(),external_observation("SP500")),snapshot=institutional_snapshot(),events=());assert result.semantic_dict()==run_external_context_replay(symbol=symbol,exchange=exchange,observations=(external_observation(),external_observation("SP500")),snapshot=institutional_snapshot(),events=()).semantic_dict()
def test_all_absent_evidence_is_unavailable_not_neutral():assert run_external_context_replay().context_status=="UNAVAILABLE"
def test_rbi_event_precedence_blocks_entries():
 r=run_external_context_replay(observations=(external_observation(),),snapshot=institutional_snapshot(),events=(scheduled_event(),));assert r.context_status=="BLOCKED" and not r.new_entries_allowed
