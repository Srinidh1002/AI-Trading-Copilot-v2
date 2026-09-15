import os
import json
import time
import signal
import sys
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from SmartApi import SmartConnect
import pyotp
from collections import defaultdict
from market_intelligence import MarketIntelligence
from index_weights import load_index_weights
from contract_metadata import load_contract_index, resolve_lot_size
from quote_freshness import QuoteFreshnessTracker
from rate_limiter import AngelRateLimitCoordinator
from market_phase import MarketPhaseEngine, NSE_HOLIDAYS_2026  # D5_holiday_authority
from fingerprint import fingerprint_snapshot
from websocket_feed import WebSocketFeed
from candle_builder import CandleBuilder
from previous_day_engine import PreviousDayEngine
from mtf_enhanced import compute_indicators as compute_mtf_indicators, timeframe_decision
from vwap import VWAPTracker
from opening_range import OpeningRangeTracker
from breadth_engine import BreadthEngine
from market_regime import MarketRegimeEngine
from external_intel import ExternalIntelEngine
from vix_enhanced import EnhancedVIX
from fii_dii_engine import FIIDIIEngine
from economic_calendar import EconomicCalendarEngine
from news_engine import NewsEngine
from option_chain_engine import OptionChainEngine
from oi_analyzer import OIAnalyzer
from liquidity_gate import LiquidityGate
from strike_ranker import StrikeRanker
from decision_composer import DecisionComposer
from market_selector import MarketSelector
from capital_engine import CapitalEngine
from exit_engine import ExitEngine, MFE_MAE_Tracker
from target_policy import TargetPolicy
from close_drain_policy import CloseDrainPolicy
from prediction_ledger import PredictionLedger
from outcome_ledger import OutcomeLedger

load_dotenv()

# CRITICAL: Silence SmartApi/logzero verbose logging (security)
import logging as _logging
try:
    import logzero as _lz
    _lz.loglevel(_logging.CRITICAL)
    _lz.setup_logger(level=_logging.CRITICAL)
except Exception:
    pass
for _name in ["SmartApi", "smartConnect", "smartWebSocketV2", "logzero"]:
    try:
        _logging.getLogger(_name).setLevel(_logging.CRITICAL)
        _logging.getLogger(_name).propagate = False
        _logging.getLogger(_name).addHandler(_logging.NullHandler())
    except Exception:
        pass
# Disable SmartApi logzero verbose logging
try:
    import logzero
    logzero.loglevel(logging.CRITICAL)
except:
    pass

# Redact sensitive data from logs
import logging
from src.sensitive_filter import SensitiveFilter
import os
_sensitive = [os.getenv('ANGEL_API_KEY'), os.getenv('ANGEL_API_SECRET'), 
              os.getenv('ANGEL_USER_ID'), os.getenv('ANGEL_PASSWORD'), 
              os.getenv('ANGEL_TOTP_SECRET')]
_sf = SensitiveFilter(_sensitive)

# D5_holiday_authority — single source of truth from market_phase.py
_NSE_HOLIDAY_DATES = frozenset(
    datetime.strptime(d, "%Y-%m-%d").date() for d in NSE_HOLIDAYS_2026
)
for _h in logging.root.handlers:
    _h.addFilter(_sf)
for _h in logging.getLogger().handlers:
    _h.addFilter(_sf)


