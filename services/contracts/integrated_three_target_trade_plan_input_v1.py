from __future__ import annotations
from dataclasses import dataclass
from services.contracts.canonical_trade_plan_input_v1 import CanonicalTradePlanInputV1
from services.contracts.entry_zone_evaluation_result_v1 import EntryZoneEvaluationResultV1
from services.contracts.stop_loss_evaluation_result_v1 import StopLossEvaluationResultV1
from services.contracts.three_target_evaluation_result_v1 import ThreeTargetEvaluationResultV1
from services.contracts.option_contract_selection_result_v1 import OptionContractSelectionResultV1
from services.contracts.capital_quantity_planning_result_v1 import CapitalQuantityPlanningResultV1
@dataclass(frozen=True,slots=True)
class IntegratedThreeTargetTradePlanInputV1:
 integration_id:str;canonical_trade_plan_input:CanonicalTradePlanInputV1;entry_zone_result:EntryZoneEvaluationResultV1;stop_loss_result:StopLossEvaluationResultV1;three_target_result:ThreeTargetEvaluationResultV1;option_contract_selection_result:OptionContractSelectionResultV1;capital_quantity_result:CapitalQuantityPlanningResultV1
 def __post_init__(self):
  if type(self.integration_id)is not str or not self.integration_id.strip():raise ValueError('integration_id')
  ts=(CanonicalTradePlanInputV1,EntryZoneEvaluationResultV1,StopLossEvaluationResultV1,ThreeTargetEvaluationResultV1,OptionContractSelectionResultV1,CapitalQuantityPlanningResultV1)
  vs=(self.canonical_trade_plan_input,self.entry_zone_result,self.stop_loss_result,self.three_target_result,self.option_contract_selection_result,self.capital_quantity_result)
  if any(type(v)is not t for v,t in zip(vs,ts)):raise TypeError('typed inputs')
  i=(self.canonical_trade_plan_input.underlying_symbol,self.canonical_trade_plan_input.exchange,self.canonical_trade_plan_input.direction)
  if any((v.underlying_symbol,v.exchange,v.direction)!=i for v in vs[1:5]):raise ValueError('identity')
