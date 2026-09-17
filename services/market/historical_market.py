"""
Unsupported legacy historical market compatibility service.

This module is intentionally isolated from Task 8/9 certified production,
replay, and dashboard authority.  It remains only for its local legacy test;
supported historical reads use LiveMultiTimeframeData instead.
"""

import pandas as pd

from services.broker.session_manager import SessionManager


class HistoricalMarket:

    def __init__(self):

        self.session = SessionManager()

    # --------------------------------------------------

    def get_data(
        self,
        exchange,
        token,
        interval,
        from_date,
        to_date,
    ):

        params = {

            "exchange": exchange,

            "symboltoken": token,

            "interval": interval,

            "fromdate": from_date,

            "todate": to_date,

        }

        response = self.session.execute(
            self.session.api.getCandleData,
            params,
        )

        return self.normalize(response)

    # --------------------------------------------------

    @staticmethod
    def normalize(response):

        if not response:

            raise ValueError(
                "Historical API returned empty response."
            )

        if not response.get("status", False):

            raise ValueError(
                response.get(
                    "message",
                    "Historical API Error",
                )
            )

        candles = response.get("data")

        if not candles:

            raise ValueError(
                "No candle data returned."
            )

        df = pd.DataFrame(

            candles,

            columns=[
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
            ],

        )

        df["timestamp"] = pd.to_datetime(
            df["timestamp"]
        )

        numeric = [
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]

        for column in numeric:

            df[column] = pd.to_numeric(
                df[column],
                errors="coerce",
            )

        df.dropna(inplace=True)

        df.sort_values(
            "timestamp",
            inplace=True,
        )

        df.reset_index(
            drop=True,
            inplace=True,
        )

        return df
