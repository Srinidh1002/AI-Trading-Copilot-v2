"""Plan and apply Task 9 campaign transitions without starting a launcher."""
from __future__ import annotations
from dataclasses import replace
from services.contracts.task9_campaign_rollover_v1 import *
from services.contracts.task9_campaign_manifest_v1 import Task9ActiveCampaignPointerStatus
from services.certification.task9_campaign_authority import validate_task9_campaign_pointer_compatibility
from services.certification.task9_campaign_index_builder import task9_campaign_indexes_semantically_equivalent
from services.certification.task9_live_paper_certification_launcher import Task9LivePaperRunManifestV1
from services.certification.task9_campaign_rollover_target_run import validate_task9_rollover_target_run_manifest
from services.contracts.task9_close_drain_state_v1 import (
    Task9CloseDrainStateV1,
    Task9CloseDrainStatus,
)
def plan_task9_campaign_rollover(*,manifest,pointer,index,target_market_date,requested_official_run_id=None,resume=False,existing_run_terminal=False):
 if target_market_date<pointer.active_market_date:raise ValueError("backward market date")
 if index.numeric_target_met:return Task9CampaignRolloverDecisionV1(manifest.campaign_id,"CAMPAIGN_NUMERIC_TARGET_MET",pointer.active_market_date,pointer.active_official_run_id,target_market_date,None,"NUMERIC_TARGET_MET")
 if pointer.status.value=="HALTED":return Task9CampaignRolloverDecisionV1(manifest.campaign_id,"REMAIN_HALTED",pointer.active_market_date,pointer.active_official_run_id,target_market_date,None,"CAMPAIGN_HALTED")
 if pointer.status.value=="PAUSED":
  if not resume:return Task9CampaignRolloverDecisionV1(manifest.campaign_id,"CAMPAIGN_TERMINAL_NO_CONTINUATION",pointer.active_market_date,pointer.active_official_run_id,target_market_date,None,"CAMPAIGN_PAUSED")
  if target_market_date>pointer.active_market_date:return Task9CampaignRolloverDecisionV1(manifest.campaign_id,"ADVANCE_TO_NEXT_MARKET_DAY",pointer.active_market_date,pointer.active_official_run_id,target_market_date,requested_official_run_id,"EXPLICIT_RESUME_NEXT_MARKET_DAY")
  return Task9CampaignRolloverDecisionV1(manifest.campaign_id,"RESUME_PAUSED_CAMPAIGN",pointer.active_market_date,pointer.active_official_run_id,target_market_date,pointer.active_official_run_id,"EXPLICIT_RESUME")
 if target_market_date==pointer.active_market_date:
  if not existing_run_terminal:return Task9CampaignRolloverDecisionV1(manifest.campaign_id,"CONTINUE_CURRENT_RUN",pointer.active_market_date,pointer.active_official_run_id,target_market_date,pointer.active_official_run_id,"SAME_DAY_RESUME")
  return Task9CampaignRolloverDecisionV1(manifest.campaign_id,"START_NEW_OFFICIAL_RUN",pointer.active_market_date,pointer.active_official_run_id,target_market_date,requested_official_run_id,"SAME_DAY_NEW_RUN")
 return Task9CampaignRolloverDecisionV1(manifest.campaign_id,"ADVANCE_TO_NEXT_MARKET_DAY",pointer.active_market_date,pointer.active_official_run_id,target_market_date,requested_official_run_id,"NEXT_MARKET_DAY")

def _receipt_for(decision, snapshot_id, snapshot_sha256, observed_at):
 return Task9CampaignRolloverReceiptV1(decision.rollover_id,decision.campaign_id,decision.previous_market_date,decision.previous_official_run_id,decision.target_market_date,decision.target_official_run_id,decision.action,"PLANNED",snapshot_id,snapshot_sha256,decision.reason_code,observed_at)

def _ensure_target_config(decision, config, snapshot_id, snapshot_sha256):
 if config.campaign_id!=decision.campaign_id or config.market_date!=decision.target_market_date: raise ValueError("rollover runtime config mismatch")
 if decision.target_official_run_id is not None and config.official_run_id!=decision.target_official_run_id: raise ValueError("rollover runtime run mismatch")
 if config.run_classification!="OFFICIAL_CERTIFICATION" or config.execution_mode!="PAPER" or config.broker_order_submission is not False or config.live_execution_eligible is not False: raise ValueError("unsafe rollover runtime config")
 if type(snapshot_id) is not str or type(snapshot_sha256) is not str: raise ValueError("runtime config provenance")

def _run_get(store, run_id):
 getter=getattr(store,"get",None) or getattr(store,"read",None)
 if not callable(getter): raise TypeError("run manifest store get")
 return getter(run_id)
def _run_save(store, value):
 saver=getattr(store,"save",None) or getattr(store,"persist",None)
 if not callable(saver): raise TypeError("run manifest store save")
 return saver(value)
def _matches_run(existing, intended):
 if existing is None:return False
 try:
  return validate_task9_rollover_target_run_manifest(run_manifest=existing,campaign_id=intended.campaign_id,market_date=intended.market_date,official_run_id=intended.official_run_id,runtime_config_snapshot_id=intended.runtime_config_snapshot_id,runtime_config_sha256=intended.runtime_config_sha256)
 except ValueError:return False

