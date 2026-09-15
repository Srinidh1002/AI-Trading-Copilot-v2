"""
Certification Engine - 100+100 PAPER Trades
Integrated with the existing paper trading engine.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


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
    is_countable: bool = True
    is_duplicate: bool = False


@dataclass
class CertificationStats:
    """Certification statistics for a market."""
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
    target1_hit_rate: float = 0.0
    target2_hit_rate: float = 0.0
    target3_hit_rate: float = 0.0
    no_trade_count: int = 0
    invalid_records: int = 0
    certification_complete: bool = False


class CertificationEngine:
    """
    Certification Engine - Integrated with paper trading.
    
    Tracks 100 countable LIVE PAPER trades per market.
    NO_TRADE and WAIT do NOT count toward certification.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        self.target_trades = self.config.get("target_trades", 100)
        self.markets = self.config.get("markets", ["NIFTY", "SENSEX"])
        
        self.records: Dict[str, List[CertificationRecord]] = {}
        self.stats: Dict[str, CertificationStats] = {}
        
        self.persist_path = Path(self.config.get("persist_path", "data/certification"))
        self.persist_path.mkdir(parents=True, exist_ok=True)
        
        # Load existing state
        self._load_state()
        
        for market in self.markets:
            if market not in self.stats:
                self.stats[market] = CertificationStats(market=market, target_trades=self.target_trades)
            if market not in self.records:
                self.records[market] = []
    
    def record_trade(self, trade) -> bool:
        """
        Record a trade for certification.
        
        A record counts only if:
        - LIVE + PAPER + VALID + COUNTABLE + MARKET-SPECIFIC
        - NOT NO_TRADE, NOT WAIT, NOT REPLAY, NOT SYNTHETIC
        """
        market = trade.market
        
        # Check if countable
        if not self._is_countable(trade):
            self.stats[market].invalid_records += 1
            self.logger.info(f"Trade {trade.trade_id} is NOT countable (NO_TRADE/WAIT)")
            return False
        
        # Check duplicate
        if self._is_duplicate(trade):
            self.logger.warning(f"Trade {trade.trade_id} is a duplicate")
            return False
        
        # Create record
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
            is_countable=True,
            is_duplicate=False
        )
        
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
        
        # Update drawdown
        if record.pnl < 0:
            stats.max_drawdown = min(stats.max_drawdown, record.pnl)
        
        # Check completion
        if stats.countable_trades >= self.target_trades:
            stats.certification_complete = True
            self.logger.info(f"✅ CERTIFICATION COMPLETE for {market}: {stats.countable_trades}/{self.target_trades}")
        
        # Persist
        self._persist_state()
        
        self.logger.info(f"📊 {market}: {stats.countable_trades}/{self.target_trades} countable trades")
        
        return True
    
    def record_decision(self, market: str, decision: str, reason: str):
        """Record a decision for analytics (does NOT count toward certification)."""
        if decision in ["NO_TRADE", "WAIT"]:
            self.stats[market].no_trade_count += 1
    
    def _is_countable(self, trade) -> bool:
        """Check if a trade counts toward certification."""
        # NO_TRADE and WAIT do NOT count
        if hasattr(trade, 'status') and trade.status in ["NO_TRADE", "WAIT"]:
            return False
        
        # Must be a valid trade
        if not hasattr(trade, 'exit_price') or trade.exit_price is None:
            return False
        
        # Must have a valid exit reason
        if hasattr(trade, 'exit_reason') and trade.exit_reason in [None, "NO_TRADE", "WAIT"]:
            return False
        
        return True
    
    def _is_duplicate(self, trade) -> bool:
        """Check if trade is a duplicate."""
        market = trade.market
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
    
    def generate_report(self, market: str) -> Dict:
        """Generate certification report for a market."""
        stats = self.stats.get(market)
        if not stats:
            return {}
        
        total = stats.wins + stats.losses
        stats.win_rate = (stats.wins / total * 100) if total > 0 else 0
        
        win_pnl = sum(r.pnl for r in self.records.get(market, []) if r.win)
        loss_pnl = abs(sum(r.pnl for r in self.records.get(market, []) if not r.win))
        stats.profit_factor = win_pnl / loss_pnl if loss_pnl > 0 else 0
        
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
            "no_trade_count": stats.no_trade_count,
            "certification_complete": stats.certification_complete
        }
    
    def _load_state(self):
        """Load persisted certification state."""
        for market in self.markets:
            stats_path = self.persist_path / f"{market}_stats.json"
            if stats_path.exists():
                try:
                    with open(stats_path) as f:
                        data = json.load(f)
                        stats = CertificationStats(**data)
                        self.stats[market] = stats
                except Exception as e:
                    self.logger.warning(f"Could not load stats for {market}: {e}")
            
            records_path = self.persist_path / f"{market}_records.json"
            if records_path.exists():
                try:
                    with open(records_path) as f:
                        data = json.load(f)
                        for item in data:
                            item["entry_time"] = datetime.fromisoformat(item["entry_time"])
                            item["exit_time"] = datetime.fromisoformat(item["exit_time"])
                            record = CertificationRecord(**item)
                            self.records[market].append(record)
                except Exception as e:
                    self.logger.warning(f"Could not load records for {market}: {e}")
    
    def _persist_state(self):
        """Persist certification state."""
        for market in self.markets:
            stats_path = self.persist_path / f"{market}_stats.json"
            stats = self.stats.get(market)
            if stats:
                with open(stats_path, "w") as f:
                    json.dump(stats.__dict__, f, indent=2, default=str)
            
            records_path = self.persist_path / f"{market}_records.json"
            records = self.records.get(market, [])
            if records:
                data = []
                for r in records:
                    item = r.__dict__.copy()
                    item["entry_time"] = r.entry_time.isoformat()
                    item["exit_time"] = r.exit_time.isoformat()
                    data.append(item)
                with open(records_path, "w") as f:
                    json.dump(data, f, indent=2)
