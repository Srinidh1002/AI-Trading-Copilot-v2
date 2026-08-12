"""Strict Angel One instrument-master service.

Downloads, validates, filters, and deterministically orders Angel option
contracts.

Read-only.
No broker order submission.
"""

from __future__ import annotations

import math
import time
from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime

import requests


INSTRUMENT_MASTER_URL = (
    "https://margincalculator.angelone.in/"
    "OpenAPI_File/files/OpenAPIScripMaster.json"
)


class AngelInstrumentMaster:
    """Read-only validated Angel instrument-master repository."""

    SOURCE_NAME = "ANGEL_ONE_OPENAPI_SCRIP_MASTER"
    DEFAULT_MAXIMUM_MASTER_AGE_SECONDS = 24 * 60 * 60

    def __init__(
        self,
        session=None,
        *,
        time_function=time.time,
        maximum_master_age_seconds=(
            DEFAULT_MAXIMUM_MASTER_AGE_SECONDS
        ),
    ):
        self.session = (
            session
            if session is not None
            else requests.Session()
        )

        if not callable(time_function):
            raise TypeError(
                "time_function must be callable."
            )

        if (
            isinstance(
                maximum_master_age_seconds,
                bool,
            )
            or not isinstance(
                maximum_master_age_seconds,
                (int, float),
            )
            or not math.isfinite(
                float(
                    maximum_master_age_seconds
                )
            )
            or float(
                maximum_master_age_seconds
            )
            <= 0
        ):
            raise ValueError(
                "maximum_master_age_seconds must "
                "be finite and greater than zero."
            )

        self.time_function = time_function
        self.maximum_master_age_seconds = float(
            maximum_master_age_seconds
        )
        self.instruments = None
        self._metadata = None

    @staticmethod
    def _required_text(
        value,
        *,
        field,
        record_index,
    ):
        if not isinstance(value, str):
            value = str(
                value
                if value is not None
                else ""
            )

        result = value.strip()

        if not result:
            raise RuntimeError(
                "Angel instrument-master record "
                f"{record_index} has blank {field}."
            )

        return result

    @staticmethod
    def _positive_float(
        value,
        *,
        field,
        record_index,
    ):
        if isinstance(value, bool):
            raise RuntimeError(
                "Angel instrument-master record "
                f"{record_index} has invalid {field}."
            )

        try:
            result = float(value)
        except (
            TypeError,
            ValueError,
        ) as exc:
            raise RuntimeError(
                "Angel instrument-master record "
                f"{record_index} has invalid {field}."
            ) from exc

        if (
            not math.isfinite(result)
            or result <= 0
        ):
            raise RuntimeError(
                "Angel instrument-master record "
                f"{record_index} has invalid {field}."
            )

        return result

    @classmethod
    def _positive_integer(
        cls,
        value,
        *,
        field,
        record_index,
    ):
        numeric = cls._positive_float(
            value,
            field=field,
            record_index=record_index,
        )

        integer = int(numeric)

        if numeric != integer:
            raise RuntimeError(
                "Angel instrument-master record "
                f"{record_index} has non-integral {field}."
            )

        return integer

    @classmethod
    def _validated_option_contract(
        cls,
        instrument,
        *,
        record_index,
        underlying,
        exchange,
    ):
        if not isinstance(instrument, Mapping):
            raise RuntimeError(
                "Angel instrument-master option "
                f"record {record_index} is not a mapping."
            )

        token = cls._required_text(
            instrument.get("token"),
            field="token",
            record_index=record_index,
        )

        symbol = cls._required_text(
            instrument.get("symbol"),
            field="symbol",
            record_index=record_index,
        ).upper()

        name = cls._required_text(
            instrument.get("name"),
            field="name",
            record_index=record_index,
        ).upper()

        expiry = cls._required_text(
            instrument.get("expiry"),
            field="expiry",
            record_index=record_index,
        )

        instrument_type = cls._required_text(
            instrument.get(
                "instrumenttype"
            ),
            field="instrumenttype",
            record_index=record_index,
        ).upper()

        exchange_segment = cls._required_text(
            instrument.get("exch_seg"),
            field="exch_seg",
            record_index=record_index,
        ).upper()

        if name != underlying:
            raise RuntimeError(
                "Angel instrument-master option "
                f"record {record_index} underlying mismatch."
            )

        if exchange_segment != exchange:
            raise RuntimeError(
                "Angel instrument-master option "
                f"record {record_index} exchange mismatch."
            )

        if instrument_type != "OPTIDX":
            raise RuntimeError(
                "Angel instrument-master option "
                f"record {record_index} type mismatch."
            )

        if symbol.endswith("CE"):
            option_type = "CE"
        elif symbol.endswith("PE"):
            option_type = "PE"
        else:
            raise RuntimeError(
                "Angel instrument-master option "
                f"record {record_index} has invalid option suffix."
            )

        parsed_expiry = cls._parse_expiry(
            expiry
        )

        if parsed_expiry is None:
            raise RuntimeError(
                "Angel instrument-master option "
                f"record {record_index} has invalid expiry."
            )

        strike = cls._positive_float(
            instrument.get("strike"),
            field="strike",
            record_index=record_index,
        )

        lot_size = cls._positive_integer(
            instrument.get("lotsize"),
            field="lotsize",
            record_index=record_index,
        )

        validated = deepcopy(
            dict(instrument)
        )

        return {
            "record": validated,
            "token": token,
            "symbol": symbol,
            "expiry_date": parsed_expiry,
            "strike": strike,
            "lot_size": lot_size,
            "option_type": option_type,
        }

    def fetch_instruments(self):
        """Download and minimally validate the Angel instrument master."""

        response = self.session.get(
            INSTRUMENT_MASTER_URL,
            timeout=30,
        )

        response.raise_for_status()

        try:
            data = response.json()
        except Exception as exc:
            raise RuntimeError(
                "Angel instrument-master response "
                "contains invalid JSON."
            ) from exc

        if not isinstance(data, list):
            raise RuntimeError(
                "Unexpected Angel One "
                "instrument-master format."
            )

        if not data:
            raise RuntimeError(
                "Angel One instrument master is empty."
            )

        copied = []

        for index, instrument in enumerate(
            data
        ):
            if not isinstance(
                instrument,
                Mapping,
            ):
                raise RuntimeError(
                    "Angel instrument-master record "
                    f"{index} is not a mapping."
                )

            copied.append(
                deepcopy(dict(instrument))
            )

        fetched_at = float(
            self.time_function()
        )

        if not math.isfinite(fetched_at):
            raise RuntimeError(
                "Instrument-master fetch timestamp "
                "must be finite."
            )

        self.instruments = copied
        self._metadata = {
            "source": self.SOURCE_NAME,
            "source_url": (
                INSTRUMENT_MASTER_URL
            ),
            "fetched_at_epoch_seconds": (
                fetched_at
            ),
            "record_count": len(copied),
            "validated": True,
        }

        return deepcopy(copied)

    def _ensure_loaded(self):
        if self.instruments is None:
            self.fetch_instruments()

        if not isinstance(
            self.instruments,
            list,
        ):
            raise RuntimeError(
                "Angel instrument master must "
                "be a list."
            )

    def _assert_fresh(self):
        """Reject stale or future provider-fetched instrument masters.

        Explicitly injected fixtures have no provider metadata and are
        preserved for deterministic tests.
        """

        if self._metadata is None:
            return

        if (
            self._metadata.get("validated")
            is not True
        ):
            raise RuntimeError(
                "Angel instrument master is not validated."
            )

        fetched_at = self._metadata.get(
            "fetched_at_epoch_seconds"
        )

        if (
            isinstance(fetched_at, bool)
            or not isinstance(
                fetched_at,
                (int, float),
            )
            or not math.isfinite(
                float(fetched_at)
            )
        ):
            raise RuntimeError(
                "Angel instrument-master fetch "
                "timestamp is invalid."
            )

        now = float(
            self.time_function()
        )

        if not math.isfinite(now):
            raise RuntimeError(
                "Instrument-master current timestamp "
                "must be finite."
            )

        age_seconds = (
            now
            - float(fetched_at)
        )

        if age_seconds < 0:
            raise RuntimeError(
                "Angel instrument-master fetch "
                "timestamp is in the future."
            )

        if (
            age_seconds
            > self.maximum_master_age_seconds
        ):
            raise RuntimeError(
                "Angel instrument master is stale."
            )

    def get_metadata(self):
        """Return defensive instrument-master provenance metadata."""

        self._ensure_loaded()

        if self._metadata is None:
            return {
                "source": self.SOURCE_NAME,
                "source_url": (
                    INSTRUMENT_MASTER_URL
                ),
                "fetched_at_epoch_seconds": None,
                "record_count": len(
                    self.instruments
                ),
                "validated": False,
                "injected_fixture": True,
            }

        return deepcopy(
            self._metadata
        )

    def get_option_contracts(
        self,
        underlying,
        exchange="NFO",
    ):
        """Return strictly validated and deterministically ordered contracts."""

        self._ensure_loaded()
        self._assert_fresh()

        underlying = str(
            underlying
        ).strip().upper()

        exchange = str(
            exchange
        ).strip().upper()

        if not underlying:
            raise ValueError(
                "underlying is required."
            )

        if not exchange:
            raise ValueError(
                "exchange is required."
            )

        candidates = []

        for index, instrument in enumerate(
            self.instruments
        ):
            if not isinstance(
                instrument,
                Mapping,
            ):
                raise RuntimeError(
                    "Angel instrument-master record "
                    f"{index} is not a mapping."
                )

            exch_seg = str(
                instrument.get(
                    "exch_seg",
                    "",
                )
            ).strip().upper()

            instrument_type = str(
                instrument.get(
                    "instrumenttype",
                    "",
                )
            ).strip().upper()

            name = str(
                instrument.get(
                    "name",
                    "",
                )
            ).strip().upper()

            if exch_seg != exchange:
                continue

            if instrument_type != "OPTIDX":
                continue

            if name != underlying:
                continue

            candidates.append(
                self._validated_option_contract(
                    instrument,
                    record_index=index,
                    underlying=underlying,
                    exchange=exchange,
                )
            )

        seen_tokens = set()
        seen_symbols = set()

        for candidate in candidates:
            token_identity = (
                exchange,
                candidate["token"],
            )

            symbol_identity = (
                exchange,
                candidate["symbol"],
            )

            if token_identity in seen_tokens:
                raise RuntimeError(
                    "Duplicate Angel option token "
                    f"for {exchange}: "
                    f"{candidate['token']}."
                )

            if symbol_identity in seen_symbols:
                raise RuntimeError(
                    "Duplicate Angel option symbol "
                    f"for {exchange}: "
                    f"{candidate['symbol']}."
                )

            seen_tokens.add(
                token_identity
            )

            seen_symbols.add(
                symbol_identity
            )

        candidates.sort(
            key=lambda item: (
                item["expiry_date"],
                item["strike"],
                item["option_type"],
                item["symbol"],
                item["token"],
            )
        )

        return [
            deepcopy(
                candidate["record"]
            )
            for candidate in candidates
        ]

    def get_available_expiries(
        self,
        underlying,
        exchange="NFO",
        include_expired=False,
    ):
        """Return deterministic unique listed expiries."""

        contracts = self.get_option_contracts(
            underlying=underlying,
            exchange=exchange,
        )

        today = datetime.now().date()

        expiries = {}

        for contract in contracts:
            raw_expiry = str(
                contract["expiry"]
            ).strip()

            parsed_date = self._parse_expiry(
                raw_expiry
            )

            if parsed_date is None:
                raise RuntimeError(
                    "Validated option contract has "
                    "an invalid expiry."
                )

            if (
                not include_expired
                and parsed_date < today
            ):
                continue

            existing = expiries.get(
                parsed_date
            )

            if (
                existing is not None
                and existing["raw"]
                != raw_expiry
            ):
                raise RuntimeError(
                    "One expiry date has conflicting "
                    "Angel raw expiry values."
                )

            expiries[parsed_date] = {
                "date": parsed_date,
                "display": (
                    parsed_date.strftime(
                        "%d%b%Y"
                    ).upper()
                ),
                "raw": raw_expiry,
            }

        return [
            deepcopy(expiries[expiry])
            for expiry in sorted(expiries)
        ]

    def get_nearest_expiry(
        self,
        underlying,
        exchange="NFO",
    ):
        """Return the nearest currently listed expiry."""

        expiries = self.get_available_expiries(
            underlying=underlying,
            exchange=exchange,
        )

        if not expiries:
            raise ValueError(
                "No active option expiries found "
                f"for {underlying}."
            )

        return deepcopy(
            expiries[0]
        )

    @staticmethod
    def _parse_expiry(value):
        """Parse supported Angel expiry formats."""

        formats = (
            "%d%b%Y",
            "%d%b%y",
            "%Y-%m-%d",
            "%d-%b-%Y",
            "%d-%b-%y",
        )

        cleaned = str(
            value
        ).strip().upper()

        if not cleaned:
            return None

        for date_format in formats:
            try:
                return datetime.strptime(
                    cleaned,
                    date_format,
                ).date()
            except ValueError:
                continue

        return None
