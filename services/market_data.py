"""Market-data access backed by yfinance."""

import pandas as pd
import yfinance as yf


def get_stock_data(symbol):
    """Return the current summary data for a valid stock symbol.

    Raises:
        ValueError: If the symbol is invalid or its quote data is unavailable.
    """
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("A non-empty stock symbol is required.")

    try:
        info = yf.Ticker(symbol.strip()).info

        company = info.get("longName") or info.get("shortName")
        price = info.get("regularMarketPrice", info.get("currentPrice"))
        previous_close = info.get(
            "regularMarketPreviousClose", info.get("previousClose")
        )
        currency = info.get("currency")
        exchange = info.get("exchange")

        if not all(
            value is not None
            for value in (company, price, previous_close, currency, exchange)
        ):
            raise ValueError(f"Invalid symbol or unavailable quote data: {symbol}")

        return {
            "company": str(company),
            "price": float(price),
            "previous_close": float(previous_close),
            "currency": str(currency),
            "exchange": str(exchange),
        }
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"Unable to retrieve data for symbol: {symbol}") from exc


def get_chart_data(symbol, period="6mo", interval="1d"):
    """Return OHLCV historical data for a stock symbol.

    Raises:
        ValueError: If the symbol is invalid or no historical data is available.
    """
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("A non-empty stock symbol is required.")

    try:
        history = yf.Ticker(symbol.strip()).history(period=period, interval=interval)
        required_columns = ["Open", "High", "Low", "Close", "Volume"]

        if history.empty or not set(required_columns).issubset(history.columns):
            raise ValueError(f"No historical data found for symbol: {symbol}")

        return history.loc[:, required_columns].copy()
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(
            f"Unable to retrieve historical data for symbol: {symbol}"
        ) from exc
