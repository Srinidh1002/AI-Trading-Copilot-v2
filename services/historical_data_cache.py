"""
Persistent historical market-data cache.

Purpose:
- Reduce repeated historical-data requests across subprocess runs.
- Persist only successfully validated candle responses.
- Never fabricate market data.
- Never use expired cache entries.
- Use atomic file replacement.

Read-only market-data infrastructure.
No order placement.
"""

import json
import os
import time
from copy import deepcopy
from pathlib import Path


class HistoricalDataCache:
    """
    Persistent JSON cache for historical candle responses.

    Cache entries are isolated by:
    - exchange
    - symbol token
    - timeframe

    Expired, malformed, or missing entries are treated as cache misses.
    """

    SCHEMA_VERSION = 1

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

        self.file_path = Path(
            file_path
        )

        self.time_function = (
            time_function
        )

    # ---------------------------------------------------------
    # KEY
    # ---------------------------------------------------------

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

    # ---------------------------------------------------------
    # DOCUMENT
    # ---------------------------------------------------------

    @classmethod
    def _empty_document(
        cls,
    ):
        return {
            "version": (
                cls.SCHEMA_VERSION
            ),
            "entries": {},
        }

    def _read_document(
        self,
    ):
        """
        Read the cache document.

        Invalid cache files are treated as empty cache state.
        Corrupt cache data must never block a fresh broker request.
        """

        if not self.file_path.exists():
            return self._empty_document()

        try:
            with self.file_path.open(
                "r",
                encoding="utf-8",
            ) as file:
                document = json.load(
                    file
                )

        except (
            json.JSONDecodeError,
            OSError,
        ):
            return self._empty_document()

        if not isinstance(
            document,
            dict,
        ):
            return self._empty_document()

        if (
            document.get(
                "version"
            )
            != self.SCHEMA_VERSION
        ):
            return self._empty_document()

        entries = document.get(
            "entries"
        )

        if not isinstance(
            entries,
            dict,
        ):
            return self._empty_document()

        return {
            "version": (
                self.SCHEMA_VERSION
            ),
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
                self.file_path.name
                + ".tmp"
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

                os.fsync(
                    file.fileno()
                )

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

    # ---------------------------------------------------------
    # READ
    # ---------------------------------------------------------

    def get(
        self,
        exchange,
        symboltoken,
        timeframe,
        *,
        max_age_seconds,
    ):
        """
        Return cached candle response when still fresh.

        Returns None for:
        - missing entries
        - expired entries
        - malformed entries
        """

        max_age_seconds = float(
            max_age_seconds
        )

        if max_age_seconds < 0:
            raise ValueError(
                "max_age_seconds cannot be negative."
            )

        key = self.build_key(
            exchange,
            symboltoken,
            timeframe,
        )

        document = (
            self._read_document()
        )

        entry = (
            document[
                "entries"
            ].get(
                key
            )
        )

        if not isinstance(
            entry,
            dict,
        ):
            return None

        cached_at = entry.get(
            "cached_at"
        )

        response = entry.get(
            "response"
        )

        if not isinstance(
            cached_at,
            (
                int,
                float,
            ),
        ):
            return None

        if not isinstance(
            response,
            dict,
        ):
            return None

        age_seconds = (
            self.time_function()
            - float(
                cached_at
            )
        )

        if age_seconds < 0:
            return None

        if (
            age_seconds
            > max_age_seconds
        ):
            return None

        return deepcopy(
            response
        )

    # ---------------------------------------------------------
    # WRITE
    # ---------------------------------------------------------

    def set(
        self,
        exchange,
        symboltoken,
        timeframe,
        response,
    ):
        """
        Persist one successful historical-data response.
        """

        if not isinstance(
            response,
            dict,
        ):
            raise TypeError(
                "response must be a dictionary."
            )

        data = response.get(
            "data"
        )

        if not isinstance(
            data,
            list,
        ):
            raise ValueError(
                "Historical response data must be a list."
            )

        if not data:
            raise ValueError(
                "Empty historical data cannot be cached."
            )

        key = self.build_key(
            exchange,
            symboltoken,
            timeframe,
        )

        document = (
            self._read_document()
        )

        document[
            "entries"
        ][
            key
        ] = {
            "cached_at": (
                float(
                    self.time_function()
                )
            ),
            "response": deepcopy(
                response
            ),
        }

        self._write_document(
            document
        )

        return deepcopy(
            response
        )