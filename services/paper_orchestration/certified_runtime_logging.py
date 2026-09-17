from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping


_RESERVED_SECRET_TOKENS = (
    "PIN",
    "PASSWORD",
    "SECRET",
    "TOKEN",
    "API_KEY",
    "TOTP",
)


def _safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Mapping):
        result = {}
        for key, item in value.items():
            name = str(key)
            upper = name.upper()
            result[name] = (
                "[REDACTED]"
                if any(token in upper for token in _RESERVED_SECRET_TOKENS)
                else _safe(item)
            )
        return result
    if isinstance(value, (tuple, list)):
        return [_safe(item) for item in value]
    if value is None or type(value) in (bool, int, float, str):
        return value
    return str(value)


class CertifiedJsonLineLogger:
    def __init__(
        self,
        *,
        file_path: str | Path,
        logger_name: str = "certified-paper-runtime",
    ) -> None:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.file_path = path
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False

        absolute = str(path.resolve())
        for handler in self.logger.handlers:
            if (
                isinstance(handler, logging.FileHandler)
                and handler.baseFilename == absolute
            ):
                self._handler = handler
                break
        else:
            handler = logging.FileHandler(
                path,
                encoding="utf-8",
            )
            handler.setFormatter(logging.Formatter("%(message)s"))
            self.logger.addHandler(handler)
            self._handler = handler

    def emit(
        self,
        *,
        event: str,
        occurred_at: datetime,
        fields: Mapping[str, Any] | None = None,
    ) -> None:
        if type(event) is not str or not event.strip():
            raise ValueError("event must be non-empty")
        if not isinstance(occurred_at, datetime):
            raise TypeError("occurred_at")
        if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
            raise ValueError("occurred_at must be timezone-aware")

        payload = {
            "event": event.strip().upper(),
            "occurred_at": occurred_at.isoformat(),
            "execution_mode": "PAPER",
            "live_execution_eligible": False,
            **_safe(dict(fields or {})),
        }
        self.logger.info(
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
        )

    def close(self) -> None:
        self._handler.flush()
