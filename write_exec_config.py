import os, json
from datetime import datetime
from zoneinfo import ZoneInfo

path = "data/execution_evidence/mcx/exec_config.json"
os.makedirs(os.path.dirname(path), exist_ok=True)

IST = ZoneInfo("Asia/Kolkata")
cfg = {
  "schema_version": "1.0",
  "calibrated_at": datetime.now(IST).isoformat(timespec="seconds"),
  "evidence_session": "2026-09-14_1733_to_2026-09-15_1009",
  "stage_evidence": {
    "stage2_snapshots": 2,
    "stage3_ws_tokens_resolved": 9,
    "stage3a_ratio_proof_100x": True,
    "stage4_samples_per_token": 180,
    "stage5_spread_samples_per_token": 180,
    "stage5a_depth_samples_per_token": 75
  },
  "CRUDEOILM": {
    "depth_quantity_semantics_verified": True,
    "depth_quantity_unit": "units",
    "execution_freshness_calibrated": True,
    "execution_quote_max_age_seconds": 10.0,
    "rest_depth_supported": True,
    "websocket_depth_supported": True,
    "calibration_source": "S7_STAGE_2_3_4",
    "observed_p95_age_s": 7.03,
    "observed_max_age_s": 7.58,
    "observed_median_spread_ticks": 10.5,
    "observed_best_ask_qty_median": 30
  },
  "GOLDM": {
    "depth_quantity_semantics_verified": True,
    "depth_quantity_unit": "units",
    "execution_freshness_calibrated": True,
    "execution_quote_max_age_seconds": 12.0,
    "rest_depth_supported": True,
    "websocket_depth_supported": True,
    "calibration_source": "S7_STAGE_2_3_4",
    "observed_p95_age_s": 7.57,
    "observed_max_age_s": 9.58,
    "observed_median_spread_ticks": 28.0,
    "observed_best_ask_qty_median": 100
  },
  "NATGASMINI": {
    "depth_quantity_semantics_verified": True,
    "depth_quantity_unit": "units",
    "execution_freshness_calibrated": True,
    "execution_quote_max_age_seconds": 20.0,
    "rest_depth_supported": True,
    "websocket_depth_supported": True,
    "calibration_source": "S7_STAGE_2_3_4",
    "observed_p95_age_s": 11.58,
    "observed_max_age_s": 18.55,
    "observed_median_spread_ticks": 1.0,
    "observed_best_ask_qty_median": 52250,
    "caution": "high_lag_and_duplicate_ticks; PRECERT only"
  }
}

with open(path, "w", encoding="utf-8") as f:
    json.dump(cfg, f, indent=2)
print(f"Wrote {path}")
