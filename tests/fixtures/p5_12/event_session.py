from dataclasses import dataclass
from datetime import timedelta
from types import MappingProxyType

from services.contracts.event_risk_context_result_v1 import EventRiskContextResultV1
from services.contracts.market_session_validation_v1 import MarketSessionValidationV1
from services.contracts.scheduled_market_event_v1 import ScheduledMarketEventV1

from .identities import normalize_test_identity
from .timebase import REPLAY_EVALUATED_AT


@dataclass(frozen=True)
class EventReplayProfileV1:
    profile_name:str; events:tuple[tuple[str,str,str,bool],...]=(); warnings:tuple[str,...]=(); blockers:tuple[str,...]=()
    @property
    def blocking(self): return bool(self.blockers)


NONE=EventReplayProfileV1('NONE')
RBI_BLOCK=EventReplayProfileV1('RBI_BLOCK',(('RBI_POLICY','RBI Policy','EXTREME',True),),blockers=('P512_RBI_BLOCK',))
UNION_BUDGET=EventReplayProfileV1('UNION_BUDGET',(('UNION_BUDGET','Union Budget','HIGH',False),),warnings=('P512_UNION_BUDGET',))
CPI_WARNING=EventReplayProfileV1('CPI_WARNING',(('CPI','CPI Release','MODERATE',False),),warnings=('P512_CPI_WARNING',))
ELECTION_EVENT=EventReplayProfileV1('ELECTION_EVENT',(('ELECTION','Election Event','HIGH',False),),warnings=('P512_ELECTION_EVENT',))
WEEKLY_EXPIRY=EventReplayProfileV1('WEEKLY_EXPIRY',(('WEEKLY_EXPIRY','Weekly Expiry','MODERATE',False),),warnings=('P512_WEEKLY_EXPIRY',))
MONTHLY_EXPIRY=EventReplayProfileV1('MONTHLY_EXPIRY',(('MONTHLY_EXPIRY','Monthly Expiry','MODERATE',False),),warnings=('P512_MONTHLY_EXPIRY',))
ROLLOVER=EventReplayProfileV1('ROLLOVER',(('ROLLOVER','Rollover','LOW',False),),warnings=('P512_ROLLOVER',))
OVERLAPPING_EVENTS=EventReplayProfileV1('OVERLAPPING_EVENTS',(('RBI_POLICY','RBI Policy','EXTREME',True),('CPI','CPI Release','MODERATE',False)),warnings=('P512_CPI_WARNING',),blockers=('P512_RBI_BLOCK',))


@dataclass(frozen=True)
class SessionReplayProfileV1:
    profile_name:str; session_state:str; session_phase:str; trading_day_status:str; analysis_allowed:bool; paper_execution_allowed:bool; reasons:tuple[str,...]=(); special:bool=False


REGULAR_SESSION=SessionReplayProfileV1('REGULAR_SESSION','REGULAR','REGULAR_TRADING','TRADING_DAY',True,True)
HOLIDAY=SessionReplayProfileV1('HOLIDAY','HOLIDAY','CLOSED_ALL_DAY','HOLIDAY',False,False,('P512_HOLIDAY',))
CLOSED_SESSION=SessionReplayProfileV1('CLOSED_SESSION','CLOSED','CLOSED_ALL_DAY','UNKNOWN',False,False,('P512_CLOSED_SESSION',))
SPECIAL_SESSION=SessionReplayProfileV1('SPECIAL_SESSION','SPECIAL','SPECIAL_TRADING','SPECIAL_TRADING_DAY',True,True,('P512_SPECIAL_SESSION',),True)
WEEKLY_EXPIRY_SESSION=SessionReplayProfileV1('WEEKLY_EXPIRY_SESSION','REGULAR','REGULAR_TRADING','TRADING_DAY',True,True,('P512_WEEKLY_EXPIRY_SESSION',))
MONTHLY_EXPIRY_SESSION=SessionReplayProfileV1('MONTHLY_EXPIRY_SESSION','REGULAR','REGULAR_TRADING','TRADING_DAY',True,True,('P512_MONTHLY_EXPIRY_SESSION',))
RBI_BLOCK_EVENT_PROFILE=RBI_BLOCK
UNION_BUDGET_EVENT_PROFILE=UNION_BUDGET
CPI_WARNING_EVENT_PROFILE=CPI_WARNING
ELECTION_EVENT_PROFILE=ELECTION_EVENT
WEEKLY_EXPIRY_EVENT_PROFILE=WEEKLY_EXPIRY
MONTHLY_EXPIRY_EVENT_PROFILE=MONTHLY_EXPIRY
ROLLOVER_EVENT_PROFILE=ROLLOVER
OVERLAPPING_EVENTS_PROFILE=OVERLAPPING_EVENTS
HOLIDAY_SESSION=HOLIDAY
SPECIAL_SESSION_PROFILE=SPECIAL_SESSION


