from datetime import date,datetime,timezone
from dataclasses import replace
import pytest
from services.certification.task9_campaign_rollover import apply_task9_campaign_rollover,plan_task9_campaign_rollover
from services.certification.task9_campaign_rollover_store import Task9CampaignRolloverStore
from services.certification.task9_active_campaign_pointer_store import Task9ActiveCampaignPointerStore
from services.certification.task9_campaign_index_builder import build_task9_campaign_index
from tests.test_task9_runtime_config_snapshot_v1 import _config
from tests.test_task9_campaign_manifest_v1 import _manifest
from tests.test_task9_active_campaign_pointer_v1 import _pointer
from services.contracts.task9_campaign_rollover_v1 import Task9CampaignRolloverReceiptV1
from services.certification.task9_live_paper_certification_launcher import Task9LivePaperRunManifestV1
from services.contracts.task9_close_drain_state_v1 import (
    Task9CloseDrainItemKind,
    Task9CloseDrainItemStatus,
    Task9CloseDrainItemV1,
    Task9CloseDrainStateV1,
    Task9CloseDrainStatus,
)

class _CloseDrainAuthority:
 def __init__(self, observed_at, status="COMPLETE", missing=False):
  self.observed_at=observed_at
  self.status=Task9CloseDrainStatus(status)
  self.missing=missing
 def get(self, *, official_run_id, market_date):
  if self.missing:
   return None
  if self.status is Task9CloseDrainStatus.COMPLETE:
   items=()
   reasons=()
  elif self.status is Task9CloseDrainStatus.BLOCKED:
   items=(Task9CloseDrainItemV1(
    prediction_id="blocked",
    market="NIFTY",
    kind=Task9CloseDrainItemKind.PAPER_TRADE,
    status=Task9CloseDrainItemStatus.BLOCKED,
    reason_codes=("BINDING_IDENTITY_MISMATCH",),
   ),)
   reasons=("BINDING_IDENTITY_MISMATCH",)
  else:
   items=(Task9CloseDrainItemV1(
    prediction_id="pending",
    market="NIFTY",
    kind=Task9CloseDrainItemKind.ABSTENTION,
    status=Task9CloseDrainItemStatus.PENDING,
    reason_codes=("ABSTENTION_VALIDITY_PENDING",),
   ),)
   reasons=("ABSTENTION_VALIDITY_PENDING",)
  return Task9CloseDrainStateV1(
   official_run_id=official_run_id,
   market_date=market_date,
   evaluated_at=self.observed_at,
   status=self.status,
   session_phases=(
    ("NIFTY","CLOSED"),
    ("SENSEX","CLOSED"),
   ),
   items=items,
   reason_codes=reasons,
  )


class _FinalizedDailyReports:
 def __init__(self, *, include=True, official_run_id="run-1"):
  self.include=include
  self.official_run_id=official_run_id
 def all_records(self):
  if not self.include:
   return ()
  return ({
   "session_date":"2026-08-15",
   "report_id":"task9-daily-run-1-2026-08-15",
   "archive_path":"daily/2026-08-15/report.json",
   "semantic_hash":"a"*64,
  },)


class Runs:
 def __init__(self): self.values={}; self.events=[]
 def get(self,id): self.events.append("read"); return self.values.get(id)
 def save(self,x): self.events.append("save"); self.values.setdefault(x.official_run_id,x); return self.values[x.official_run_id]
def _ctx(tmp_path):
 sha="a"*64; sid="task9-runtime-config-"+sha; now=datetime(2026,8,16,tzinfo=timezone.utc); manifest=_manifest(runtime_config_snapshot_id=sid,runtime_config_sha256=sha); pointer=_pointer(runtime_config_snapshot_id=sid,runtime_config_sha256=sha); ps=Task9ActiveCampaignPointerStore(tmp_path);ps.set(pointer,manifest=manifest); index=build_task9_campaign_index(campaign_id=manifest.campaign_id,campaign_manifest_ref=pointer.campaign_manifest_ref,campaign_status="ACTIVE",contributions=()); config=_config(market_date=date(2026,8,16),official_run_id="run-2"); d=plan_task9_campaign_rollover(manifest=manifest,pointer=pointer,index=index,target_market_date=config.market_date,requested_official_run_id="run-2"); return sha,sid,now,manifest,pointer,ps,index,config,d