class UnifiedTradingBot:
    def __init__(self, market='NIFTY'):
        self.market = market.upper()
        self.api_key = os.getenv('ANGEL_API_KEY')
        self.user_id = os.getenv('ANGEL_USER_ID')
        self.password = os.getenv('ANGEL_PASSWORD')
        self.totp_secret = os.getenv('ANGEL_TOTP_SECRET')
        
        self.obj = None
        self.instruments = []
        self.active_trades = {}
        self.completed_trades = []
        
        self.total_pnl = 0
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        
        self.t1_hits = 0
        self.t2_hits = 0
        self.t3_hits = 0
        self.stop_losses = 0
        self.market_close_exits = 0
        
        self.T1_PERCENT = 15
        self.T2_PERCENT = 30
        self.T3_PERCENT = 50
        self.STOP_LOSS_PERCENT = 5
        
        # D2_safety_flags — explicit PAPER-only contract
        self.EXECUTION_MODE = "PAPER"
        self.BROKER_SUBMISSION = False
        self.LIVE_EXECUTION = False
        
        self.session_history = []
        self.is_running = True
        self.is_connected = False
        self.current_session = 0
        self.total_sessions = 100
        self.sessions_completed_today = 0
        
        self.consecutive_wins = 0
        self.consecutive_losses = 0
        
        self.MARKET_OPEN = datetime.now().replace(hour=9, minute=15, second=0, microsecond=0)
        self.MARKET_CLOSE = datetime.now().replace(hour=15, minute=30, second=0, microsecond=0)
        self.FINAL_EXIT = datetime.now().replace(hour=15, minute=28, second=0, microsecond=0)
        
        # Market analysis data
        self.global_market_data = {}
        self.fii_dii_data = {}
        self.top_stocks_data = {}
        
        if self.market == 'NIFTY':
            self.index_token = '99926000'
            self.index_exchange = 'NSE'
            self.index_symbol = 'NIFTY'
            self.lot_size = 75
            self.strike_interval = 50
            self.option_exchange = 'NFO'
            self.strike_divisor = 100
            self.top_stocks = ['RELIANCE', 'HDFCBANK', 'ICICIBANK', 'INFY', 'TCS', 'ITC', 'KOTAKBANK', 'LT', 'SBIN', 'BHARTIARTL']
        elif self.market == 'SENSEX':
            self.index_token = '1'
            self.index_exchange = 'BSE'
            self.index_symbol = 'SENSEX'
            self.lot_size = 20
            self.strike_interval = 100
            self.option_exchange = 'BFO'
            self.strike_divisor = 100
            self.top_stocks = ['RELIANCE', 'HDFCBANK', 'ICICIBANK', 'INFY', 'TCS', 'ITC', 'KOTAKBANK', 'LT', 'SBIN', 'BHARTIARTL']
        else:
            print(f"Invalid market: {self.market}")
            sys.exit(1)
        
        self.state_file = f"data/paper_trades/{self.market.lower()}_experimental.json"
        self.market_intel = None  # Initialized after connection
        self.quote_tracker = QuoteFreshnessTracker(freshness_budget_seconds=90)  # REST cadence: WS broken, 50s polls + buffer
        self.rate_limiter = AngelRateLimitCoordinator()
        self.market_phase = MarketPhaseEngine(self.market)
        # WebSocket + live candle state
        self.ws_feed = None
        self.candle_builder = CandleBuilder(max_history=500)
        self.ws_healthy = False
        # Phase B engines
        self.vwap_tracker = VWAPTracker()
        self.or_tracker = OpeningRangeTracker()
        self.breadth_engine = BreadthEngine()
        self.regime_engine = MarketRegimeEngine()
        self.prev_day_engine = None  # Initialized after connect
        self.external_intel = None  # Initialized after connect
        self.vix_engine = None  # Phase C4
        self.fii_dii_engine = None  # Phase C5
        self.calendar_engine = None  # Phase C6
        self.news_engine = None  # Phase C7
        # Phase D engines
        self.option_chain_engine = None
        self.oi_analyzer = OIAnalyzer()
        self.liquidity_gate = LiquidityGate(max_spread_pct=2.0, min_volume=100, min_oi=500)
        self.strike_ranker = StrikeRanker(self.liquidity_gate)
        # Phase E engines
        self.decision_composer = DecisionComposer()
        self.market_selector = MarketSelector()
        # Phase F engines
        self.capital_engine = CapitalEngine(deployable_capital=100000)
        self.exit_engine = ExitEngine(premium_stop_pct=-5.0, time_stop_minutes=30,
                                      underlying_invalidation_pct=0.5)
        self.mfe_mae = MFE_MAE_Tracker()
        self.target_policy = TargetPolicy(t1_pct=15, t2_pct=30, t3_pct=50, single_lot=True)
        self.close_drain = CloseDrainPolicy(self.market)
        # Phase G: prediction ledger
        self.prediction_ledger = PredictionLedger(self.market)
        self.outcome_ledger = OutcomeLedger(self.market)
        # Phase H fix: re-entry control
        self.last_exit_time = None
        self.last_exit_direction = None
        self.same_direction_stops = 0
        self.daily_realized_loss = 0.0
        self.daily_trade_count = 0
        self.MAX_CONSECUTIVE_SAME_DIR_STOPS = 3
        self.COOLDOWN_AFTER_STOP_SECONDS = 300      # 5 min
        self.COOLDOWN_AFTER_2_STOPS_SECONDS = 900    # 15 min
        self.MAX_DAILY_NET_LOSS = 3000               # ₹
        self.MAX_DAILY_TRADES = 12
        self.index_weights, self.index_coverage = load_index_weights(self.market)
        # Contract metadata index for dynamic lot size (Phase A1)
        try:
            self.contract_index = load_contract_index()
            print(f"[init] Contract index loaded: {len(self.contract_index)} entries")
        except Exception as _e:
            self.contract_index = {}
            print(f"[init] Contract index FAILED: {_e}")
        self.entry_spot = None  # For invalidation tracking
        
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
    def signal_handler(self, signum, frame):
        print("\n\n🛑 Shutdown signal received!")
        print("Saving current state...")
        self.save_state()
        self.is_running = False
        print("✅ State saved. Exiting safely...")
        sys.exit(0)
    
    def save_state(self):
        state = {
            'market': self.market,
            'timestamp': datetime.now().isoformat(),
            'current_session': self.current_session,
            'total_sessions': self.total_sessions,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'total_pnl': self.total_pnl,
            't1_hits': self.t1_hits,
            't2_hits': self.t2_hits,
            't3_hits': self.t3_hits,
            'stop_losses': self.stop_losses,
            'market_close_exits': self.market_close_exits,
            'consecutive_wins': self.consecutive_wins,
            'consecutive_losses': self.consecutive_losses,
            'session_history': self.session_history,
            'completed_trades': self.completed_trades,
            'active_trades': list(self.active_trades.values()),
            'sessions_completed_today': self.sessions_completed_today
        }
        
        with open(self.state_file, 'w') as f:
            json.dump(state, f, default=str, indent=2)
        
        print(f"✅ State saved")
    
    def load_state(self):
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                
                self.current_session = state.get('current_session', 0)
                self.total_sessions = state.get('total_sessions', 100)
                self.total_trades = state.get('total_trades', 0)
                self.winning_trades = state.get('winning_trades', 0)
                self.losing_trades = state.get('losing_trades', 0)
                self.total_pnl = state.get('total_pnl', 0)
                self.t1_hits = state.get('t1_hits', 0)
                self.t2_hits = state.get('t2_hits', 0)
                self.t3_hits = state.get('t3_hits', 0)
                self.stop_losses = state.get('stop_losses', 0)
                self.market_close_exits = state.get('market_close_exits', 0)
                self.consecutive_wins = state.get('consecutive_wins', 0)
                self.consecutive_losses = state.get('consecutive_losses', 0)
                self.session_history = state.get('session_history', [])
                self.completed_trades = state.get('completed_trades', [])
                self.sessions_completed_today = state.get('sessions_completed_today', 0)
                
                print(f"✅ Loaded {self.market} state:")
                print(f"   Sessions: {self.current_session}/{self.total_sessions}")
                print(f"   P&L: ₹{self.total_pnl:.2f}")
                return True
        except Exception as e:
            print(f"Could not load state: {e}")
        
        return False
    
    def connect_with_retry(self, max_retries=5, retry_delay=30):
        for attempt in range(max_retries):
            try:
                print(f"Connection attempt {attempt + 1}/{max_retries}...")
                
                self.obj = SmartConnect(api_key=self.api_key)
                totp = pyotp.TOTP(self.totp_secret).now()
                
                data = self.obj.generateSession(
                    clientCode=self.user_id,
                    password=self.password,
                    totp=totp
                )
                
                if data and data.get('status'):
                    self.is_connected = True
                    # Store tokens for WebSocket
                    try:
                        self.auth_token = data['data'].get('jwtToken', '')
                        self.refresh_token = data['data'].get('refreshToken', '')
                        self.feed_token = self.obj.getfeedToken() if hasattr(self.obj, "getfeedToken") else data['data'].get('feedToken', '')
                    except Exception as _e:
                        print(f"[warn] token store failed: {_e}")
                    print("✅ Connected successfully!")
                    if self.market_intel is None:
                        try:
                            self.market_intel = MarketIntelligence(self.obj, self.market, rate_limiter=self.rate_limiter)
                            print("✅ Market intelligence initialized")
                        except Exception as _e:
                            print(f"⚠️ Market intel init failed: {_e}")
                    
                    # Init VIX engine
                    if self.vix_engine is None:
                        try:
                            self.vix_engine = EnhancedVIX(self.obj, rate_limiter=self.rate_limiter)
                            print("[init] VIX engine ready")
                        except Exception as _e:
                            print(f"[init] VIX engine failed: {_e}")
                    
                    # Init calendar engine
                    if self.calendar_engine is None:
                        try:
                            self.calendar_engine = EconomicCalendarEngine()
                            self.calendar_engine.load_recurring()
                            print("[init] Calendar engine ready")
                        except Exception as _e:
                            print(f"[init] Calendar failed: {_e}")
                    
                    # Init option chain engine
                    if self.option_chain_engine is None:
                        try:
                            self.option_chain_engine = OptionChainEngine(
                                self.obj, self.market, self.option_exchange,
                                self.strike_divisor, rate_limiter=self.rate_limiter,
                                cache_ttl=60
                            )
                            print("[init] Option chain engine ready")
                        except Exception as _e:
                            print(f"[init] Option chain failed: {_e}")
                    
                    # Init news engine
                    if self.news_engine is None:
                        try:
                            self.news_engine = NewsEngine(cache_ttl=1800)
                            print("[init] News engine ready")
                        except Exception as _e:
                            print(f"[init] News failed: {_e}")
                    
                    # Init FII/DII engine
                    if self.fii_dii_engine is None:
                        try:
                            self.fii_dii_engine = FIIDIIEngine(cache_ttl=1800)
                            print("[init] FII/DII engine ready")
                        except Exception as _e:
                            print(f"[init] FII/DII failed: {_e}")
                    
                    # Init external intel engine
                    if self.external_intel is None:
                        try:
                            self.external_intel = ExternalIntelEngine(cache_ttl=900)
                            print("[init] External intel engine ready")
                        except Exception as _e:
                            print(f"[init] External intel failed: {_e}")
                    
                    # Init previous day engine
                    if self.prev_day_engine is None:
                        try:
                            self.prev_day_engine = PreviousDayEngine(
                                self.obj, self.market, self.index_exchange,
                                self.index_token, rate_limiter=self.rate_limiter
                            )
                            print("[init] Previous day engine ready")
                        except Exception as _e:
                            print(f"[init] Previous day failed: {_e}")
                    
                    # Start WebSocket feed
                    if self.ws_feed is None:
                        try:
                            self._start_websocket()
                        except Exception as _e:
                            print(f"⚠️ WS start failed: {_e}")
                    return True
                    
            except Exception as e:
                print(f"❌ Connection error: {e}")
            
            if attempt < max_retries - 1:
                print(f"Waiting {retry_delay} seconds...")
                time.sleep(retry_delay)
        
        self.is_connected = False
        return False
    
    def check_connection(self):
        try:
            data = self.obj.ltpData(self.index_exchange, self.index_symbol, self.index_token)
            return data and data.get('data')
        except:
            return False
    
    def reconnect_if_needed(self):
        if not self.check_connection():
            print("\n⚠️ Connection lost! Reconnecting...")
            self.is_connected = False
            
            for attempt in range(3):
                if self.connect_with_retry(max_retries=1, retry_delay=10):
                    print("✅ Reconnected!")
                    return True
                time.sleep(10)
            
            return False
        
        return True
    
    def wait_for_market_open(self):
        now = datetime.now()
        
        if now < self.MARKET_OPEN:
            wait_seconds = (self.MARKET_OPEN - now).seconds
            print(f"\n⏰ Market opens at 9:15 AM")
            print(f"Waiting {wait_seconds//60} minutes...")
            
            while datetime.now() < self.MARKET_OPEN and self.is_running:
                time.sleep(5)
                remaining = (self.MARKET_OPEN - datetime.now()).seconds
                if remaining % 300 < 30:
                    print(f"  {remaining//60} minutes until market opens...")
            
            print("✅ Market is now open!")
            return True
        
        return True
    
    def is_market_open(self):
        """D1_market_phase — delegate to MarketPhaseEngine.
        True during CONTINUOUS (09:15-15:15) and CLOSE_DRAIN (15:15-15:28).
        False on weekends, holidays, and after 15:28."""
        try:
            phase, _, _, _ = self.market_phase.get_phase()
            return phase in ("CONTINUOUS", "CLOSE_DRAIN")
        except AttributeError:
            now = datetime.now()
            return self.MARKET_OPEN <= now <= self.FINAL_EXIT
    
    def load_instruments(self):
        try:
            with open('data/instruments.json', 'r') as f:
                raw = json.load(f)
            
            self.instruments = []
            for inst in raw:
                symbol = inst.get('symbol', '')
                
                if self.market == 'NIFTY':
                    if not ('NIFTY' in symbol and 'BANKNIFTY' not in symbol and 'FINNIFTY' not in symbol):
                        continue
                elif self.market == 'SENSEX':
                    if 'SENSEX' not in symbol or 'SENSEX50' in symbol:
                        continue
                
                if inst.get('instrumenttype') == 'OPTIDX':
                    strike = float(inst.get('strike', 0)) / self.strike_divisor
                    
                    self.instruments.append({
                        'symbol': symbol,
                        'token': inst.get('token'),
                        'strike': strike,
                        'expiry': inst.get('expiry', ''),
                        'type': 'CE' if symbol.endswith('CE') else 'PE',
                        'exchange': inst.get('exch_seg', self.option_exchange),
                        'market': self.market
                    })
            
            print(f"✅ Loaded {len(self.instruments)} {self.market} options")
            return True
        except Exception as e:
            print(f"❌ Error loading instruments: {e}")
            return False
    
    def _start_websocket(self):
        """Start WebSocket feed and subscribe to spot tokens."""
        try:
            # Tokens captured at login (see connect_with_retry)
            _auth = getattr(self, "auth_token", None)
            _feed = getattr(self, "feed_token", None)
            if not _auth or not _feed:
                print("[WS] missing auth/feed token - skipping WS")
                self.ws_feed = None
                return
            self.ws_feed = WebSocketFeed(
                auth_token=_auth,
                api_key=self.api_key,
                client_id=self.user_id,
                feed_token=_feed,
            )
            
            # Wire ticks into candle builder
            def on_tick(tick):
                self.candle_builder.on_tick(tick["token"], tick["ltp"], tick["ts"])
                self.ws_healthy = True
            
            self.ws_feed.register_callback(on_tick)
            
            if not self.ws_feed.start():
                print("[WS] start() returned False")
                self.ws_feed = None
                return
            
            # Subscribe spot tokens
            import time as _t
            _t.sleep(2)  # Give WS time to connect
            
            if self.market == "NIFTY":
                subs = {"NSE_CM": ["99926000"]}
            else:
                subs = {"BSE_CM": ["1"]}
            
            self.ws_feed.subscribe(subs, mode=2)
            print(f"[WS] Subscribed to {self.market} spot")
        except Exception as e:
            print(f"[WS] setup error: {str(e)[:80]}")
            self.ws_feed = None
    
    def get_spot(self):
        for attempt in range(3):
            try:
                data = self.obj.ltpData(self.index_exchange, self.index_symbol, self.index_token)
                if data and data.get('data'):
                    ltp = float(data['data'].get('ltp', 0))
                    provider_ts = data['data'].get('exchange_timestamp') or data['data'].get('timestamp')
                    freshness = self.quote_tracker.update(
                        self.index_symbol, ltp, provider_timestamp=provider_ts
                    )
                    # Store last freshness for reporting
                    self._last_spot_freshness = freshness
                    # Feed Phase B trackers
                    try:
                        self.vwap_tracker.on_tick(ltp, volume=1)
                        self.or_tracker.on_tick(ltp)
                    except Exception:
                        pass
                    return ltp
            except:
                pass
            time.sleep(2)
        return 0
    
    def get_day_open(self, spot):
        """Get actual day open. Returns (value, status). None if unavailable."""
        today = datetime.now().strftime("%Y-%m-%d")
        
        attempts = [
            ("FIVE_MINUTE", f"{today} 09:15", f"{today} 09:45"),
            ("FIFTEEN_MINUTE", f"{today} 09:15", f"{today} 10:00"),
            ("ONE_HOUR", f"{today} 09:15", f"{today} 11:00"),
        ]
        
        for interval, from_date, to_date in attempts:
            try:
                self.rate_limiter.wait_if_needed("get_candle_data")
                candles = self.obj.getCandleData({
                    "exchange": self.index_exchange,
                    "symboltoken": self.index_token,
                    "interval": interval,
                    "fromdate": from_date,
                    "todate": to_date,
                })
                if candles and candles.get("data") and len(candles["data"]) > 0:
                    day_open = float(candles["data"][0][1])
                    if day_open > 0:
                        print(f"    [day_open] {interval}: {day_open:.2f}")
                        return day_open, "OK"
            except Exception as e:
                print(f"    [day_open] {interval} failed: {str(e)[:40]}")
                continue
        
        return None, "EVIDENCE_UNAVAILABLE"
    

    def get_expiry(self):
        today = datetime.now().date()  # DATE only, not datetime
        expiries = sorted(set(inst['expiry'] for inst in self.instruments))
        
        valid = []
        for exp_str in expiries:
            try:
                exp_date = datetime.strptime(exp_str, '%d%b%Y').date()  # DATE only
                calendar_dte = (exp_date - today).days  # Pure date diff
                if calendar_dte >= 0:
                    valid.append((exp_str, calendar_dte, exp_date))
            except:
                continue
        
        valid.sort(key=lambda x: x[1])
        
        if not valid:
            return None
        
        nearest_expiry, nearest_dte, nearest_date = valid[0]
        
        # Holiday-aware trading days calculator (D5_holiday_authority)
        def trading_days_between(start_date, end_date):
            holidays = _NSE_HOLIDAY_DATES
            count = 0
            current = start_date + timedelta(days=1)
            while current <= end_date:
                if current.weekday() < 5 and current not in holidays:
                    count += 1
                current += timedelta(days=1)
            return count
        
        if self.market == 'SENSEX' and nearest_dte == 0 and len(valid) > 1:
            selected_expiry, selected_dte, selected_date = valid[1]
            trading_days = trading_days_between(today, selected_date)
            print(f'  NEAREST_EXPIRY: {nearest_expiry}')
            print(f'  NEAREST_EXPIRY_DTE: 0 (SAME DAY)')
            print(f'  SELECTED_EXPIRY: {selected_expiry}')
            print(f'  CALENDAR_DTE: {selected_dte}')
            print(f'  TRADING_DAYS_TO_EXPIRY: {trading_days}')
            print(f'  EXPIRY_SELECTION_REASON: SAME_DAY_EXPIRY_EXCLUDED')
            return selected_expiry
        
        trading_days = trading_days_between(today, nearest_date)
        print(f'  Expiry: {nearest_expiry}')
        print(f'  CALENDAR_DTE: {nearest_dte}')
        print(f'  TRADING_DAYS_TO_EXPIRY: {trading_days}')
        return nearest_expiry
    
    def get_options(self, spot, expiry):
        atm = round(spot / self.strike_interval) * self.strike_interval
        
        print(f"Spot: {spot}")
        print(f"ATM: {atm}")
        print(f"Expiry: {expiry}")
        
        options = []
        
        for inst in self.instruments:
            if inst['expiry'] == expiry and abs(inst['strike'] - atm) <= self.strike_interval * 3:
                try:
                    ltp_data = self.obj.ltpData(inst['exchange'], inst['symbol'], inst['token'])
                    if ltp_data and ltp_data.get('data'):
                        ltp = float(ltp_data['data'].get('ltp', 0))
                        if ltp > 0:
                            inst['ltp'] = ltp
                            options.append(inst)
                            print(f"  {inst['type']} {inst['strike']}: ₹{ltp:.2f}")
                except:
                    pass
                time.sleep(0.2)
        
        print(f"Total options found: {len(options)}")
        return options, atm
    
    def get_market_sentiment(self, spot, options):
        """Basic PCR sentiment"""
        if not options:
            return 'NEUTRAL', 0.5
        
        ce_options = [o for o in options if o['type'] == 'CE' and o['ltp'] > 10]
        pe_options = [o for o in options if o['type'] == 'PE' and o['ltp'] > 10]
        
        if ce_options and pe_options:
            ce_premium = ce_options[0]['ltp']
            pe_premium = pe_options[0]['ltp']
            
            pcr = pe_premium / ce_premium if ce_premium > 0 else 1
            
            print(f"PCR: {pcr:.2f}")
            
            if pcr < 0.7:
                return 'BULLISH', 0.8
            elif pcr > 1.3:
                return 'BEARISH', 0.8
            elif pcr < 0.9:
                return 'BULLISH', 0.6
            elif pcr > 1.1:
                return 'BEARISH', 0.6
            else:
                return 'NEUTRAL', 0.4
        
        return 'NEUTRAL', 0.3
    
    def analyze_top_stocks(self):
        """Analyze FIXED weighted stock universe - NIFTY/SENSEX constituents"""
        print(' 📊 Analyzing Weighted Constituents (FIXED UNIVERSE)...')
        
        if self.market == 'NIFTY':
            universe = self.index_weights
        else:
            universe = self.index_weights
        
        if not hasattr(self, '_token_cache'):
            self._token_cache = {}
            try:
                with open('data/instruments.json', 'r') as f:
                    raw = json.load(f)
                for inst in raw:
                    if inst.get('exch_seg') == 'NSE':
                        sym = inst.get('symbol', '')
                        if sym.endswith('-EQ'):
                            self._token_cache[sym] = inst.get('token')
            except:
                pass
        
        weighted_bull = 0.0
        weighted_bear = 0.0
        valid_count = 0
        missing_count = 0
        self._stock_changes = {}
        
        for symbol, weight in universe:
            try:
                token = self._token_cache.get(symbol, '')
                if not token:
                    missing_count += 1
                    continue
                
                quote = self.obj.ltpData('NSE', symbol, token)
                if not quote or not quote.get('data'):
                    missing_count += 1
                    continue
                
                ltp = float(quote['data'].get('ltp', 0))
                prev_close = float(quote['data'].get('close', 0))
                
                if ltp <= 0 or prev_close <= 0:
                    missing_count += 1
                    continue
                
                change_pct = ((ltp - prev_close) / prev_close) * 100
                contribution = (weight / 100) * change_pct
                self._stock_changes[symbol.replace('-EQ', '')] = change_pct
                
                if change_pct > 0.15:
                    weighted_bull += contribution
                    marker = 'UP'
                elif change_pct < -0.15:
                    weighted_bear += abs(contribution)
                    marker = 'DN'
                else:
                    marker = '--'
                
                valid_count += 1
                print(f'  [{marker}] {symbol.replace("-EQ", "")} ({weight:.1f}%): {change_pct:+.2f}% | contrib: {contribution:+.3f}')
                
                time.sleep(0.5)
                
            except Exception:
                missing_count += 1
                continue
        
        total_expected = len(universe)
        completeness = valid_count / total_expected if total_expected > 0 else 0
        
        # Cache stock changes for BreadthEngine (Phase B5)
        try:
            _cache = []
            for _sym, _w in universe:
                _cp = self._stock_changes.get(_sym.replace('-EQ', ''))
                if _cp is not None:
                    _cache.append({
                        'symbol': _sym.replace('-EQ', ''),
                        'weight': _w,
                        'change_pct': _cp,
                        'above_vwap': None,
                        'above_ema20': None,
                    })
            self._last_stock_data = _cache
        except Exception:
            self._last_stock_data = []

        print(f'  Evidence: {valid_count}/{total_expected} stocks loaded')
        
        if completeness < 0.6:
            print(f'  INSUFFICIENT EVIDENCE ({completeness:.0%}) - abstaining')
            return 0, 0, 'INCOMPLETE'
        
        print(f'  Weighted Bull: +{weighted_bull:.3f}')
        print(f'  Weighted Bear: -{weighted_bear:.3f}')
        
        if weighted_bull > weighted_bear * 1.5 and weighted_bull > 0.15:
            return valid_count, missing_count, 'BULLISH'
        elif weighted_bear > weighted_bull * 1.5 and weighted_bear > 0.15:
            return valid_count, missing_count, 'BEARISH'
        else:
            return valid_count, missing_count, 'NEUTRAL'
    
    def get_stock_token(self, stock):
        """Get stock token from instrument file"""
        try:
            with open('data/instruments.json', 'r') as f:
                raw = json.load(f)
            
            for inst in raw:
                if (inst.get('symbol') == stock or inst.get('symbol') == stock + '-EQ') and inst.get('exch_seg') == 'NSE':
                    return inst.get('token')
        except:
            pass
        return ''
    
    def get_enhanced_sentiment(self, spot, options):
        """FULL ADAPTIVE sentiment - all pillars"""
        print('\n' + '='*60)
        print('ENHANCED MARKET ANALYSIS - ALL PILLARS')
        print('='*60)
        
        # Session open tracking
        if not hasattr(self, '_session_open_price'):
            # Fetch day open with honest status reporting
            if not hasattr(self, '_day_open_loaded'):
                _open_val, _open_status = self.get_day_open(spot)
                self._day_open_value = _open_val
                self._day_open_status = _open_status
                self._day_open_loaded = True
            
            _phase = self.market_phase.describe()
        print(f'MARKET_PHASE: {_phase["phase"]} (enter={_phase["can_enter"]} exit={_phase["can_exit"]})')
        if self.ws_feed:
            _ws_status = self.ws_feed.health_str()
        else:
            _ws_status = "OFFLINE"
        print(f'WS_STATUS: {_ws_status}')
        print(f'RUN_START_SPOT: {spot:.2f}')
        if hasattr(self, '_last_spot_freshness'):
            _f = self._last_spot_freshness
            print(f'SPOT_FRESHNESS: {_f["status"]} (age={_f["age_seconds"]:.1f}s)')
            if self._day_open_status == 'OK' and self._day_open_value:
                print(f'DAY_OPEN_STATUS: OK')
                print(f'DAY_OPEN_VALUE: {self._day_open_value:.2f}')
                session_change = ((spot - self._day_open_value) / self._day_open_value) * 100
                print(f'Change from day open: {session_change:+.3f}%')
            else:
                print(f'DAY_OPEN_STATUS: EVIDENCE_UNAVAILABLE')
                print(f'DAY_OPEN_VALUE: null')
                session_change = 0.0
                print(f'Change from day open: unavailable')
        
        # Spot trend
        if hasattr(self, 'previous_spot') and self.previous_spot > 0:
            spot_change = ((spot - self.previous_spot) / self.previous_spot) * 100
            if spot_change > 0.15:
                spot_trend = 'RISING'
            elif spot_change < -0.15:
                spot_trend = 'FALLING'
            else:
                spot_trend = 'FLAT'
        else:
            spot_trend = 'UNKNOWN'
        self.previous_spot = spot
        print(f'Spot trend (tick): {spot_trend}')
        
        # ============ PILLAR 1: PCR ============
        pcr_sentiment, pcr_conf = self.get_market_sentiment(spot, options)
        print(f'[1/6] PCR: {pcr_sentiment} ({pcr_conf:.2f})')
        
        # ============ PILLAR 2: Weighted Stocks ============
        result = self.analyze_top_stocks()
        if len(result) == 3:
            valid_count, missing_count, stock_sentiment = result
        else:
            valid_count, stock_sentiment = result
            missing_count = 0
        
        if stock_sentiment == 'INCOMPLETE':
            print('>>> SKIP: Stock data incomplete')
            self.decision_state = 'WAIT_DATA'
            return 'NEUTRAL'
        print(f'[2/6] Stocks: {stock_sentiment} ({valid_count} valid / {missing_count} missing)')
        
        # ============ PHASE B: BREADTH (from stock analysis) ============
        try:
            # Rebuild breadth input from last stock scan
            stock_data = getattr(self, "_last_stock_data", [])
            if stock_data:
                breadth = self.breadth_engine.compute(stock_data)
                print(f"[B5] Breadth: {breadth.get('bias')} | adv={breadth.get('advancing')} dec={breadth.get('declining')} | weight_adv%={breadth.get('weight_advancing_pct')} weight_dec%={breadth.get('weight_declining_pct')}")
                print(f"     above_vwap%={breadth.get('above_vwap_pct')}")
            else:
                print("[B5] Breadth: EVIDENCE_UNAVAILABLE (no stock data cached)")
        except Exception as e:
            print(f"[B5] Breadth error: {str(e)[:50]}")
        
        # ============ PILLAR 3: Multi-timeframe technicals ============
        tech_consensus = 'UNKNOWN'
        tech_data = {}
        if self.market_intel:
            try:
                tech_data = self.market_intel.get_multi_timeframe_technicals()
                tech_consensus = tech_data.get('consensus', 'UNKNOWN')
                print(f'[3/6] Technicals (MTF): {tech_consensus}')
                for tf in ['1m', '5m', '15m', '1h']:
                    if tf in tech_data:
                        d = tech_data[tf]
                        if 'trend' in d:
                            rsi_v = d.get('rsi')
                            rsi_str = f'{rsi_v:.0f}' if rsi_v else '--'
                            print(f'      {tf}: {d["trend"]} (RSI={rsi_str})')
            except Exception as e:
                print(f'[3/6] Technicals: ERROR ({str(e)[:30]})')
        else:
            print('[3/6] Technicals: NOT INITIALIZED')
        
        # ============ PILLAR 4: Global markets ============
        global_sentiment = 'UNKNOWN'
        if self.market_intel:
            try:
                glob = self.market_intel.get_global_markets()
                global_sentiment = glob.get('sentiment', 'UNKNOWN')
                print(f'[4/6] Global: {global_sentiment}')
                for name in ['Dow', 'SP500', 'Nasdaq', 'Nikkei', 'HangSeng']:
                    if name in glob and isinstance(glob[name], dict):
                        cp = glob[name].get('change_pct', 0)
                        print(f'      {name}: {cp:+.2f}%')
                if 'Crude' in glob:
                    print(f'      Crude: {glob["Crude"].get("change_pct", 0):+.2f}%')
            except Exception as e:
                print(f'[4/6] Global: ERROR ({str(e)[:30]})')
        else:
            print('[4/6] Global: NOT INITIALIZED')
        
        # ============ PILLAR 5: India VIX ============
        vix_regime = 'UNKNOWN'
        vix_val = None
        if self.market_intel:
            try:
                vix = self.market_intel.get_india_vix()
                vix_regime = vix.get('regime', 'UNKNOWN')
                vix_val = vix.get('vix')
                # Enhanced VIX with change/percentile/trend (Phase C4)
                if self.vix_engine:
                    try:
                        evix = self.vix_engine.fetch()
                        if evix.get("status") == "OK":
                            vix_regime = evix.get("regime", vix_regime)
                            vix_val = evix.get("vix", vix_val)
                            print(f'[5/6] India VIX: {vix_val:.2f} ({vix_regime}) '
                                  f'{evix.get("change_1d_pct", 0):+.2f}% '
                                  f'trend={evix.get("trend")} '
                                  f'pct={evix.get("percentile_45d")}')
                        else:
                            print(f'[5/6] India VIX: {vix_val} ({vix_regime}) [enhanced unavailable]')
                    except Exception as _e:
                        print(f'[5/6] India VIX: {vix_val} ({vix_regime})')
                else:
                    if vix_val:
                        print(f'[5/6] India VIX: {vix_val:.2f} ({vix_regime})')
                    else:
                        print(f'[5/6] India VIX: unavailable')
            except Exception as e:
                print(f'[5/6] VIX: ERROR ({str(e)[:30]})')
        else:
            print('[5/6] VIX: NOT INITIALIZED')
        
        # ============ PILLAR 6: FII/DII ============
        fii_bias = 'UNKNOWN'
        if self.market_intel:
            try:
                # Enhanced FII/DII (Phase C5)
                if self.fii_dii_engine:
                    try:
                        efii = self.fii_dii_engine.fetch()
                        if efii.get("status") == "OK":
                            fii_bias = efii.get("bias", "UNKNOWN")
                            print(f'[6/6] FII/DII [{efii.get("type")}]: {fii_bias}')
                            print(f'      Date={efii.get("trade_date")} '
                                  f'FII=₹{efii.get("fii_cash_net", 0):.0f}Cr '
                                  f'DII=₹{efii.get("dii_cash_net", 0):.0f}Cr '
                                  f'combined=₹{efii.get("combined_net", 0):.0f}Cr')
                        else:
                            print(f'[6/6] FII/DII: EVIDENCE_UNAVAILABLE')
                    except Exception as _e:
                        print(f'[6/6] FII/DII: error {str(_e)[:40]}')
                else:
                    fii = self.market_intel.get_fii_dii()
                    fii_bias = fii.get('bias', 'UNKNOWN')
                    fii_net = fii.get('fii_net')
                    dii_net = fii.get('dii_net')
                    print(f'[6/6] FII/DII: {fii_bias}')
                    if fii_net is not None:
                        print(f'      FII net: Rs{fii_net:.0f}Cr | DII net: Rs{dii_net:.0f}Cr')
            except Exception as e:
                print(f'[6/6] FII/DII: ERROR ({str(e)[:30]})')
        else:
            print('[6/6] FII/DII: NOT INITIALIZED')
        
        # ============ PHASE B: PREVIOUS-DAY CONTEXT ============
        prev_ctx = {}
        if self.prev_day_engine:
            try:
                prev_ctx = self.prev_day_engine.fetch()
                if prev_ctx.get("status") == "OK":
                    print(f"[B1] Prev Day: O={prev_ctx['open']:.2f} H={prev_ctx['high']:.2f} L={prev_ctx['low']:.2f} C={prev_ctx['close']:.2f}")
                    print(f"     Type={prev_ctx['day_type']} Range%={prev_ctx['range_pct']:.2f} CloseLoc={prev_ctx['close_location']:.2f}")
                    print(f"     ATR14={prev_ctx['atr14']:.2f}" if prev_ctx.get('atr14') else "     ATR14=N/A")
                else:
                    print(f"[B1] Prev Day: EVIDENCE_UNAVAILABLE ({prev_ctx.get('reason')})")
            except Exception as e:
                print(f"[B1] Prev Day error: {str(e)[:50]}")
        
        # ============ PHASE B: VWAP ============
        vwap_ctx = self.vwap_tracker.describe(price=spot)
        if vwap_ctx.get("vwap"):
            print(f"[B3] INDEX_TWAP: {vwap_ctx['vwap']:.2f} | Price {vwap_ctx['position']} | H={vwap_ctx['high']:.2f} L={vwap_ctx['low']:.2f} ticks={vwap_ctx['ticks']}")
        else:
            print("[B3] INDEX_TWAP: INSUFFICIENT_DATA")
        
        # ============ PHASE B: OPENING RANGE ============
        or_ctx = self.or_tracker.describe(price=spot)
        for tf in ["5m", "15m", "30m"]:
            r = or_ctx.get(tf, {})
            if r.get("high"):
                print(f"[B4] OR-{tf}: H={r['high']:.2f} L={r['low']:.2f} W={r['width']:.2f} locked={r['locked']} status={r['status']}")
        
        # ============ PHASE B: REGIME ============
        regime_ctx = {"regime": "UNKNOWN", "confidence": 0.0}
        try:
            if self.market_intel:
                # Gather raw candles for each timeframe
                tf_map = {"1h": "ONE_HOUR", "15m": "FIFTEEN_MINUTE", "5m": "FIVE_MINUTE"}
                mtf_full = {}
                for tf_name, tf_interval in tf_map.items():
                    df = self.market_intel.get_candles(tf_interval, days_back=10 if tf_name == "1h" else 5)
                    if df is not None and len(df) >= 26:
                        ind = compute_mtf_indicators(df)
                        mtf_full[tf_name] = ind
                    time.sleep(0.4)  # D12_stagger - space out candle requests
                
                if mtf_full:
                    regime_ctx = self.regime_engine.classify(mtf_full, vwap_ctx=vwap_ctx, or_data=or_ctx)
                    print(f"[B7] Regime: {regime_ctx['regime']} (conf={regime_ctx['confidence']}) ADX={regime_ctx.get('avg_adx')} {regime_ctx.get('trends_summary')}")
                    
                    # Detailed MTF decisions
                    for tf_name in ["1h", "15m", "5m"]:
                        ind = mtf_full.get(tf_name)
                        if ind and ind.get("status") == "OK":
                            dec, conf = timeframe_decision(ind)
                            print(f"     {tf_name}: {dec} (conf={conf:.2f}) trend={ind['trend']} mom={ind['momentum']} RSI={ind['rsi']:.0f} ADX={ind.get('adx', 0):.0f}")
        except Exception as e:
            print(f"[B7] Regime error: {str(e)[:50]}")
        
        # ============ PHASE C: EXTERNAL INTEL ============
        ext = {}
        if self.external_intel:
            try:
                ext = self.external_intel.fetch()
                if ext.get("status") == "OK":
                    r = ext.get("risk", {})
                    c = ext.get("crude", {})
                    print(f"[C] External: RISK={r.get('sentiment')} (conf={r.get('confidence')})")
                    print(f"    Crude: ${c.get('brent_price', 0):.2f} 1d={c.get('change_1d_pct', 0):+.2f}% 5d={c.get('change_5d_pct', 0):+.2f}% pct={c.get('percentile_30d', 0):.0f} -> {c.get('regime')} | India: {c.get('india_macro_pressure')}")
                    print(f"    Coverage: {ext.get('coverage')}")
            except Exception as e:
                print(f"[C] External error: {str(e)[:50]}")

        # ============ PHASE C6: CALENDAR ============
        if self.calendar_engine:
            try:
                high_impact = self.calendar_engine.minutes_to_next_high_impact(10)
                if high_impact.get("block_entries"):
                    for ev in high_impact.get("events", []):
                        print(f"[C6] EVENT RISK: {ev['name']} in {ev['in_minutes']}min -> entries BLOCKED")
                else:
                    today_events = self.calendar_engine.upcoming_today()
                    if today_events:
                        print(f"[C6] Calendar: {len(today_events)} events today, next={today_events[0]['name']}@{today_events[0]['at']}")
                    else:
                        print(f"[C6] Calendar: no events today")
            except Exception as e:
                print(f"[C6] Calendar error: {str(e)[:50]}")
        
        # ============ PHASE C7: NEWS ============
        if self.news_engine:
            try:
                news = self.news_engine.fetch()
                if news.get("status") == "OK":
                    print(f"[C7] News: {news.get('sentiment')} "
                          f"(+{news.get('positive_count', 0)}/-{news.get('negative_count', 0)}/{news.get('total_count', 0)}) "
                          f"feeds={news.get('coverage')}")
                else:
                    print(f"[C7] News: {news.get('status')}")
            except Exception as e:
                print(f"[C7] News error: {str(e)[:50]}")
        
        # ============ COMPOSITE SCORING ============
        print()
        print('--- Composite Scoring ---')
        
        bull_score = 0.0
        bear_score = 0.0
        
        # PCR (weight 1.0)
        # PHASE H FIX: Only count PCR if it came from chain module, not legacy
        # Legacy PCR from ltpData has no OI/volume provenance
        _pcr_has_provenance = False  # Set True only if chain module returned PCR_OI
        try:
            if hasattr(self, '_last_chain') and self._last_chain:
                if self._last_chain.get('pcr_oi') is not None:
                    _pcr_has_provenance = True
        except Exception:
            pass
        
        if _pcr_has_provenance:
            if pcr_sentiment == 'BULLISH':
                bull_score += pcr_conf
            elif pcr_sentiment == 'BEARISH':
                bear_score += pcr_conf
        else:
            print(f'  [PCR] Legacy PCR vote skipped (no OI provenance): {pcr_sentiment}')
        
        # Stocks (weight 1.0)
        if stock_sentiment == 'BULLISH':
            bull_score += 0.7
        elif stock_sentiment == 'BEARISH':
            bear_score += 0.7
        
        # Technicals (weight 1.0)
        if tech_consensus == 'BULLISH':
            bull_score += 1.0
        elif tech_consensus == 'BEARISH':
            bear_score += 1.0
        elif tech_consensus == 'WEAK_BULLISH':
            bull_score += 0.5
        elif tech_consensus == 'WEAK_BEARISH':
            bear_score += 0.5
        
        # Global (weight 0.5)
        if global_sentiment == 'RISK_ON':
            bull_score += 0.5
        elif global_sentiment == 'RISK_OFF':
            bear_score += 0.5
        
        # VIX (regime modifies risk, doesn't add direction)
        if vix_regime == 'HIGH':
            print('  NOTE: HIGH VIX - reducing confidence')
            bull_score *= 0.8
            bear_score *= 0.8
        
        # FII/DII (weight 0.5)
        if fii_bias == 'BULLISH':
            bull_score += 0.5
        elif fii_bias == 'BEARISH':
            bear_score += 0.5
        
        print(f'  Bull score: {bull_score:.2f}')
        print(f'  Bear score: {bear_score:.2f}')
        
        # ============ DECISION RULES ============
        # Rule 1: Skip flat spot (refined Phase H fix)
        # Only skip if BOTH:
        #   - intraday change from open is tiny (<0.10%)
        #   - AND regime is truly range-bound or unknown
        # We DO NOT skip when there is a clear overnight gap or trend
        _regime_for_flat = regime_ctx.get("regime", "UNKNOWN") if 'regime_ctx' in dir() else "UNKNOWN"
        _regime_is_range = _regime_for_flat in ("RANGE_BOUND", "LOW_VOLATILITY_COMPRESSION", "UNKNOWN")
        
        # Check overnight context via previous_day_engine
        _gap_pct = None
        try:
            if self.prev_day_engine:
                _pd = self.prev_day_engine.fetch()
                if _pd.get("status") == "OK" and _pd.get("close"):
                    _gap_pct = ((self._session_open_price - _pd["close"]) / _pd["close"]) * 100 if self._session_open_price else None
        except Exception:
            pass
        
        _big_move = False
        if abs(session_change) >= 0.10:
            _big_move = True
        if _gap_pct is not None and abs(_gap_pct) >= 0.30:
            _big_move = True
        
        if spot_trend == 'FLAT' and not _big_move and _regime_is_range:
            print(f'>>> SKIP: Market FLAT (session={session_change:+.3f}% gap={_gap_pct if _gap_pct is None else round(_gap_pct,3)} regime={_regime_for_flat})')
            self.decision_state = 'WAIT_CONFIRMATION'
            return 'NEUTRAL'
        
        # Rule 2: Need 2+ independent pillars agreeing
        bull_pillars = sum([
            pcr_sentiment == 'BULLISH',
            stock_sentiment == 'BULLISH',
            tech_consensus in ('BULLISH', 'WEAK_BULLISH'),
            global_sentiment == 'RISK_ON',
            fii_bias == 'BULLISH',
        ])
        bear_pillars = sum([
            pcr_sentiment == 'BEARISH',
            stock_sentiment == 'BEARISH',
            tech_consensus in ('BEARISH', 'WEAK_BEARISH'),
            global_sentiment == 'RISK_OFF',
            fii_bias == 'BEARISH',
        ])
        
        print(f'  Bull pillars: {bull_pillars}/5')
        print(f'  Bear pillars: {bear_pillars}/5')
        
        # ============ PHASE E: DECISION COMPOSER ============
        session_state = self.market_phase.describe()
        spot_fresh = getattr(self, '_last_spot_freshness', {}).get('status', 'UNKNOWN')
        tech_ok = tech_consensus not in ('UNKNOWN', 'INSUFFICIENT_DATA')
        
        total_pillars = 7
        loaded_pillars = sum([
            pcr_sentiment != 'NEUTRAL',
            stock_sentiment != 'INSUFFICIENT',
            tech_ok,
            global_sentiment != 'UNKNOWN',
            vix_regime != 'UNKNOWN',
            fii_bias != 'UNKNOWN',
            regime_ctx.get('regime', 'UNKNOWN') != 'UNKNOWN',
        ])
        coverage_pct = (loaded_pillars / total_pillars) * 100
        
        event_block = False
        if self.calendar_engine:
            try:
                _evt = self.calendar_engine.minutes_to_next_high_impact(10)
                event_block = _evt.get('block_entries', False)
            except Exception:
                pass
        
        decision_ctx = {
            'market_identity_ok': True,
            'session_state': session_state,
            'spot_freshness': spot_fresh,
            'option_freshness': 'NOT_YET_CHECKED',
            'contract_metadata_ok': bool(self.contract_index),
            'expiry_validity_ok': True,
            'bull_score': bull_score,
            'bear_score': bear_score,
            'bull_pillars': bull_pillars,
            'bear_pillars': bear_pillars,
            'technical_data_ok': tech_ok,
            'evidence_coverage_pct': coverage_pct,
            'regime': regime_ctx.get('regime', 'UNKNOWN'),
            'event_block': event_block,
        }
        
        decision = self.decision_composer.compose(decision_ctx)
        
        print(f'\n  [E] MARKET_BIAS={decision["bias"]} conf={decision["bias_confidence"]}')
        print(f'  [E] ENTRY_READINESS={decision["readiness"]} ACTION={decision["action"]}')
        print(f'  [E] Coverage: {loaded_pillars}/{total_pillars} ({coverage_pct:.0f}%)')
        if decision.get('blockers'):
            print(f'  [E] Blockers: {decision["blockers"]}')
        
        # ===== PHASE G1: Record prediction to ledger =====
        try:
            _record = self.prediction_ledger.build_record(
                market=self.market,
                bias=decision['bias'],
                bias_confidence=decision['bias_confidence'],
                readiness=decision['readiness'],
                action=decision['action'],
                blockers=decision.get('blockers', []),
                bull_score=bull_score,
                bear_score=bear_score,
                bull_pillars=bull_pillars,
                bear_pillars=bear_pillars,
                evidence_coverage_pct=coverage_pct,
                spot=spot,
                spot_freshness=spot_fresh,
                regime=regime_ctx.get('regime', 'UNKNOWN'),
                selected_trade=None,
                config_version='v3-phase-g',
            )
            self.prediction_ledger.record(_record)
        except Exception as _e:
            print(f'[G1] ledger error: {str(_e)[:60]}')
        
        if decision['action'] == 'BUY_CALL':
            self.decision_state = 'ENTRY_ELIGIBLE'
            return 'BULLISH'
        elif decision['action'] == 'BUY_PUT':
            self.decision_state = 'ENTRY_ELIGIBLE'
            return 'BEARISH'
        elif decision['action'] == 'WAIT':
            self.decision_state = 'WAIT_CONFIRMATION'
            return 'NEUTRAL'
        else:
            self.decision_state = 'BLOCKED'
            return 'NEUTRAL'
    
    def select_trade(self, sentiment, spot, options):
        """PHASE D: Full chain + liquidity gate + strike ranking."""
        if not options:
            return None
        
        atm = round(spot / self.strike_interval) * self.strike_interval
        expiry = self.get_expiry()
        
        # Try full chain engine first (Phase D)
        if self.option_chain_engine and self.strike_ranker:
            try:
                inst_flat = [
                    {
                        "symbol": i["symbol"],
                        "token": i["token"],
                        "strike": i["strike"],
                        "expiry": i["expiry"],
                        "type": i["type"],
                        "market": self.market,
                        "exchange": i.get("exchange", self.option_exchange),
                    }
                    for i in self.instruments
                ]
                
                chain = self.option_chain_engine.fetch(expiry, atm, inst_flat, strike_range=200)
                self._last_chain = chain  # Phase H: for PCR provenance check
                
                if chain and chain.get("status") == "OK":
                    print(f"\n  [D1] CHAIN: {self.option_chain_engine.describe(chain)}")
                    
                    oi_analysis = self.oi_analyzer.analyze(chain)
                    if oi_analysis.get("status") == "OK":
                        print(f"  [D2] {self.oi_analyzer.describe(oi_analysis)}")
                    
                    ranking = self.strike_ranker.rank(chain, sentiment, atm)
                    if ranking.get("status") == "OK":
                        top = ranking.get("top_pick")
                        if top:
                            print(f"  [D3/D4] RANKED top={top['type']} {top['strike']} score={top['score']} LTP={top['ltp']} spread={top.get('spread_pct')}% vol={top['volume']}")
                            for c in ranking.get("candidates", [])[1:4]:
                                status = "OK " if c["passes_liquidity"] else "REJ"
                                print(f"          [{status}] {c['type']} {c['strike']} score={c['score']} LTP={c['ltp']}")
                            sym = top.get("symbol")
                            tok = top.get("token")
                            if sym and tok:
                                return {
                                    "type": top["type"],
                                    "strike": top["strike"],
                                    "signal": "BUY",
                                    "entry": top["ltp"],
                                    "ltp": top.get("ltp", 0),
                                    "bid": top.get("bid", 0),
                                    "ask": top.get("ask", 0),
                                    "oi": top.get("oi", 0),
                                    "volume": top.get("volume", 0),
                                    "spread_pct": top.get("spread_pct"),
                                    "token": tok,
                                    "symbol": sym,
                                    "reason": f"Ranked D4 #{top['score']}",
                                    "rank_score": top["score"],
                                }
                        else:
                            print("  [D3] NO ELIGIBLE candidate passed liquidity gate")
            except Exception as e:
                print(f"  [D] Chain error: {str(e)[:60]}")
        
        # PHASE H CRITICAL FIX: No fallback allowed
        # If chain module returned no eligible candidate, we do NOT trade.
        # This was previously bypassing the liquidity gate.
        print('  >>> ENTRY BLOCKED: NO_ELIGIBLE_OPTION_PASSED_GATES')
        print('  >>> Reason: chain/liquidity/ranking produced no tradeable strike')
        self.decision_state = 'BLOCKED'
        return None

    

    def run_single_session(self):
        # D2_safety_flags — hard refuse if any mode flag is misconfigured
        assert self.EXECUTION_MODE == "PAPER", "EXECUTION_MODE must be PAPER"
        assert self.BROKER_SUBMISSION is False, "BROKER_SUBMISSION must be False"
        assert self.LIVE_EXECUTION is False, "LIVE_EXECUTION must be False"
        
        if not self.is_running:
            return None
        
        if not self.reconnect_if_needed():
            return None
        
        spot = self.get_spot()
        if spot == 0:
            print(f"Cannot get {self.market} spot price")
            return None
        
        expiry = self.get_expiry()
        options, atm = self.get_options(spot, expiry)
        
        if not options:
            print(f"No {self.market} options available")
            return None
        
        sentiment = self.get_enhanced_sentiment(spot, options)
        print(f"\nFinal Decision: {sentiment}")
        
        if sentiment == 'NEUTRAL':
            print("⚠️ No strong signal. Skipping trade.")
            return None
        
        # Event gate - block if high-impact event within 10 min
        if self.calendar_engine:
            try:
                _evt = self.calendar_engine.minutes_to_next_high_impact(10)
                if _evt.get("block_entries"):
                    _names = ", ".join(e["name"] for e in _evt.get("events", []))
                    print(f'>>> SKIP: High-impact event within 10min: {_names}')
                    return None
            except Exception:
                pass
        
        # RE-ENTRY + DAILY LIMIT GATES (Phase H critical fix)
        from datetime import datetime as _dt2
        _now2 = _dt2.now()
        
        # Daily loss limit
        if self.daily_realized_loss <= -self.MAX_DAILY_NET_LOSS:
            print(f">>> SKIP: DAILY_LOSS_LIMIT_HIT (₹{self.daily_realized_loss:.0f})")
            return None
        
        # Daily trade count limit
        if self.daily_trade_count >= self.MAX_DAILY_TRADES:
            print(f">>> SKIP: DAILY_TRADE_LIMIT_HIT ({self.daily_trade_count})")
            return None
        
        # Same-direction stop streak — disable that direction
        if self.same_direction_stops >= self.MAX_CONSECUTIVE_SAME_DIR_STOPS:
            print(f">>> SKIP: {self.last_exit_direction}_DISABLED_AFTER_{self.same_direction_stops}_STOPS")
            return None
        
        # Cooldown after stop
        if self.last_exit_time is not None:
            _elapsed = (_now2 - self.last_exit_time).total_seconds()
            _needed = self.COOLDOWN_AFTER_STOP_SECONDS if self.same_direction_stops <= 1 else self.COOLDOWN_AFTER_2_STOPS_SECONDS
            if _elapsed < _needed:
                _remaining = int(_needed - _elapsed)
                print(f">>> SKIP: COOLDOWN_ACTIVE ({_remaining}s remaining after {self.same_direction_stops} stops)")
                return None
        
        # Phase gate - no new entries during close drain
        if not self.market_phase.can_enter():
            _p = self.market_phase.describe()
            print(f'>>> SKIP: Market phase {_p["phase"]} - no new entries ({_p["note"]})')
            return None
        
        trade = self.select_trade(sentiment, spot, options)
        
        if not trade:
            print("No trade selected")
            return None
        
        trade_id = f"TRD_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # ===== PHASE A1: Dynamic lot size from instrument master =====
        _lot_size, _lot_source = resolve_lot_size(
            self.contract_index,
            self.market,
            expiry,
            trade['strike'],
            trade['type']
        )
        
        print(f"\n  LOT_SIZE_LOOKUP:")
        print(f"    market={self.market} expiry={expiry} strike={trade['strike']} type={trade['type']}")
        print(f"    resolved_lot={_lot_size} source={_lot_source}")
        
        if _lot_size is None or _lot_size <= 0:
            print(f"  LOT_SIZE_EVIDENCE_UNAVAILABLE - refusing trade")
            self.decision_state = 'BLOCKED'
            return None
        
        # Use resolved lot size (overrides __init__ default)
        self.lot_size = _lot_size
        
        # ===== PHASE F: Realistic paper fill =====
        # D11_entry_full_quote - fetch live bid/ask (chain engine is LTP-only)
        _entry_quote = self._fetch_option_quote_full(trade["symbol"], trade["token"])
        _bid = float(_entry_quote.get("bid") or 0)
        _ask = float(_entry_quote.get("ask") or 0)
        _ltp = float(_entry_quote.get("ltp") or trade.get("entry") or 0)
        if _bid <= 0 or _ask <= 0 or _ask <= _bid:
            print(f"  ENTRY_FULL_QUOTE_INCOMPLETE: bid={_bid} ask={_ask} ltp={_ltp}")
            print(f"  Refusing trade - entry requires live full depth")
            self.decision_state = 'BLOCKED'
            return None
        _fill, _fill_status = self.capital_engine.compute_paper_fill(_bid, _ask, _ltp, direction="BUY")
        print(f"\n  [F1] PAPER_FILL:")
        print(f"        quoted_ltp=₹{_ltp:.2f} bid=₹{_bid:.2f} ask=₹{_ask:.2f}")
        if _fill is None or _fill_status != "OK":
            print(f"  EXECUTION_EVIDENCE_UNAVAILABLE: {_fill_status}")
            print(f"  Refusing trade - no valid executable quote")
            self.decision_state = 'BLOCKED'
            return None
        _paper_fill = _fill
        print(f"        simulated_buy_fill=₹{_paper_fill:.2f} (incl slippage)")
        
        # Affordability check
        _lots = self.capital_engine.compute_lot_size(_paper_fill, self.lot_size)
        print(f"        capital=₹{self.capital_engine.capital:,.0f} lot_size={self.lot_size}")
        print(f"        lots_affordable={_lots}")
        if _lots < 1:
            print(f"  CAPITAL_INSUFFICIENT - refusing trade")
            self.decision_state = 'BLOCKED'
            return None
        
        entry = _paper_fill  # Use simulated fill as entry
        t1_price = entry * (1 + self.T1_PERCENT/100)
        t2_price = entry * (1 + self.T2_PERCENT/100)
        t3_price = entry * (1 + self.T3_PERCENT/100)
        sl_price = entry * (1 - self.STOP_LOSS_PERCENT/100)
        
        active_trade = {
            'trade_id': trade_id,
            'market': self.market,
            'type': trade['type'],
            'strike': trade['strike'],
            'signal': trade['signal'],
            'entry': entry,
            'token': trade['token'],
            'symbol': trade['symbol'],
            'quantity': self.lot_size,
            'lot_size': self.lot_size,
            'entry_bid': _bid,
            'entry_ask': _ask,
            'entry_ltp': _ltp,
            'lot_size_source': _lot_source if '_lot_source' in dir() else 'unknown',
            'entry_time': datetime.now(),
            'current_price': entry,
            'pnl': 0,
            'pnl_pct': 0,
            'max_profit': 0,
            't1_price': t1_price,
            't2_price': t2_price,
            't3_price': t3_price,
            'sl_price': sl_price,
            'reason': trade['reason'],
            'status': 'OPEN',
            # D3_cert_eligible — entry-time certification contract
            'execution_mode': self.EXECUTION_MODE,
            'broker_submission': self.BROKER_SUBMISSION,
            'live_execution': self.LIVE_EXECUTION,
            'certification_eligible': (
                self.EXECUTION_MODE == "PAPER"
                and self.BROKER_SUBMISSION is False
                and self.LIVE_EXECUTION is False
                and self.market in ("NIFTY", "SENSEX")
                and _bid > 0 and _ask > 0 and _ask > _bid
                and self.lot_size > 0
            ),
        }
        
        self.active_trades[trade_id] = active_trade
        self.entry_spot = spot  # Track entry spot for invalidation
        # Phase F: register MFE/MAE tracker + init target state
        self.mfe_mae.register(trade_id, entry)
        active_trade['t1_hit'] = False
        active_trade['t2_hit'] = False
        active_trade['peak_price'] = entry
        active_trade['peak_bid'] = None  # D7_D9_design_b
        active_trade['trail_stop'] = None
        active_trade['entry_spot'] = spot
        self.total_trades += 1
        
        _notional = entry * self.lot_size
        print(f"\n{'='*60}")
        print(f"📊 {self.market} Trade: {trade['signal']} {trade['type']} {trade['strike']}")
        print(f"{'='*60}")
        print(f"Entry: ₹{entry:.2f}")
        print(f"Lot Size: {self.lot_size} (source: {_lot_source})")
        print(f"Notional: ₹{_notional:,.2f}")
        print(f"Stop Loss: ₹{sl_price:.2f} (-{self.STOP_LOSS_PERCENT}%)")
        print(f"T1: ₹{t1_price:.2f} (+{self.T1_PERCENT}%)")
        print(f"T2: ₹{t2_price:.2f} (+{self.T2_PERCENT}%)")
        print(f"T3: ₹{t3_price:.2f} (+{self.T3_PERCENT}%)")
        print(f"Will close at 3:28 PM if no target/SL hit")
        
        start_time = datetime.now()
        last_update = start_time
        
        while self.is_running and self.is_market_open():
            time.sleep(3)
            
            if trade_id not in self.active_trades:
                break
            
            if (datetime.now() - start_time).seconds % 60 == 0:
                if not self.reconnect_if_needed():
                    continue
            
            try:
                # D7_D9_design_b — one full-quote call per cycle: LTP + bid + ask
                quote = self._fetch_option_quote_full(trade['symbol'], trade['token'])
                current_ltp = quote.get('ltp') or 0
                current_bid = quote.get('bid')  # may be None
                current_price = current_ltp  # LTP drives pnl/threshold decisions
                
                # Track peak executable bid
                if current_bid is not None and current_bid > 0:
                    if active_trade.get('peak_bid') is None or current_bid > active_trade['peak_bid']:
                        active_trade['peak_bid'] = current_bid
                
                if current_price > 0:
                    
                    if current_price > 0:
                        if trade['signal'] == 'BUY':
                            pnl = (current_price - entry) * self.lot_size
                            pnl_pct = ((current_price - entry) / entry) * 100
                        else:
                            pnl = (entry - current_price) * self.lot_size
                            pnl_pct = ((entry - current_price) / entry) * 100
                        
                        active_trade['current_price'] = current_price
                        active_trade['pnl'] = pnl
                        active_trade['pnl_pct'] = pnl_pct
                        
                        if pnl > active_trade['max_profit']:
                            active_trade['max_profit'] = pnl
                        
                        
                        # ===== D7_D9_design_b — inline Design B trail (Reading B) =====
                        # T1 (+15% LTP) activates trail, does NOT exit.
                        # Trail = max(entry * 1.10, peak_bid * 0.95). Never below +10%.
                        # T3 (+50%) and SL (-5%) still exit hard.
                        try:
                            self.mfe_mae.update(trade_id, current_price)
                            if 'peak_price' not in active_trade or current_price > active_trade['peak_price']:
                                active_trade['peak_price'] = current_price
                            
                            _floor = entry * 1.10  # +10% premium lock
                            
                            # Activation: first time LTP pnl_pct crosses T1
                            if not active_trade.get('t1_hit') and pnl_pct >= self.T1_PERCENT:
                                active_trade['t1_hit'] = True
                                _pb = active_trade.get('peak_bid')
                                _init_stop = _floor
                                if _pb is not None:
                                    _init_stop = max(_floor, _pb * 0.95)
                                active_trade['trail_stop'] = _init_stop
                                print(f'  [T1] trail ACTIVE floor={_floor:.2f} stop={_init_stop:.2f}')
                            
                            # Update: after T1, chase peak_bid with 5% step, floored at +10%
                            if active_trade.get('t1_hit'):
                                _pb = active_trade.get('peak_bid')
                                if _pb is not None:
                                    _cand = max(_floor, _pb * 0.95)
                                    if _cand > (active_trade.get('trail_stop') or 0):
                                        active_trade['trail_stop'] = _cand
                            
                            # Exit: current bid at or below trail stop
                            if active_trade.get('t1_hit'):
                                _stop = active_trade.get('trail_stop')
                                if _stop is not None and current_bid is not None:
                                    if current_bid <= _stop:
                                        _exit_px, _pnl, _pnl_pct = self._bid_based_exit(
                                            entry, current_bid, current_price, self.lot_size)
                                        print(f'  TRAIL STOP HIT: bid={current_bid:.2f} stop={_stop:.2f} exit={_exit_px:.2f}')
                                        self.close_position(trade_id, _exit_px, 'TRAIL_STOP', _pnl, _pnl_pct)
                                        break
                        except Exception as _e:
                            print(f'[F] policy error: {str(_e)[:60]}')
                        
                        # UNDERLYING INVALIDATION CHECK
                        # If spot moves >0.5% against our position, exit early
                        if self.entry_spot and self.entry_spot > 0:
                            try:
                                current_spot = self.get_spot()
                                if current_spot > 0:
                                    spot_move_pct = ((current_spot - self.entry_spot) / self.entry_spot) * 100
                                    
                                    # If long CE and spot fell >0.5%, invalidate
                                    if trade['type'] == 'CE' and spot_move_pct < -0.5:
                                        print(f'\n⚠️ UNDERLYING INVALIDATION: spot {spot_move_pct:+.2f}%')
                                        _exit_px, _pnl, _pnl_pct = self._bid_based_exit(entry, current_bid, current_price, self.lot_size)
                                        self.close_position(trade_id, _exit_px, 'SPOT_INVALIDATED', _pnl, _pnl_pct)
                                        self.stop_losses += 1
                                        break
                                    # If long PE and spot rose >0.5%, invalidate
                                    elif trade['type'] == 'PE' and spot_move_pct > 0.5:
                                        print(f'\n⚠️ UNDERLYING INVALIDATION: spot {spot_move_pct:+.2f}%')
                                        _exit_px, _pnl, _pnl_pct = self._bid_based_exit(entry, current_bid, current_price, self.lot_size)
                                        self.close_position(trade_id, _exit_px, 'SPOT_INVALIDATED', _pnl, _pnl_pct)
                                        self.stop_losses += 1
                                        break
                            except Exception:
                                pass
                        
                        # D7_D9_design_b — T1/T2 no longer exit here (T1 activates trail above)
                        if pnl_pct >= self.T3_PERCENT:
                            _exit_px, _pnl, _pnl_pct = self._bid_based_exit(
                                entry, current_bid, current_price, self.lot_size)
                            print(f'  T3 REACHED: ltp_pct={pnl_pct:.2f}% exit={_exit_px:.2f}')
                            self.close_position(trade_id, _exit_px, 'T3_50%', _pnl, _pnl_pct)
                            self.t3_hits += 1
                            break
                        elif pnl_pct <= -self.STOP_LOSS_PERCENT:
                            _exit_px, _pnl, _pnl_pct = self._bid_based_exit(
                                entry, current_bid, current_price, self.lot_size)
                            self.close_position(trade_id, _exit_px, 'STOP_LOSS', _pnl, _pnl_pct)
                            self.stop_losses += 1
                            break
                        
                        if (datetime.now() - last_update).seconds >= 30:
                            elapsed = (datetime.now() - start_time).seconds // 60
                            print(f"\n[{elapsed}min] Price: ₹{current_price:.2f} | P&L: {pnl_pct:.2f}%")
                            last_update = datetime.now()
            
            except Exception as e:
                pass
        
        if trade_id in self.active_trades:
            try:
                # D7_D9_design_b — session-close uses bid-based exit too
                _quote = self._fetch_option_quote_full(trade['symbol'], trade['token'])
                _ltp = _quote.get('ltp') or 0
                _bid = _quote.get('bid')
                if _ltp > 0:
                    _exit_px, _pnl, _pnl_pct = self._bid_based_exit(
                        entry, _bid, _ltp, self.lot_size)
                    self.close_position(trade_id, _exit_px, 'MARKET_CLOSE_3:28PM', _pnl, _pnl_pct)
                    self.market_close_exits += 1
            except Exception as _e:
                print(f"  [session-close] err: {str(_e)[:60]}")
        
        return {
            'market': self.market,
            'type': trade['type'],
            'pnl': pnl if 'pnl' in locals() else 0,
            'win': pnl > 0 if 'pnl' in locals() else False
        }
    
    def close_position(self, trade_id, exit_price, reason, pnl, pnl_pct):
        trade = self.active_trades[trade_id]
        trade['exit_price'] = exit_price
        trade['exit_reason'] = reason
        trade['pnl'] = pnl
        trade['pnl_pct'] = pnl_pct
        trade['exit_time'] = datetime.now()
        trade['status'] = 'CLOSED'
        
        # ===== PHASE F: MFE/MAE + realistic net P&L =====
        try:
            mfe_mae = self.mfe_mae.snapshot(trade_id)
            trade['mfe'] = mfe_mae.get('max_favorable', 0)
            trade['mae'] = mfe_mae.get('max_adverse', 0)
            trade['peak_pnl_pct'] = round(mfe_mae.get('peak_pnl_pct', 0), 2)
            trade['trough_pnl_pct'] = round(mfe_mae.get('trough_pnl_pct', 0), 2)
            
            # Net P&L after costs
            entry_price = trade.get('entry', 0)
            qty = trade.get('quantity', 0)
            direction = trade.get('signal', 'BUY')
            if entry_price > 0 and qty > 0:
                net_info = self.capital_engine.compute_net_pnl(
                    entry_price, exit_price, qty, direction
                )
                trade['gross_pnl'] = net_info['gross_pnl']
                trade['costs_total'] = net_info['costs']['total']
                trade['cost_breakdown'] = net_info['costs']
                trade['net_pnl'] = net_info['net_pnl']
                trade['net_pnl_pct'] = net_info['net_pnl_pct']
                
                print(f'\n  [F] TRADE RECONCILIATION:')
                print(f'      MFE: ₹{trade["mfe"]:.2f} ({trade["peak_pnl_pct"]}%)')
                print(f'      MAE: ₹{trade["mae"]:.2f} ({trade["trough_pnl_pct"]}%)')
                print(f'      Gross P&L: ₹{trade["gross_pnl"]:.2f}')
                print(f'      Costs: ₹{trade["costs_total"]:.2f}')
                print(f'      NET P&L: ₹{trade["net_pnl"]:.2f} ({trade["net_pnl_pct"]}%)')
        except Exception as _e:
            print(f'  [F] reconciliation error: {str(_e)[:60]}')
        
        # ===== PHASE G2: Record outcome to ledger =====
        try:
            self.outcome_ledger.record(trade)
            print(f'  [G2] Outcome recorded to {self.market.lower()}_outcomes.jsonl')
            
            # Phase H: re-entry state tracking
            self.last_exit_time = datetime.now()
            # D8_same_direction_fix — capture prior direction BEFORE overwrite
            _prev_exit_direction = self.last_exit_direction
            self.last_exit_direction = trade.get('type', 'UNKNOWN')
            self.daily_trade_count += 1
            _net = trade.get('net_pnl', 0) or 0
            self.daily_realized_loss += _net
            
            if reason == 'STOP_LOSS':
                if _prev_exit_direction is not None and trade.get('type') == _prev_exit_direction:
                    self.same_direction_stops += 1
                else:
                    self.same_direction_stops = 1   # new direction streak starts at 1
            else:
                self.same_direction_stops = 0
            
            print(f'  [Re-entry] Same-dir stops: {self.same_direction_stops} | Daily trades: {self.daily_trade_count} | Daily P&L: ₹{self.daily_realized_loss:.0f}')
        except Exception as _e:
            print(f'  [G2] outcome ledger error: {str(_e)[:60]}')
        
        # D10_net_pnl - running total uses net P&L when available
        _pnl_for_total = trade.get('net_pnl')
        if _pnl_for_total is None:
            _pnl_for_total = pnl
        self.total_pnl += _pnl_for_total
        
        if _pnl_for_total > 0:
            self.winning_trades += 1
            self.consecutive_wins += 1
            self.consecutive_losses = 0
        else:
            self.losing_trades += 1
            self.consecutive_losses += 1
            self.consecutive_wins = 0
        
        self.completed_trades.append(trade)
        del self.active_trades[trade_id]
        
        print(f"\n{'='*60}")
        print(f"📊 Position Closed: {reason}")
        print(f"{'='*60}")
        print(f"{self.market} {trade['signal']} {trade['type']} {trade['strike']}")
        print(f"Entry: ₹{trade['entry']:.2f} → Exit: ₹{exit_price:.2f}")
        print(f"P&L: ₹{pnl:.2f} ({pnl_pct:.2f}%)")
        print(f"Total P&L: ₹{self.total_pnl:.2f}")
    
    # ===== D7_D9_design_b — full quote + bid-based exits =====
    def _fetch_option_quote_full(self, symbol, token):
        """One REST call: LTP + best bid + best ask. None for missing fields."""
        try:
            self.rate_limiter.wait_if_needed("ltp_data")
            resp = self.obj.getMarketData(
                "FULL", {self.option_exchange: [str(token)]}
            )
            if not resp or not resp.get("data"):
                return {"ltp": None, "bid": None, "ask": None}
            rows = resp["data"].get("fetched") or []
            row = None
            for r in rows:
                if str(r.get("symbolToken")) == str(token):
                    row = r
                    break
            if row is None:
                return {"ltp": None, "bid": None, "ask": None}
            ltp = row.get("ltp")
            try:
                ltp = float(ltp) if ltp is not None else None
            except (TypeError, ValueError):
                ltp = None
            depth = row.get("depth") or {}
            bids = depth.get("buy") or []
            asks = depth.get("sell") or []
            bid = None
            ask = None
            if bids and bids[0].get("price"):
                try: bid = float(bids[0]["price"])
                except (TypeError, ValueError): bid = None
            if asks and asks[0].get("price"):
                try: ask = float(asks[0]["price"])
                except (TypeError, ValueError): ask = None
            return {"ltp": ltp, "bid": bid, "ask": ask}
        except Exception as e:
            print(f"  [FULL_QUOTE] err: {str(e)[:60]}")
            return {"ltp": None, "bid": None, "ask": None}

    def _exit_price_from_bid(self, bid):
        """Exit fill = bid minus adverse slippage (same % as entry)."""
        if bid is None or bid <= 0:
            return None
        slip = bid * (self.capital_engine.slippage_pct / 100.0)
        return round(bid - slip, 2)

    def _bid_based_exit(self, entry, exit_bid, fallback_ltp, lot_size):
        """(exit_px, pnl, pnl_pct) using executable bid. Falls back to LTP with warning."""
        exit_px = self._exit_price_from_bid(exit_bid)
        if exit_px is None:
            exit_px = fallback_ltp
            print(f"  [D7] WARN: no bid available, using LTP {exit_px:.2f} as exit")
        pnl = (exit_px - entry) * lot_size
        pnl_pct = ((exit_px - entry) / entry) * 100 if entry else 0.0
        return exit_px, pnl, pnl_pct
    # ===== end D7_D9 helpers =====

    def run_daily_sessions(self):
        # Wait for market to be open (works for overnight)
        while self.is_running and not self.is_market_open():
            now = datetime.now()
            if now < self.MARKET_OPEN:
                wait_seconds = (self.MARKET_OPEN - now).seconds
                hours = wait_seconds // 3600
                minutes = (wait_seconds % 3600) // 60
                print(f"\nWaiting for market open... {hours}h {minutes}m remaining")
                time.sleep(60)
            else:
                next_open = self.MARKET_OPEN + timedelta(days=1)
                wait_seconds = (next_open - now).seconds
                hours = wait_seconds // 3600
                minutes = (wait_seconds % 3600) // 60
                print(f"\nMarket closed. Next open in {hours}h {minutes}m")
                time.sleep(60)
        
        if not self.is_running:
            return
        
        print("\nMarket is open! Starting trading...")
    def show_daily_summary(self):
        print(f"\n{'='*60}")
        print(f"{self.market} DAILY SUMMARY - {datetime.now().strftime('%Y-%m-%d')}")
        print(f"{'='*60}")
        print(f"Sessions Today: {self.sessions_completed_today}")
        print(f"Total Sessions: {self.current_session}/{self.total_sessions}")
        print(f"Total P&L: ₹{self.total_pnl:.2f}")
        if self.total_trades > 0:
            print(f"Win Rate: {(self.winning_trades / self.total_trades * 100):.1f}%")
        
        if self.current_session >= self.total_sessions:
            print(f"\n🎉 {self.market} TESTING COMPLETE!")
            self.generate_certification()
        else:
            remaining = self.total_sessions - self.current_session
            print(f"\nRemaining sessions: {remaining}")
            print(f"Next session will run tomorrow at market open.")
    
    def generate_certification(self):
        certification = {
            'market': self.market,
            'completion_date': datetime.now().isoformat(),
            'total_sessions': self.total_sessions,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0,
            'total_pnl': self.total_pnl,
            't1_hits': self.t1_hits,
            't2_hits': self.t2_hits,
            't3_hits': self.t3_hits,
            'stop_losses': self.stop_losses,
            'market_close_exits': self.market_close_exits,
            'average_pnl_per_trade': self.total_pnl / self.total_trades if self.total_trades > 0 else 0
        }
        
        filename = f"data/paper_trades/{self.market.lower()}_certification.json"
        with open(filename, 'w') as f:
            json.dump(certification, f, indent=2)
        
        print(f"\n📜 Certification saved to {filename}")
    
    def show_summary(self):
        print("\n" + "=" * 60)
        print(f"{self.market} TRADING SUMMARY")
        print("=" * 60)
        
        print(f"\nTotal Trades: {self.total_trades}")
        print(f"Winning: {self.winning_trades}")
        print(f"Losing: {self.losing_trades}")
        
        if self.total_trades > 0:
            win_rate = (self.winning_trades / self.total_trades) * 100
            print(f"Win Rate: {win_rate:.1f}%")
        
        print(f"\nExit Statistics:")
        print(f"  T1 (15%): {self.t1_hits} times")
        print(f"  T2 (30%): {self.t2_hits} times")
        print(f"  T3 (50%): {self.t3_hits} times")
        print(f"  Stop Loss: {self.stop_losses} times")
        print(f"  Market Close: {self.market_close_exits} times")
        
        print(f"\nTotal P&L: ₹{self.total_pnl:.2f}")
        print(f"Sessions: {self.current_session}/{self.total_sessions}")

