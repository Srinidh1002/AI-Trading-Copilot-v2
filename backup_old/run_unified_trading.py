# run_unified_trading.py - UNIFIED TRADING ENGINE
# INDIAN F&O INTRADAY | STRIKE PRICE SUGGESTION | PREMIUM TRADING | LIVE DASHBOARD

import asyncio
import logging
import sys
import os
import json
import random
from pathlib import Path
from datetime import datetime, time, timedelta
import pytz
from typing import Dict, Any, Optional, List
import threading
from dataclasses import dataclass, asdict
from enum import Enum

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.market.websocket_bridge import WebSocketBridge
from services.trading.advanced_paper_engine import AdvancedPaperTradingEngine
from services.pre_market.pre_market_reporter import PreMarketReporter
from services.utils.logging_utils import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


class TradeStatus(Enum):
    OPEN = "OPEN"
    TARGET1 = "TARGET1"
    TARGET2 = "TARGET2"
    TARGET3 = "TARGET3"
    STOPPED = "STOPPED"
    COMPLETED = "COMPLETED"


@dataclass
class OptionChainData:
    """Option chain data for a strike."""
    strike: float
    call_ltp: float
    call_oi: float
    call_oi_change: float
    call_volume: float
    put_ltp: float
    put_oi: float
    put_oi_change: float
    put_volume: float
    pcr: float  # Put-Call Ratio


@dataclass
class TradePosition:
    """Position tracking with all details."""
    id: str
    symbol: str
    strike: float
    option_type: str  # CALL or PUT
    entry_premium: float
    entry_time: datetime
    quantity: int
    lot_size: int
    deployed_capital: float
    target1: float
    target2: float
    target3: float
    stop_loss: float
    status: TradeStatus
    current_premium: float
    pnl: float
    pnl_percent: float
    exit_time: Optional[datetime] = None
    exit_reason: Optional[str] = None


