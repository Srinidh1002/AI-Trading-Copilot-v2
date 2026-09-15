# run_advanced_trading.py - COMPLETE SYSTEM: Pre-market → Trading → EOD Report

import asyncio
import logging
import sys
import os
import json
from pathlib import Path
from datetime import datetime, time, timedelta
import pytz

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.market.websocket_bridge import WebSocketBridge
from services.trading.advanced_paper_engine import AdvancedPaperTradingEngine
from services.core.system_controller import SystemController
from services.dashboard.dashboard_manager import DashboardManager
from services.utils.logging_utils import setup_logging
from services.pre_market.pre_market_reporter import PreMarketReporter
from services.reporting.paper_certification_daily_report import PaperCertificationDailyReport

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

class AdvancedTradingSystem:
    """Complete trading system with pre-market, trading, and EOD reporting"""
    
    def __init__(self):
        self.engine = None
        self.bridge = None
        self.controller = SystemController()
        self.dashboard = DashboardManager()
        self.pre_market = PreMarketReporter()
        self.eod_reporter = PaperCertificationDailyReport()
        self.is_running = False
        self.trading_started = False
        self.cycle_count = 0
        self.today_date = datetime.now(pytz.timezone('Asia/Kolkata')).strftime("%Y-%m-%d")
        
    async def wait_until_market_ready(self):
        """Wait until 9:00 AM for pre-market, or 9:15 AM for trading"""
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        
        pre_market_start = time(9, 0)    # 9:00 AM - Pre-market analysis
        market_open = time(9, 15)         # 9:15 AM - Trading starts
        shutdown_time = time(15, 40)      # 3:40 PM - Peaceful shutdown
        eod_report_time = time(15, 45)    # 3:45 PM - EOD Report
        
        current_time = now.time()
        current_date = now.date()
        
        # CASE 1: After shutdown time (3:40 PM to midnight) - Wait until tomorrow 9:00 AM
        if current_time >= shutdown_time:
            tomorrow = current_date + timedelta(days=1)
            # If tomorrow is Saturday or Sunday, wait until Monday
            while tomorrow.weekday() >= 5:  # 5=Saturday, 6=Sunday
                tomorrow += timedelta(days=1)
            target = datetime.combine(tomorrow, pre_market_start, tzinfo=ist)
            wait_seconds = (target - now).total_seconds()
            wait_hours = int(wait_seconds // 3600)
            wait_minutes = int((wait_seconds % 3600) // 60)
            
            logger.info("=" * 70)
            logger.info("📊 AI TRADING COPILOT - SCHEDULER")
            logger.info("=" * 70)
            logger.info(f"📅 Current IST: {now.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"🕐 Market Closed for today (after {shutdown_time.strftime('%I:%M %p')})")
            logger.info(f"⏰ Next session: {target.strftime('%A, %Y-%m-%d at %I:%M %p')}")
            logger.info(f"⌛ Waiting {wait_hours}h {wait_minutes}m...")
            logger.info("=" * 70)
            
            await asyncio.sleep(wait_seconds)
            return "PRE_MARKET"
        
        # CASE 2: Before 9:00 AM - Wait until 9:00 AM for pre-market
        elif current_time < pre_market_start:
            target = datetime.combine(current_date, pre_market_start, tzinfo=ist)
            wait_seconds = (target - now).total_seconds()
            wait_hours = int(wait_seconds // 3600)
            wait_minutes = int((wait_seconds % 3600) // 60)
            
            logger.info("=" * 70)
            logger.info("📊 AI TRADING COPILOT - SCHEDULER")
            logger.info("=" * 70)
            logger.info(f"📅 Current IST: {now.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"⏰ Pre-market starts at 9:00 AM")
            logger.info(f"⌛ Waiting {wait_hours}h {wait_minutes}m...")
            logger.info("=" * 70)
            
            await asyncio.sleep(wait_seconds)
            return "PRE_MARKET"
        
        # CASE 3: Between 9:00 AM and 9:15 AM - Pre-market period
        elif pre_market_start <= current_time < market_open:
            logger.info("=" * 70)
            logger.info("📊 AI TRADING COPILOT - PRE-MARKET PERIOD")
            logger.info("=" * 70)
            logger.info(f"📅 Current IST: {now.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info("📈 Running pre-market analysis...")
            logger.info("⏰ Trading will start at 9:15 AM")
            logger.info("=" * 70)
            return "PRE_MARKET"
        
        # CASE 4: Between 9:15 AM and 3:40 PM - Market is open
        elif market_open <= current_time < shutdown_time:
            logger.info("=" * 70)
            logger.info("📊 AI TRADING COPILOT - TRADING SESSION")
            logger.info("=" * 70)
            logger.info(f"📅 Current IST: {now.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info("✅ Market is OPEN! Starting trading...")
            logger.info("=" * 70)
            return "TRADING"
        
        else:
            return "PRE_MARKET"
    
    async def run_pre_market_analysis(self):
        """Run complete pre-market analysis"""
        logger.info("=" * 70)
        logger.info("📈 PRE-MARKET ANALYSIS - STARTING")
        logger.info("=" * 70)
        
        try:
            # 1. Fetch yesterday's data
            logger.info("📊 Fetching yesterday's market data...")
            yesterday_data = await self.get_yesterday_data()
            
            # 2. Global markets
            logger.info("🌍 Fetching global market data...")
            global_data = await self.pre_market.get_global_markets()
            
            # 3. Economic calendar
            logger.info("📅 Fetching economic calendar...")
            economic_data = await self.pre_market.get_economic_calendar()
            
            # 4. News sentiment
            logger.info("📰 Fetching news sentiment...")
            news_data = await self.pre_market.get_news_sentiment()
            
            # 5. VIX data
            logger.info("📊 Fetching VIX data...")
            vix_data = await self.pre_market.get_vix()
            
            # 6. Generate report
            logger.info("📝 Generating pre-market report...")
            report = await self.pre_market.run_analysis()
            
            if report:
                # Apply market bias to engine
                bias = report.get('market_summary', {}).get('market_bias', 'NEUTRAL')
                sentiment = report.get('market_summary', {}).get('overall_sentiment', 'NEUTRAL')
                volatility = report.get('market_summary', {}).get('volatility_level', 'MEDIUM')
                recommendation = report.get('recommendations', {}).get('action', 'WAIT')
                recommended_market = report.get('recommendations', {}).get('market', 'NIFTY')
                
                if self.engine:
                    self.engine.market_bias = bias
                    self.engine.regime = bias
                
                # Save report
                report_dir = Path("data/reports/pre_market")
                report_dir.mkdir(parents=True, exist_ok=True)
                report_file = report_dir / f"pre_market_{self.today_date}.json"
                with open(report_file, 'w') as f:
                    json.dump(report, f, indent=2, default=str)
                
                logger.info("=" * 70)
                logger.info("📊 PRE-MARKET SUMMARY")
                logger.info("=" * 70)
                logger.info(f"📈 Market Bias: {bias}")
                logger.info(f"📊 Sentiment: {sentiment}")
                logger.info(f"🌊 Volatility: {volatility}")
                logger.info(f"🎯 Recommendation: {recommendation} on {recommended_market}")
                logger.info(f"📁 Report saved: {report_file}")
                logger.info("=" * 70)
                
                return report
            
            return None
            
        except Exception as e:
            logger.error(f"[ERROR] Pre-market analysis failed: {e}")
            return None
    
    async def get_yesterday_data(self):
        """Fetch yesterday's market data"""
        try:
            ist = pytz.timezone('Asia/Kolkata')
            yesterday = datetime.now(ist) - timedelta(days=1)
            yesterday_date = yesterday.strftime("%Y-%m-%d")
            
            # Check if we have saved data
            data_dir = Path("data/dashboard")
            files = sorted(data_dir.glob(f"dashboard_*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
            
            yesterday_data = {
                'date': yesterday_date,
                'nifty_close': None,
                'sensex_close': None,
                'nifty_change': None,
                'sensex_change': None,
                'summary': 'No data available'
            }
            
            if files:
                with open(files[0], 'r') as f:
                    data = json.load(f)
                    market_data = data.get('market_data', {})
                    nifty = market_data.get('NIFTY', {})
                    sensex = market_data.get('SENSEX', {})
                    
                    yesterday_data['nifty_close'] = nifty.get('ltp')
                    yesterday_data['sensex_close'] = sensex.get('ltp')
                    yesterday_data['nifty_change'] = nifty.get('change_percent')
                    yesterday_data['sensex_change'] = sensex.get('change_percent')
                    
                    if nifty.get('ltp'):
                        yesterday_data['summary'] = f"NIFTY: {nifty.get('ltp'):.2f} ({nifty.get('change_percent', 0):.2f}%), SENSEX: {sensex.get('ltp', 0):.2f} ({sensex.get('change_percent', 0):.2f}%)"
            
            logger.info(f"📊 Yesterday's data ({yesterday_date}): {yesterday_data['summary']}")
            return yesterday_data
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to get yesterday's data: {e}")
            return None
    
    async def start_trading(self):
        """Start the trading engine"""
        logger.info("=" * 70)
        logger.info("🚀 STARTING TRADING ENGINE")
        logger.info("=" * 70)
        
        # Initialize WebSocket Bridge
        self.bridge = WebSocketBridge('data/task9/live_stream')
        self.bridge.initialize()
        logger.info("[BRIDGE] WebSocket Bridge initialized")
        
        # Initialize Engine (uses PREMIUM)
        self.engine = AdvancedPaperTradingEngine(
            bridge=self.bridge,
            capital=1000000,
            max_positions=2
        )
        await self.engine.start()
        logger.info("[ENGINE] Trading Engine started (PREMIUM-based)")
        logger.info(f"[LOT] NIFTY: 65 shares/lot | SENSEX: 20 shares/lot")
        logger.info(f"[TARGETS] T1: +15%, T2: +30%, T3: +50% (on premium)")
        logger.info(f"[STOP] Stop Loss: -5% (on premium)")
        
        self.trading_started = True
        self.is_running = True
        
        # Start dashboard
        try:
            await self.dashboard.start()
            logger.info("[DASHBOARD] Dashboard started")
        except Exception as e:
            logger.warning(f"[DASHBOARD] Could not start dashboard: {e}")
    
    async def run_trading_loop(self):
        """Main trading loop - runs from 9:15 AM to 3:40 PM"""
        logger.info("=" * 70)
        logger.info("📊 TRADING LOOP - ACTIVE")
        logger.info("=" * 70)
        logger.info("⏰ Trading hours: 9:15 AM - 3:40 PM IST")
        logger.info("🎯 Targets: T1=15%, T2=30%, T3=50%")
        logger.info("🛑 Stop Loss: -5%")
        logger.info("=" * 70)
        
        while self.is_running:
            try:
                self.cycle_count += 1
                
                # Check if market is still open
                ist = pytz.timezone('Asia/Kolkata')
                now = datetime.now(ist)
                shutdown_time = time(15, 40)
                
                if now.time() >= shutdown_time:
                    logger.info("[EOD] Market closing time reached (3:40 PM)")
                    break
                
                # Get live data from bridge
                market_data = {}
                if self.bridge and hasattr(self.bridge, 'get_latest_data'):
                    try:
                        market_data = self.bridge.get_latest_data()
                    except Exception as e:
                        logger.debug(f"[BRIDGE] Could not get data: {e}")
                
                # Process NIFTY and SENSEX
                for symbol in ['NIFTY', 'SENSEX']:
                    if symbol in market_data:
                        tick = market_data[symbol]
                        ltp = tick.get('ltp', 0)
                        
                        if ltp <= 0:
                            continue
                        
                        # Get premium (calculated from underlying)
                        premium = self.engine.get_option_premium(symbol, ltp, 'CALL')
                        
                        # Check if we can enter a trade
                        open_positions = [p for p in self.engine.positions if p.get('status') == 'OPEN']
                        if len(open_positions) < self.engine.max_positions:
                            # Analyze signal
                            signal = await self.engine.analyze_signal({
                                'symbol': symbol,
                                'ltp': ltp,
                                'timestamp': datetime.now().isoformat()
                            })
                            
                            if signal and signal.get('signal') == 'TRADE':
                                # Enter position with PREMIUM
                                position = self.engine._enter_option_position(
                                    {'symbol': symbol, 'ltp': ltp},
                                    'CALL',
                                    signal,
                                    {}
                                )
                                if position:
                                    logger.info(f"✅ [TRADE] {symbol} CALL @ ₹{position['entry_price']:.2f} premium")
                                    logger.info(f"💰 [COST] Deployed: ₹{position['deployed_capital']:,.2f} ({position['deployed_capital']/1000000*100:.1f}% of capital)")
                                    logger.info(f"🎯 [TARGETS] T1: ₹{position['target1']:.2f}, T2: ₹{position['target2']:.2f}, T3: ₹{position['target3']:.2f}")
                        
                        # Update positions with current price
                        self.engine.update_positions({'symbol': symbol, 'ltp': ltp})
                
                # Status every 10 cycles
                if self.cycle_count % 10 == 0:
                    stats = self.engine.get_stats()
                    total_deployed = stats['total_deployed']
                    usage = stats['usage_percent']
                    open_pos = stats['open_positions']
                    
                    logger.info(f"📊 [STATUS] Cycle {self.cycle_count}: {open_pos} open, Deployed: ₹{total_deployed:,.2f} ({usage:.1f}%)")
                    
                    # Show position details
                    for pos in stats['positions']:
                        if pos.get('status') == 'OPEN':
                            symbol = pos.get('symbol')
                            entry = pos.get('entry_price', 0)
                            current = pos.get('current_price', entry)
                            pnl_pct = pos.get('pnl_percent', 0)
                            status = pos.get('status', 'OPEN')
                            logger.info(f"   📈 {symbol}: Entry ₹{entry:.2f} → Current ₹{current:.2f} ({pnl_pct:+.1f}%) [{status}]")
                
                # Check for target hits and log them
                for pos in self.engine.positions:
                    if pos.get('status') in ['TARGET1', 'TARGET2', 'TARGET3']:
                        symbol = pos.get('symbol')
                        status = pos.get('status')
                        pnl = pos.get('pnl', 0)
                        logger.info(f"🎯 [TARGET HIT] {symbol} {status}: +{pos.get('pnl_percent', 0):.1f}% (₹{pnl:,.2f})")
                
                # Wait before next cycle
                await asyncio.sleep(3)
                
            except KeyboardInterrupt:
                logger.info("[STOP] Interrupted by user")
                self.is_running = False
                break
            except Exception as e:
                logger.error(f"[ERROR] {e}")
                await asyncio.sleep(5)
    
    async def generate_eod_report(self):
        """Generate End-of-Day report"""
        logger.info("=" * 70)
        logger.info("📊 END-OF-DAY REPORT - GENERATING")
        logger.info("=" * 70)
        
        try:
            # Get engine stats
            stats = self.engine.get_stats() if self.engine else {}
            
            # Build report
            report = {
                'date': self.today_date,
                'timestamp': datetime.now(pytz.timezone('Asia/Kolkata')).isoformat(),
                'total_positions': stats.get('total_positions', 0),
                'open_positions': stats.get('open_positions', 0),
                'total_deployed': stats.get('total_deployed', 0),
                'usage_percent': stats.get('usage_percent', 0),
                'winning_trades': stats.get('winning_trades', 0),
                'losing_trades': stats.get('losing_trades', 0),
                'win_rate': stats.get('win_rate', 0),
                'positions': []
            }
            
            # Add position details
            for pos in stats.get('positions', []):
                report['positions'].append({
                    'symbol': pos.get('symbol'),
                    'option_type': pos.get('option_type'),
                    'entry_price': pos.get('entry_price'),
                    'current_price': pos.get('current_price'),
                    'status': pos.get('status'),
                    'pnl': pos.get('pnl', 0),
                    'pnl_percent': pos.get('pnl_percent', 0),
                    'deployed_capital': pos.get('deployed_capital', 0),
                    'hold_count': pos.get('hold_count', 0)
                })
            
            # Save report
            report_dir = Path("data/reports/eod")
            report_dir.mkdir(parents=True, exist_ok=True)
            report_file = report_dir / f"eod_{self.today_date}.json"
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            
            # Print summary
            logger.info("=" * 70)
            logger.info("📊 EOD REPORT SUMMARY")
            logger.info("=" * 70)
            logger.info(f"📅 Date: {self.today_date}")
            logger.info(f"📈 Total Positions: {report['total_positions']}")
            logger.info(f"📊 Open Positions: {report['open_positions']}")
            logger.info(f"💰 Total Deployed: ₹{report['total_deployed']:,.2f}")
            logger.info(f"📊 Usage: {report['usage_percent']:.1f}%")
            logger.info(f"✅ Winning Trades: {report['winning_trades']}")
            logger.info(f"❌ Losing Trades: {report['losing_trades']}")
            logger.info(f"📈 Win Rate: {report['win_rate']:.1f}%")
            logger.info("=" * 70)
            
            if report['positions']:
                logger.info("📊 POSITION DETAILS:")
                for pos in report['positions']:
                    logger.info(f"  {pos['symbol']} {pos['option_type']} @ ₹{pos['entry_price']:.2f} [{pos['status']}]")
                    logger.info(f"    P&L: ₹{pos['pnl']:,.2f} ({pos['pnl_percent']:+.1f}%) | Deployed: ₹{pos['deployed_capital']:,.2f}")
            logger.info("=" * 70)
            
            logger.info(f"📁 Report saved: {report_file}")
            return report
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to generate EOD report: {e}")
            return None
    
    async def start(self):
        """Start the complete system"""
        try:
            # Wait until market ready
            phase = await self.wait_until_market_ready()
            
            if phase == "PRE_MARKET":
                # Run pre-market analysis at 9:00 AM
                await self.run_pre_market_analysis()
                
                # Wait until 9:15 AM for trading to start
                ist = pytz.timezone('Asia/Kolkata')
                now = datetime.now(ist)
                market_open = time(9, 15)
                target = datetime.combine(now.date(), market_open, tzinfo=ist)
                wait_seconds = (target - now).total_seconds()
                
                if wait_seconds > 0:
                    logger.info(f"⏰ Waiting {wait_seconds/60:.0f} minutes until market opens at 9:15 AM...")
                    await asyncio.sleep(wait_seconds)
            
            # Start trading
            await self.start_trading()
            
            # Run trading loop (9:15 AM - 3:40 PM)
            await self.run_trading_loop()
            
            # Generate EOD report at 3:40 PM
            await self.generate_eod_report()
            
            # Close gracefully
            logger.info("=" * 70)
            logger.info("✅ TRADING DAY COMPLETE")
            logger.info(f"📅 Date: {self.today_date}")
            logger.info("📊 EOD Report generated successfully")
            logger.info("=" * 70)
            
        except KeyboardInterrupt:
            logger.info("[STOP] Interrupted by user")
            # Generate partial report
            await self.generate_eod_report()
        except Exception as e:
            logger.error(f"[ERROR] {e}")
            import traceback
            logger.error(traceback.format_exc())
        finally:
            if self.engine:
                await self.engine.stop()
            if self.dashboard:
                await self.dashboard.stop()
    
    async def stop(self):
        """Stop the system"""
        self.is_running = False
        if self.engine:
            await self.engine.stop()
        if self.dashboard:
            await self.dashboard.stop()
        logger.info("[STOP] System stopped")

async def main():
    system = AdvancedTradingSystem()
    await system.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("[STOP] Interrupted by user")
