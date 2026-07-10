"""
Live NSE Option Chain
"""

from services.nse_client import NSEClient

client = NSEClient()


def get_option_chain(symbol="NIFTY"):

    return client.option_chain(symbol)