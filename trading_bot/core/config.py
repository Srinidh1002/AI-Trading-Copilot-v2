# trading_bot/core/config.py
# Configuration management

import os
import json
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, Any, Optional

load_dotenv()


class Config:
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file or "config.json"
        self._config = self._load_config()
        self._load_env()

    def _load_config(self) -> Dict[str, Any]:
        default_config = {
            "trading": {
                "capital": 1000000,
                "max_positions": 2,
                "max_positions_per_market": 1,
                "targets": {"T1": 0.15, "T2": 0.30, "T3": 0.50},
                "stop_loss_pct": 0.05,
                "cooldown_seconds": 15,
                "max_trades_per_day": 10
            },
            "market": {
                "symbols": ["NIFTY", "SENSEX"],
                "expiry_offset_days": 7,
                "warmup_cycles": 10
            },
            "data": {
                "freshness_threshold": 2,
                "max_stale_cycles": 5
            },
            "certification": {
                "nifty_required": 100,
                "sensex_required": 100,
                "paper_mode": True
            }
        }
        config_path = Path(self.config_file)
        if config_path.exists():
            with open(config_path, "r") as f:
                loaded = json.load(f)
                self._deep_merge(default_config, loaded)
        return default_config

    def _deep_merge(self, target: dict, source: dict):
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_merge(target[key], value)
            else:
                target[key] = value

    def _load_env(self):
        self.api_key = os.getenv("ANGEL_API_KEY", "") or os.getenv("ANGEL_APIKEY", "")
        self.client_id = os.getenv("ANGEL_CLIENT_ID", "")
        self.pin = os.getenv("ANGEL_PIN", "")
        self.totp_secret = os.getenv("ANGEL_TOTP_SECRET", "")
        if os.getenv("CAPITAL"):
            self._config["trading"]["capital"] = float(os.getenv("CAPITAL"))

    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    @property
    def is_paper_mode(self) -> bool:
        return self.get("certification.paper_mode", True)

    @property
    def capital(self) -> float:
        return self.get("trading.capital", 1000000)

    @property
    def targets(self) -> dict:
        return self.get("trading.targets", {"T1": 0.15, "T2": 0.30, "T3": 0.50})

    @property
    def stop_loss_pct(self) -> float:
        return self.get("trading.stop_loss_pct", 0.05)

    @property
    def symbols(self) -> list:
        return self.get("market.symbols", ["NIFTY", "SENSEX"])

    @property
    def max_positions(self) -> int:
        return self.get("trading.max_positions", 2)

    @property
    def max_positions_per_market(self) -> int:
        return self.get("trading.max_positions_per_market", 1)

    @property
    def nifty_required(self) -> int:
        return self.get("certification.nifty_required", 100)

    @property
    def sensex_required(self) -> int:
        return self.get("certification.sensex_required", 100)
