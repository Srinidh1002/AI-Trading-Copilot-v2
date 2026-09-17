# services/trading/paper_engine.py - Complete Paper Trading Engine

import asyncio
import logging
from typing import Dict, Optional, List
from datetime import datetime
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class PaperTradingEngine:
    """Paper trading engine with T1/T2/T3 targets."""
    
    def __init__(self, data_provider):
        self.data_provider = data_provider
        self.is_running = False
        self.positions = {}
        self.trades = []
        self.certification_scores = {"NIFTY": 0, "SENSEX": 0}
        self.cycle = 0
        
        # Target percentages (based on deployed capital)
        self.T1 = 0.15   # 15%
        self.T2 = 0.30   # 30%
        self.T3 = 0.50   # 50%
        self.stop_loss = -0.05  # -5%
        
        # Position sizing
        self.position_tiers = {
            "T1": 0.30,
            "T2": 0.30,
            "T3": 0.40
        }
        
        # Entry parameters
        self.min_price_movement = 1.5
        self.min_cycles_before_entry = 3
        
        self.hold_until_target = True
        
        # Subscribe to data
        self.data_provider.subscribe(self._on_data)
        
        # Load certification state
        self._load_certification()
        
        logger.info("📊 PAPER TRADING ENGINE: HOLD FOR T1/T2/T3 MODE ENABLED")
        logger.info(f"📊 T1: {self.T1*100}%, T2: {self.T2*100}%, T3: {self.T3*100}%")
        logger.info(f"📊 Stop Loss: {self.stop_loss*100}%")
    
    async def _on_data(self, tick_data: dict):
        """Callback from data provider."""
        symbol = tick_data.get("symbol", tick_data.get("market", ""))
        ltp = tick_data.get("ltp", 0)
        
        if not symbol or not ltp:
            return
        
        # Process the tick
        await self._process_tick(symbol, ltp)
    
    async def _process_tick(self, symbol: str, ltp: float):
        """Process a single tick."""
        # Update positions if any
        if symbol in self.positions:
            await self._update_position(symbol, ltp)
        else:
            # Look for entry opportunity
            await self._look_for_entry(symbol, ltp)
    
    async def _look_for_entry(self, symbol: str, ltp: float):
        """Look for entry signals."""
        # Simple logic: check if we have enough cycles
        if self.cycle < self.min_cycles_before_entry:
            return
        
        # For now, enter a trade if we have no position
        # This will be replaced with actual strategy logic
        if len(self.positions) < 2:
            await self._enter_position(symbol, ltp, "BUY")
    
    async def _enter_position(self, symbol: str, ltp: float, side: str = "BUY"):
        """Enter a new position."""
        # Calculate position based on capital
        capital_per_trade = 1000000 * 0.05  # 5% of capital per trade
        quantity = int(capital_per_trade / ltp)
        quantity = max(1, min(quantity, 100))  # Limit to reasonable size
        
        position = {
            "symbol": symbol,
            "side": side,
            "entry_price": ltp,
            "entry_time": datetime.now().isoformat(),
            "entry_cycle": self.cycle,
            "current_price": ltp,
            "status": "OPEN",
            "quantity": quantity,
            "booked": {"T1": False, "T2": False, "T3": False},
            "highest_price": ltp,
            "lowest_price": ltp,
            "hold_count": 0,
            "entry_signal": "TEST_SIGNAL"
        }
        
        self.positions[symbol] = position
        
        # Calculate targets based on entry price
        t1 = ltp * (1 + self.T1)
        t2 = ltp * (1 + self.T2)
        t3 = ltp * (1 + self.T3)
        sl = ltp * (1 + self.stop_loss)
        
        logger.info(f"✅ ENTERED {side} position for {symbol} @ {ltp:.2f}")
        logger.info(f"   T1: {t1:.2f} | T2: {t2:.2f} | T3: {t3:.2f} | SL: {sl:.2f}")
    
    async def _update_position(self, symbol: str, ltp: float):
        """Update an existing position."""
        position = self.positions[symbol]
        position["current_price"] = ltp
        position["hold_count"] += 1
        
        # Update highs/lows
        if ltp > position["highest_price"]:
            position["highest_price"] = ltp
        if ltp < position["lowest_price"]:
            position["lowest_price"] = ltp
        
        # Calculate P&L
        if position["side"] == "BUY":
            pnl = ltp - position["entry_price"]
            pnl_percent = (pnl / position["entry_price"]) * 100
        else:
            pnl = position["entry_price"] - ltp
            pnl_percent = (pnl / position["entry_price"]) * 100
        
        # Check targets
        if pnl_percent >= self.T1 * 100 and not position["booked"]["T1"]:
            position["booked"]["T1"] = True
            logger.info(f"🎯 T1 HIT for {symbol}! P&L: {pnl_percent:.2f}%")
            self.certification_scores[symbol] = min(self.certification_scores[symbol] + 1, 100)
            self._save_certification()
        
        if pnl_percent >= self.T2 * 100 and not position["booked"]["T2"]:
            position["booked"]["T2"] = True
            logger.info(f"🎯 T2 HIT for {symbol}! P&L: {pnl_percent:.2f}%")
        
        if pnl_percent >= self.T3 * 100 and not position["booked"]["T3"]:
            position["booked"]["T3"] = True
            logger.info(f"🎯 T3 HIT for {symbol}! P&L: {pnl_percent:.2f}%")
            await self._exit_position(symbol, ltp, "ALL_TARGETS_HIT", pnl_percent)
            return
        
        # Check stop loss
        if pnl_percent <= self.stop_loss * 100:
            logger.warning(f"⛔ STOP LOSS for {symbol}! P&L: {pnl_percent:.2f}%")
            await self._exit_position(symbol, ltp, "STOP_LOSS", pnl_percent)
            return
        
        # Check if all targets are hit
        if all(position["booked"].values()):
            await self._exit_position(symbol, ltp, "ALL_TARGETS_HIT", pnl_percent)
    
    async def _exit_position(self, symbol: str, ltp: float, reason: str, pnl_percent: float):
        """Exit a position."""
        if symbol not in self.positions:
            return
        
        position = self.positions.pop(symbol)
        trade = {
            "symbol": symbol,
            "side": position["side"],
            "entry_price": position["entry_price"],
            "exit_price": ltp,
            "pnl_percent": pnl_percent,
            "entry_time": position["entry_time"],
            "exit_time": datetime.now().isoformat(),
            "reason": reason,
            "holding_cycles": self.cycle - position["entry_cycle"]
        }
        self.trades.append(trade)
        
        logger.info(f"📤 EXIT {symbol}: {reason} | P&L: {pnl_percent:.2f}%")
        
        # Update certification
        if pnl_percent > 0:
            self.certification_scores[symbol] = min(self.certification_scores[symbol] + 1, 100)
            self._save_certification()
    
    async def start(self):
        """Start the engine."""
        self.is_running = True
        logger.info("🚀 Paper trading engine started")
        
        # Start data provider
        await self.data_provider.connect()
        
        # Main cycle loop
        while self.is_running:
            self.cycle += 1
            await self._run_cycle()
            await asyncio.sleep(1)
    
    async def _run_cycle(self):
        """Run a single trading cycle."""
        # Cycle logic is handled by _on_data callback
        if self.cycle % 50 == 0:
            self._log_stats()
    
    def _log_stats(self):
        """Log trading statistics."""
        total_trades = len(self.trades)
        winning_trades = sum(1 for t in self.trades if t.get("pnl_percent", 0) > 0)
        
        t1_hits = sum(1 for t in self.trades if t.get("reason") == "TARGET1_HIT")
        t2_hits = sum(1 for t in self.trades if t.get("reason") == "TARGET2_HIT")
        t3_hits = sum(1 for t in self.trades if t.get("reason") == "TARGET3_HIT")
        
        logger.info(f"""
========================================
📊 STATS (Cycle {self.cycle}):
  Total Trades: {total_trades}
  Win Rate: {(winning_trades/total_trades*100 if total_trades > 0 else 0):.1f}%
  Open Positions: {len(self.positions)}
  
🎯 TARGET HITS:
  T1 (15%): {t1_hits}
  T2 (30%): {t2_hits}
  T3 (50%): {t3_hits}
  
📋 CERTIFICATION:
  NIFTY: {self.certification_scores["NIFTY"]}/100
  SENSEX: {self.certification_scores["SENSEX"]}/100
========================================
        """)
    
    def _load_certification(self):
        """Load certification state."""
        cert_file = Path("data/certification.json")
        if cert_file.exists():
            try:
                with open(cert_file, "r") as f:
                    data = json.load(f)
                    self.certification_scores = data.get("scores", {"NIFTY": 0, "SENSEX": 0})
            except:
                pass
    
    def _save_certification(self):
        """Save certification state."""
        cert_file = Path("data/certification.json")
        cert_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(cert_file, "w") as f:
                json.dump({
                    "scores": self.certification_scores,
                    "updated": datetime.now().isoformat()
                }, f, indent=2)
        except:
            pass
    
    def get_active_trades(self):
        """Get active trades."""
        return self.positions
    
    def stop(self):
        """Stop the engine."""
        self.is_running = False
        self.data_provider.stop()
        logger.info("🛑 Paper trading engine stopped")