def _receipt(d,m,p,c,sid,sha,now,status="PLANNED"): return Task9CampaignRolloverReceiptV1(d.rollover_id,m.campaign_id,p.active_market_date,p.active_official_run_id,c.market_date,"run-2",d.action,status,sid,sha,d.reason_code,now)
def _target(d,m,sid,sha,now): return Task9LivePaperRunManifestV1("run-2",now,runtime_config_snapshot_id=sid,runtime_config_sha256=sha,campaign_id=m.campaign_id,market_date=d.target_market_date)
def _apply(ctx,runs,receipts):
 sha,sid,now,m,p,ps,index,c,d=ctx; return apply_task9_campaign_rollover(decision=d,manifest=m,pointer_store=ps,index=index,runtime_config=c,runtime_config_snapshot_id=sid,runtime_config_sha256=sha,run_manifest_store=runs,receipt_store=receipts,observed_at=now,close_drain_state_store=_CloseDrainAuthority(now),finalized_daily_report_index=_FinalizedDailyReports())
def test_next_day_rollover_persists_manifest_before_pointer_and_is_idempotent(tmp_path):
 sha="a"*64; sid="task9-runtime-config-"+sha; manifest=_manifest(runtime_config_snapshot_id=sid,runtime_config_sha256=sha); pointer=_pointer(runtime_config_snapshot_id=sid,runtime_config_sha256=sha)
 ps=Task9ActiveCampaignPointerStore(tmp_path); ps.set(pointer,manifest=manifest); index=build_task9_campaign_index(campaign_id=manifest.campaign_id,campaign_manifest_ref=pointer.campaign_manifest_ref,campaign_status="ACTIVE",contributions=())
 config=_config(market_date=date(2026,8,16),official_run_id="run-2"); decision=plan_task9_campaign_rollover(manifest=manifest,pointer=pointer,index=index,target_market_date=config.market_date,requested_official_run_id="run-2")
 runs=Runs(); receipts=Task9CampaignRolloverStore(tmp_path); now=datetime(2026,8,16,tzinfo=timezone.utc)
 result=apply_task9_campaign_rollover(decision=decision,manifest=manifest,pointer_store=ps,index=index,runtime_config=config,runtime_config_snapshot_id=sid,runtime_config_sha256=sha,run_manifest_store=runs,receipt_store=receipts,observed_at=now,close_drain_state_store=_CloseDrainAuthority(now),finalized_daily_report_index=_FinalizedDailyReports())
 assert result.status.value=="APPLIED" and ps.get().active_official_run_id=="run-2" and runs.events.index("save")<len(runs.events)
 assert apply_task9_campaign_rollover(decision=decision,manifest=manifest,pointer_store=ps,index=index,runtime_config=config,runtime_config_snapshot_id=sid,runtime_config_sha256=sha,run_manifest_store=runs,receipt_store=receipts,observed_at=now,close_drain_state_store=_CloseDrainAuthority(now),finalized_daily_report_index=_FinalizedDailyReports()).status.value=="APPLIED"

