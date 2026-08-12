from datetime import datetime, timedelta, timezone

import pytest

from services.certification.task9_external_provider_blocker import Task9ExternalProviderBlockerStore
from services.certification.task9_live_paper_certification_launcher import Task9ExternalProviderBlockedError, Task9LivePaperCertificationLauncher, Task9ParentEvidenceSessionClosedError


NOW=datetime(2026,8,10,13,5,tzinfo=timezone.utc)
OPEN=datetime(2026,8,10,5,0,tzinfo=timezone.utc)


def _record_non_fallback_blocker(store, *, observed_at):
 store.record("run",observed_at=observed_at,probe_result="FAILED",failure_reason="HISTORICAL-DATA_UNAVAILABLE")

@pytest.mark.parametrize("offset,code",((0,"TASK9_EXTERNAL_PROVIDER_BLOCKER_ACTIVE"),(2,"RECOVERY_PROBE_REQUIRED")))
def test_active_blocker_stops_launcher_before_dependencies(tmp_path,offset,code):
 store=Task9ExternalProviderBlockerStore(tmp_path);_record_non_fallback_blocker(store,observed_at=NOW if offset==0 else NOW-timedelta(hours=2))
 calls=[]
 launcher=Task9LivePaperCertificationLauncher(persistence_root=tmp_path,official_run_id="run",clock=lambda:NOW+timedelta(minutes=offset),sleep=lambda _:None,task8_dependencies_factory=lambda **_:calls.append(1),runtime_factory=lambda **_:calls.append(2))
 with pytest.raises(Task9ExternalProviderBlockedError,match=code):launcher.run(max_cycles=1)
 assert calls==[] and not (tmp_path/"task9-live-paper.lock").exists() and not list(tmp_path.glob("task9-cycle-results/*"))

def test_corrupt_and_wrong_run_blocker_fail_closed(tmp_path):
 store=Task9ExternalProviderBlockerStore(tmp_path);store.path.parent.mkdir(parents=True, exist_ok=True);store.path.write_text("{}",encoding="utf-8")
 launcher=Task9LivePaperCertificationLauncher(persistence_root=tmp_path,official_run_id="run",clock=lambda:NOW,sleep=lambda _:None)
 with pytest.raises(Exception):launcher.run(max_cycles=1)


def test_active_external_blocker_remains_higher_priority_than_closed_parent_evidence_window(tmp_path):
 store=Task9ExternalProviderBlockerStore(tmp_path);_record_non_fallback_blocker(store,observed_at=NOW-timedelta(hours=2))
 calls=[]
 launcher=Task9LivePaperCertificationLauncher(persistence_root=tmp_path,official_run_id="run",clock=lambda:NOW+timedelta(hours=9),sleep=lambda _:None,task8_dependencies_factory=lambda **_:calls.append(1),runtime_factory=lambda **_:calls.append(2))
 with pytest.raises(Task9ExternalProviderBlockedError,match="RECOVERY_PROBE_REQUIRED"):launcher.run(max_cycles=1)
 assert calls==[] and not (tmp_path/"task9-live-paper.lock").exists()


def test_active_typed_rate_limit_selects_local_fallback_at_open_session_without_blocker_mutation(tmp_path):
 store=Task9ExternalProviderBlockerStore(tmp_path);before=store.record("run",observed_at=OPEN)
 selected=[]
 launcher=Task9LivePaperCertificationLauncher(persistence_root=tmp_path,official_run_id="run",clock=lambda:OPEN,sleep=lambda _:None,task8_dependencies_factory=lambda **_:None,runtime_factory=lambda **_:None)
 launcher._startup_safety=lambda:None
 launcher._run_one_cycle=lambda _manifest,**kwargs:selected.append(kwargs["precomposed_timeframe_provider_factory"])
 launcher.run(max_cycles=1)
 assert len(selected)==1 and callable(selected[0])
 assert store.load("run")==before


@pytest.mark.parametrize("state", ("ABSENT", "CLEARED"))
def test_normal_task9_cycle_always_selects_local_provider_without_historical_rest(tmp_path,state):
 store=Task9ExternalProviderBlockerStore(tmp_path)
 if state=="CLEARED":
  store.record("run",observed_at=OPEN);before=store.clear("run",observed_at=OPEN+timedelta(seconds=1))
 else: before=None
 selected=[]
 launcher=Task9LivePaperCertificationLauncher(persistence_root=tmp_path,official_run_id="run",clock=lambda:OPEN,sleep=lambda _:None,task8_dependencies_factory=lambda **_:None,runtime_factory=lambda **_:None)
 launcher._startup_safety=lambda:None
 launcher._run_one_cycle=lambda _manifest,**kwargs:selected.append(kwargs["precomposed_timeframe_provider_factory"])
 launcher.run(max_cycles=1)
 assert len(selected)==1 and callable(selected[0])
 assert store.load("run")==before


def test_launcher_has_no_direct_legacy_historical_bypass():
 source=__import__("pathlib").Path(__import__("services.certification.task9_live_paper_certification_launcher",fromlist=["__file__"]).__file__).read_text(encoding="utf-8")
 assert "historical_market" not in source
 assert "CompletedCandleService" not in source


def test_active_typed_rate_limit_fallback_still_respects_closed_parent_evidence_session(tmp_path):
 store=Task9ExternalProviderBlockerStore(tmp_path);store.record("run",observed_at=NOW)
 calls=[]
 launcher=Task9LivePaperCertificationLauncher(persistence_root=tmp_path,official_run_id="run",clock=lambda:NOW,sleep=lambda _:None,task8_dependencies_factory=lambda **_:calls.append(1),runtime_factory=lambda **_:calls.append(2))
 launcher._startup_safety=lambda:None
 with pytest.raises(Task9ParentEvidenceSessionClosedError,match="TASK9_PARENT_EVIDENCE_SESSION_CLOSED"):launcher.run(max_cycles=1)
 assert calls==[]
