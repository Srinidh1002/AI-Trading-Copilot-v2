"""
Certification Runner - PDF Sections 35-40
100 countable live PAPER trades per market.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging
import json
from pathlib import Path


@dataclass
class CertificationRecord:
    """Single certification record."""
    trade_id: str
    market: str
    direction: str
    entry_price: float
    exit_price: float
    pnl: float
    win: bool
    entry_time: datetime
    exit_time: datetime
    exit_reason: str
    confidence: float
    decision_gates_passed: int
    total_gates: int
    is_countable: bool = True
    is_duplicate: bool = False
    is_replay: bool = False
    is_synthetic: bool = False


@dataclass
class CertificationStats:
    """Certification statistics."""
    market: str
    target_trades: int = 100
    total_trades: int = 0
    countable_trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    target1_hit_rate: float = 0.0
    target2_hit_rate: float = 0.0
    target3_hit_rate: float = 0.0
    no_trade_count: int = 0
    invalid_records: int = 0
    certification_complete: bool = False
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class CertificationRunner:
    """
    Certification Runner - PDF Sections 35-40.
    
    Tracks 100 countable live PAPER records per market.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # Configuration
        self.target_trades = self.config.get("target_trades", 100)
        self.markets = self.config.get("markets", ["NIFTY", "SENSEX"])
        
        # State
        self.records: Dict[str, List[CertificationRecord]] = {}
        self.stats: Dict[str, CertificationStats] = {}
        
        # Persistence
        self.persist_path = Path(self.config.get("persist_path", "data/certification"))
        self.persist_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize stats for each market
        for market in self.markets:
            self.stats[market] = CertificationStats(market=market, target_trades=self.target_trades)
            self.records[market] = []
    
    def record_trade(self, trade, market: str) -> bool:
        """
        Record a trade for certification.
        
        PDF Section 36-37: What counts vs what does NOT count.
        """
        # Check if this is a countable record
        if not self._is_countable(trade):
            self.logger.info(f"Trade {trade.trade_id} is NOT countable")
            self.stats[market].invalid_records += 1
            return False
        
        # Check for duplicates
        if self._is_duplicate(trade, market):
            self.logger.warning(f"Trade {trade.trade_id} is a duplicate")
            return False
        
        # Create certification record
        record = CertificationRecord(
            trade_id=trade.trade_id,
            market=market,
            direction=trade.direction,
            entry_price=trade.entry_price,
            exit_price=trade.exit_price or trade.entry_price,
            pnl=trade.pnl,
            win=trade.pnl > 0,
            entry_time=trade.entry_time,
            exit_time=trade.exit_time or datetime.now(),
            exit_reason=trade.exit_reason or "UNKNOWN",
            confidence=trade.decision_confidence,
            decision_gates_passed=len([g for g in trade.gate_results if g.get("status") == "PASS"]),
            total_gates=len(trade.gate_results),
            is_countable=True,
            is_duplicate=False,
            is_replay=(trade.mode == "replay"),
            is_synthetic=(trade.mode == "synthetic")
        )
        
        # Add to records
        self.records[market].append(record)
        
        # Update stats
        stats = self.stats[market]
        stats.total_trades += 1
        stats.countable_trades += 1
        
        if record.win:
            stats.wins += 1
        else:
            stats.losses += 1
        
        stats.total_pnl += record.pnl
        
        # Check if certification is complete
        if stats.countable_trades >= self.target_trades:
            stats.certification_complete = True
            stats.completed_at = datetime.now()
            self.logger.info(f"CERTIFICATION COMPLETE for {market}: {stats.countable_trades} countable trades")
        
        # Persist
        self._persist_records(market)
        self._persist_stats(market)
        
        return True
    
    def record_decision(self, market: str, decision: str, reason: str):
        """Record a NO_TRADE or WAIT decision for analytics."""
        # NO_TRADE does NOT count toward certification (PDF Section 19)
        if decision in ["NO_TRADE", "WAIT"]:
            self.stats[market].no_trade_count += 1
            self.logger.debug(f"{decision} recorded for {market}: {reason}")
    
    def is_complete(self, market: str) -> bool:
        """Check if certification is complete for a market."""
        stats = self.stats.get(market)
        if not stats:
            return False
        return stats.certification_complete
    
    def get_stats(self, market: str) -> Optional[CertificationStats]:
        """Get certification stats for a market."""
        return self.stats.get(market)
    
    def get_all_stats(self) -> Dict[str, CertificationStats]:
        """Get stats for all markets."""
        return self.stats
    
    def get_records(self, market: str) -> List[CertificationRecord]:
        """Get all certification records for a market."""
        return self.records.get(market, [])
    
    def _is_countable(self, trade) -> bool:
        """
        PDF Section 36-37: What counts.
        
        A record counts only if it is:
        - LIVE (not replay)
        - PAPER (not live execution)
        - VALID (all gates passed)
        - COUNTABLE (not NO_TRADE/WAIT)
        - MARKET-SPECIFIC
        """
        # Check mode
        if getattr(trade, "mode", "paper") not in ["paper", "live"]:
            return False
        
        # Check if it's a valid trade
        if not getattr(trade, "is_valid", True):
            return False
        
        # Check if all gates passed
        gate_results = getattr(trade, "gate_results", [])
        if gate_results:
            passed = len([g for g in gate_results if g.get("status") == "PASS"])
            total = len(gate_results)
            if passed < total:
                return False
        
        # Check if it's a trade (not NO_TRADE/WAIT)
        if getattr(trade, "status", "") in ["NO_TRADE", "WAIT"]:
            return False
        
        return True
    
    def _is_duplicate(self, trade, market: str) -> bool:
        """Check if trade is a duplicate."""
        existing = self.records.get(market, [])
        
        # Check by trade_id
        for record in existing:
            if record.trade_id == trade.trade_id:
                return True
        
        # Check by entry_time + market + direction (within 1 second)
        for record in existing:
            time_diff = abs((trade.entry_time - record.entry_time).total_seconds())
            if (time_diff < 1 and 
                record.market == market and 
                record.direction == trade.direction):
                return True
        
        return False
    
    def _persist_records(self, market: str):
        """Persist certification records."""
        path = self.persist_path / f"{market}_records.json"
        records = self.records.get(market, [])
        
        data = []
        for r in records:
            data.append({
                "trade_id": r.trade_id,
                "market": r.market,
                "direction": r.direction,
                "entry_price": r.entry_price,
                "exit_price": r.exit_price,
                "pnl": r.pnl,
                "win": r.win,
                "entry_time": r.entry_time.isoformat(),
                "exit_time": r.exit_time.isoformat(),
                "exit_reason": r.exit_reason,
                "confidence": r.confidence,
                "is_countable": r.is_countable,
                "is_duplicate": r.is_duplicate
            })
        
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    
    def _persist_stats(self, market: str):
        """Persist certification stats."""
        path = self.persist_path / f"{market}_stats.json"
        stats = self.stats.get(market)
        if not stats:
            return
        
        data = {
            "market": stats.market,
            "target_trades": stats.target_trades,
            "total_trades": stats.total_trades,
            "countable_trades": stats.countable_trades,
            "wins": stats.wins,
            "losses": stats.losses,
            "win_rate": stats.win_rate,
            "total_pnl": stats.total_pnl,
            "profit_factor": stats.profit_factor,
            "max_drawdown": stats.max_drawdown,
            "avg_win": stats.avg_win,
            "avg_loss": stats.avg_loss,
            "target1_hit_rate": stats.target1_hit_rate,
            "target2_hit_rate": stats.target2_hit_rate,
            "target3_hit_rate": stats.target3_hit_rate,
            "no_trade_count": stats.no_trade_count,
            "invalid_records": stats.invalid_records,
            "certification_complete": stats.certification_complete,
            "started_at": stats.started_at.isoformat() if stats.started_at else None,
            "completed_at": stats.completed_at.isoformat() if stats.completed_at else None
        }
        
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    
    def _calculate_derived_stats(self, market: str):
        """Calculate derived statistics."""
        stats = self.stats.get(market)
        if not stats:
            return
        
        total = stats.wins + stats.losses
        stats.win_rate = (stats.wins / total * 100) if total > 0 else 0
        
        # Profit factor
        win_pnl = sum(r.pnl for r in self.records.get(market, []) if r.win)
        loss_pnl = abs(sum(r.pnl for r in self.records.get(market, []) if not r.win))
        stats.profit_factor = win_pnl / loss_pnl if loss_pnl > 0 else 0
        
        # Average win/loss
        wins = [r.pnl for r in self.records.get(market, []) if r.win]
        losses = [abs(r.pnl) for r in self.records.get(market, []) if not r.win]
        stats.avg_win = sum(wins) / len(wins) if wins else 0
        stats.avg_loss = sum(losses) / len(losses) if losses else 0
    
    def generate_report(self, market: str) -> Dict:
        """Generate certification report."""
        self._calculate_derived_stats(market)
        stats = self.stats.get(market)
        
        if not stats:
            return {}
        
        return {
            "market": stats.market,
            "target_trades": stats.target_trades,
            "countable_trades": stats.countable_trades,
            "total_trades": stats.total_trades,
            "wins": stats.wins,
            "losses": stats.losses,
            "win_rate": stats.win_rate,
            "total_pnl": stats.total_pnl,
            "profit_factor": stats.profit_factor,
            "max_drawdown": stats.max_drawdown,
            "avg_win": stats.avg_win,
            "avg_loss": stats.avg_loss,
            "no_trade_count": stats.no_trade_count,
            "certification_complete": stats.certification_complete,
            "duration_hours": (
                (stats.completed_at - stats.started_at).total_seconds() / 3600
                if stats.started_at and stats.completed_at else 0
            )
        }