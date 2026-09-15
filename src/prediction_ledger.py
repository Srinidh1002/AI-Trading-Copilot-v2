"""Prediction Ledger - Persistent record of every decision cycle.
Captures full evidence snapshot for audit + learning.
"""
import json
import os
from datetime import datetime
from fingerprint import fingerprint_snapshot


class PredictionLedger:
    def __init__(self, market="NIFTY", base_dir="data/paper_trades"):
        self.market = market.upper()
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)
        self.path = os.path.join(base_dir, f"{self.market.lower()}_predictions.jsonl")
    
    def record(self, prediction):
        """Append one prediction to JSONL (one line per record)."""
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(prediction, default=str) + "\n")
            return True
        except Exception as e:
            print(f"[Ledger] write failed: {str(e)[:60]}")
            return False
    
    def count_today(self):
        """How many predictions today?"""
        if not os.path.exists(self.path):
            return 0
        today = datetime.now().strftime("%Y-%m-%d")
        count = 0
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        rec = json.loads(line)
                        if rec.get("timestamp", "").startswith(today):
                            count += 1
                    except Exception:
                        continue
        except Exception:
            pass
        return count
    
    def build_record(self, market, bias, bias_confidence, readiness, action,
                     blockers, bull_score, bear_score, bull_pillars, bear_pillars,
                     evidence_coverage_pct, spot, spot_freshness, regime,
                     selected_trade=None, config_version="v3"):
        """Build a standard prediction record."""
        record = {
            "timestamp": datetime.now().isoformat(),
            "market": market,
            "bias": bias,
            "bias_confidence": bias_confidence,
            "readiness": readiness,
            "action": action,
            "blockers": blockers or [],
            "bull_score": round(bull_score, 3),
            "bear_score": round(bear_score, 3),
            "bull_pillars": bull_pillars,
            "bear_pillars": bear_pillars,
            "evidence_coverage_pct": round(evidence_coverage_pct, 1),
            "spot": round(spot, 2),
            "spot_freshness": spot_freshness,
            "regime": regime,
            "config_version": config_version,
            "selected_trade": selected_trade,
        }
        # Fingerprint
        record["fingerprint"] = fingerprint_snapshot(
            market=market, bias=bias, action=action,
            bull=round(bull_score, 2), bear=round(bear_score, 2),
            spot=round(spot, 1)
        )
        return record


if __name__ == "__main__":
    ledger = PredictionLedger("NIFTY")
    rec = ledger.build_record(
        market="NIFTY",
        bias="BEARISH", bias_confidence="MODERATE",
        readiness="READY", action="BUY_PUT",
        blockers=[],
        bull_score=1.2, bear_score=2.1,
        bull_pillars=2, bear_pillars=3,
        evidence_coverage_pct=71.4,
        spot=23450.5, spot_freshness="FRESH",
        regime="TRENDING_DOWN",
        selected_trade={"strike": 23600, "type": "PE", "ltp": 175},
    )
    print("Record:")
    print(json.dumps(rec, indent=2))
    
    ok = ledger.record(rec)
    print(f"\nWritten: {ok}")
    print(f"Total today: {ledger.count_today()}")
