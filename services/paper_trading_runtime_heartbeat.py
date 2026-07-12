"""
Paper Trading Runtime Heartbeat.

Persists the latest paper-trading runtime health snapshot
to a JSON file for operational visibility across restarts.

IMPORTANT:
- PAPER TRADING ONLY.
- STATUS PERSISTENCE ONLY.
- NO BROKER ORDERS ARE PLACED.
"""

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path


class PaperTradingRuntimeHeartbeat:
    """
    Persist and retrieve the latest runtime heartbeat.
    """

    DEFAULT_FILE_PATH = (
        Path("data")
        / "paper_trading_runtime_heartbeat.json"
    )

    def __init__(
        self,
        file_path=None,
        *,
        clock=None,
    ):
        self.file_path = Path(
            file_path
            if file_path is not None
            else self.DEFAULT_FILE_PATH
        )

        self.clock = (
            clock
            if clock is not None
            else self._utc_now
        )

        if not callable(
            self.clock
        ):
            raise ValueError(
                "clock must be callable."
            )

    @staticmethod
    def _utc_now():
        return datetime.now(
            timezone.utc
        )

    def _timestamp(self):
        value = self.clock()

        if not isinstance(
            value,
            datetime,
        ):
            raise ValueError(
                "clock must return a datetime."
            )

        if value.tzinfo is None:
            value = value.replace(
                tzinfo=timezone.utc
            )

        return value.isoformat()

    def write(
        self,
        health_snapshot,
    ):
        """
        Persist the latest runtime health snapshot.
        """

        if not isinstance(
            health_snapshot,
            dict,
        ):
            raise ValueError(
                "health_snapshot must be a dictionary."
            )

        payload = {
            "heartbeat_at": (
                self._timestamp()
            ),
            "health_snapshot": deepcopy(
                health_snapshot
            ),
        }

        parent = (
            self.file_path.parent
        )

        parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_path = (
            self.file_path.with_suffix(
                self.file_path.suffix
                + ".tmp"
            )
        )

        with temporary_path.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                payload,
                file,
                indent=2,
                ensure_ascii=False,
                default=str,
            )

        temporary_path.replace(
            self.file_path
        )

        return deepcopy(
            payload
        )

    def read(
        self,
    ):
        """
        Read the latest persisted heartbeat.

        Returns None when no heartbeat exists.
        """

        if not self.file_path.exists():
            return None

        try:
            with self.file_path.open(
                "r",
                encoding="utf-8",
            ) as file:
                payload = json.load(
                    file
                )

        except (
            OSError,
            json.JSONDecodeError,
        ) as exc:
            raise RuntimeError(
                "Unable to read runtime heartbeat."
            ) from exc

        if not isinstance(
            payload,
            dict,
        ):
            raise RuntimeError(
                "Runtime heartbeat must contain a dictionary."
            )

        if not isinstance(
            payload.get(
                "heartbeat_at"
            ),
            str,
        ):
            raise RuntimeError(
                "Runtime heartbeat timestamp is invalid."
            )

        if not isinstance(
            payload.get(
                "health_snapshot"
            ),
            dict,
        ):
            raise RuntimeError(
                "Runtime heartbeat health snapshot is invalid."
            )

        return deepcopy(
            payload
        )

    def exists(
        self,
    ):
        """
        Return whether a persisted heartbeat exists.
        """

        return self.file_path.exists()