"""Outcome Ledger - Records completed trade outcomes for offline learning.
"""
import json
import os
from datetime import datetime


class OutcomeLedger:
    def __init__(self, market="NIFTY", base_dir="data/paper_trades"):
        self.market = market.upper()
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)
        self.path = os.path.join(base_dir, f"{self.market.lower()}_outcomes.jsonl")
    
    def record(self, trade):
        """Append one completed trade outcome."""
        record = {
            "timestamp": datetime.now().isoformat(),
            "trade_id": trade.get("trade_id"),
            "market": self.market,
            "symbol": trade.get("symbol"),
            "type": trade.get("type"),
            "strike": trade.get("strike"),
            "signal": trade.get("signal"),
            "entry": trade.get("entry"),
            "exit": trade.get("exit_price"),
            "entry_time": trade.get("entry_time"),
            "exit_time": trade.get("exit_time"),
            "exit_reason": trade.get("exit_reason"),
            "quantity": trade.get("quantity"),
            "lot_size": trade.get("lot_size"),
            "gross_pnl": trade.get("gross_pnl") if trade.get("gross_pnl") is not None else trade.get("pnl"),
            "net_pnl": trade.get("net_pnl") if trade.get("net_pnl") is not None else trade.get("pnl"),
            "net_pnl_pct": trade.get("net_pnl_pct") if trade.get("net_pnl_pct") is not None else trade.get("pnl_pct"),
            "costs_total": trade.get("costs_total"),
            "mfe": trade.get("mfe"),
            "mae": trade.get("mae"),
            "peak_pnl_pct": trade.get("peak_pnl_pct"),
            "trough_pnl_pct": trade.get("trough_pnl_pct"),
            "rank_score": trade.get("rank_score"),
            # D3_cert_eligible — certification contract fields
            "execution_mode": trade.get("execution_mode"),
            "broker_submission": trade.get("broker_submission"),
            "live_execution": trade.get("live_execution"),
            "certification_eligible": trade.get("certification_eligible"),
            # R7_cert_evidence_schema — pure serialization, no derivation.
            # Every field is trade.get(name). Missing -> None.
            # Strategy epoch provenance
            "strategy_version":             trade.get("strategy_version"),
            "certification_epoch":          trade.get("certification_epoch"),
            # Decision linkage
            "prediction_fingerprint":       trade.get("prediction_fingerprint"),
            # Entry execution
            "entry_bid":                    trade.get("entry_bid"),
            "entry_ask":                    trade.get("entry_ask"),
            "entry_ltp":                    trade.get("entry_ltp"),
            # Exit execution
            "exit_bid":                     trade.get("exit_bid"),
            # Milestone booleans
            "t1_hit":                       trade.get("t1_hit"),
            "t2_hit":                       trade.get("t2_hit"),
            # First-touch timestamps
            "t1_first_seen_at":             trade.get("t1_first_seen_at"),
            "t2_first_seen_at":             trade.get("t2_first_seen_at"),
            "t3_first_seen_at":             trade.get("t3_first_seen_at"),
            "sl_first_seen_at":             trade.get("sl_first_seen_at"),
            # First-touch bid levels
            "t1_bid":                       trade.get("t1_bid"),
            "t2_bid":                       trade.get("t2_bid"),
            "t3_bid":                       trade.get("t3_bid"),
            "sl_bid":                       trade.get("sl_bid"),
            # Chronological resolution
            "first_touch_result":           trade.get("first_touch_result"),
            # Certification outcome
            "certification_win":            trade.get("certification_win"),
            "certification_loss":           trade.get("certification_loss"),
            "certification_countable":      trade.get("certification_countable"),
            # Design B trail evidence
            "trail_stop":                   trade.get("trail_stop"),
            "peak_bid":                     trade.get("peak_bid"),
            "trough_bid":                   trade.get("trough_bid"),
            # Monitoring-gap evidence
            "monitoring_gap_count":         trade.get("monitoring_gap_count"),
            "monitoring_gap_started_at":    trade.get("monitoring_gap_started_at"),
            "evidence_ambiguous":           trade.get("evidence_ambiguous"),
            # R15_diversity_evidence - pure serialization; None if absent
            "certification_trade_date":         trade.get("certification_trade_date"),
            "certification_regime":             trade.get("certification_regime"),
            "certification_session_phase":      trade.get("certification_session_phase"),
            "diversity_daily_count_after":      trade.get("diversity_daily_count_after"),
            "diversity_counted":                trade.get("diversity_counted"),
            "certification_countability_reason": trade.get("certification_countability_reason"),
        }
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, default=str) + "\n")
            return True
        except Exception as e:
            print(f"[OutcomeLedger] write failed: {str(e)[:60]}")
            return False
    
    def summary(self):
        """Aggregate stats over all outcomes."""
        if not os.path.exists(self.path):
            return {"total": 0}
        
        trades = []
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        trades.append(json.loads(line))
                    except Exception:
                        continue
        except Exception:
            return {"total": 0}
        
        if not trades:
            return {"total": 0}
        
        wins = [t for t in trades if (t.get("net_pnl") or 0) > 0]
        losses = [t for t in trades if (t.get("net_pnl") or 0) < 0]
        total_net = sum(t.get("net_pnl", 0) or 0 for t in trades)
        
        return {
            "total": len(trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(len(wins) / len(trades) * 100, 1) if trades else 0,
            "total_net_pnl": round(total_net, 2),
            "avg_win": round(sum(t.get("net_pnl", 0) for t in wins) / len(wins), 2) if wins else 0,
            "avg_loss": round(sum(t.get("net_pnl", 0) for t in losses) / len(losses), 2) if losses else 0,
        }


if __name__ == "__main__":
    ledger = OutcomeLedger("NIFTY")
    print(f"Path: {ledger.path}")
    print(f"Summary: {ledger.summary()}")
    print("OutcomeLedger ready")
