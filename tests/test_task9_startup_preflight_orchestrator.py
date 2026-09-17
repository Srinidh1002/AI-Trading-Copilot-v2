from datetime import datetime,timezone
from services.certification.task9_startup_preflight_orchestrator import *
from services.certification.task9_provider_capability_report_builder import build_task9_provider_capability_report
from services.contracts.task9_runtime_config_snapshot_v1 import build_task9_runtime_config_snapshot
from services.contracts.task9_startup_preflight_v1 import *
from tests.test_task9_runtime_config_snapshot_v1 import _config
NOW=datetime(2026,8,15,tzinfo=timezone.utc)
def _pass(phase):return lambda:Task9StartupPreflightPhaseResultV1(phase,Task9StartupPreflightPhaseStatus.PASS,False,"INJECTED_PASS",None,NOW)
def test_exact_order_fully_injected_live_approves_and_offline_does_not():
 c=_config();s=build_task9_runtime_config_snapshot(c);r=build_task9_provider_capability_report(c);checks={p:_pass(p) for p in tuple(Task9StartupPreflightPhase)[2:-1]}
 live=Task9StartupPreflightOrchestrator(runtime_config=c,snapshot=s,capability_report=r,mode="LIVE_CERTIFICATION_STARTUP",checks=checks).run(preflight_id="p1",observed_at=NOW)
 assert tuple(x.phase for x in live.phase_results)==tuple(Task9StartupPreflightPhase) and live.launch_approved
 offline=Task9StartupPreflightOrchestrator(runtime_config=c,snapshot=s,capability_report=r,mode="OFFLINE_BUILD_VALIDATION",checks=checks).run(preflight_id="p2",observed_at=NOW);assert not offline.launch_approved
def test_blocker_stops_later_checks():
 c=_config();s=build_task9_runtime_config_snapshot(c);r=build_task9_provider_capability_report(c);called=[]
 def fail():return Task9StartupPreflightPhaseResultV1(Task9StartupPreflightPhase.CAMPAIGN_RUN_ROOT_IDENTITY,Task9StartupPreflightPhaseStatus.FAIL_FATAL,True,"CAMPAIGN_RUN_MISMATCH",None,NOW)
 def later():called.append(1);return _pass(Task9StartupPreflightPhase.PERSISTENCE_INTEGRITY_WRITABILITY)()
 x=Task9StartupPreflightOrchestrator(runtime_config=c,snapshot=s,capability_report=r,mode="LIVE_CERTIFICATION_STARTUP",checks={Task9StartupPreflightPhase.CAMPAIGN_RUN_ROOT_IDENTITY:fail,Task9StartupPreflightPhase.PERSISTENCE_INTEGRITY_WRITABILITY:later}).run(preflight_id="p3",observed_at=NOW)
 assert x.blocking_phase is Task9StartupPreflightPhase.CAMPAIGN_RUN_ROOT_IDENTITY and not called and all(y.status is Task9StartupPreflightPhaseStatus.NOT_RUN for y in x.phase_results[3:])
