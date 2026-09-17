# services/trading/advanced_paper_engine.py - Fixed for Certification

import asyncio
import logging
import json
import random
from typing import Dict, Optional, List
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class AdvancedPaperTradingEngine:
    """Advanced paper trading engine - CERTIFICATION MODE."""
    
    def __init__(self, data_provider, capital: float = 1000000):
        self.data_provider = data_provider
        self.capital = capital
        self.is_running = False
        self.positions = {}
        self.trades = []
        self.certification_scores = {"NIFTY": 0, "SENSEX": 0}
        self.cycle = 0
        self.entry_count = 0
        self.max_entries = 200
        
        # Target percentages
        self.T1 = 0.15
        self.T2 = 0.30
        self.T3 = 0.50
        self.stop_loss_pct = 0.05
        
        # Lot sizes
        self.lot_sizes = {"NIFTY": 65, "SENSEX": 20}
        self.strike_steps = {"NIFTY": 50, "SENSEX": 100}
        
        # Entry parameters - AGGRESSIVE for certification
        self.min_cycles_before_entry = 2
        self.max_positions = 2
        
        # Track last recommendation
        self.last_recommendation = {}
        
        # Subscribe to data
        self.data_provider.subscribe(self._on_data)
        
        # Load certification state
        self._load_certification()
        
        logger.info("=" * 60)
        logger.info("📊 ADVANCED PAPER TRADING ENGINE - CERTIFICATION MODE")
        logger.info(f"📊 Capital: ₹{capital:,.2f}")
        logger.info(f"📊 T1: {self.T1*100}%, T2: {self.T2*100}%, T3: {self.T3*100}%")
        logger.info(f"📊 Stop Loss: {self.stop_loss_pct*100}%")
        logger.info("=" * 60)
    
    async def _on_data(self, tick_data: dict):
        """Callback from data provider."""
        symbol = tick_data.get("symbol", tick_data.get("market", ""))
        ltp = tick_data.get("ltp", 0)
        
        if not symbol or not ltp:
            return
        
        # Log strike recommendation
        best_call = tick_data.get("best_call", {})
        if best_call and best_call.get("strike", 0) > 0:
            self.last_recommendation[symbol] = {
                "strike": best_call.get("strike", 0),
                "premium": best_call.get("premium", 0),
                "score": best_call.get("score", 0),
                "moneyness": best_call.get("moneyness", "UNKNOWN"),
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"💡 [{symbol}] RECOMMENDATION: Strike {best_call.get('strike', 0)} @ ₹{best_call.get('premium', 0):.2f} (Score: {best_call.get('score', 0)})")
        
        # Process the tick - ENTER AGGRESSIVELY
        await self._process_tick(symbol, ltp, tick_data)
    
    async def _process_tick(self, symbol: str, ltp: float, tick_data: dict):
        """Process a single tick."""
        # Update positions if any
        if symbol in self.positions:
            await self._update_position(symbol, ltp, tick_data)
        else:
            # Look for entry opportunity - AGGRESSIVE
            if self.cycle >= self.min_cycles_before_entry:
                await self._look_for_entry(symbol, ltp, tick_data)
    
    async def _look_for_entry(self, symbol: str, ltp: float, tick_data: dict):
        """Look for entry opportunities - AGGRESSIVE."""
        # Check if we have room for more positions
        if len(self.positions) >= self.max_positions:
            return
        
        # Check if already have this symbol
        if symbol in self.positions:
            return
        
        # Check if we've reached max entries
        if len(self.trades) >= self.max_entries:
            return
        
        # Get best strike from data provider
        best_call = tick_data.get("best_call", {})
        
        # If no best_call, try to get from data provider directly
        if not best_call or best_call.get("premium", 0) <= 0:
            # Try to get option chain and find best
            chain = self.data_provider.get_option_chain(symbol) if hasattr(self.data_provider, "get_option_chain") else []
            if chain:
                for strike_data in chain:
                    if strike_data.get("is_atm", False):
                        best_call = {
                            "strike": strike_data.get("strike", 0),
                            "premium": strike_data.get("call_ltp", 0),
                            "score": 50,
                            "moneyness": "ATM"
                        }
                        break
        
        # If still no valid strike, calculate ATM manually
        if not best_call or best_call.get("premium", 0) <= 0:
            step = self.strike_steps.get(symbol, 50)
            atm_strike = round(ltp / step) * step
            if symbol == "NIFTY":
                premium = ltp * 0.0044
            else:
                premium = ltp * 0.0015
            premium = max(10, round(premium, 2))
            best_call = {
                "strike": atm_strike,
                "premium": premium,
                "score": 40,
                "moneyness": "ATM"
            }
        
        strike = best_call.get("strike", 0)
        premium = best_call.get("premium", 0)
        
        if premium <= 0 or strike <= 0:
            logger.debug(f"⏳ {symbol}: No valid strike (premium={premium}, strike={strike})")
            return
        
        # ENTER THE TRADE - AGGRESSIVE
        await self._enter_position(symbol, ltp, strike, premium, tick_data)
    
    async def _enter_position(self, symbol: str, ltp: float, strike: float, premium: float, tick_data: dict):
        """Enter a new position."""
        # Calculate position size (1 lot)
        lot_size = self.lot_sizes.get(symbol, 65)
        quantity = lot_size
        deployed = premium * quantity
        
        # Calculate targets
        t1 = premium * (1 + self.T1)
        t2 = premium * (1 + self.T2)
        t3 = premium * (1 + self.T3)
        sl = premium * (1 - self.stop_loss_pct)
        
        position = {
            "symbol": symbol,
            "strike": strike,
            "option_type": "CALL",
            "entry_premium": premium,
            "entry_underlying": ltp,
            "entry_time": datetime.now().isoformat(),
            "entry_cycle": self.cycle,
            "quantity": quantity,
            "lot_size": lot_size,
            "deployed_capital": deployed,
            "status": "OPEN",
            "current_premium": premium,
            "current_underlying": ltp,
            "hold_count": 0,
            "pnl": 0,
            "pnl_percent": 0,
            "target1": t1,
            "target2": t2,
            "target3": t3,
            "stop_loss": sl,
            "targets_hit": {"T1": False, "T2": False, "T3": False}
        }
        
        self.positions[symbol] = position
        self.entry_count += 1
        
        logger.info("=" * 60)
        logger.info(f"✅ [TRADE #{self.entry_count}] {symbol} CALL")
        logger.info(f"   📍 Strike: {strike}")
        logger.info(f"   💰 Premium: ₹{premium:.2f}")
        logger.info(f"   📦 Quantity: {quantity} ({lot_size} shares/lot)")
        logger.info(f"   📊 Underlying: ₹{ltp:,.2f}")
        logger.info(f"   💵 Deployed: ₹{deployed:,.2f} ({deployed/self.capital*100:.1f}%)")
        logger.info(f"   🎯 T1: ₹{t1:.2f} (+{self.T1*100}%)")
        logger.info(f"   🎯 T2: ₹{t2:.2f} (+{self.T2*100}%)")
        logger.info(f"   🎯 T3: ₹{t3:.2f} (+{self.T3*100}%)")
        logger.info(f"   ⛔ Stop Loss: ₹{sl:.2f} (-{self.stop_loss_pct*100}%)")
        logger.info("=" * 60)
        
        self._save_certification()
    
    async def _update_position(self, symbol: str, ltp: float, tick_data: dict):
        """Update an existing position."""
        position = self.positions[symbol]
        position["hold_count"] += 1
        
        # Get current premium from tick data
        best_call = tick_data.get("best_call", {})
        current_premium = best_call.get("premium", position["entry_premium"])
        
        # If premium is 0, try to calculate from chain
        if current_premium <= 0:
            chain = self.data_provider.get_option_chain(symbol) if hasattr(self.data_provider, "get_option_chain") else []
            for strike_data in chain:
                if strike_data.get("strike", 0) == position["strike"]:
                    current_premium = strike_data.get("call_ltp", position["entry_premium"])
                    break
        
        position["current_premium"] = current_premium
        position["current_underlying"] = ltp
        
        pnl = (current_premium - position["entry_premium"]) * position["quantity"]
        pnl_pct = ((current_premium / position["entry_premium"]) - 1) * 100
        position["pnl"] = pnl
        position["pnl_percent"] = pnl_pct
        
        # Log every cycle
        logger.info(f"📊 {symbol}: Underlying ₹{ltp:,.2f} | Premium ₹{current_premium:.2f} | P&L {pnl_pct:+.1f}% (₹{pnl:,.2f})")
        logger.info(f"   Targets: T1 ₹{position['target1']:.2f} | T2 ₹{position['target2']:.2f} | T3 ₹{position['target3']:.2f}")
        
        # Check targets
        if pnl_pct >= self.T1 * 100 and not position["targets_hit"]["T1"]:
            position["targets_hit"]["T1"] = True
            logger.info(f"🎯 [T1] {symbol}: +{pnl_pct:.1f}% (₹{pnl:,.2f})")
            self.certification_scores[symbol] = min(self.certification_scores[symbol] + 1, 100)
            self._save_certification()
            self._record_trade(position, current_premium, pnl, pnl_pct, "TARGET1")
            await self._exit_position(symbol, "T1_HIT")
            return
        
        if pnl_pct >= self.T2 * 100 and not position["targets_hit"]["T2"]:
            position["targets_hit"]["T2"] = True
            logger.info(f"🎯 [T2] {symbol}: +{pnl_pct:.1f}% (₹{pnl:,.2f})")
            self.certification_scores[symbol] = min(self.certification_scores[symbol] + 1, 100)
            self._save_certification()
            self._record_trade(position, current_premium, pnl, pnl_pct, "TARGET2")
            await self._exit_position(symbol, "T2_HIT")
            return
        
        if pnl_pct >= self.T3 * 100 and not position["targets_hit"]["T3"]:
            position["targets_hit"]["T3"] = True
            logger.info(f"🎯 [T3] {symbol}: +{pnl_pct:.1f}% (₹{pnl:,.2f})")
            self.certification_scores[symbol] = min(self.certification_scores[symbol] + 1, 100)
            self._save_certification()
            self._record_trade(position, current_premium, pnl, pnl_pct, "TARGET3")
            await self._exit_position(symbol, "T3_HIT")
            return
        
        # Check stop loss
        if pnl_pct <= -self.stop_loss_pct * 100:
            logger.warning(f"⛔ [STOP LOSS] {symbol}: {pnl_pct:.1f}% (₹{pnl:,.2f})")
            self._record_trade(position, current_premium, pnl, pnl_pct, "STOPPED")
            await self._exit_position(symbol, "STOP_LOSS")
            return
        
        # Time exit after enough cycles
        if position["hold_count"] > 100:
            logger.info(f"⏰ [TIME EXIT] {symbol}: {pnl_pct:.1f}% (₹{pnl:,.2f})")
            self._record_trade(position, current_premium, pnl, pnl_pct, "CLOSED")
            await self._exit_position(symbol, "TIME_EXIT")
    
    def _record_trade(self, position: dict, exit_premium: float, pnl: float, pnl_pct: float, status: str):
        """Record a completed trade."""
        self.trades.append({
            "symbol": position["symbol"],
            "strike": position["strike"],
            "entry_premium": position["entry_premium"],
            "exit_premium": exit_premium,
            "pnl": pnl,
            "pnl_percent": pnl_pct,
            "status": status,
            "exit_reason": status,
            "entry_time": position["entry_time"],
            "exit_time": datetime.now().isoformat(),
            "hold_cycles": position["hold_count"]
        })
    
    async def _exit_position(self, symbol: str, reason: str):
        """Exit a position."""
        if symbol not in self.positions:
            return
        
        position = self.positions.pop(symbol)
        logger.info(f"📤 [EXIT] {symbol}: {reason} | Final P&L: {position['pnl_percent']:+.1f}% (₹{position['pnl']:,.2f})")
        self._save_certification()
    
    async def start(self):
        """Start the engine."""
        self.is_running = True
        logger.info("🚀 Advanced paper trading engine started")
        await self.data_provider.connect()
        
        while self.is_running:
            self.cycle += 1
            await asyncio.sleep(1)
            
            if self.cycle % 20 == 0:
                self._log_status()
            
            if self.certification_scores["NIFTY"] >= 100 and self.certification_scores["SENSEX"] >= 100:
                logger.info("🎉 CERTIFICATION COMPLETE!")
                self.is_running = False
    
    def _log_status(self):
        """Log current status."""
        nifty_score = self.certification_scores["NIFTY"]
        sensex_score = self.certification_scores["SENSEX"]
        
        logger.info("=" * 60)
        logger.info(f"📊 STATUS - Cycle {self.cycle}")
        logger.info(f"   NIFTY: {nifty_score}/100 | SENSEX: {sensex_score}/100")
        logger.info(f"   Open Positions: {len(self.positions)}")
        logger.info(f"   Total Trades: {len(self.trades)}")
        
        # Show recommendations
        for symbol in ["NIFTY", "SENSEX"]:
            if symbol in self.last_recommendation:
                rec = self.last_recommendation[symbol]
                logger.info(f"   💡 {symbol} Recommendation: Strike {rec['strike']} @ ₹{rec['premium']:.2f}")
        
        # Show active positions
        for symbol, pos in self.positions.items():
            if pos["status"] == "OPEN":
                logger.info(f"   📈 {symbol}: Strike {pos['strike']} | Premium ₹{pos['current_premium']:.2f} | P&L {pos['pnl_percent']:+.1f}%")
        
        logger.info("=" * 60)
    
    def _load_certification(self):
        """Load certification state."""
        cert_file = Path("data/certification.json")
        if cert_file.exists():
            try:
                with open(cert_file, "r") as f:
                    data = json.load(f)
                    self.certification_scores = data.get("scores", {"NIFTY": 0, "SENSEX": 0})
                    self.trades = data.get("trades", [])
                    self.entry_count = len(self.trades)
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
                    "trades": self.trades,
                    "positions": {
                        k: v for k, v in self.positions.items() if v.get("status") == "OPEN"
                    },
                    "updated": datetime.now().isoformat(),
                    "cycle": self.cycle,
                    "entry_count": self.entry_count,
                    "last_recommendation": self.last_recommendation
                }, f, indent=2)
        except:
            pass
    
    def get_active_trades(self):
        """Get active trades."""
        return self.positions
    
    def get_stats(self):
        """Get trading stats."""
        return {
            "nifty_score": self.certification_scores["NIFTY"],
            "sensex_score": self.certification_scores["SENSEX"],
            "total_trades": len(self.trades),
            "open_positions": len(self.positions),
            "cycle": self.cycle,
            "positions": self.positions,
            "recommendations": self.last_recommendation
        }
    
    def stop(self):
        """Stop the engine."""
        self.is_running = False
        self.data_provider.stop()
        self._save_certification()
        logger.info("🛑 Paper trading engine stopped")