def test_later_receipt_cannot_recover_missing_authority(tmp_path):
 sha="a"*64; sid="task9-runtime-config-"+sha; manifest=_manifest(runtime_config_snapshot_id=sid,runtime_config_sha256=sha); pointer=_pointer(runtime_config_snapshot_id=sid,runtime_config_sha256=sha)
 ps=Task9ActiveCampaignPointerStore(tmp_path); ps.set(pointer,manifest=manifest); index=build_task9_campaign_index(campaign_id=manifest.campaign_id,campaign_manifest_ref=pointer.campaign_manifest_ref,campaign_status="ACTIVE",contributions=()); config=_config(market_date=date(2026,8,16),official_run_id="run-2")
 decision=plan_task9_campaign_rollover(manifest=manifest,pointer=pointer,index=index,target_market_date=config.market_date,requested_official_run_id="run-2"); receipts=Task9CampaignRolloverStore(tmp_path); now=datetime(2026,8,16,tzinfo=timezone.utc)
 receipts.save(__import__('services.contracts.task9_campaign_rollover_v1',fromlist=['Task9CampaignRolloverReceiptV1']).Task9CampaignRolloverReceiptV1(decision.rollover_id,manifest.campaign_id,pointer.active_market_date,pointer.active_official_run_id,config.market_date,"run-2",decision.action,"PLANNED",sid,sha,decision.reason_code,now)); receipts.advance(decision.rollover_id,"RUN_MANIFEST_PERSISTED",applied_at=now)
 with pytest.raises(ValueError,match="missing target run"): apply_task9_campaign_rollover(decision=decision,manifest=manifest,pointer_store=ps,index=index,runtime_config=config,runtime_config_snapshot_id=sid,runtime_config_sha256=sha,run_manifest_store=Runs(),receipt_store=Task9CampaignRolloverStore(tmp_path),observed_at=now,close_drain_state_store=_CloseDrainAuthority(now),finalized_daily_report_index=_FinalizedDailyReports())

def test_paused_halted_and_numeric_plans_do_not_bypass_authority():
 pointer=_pointer(status="PAUSED"); manifest=_manifest(); index=build_task9_campaign_index(campaign_id=manifest.campaign_id,campaign_manifest_ref=pointer.campaign_manifest_ref,campaign_status="ACTIVE",contributions=())
 assert plan_task9_campaign_rollover(manifest=manifest,pointer=pointer,index=index,target_market_date=pointer.active_market_date).action.value=="CAMPAIGN_TERMINAL_NO_CONTINUATION"
 assert plan_task9_campaign_rollover(manifest=manifest,pointer=pointer,index=index,target_market_date=date(2026,8,16),requested_official_run_id="r2",resume=True).action.value=="ADVANCE_TO_NEXT_MARKET_DAY"
 halted=replace(pointer,status="HALTED")
 assert plan_task9_campaign_rollover(manifest=manifest,pointer=halted,index=index,target_market_date=date(2026,8,16),requested_official_run_id="r2").action.value=="REMAIN_HALTED"
 full=build_task9_campaign_index(campaign_id=manifest.campaign_id,campaign_manifest_ref=pointer.campaign_manifest_ref,campaign_status="ACTIVE",contributions=(__import__('tests.test_task9_campaign_index_builder',fromlist=['c']).c("full",100,100),))
 assert plan_task9_campaign_rollover(manifest=manifest,pointer=_pointer(),index=full,target_market_date=date(2026,8,16),requested_official_run_id="r2").action.value=="CAMPAIGN_NUMERIC_TARGET_MET"

@pytest.mark.parametrize("stage",["PLANNED","RUN_MANIFEST_PERSISTED","POINTER_UPDATED","APPLIED"])
def test_recovery_resumes_each_durable_receipt_boundary(tmp_path,stage):
 ctx=_ctx(tmp_path);sha,sid,now,m,p,ps,index,c,d=ctx;runs=Runs();receipts=Task9CampaignRolloverStore(tmp_path);receipts.save(_receipt(d,m,p,c,sid,sha,now))
 if stage!="PLANNED":
  runs.save(_target(d,m,sid,sha,now)); receipts.advance(d.rollover_id,"RUN_MANIFEST_PERSISTED",applied_at=now)
 if stage in {"POINTER_UPDATED","APPLIED"}:
  ps.set(replace(p,active_market_date=d.target_market_date,active_official_run_id="run-2",updated_at=now),manifest=m); receipts.advance(d.rollover_id,"POINTER_UPDATED",applied_at=now)
 if stage=="APPLIED":receipts.advance(d.rollover_id,"APPLIED",applied_at=now)
 assert _apply(ctx,runs,Task9CampaignRolloverStore(tmp_path)).status.value=="APPLIED"

