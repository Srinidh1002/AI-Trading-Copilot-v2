from datetime import datetime,time
from zoneinfo import ZoneInfo
from uuid import uuid4
from services.contracts.market_session_validation_v1 import MarketSessionValidationV1
from .calendar import EmptyTradingCalendar
from .identity import normalize_market_identity
from .policies import NSE_NIFTY_POLICY, BSE_SENSEX_POLICY
from services.observability import AuditEmitter,AuditContext,create_audit_event
IST=ZoneInfo("Asia/Kolkata")
def validate_session_timestamp(*,symbol,exchange,market_timestamp,evaluated_at,calendar=None,policy=None,validation_mode="LENIENT_ANALYSIS",id_factory=None,audit_emitter=None,audit_context=None):
    emitter=audit_emitter or AuditEmitter(); emitter.emit(create_audit_event("SESSION_VALIDATION_STARTED",component="market_session",operation="validate",outcome="STARTED",context=audit_context,symbol=str(symbol),exchange=str(exchange)))
    cal=calendar or EmptyTradingCalendar(); blockers=[]; warnings=[]; identity=normalize_market_identity(symbol,exchange)
    if not isinstance(market_timestamp,datetime) or not isinstance(evaluated_at,datetime) or market_timestamp.tzinfo is None or evaluated_at.tzinfo is None: raise ValueError("Session timestamps must be timezone-aware datetimes.")
    market_timestamp=market_timestamp.astimezone(IST); evaluated_at=evaluated_at.astimezone(IST); policy=policy or (NSE_NIFTY_POLICY if exchange.upper()=="NSE" else BSE_SENSEX_POLICY); age=(evaluated_at-market_timestamp).total_seconds(); stale=age>policy.max_snapshot_age_seconds; future=age < -policy.max_future_skew_seconds
    day=market_timestamp.date(); holiday=cal.holiday_for(exchange.upper(),day); special=cal.special_session_for(exchange.upper(),day)
    state,phase,status="CLOSED","CLOSED_ALL_DAY","TRADING_DAY"; allowed=False
    if not identity: blockers.append("Unsupported symbol/exchange identity."); status="UNKNOWN"; state="UNKNOWN"; phase="UNKNOWN"
    elif day.weekday()>4: blockers.append("Weekend market closure."); status="WEEKEND"; state="WEEKEND"
    elif holiday and holiday.full_day and not special: blockers.append("Exchange holiday: "+holiday.name); status="HOLIDAY"; state="HOLIDAY"
    elif special:
        status="SPECIAL_TRADING_DAY"; state="SPECIAL"; phase="SPECIAL_TRADING"; allowed=special.analysis_allowed
        if not allowed: blockers.append("Special session does not allow analysis.")
    else:
        if getattr(cal,"source","EMPTY")=="EMPTY": warnings.append("No exchange holiday calendar was supplied.")
        value=market_timestamp.timetz().replace(tzinfo=None)
        if policy.regular_open<=value<=policy.regular_close: state,phase,allowed="REGULAR","REGULAR_TRADING",True
        elif policy.pre_open_start<=value<policy.regular_open: state="PRE_OPEN"; phase="PRE_OPEN_ORDER_ENTRY" if value<policy.pre_open_order_entry_end else "PRE_OPEN_MATCHING" if value<policy.pre_open_matching_end else "PRE_OPEN_BUFFER"; blockers.append("Market is not in regular trading session.")
        elif value>policy.regular_close: state,phase="POST_CLOSE","AFTER_MARKET"; blockers.append("Market is closed for actionable trading.")
        else: blockers.append("Market is closed before pre-open.")
    if stale: blockers.append("Market timestamp is stale.")
    if future: blockers.append("Market timestamp exceeds allowed future skew.")
    if validation_mode=="STRICT_EXECUTION" and not getattr(cal,"trusted",False): blockers.append("Trusted exchange holiday calendar is required for execution.")
    allowed=allowed and not stale and not future and not blockers
    result=MarketSessionValidationV1(validation_id=(id_factory or (lambda:str(uuid4())))(),evaluated_at=evaluated_at,market_timestamp=market_timestamp,symbol=identity.canonical_symbol if identity else str(symbol),exchange=exchange.upper(),timezone="Asia/Kolkata",trading_date=day,session_state=state,session_phase=phase,trading_day_status=status,is_trading_day=status in {"TRADING_DAY","SPECIAL_TRADING_DAY"},regular_session_open=state=="REGULAR",analysis_allowed=allowed,paper_preparation_allowed=allowed,paper_execution_allowed=allowed and (validation_mode!="STRICT_EXECUTION" or getattr(cal,"trusted",False)),timestamp_age_seconds=age,stale=stale,future_timestamp=future,holiday_name=holiday.name if holiday else None,special_session=bool(special),special_session_name=special.name if special else None,blockers=tuple(sorted(blockers)),warnings=tuple(sorted(warnings)),metadata={"calendar_source":getattr(cal,"source","CUSTOM"),"validation_mode":validation_mode})
    emitter.emit(create_audit_event("SESSION_VALIDATION_COMPLETED" if result.analysis_allowed else "SESSION_VALIDATION_BLOCKED",component="market_session",operation="validate",outcome="SUCCEEDED" if result.analysis_allowed else "BLOCKED",context=audit_context,snapshot_id=None,symbol=result.symbol,exchange=result.exchange,attributes={"session_state":result.session_state,"session_phase":result.session_phase,"trading_day_status":result.trading_day_status,"stale":result.stale,"future_timestamp":result.future_timestamp,"validation_mode":validation_mode,"calendar_source":result.metadata["calendar_source"],"blocker_count":len(result.blockers)})); return result
def validate_market_session(snapshot,*,evaluated_at=None,calendar=None,policy=None,validation_mode="LENIENT_ANALYSIS",id_factory=None,clock=None,**kwargs):
    now=evaluated_at or (clock() if clock else snapshot.captured_at); return validate_session_timestamp(symbol=snapshot.symbol,exchange=snapshot.exchange,market_timestamp=snapshot.market_timestamp,evaluated_at=now,calendar=calendar,policy=policy,validation_mode=validation_mode,id_factory=id_factory,audit_emitter=kwargs.get("audit_emitter"),audit_context=kwargs.get("audit_context"))