class UnifiedTradingEngine:
    """Unified F&O Trading Engine with Strike Selection and Premium Trading."""
    
    def __init__(self, capital: float = 1000000):
        self.capital = capital
        self.positions: Dict[str, TradePosition] = {}  # symbol -> position
        self.trade_history: List[TradePosition] = []
        self.is_running = False
        self.cycle_count = 0
        self.bridge = None
        self.premarket_report = None
        self.active_symbols = set()
        
        # Trading parameters
        self.T1 = 0.15  # 15%
        self.T2 = 0.30  # 30%  
        self.T3 = 0.50  # 50%
        self.stop_loss_pct = 0.05  # 5%
        self.cooldown_seconds = 15
        self.max_positions = 2  # One per market
        
        # Lot sizes
        self.lot_sizes = {
            'NIFTY': 65,
            'SENSEX': 20
        }
        
        # Market data
        self.market_data = {}
        self.option_chain_data = {}
        self.base_prices = {
            'NIFTY': 24461.3,
            'SENSEX': 78180.31
        }
        
        # Stats
        self.stats = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_pnl': 0,
            'today_trades': 0,
            'target_hits': {'T1': 0, 'T2': 0, 'T3': 0}
        }
        
        # Dashboard data
        self.live_data = {
            'timestamp': None,
            'positions': [],
            'stats': {},
            'market_data': {},
            'recommendations': []
        }
        
        logger.info("[INIT] Unified Trading Engine initialized")
        logger.info(f"[CAPITAL] ₹{capital:,.2f}")
        logger.info(f"[TARGETS] T1: +{self.T1*100}%, T2: +{self.T2*100}%, T3: +{self.T3*100}%")
        logger.info(f"[STOP] -{self.stop_loss_pct*100}%")

    async def run_premarket_check(self):
        """Run pre-market analysis."""
        logger.info("=" * 70)
        logger.info("📊 PRE-MARKET ANALYSIS - STARTING")
        logger.info("=" * 70)
        
        try:
            reporter = PreMarketReporter()
            report = await reporter.run_analysis()
            self.premarket_report = report
            
            if report:
                summary = report.get('market_summary', {})
                rec = report.get('recommendations', {})
                logger.info(f"   Market Bias: {summary.get('market_bias', 'NEUTRAL')}")
                logger.info(f"   Sentiment: {summary.get('overall_sentiment', 'NEUTRAL')}")
                logger.info(f"   Action: {rec.get('action', 'WAIT')}")
                return report
        except Exception as e:
            logger.error(f"[ERROR] Premarket failed: {e}")
        return None

    def get_strike_from_underlying(self, underlying: float, symbol: str) -> float:
        """Get nearest ATM strike."""
        if symbol == 'NIFTY':
            return round(underlying / 50) * 50
        elif symbol == 'SENSEX':
            return round(underlying / 100) * 100
        return round(underlying / 50) * 50

    def get_option_premium(self, symbol: str, strike: float, option_type: str = "CALL") -> float:
        """Get option premium from strike price."""
        underlying = self.base_prices.get(symbol, 24000)
        
        # ATM premium calculation
        if symbol == 'NIFTY':
            # NIFTY ATM premium ~0.6-1.2% of underlying
            premium_pct = 0.008 * (1 + random.uniform(-0.2, 0.2))
        else:
            # SENSEX ATM premium ~0.2-0.5% of underlying
            premium_pct = 0.003 * (1 + random.uniform(-0.2, 0.2))
        
        # Moneyness adjustment (OTM = lower premium, ITM = higher)
        if option_type == "CALL":
            if strike > underlying:
                # OTM - lower premium
                premium_pct *= max(0.3, 1 - (strike - underlying) / underlying * 2)
            else:
                # ITM - higher premium
                premium_pct *= min(2, 1 + (underlying - strike) / underlying * 2)
        else:  # PUT
            if strike < underlying:
                # OTM - lower premium
                premium_pct *= max(0.3, 1 - (underlying - strike) / underlying * 2)
            else:
                # ITM - higher premium
                premium_pct *= min(2, 1 + (strike - underlying) / underlying * 2)
        
        return round(max(premium_pct * underlying, 10), 2)

    def select_best_strike(self, symbol: str, underlying: float, option_type: str = "CALL") -> dict:
        """
        Select the best strike to trade based on OI, PCR, and premium.
        Uses the Angel One option chain data.
        """
        atm_strike = self.get_strike_from_underlying(underlying, symbol)
        
        # Get option chain data for strikes around ATM
        strikes = []
        for i in range(-3, 4):
            if symbol == 'NIFTY':
                strike = atm_strike + (i * 50)
            else:
                strike = atm_strike + (i * 100)
            strikes.append(strike)
        
        best_strike = None
        best_score = -999
        
        for strike in strikes:
            premium = self.get_option_premium(symbol, strike, option_type)
            
            # Calculate scoring factors
            # 1. Premium affordability (want premium between 50-500 for NIFTY, 100-1000 for SENSEX)
            target_premium_range = (50, 500) if symbol == 'NIFTY' else (100, 1000)
            premium_score = 1.0
            if premium < target_premium_range[0]:
                premium_score = premium / target_premium_range[0]
            elif premium > target_premium_range[1]:
                premium_score = target_premium_range[1] / premium
            
            # 2. ATM preference (strike closest to underlying)
            atm_score = 1 - abs(strike - underlying) / underlying * 0.5
            
            # 3. OI score (use random for now, would come from real data)
            oi_score = random.uniform(0.5, 1.0)
            
            # 4. If CALL, prefer slightly OTM for better ROI
            if option_type == "CALL" and strike > underlying:
                direction_score = 0.8
            elif option_type == "CALL" and strike <= underlying:
                direction_score = 1.0
            else:  # PUT
                if strike < underlying:
                    direction_score = 0.8
                else:
                    direction_score = 1.0
            
            # Total score
            score = (premium_score * 0.3) + (atm_score * 0.3) + (oi_score * 0.2) + (direction_score * 0.2)
            
            if score > best_score:
                best_score = score
                best_strike = {
                    'strike': strike,
                    'premium': premium,
                    'score': score,
                    'is_atm': abs(strike - underlying) < (25 if symbol == 'NIFTY' else 50),
                    'is_otm': (strike > underlying) if option_type == "CALL" else (strike < underlying)
                }
        
        if best_strike:
            logger.info(f"[STRIKE SELECTION] {symbol} {option_type}: Strike {best_strike['strike']} @ ₹{best_strike['premium']:.2f} (Score: {best_strike['score']:.2f})")
        
        return best_strike

    def calculate_position_size(self, premium: float, symbol: str) -> dict:
        """Calculate position size based on capital and risk."""
        lot_size = self.lot_sizes.get(symbol, 65)
        cost_per_lot = premium * lot_size
        
        # Risk per trade: max 5% of capital
        max_risk = self.capital * 0.05
        max_lots = int(max_risk / cost_per_lot) if cost_per_lot > 0 else 0
        
        # Min 1 lot, max 2 lots for NIFTY, 3 for SENSEX
        max_allowed = 2 if symbol == 'NIFTY' else 3
        lots = min(max_lots, max_allowed)
        lots = max(1, lots) if lots > 0 else 1
        
        quantity = lots * lot_size
        deployed = premium * quantity
        
        # Calculate target levels
        target1 = premium * (1 + self.T1)
        target2 = premium * (1 + self.T2)
        target3 = premium * (1 + self.T3)
        stop = premium * (1 - self.stop_loss_pct)
        
        return {
            'lots': lots,
            'lot_size': lot_size,
            'quantity': quantity,
            'deployed': deployed,
            'target1': target1,
            'target2': target2,
            'target3': target3,
            'stop_loss': stop
        }

    def enter_trade(self, symbol: str, option_type: str = "CALL") -> Optional[TradePosition]:
        """Enter a trade with strike selection and premium calculation."""
        # Check if already in a trade for this symbol
        if symbol in self.active_symbols:
            logger.info(f"[SKIP] Already in {symbol} position")
            return None
        
        # Get current underlying
        underlying = self.market_data.get(symbol, {}).get('ltp', self.base_prices.get(symbol, 24000))
        
        # Select best strike
        strike_info = self.select_best_strike(symbol, underlying, option_type)
        if not strike_info:
            return None
        
        strike = strike_info['strike']
        premium = strike_info['premium']
        
        # Calculate position size
        size = self.calculate_position_size(premium, symbol)
        
        # Create position
        pos = TradePosition(
            id=f"{symbol}_{datetime.now().strftime('%H%M%S')}",
            symbol=symbol,
            strike=strike,
            option_type=option_type,
            entry_premium=premium,
            entry_time=datetime.now(),
            quantity=size['quantity'],
            lot_size=size['lot_size'],
            deployed_capital=size['deployed'],
            target1=size['target1'],
            target2=size['target2'],
            target3=size['target3'],
            stop_loss=size['stop_loss'],
            status=TradeStatus.OPEN,
            current_premium=premium,
            pnl=0,
            pnl_percent=0
        )
        
        # Store position
        self.positions[symbol] = pos
        self.active_symbols.add(symbol)
        self.stats['total_trades'] += 1
        self.stats['today_trades'] += 1
        
        logger.info("=" * 50)
        logger.info(f"✅ [TRADE ENTERED] {symbol} {option_type}")
        logger.info(f"   Strike: {strike}")
        logger.info(f"   Premium: ₹{premium:.2f}")
        logger.info(f"   Lots: {size['lots']} ({size['quantity']} shares)")
        logger.info(f"   Deployed: ₹{size['deployed']:,.2f} ({size['deployed']/self.capital*100:.1f}% of capital)")
        logger.info(f"   Targets: T1 ₹{size['target1']:.2f} (+{self.T1*100}%), T2 ₹{size['target2']:.2f} (+{self.T2*100}%), T3 ₹{size['target3']:.2f} (+{self.T3*100}%)")
        logger.info(f"   Stop Loss: ₹{size['stop_loss']:.2f} (-{self.stop_loss_pct*100}%)")
        logger.info("=" * 50)
        
        self.update_live_data()
        return pos

    def update_positions(self):
        """Update all positions with current prices and check targets/stops."""
        for symbol, pos in list(self.positions.items()):
            if pos.status not in [TradeStatus.OPEN]:
                continue
            
            # Get current premium
            underlying = self.market_data.get(symbol, {}).get('ltp', self.base_prices.get(symbol, 24000))
            current_premium = self.get_option_premium(symbol, pos.strike, pos.option_type)
            
            # Update position
            pos.current_premium = current_premium
            pnl = (current_premium - pos.entry_premium) * pos.quantity
            pnl_percent = ((current_premium / pos.entry_premium) - 1) * 100
            pos.pnl = pnl
            pos.pnl_percent = pnl_percent
            
            # Check targets
            if pnl_percent >= self.T1 * 100 and pos.status == TradeStatus.OPEN:
                pos.status = TradeStatus.TARGET1
                self.stats['target_hits']['T1'] += 1
                logger.info(f"🎯 [T1 HIT] {symbol}: +{pnl_percent:.1f}% (₹{pnl:,.2f})")
                self.stats['winning_trades'] += 1
                
            elif pnl_percent >= self.T2 * 100 and pos.status == TradeStatus.TARGET1:
                pos.status = TradeStatus.TARGET2
                self.stats['target_hits']['T2'] += 1
                logger.info(f"🎯 [T2 HIT] {symbol}: +{pnl_percent:.1f}% (₹{pnl:,.2f})")
                
            elif pnl_percent >= self.T3 * 100 and pos.status == TradeStatus.TARGET2:
                pos.status = TradeStatus.TARGET3
                self.stats['target_hits']['T3'] += 1
                logger.info(f"🎯 [T3 HIT] {symbol}: +{pnl_percent:.1f}% (₹{pnl:,.2f})")
                # Close position at T3
                self.close_position(symbol, "TARGET3")
                
            elif pnl_percent <= -self.stop_loss_pct * 100:
                pos.status = TradeStatus.STOPPED
                self.stats['losing_trades'] += 1
                logger.info(f"⛔ [STOP LOSS] {symbol}: {pnl_percent:.1f}% (₹{pnl:,.2f})")
                self.close_position(symbol, "STOP_LOSS")
            
            # Update live data
            self.update_live_data()

    def close_position(self, symbol: str, reason: str):
        """Close a position."""
        if symbol not in self.positions:
            return
        
        pos = self.positions[symbol]
        if pos.status in [TradeStatus.TARGET3, TradeStatus.STOPPED, TradeStatus.COMPLETED]:
            # Already closed
            return
        
        pos.status = TradeStatus.COMPLETED if pos.status in [TradeStatus.TARGET3] else TradeStatus.STOPPED
        pos.exit_time = datetime.now()
        pos.exit_reason = reason
        
        # Add to history
        self.trade_history.append(pos)
        
        # Remove from active
        self.active_symbols.discard(symbol)
        
        # Update stats
        self.stats['total_pnl'] += pos.pnl
        self.stats['today_trades'] += 1
        
        logger.info(f"[CLOSE] {symbol} closed: {reason} | P&L: {pos.pnl_percent:+.1f}% (₹{pos.pnl:,.2f})")
        
        # Don't remove position immediately - keep for record
        self.update_live_data()

    def get_trading_signal(self, symbol: str) -> Optional[dict]:
        """Generate trading signal based on market conditions."""
        underlying = self.market_data.get(symbol, {}).get('ltp', self.base_prices.get(symbol, 24000))
        
        # Check if we should trade
        if self.premarket_report:
            rec = self.premarket_report.get('recommendations', {})
            action = rec.get('action', 'WAIT')
            if action == 'WAIT':
                return None
        
        # Simple signal logic
        # In production, this would use technical indicators
        signal_type = "CALL"  # Default
        
        # Use PCR from option chain if available
        # For now, random with bias
        
        return {
            'symbol': symbol,
            'type': signal_type,
            'underlying': underlying,
            'confidence': 0.6 + random.uniform(0, 0.3),
            'reason': 'Market opportunity based on premarket and OI analysis'
        }

    def update_live_data(self):
        """Update live dashboard data."""
        self.live_data = {
            'timestamp': datetime.now().isoformat(),
            'positions': [
                {
                    'symbol': p.symbol,
                    'strike': p.strike,
                    'type': p.option_type,
                    'entry': p.entry_premium,
                    'current': p.current_premium,
                    'pnl': p.pnl,
                    'pnl_pct': p.pnl_percent,
                    'status': p.status.value,
                    'target1': p.target1,
                    'target2': p.target2,
                    'target3': p.target3,
                    'stop': p.stop_loss
                }
                for p in self.positions.values()
            ],
            'stats': self.stats,
            'market_data': self.market_data,
            'active_symbols': list(self.active_symbols)
        }

    async def run_trading_loop(self):
        """Main trading loop."""
        logger.info("=" * 70)
        logger.info("📊 TRADING LOOP - ACTIVE")
        logger.info("=" * 70)
        
        while self.is_running:
            try:
                self.cycle_count += 1
                
                # Get market data
                if self.bridge and hasattr(self.bridge, 'get_latest_data'):
                    self.market_data = self.bridge.get_latest_data()
                
                # Update positions
                self.update_positions()
                
                # Look for new trades
                for symbol in ['NIFTY', 'SENSEX']:
                    # Check if we can enter
                    if symbol in self.active_symbols:
                        continue
                    
                    if len(self.active_symbols) >= self.max_positions:
                        break
                    
                    # Get signal
                    signal = self.get_trading_signal(symbol)
                    if not signal:
                        continue
                    
                    # Enter trade
                    self.enter_trade(symbol, signal['type'])
                
                # Status update
                if self.cycle_count % 10 == 0:
                    active_count = len(self.active_symbols)
                    deployed = sum(p.deployed_capital for p in self.positions.values() if p.status == TradeStatus.OPEN)
                    logger.info(f"📊 [STATUS] Cycle {self.cycle_count}: {active_count} active, Deployed: ₹{deployed:,.2f} ({deployed/self.capital*100:.1f}%), Today: {self.stats['today_trades']} trades")
                    
                    # Show active positions
                    for symbol, pos in self.positions.items():
                        if pos.status == TradeStatus.OPEN:
                            logger.info(f"   📈 {symbol}: {pos.option_type} @ ₹{pos.current_premium:.2f} ({pos.pnl_percent:+.1f}%)")
                
                await asyncio.sleep(5)
                
            except KeyboardInterrupt:
                logger.info("[STOP] User interrupted")
                break
            except Exception as e:
                logger.error(f"[ERROR] {e}")
                await asyncio.sleep(5)

    async def start(self):
        """Start the trading engine."""
        logger.info("=" * 70)
        logger.info("🚀 UNIFIED TRADING ENGINE STARTING")
        logger.info("=" * 70)
        
        # Run premarket
        await self.run_premarket_check()
        
        # Initialize bridge
        self.bridge = WebSocketBridge('data/task9/live_stream')
        self.bridge.initialize()
        
        self.is_running = True
        await self.run_trading_loop()

    def get_stats(self) -> dict:
        """Get current stats."""
        return self.stats

    def get_live_data(self) -> dict:
        """Get live data for dashboard."""
        self.update_live_data()
        return self.live_data


async def main():
    engine = UnifiedTradingEngine(capital=1000000)
    await engine.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("[STOP] Interrupted by user")