def build_market_session_validation(identity,*,session_profile=REGULAR_SESSION,evaluated_at=REPLAY_EVALUATED_AT):
    symbol,exchange=normalize_test_identity(*identity)
    profile=session_profile
    return MarketSessionValidationV1(
        f'p512-session-{profile.profile_name}-{symbol}',evaluated_at,evaluated_at,symbol,exchange,'UTC',evaluated_at.date(),
        profile.session_state,profile.session_phase,profile.trading_day_status,is_trading_day=profile.trading_day_status in {'TRADING_DAY','SPECIAL_TRADING_DAY'},
        regular_session_open=profile.session_state=='REGULAR',analysis_allowed=profile.analysis_allowed,paper_execution_allowed=profile.paper_execution_allowed,
        holiday_name='P512_HOLIDAY' if profile is HOLIDAY else None,special_session=profile.special,special_session_name='P512_SPECIAL_SESSION' if profile.special else None,
        blockers=profile.reasons if not profile.paper_execution_allowed else (),warnings=profile.reasons if profile.paper_execution_allowed and profile.reasons else (),
    )


def build_event_risk_context(identity,*,event_profile=NONE,event_profiles=None,evaluated_at=REPLAY_EVALUATED_AT):
    symbol,exchange=normalize_test_identity(*identity); profiles=tuple(event_profiles or (event_profile,)); records=[]; warnings=[]; blockers=[]
    for profile in profiles:
        warnings.extend(profile.warnings);blockers.extend(profile.blockers)
        for index,(category,name,severity,blocking) in enumerate(profile.events):
            event_id=f'p512-event-{profile.profile_name}-{index}-{symbol}'
            records.append(ScheduledMarketEventV1(event_id,evaluated_at,name,category,evaluated_at,evaluated_at+timedelta(minutes=30),'P512',evaluated_at,'CONFIRMED','BLOCKED' if blocking else 'UPCOMING',severity,((symbol,exchange),),(exchange,),True,not blocking,'NONE',blockers=(f'P512_{category}_BLOCK',) if blocking else (),warnings=profile.warnings if not blocking else ()))
    records=tuple(sorted(records,key=lambda item:item.scheduled_market_event_id));active=tuple(item.scheduled_market_event_id for item in records if item.event_status=='BLOCKED');upcoming=tuple(item.scheduled_market_event_id for item in records if item.event_status=='UPCOMING');blocking=tuple(item.scheduled_market_event_id for item in records if item.event_status=='BLOCKED')
    status='BLOCKED' if blockers else 'READY_WITH_WARNINGS' if warnings else 'READY';risk='EXTREME' if blockers else max((item.severity for item in records),default='NONE',key=lambda value:('NONE','LOW','MODERATE','HIGH','EXTREME').index(value));restriction='BLOCKED' if blockers else 'WARNING' if warnings else 'OPEN'
    return EventRiskContextResultV1(f'p512-event-risk-{symbol}',evaluated_at,symbol,exchange,records,status,risk,restriction,True,not bool(blockers),len(active),len(upcoming),0,len(blocking),len(upcoming),risk,active,upcoming,(),blocking,warnings=tuple(sorted(set(warnings))),blockers=tuple(sorted(set(blockers))),source_timestamps=MappingProxyType({'EVENTS':evaluated_at}))
