"""Append-only log of MCX signals evaluated but not entered.

Purpose: after ~200 samples, measure expectancy of 55-69 confidence
signals and decide whether ENTRY_THRESHOLD=70 is optimal.

Never influences trading. Write-only.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

_LOG = os.path.join("data", "paper_trades", "mcx_counterfactual.jsonl")


def log_rejection(*, product, confidence, direction, regime,
                  blocking_reasons, signal_price=None, setup_id=None):
    os.makedirs(os.path.dirname(_LOG), exist_ok=True)
    row = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "product": product,
        "confidence": float(confidence),
        "direction": direction,
        "regime": regime,
        "blocking_reasons": list(blocking_reasons or []),
        "signal_price": signal_price,
        "setup_id": setup_id,
    }
    with open(_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")
