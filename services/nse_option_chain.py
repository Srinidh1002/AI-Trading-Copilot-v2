"""
Live NSE Option Chain
"""

from nselib import derivatives
import traceback


def get_nifty_option_chain():

    try:

        data = derivatives.nse_live_option_chain("NIFTY")

        return data

    except Exception as e:

        print("\nERROR OCCURRED\n")

        traceback.print_exc()

        print(e)

        return None