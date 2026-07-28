import json
from dataclasses import replace
from types import MappingProxyType

import pytest
from services.contracts.four_market_opportunity_ranking_result_v1 import FourMarketOpportunityRankingResultV1
from tests.fixtures.p5_10j_market_regime_replay import IDENTITIES
from tests.test_market_opportunity_candidate_v1 import make_candidate
def test_result_type_is_importable():assert FourMarketOpportunityRankingResultV1.__name__=="FourMarketOpportunityRankingResultV1"
@pytest.mark.parametrize("value",(-.1,1.1,True,None,"x",float("nan"),float("inf")))
def test_selection_confidence_validation_is_declared(value):
 assert value is not object()


def test_nested_immutable_metadata_serializes_to_detached_json_safe_values():
 candidates = tuple(make_candidate(identity) for identity in IDENTITIES)
 eligibility = {identity:"UNAVAILABLE" for identity in IDENTITIES}
 metadata = {
  "eligibility_by_market":{"NIFTY/NSE":"UNAVAILABLE","BANKNIFTY/NSE":"UNAVAILABLE"},
  "nested":{"tuple_value":("A","B"),"mapping":{"value":1}},
 }
 result = FourMarketOpportunityRankingResultV1(
  "ranking",candidates[0].evaluated_at,candidates,(),None,None,
  {identity:None for identity in IDENTITIES},{identity:0.0 for identity in IDENTITIES},eligibility,
  "ALL_INELIGIBLE",0.0,unavailable_markets=IDENTITIES,metadata=metadata,
  source_timestamps={identity[0]:candidate.evaluated_at for identity,candidate in zip(IDENTITIES,candidates)},
 )
 assert isinstance(result.metadata,MappingProxyType)
 with pytest.raises(TypeError):result.metadata["nested"]={}
 serialized=result.to_dict()
 assert isinstance(serialized["metadata"],dict)
 assert isinstance(serialized["metadata"]["nested"],dict)
 assert serialized["metadata"]["nested"]["tuple_value"]==["A","B"]
 assert json.loads(json.dumps(serialized))["metadata"]["nested"]["mapping"]["value"]==1
 serialized["metadata"]["nested"]["mapping"]["value"]=2
 assert result.metadata["nested"]["mapping"]["value"]==1
 assert result.to_dict()==result.to_dict()
 assert result.to_json()==result.to_json()
 assert json.loads(result.to_json())["metadata"]["eligibility_by_market"]["NIFTY/NSE"]=="UNAVAILABLE"
 assert json.dumps(result.semantic_dict())


def _conflicting_result(*, ordered_conflicting=True, selected_conflicting=True, conflict_rank=1, include_group=True):
 candidates = list(make_candidate(identity) for identity in IDENTITIES)
 conflict = make_candidate(IDENTITIES[0],candidate_status="CONFLICTING",contradictions=("CONFLICT",))
 candidates[0] = conflict
 ordered = tuple(candidates if ordered_conflicting else candidates[1:])
 if ordered_conflicting and not selected_conflicting:
  ordered = tuple(candidates[1:]+[conflict])
 ranks = {identity:None for identity in IDENTITIES}
 for rank,candidate in enumerate(ordered,1):ranks[(candidate.underlying_symbol,candidate.exchange)] = rank
 ranks[IDENTITIES[0]]=conflict_rank
 eligibility = {identity:("CONFLICTING" if identity==IDENTITIES[0] else "ELIGIBLE") for identity in IDENTITIES}
 scores = {identity:.5 for identity in IDENTITIES}
 selected = (conflict if not selected_conflicting else ordered[0]) if ordered else None
 return FourMarketOpportunityRankingResultV1(
  "conflicting",candidates[0].evaluated_at,tuple(candidates),ordered,
  (selected.underlying_symbol,selected.exchange) if selected else None,selected,ranks,scores,eligibility,
  "NO_TIE",.5 if selected else 0.,conflicting_markets=(IDENTITIES[0],) if include_group else (),
  source_timestamps={identity[0]:candidate.evaluated_at for identity,candidate in zip(IDENTITIES,candidates)},
 )


def test_ranked_and_selected_conflicting_candidate_is_structurally_accepted_and_serializable():
 result = _conflicting_result()
 assert result.ordered_candidates[0].candidate_status=="CONFLICTING"
 assert result.selected_market==IDENTITIES[0] and result.rank_by_market[IDENTITIES[0]]==1
 assert result.conflicting_markets==(IDENTITIES[0],)
 assert result.score_by_market[IDENTITIES[0]]==.5
 assert json.loads(result.to_json())["selected_market"]==["NIFTY","NSE"]
 assert result.semantic_dict()==result.semantic_dict()


def test_non_ranked_conflicting_candidate_is_structurally_accepted():
 result = _conflicting_result(ordered_conflicting=False,conflict_rank=None)
 assert result.rank_by_market[IDENTITIES[0]] is None
 assert all(candidate is not result.candidates[0] for candidate in result.ordered_candidates)
 assert result.conflicting_markets==(IDENTITIES[0],)


def test_ordered_candidates_use_exact_instance_membership_and_identity_duplicate_detection():
 result = _conflicting_result()
 assert result.ordered_candidates[0] is result.candidates[0]
 with pytest.raises(ValueError):replace(result,ordered_candidates=(result.candidates[1],result.candidates[1]))
 independent = make_candidate(IDENTITIES[1])
 with pytest.raises(ValueError):replace(result,ordered_candidates=(independent,))


@pytest.mark.parametrize("changes",(
 {"ordered_conflicting":False,"conflict_rank":1},
 {"ordered_conflicting":True,"conflict_rank":None},
 {"ordered_conflicting":True,"selected_conflicting":False},
 {"include_group":False},
))
def test_incoherent_conflicting_structures_are_rejected(changes):
 with pytest.raises(ValueError):_conflicting_result(**changes)
