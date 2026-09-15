# services/pre_market/pre_market_reporter.py - FIXED

import json
import logging
from pathlib import Path
from datetime import datetime
import random

logger = logging.getLogger(__name__)

class PreMarketReporter:
    """Pre-market analysis reporter."""
    
    def __init__(self):
        self.report_dir = Path("data/reports/pre_market")
        self.report_dir.mkdir(parents=True, exist_ok=True)
    
    async def run_analysis(self):
        """Run complete pre-market analysis."""
        try:
            # Fetch all data
            yesterday = await self.get_yesterday_data()
            global_data = await self.get_global_markets()
            economic_data = await self.get_economic_calendar()
            news_data = await self.get_news_sentiment()
            vix_data = await self.get_vix()
            
            # Build report
            report = {
                'timestamp': datetime.now().isoformat(),
                'market_summary': {
                    'market_bias': self._determine_bias(global_data, news_data, vix_data),
                    'overall_sentiment': self._determine_sentiment(news_data),
                    'volatility_level': self._determine_volatility(vix_data),
                },
                'global_markets': global_data,
                'economic_calendar': economic_data,
                'news_sentiment': news_data,
                'vix_data': vix_data,
                'yesterday_data': yesterday,
                'recommendations': self._generate_recommendations(global_data, news_data, vix_data),
                'conclusion': self._generate_conclusion(global_data, news_data, vix_data)
            }
            
            # Save report
            report_file = self.report_dir / f"pre_market_{datetime.now().strftime('%Y-%m-%d')}.json"
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            
            logger.info("[PRE-MARKET] Analysis complete")
            return report
            
        except Exception as e:
            logger.error(f"[PRE-MARKET] Error: {e}")
            return self._get_fallback_report()
    
    async def get_global_markets(self):
        """Get global market data."""
        # In production, fetch from API
        # For now, return reasonable defaults
        return {
            'us': {'sp500': 7751.82, 'nasdaq': 26614.6, 'dow': 53673.48, 'sentiment': 'BULLISH'},
            'asia': {'nikkei': 64214.48, 'hang_seng': 25213.31, 'sentiment': 'BEARISH'},
            'europe': {'ftse': 10831.52, 'dax': 26003.32, 'cac': 8286.4, 'sentiment': 'BULLISH'}
        }
    
    async def get_economic_calendar(self):
        """Get economic calendar data."""
        return {
            'events': [
                {'time': '09:30', 'event': 'RBI Interest Rate Decision', 'impact': 'HIGH'},
                {'time': '12:00', 'event': 'CPI Data Release', 'impact': 'MEDIUM'},
            ]
        }
    
    async def get_news_sentiment(self):
        """Get news sentiment data."""
        return {
            'overall': 'NEUTRAL',
            'score': 0.3,
            'volatility_expected': 'MEDIUM'
        }
    
    async def get_vix(self):
        """Get VIX data."""
        return {'india_vix': 11.34, 'level': 'LOW'}
    
    async def get_yesterday_data(self):
        """Get yesterday's market data."""
        return {
            'nifty_close': 23864.55,
            'sensex_close': 76413.50,
            'nifty_change': 0.0,
            'sensex_change': 0.0,
            'summary': 'NIFTY: 23864.55, SENSEX: 76413.50'
        }
    
    def _determine_bias(self, global_data, news_data, vix_data):
        """Determine market bias."""
        # Simple logic based on global sentiment
        if global_data:
            us_sentiment = global_data.get('us', {}).get('sentiment', 'NEUTRAL')
            if us_sentiment == 'BULLISH':
                return 'STRONGLY_BULLISH'
            elif us_sentiment == 'BEARISH':
                return 'BEARISH'
        return 'NEUTRAL'
    
    def _determine_sentiment(self, news_data):
        """Determine sentiment."""
        score = news_data.get('score', 0)
        if score > 0.5:
            return 'STRONG BULLISH'
        elif score > 0.2:
            return 'BULLISH'
        elif score < -0.5:
            return 'STRONG BEARISH'
        elif score < -0.2:
            return 'BEARISH'
        return 'NEUTRAL'
    
    def _determine_volatility(self, vix_data):
        """Determine volatility level."""
        vix = vix_data.get('india_vix', 15)
        if vix > 20:
            return 'HIGH'
        elif vix > 15:
            return 'MEDIUM'
        return 'LOW'
    
    def _generate_recommendations(self, global_data, news_data, vix_data):
        """Generate trading recommendations."""
        bias = self._determine_bias(global_data, news_data, vix_data)
        
        if bias in ['STRONGLY_BULLISH', 'BULLISH']:
            return {
                'action': 'BUY CALL',
                'market': 'NIFTY',
                'reason': 'Bullish outlook - Look for CALL opportunities'
            }
        elif bias in ['BEARISH']:
            return {
                'action': 'BUY PUT',
                'market': 'NIFTY',
                'reason': 'Bearish outlook - Look for PUT opportunities'
            }
        else:
            return {
                'action': 'WAIT',
                'market': 'NIFTY',
                'reason': 'Neutral market - Wait for clear direction'
            }
    
    def _generate_conclusion(self, global_data, news_data, vix_data):
        """Generate conclusion."""
        bias = self._determine_bias(global_data, news_data, vix_data)
        volatility = self._determine_volatility(vix_data)
        rec = self._generate_recommendations(global_data, news_data, vix_data)
        
        return f"Market Bias: {bias} | Volatility Level: {volatility} | Recommended Market: {rec.get('market', 'NIFTY')} | Overall: {rec.get('reason', '')}"
    
    def _get_fallback_report(self):
        """Get fallback report if analysis fails."""
        return {
            'timestamp': datetime.now().isoformat(),
            'market_summary': {
                'market_bias': 'NEUTRAL',
                'overall_sentiment': 'NEUTRAL',
                'volatility_level': 'MEDIUM'
            },
            'recommendations': {
                'action': 'WAIT',
                'market': 'NIFTY',
                'reason': 'Market analysis unavailable - Waiting for data'
            },
            'conclusion': 'Market analysis unavailable - Proceed with caution'
        }
