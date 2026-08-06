"""Persistent historical market-data cache.

Purpose:
- Reduce repeated historical-data requests across subprocess runs.
- Persist only successfully validated candle responses.
- Never fabricate market data.
- Never use expired cache entries.
- Return explicit cache provenance and freshness metadata.
- Use atomic file replacement.

Read-only market-data infrastructure.
No order placement.
"""

import json
import math
import os
import time
from copy import deepcopy
from pathlib import Path


class HistoricalDataCache:
    """Persistent JSON cache for historical candle responses."""

    SCHEMA_VERSION = 1
    DEFAULT_SOURCE = "ANGEL_ONE_HISTORICAL"

    def __init__(
        self,
        file_path=None,
        *,
        time_function=time.time,
    ):
        if file_path is None:
            file_path = (
                "data/market_data_cache/"
                "historical_data_cache.json"
            )

        self.file_path = Path(file_path)

        if not callable(time_function):
            raise TypeError(
                "time_function must be callable."
            )

        self.time_function = time_function

    @staticmethod
    def build_key(
        exchange,
        symboltoken,
        timeframe,
    ):
        exchange = str(
            exchange
        ).strip().upper()

        symboltoken = str(
            symboltoken
        ).strip()

        timeframe = str(
            timeframe
        ).strip().lower()

        if not exchange:
            raise ValueError(
                "exchange is required."
            )

        if not symboltoken:
            raise ValueError(
                "symboltoken is required."
            )

        if not timeframe:
            raise ValueError(
                "timeframe is required."
            )

        return (
            f"{exchange}:"
            f"{symboltoken}:"
            f"{timeframe}"
        )

    @classmethod
    def _empty_document(cls):
        return {
            "version": cls.SCHEMA_VERSION,
            "entries": {},
        }

    def _read_document(self):
        if not self.file_path.exists():
            return self._empty_document()

        try:
            with self.file_path.open(
                "r",
                encoding="utf-8",
            ) as file:
                document = json.load(file)
        except (
            json.JSONDecodeError,
            OSError,
        ):
            return self._empty_document()

        if not isinstance(document, dict):
            return self._empty_document()

        if (
            document.get("version")
            != self.SCHEMA_VERSION
        ):
            return self._empty_document()

        entries = document.get("entries")

        if not isinstance(entries, dict):
            return self._empty_document()

        return {
            "version": self.SCHEMA_VERSION,
            "entries": entries,
        }

    def _write_document(
        self,
        document,
    ):
        self.file_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_path = (
            self.file_path.with_name(
                self.file_path.name + ".tmp"
            )
        )

        try:
            with temporary_path.open(
                "w",
                encoding="utf-8",
            ) as file:
                json.dump(
                    document,
                    file,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )

                file.flush()
                os.fsync(file.fileno())

            os.replace(
                temporary_path,
                self.file_path,
            )
        except Exception:
            try:
                if temporary_path.exists():
                    temporary_path.unlink()
            except OSError:
                pass

            raise

    @staticmethod
    def _max_age(
        value,
    ):
        if isinstance(value, bool):
            raise ValueError(
                "max_age_seconds must be numeric."
            )

        try:
            result = float(value)
        except (
            TypeError,
            ValueError,
        ) as exc:
            raise ValueError(
                "max_age_seconds must be numeric."
            ) from exc

        if (
            not math.isfinite(result)
            or result < 0
        ):
            raise ValueError(
                "max_age_seconds must be finite "
                "and non-negative."
            )

        return result

    def get_with_metadata(
        self,
        exchange,
        symboltoken,
        timeframe,
        *,
        max_age_seconds,
    ):
        """Return a cache result containing response and provenance metadata."""

        max_age_seconds = self._max_age(
            max_age_seconds
        )

        key = self.build_key(
            exchange,
            symboltoken,
            timeframe,
        )

        document = self._read_document()

        entry = document[
            "entries"
        ].get(key)

        if not isinstance(entry, dict):
            return None

        cached_at = entry.get(
            "cached_at"
        )
        response = entry.get(
            "response"
        )
        source = entry.get(
            "source",
            self.DEFAULT_SOURCE,
        )

        if (
            isinstance(cached_at, bool)
            or not isinstance(
                cached_at,
                (
                    int,
                    float,
                ),
            )
            or not math.isfinite(
                float(cached_at)
            )
        ):
            return None

        if not isinstance(response, dict):
            return None

        if (
            not isinstance(source, str)
            or not source.strip()
        ):
            return None

        now = float(
            self.time_function()
        )

        if not math.isfinite(now):
            return None

        cached_at = float(
            cached_at
        )

        age_seconds = (
            now - cached_at
        )

        if age_seconds < 0:
            return None

        expires_at = (
            cached_at
            + max_age_seconds
        )

        if age_seconds > max_age_seconds:
            return None

        return {
            "response": deepcopy(response),
            "metadata": {
                "cache_status": "HIT",
                "cache_source": source.strip(),
                "cache_key": key,
                "cached_at_epoch_seconds": cached_at,
                "read_at_epoch_seconds": now,
                "age_seconds": age_seconds,
                "max_age_seconds": max_age_seconds,
                "expires_at_epoch_seconds": expires_at,
                "expired": False,
            },
        }

    def get(
        self,
        exchange,
        symboltoken,
        timeframe,
        *,
        max_age_seconds,
    ):
        """Compatibility response-only cache accessor."""

        result = self.get_with_metadata(
            exchange,
            symboltoken,
            timeframe,
            max_age_seconds=max_age_seconds,
        )

        if result is None:
            return None

        return deepcopy(
            result["response"]
        )

    def set(
        self,
        exchange,
        symboltoken,
        timeframe,
        response,
        *,
        source=DEFAULT_SOURCE,
    ):
        """Persist one successful historical-data response."""

        if not isinstance(response, dict):
            raise TypeError(
                "response must be a dictionary."
            )

        data = response.get("data")

        if not isinstance(data, list):
            raise ValueError(
                "Historical response data must be a list."
            )

        if not data:
            raise ValueError(
                "Empty historical data cannot be cached."
            )

        source = str(
            source
        ).strip()

        if not source:
            raise ValueError(
                "source is required."
            )

        key = self.build_key(
            exchange,
            symboltoken,
            timeframe,
        )

        cached_at = float(
            self.time_function()
        )

        if not math.isfinite(cached_at):
            raise ValueError(
                "cache timestamp must be finite."
            )

        document = self._read_document()

        document[
            "entries"
        ][key] = {
            "cached_at": cached_at,
            "source": source,
            "response": deepcopy(response),
        }

        self._write_document(
            document
        )

        return deepcopy(response)
