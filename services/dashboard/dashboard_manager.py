# services/dashboard/dashboard_manager.py - FIXED

import logging
from pathlib import Path
import json

logger = logging.getLogger(__name__)

class DashboardManager:
    """Dashboard manager for the trading system."""
    
    def __init__(self):
        self.is_running = False
        self.data_dir = Path("data/dashboard")
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    async def start(self):
        """Start the dashboard manager."""
        self.is_running = True
        logger.info("[DASHBOARD] Dashboard manager started")
        return True
    
    async def stop(self):
        """Stop the dashboard manager."""
        self.is_running = False
        logger.info("[DASHBOARD] Dashboard manager stopped")
    
    def update_data(self, data):
        """Update dashboard data."""
        try:
            import json
            from datetime import datetime
            
            file_path = self.data_dir / f"dashboard_{datetime.now().strftime('%Y-%m-%d')}.json"
            
            # Read existing data if any
            existing_data = {}
            if file_path.exists():
                with open(file_path, 'r') as f:
                    existing_data = json.load(f)
            
            # Update with new data
            existing_data.update(data)
            existing_data['updated_at'] = datetime.now().isoformat()
            
            with open(file_path, 'w') as f:
                json.dump(existing_data, f, indent=2, default=str)
            
            return True
        except Exception as e:
            logger.error(f"[DASHBOARD] Failed to update data: {e}")
            return False
