from datetime import datetime
from uuid import uuid4
from .policies import OptionSelectionPolicy
from services.contracts.selected_option_contract_v1 import SelectedOptionContractV1
def select_option_contract(decision,universe,*,now,policy=None,snapshot_id=None,requested_expiry=None,requested_strike=None,id_factory=None):
    policy=policy or OptionSelectionPolicy(); blockers=[]; required="CALL" if decision.action=="BUY" else "PUT" if decision.action=="SELL" else None
    if not required or decision.authorization_status=="BLOCKED": blockers.append("Decision is not actionable.")
    if universe is None: blockers.append("Option contract universe is required.")
    elif universe.underlying_symbol!=decision.symbol or universe.exchange!=decision.exchange: blockers.append("Universe identity does not match decision.")
    elif policy.require_trusted_universe and not universe.trusted: blockers.append("Trusted option universe is required.")
    elif (now-universe.captured_at).total_seconds()>policy.max_universe_age_seconds or (universe.captured_at-now).total_seconds()>policy.max_future_skew_seconds: blockers.append("Option universe timestamp is invalid.")
    contracts=[] if blockers or not universe else [c for c in universe.contracts if c.option_type==required and c.tradable and c.expiry_date>=now.date() and (now-c.market_timestamp).total_seconds()<=policy.max_contract_age_seconds]
    if requested_expiry is not None: contracts=[c for c in contracts if c.expiry_date==requested_expiry]
    elif contracts: contracts=[c for c in contracts if c.expiry_date==min(x.expiry_date for x in contracts)]
    if requested_strike is not None: contracts=[c for c in contracts if c.strike==requested_strike]
    elif contracts: contracts=sorted(contracts,key=lambda c:(abs(c.strike-universe.spot_price),c.strike if required=="CALL" else -c.strike,c.contract_id))[:1]
    if not contracts: blockers.append("No eligible option contract.")
    c=contracts[0] if contracts else None; price,source=_price(c,policy.reference_price_policy) if c else (None,"UNAVAILABLE")
    warnings=("Option universe is untrusted.",) if universe and not universe.trusted and not policy.require_trusted_universe else ()
    return SelectedOptionContractV1((id_factory or (lambda:str(uuid4())))(),now,snapshot_id or decision.snapshot_id,decision.decision_id,universe.universe_id if c else None,c.contract_id if c else None,decision.symbol,decision.exchange,decision.action,required,c.trading_symbol if c else None,c.instrument_token if c else None,c.expiry_date if c else None,c.strike if c else None,c.lot_size if c else None,universe.spot_price if c else None,price,source,policy.expiry_policy,policy.strike_policy,not blockers,tuple(sorted(set(blockers)),),warnings)
def _price(c,p):
    bid,ask,last=c.bid_price,c.ask_price,c.last_price
    if p in {"MID","BEST_AVAILABLE"} and bid is not None and ask is not None:return ((bid+ask)/2,"MID")
    if p in {"ASK","BEST_AVAILABLE"} and ask is not None:return (ask,"ASK")
    if p in {"LAST","BEST_AVAILABLE"} and last is not None:return (last,"LAST")
    return (bid,"BID") if bid is not None else (None,"UNAVAILABLE")
