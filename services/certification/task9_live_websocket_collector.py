# services/certification/task9_live_websocket_collector.py - Task 9 Certification

import asyncio
import logging
import json
import sys
import os
from pathlib import Path
from datetime import datetime, time
import pytz

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from services.auth.auth_manager import AuthManager
from services.market.websocket_collector import WebSocketCollector
from services.trading.paper_engine import PaperTradingEngine

logger = logging.getLogger(__name__)


class Task9Certification:
    """Task 9 Certification runner."""
    
    def __init__(self, persistence_root: str = "data/task9", live_stream_root: str = "data/task9/live_stream"):
        self.persistence_root = Path(persistence_root)
        self.live_stream_root = Path(live_stream_root)
        self.persistence_root.mkdir(parents=True, exist_ok=True)
        self.live_stream_root.mkdir(parents=True, exist_ok=True)
        
        self.certification = {
            "NIFTY": {"countable": 0, "total": 0, "trades": []},
            "SENSEX": {"countable": 0, "total": 0, "trades": []}
        }
        self.required = 100
        self.is_running = False
        self.trade_count = 0
        
        # Initialize components
        self.auth = AuthManager()
        self.collector = WebSocketCollector()
        self.engine = PaperTradingEngine(self.collector)
        
        # Track decisions
        self.decisions = {"NO_TRADE": 0, "WAIT": 0, "TRADE": 0}
        
        logger.info("=" * 60)
        logger.info("  TASK 9 CERTIFICATION - LIVE WEBSOCKET COLLECTOR")
        logger.info(f"  NIFTY Required: {self.required}")
        logger.info(f"  SENSEX Required: {self.required}")
        logger.info("=" * 60)
    
    async def run(self):
        """Run the certification process."""
        logger.info("🚀 Starting Task 9 Certification...")
        self.is_running = True
        
        # Connect to WebSocket
        await self.collector.connect()
        
        # Start engine
        await self.engine.start()
        
        # Monitor certification progress
        while self.is_running:
            self._check_certification_progress()
            await asyncio.sleep(10)
        
        self._print_summary()
    
    def _check_certification_progress(self):
        """Check and log certification progress."""
        nifty_count = self.certification["NIFTY"]["countable"]
        sensex_count = self.certification["SENSEX"]["countable"]
        
        if nifty_count >= self.required and sensex_count >= self.required:
            logger.info("=" * 60)
            logger.info("  🎉 CERTIFICATION COMPLETE!")
            logger.info(f"  NIFTY: {nifty_count}/{self.required}")
            logger.info(f"  SENSEX: {sensex_count}/{self.required}")
            logger.info("=" * 60)
            self.is_running = False
    
    def _print_summary(self):
        """Print certification summary."""
        logger.info("=" * 60)
        logger.info("  📊 TASK 9 CERTIFICATION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"  NIFTY Countable: {self.certification['NIFTY']['countable']}/{self.required}")
        logger.info(f"  SENSEX Countable: {self.certification['SENSEX']['countable']}/{self.required}")
        logger.info(f"  Total Trades: {self.trade_count}")
        logger.info(f"  NO_TRADE: {self.decisions['NO_TRADE']}")
        logger.info(f"  WAIT: {self.decisions['WAIT']}")
        logger.info("=" * 60)
        
        # Save certification report
        report_file = self.persistence_root / "certification_report.json"
        with open(report_file, "w") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "certification": self.certification,
                "decisions": self.decisions,
                "status": "COMPLETE" if self.certification["NIFTY"]["countable"] >= self.required and 
                                   self.certification["SENSEX"]["countable"] >= self.required else "IN_PROGRESS"
            }, f, indent=2)


async def main():
    logging.basicConfig(level=logging.INFO)
    
    # Parse command line args
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--persistence-root", default="data/task9")
    parser.add_argument("--live-stream-root", default="data/task9/live_stream")
    parser.add_argument("--nfo-new-entry-cutoff", default="15:30")
    parser.add_argument("--bfo-new-entry-cutoff", default="15:30")
    args = parser.parse_args()
    
    cert = Task9Certification(
        persistence_root=args.persistence_root,
        live_stream_root=args.live_stream_root
    )
    
    try:
        await cert.run()
    except KeyboardInterrupt:
        logger.info("🛑 Interrupted")
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
