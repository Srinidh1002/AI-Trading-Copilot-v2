# services/trading/pnl_tracker.py
# FIXED: Correct P&L calculation

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)

class PnLTracker:
    """Tracks Daily, Weekly, Monthly P&L - FIXED CALCULATION"""
    
    def __init__(self, data_dir: str = "data/pnl"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.daily_pnl = {'profit': 0, 'loss': 0, 'trades': 0, 'win_rate': 0}
        self.weekly_pnl = {'profit': 0, 'loss': 0, 'trades': 0, 'win_rate': 0}
        self.monthly_pnl = {'profit': 0, 'loss': 0, 'trades': 0, 'win_rate': 0}
        
        self.trade_history = []  # Store all trades for accurate calculations
        
        self.load_pnl_data()
        
    def load_pnl_data(self):
        """Load existing P&L data"""
        try:
            daily_file = self.data_dir / f"daily_{datetime.now().strftime('%Y-%m-%d')}.json"
            if daily_file.exists():
                with open(daily_file, 'r') as f:
                    data = json.load(f)
                    self.daily_pnl = data.get('metrics', self.daily_pnl)
                    self.trade_history = data.get('trades', [])
        except:
            pass
    
    def update_pnl(self, trade_data: Dict):
        """Update P&L with new trade - FIXED CALCULATION"""
        
        # Extract trade details
        entry_price = trade_data.get('entry_price', 0)
        exit_price = trade_data.get('exit_price', 0)
        quantity = trade_data.get('quantity', 0)
        symbol = trade_data.get('symbol', '')
        option_type = trade_data.get('option_type', '')
        
        # CORRECT P&L CALCULATION
        if option_type == 'CALL':
            # For CALL: Profit = (Exit - Entry) × Quantity
            pnl_per_share = exit_price - entry_price
        elif option_type == 'PUT':
            # For PUT: Profit = (Entry - Exit) × Quantity
            pnl_per_share = entry_price - exit_price
        else:
            # Default
            pnl_per_share = exit_price - entry_price
        
        pnl_absolute = pnl_per_share * quantity
        
        # Calculate percentage
        pnl_percent = (pnl_per_share / entry_price) * 100 if entry_price > 0 else 0
        
        # Create trade record with correct values
        trade_record = {
            'symbol': symbol,
            'option_type': option_type,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'quantity': quantity,
            'pnl_per_share': pnl_per_share,
            'pnl_absolute': pnl_absolute,
            'pnl_percent': pnl_percent,
            'timestamp': datetime.now().isoformat(),
            'tier': trade_data.get('tier', 'FINAL'),
            'reason': trade_data.get('reason', '')
        }
        
        self.trade_history.append(trade_record)
        
        # Update daily
        self.daily_pnl['trades'] += 1
        if pnl_absolute > 0:
            self.daily_pnl['profit'] += pnl_absolute
        else:
            self.daily_pnl['loss'] += abs(pnl_absolute)
        self.daily_pnl['win_rate'] = self._calculate_win_rate(self.daily_pnl)
        
        # Update weekly
        self.weekly_pnl['trades'] += 1
        if pnl_absolute > 0:
            self.weekly_pnl['profit'] += pnl_absolute
        else:
            self.weekly_pnl['loss'] += abs(pnl_absolute)
        self.weekly_pnl['win_rate'] = self._calculate_win_rate(self.weekly_pnl)
        
        # Update monthly
        self.monthly_pnl['trades'] += 1
        if pnl_absolute > 0:
            self.monthly_pnl['profit'] += pnl_absolute
        else:
            self.monthly_pnl['loss'] += abs(pnl_absolute)
        self.monthly_pnl['win_rate'] = self._calculate_win_rate(self.monthly_pnl)
        
        # Log the trade
        logger.info(f"[P&L] {symbol} {option_type} #{trade_data.get('position_number', 1)}: P&L ₹{pnl_absolute:,.2f} ({pnl_percent:+.2f}%)")
        
        # Save to file
        self._save_pnl_data()
    
    def _calculate_win_rate(self, pnl_data: Dict) -> float:
        """Calculate win rate from P&L data"""
        trades = pnl_data.get('trades', 0)
        if trades == 0:
            return 0
        profit = pnl_data.get('profit', 0)
        loss = pnl_data.get('loss', 0)
        total = profit + loss
        if total == 0:
            return 0
        win_rate = (profit / total) * 100
        return round(win_rate, 1)
    
    def _save_pnl_data(self):
        """Save P&L data to files"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            
            # Daily
            daily_file = self.data_dir / f"daily_{today}.json"
            with open(daily_file, 'w') as f:
                json.dump({
                    'metrics': self.daily_pnl,
                    'trades': self.trade_history[-20:]  # Keep last 20 trades
                }, f, indent=2)
            
            # Weekly
            week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime('%Y-%m-%d')
            weekly_file = self.data_dir / f"weekly_{week_start}.json"
            with open(weekly_file, 'w') as f:
                json.dump(self.weekly_pnl, f, indent=2)
            
            # Monthly
            month_start = datetime.now().strftime('%Y-%m')
            monthly_file = self.data_dir / f"monthly_{month_start}.json"
            with open(monthly_file, 'w') as f:
                json.dump(self.monthly_pnl, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving P&L data: {e}")
    
    def get_pnl_summary(self) -> Dict:
        """Get P&L summary"""
        return {
            'daily': self.daily_pnl,
            'weekly': self.weekly_pnl,
            'monthly': self.monthly_pnl,
            'net_daily': self.daily_pnl.get('profit', 0) - self.daily_pnl.get('loss', 0),
            'net_weekly': self.weekly_pnl.get('profit', 0) - self.weekly_pnl.get('loss', 0),
            'net_monthly': self.monthly_pnl.get('profit', 0) - self.monthly_pnl.get('loss', 0),
            'trade_history': self.trade_history[-10:]  # Last 10 trades
        }
    
    def get_trade_history(self) -> List[Dict]:
        """Get all trades"""
        return self.trade_history
    
    def get_recent_trades(self, count: int = 10) -> List[Dict]:
        """Get recent trades"""
        return self.trade_history[-count:] if self.trade_history else []
    
    def generate_report(self) -> str:
        """Generate P&L report"""
        summary = self.get_pnl_summary()
        
        # Get recent trades
        recent = self.get_recent_trades(5)
        recent_text = ""
        for trade in recent:
            recent_text += f"  {trade['symbol']} {trade['option_type']}: ₹{trade['pnl_absolute']:,.2f} ({trade['pnl_percent']:+.2f}%)\n"
        
        report = f"""
========================================
[STATS] P&L SUMMARY REPORT
========================================
[DATE] Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

[UP] DAILY:
  Total Trades: {summary['daily'].get('trades', 0)}
  Profit: ₹{summary['daily'].get('profit', 0):,.2f}
  Loss: ₹{summary['daily'].get('loss', 0):,.2f}
  Net: ₹{summary['net_daily']:,.2f}
  Win Rate: {summary['daily'].get('win_rate', 0):.1f}%

[STATS] WEEKLY:
  Total Trades: {summary['weekly'].get('trades', 0)}
  Profit: ₹{summary['weekly'].get('profit', 0):,.2f}
  Loss: ₹{summary['weekly'].get('loss', 0):,.2f}
  Net: ₹{summary['net_weekly']:,.2f}
  Win Rate: {summary['weekly'].get('win_rate', 0):.1f}%

[UP] MONTHLY:
  Total Trades: {summary['monthly'].get('trades', 0)}
  Profit: ₹{summary['monthly'].get('profit', 0):,.2f}
  Loss: ₹{summary['monthly'].get('loss', 0):,.2f}
  Net: ₹{summary['net_monthly']:,.2f}
  Win Rate: {summary['monthly'].get('win_rate', 0):.1f}%

[NOTE] RECENT TRADES:
{recent_text}
========================================
"""
        return report
