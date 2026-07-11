"""
Angel One SmartAPI client.

Handles:
- Authentication using TOTP
- Live market data requests
- Historical candle data requests
- Option Greeks requests

No orders are placed from this client.
"""

import pyotp
from SmartApi import SmartConnect

from config import (
    ANGEL_API_KEY,
    ANGEL_CLIENT_ID,
    ANGEL_PIN,
    ANGEL_TOTP_SECRET,
)


class AngelMarketDataClient:
    """Read-only client for Angel One SmartAPI market data."""

    def __init__(self):
        if not ANGEL_API_KEY:
            raise ValueError(
                "ANGEL_API_KEY is missing."
            )

        self.api = SmartConnect(
            api_key=ANGEL_API_KEY
        )

        self.authenticated = False
        self.session = None

    # ---------------------------------
    # AUTHENTICATION
    # ---------------------------------

    def login(self):
        """
        Authenticate with Angel One using
        Client ID, PIN and TOTP.
        """

        if not ANGEL_CLIENT_ID:
            raise ValueError(
                "ANGEL_CLIENT_ID is missing."
            )

        if not ANGEL_PIN:
            raise ValueError(
                "ANGEL_PIN is missing."
            )

        if not ANGEL_TOTP_SECRET:
            raise ValueError(
                "ANGEL_TOTP_SECRET is missing."
            )

        totp = pyotp.TOTP(
            ANGEL_TOTP_SECRET
        ).now()

        response = self.api.generateSession(
            ANGEL_CLIENT_ID,
            ANGEL_PIN,
            totp,
        )

        if (
            not response
            or not response.get("status")
        ):
            message = (
                response.get(
                    "message",
                    "Unknown login error",
                )
                if isinstance(
                    response,
                    dict,
                )
                else "Unknown login error"
            )

            raise RuntimeError(
                "Angel One login failed: "
                f"{message}"
            )

        self.authenticated = True
        self.session = response

        return response

    # ---------------------------------
    # LIVE MARKET DATA
    # ---------------------------------

    def get_market_data(
        self,
        mode,
        exchange_tokens,
    ):
        """
        Fetch live market data.

        Parameters
        ----------
        mode : str
            LTP, OHLC, or FULL.

        exchange_tokens : dict
            Example:
            {
                "NSE": ["99926000"]
            }
        """

        valid_modes = {
            "LTP",
            "OHLC",
            "FULL",
        }

        mode = mode.upper()

        if mode not in valid_modes:
            raise ValueError(
                "mode must be one of: "
                "LTP, OHLC, FULL"
            )

        if not isinstance(
            exchange_tokens,
            dict,
        ):
            raise ValueError(
                "exchange_tokens must "
                "be a dictionary."
            )

        if not exchange_tokens:
            raise ValueError(
                "exchange_tokens cannot be empty."
            )

        if not self.authenticated:
            self.login()

        response = self.api.getMarketData(
            mode,
            exchange_tokens,
        )

        if not response:
            raise RuntimeError(
                "Angel One returned an empty "
                "market-data response."
            )

        if response.get("status") is False:
            raise RuntimeError(
                "Angel One market-data request "
                "failed: "
                f"{response.get('message', 'Unknown error')}"
            )

        return response

    # ---------------------------------
    # HISTORICAL CANDLE DATA
    # ---------------------------------

    def get_historical_data(
        self,
        exchange,
        symboltoken,
        interval,
        fromdate,
        todate,
    ):
        """
        Fetch historical candle data.

        Parameters
        ----------
        exchange : str
            Example: NSE.

        symboltoken : str
            Angel One symbol token.

        interval : str
            Examples:
            ONE_MINUTE
            FIVE_MINUTE
            FIFTEEN_MINUTE
            ONE_HOUR
            ONE_DAY

        fromdate : str
            Example:
            "2026-07-10 09:15"

        todate : str
            Example:
            "2026-07-10 15:30"
        """

        if not self.authenticated:
            self.login()

        params = {
            "exchange": exchange,
            "symboltoken": symboltoken,
            "interval": interval,
            "fromdate": fromdate,
            "todate": todate,
        }

        response = self.api.getCandleData(
            params
        )

        if not response:
            raise RuntimeError(
                "Angel One returned an empty "
                "historical-data response."
            )

        if response.get("status") is False:
            raise RuntimeError(
                "Angel One historical-data request "
                "failed: "
                f"{response.get('message', 'Unknown error')}"
            )

        return response

    # ---------------------------------
    # OPTION GREEKS
    # ---------------------------------

    def get_option_greeks(
        self,
        name,
        expiry_date,
    ):
        """
        Fetch option Greeks from Angel One.

        Parameters
        ----------
        name : str
            Underlying name.
            Example: NIFTY.

        expiry_date : str
            Expiry format required by
            Angel One SmartAPI.

        Returns Greeks such as:
        - Delta
        - Gamma
        - Theta
        - Vega
        - Implied volatility

        This method is read-only.
        """

        if not name:
            raise ValueError(
                "Option underlying name "
                "is required."
            )

        if not expiry_date:
            raise ValueError(
                "Option expiry date "
                "is required."
            )

        if not self.authenticated:
            self.login()

        params = {
            "name": name.upper(),
            "expirydate": expiry_date,
        }

        response = self.api.optionGreek(
            params
        )

        if not response:
            raise RuntimeError(
                "Angel One returned an empty "
                "Option Greeks response."
            )

        if response.get("status") is False:
            raise RuntimeError(
                "Angel One Option Greeks request "
                "failed: "
                f"{response.get('message', 'Unknown error')}"
            )

        return response