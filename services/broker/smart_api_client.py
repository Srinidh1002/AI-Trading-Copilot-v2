"""
==============================================================
SmartAPI Client
==============================================================

Centralized Angel One SmartAPI Client

Features
--------
✓ Singleton Pattern
✓ Automatic Login
✓ Automatic TOTP Generation
✓ JWT Storage
✓ Refresh Token Storage
✓ Feed Token Storage
✓ User Profile
✓ LTP Helper
✓ Holdings Helper
✓ Positions Helper
✓ Orders Helper
✓ Profile Helper
✓ Reusable Across Entire Project
==============================================================
"""

from __future__ import annotations

from typing import Any, Dict, List

import pyotp
from SmartApi import SmartConnect

from config import (
    SMART_API_KEY,
    SMART_CLIENT_ID,
    SMART_PASSWORD,
    SMART_TOTP,
)


class SmartAPIClient:

    _instance = None

    # -----------------------------------------------------

    def __new__(cls):

        if cls._instance is None:
            cls._instance = super().__new__(cls)

        return cls._instance

    # -----------------------------------------------------

    def __init__(self):

        if hasattr(self, "_initialized"):
            return

        self._initialized = True

        self.api = None

        self.jwt_token = ""

        self.refresh_token = ""

        self.feed_token = ""

        self.profile = {}

        self.login()

    # -----------------------------------------------------

    def login(self):

        print("\n" + "=" * 60)
        print("Connecting to Angel One...")
        print("=" * 60)

        otp = pyotp.TOTP(
            SMART_TOTP
        ).now()

        self.api = SmartConnect(
            api_key=SMART_API_KEY
        )

        response = self.api.generateSession(
            SMART_CLIENT_ID,
            SMART_PASSWORD,
            otp,
        )

        if not response.get("status", False):

            raise Exception(
                response.get(
                    "message",
                    "Login Failed"
                )
            )

        data = response["data"]

        self.jwt_token = data["jwtToken"]

        self.refresh_token = data["refreshToken"]

        self.feed_token = data["feedToken"]

        self.profile = {

            "Client ID": data["clientcode"],

            "Name": data["name"],

            "Exchanges": data["exchanges"],

            "Products": data["products"],

        }

        print("✓ Login Successful")
        print("✓ Feed Token Generated")
        print("=" * 60)

    # -----------------------------------------------------

    def reconnect(self):

        print("\nReconnecting...\n")

        self.login()

    # -----------------------------------------------------

    def is_logged_in(self):

        return self.api is not None

    # -----------------------------------------------------

    def get_api(self):

        return self.api

    # -----------------------------------------------------

    def get_profile(self):

        return self.profile

    # -----------------------------------------------------

    def get_feed_token(self):

        return self.feed_token

    # -----------------------------------------------------

    def get_jwt(self):

        return self.jwt_token

    # -----------------------------------------------------

    def get_refresh_token(self):

        return self.refresh_token

    # =====================================================
    # MARKET HELPERS
    # =====================================================

    def ltp(
        self,
        exchange: str,
        symbol: str,
        token: str,
    ) -> Dict[str, Any]:

        response = self.api.ltpData(
            exchange,
            symbol,
            token,
        )

        if not response.get("status", False):

            raise Exception(
                response.get("message")
            )

        return response["data"]

    # =====================================================
    # ACCOUNT HELPERS
    # =====================================================

    def holdings(self):

        response = self.api.holding()

        if not response:
            return []

        if not response.get("status", False):
            return []

        return response.get("data") or []

    # -----------------------------------------------------

    def positions(self):

        response = self.api.position()

        if not response:
            return []

        if not response.get("status", False):
            return []

        return response.get("data") or []

    # -----------------------------------------------------

    def order_book(self):

        response = self.api.orderBook()

        if not response:
            return []

        if not response.get("status", False):
            return []

        return response.get("data") or []

    # -----------------------------------------------------

    def trade_book(self):

        response = self.api.tradeBook()

        if not response:
            return []

        if not response.get("status", False):
            return []

        return response.get("data") or []

    # =====================================================
    # INFORMATION
    # =====================================================

    def summary(self):

        return {

            "Logged In": self.is_logged_in(),

            "Client": self.profile.get("Client ID"),

            "Name": self.profile.get("Name"),

            "JWT": self.jwt_token[:40] + "...",

            "Feed Token": self.feed_token[:40] + "...",

        }