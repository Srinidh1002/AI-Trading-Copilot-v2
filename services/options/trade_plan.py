from datetime import datetime,timedelta
from uuid import uuid4
from services.contracts.trade_plan_v1 import TradePlanV1
from services.contracts.selected_option_contract_v1 import SelectedOptionContractV1
from .policies import TradePlanPolicy

def build_trade_plan(*,snapshot_id,analysis_id,decision_id,action,selected_contract,policy=None,session_close_at=None,contract_expiry_at=None,entry_reference_price=None,entry_price_source=None,stop_loss_price=None,stop_loss_source=None,target_price=None,target_source=None,clock=None,id_factory=None):
    policy=policy or TradePlanPolicy(); now=(clock() if clock else selected_contract.selected_at); blockers=[]
    if not isinstance(selected_contract,SelectedOptionContractV1) or not selected_contract.selection_valid: blockers.append("Selected contract is invalid.")
    if action not in {"BUY","SELL"} or (action=="BUY" and selected_contract.option_type!="CALL") or (action=="SELL" and selected_contract.option_type!="PUT"): blockers.append("Action and option type do not match.")
    entry=entry_reference_price if entry_reference_price is not None else selected_contract.reference_option_price
    if policy.require_entry_reference_price and entry is None: blockers.append("Entry reference is required.")
    if policy.require_stop_loss and stop_loss_price is None: blockers.append("Stop loss is required.")
    if policy.require_target and target_price is None: blockers.append("Target is required.")
    until=now+timedelta(seconds=policy.validity_seconds)
    for cap in (contract_expiry_at,session_close_at):
        if cap is not None:
            if cap.tzinfo is None: raise ValueError("Validity caps must be timezone-aware.")
            until=min(until,cap)
    if until<=now: blockers.append("Trade plan is expired.")
    status="EXPIRED" if until<=now else "INSUFFICIENT_DATA" if blockers else "READY_FOR_RISK"
    usable=not blockers
    return TradePlanV1((id_factory or (lambda:str(uuid4())))(),now,snapshot_id,analysis_id,decision_id,selected_contract.selection_id if usable else None,selected_contract.contract_id if usable else None,selected_contract.underlying_symbol,selected_contract.exchange,action,selected_contract.option_type if usable else None,selected_contract.trading_symbol if usable else None,selected_contract.expiry_date if usable else None,selected_contract.strike if usable else None,selected_contract.lot_size if usable else None,entry,entry_price_source,stop_loss_price,target_price,stop_loss_source,target_source,now,until,status,usable,"trade_plan.v1",None,None,None,None,False,tuple(sorted(set(blockers))))
