# services/core/system_controller.py
# FIXED - Removed psutil dependency

import asyncio
import signal
import logging
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class SystemController:
    """Handles graceful shutdown, auto-reconnect, and system state"""
    
    def __init__(self, state_file: str = "data/system_state.json"):
        self.state_file = Path(state_file)
        self.is_running = False
        self.is_shutting_down = False
        self.components = {}
        self.state = self._load_state()
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        self.reconnect_delay = 5
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Create state directory
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"⚠️ Signal {signum} received. Starting graceful shutdown...")
        self._graceful_shutdown()
        
    def _graceful_shutdown(self):
        """Perform graceful shutdown"""
        if self.is_shutting_down:
            return
            
        self.is_shutting_down = True
        logger.info("🛑 Initiating graceful shutdown...")
        
        # Save current state
        self._save_state()
        
        # Stop all components
        for name, component in self.components.items():
            try:
                if hasattr(component, 'stop'):
                    component.stop()
                    logger.info(f"✅ Stopped: {name}")
            except Exception as e:
                logger.error(f"❌ Error stopping {name}: {e}")
        
        # Close connections
        try:
            # Close any open WebSocket connections
            pass
        except:
            pass
        
        self.is_running = False
        logger.info("✅ Graceful shutdown complete")
        
        # Final state save
        self._save_state()
        
        # Exit cleanly
        os._exit(0)
    
    def register_component(self, name: str, component):
        """Register a component for shutdown management"""
        self.components[name] = component
        
    async def handle_connection_loss(self):
        """Handle connection loss and auto-reconnect"""
        self.reconnect_attempts += 1
        
        if self.reconnect_attempts > self.max_reconnect_attempts:
            logger.error("❌ Max reconnection attempts reached")
            self._graceful_shutdown()
            return False
        
        logger.info(f"🔄 Reconnection attempt {self.reconnect_attempts}/{self.max_reconnect_attempts}")
        logger.info(f"⏳ Waiting {self.reconnect_delay} seconds...")
        
        await asyncio.sleep(self.reconnect_delay)
        self.reconnect_attempts = 0
        return True
    
    def _load_state(self) -> Dict:
        """Load system state from file"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {
            'last_start': None,
            'last_shutdown': None,
            'total_cycles': 0,
            'total_trades': 0,
            'status': 'stopped',
            'current_positions': []
        }
    
    def _save_state(self):
        """Save system state to file"""
        try:
            self.state['last_shutdown'] = datetime.now().isoformat()
            self.state['status'] = 'stopped' if self.is_shutting_down else 'running'
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving state: {e}")
    
    def update_state(self, **kwargs):
        """Update system state"""
        for key, value in kwargs.items():
            self.state[key] = value
        self._save_state()
    
    def get_state(self) -> Dict:
        """Get current system state"""
        return self.state
    
    async def wait_for_power_restore(self):
        """Wait for power restore and reconnect"""
        logger.info("⚡ Power restored. Reconnecting...")
        await asyncio.sleep(2)  # Wait for stable connection
        return await self.handle_connection_loss()
    
    def is_healthy(self) -> bool:
        """Check if system is healthy"""
        # Check if we're still running
        if not self.is_running:
            return False
        
        # Check components
        for name, component in self.components.items():
            if hasattr(component, 'is_healthy'):
                if not component.is_healthy():
                    logger.warning(f"⚠️ Component {name} is not healthy")
                    return False
        
        return True

# Utility function for power failure simulation
class PowerMonitor:
    """Monitors system for power failures"""
    
    def __init__(self):
        self.last_power_check = datetime.now()
        self.power_failure_detected = False
        
    def check_power(self):
        """Check if power is stable"""
        # In production, this would check UPS status
        # For now, just return True
        return True
    
    async def monitor(self, controller: SystemController):
        """Monitor power and trigger reconnect"""
        while True:
            if not self.check_power():
                logger.warning("⚡ Power failure detected!")
                self.power_failure_detected = True
                await controller.wait_for_power_restore()
            
            await asyncio.sleep(10)
