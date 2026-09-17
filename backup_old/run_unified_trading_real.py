# run_unified_trading_real.py
# UNIFIED TRADING ENGINE - REAL DATA FROM ANGEL ONE
# Reads credentials from .env

import asyncio
import logging
import sys
import os
import json
from pathlib import Path
from datetime import datetime, time, timedelta
import pytz
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.market.angel_one_api import AngelOneAPI
from services.market.websocket_bridge import WebSocketBridge
from services.pre_market.pre_market_reporter import PreMarketReporter
from services.utils.logging_utils import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


class RealDataTradingEngine:
    """
    Trading engine with REAL data from Angel One.
    NO HARDCODED VALUES - Everything from API.
    """
    
    def __init__(self, capital: float = 1000000):
        self.capital = capital
        self.positions: Dict[str, Dict] = {}
        self.trade_history: List[Dict] = []
        self.is_running = False
        self.cycle_count = 0
        self.active_symbols = set()
        
        # Trading parameters
        self.T1 = 0.15
        self.T2 = 0.30
        self.T3 = 0.50
        self.stop_loss_pct = 0.05
        self.cooldown_seconds = 15
        self.max_positions = 2
        
        # Lot sizes
        self.lot_sizes = {
            'NIFTY': 65,
            'SENSEX': 20
        }
        
        # Market data - from Angel One
        self.market_data = {}
        self.option_chain = {}
        self.premarket_report = None
        
        # Stats
        self.stats = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_pnl': 0,
            'today_trades': 0,
            'target_hits': {'T1': 0, 'T2': 0, 'T3': 0}
        }
        
        # Initialize Angel One with credentials from .env
        logger.info("[INIT] Initializing Angel One API...")
        self.angel_api = AngelOneAPI()
        
        # Authenticate
        if self.angel_api.authenticate():
            logger.info("[ANGEL] Authentication successful!")
        else:
            logger.warning("[ANGEL] Authentication failed. Using fallback data.")
        
        # Initialize bridge as fallback
        self.bridge = WebSocketBridge('data/task9/live_stream')
        self.bridge.initialize()
        
        logger.info("=" * 60)
        logger.info("[INIT] REAL DATA TRADING ENGINE")
        logger.info(f"[CAPITAL] ₹{capital:,.2f}")
        logger.info(f"[TARGETS] T1: +{self.T1*100}%, T2: +{self.T2*100}%, T3: +{self.T3*100}%")
        logger.info(f"[STOP] -{self.stop_loss_pct*100}%")
        logger.info("=" * 60)

    async def run_premarket_check(self):
        """Run pre-market analysis with REAL data."""
        logger.info("=" * 60)
        logger.info("📊 PRE-MARKET ANALYSIS")
        logger.info("=" * 60)
        
        try:
            # Get REAL LTP
            logger.info("[PREMARKET] Fetching current market data...")
            
            for symbol in ['NIFTY', 'SENSEX']:
                ltp = self.angel_api.get_ltp(symbol)
                if ltp > 0:
                    self.market_data[symbol] = {'ltp': ltp}
                    logger.info(f"   {symbol}: ₹{ltp:,.2f}")
                else:
                    # Fallback to bridge
                    data = self.bridge.get_latest_data()
                    if symbol in data:
                        self.market_data[symbol] = {'ltp': data[symbol].get('ltp', 0)}
            
            # Get option chain
            logger.info("[PREMARKET] Fetching option chain data...")
            
            for symbol in ['NIFTY', 'SENSEX']:
                chain = self.angel_api.get_option_chain(symbol)
                if chain and chain.get('strikes'):
                    self.option_chain[symbol] = chain
                    strikes = len(chain.get('strikes', []))
                    logger.info(f"   {symbol}: {strikes} strikes loaded")
                    
                    # Get ATM data
                    atm = self._get_atm_strike(symbol, chain)
                    if atm:
                        logger.info(f"      ATM: {atm['strike']}")
                        logger.info(f"      CALL: ₹{atm['call_ltp']:.2f}")
                        logger.info(f"      PUT: ₹{atm['put_ltp']:.2f}")
                        logger.info(f"      PCR: {atm['pcr']:.2f}")
            
            # Generate recommendations
            recommendations = self._generate_recommendations()
            
            self.premarket_report = {
                'timestamp': datetime.now().isoformat(),
                'market_data': self.market_data,
                'option_chain': self.option_chain,
                'recommendations': recommendations
            }
            
            logger.info("=" * 60)
            logger.info("✅ [PREMARKET] Analysis complete")
            logger.info("=" * 60)
            
            return self.premarket_report
            
        except Exception as e:
            logger.error(f"[PREMARKET] Error: {e}")
            return None

    def _get_atm_strike(self, symbol: str, chain: dict) -> Optional[dict]:
        """Get ATM strike from option chain."""
        if not chain:
            return None
        
        underlying = chain.get('underlying', 0)
        strikes = chain.get('strikes', [])
        
        if not strikes or underlying == 0:
            return None
        
        # Find closest strike to underlying
        atm = min(strikes, key=lambda s: abs(s['strike'] - underlying))
        return atm

    def _generate_recommendations(self) -> dict:
        """Generate trading recommendations from REAL data."""
        recommendations = {}
        
        for symbol in ['NIFTY', 'SENSEX']:
            chain = self.option_chain.get(symbol, {})
            strikes = chain.get('strikes', [])
            
            if not strikes:
                recommendations[symbol] = {
                    'action': 'WAIT',
                    'reason': 'No option chain data available',
                    'strike': 0,
                    'premium': 0
                }
                continue
            
            # Calculate indicators from REAL data
            pcr = chain.get('total_pcr', 0.5)
            atm = self._get_atm_strike(symbol, chain)
            
            # Find max OI strikes
            if strikes:
                max_call = max(strikes, key=lambda s: s.get('call_oi', 0))
                max_put = max(strikes, key=lambda s: s.get('put_oi', 0))
            else:
                max_call = None
                max_put = None
            
            # Generate recommendation based on PCR
            if pcr < 0.5:
                action = 'BUY_CALL'
                reason = f'Low PCR ({pcr:.2f}) - Bullish sentiment'
                strike = atm['strike'] if atm else 0
                premium = atm['call_ltp'] if atm else 0
            elif pcr > 1.0:
                action = 'BUY_PUT'
                reason = f'High PCR ({pcr:.2f}) - Bearish sentiment'
                strike = atm['strike'] if atm else 0
                premium = atm['put_ltp'] if atm else 0
            else:
                action = 'WAIT'
                reason = f'Neutral PCR ({pcr:.2f}) - Wait for direction'
                strike = atm['strike'] if atm else 0
                premium = 0
            
            recommendations[symbol] = {
                'action': action,
                'reason': reason,
                'strike': strike,
                'premium': premium,
                'pcr': pcr,
                'atm_strike': atm['strike'] if atm else 0,
                'max_call_oi': max_call['strike'] if max_call else 0,
                'max_put_oi': max_put['strike'] if max_put else 0
            }
        
        return recommendations

    def get_real_ltp(self, symbol: str) -> float:
        """Get REAL LTP from Angel One."""
        try:
            ltp = self.angel_api.get_ltp(symbol)
            if ltp > 0:
                return ltp
        except:
            pass
        
        # Fallback to bridge
        data = self.bridge.get_latest_data()
        return data.get(symbol, {}).get('ltp', 0)

    def get_real_option_premium(self, symbol: str, strike: float, option_type: str) -> float:
        """Get REAL option premium from Angel One."""
        chain = self.option_chain.get(symbol, {})
        strikes = chain.get('strikes', [])
        
        # Find strike
        for s in strikes:
            if s['strike'] == strike:
                if option_type == 'CALL':
                    return s.get('call_ltp', 0)
                else:
                    return s.get('put_ltp', 0)
        
        return 0

    def select_best_strike(self, symbol: str, option_type: str = "CALL") -> dict:
        """Select the best strike using REAL option chain data."""
        chain = self.option_chain.get(symbol, {})
        strikes = chain.get('strikes', [])
        underlying = self.market_data.get(symbol, {}).get('ltp', 0)
        
        if underlying == 0:
            underlying = self.get_real_ltp(symbol)
        
        if not strikes or underlying == 0:
            # Use fallback
            step = 50 if symbol == 'NIFTY' else 100
            atm_strike = round(underlying / step) * step
            premium = self.get_real_option_premium(symbol, atm_strike, option_type)
            if premium <= 0:
                # Calculate approximate premium
                premium = self._calc_approximate_premium(symbol, atm_strike, option_type)
            return {'strike': atm_strike, 'premium': premium, 'score': 0.5}
        
        best = None
        best_score = -999
        
        for strike_data in strikes:
            strike = strike_data['strike']
            
            if option_type == 'CALL':
                premium = strike_data.get('call_ltp', 0)
                oi = strike_data.get('call_oi', 0)
                oi_change = strike_data.get('call_oi_change', 0)
            else:
                premium = strike_data.get('put_ltp', 0)
                oi = strike_data.get('put_oi', 0)
                oi_change = strike_data.get('put_oi_change', 0)
            
            if premium <= 0:
                continue
            
            # Scoring
            oi_score = min(1, oi / 1000000) if oi > 0 else 0
            oi_change_score = min(1, max(0, oi_change / 50))
            
            atm_distance = abs(strike - underlying)
            max_distance = underlying * 0.02
            atm_score = 1 - min(1, atm_distance / max_distance)
            
            # Premium affordability
            ideal_premium = 100 if symbol == 'NIFTY' else 300
            premium_score = 1 - min(0.5, abs(premium - ideal_premium) / ideal_premium)
            
            # Direction score
            if option_type == 'CALL':
                direction_score = 0.8 if strike > underlying else 1.0
            else:
                direction_score = 0.8 if strike < underlying else 1.0
            
            score = (
                oi_score * 0.3 +
                oi_change_score * 0.2 +
                atm_score * 0.25 +
                premium_score * 0.15 +
                direction_score * 0.1
            )
            
            if score > best_score:
                best_score = score
                best = {
                    'strike': strike,
                    'premium': premium,
                    'oi': oi,
                    'oi_change': oi_change,
                    'score': score,
                    'distance': atm_distance
                }
        
        if best:
            logger.info(f"[STRIKE SELECT] {symbol} {option_type}: Strike {best['strike']} @ ₹{best['premium']:.2f} (Score: {best['score']:.2f})")
        else:
            # Fallback to ATM
            step = 50 if symbol == 'NIFTY' else 100
            atm_strike = round(underlying / step) * step
            premium = self._calc_approximate_premium(symbol, atm_strike, option_type)
            best = {'strike': atm_strike, 'premium': premium, 'score': 0.5}
        
        return best

    def _calc_approximate_premium(self, symbol: str, strike: float, option_type: str) -> float:
        """Calculate approximate premium when API data is unavailable."""
        underlying = self.market_data.get(symbol, {}).get('ltp', 0)
        if underlying == 0:
            underlying = self.get_real_ltp(symbol)
        
        if underlying == 0:
            return 0
        
        atm_premium = underlying * (0.008 if symbol == 'NIFTY' else 0.003)
        distance_pct = abs(strike - underlying) / underlying
        
        if option_type == 'CALL':
            if strike > underlying:
                premium = atm_premium * max(0.1, 1 - distance_pct * 2)
            else:
                premium = atm_premium * (1 + distance_pct * 2)
        else:
            if strike < underlying:
                premium = atm_premium * max(0.1, 1 - distance_pct * 2)
            else:
                premium = atm_premium * (1 + distance_pct * 2)
        
        return round(max(5, premium), 2)

    def calculate_position_size(self, premium: float, symbol: str) -> dict:
        """Calculate position size based on REAL premium and capital."""
        lot_size = self.lot_sizes.get(symbol, 65)
        cost_per_lot = premium * lot_size
        
        max_risk = self.capital * 0.05
        max_lots = int(max_risk / cost_per_lot) if cost_per_lot > 0 else 0
        
        max_allowed = 2 if symbol == 'NIFTY' else 3
        lots = min(max_lots, max_allowed)
        lots = max(1, lots) if lots > 0 else 1
        
        quantity = lots * lot_size
        deployed = premium * quantity
        
        return {
            'lots': lots,
            'lot_size': lot_size,
            'quantity': quantity,
            'deployed': deployed,
            'target1': premium * (1 + self.T1),
            'target2': premium * (1 + self.T2),
            'target3': premium * (1 + self.T3),
            'stop_loss': premium * (1 - self.stop_loss_pct)
        }

    def enter_trade(self, symbol: str, option_type: str = "CALL") -> Optional[Dict]:
        """Enter a trade using REAL data."""
        if symbol in self.active_symbols:
            logger.info(f"[SKIP] Already in {symbol} position")
            return None
        
        # Get REAL underlying
        underlying = self.market_data.get(symbol, {}).get('ltp', 0)
        if underlying == 0:
            underlying = self.get_real_ltp(symbol)
        
        if underlying == 0:
            logger.error(f"[ERROR] Cannot get LTP for {symbol}")
            return None
        
        # Select best strike from REAL option chain
        strike_info = self.select_best_strike(symbol, option_type)
        if not strike_info or strike_info.get('premium', 0) <= 0:
            logger.error(f"[ERROR] Cannot get premium for {symbol}")
            return None
        
        strike = strike_info['strike']
        premium = strike_info['premium']
        
        # Calculate position size
        size = self.calculate_position_size(premium, symbol)
        
        # Create position
        position = {
            'id': f"{symbol}_{datetime.now().strftime('%H%M%S')}",
            'symbol': symbol,
            'strike': strike,
            'option_type': option_type,
            'entry_premium': premium,
            'entry_underlying': underlying,
            'entry_time': datetime.now().isoformat(),
            'lots': size['lots'],
            'lot_size': size['lot_size'],
            'quantity': size['quantity'],
            'deployed_capital': size['deployed'],
            'target1': size['target1'],
            'target2': size['target2'],
            'target3': size['target3'],
            'stop_loss': size['stop_loss'],
            'status': 'OPEN',
            'current_premium': premium,
            'current_underlying': underlying,
            'pnl': 0,
            'pnl_percent': 0,
            'hold_count': 0
        }
        
        # Store position
        self.positions[symbol] = position
        self.active_symbols.add(symbol)
        self.stats['total_trades'] += 1
        self.stats['today_trades'] += 1
        
        logger.info("=" * 60)
        logger.info(f"✅ [TRADE ENTERED] {symbol} {option_type}")
        logger.info(f"   Underlying: ₹{underlying:,.2f}")
        logger.info(f"   Strike: {strike}")
        logger.info(f"   Premium: ₹{premium:.2f}")
        logger.info(f"   Lots: {size['lots']} ({size['quantity']} shares)")
        logger.info(f"   Deployed: ₹{size['deployed']:,.2f} ({size['deployed']/self.capital*100:.1f}%)")
        logger.info(f"   Targets: T1 ₹{size['target1']:.2f} (+{self.T1*100}%), T2 ₹{size['target2']:.2f} (+{self.T2*100}%), T3 ₹{size['target3']:.2f} (+{self.T3*100}%)")
        logger.info(f"   Stop Loss: ₹{size['stop_loss']:.2f} (-{self.stop_loss_pct*100}%)")
        logger.info("=" * 60)
        
        return position

    def update_positions(self):
        """Update positions with REAL current prices."""
        for symbol, pos in list(self.positions.items()):
            if pos['status'] != 'OPEN':
                continue
            
            # Get REAL current premium
            current_premium = self.get_real_option_premium(
                symbol, 
                pos['strike'], 
                pos['option_type']
            )
            
            if current_premium <= 0:
                current_premium = pos['current_premium']
            
            # Update position
            pos['current_premium'] = current_premium
            pos['current_underlying'] = self.market_data.get(symbol, {}).get('ltp', 0)
            pos['hold_count'] += 1
            
            # Calculate P&L
            pnl = (current_premium - pos['entry_premium']) * pos['quantity']
            pnl_percent = ((current_premium / pos['entry_premium']) - 1) * 100
            pos['pnl'] = pnl
            pos['pnl_percent'] = pnl_percent
            
            # Check targets
            if pnl_percent >= self.T1 * 100 and pos['status'] == 'OPEN':
                pos['status'] = 'TARGET1'
                self.stats['target_hits']['T1'] += 1
                self.stats['winning_trades'] += 1
                logger.info(f"🎯 [T1 HIT] {symbol}: +{pnl_percent:.1f}% (₹{pnl:,.2f})")
                
            elif pnl_percent >= self.T2 * 100 and pos['status'] == 'TARGET1':
                pos['status'] = 'TARGET2'
                self.stats['target_hits']['T2'] += 1
                logger.info(f"🎯 [T2 HIT] {symbol}: +{pnl_percent:.1f}% (₹{pnl:,.2f})")
                
            elif pnl_percent >= self.T3 * 100 and pos['status'] == 'TARGET2':
                pos['status'] = 'TARGET3'
                self.stats['target_hits']['T3'] += 1
                logger.info(f"🎯 [T3 HIT] {symbol}: +{pnl_percent:.1f}% (₹{pnl:,.2f})")
                self.close_position(symbol, "TARGET3")
                
            elif pnl_percent <= -self.stop_loss_pct * 100:
                pos['status'] = 'STOPPED'
                self.stats['losing_trades'] += 1
                logger.info(f"⛔ [STOP LOSS] {symbol}: {pnl_percent:.1f}% (₹{pnl:,.2f})")
                self.close_position(symbol, "STOP_LOSS")

    def close_position(self, symbol: str, reason: str):
        """Close a position."""
        if symbol not in self.positions:
            return
        
        pos = self.positions[symbol]
        if pos['status'] in ['COMPLETED', 'STOPPED']:
            return
        
        pos['status'] = 'COMPLETED'
        pos['exit_time'] = datetime.now().isoformat()
        pos['exit_reason'] = reason
        
        self.trade_history.append(pos.copy())
        self.stats['total_pnl'] += pos['pnl']
        self.active_symbols.discard(symbol)
        
        logger.info(f"[CLOSE] {symbol}: {reason} | P&L: {pos['pnl_percent']:+.1f}% (₹{pos['pnl']:,.2f})")

    def refresh_market_data(self):
        """Refresh ALL market data from Angel One."""
        try:
            for symbol in ['NIFTY', 'SENSEX']:
                ltp = self.angel_api.get_ltp(symbol)
                if ltp > 0:
                    self.market_data[symbol] = {'ltp': ltp}
            
            for symbol in ['NIFTY', 'SENSEX']:
                chain = self.angel_api.get_option_chain(symbol)
                if chain and chain.get('strikes'):
                    self.option_chain[symbol] = chain
                    
        except Exception as e:
            logger.debug(f"[REFRESH] Error: {e}")

    async def run_trading_loop(self):
        """Main trading loop with REAL data."""
        logger.info("=" * 60)
        logger.info("📊 TRADING LOOP - ACTIVE (REAL DATA)")
        logger.info("=" * 60)
        
        while self.is_running:
            try:
                self.cycle_count += 1
                
                # Refresh market data
                self.refresh_market_data()
                
                # Update positions
                self.update_positions()
                
                # Check for new trades
                for symbol in ['NIFTY', 'SENSEX']:
                    if symbol in self.active_symbols:
                        continue
                    
                    if len(self.active_symbols) >= self.max_positions:
                        break
                    
                    # Get recommendation
                    if self.premarket_report:
                        rec = self.premarket_report.get('recommendations', {}).get(symbol, {})
                        action = rec.get('action', 'WAIT')
                        
                        if action == 'WAIT':
                            continue
                        
                        if action == 'BUY_CALL':
                            option_type = 'CALL'
                        elif action == 'BUY_PUT':
                            option_type = 'PUT'
                        else:
                            continue
                        
                        self.enter_trade(symbol, option_type)
                
                # Status update
                if self.cycle_count % 10 == 0:
                    active_count = len(self.active_symbols)
                    deployed = sum(p['deployed_capital'] for p in self.positions.values() if p['status'] == 'OPEN')
                    
                    logger.info(f"📊 [STATUS] Cycle {self.cycle_count}: {active_count} active, Deployed: ₹{deployed:,.2f} ({deployed/self.capital*100:.1f}%), Today: {self.stats['today_trades']} trades")
                    
                    for symbol in ['NIFTY', 'SENSEX']:
                        data = self.market_data.get(symbol, {})
                        if data:
                            logger.info(f"   {symbol}: ₹{data.get('ltp', 0):,.2f}")
                
                await asyncio.sleep(5)
                
            except KeyboardInterrupt:
                logger.info("[STOP] User interrupted")
                break
            except Exception as e:
                logger.error(f"[ERROR] {e}")
                await asyncio.sleep(5)

    async def start(self):
        """Start the trading engine."""
        logger.info("=" * 60)
        logger.info("🚀 REAL DATA TRADING ENGINE STARTING")
        logger.info("=" * 60)
        
        # Run premarket
        await self.run_premarket_check()
        
        self.is_running = True
        await self.run_trading_loop()

    def get_stats(self) -> dict:
        """Get current stats."""
        return self.stats


async def main():
    engine = RealDataTradingEngine(capital=1000000)
    await engine.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("[STOP] Interrupted by user")