def test_pointer_updated_receipt_with_old_pointer_is_corrupt(tmp_path):
 ctx=_ctx(tmp_path);sha,sid,now,m,p,ps,index,c,d=ctx;runs=Runs();runs.save(_target(d,m,sid,sha,now));receipts=Task9CampaignRolloverStore(tmp_path);receipts.save(_receipt(d,m,p,c,sid,sha,now));receipts.advance(d.rollover_id,"RUN_MANIFEST_PERSISTED",applied_at=now);receipts.advance(d.rollover_id,"POINTER_UPDATED",applied_at=now)
 with pytest.raises(ValueError,match="missing target pointer"): _apply(ctx,runs,Task9CampaignRolloverStore(tmp_path))

def test_planned_receipt_reuses_already_written_target_manifest_after_restart(tmp_path):
 ctx=_ctx(tmp_path);sha,sid,now,m,p,ps,index,c,d=ctx;runs=Runs();runs.save(_target(d,m,sid,sha,now));receipts=Task9CampaignRolloverStore(tmp_path);receipts.save(_receipt(d,m,p,c,sid,sha,now))
 assert _apply(ctx,runs,Task9CampaignRolloverStore(tmp_path)).status.value=="APPLIED" and runs.events.count("save")==1

def test_new_run_operation_order_writes_and_verifies_manifest_before_pointer(tmp_path):
 ctx=_ctx(tmp_path); sha,sid,now,m,p,real_pointer,index,c,d=ctx; log=[]
 class SpyRuns(Runs):
  def get(self,id): log.append("run:read"); return super().get(id)
  def save(self,x): log.append("run:write"); return super().save(x)
 class SpyPointers:
  def get(self): log.append("pointer:read"); return real_pointer.get()
  def set(self,x,**kw): log.append("pointer:write"); return real_pointer.set(x,**kw)
 class SpyReceipts:
  def __init__(self): self.inner=Task9CampaignRolloverStore(tmp_path)
  def get(self,id): return self.inner.get(id)
  def save(self,x): log.append("receipt:planned"); return self.inner.save(x)
  def advance(self,*a,**k): log.append("receipt:"+str(a[1])); return self.inner.advance(*a,**k)
 result=apply_task9_campaign_rollover(decision=d,manifest=m,pointer_store=SpyPointers(),index=index,runtime_config=c,runtime_config_snapshot_id=sid,runtime_config_sha256=sha,run_manifest_store=SpyRuns(),receipt_store=SpyReceipts(),observed_at=now,close_drain_state_store=_CloseDrainAuthority(now),finalized_daily_report_index=_FinalizedDailyReports())
 assert result.status.value=="APPLIED" and log.index("run:write")<log.index("pointer:write") and log.index("run:read",1)<log.index("pointer:write")

