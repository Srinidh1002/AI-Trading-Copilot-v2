# services/reporting/paper_certification_daily_report.py
# Daily report generator for paper certification

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class PaperCertificationDailyReport:
    """Generate daily paper certification reports."""
    
    def __init__(self):
        self.report_dir = Path("data/reports/eod")
        self.report_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_report(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a daily report from trading data."""
        try:
            report = {
                'date': datetime.now().strftime("%Y-%m-%d"),
                'timestamp': datetime.now().isoformat(),
                'summary': {
                    'total_trades': data.get('total_positions', 0),
                    'open_positions': data.get('open_positions', 0),
                    'total_deployed': data.get('total_deployed', 0),
                    'usage_percent': data.get('usage_percent', 0),
                    'winning_trades': data.get('winning_trades', 0),
                    'losing_trades': data.get('losing_trades', 0),
                    'win_rate': data.get('win_rate', 0)
                },
                'positions': data.get('positions', []),
                'nifty_stats': {},
                'sensex_stats': {}
            }
            
            # Calculate per-symbol stats
            for pos in report['positions']:
                symbol = pos.get('symbol')
                if symbol == 'NIFTY':
                    if 'nifty_trades' not in report['nifty_stats']:
                        report['nifty_stats']['nifty_trades'] = 0
                        report['nifty_stats']['nifty_wins'] = 0
                        report['nifty_stats']['nifty_pnl'] = 0
                    report['nifty_stats']['nifty_trades'] += 1
                    if pos.get('pnl', 0) > 0:
                        report['nifty_stats']['nifty_wins'] += 1
                    report['nifty_stats']['nifty_pnl'] += pos.get('pnl', 0)
                
                elif symbol == 'SENSEX':
                    if 'sensex_trades' not in report['sensex_stats']:
                        report['sensex_stats']['sensex_trades'] = 0
                        report['sensex_stats']['sensex_wins'] = 0
                        report['sensex_stats']['sensex_pnl'] = 0
                    report['sensex_stats']['sensex_trades'] += 1
                    if pos.get('pnl', 0) > 0:
                        report['sensex_stats']['sensex_wins'] += 1
                    report['sensex_stats']['sensex_pnl'] += pos.get('pnl', 0)
            
            # Save report
            report_file = self.report_dir / f"daily_report_{report['date']}.json"
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            
            logger.info(f"[REPORT] Daily report saved: {report_file}")
            return report
            
        except Exception as e:
            logger.error(f"[REPORT] Failed to generate report: {e}")
            return {}
    
    async def generate(self, engine_stats: Dict[str, Any]) -> Dict[str, Any]:
        """Async wrapper for generate_report."""
        return self.generate_report(engine_stats)