def _require_previous_session_finalized(
    *,
    decision,
    close_drain_state_store,
    finalized_daily_report_index,
):
    if (
        decision.action
        is not Task9CampaignRolloverAction.ADVANCE_TO_NEXT_MARKET_DAY
    ):
        return

    drain_get = getattr(
        close_drain_state_store,
        "get",
        None,
    )
    if not callable(drain_get):
        raise ValueError(
            "TASK9_CLOSE_DRAIN_AUTHORITY_REQUIRED"
        )

    drain_state = drain_get(
        official_run_id=decision.previous_official_run_id,
        market_date=decision.previous_market_date,
    )

    if drain_state is None:
        raise ValueError(
            "TASK9_CLOSE_DRAIN_STATE_MISSING"
        )

    if type(drain_state) is not Task9CloseDrainStateV1:
        raise ValueError(
            "TASK9_CLOSE_DRAIN_STATE_INVALID"
        )

    if (
        drain_state.official_run_id
        != decision.previous_official_run_id
        or drain_state.market_date
        != decision.previous_market_date
    ):
        raise ValueError(
            "TASK9_CLOSE_DRAIN_IDENTITY_MISMATCH"
        )

    if drain_state.status is Task9CloseDrainStatus.BLOCKED:
        raise ValueError(
            "TASK9_CLOSE_DRAIN_BLOCKED"
        )

    if drain_state.status is not Task9CloseDrainStatus.COMPLETE:
        raise ValueError(
            "TASK9_CLOSE_DRAIN_INCOMPLETE:"
            f"{drain_state.status.value}"
        )

    if drain_state.session_phases != (
        ("NIFTY", "CLOSED"),
        ("SENSEX", "CLOSED"),
    ):
        raise ValueError(
            "TASK9_CLOSE_DRAIN_SESSION_NOT_CLOSED"
        )

    report_records = getattr(
        finalized_daily_report_index,
        "all_records",
        None,
    )
    if not callable(report_records):
        raise ValueError(
            "TASK9_FINALIZED_DAILY_REPORT_AUTHORITY_REQUIRED"
        )

    index_run_id = getattr(
        finalized_daily_report_index,
        "official_run_id",
        decision.previous_official_run_id,
    )
    if (
        index_run_id
        != decision.previous_official_run_id
    ):
        raise ValueError(
            "TASK9_FINALIZED_DAILY_REPORT_RUN_MISMATCH"
        )

    expected_date = (
        decision.previous_market_date.isoformat()
    )

    matches = tuple(
        record
        for record in report_records()
        if (
            type(record) is dict
            and record.get("session_date")
            == expected_date
        )
    )

    if not matches:
        raise ValueError(
            "TASK9_PREVIOUS_SESSION_REPORT_NOT_FINALIZED"
        )

    if len(matches) != 1:
        raise ValueError(
            "TASK9_PREVIOUS_SESSION_REPORT_INDEX_CONFLICT"
        )

    record = matches[0]
    for field in (
        "report_id",
        "archive_path",
        "semantic_hash",
    ):
        value = record.get(field)
        if type(value) is not str or not value.strip():
            raise ValueError(
                "TASK9_PREVIOUS_SESSION_REPORT_INDEX_INVALID"
            )

