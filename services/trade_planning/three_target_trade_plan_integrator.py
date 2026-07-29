from services.contracts.integrated_three_target_trade_plan_input_v1 import IntegratedThreeTargetTradePlanInputV1
from services.contracts.integrated_three_target_trade_plan_result_v1 import IntegratedThreeTargetTradePlanResultV1
def integrate_three_target_trade_plan(integration_input):
 if type(integration_input)is not IntegratedThreeTargetTradePlanInputV1:raise TypeError('integration_input')
 values=(integration_input.entry_zone_result,integration_input.stop_loss_result,integration_input.three_target_result,integration_input.option_contract_selection_result,integration_input.capital_quantity_result)
 blockers=tuple(v.status for v in values[:-1] if v.status!='READY')
 if blockers:return IntegratedThreeTargetTradePlanResultV1(integration_input.integration_id,'BLOCKED',integration_input.canonical_trade_plan_input,*values,blockers=blockers,metadata={'integration_stage':'ASSEMBLY'})
 if integration_input.capital_quantity_result.status=='NO_SIZE':return IntegratedThreeTargetTradePlanResultV1(integration_input.integration_id,'NO_SIZE',integration_input.canonical_trade_plan_input,*values,decision_reasons=integration_input.capital_quantity_result.decision_reasons,metadata={'integration_stage':'ASSEMBLY'})
 return IntegratedThreeTargetTradePlanResultV1(integration_input.integration_id,'READY',integration_input.canonical_trade_plan_input,*values,metadata={'integration_stage':'ASSEMBLY'})