def main():
    print("=" * 60)
    print("UNIFIED TRADING BOT")
    print("=" * 60)
    print("Select Market:")
    print("1. NIFTY")
    print("2. SENSEX")
    
    market_choice = input("\nChoice (1-2): ")
    
    if market_choice == '1':
        market = 'NIFTY'
    elif market_choice == '2':
        market = 'SENSEX'
    else:
        print("Invalid choice. Defaulting to NIFTY")
        market = 'NIFTY'
    
    bot = UnifiedTradingBot(market)
    
    has_previous_state = bot.load_state()
    
    if not bot.connect_with_retry():
        print("Failed to connect")
        return
    
    bot.load_instruments()
    print(f"✅ Ready for {market} trading")
    
    if bot.current_session >= bot.total_sessions:
        print(f"\n🎉 {market} testing already completed!")
        bot.show_summary()
        return
    
    if has_previous_state and bot.current_session > 0:
        print(f"\n🔄 Continue from session {bot.current_session + 1}/{bot.total_sessions}?")
        resume = input("(y/n): ").lower()
        
        if resume == 'y':
            if bot.is_market_open():
                bot.run_daily_sessions()
            else:
                print(f"\n⏰ Market is closed.")
                print(f"Will auto-start at market open (9:15 AM)")
                bot.wait_for_market_open()
                bot.run_daily_sessions()
            return
    
    while bot.is_running:
        print("\n" + "=" * 60)
        print(f"{market} UNIFIED TRADING BOT")
        print(f"T1: {bot.T1_PERCENT}% | T2: {bot.T2_PERCENT}% | T3: {bot.T3_PERCENT}%")
        print(f"Stop Loss: {bot.STOP_LOSS_PERCENT}%")
        print(f"Close at: 3:28 PM")
        print(f"Progress: {bot.current_session}/{bot.total_sessions} sessions")
        print("=" * 60)
        print("1. Start Auto Trading (waits for market open)")
        print("2. Run Today's Sessions")
        print("3. View Summary")
        print("4. Generate Certification")
        print("5. Exit")
        
        choice = input("\nChoice: ")
        
        if choice == '1':
            bot.run_daily_sessions()
        elif choice == '2':
            if bot.is_market_open():
                bot.run_daily_sessions()
            else:
                print("Market is closed. Use option 1 for auto-start.")
        elif choice == '3':
            bot.show_summary()
        elif choice == '4':
            bot.generate_certification()
        elif choice == '5':
            bot.save_state()
            print("Goodbye!")
            break

if __name__ == "__main__":
    main()