def apply_task9_campaign_rollover(*, decision, manifest, pointer_store, index, runtime_config,
                                  runtime_config_snapshot_id, runtime_config_sha256,
                                  run_manifest_store, receipt_store, observed_at,
                                  close_drain_state_store=None,
                                  finalized_daily_report_index=None):
 """Apply a prior decision using only durable stores, in manifest-before-pointer order.

 ``run_manifest_store`` is deliberately injected: this authority does not alter
 launcher behavior or choose a filesystem layout for a live run.
 """
 if type(decision) is not Task9CampaignRolloverDecisionV1: raise TypeError("decision")
 _ensure_target_config(decision,runtime_config,runtime_config_snapshot_id,runtime_config_sha256)
 current=pointer_store.get()
 if current is None: raise ValueError("active pointer unavailable")
 validate_task9_campaign_pointer_compatibility(manifest,current,require_runtime_config_provenance_match=False)
 existing_receipt=receipt_store.get(decision.rollover_id)
 old_pointer=(current.active_market_date==decision.previous_market_date and current.active_official_run_id==decision.previous_official_run_id)
 target_pointer=(decision.target_official_run_id is not None and current.active_market_date==decision.target_market_date and current.active_official_run_id==decision.target_official_run_id)
 if manifest.campaign_id!=decision.campaign_id or not old_pointer and not (existing_receipt is not None and target_pointer): raise ValueError("stale rollover decision")
 if manifest.campaign_status.value in {"COMPLETED","INVALID"}: raise ValueError("terminal campaign")
 _require_previous_session_finalized(
  decision=decision,
  close_drain_state_store=close_drain_state_store,
  finalized_daily_report_index=finalized_daily_report_index,
 )
 before=index
 receipt=existing_receipt or receipt_store.save(_receipt_for(decision,runtime_config_snapshot_id,runtime_config_sha256,observed_at))
 new_actions={Task9CampaignRolloverAction.START_NEW_OFFICIAL_RUN,Task9CampaignRolloverAction.ADVANCE_TO_NEXT_MARKET_DAY}
 if decision.action in new_actions:
  intended=Task9LivePaperRunManifestV1(official_run_id=decision.target_official_run_id,official_start_at=observed_at,run_classification="OFFICIAL_CERTIFICATION",runtime_config_snapshot_id=runtime_config_snapshot_id,runtime_config_sha256=runtime_config_sha256,campaign_id=manifest.campaign_id,market_date=decision.target_market_date)
  existing=_run_get(run_manifest_store,decision.target_official_run_id)
  if existing is None and receipt.status is not Task9CampaignRolloverReceiptStatus.PLANNED: raise ValueError("receipt claims missing target run manifest")
  if existing is None: _run_save(run_manifest_store,intended)
  elif not _matches_run(existing,intended): raise ValueError("conflicting target run manifest")
  verified=_run_get(run_manifest_store,decision.target_official_run_id)
  if not _matches_run(verified,intended): raise ValueError("target run manifest verification failed")
  if receipt.status is Task9CampaignRolloverReceiptStatus.PLANNED: receipt=receipt_store.advance(receipt.rollover_id,"RUN_MANIFEST_PERSISTED",applied_at=observed_at)
  target=replace(current,active_market_date=decision.target_market_date,active_official_run_id=decision.target_official_run_id,runtime_config_snapshot_id=runtime_config_snapshot_id,runtime_config_sha256=runtime_config_sha256,updated_at=observed_at,status=Task9ActiveCampaignPointerStatus.ACTIVE,startup_preflight_id=None)
  durable=pointer_store.get()
  if durable.active_market_date==target.active_market_date and durable.active_official_run_id==target.active_official_run_id:
   if (durable.runtime_config_snapshot_id,durable.runtime_config_sha256)!=(runtime_config_snapshot_id,runtime_config_sha256): raise ValueError("conflicting target pointer")
  elif durable.active_market_date!=decision.previous_market_date or durable.active_official_run_id!=decision.previous_official_run_id: raise ValueError("pointer advanced elsewhere")
  else:
   if receipt.status in {Task9CampaignRolloverReceiptStatus.POINTER_UPDATED,Task9CampaignRolloverReceiptStatus.APPLIED}: raise ValueError("receipt claims missing target pointer")
   pointer_store.set(
    target,
    manifest=manifest,
    require_runtime_config_provenance_match=False,
   )
  durable=pointer_store.get()
  if durable.active_market_date!=target.active_market_date or durable.active_official_run_id!=target.active_official_run_id or durable.status is not Task9ActiveCampaignPointerStatus.ACTIVE: raise ValueError("target pointer verification failed")
  if receipt.status is Task9CampaignRolloverReceiptStatus.RUN_MANIFEST_PERSISTED: receipt=receipt_store.advance(receipt.rollover_id,"POINTER_UPDATED",applied_at=observed_at)
 elif decision.action is Task9CampaignRolloverAction.RESUME_PAUSED_CAMPAIGN:
  if current.status is not Task9ActiveCampaignPointerStatus.PAUSED: raise ValueError("paused authority changed")
  target=replace(current,status=Task9ActiveCampaignPointerStatus.ACTIVE,updated_at=observed_at,startup_preflight_id=None)
  pointer_store.set(target,manifest=manifest)
  if pointer_store.get().status is not Task9ActiveCampaignPointerStatus.ACTIVE: raise ValueError("resume pointer verification failed")
  receipt=receipt_store.advance(receipt.rollover_id,"RUN_MANIFEST_PERSISTED",applied_at=observed_at)
  receipt=receipt_store.advance(receipt.rollover_id,"POINTER_UPDATED",applied_at=observed_at)
 elif decision.action is Task9CampaignRolloverAction.CONTINUE_CURRENT_RUN:
  if current.status is not Task9ActiveCampaignPointerStatus.ACTIVE: raise ValueError("current run is not active")
  receipt=receipt_store.advance(receipt.rollover_id,"RUN_MANIFEST_PERSISTED",applied_at=observed_at)
  receipt=receipt_store.advance(receipt.rollover_id,"POINTER_UPDATED",applied_at=observed_at)
 else:
  # Halted, numeric-target and terminal decisions are auditable no-ops.
  receipt=receipt_store.advance(receipt.rollover_id,"RUN_MANIFEST_PERSISTED",applied_at=observed_at)
  receipt=receipt_store.advance(receipt.rollover_id,"POINTER_UPDATED",applied_at=observed_at)
 if receipt.status is Task9CampaignRolloverReceiptStatus.POINTER_UPDATED: receipt=receipt_store.advance(receipt.rollover_id,"APPLIED",applied_at=observed_at)
 if not task9_campaign_indexes_semantically_equivalent(before,index): raise ValueError("rollover must not mutate campaign index")
 return receipt


