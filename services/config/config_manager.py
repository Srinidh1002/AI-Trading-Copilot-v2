"""
Config Manager

Central configuration manager for the
AI Trading Copilot.

Responsibilities
----------------
✓ Load Configuration
✓ Save Configuration
✓ Environment Overrides
✓ Runtime Updates
✓ Configuration Validation
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class ConfigManager:

    def __init__(
        self,
        config_file: str = "config.json",
    ):

        self.config_path = Path(config_file)

        self.config: dict[str, Any] = {}

        if self.config_path.exists():

            self.load()

    # --------------------------------------------------

    def load(self) -> dict[str, Any]:

        if not self.config_path.exists():

            self.config = {}

            return self.config

        with self.config_path.open(
            "r",
            encoding="utf-8",
        ) as file:

            self.config = json.load(file)

        return self.config

    # --------------------------------------------------

    def save(self):

        self.config_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with self.config_path.open(
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(

                self.config,

                file,

                indent=4,

                default=str,

            )

    # --------------------------------------------------

    def get(
        self,
        key: str,
        default: Any = None,
    ) -> Any:

        return self.config.get(
            key,
            default,
        )

    # --------------------------------------------------

    def set(
        self,
        key: str,
        value: Any,
    ):

        self.config[key] = value

    # --------------------------------------------------

    def update(
        self,
        values: dict[str, Any],
    ):

        self.config.update(values)

    # --------------------------------------------------

    def remove(
        self,
        key: str,
    ) -> bool:

        return (

            self.config.pop(
                key,
                None,
            )

            is not None

        )

    # --------------------------------------------------

    def load_environment(
        self,
        mapping: dict[str, str],
    ):

        for config_key, env_name in mapping.items():

            value = os.getenv(env_name)

            if value is not None:

                self.config[config_key] = value

    # --------------------------------------------------

    def exists(
        self,
        key: str,
    ) -> bool:

        return key in self.config

    # --------------------------------------------------

    def validate(
        self,
        required_keys: list[str],
    ) -> bool:

        return all(

            key in self.config

            and self.config[key] is not None

            for key in required_keys

        )

    # --------------------------------------------------

    def summary(self):

        return {

            "config_file": str(self.config_path),

            "entries": len(self.config),

            "keys": sorted(

                self.config.keys()

            ),

        }

    # --------------------------------------------------

    def clear(self):

        self.config.clear()