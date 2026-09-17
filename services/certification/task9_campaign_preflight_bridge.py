from services.contracts.task9_startup_preflight_v1 import Task9StartupPreflightPhase,Task9StartupPreflightPhaseResultV1,Task9StartupPreflightPhaseStatus
from services.contracts.task9_startup_failure_semantics_v1 import build_task9_startup_phase_result,Task9StartupReasonCode
from services.certification.task9_campaign_authority import validate_task9_campaign_pointer_compatibility
def build_task9_campaign_preflight_phase(*,runtime_config,manifest_store,pointer_store,observed_at,runtime_config_snapshot_id=None,runtime_config_sha256=None,campaign_index=None):
 try:
  manifest=manifest_store.get(runtime_config.campaign_id);pointer=pointer_store.get()
 except ValueError:return build_task9_startup_phase_result(phase=Task9StartupPreflightPhase.CAMPAIGN_RUN_ROOT_IDENTITY,reason_code=Task9StartupReasonCode.CORRUPT_AUTHORITATIVE_STATE,observed_at=observed_at)
 if manifest is None or pointer is None:return build_task9_startup_phase_result(phase=Task9StartupPreflightPhase.CAMPAIGN_RUN_ROOT_IDENTITY,reason_code=Task9StartupReasonCode.ACTIVE_AUTHORITY_UNAVAILABLE,observed_at=observed_at)
 try:
  # Campaign-manifest provenance records campaign creation.  After a
  # canonical cross-day rollover, the active pointer records the current
  # official-run provenance.  Validate campaign/root/status compatibility
  # here without requiring those two provenance generations to be equal.
  # Current-run snapshot/SHA and market-date/run identity remain enforced
  # independently below.
  validate_task9_campaign_pointer_compatibility(
   manifest,
   pointer,
   require_runtime_config_provenance_match=False,
  )
  if campaign_index is not None and campaign_index.numeric_target_met:return build_task9_startup_phase_result(phase=Task9StartupPreflightPhase.CAMPAIGN_RUN_ROOT_IDENTITY,reason_code=Task9StartupReasonCode.CAMPAIGN_NUMERIC_TARGET_MET,observed_at=observed_at)
  if manifest.campaign_status.value=="INVALID":return build_task9_startup_phase_result(phase=Task9StartupPreflightPhase.CAMPAIGN_RUN_ROOT_IDENTITY,reason_code=Task9StartupReasonCode.CORRUPT_AUTHORITATIVE_STATE,observed_at=observed_at)
  if manifest.campaign_status.value=="COMPLETED" or pointer.status.value=="COMPLETED":return build_task9_startup_phase_result(phase=Task9StartupPreflightPhase.CAMPAIGN_RUN_ROOT_IDENTITY,reason_code=Task9StartupReasonCode.CAMPAIGN_COMPLETE,observed_at=observed_at)
  if pointer.status.value=="PAUSED":return build_task9_startup_phase_result(phase=Task9StartupPreflightPhase.CAMPAIGN_RUN_ROOT_IDENTITY,reason_code=Task9StartupReasonCode.CAMPAIGN_PAUSED,observed_at=observed_at)
  if pointer.status.value=="HALTED":return build_task9_startup_phase_result(phase=Task9StartupPreflightPhase.CAMPAIGN_RUN_ROOT_IDENTITY,reason_code=Task9StartupReasonCode.CAMPAIGN_HALTED,observed_at=observed_at)
  if runtime_config_snapshot_id is not None and (pointer.runtime_config_snapshot_id,pointer.runtime_config_sha256)!=(runtime_config_snapshot_id,runtime_config_sha256):return build_task9_startup_phase_result(phase=Task9StartupPreflightPhase.CAMPAIGN_RUN_ROOT_IDENTITY,reason_code=Task9StartupReasonCode.SNAPSHOT_HASH_MISMATCH,observed_at=observed_at)
  if pointer.active_market_date!=runtime_config.market_date or pointer.active_official_run_id!=runtime_config.official_run_id:return build_task9_startup_phase_result(phase=Task9StartupPreflightPhase.CAMPAIGN_RUN_ROOT_IDENTITY,reason_code=Task9StartupReasonCode.ROLLOVER_REQUIRED,observed_at=observed_at)
  return Task9StartupPreflightPhaseResultV1(Task9StartupPreflightPhase.CAMPAIGN_RUN_ROOT_IDENTITY,Task9StartupPreflightPhaseStatus.PASS,False,"CAMPAIGN_AUTHORITY_VALID",None,observed_at)
 except ValueError:return build_task9_startup_phase_result(phase=Task9StartupPreflightPhase.CAMPAIGN_RUN_ROOT_IDENTITY,reason_code=Task9StartupReasonCode.CAMPAIGN_RUN_MISMATCH,observed_at=observed_at)
