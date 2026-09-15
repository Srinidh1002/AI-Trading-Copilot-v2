"""Pure validation of a new rollover target run authority."""
from __future__ import annotations
from datetime import date

def validate_task9_rollover_target_run_manifest(*, run_manifest, campaign_id, market_date,
                                                 official_run_id, runtime_config_snapshot_id,
                                                 runtime_config_sha256):
    """Reject legacy/incomplete or conflicting evidence as a new target run."""
    if type(market_date) is not date:
        raise ValueError("market_date")
    expected = (campaign_id, market_date, official_run_id, runtime_config_snapshot_id, runtime_config_sha256)
    actual = (getattr(run_manifest,"campaign_id",None), getattr(run_manifest,"market_date",None),
              getattr(run_manifest,"official_run_id",None), getattr(run_manifest,"runtime_config_snapshot_id",None),
              getattr(run_manifest,"runtime_config_sha256",None))
    if actual != expected:
        raise ValueError("target run manifest identity mismatch")
    if (getattr(run_manifest,"run_classification",None) != "OFFICIAL_CERTIFICATION" or
        getattr(run_manifest,"execution_mode",None) != "PAPER" or
        getattr(run_manifest,"broker_order_submission",None) is not False or
        getattr(run_manifest,"live_execution_eligible",None) is not False):
        raise ValueError("unsafe target run manifest")
    return True