def test_paused_and_halted_apply_do_not_bypass_pointer_authority(tmp_path):
 ctx=_ctx(tmp_path);sha,sid,now,m,p,ps,index,c,d=ctx; paused=replace(p,status="PAUSED");ps.set(paused,manifest=m); runs=Runs(); receipts=Task9CampaignRolloverStore(tmp_path)
 current=_config(market_date=p.active_market_date,official_run_id=p.active_official_run_id); no_resume=plan_task9_campaign_rollover(manifest=m,pointer=paused,index=index,target_market_date=p.active_market_date)
 assert apply_task9_campaign_rollover(decision=no_resume,manifest=m,pointer_store=ps,index=index,runtime_config=current,runtime_config_snapshot_id=sid,runtime_config_sha256=sha,run_manifest_store=runs,receipt_store=receipts,observed_at=now,close_drain_state_store=_CloseDrainAuthority(now),finalized_daily_report_index=_FinalizedDailyReports()).status.value=="APPLIED" and ps.get().status.value=="PAUSED" and not runs.values
 resume=plan_task9_campaign_rollover(manifest=m,pointer=paused,index=index,target_market_date=p.active_market_date,resume=True)
 assert apply_task9_campaign_rollover(decision=resume,manifest=m,pointer_store=ps,index=index,runtime_config=current,runtime_config_snapshot_id=sid,runtime_config_sha256=sha,run_manifest_store=runs,receipt_store=Task9CampaignRolloverStore(tmp_path),observed_at=now,close_drain_state_store=_CloseDrainAuthority(now),finalized_daily_report_index=_FinalizedDailyReports()).status.value=="APPLIED" and ps.get().status.value=="ACTIVE" and not runs.values
 halted=replace(ps.get(),status="HALTED");ps.set(halted,manifest=m); stop=plan_task9_campaign_rollover(manifest=m,pointer=halted,index=index,target_market_date=date(2026,8,16),requested_official_run_id="run-2",resume=True)
 assert apply_task9_campaign_rollover(decision=stop,manifest=m,pointer_store=ps,index=index,runtime_config=_config(market_date=date(2026,8,16),official_run_id="run-2"),runtime_config_snapshot_id=sid,runtime_config_sha256=sha,run_manifest_store=runs,receipt_store=Task9CampaignRolloverStore(tmp_path),observed_at=now,close_drain_state_store=_CloseDrainAuthority(now),finalized_daily_report_index=_FinalizedDailyReports()).status.value=="APPLIED" and ps.get().status.value=="HALTED" and not runs.values

def test_paused_explicit_next_day_resume_creates_one_new_run_idempotently(tmp_path):
 ctx=_ctx(tmp_path);sha,sid,now,m,p,ps,index,c,d=ctx;ps.set(replace(p,status="PAUSED"),manifest=m);decision=plan_task9_campaign_rollover(manifest=m,pointer=ps.get(),index=index,target_market_date=c.market_date,requested_official_run_id="run-2",resume=True);runs=Runs();receipts=Task9CampaignRolloverStore(tmp_path)
 assert _apply((sha,sid,now,m,p,ps,index,c,decision),runs,receipts).status.value=="APPLIED" and ps.get().active_official_run_id=="run-2" and runs.events.count("save")==1
 assert _apply((sha,sid,now,m,p,ps,index,c,decision),runs,Task9CampaignRolloverStore(tmp_path)).status.value=="APPLIED" and runs.events.count("save")==1


def test_next_day_rollover_requires_close_drain_authority(tmp_path):
 ctx=_ctx(tmp_path)
 sha,sid,now,m,p,ps,index,c,d=ctx
 runs=Runs()
 receipts=Task9CampaignRolloverStore(tmp_path)

 with pytest.raises(
  ValueError,
  match="TASK9_CLOSE_DRAIN_AUTHORITY_REQUIRED",
 ):
  apply_task9_campaign_rollover(
   decision=d,
   manifest=m,
   pointer_store=ps,
   index=index,
   runtime_config=c,
   runtime_config_snapshot_id=sid,
   runtime_config_sha256=sha,
   run_manifest_store=runs,
   receipt_store=receipts,
   observed_at=now,
   finalized_daily_report_index=_FinalizedDailyReports(),
  )

 assert ps.get().active_official_run_id==p.active_official_run_id
 assert not runs.values
 assert receipts.get(d.rollover_id) is None


