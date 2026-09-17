from __future__ import annotations
import json
from dataclasses import dataclass,field
from typing import Any,Mapping
@dataclass(frozen=True,slots=True)
class IntegratedThreeTargetTradePlanResultV1:
 integration_id:str;status:str;canonical_trade_plan_input:Any;entry_zone_result:Any;stop_loss_result:Any;three_target_result:Any;option_contract_selection_result:Any;capital_quantity_result:Any;blockers:tuple[str,...]=();warnings:tuple[str,...]=();decision_reasons:tuple[str,...]=();metadata:Mapping[str,Any]=field(default_factory=dict);execution_mode:str='PAPER';live_execution_eligible:bool=False;schema_version:str='1.0'
 def __post_init__(self):
  if self.status not in {'READY','BLOCKED','NO_SIZE'} or self.execution_mode!='PAPER' or self.live_execution_eligible is not False:raise ValueError('status/paper')
  if self.status=='READY' and self.blockers:raise ValueError('READY')
  if self.status=='BLOCKED' and not self.blockers:raise ValueError('BLOCKED')
  if self.status=='NO_SIZE' and (self.blockers or not self.decision_reasons):raise ValueError('NO_SIZE')
 def to_dict(self):return {'integration_id':self.integration_id,'status':self.status,'entry_zone_result':self.entry_zone_result.to_dict(),'stop_loss_result':self.stop_loss_result.to_dict(),'three_target_result':self.three_target_result.to_dict(),'option_contract_selection_result':self.option_contract_selection_result.to_dict(),'capital_quantity_result':self.capital_quantity_result.to_dict(),'blockers':list(self.blockers),'warnings':list(self.warnings),'decision_reasons':list(self.decision_reasons),'metadata':dict(self.metadata),'execution_mode':self.execution_mode,'live_execution_eligible':self.live_execution_eligible,'schema_version':self.schema_version}
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(',',':'))
