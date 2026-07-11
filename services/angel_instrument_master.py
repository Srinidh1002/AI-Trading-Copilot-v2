"""
Angel One instrument-master service.

Downloads and filters the Angel One instrument master to discover
currently listed option contracts and expiries.

Read-only. No orders are placed.
"""

from datetime import datetime

import requests


INSTRUMENT_MASTER_URL = (
    "https://margincalculator.angelone.in/"
    "OpenAPI_File/files/OpenAPIScripMaster.json"
)


class AngelInstrumentMaster:

    def __init__(self, session=None):
        self.session = (
            session
            if session is not None
            else requests.Session()
        )

        self.instruments = None

    def fetch_instruments(self):
        """
        Download the Angel One instrument master.
        """

        response = self.session.get(
            INSTRUMENT_MASTER_URL,
            timeout=30,
        )

        response.raise_for_status()

        data = response.json()

        if not isinstance(data, list):
            raise RuntimeError(
                "Unexpected Angel One instrument-master format."
            )

        self.instruments = data

        return data

    def _ensure_loaded(self):
        """
        Load instruments if they have not already been fetched.
        """

        if self.instruments is None:
            self.fetch_instruments()

    def get_option_contracts(
        self,
        underlying,
        exchange="NFO",
    ):
        """
        Return listed option contracts for an underlying.

        Example:
            underlying="NIFTY"
        """

        self._ensure_loaded()

        underlying = underlying.upper()

        contracts = []

        for instrument in self.instruments:

            exch_seg = str(
                instrument.get(
                    "exch_seg",
                    ""
                )
            ).upper()

            instrument_type = str(
                instrument.get(
                    "instrumenttype",
                    ""
                )
            ).upper()

            symbol = str(
                instrument.get(
                    "symbol",
                    ""
                )
            ).upper()

            name = str(
                instrument.get(
                    "name",
                    ""
                )
            ).upper()

            if exch_seg != exchange.upper():
                continue

            if instrument_type != "OPTIDX":
                continue

            if name != underlying:
                continue

            if not (
                symbol.endswith("CE")
                or symbol.endswith("PE")
            ):
                continue

            contracts.append(
                instrument
            )

        return contracts

    def get_available_expiries(
        self,
        underlying,
        exchange="NFO",
        include_expired=False,
    ):
        """
        Return sorted unique expiry dates.

        Output format:
            [
                {
                    "date": date_object,
                    "display": "14JUL2026",
                    "raw": "14JUL2026"
                }
            ]
        """

        contracts = self.get_option_contracts(
            underlying=underlying,
            exchange=exchange,
        )

        today = datetime.now().date()

        expiries = {}

        for contract in contracts:

            raw_expiry = str(
                contract.get(
                    "expiry",
                    ""
                )
            ).strip()

            if not raw_expiry:
                continue

            parsed_date = self._parse_expiry(
                raw_expiry
            )

            if parsed_date is None:
                continue

            if (
                not include_expired
                and parsed_date < today
            ):
                continue

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
            expiries[expiry]
            for expiry in sorted(expiries)
        ]

    def get_nearest_expiry(
        self,
        underlying,
        exchange="NFO",
    ):
        """
        Return the nearest currently listed expiry.
        """

        expiries = self.get_available_expiries(
            underlying=underlying,
            exchange=exchange,
        )

        if not expiries:
            raise ValueError(
                f"No active option expiries found for {underlying}."
            )

        return expiries[0]

    @staticmethod
    def _parse_expiry(value):
        """
        Parse common Angel One expiry formats.
        """

        formats = (
            "%d%b%Y",
            "%d%b%y",
            "%Y-%m-%d",
            "%d-%b-%Y",
            "%d-%b-%y",
        )

        cleaned = (
            str(value)
            .strip()
            .upper()
        )

        for date_format in formats:
            try:
                return datetime.strptime(
                    cleaned,
                    date_format,
                ).date()

            except ValueError:
                continue

        return None