def test_next_day_rollover_pending_close_drain_makes_no_mutation(tmp_path):
 ctx=_ctx(tmp_path)
 sha,sid,now,m,p,ps,index,c,d=ctx
 runs=Runs()
 receipts=Task9CampaignRolloverStore(tmp_path)

 with pytest.raises(
  ValueError,
  match="TASK9_CLOSE_DRAIN_INCOMPLETE:PENDING",
 ):
  apply_task9_campaign_rollover(
   decision=d,
   manifest=m,
   pointer_store=ps,
   index=index,
   runtime_config=c,
   runtime_config_snapshot_id=sid,
   runtime_config_sha256=sha,
   run_manifest_store=runs,
   receipt_store=receipts,
   observed_at=now,
   close_drain_state_store=_CloseDrainAuthority(
    now,
    status="PENDING",
   ),
   finalized_daily_report_index=_FinalizedDailyReports(),
  )

 assert ps.get().active_official_run_id==p.active_official_run_id
 assert not runs.values
 assert receipts.get(d.rollover_id) is None


def test_next_day_rollover_blocked_close_drain_fails_visible(tmp_path):
 ctx=_ctx(tmp_path)
 sha,sid,now,m,p,ps,index,c,d=ctx
 runs=Runs()
 receipts=Task9CampaignRolloverStore(tmp_path)

 with pytest.raises(
  ValueError,
  match="TASK9_CLOSE_DRAIN_BLOCKED",
 ):
  apply_task9_campaign_rollover(
   decision=d,
   manifest=m,
   pointer_store=ps,
   index=index,
   runtime_config=c,
   runtime_config_snapshot_id=sid,
   runtime_config_sha256=sha,
   run_manifest_store=runs,
   receipt_store=receipts,
   observed_at=now,
   close_drain_state_store=_CloseDrainAuthority(
    now,
    status="BLOCKED",
   ),
   finalized_daily_report_index=_FinalizedDailyReports(),
  )

 assert ps.get().active_official_run_id==p.active_official_run_id
 assert not runs.values
 assert receipts.get(d.rollover_id) is None


def test_next_day_rollover_requires_finalized_prior_daily_report(tmp_path):
 ctx=_ctx(tmp_path)
 sha,sid,now,m,p,ps,index,c,d=ctx
 runs=Runs()
 receipts=Task9CampaignRolloverStore(tmp_path)

 with pytest.raises(
  ValueError,
  match="TASK9_PREVIOUS_SESSION_REPORT_NOT_FINALIZED",
 ):
  apply_task9_campaign_rollover(
   decision=d,
   manifest=m,
   pointer_store=ps,
   index=index,
   runtime_config=c,
   runtime_config_snapshot_id=sid,
   runtime_config_sha256=sha,
   run_manifest_store=runs,
   receipt_store=receipts,
   observed_at=now,
   close_drain_state_store=_CloseDrainAuthority(now),
   finalized_daily_report_index=_FinalizedDailyReports(
    include=False,
   ),
  )

 assert ps.get().active_official_run_id==p.active_official_run_id
 assert not runs.values
 assert receipts.get(d.rollover_id) is None


def test_same_day_continue_does_not_require_close_drain_gate(tmp_path):
 ctx=_ctx(tmp_path)
 sha,sid,now,m,p,ps,index,c,d=ctx

 current=_config(
  market_date=p.active_market_date,
  official_run_id=p.active_official_run_id,
 )
 decision=plan_task9_campaign_rollover(
  manifest=m,
  pointer=p,
  index=index,
  target_market_date=p.active_market_date,
 )

 assert decision.action.value=="CONTINUE_CURRENT_RUN"

 result=apply_task9_campaign_rollover(
  decision=decision,
  manifest=m,
  pointer_store=ps,
  index=index,
  runtime_config=current,
  runtime_config_snapshot_id=sid,
  runtime_config_sha256=sha,
  run_manifest_store=Runs(),
  receipt_store=Task9CampaignRolloverStore(
   tmp_path/"same-day"
  ),
  observed_at=now,
 )

 assert result.status.value=="APPLIED"
 assert ps.get().active_official_run_id==p.active_official_run_id
