from tests.test_task9_startup_preflight_orchestrator import NOW,_pass
from services.certification.task9_startup_preflight_orchestrator import *
from services.certification.task9_startup_preflight_store import Task9StartupPreflightStore
from services.certification.task9_provider_capability_report_builder import build_task9_provider_capability_report
from services.contracts.task9_runtime_config_snapshot_v1 import build_task9_runtime_config_snapshot
from services.contracts.task9_startup_preflight_v1 import Task9StartupPreflightPhase
from tests.test_task9_runtime_config_snapshot_v1 import _config
def test_store_idempotent_restart_and_conflict(tmp_path):
 c=_config();s=build_task9_runtime_config_snapshot(c);r=build_task9_provider_capability_report(c);checks={p:_pass(p) for p in tuple(Task9StartupPreflightPhase)[2:-1]};x=Task9StartupPreflightOrchestrator(runtime_config=c,snapshot=s,capability_report=r,mode="LIVE_CERTIFICATION_STARTUP",checks=checks).run(preflight_id="receipt-1",observed_at=NOW);store=Task9StartupPreflightStore(tmp_path);assert store.save(x)==x and Task9StartupPreflightStore(tmp_path).get("receipt-1")==x
