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
